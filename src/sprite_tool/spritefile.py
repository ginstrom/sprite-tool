"""Parse `*.sprite.toml` files into sprites.

Bad art never raises: each problem becomes a `Problem` and parsing carries on
with the next frame or file. A frame that did not resolve is left out of its
sprite, and a file with no resolved frame gives no sprite.
"""

from __future__ import annotations

import re
import tomllib
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from .model import Anim, Canvas, Frame, Problem, Project, Sprite

SUFFIX = ".sprite.toml"
TRANSPARENT = "."
MAX_E104_PER_FRAME = 10

_TOP_LEVEL_KEYS = ("canvas", "frames", "anim", "variants", "outline", "grounded")
_FRAME_KEYS = ("from", "rows", "runs", "shift", "flip")
_ANIM_KEYS = ("frames", "ms", "loop")
_VARIANT_KEYS = ("swap",)
ID_RE = re.compile(r"[a-z0-9_]+")
_FRAME_NAME_RE = ID_RE
_ROW_INDEX_RE = re.compile(r"[0-9]{1,9}")
_TOML_POSITION_RE = re.compile(r"at line (\d+), column (\d+)")
_KEY_LINE_RE = re.compile(r"""\s*(?:([A-Za-z0-9_-]+)|"([^"]*)"|'([^']*)')\s*=\s*(.*)""")


def discover(root: Path) -> list[Path]:
    """Every `*.sprite.toml` file under `root`, sorted."""
    return sorted(path for path in root.rglob("*" + SUFFIX) if path.is_file())


def load_all(project: Project, paths: Sequence[Path] | None = None) -> tuple[list[Sprite], list[Problem]]:
    """Parse the given sprite files (default: every one in the project).

    Returns the sprites sorted by id, variants included, and the problems in
    file order. Sprites whose ids clash are all returned.
    """
    sprites: list[Sprite] = []
    problems: list[Problem] = []
    for path in discover(project.root) if paths is None else paths:
        found, bad = _load_file(Path(path), project)
        sprites.extend(found)
        problems.extend(bad)
    sprites.sort(key=lambda sprite: sprite.id)
    return sprites, problems


def _load_file(path: Path, project: Project) -> tuple[list[Sprite], list[Problem]]:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return [], [Problem(path, 0, 0, "E001", f"cannot read file: {exc}")]
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        match = _TOML_POSITION_RE.search(str(exc))
        line, col = (int(match[1]), int(match[2])) if match else (1, 1)
        return [], [Problem(path, line, col, "E001", f"invalid TOML: {exc}")]
    sprite_id = path.name.removesuffix(SUFFIX)
    if not ID_RE.fullmatch(sprite_id):
        # The id names exported files and engine keys, so it is as strict as `sprite new`.
        message = f"sprite id {sprite_id!r} (the file name) must match {ID_RE.pattern}"
        return [], [Problem(path, 0, 0, "E001", message)]
    parser = _Parser(path, text, project)
    return parser.parse(data), parser.problems


def add_outline(rows: tuple[str, ...], key: str) -> tuple[str, ...]:
    """`rows` with `key` on every transparent pixel directly above, below,
    left or right of a drawn one.

    One pass over the rows as given: the new pixels grow no outline of their
    own, and diagonals do not count, so corners come out rounded.
    """
    height = len(rows)
    width = len(rows[0]) if rows else 0

    def drawn(r: int, c: int) -> bool:
        return 0 <= r < height and 0 <= c < width and rows[r][c] != TRANSPARENT

    def pixel(r: int, c: int) -> str:
        if rows[r][c] != TRANSPARENT:
            return rows[r][c]
        beside = drawn(r - 1, c) or drawn(r + 1, c) or drawn(r, c - 1) or drawn(r, c + 1)
        return key if beside else TRANSPARENT

    return tuple("".join(pixel(r, c) for c in range(width)) for r in range(height))


# --- source positions -------------------------------------------------------


def _scan(text: str) -> tuple[dict[tuple[str, ...], int], dict[tuple[str, ...], int]]:
    """Find where keys are defined, since `tomllib` reports no positions.

    Returns two maps from `(table..., key)` to a 1-based line: the line of the
    key (or table header), and for a string value the line its first row is on.
    Works line by line, so dotted keys and inline tables are not found.
    """
    keys: dict[tuple[str, ...], int] = {}
    first_rows: dict[tuple[str, ...], int] = {}
    table: tuple[str, ...] = ()
    closing: str | None = None
    for number, raw in enumerate(text.split("\n"), start=1):
        if closing is not None:
            if closing in raw:
                closing = None
            continue
        if raw.lstrip().startswith("["):
            header = _header_path(raw)
            if header is not None:
                table = header
                keys.setdefault(table, number)
            continue
        match = _KEY_LINE_RE.match(raw)
        if match is None:
            continue
        key = next(group for group in match.groups()[:3] if group is not None)
        path = (*table, key)
        value = match[4]
        keys.setdefault(path, number)
        delimiter = value[:3]
        if delimiter in ('"""', "'''"):
            # The newline right after the opening delimiter is not a row.
            rest = value[3:]
            first_rows.setdefault(path, number if rest else number + 1)
            if delimiter not in rest:
                closing = delimiter
        else:
            first_rows.setdefault(path, number)
    return keys, first_rows


def _header_path(raw: str) -> tuple[str, ...] | None:
    """The table named by a `[a.b]` header line, or None if it is not one."""
    try:
        value: Any = tomllib.loads(raw)
    except tomllib.TOMLDecodeError:
        return None
    path = []
    while isinstance(value, dict) and len(value) == 1:
        key, value = next(iter(value.items()))
        path.append(key)
    return tuple(path)


# --- one file ---------------------------------------------------------------


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_run(value: Any) -> bool:
    """Whether `value` has the shape of a run, `[column, "pixels"]`."""
    return isinstance(value, list) and len(value) == 2 and _is_int(value[0]) and isinstance(value[1], str)


@dataclass(frozen=True)
class _Derived:
    """A frame table whose own fields are valid; `parent` is not resolved yet.

    With no `parent` the frame starts from a transparent canvas.
    """

    parent: str | None
    rows: dict[int, str]
    runs: dict[int, list[tuple[int, str]]]
    shift: tuple[int, int]
    flip: bool
    line: int

    def apply(self, parent_rows: tuple[str, ...], canvas: Canvas) -> tuple[str, ...]:
        """`rows`, then `runs`, then `shift`, then `flip`."""
        rows = list(parent_rows)
        for index, row in self.rows.items():
            rows[index] = row
        for index, runs in self.runs.items():
            for col, text in runs:
                rows[index] = rows[index][:col] + text + rows[index][col + len(text) :]

        dx, dy = self.shift
        if (dx, dy) != (0, 0):
            source = rows

            def pixel(x: int, y: int) -> str:
                inside = 0 <= x < canvas.width and 0 <= y < canvas.height
                return source[y][x] if inside else TRANSPARENT

            rows = ["".join(pixel(x - dx, y - dy) for x in range(canvas.width)) for y in range(canvas.height)]

        if self.flip:
            rows = [row[::-1] for row in rows]
        return tuple(rows)


class _Parser:
    """Turns one parsed sprite file into sprites, collecting `problems`."""

    def __init__(self, path: Path, text: str, project: Project) -> None:
        self.path = path
        self.project = project
        self.problems: list[Problem] = []
        self.keys, self.first_rows = _scan(text)

    def line(self, *key_path: str) -> int:
        """The line of `key_path`, else of the table holding it; 0 if not found."""
        for end in range(len(key_path), min(len(key_path), 2) - 1, -1):
            line = self.keys.get(key_path[:end], 0)
            if line:
                return line
        return 0

    def report(self, code: str, message: str, *key_path: str) -> None:
        """Record a problem at the line of `key_path`, or line 1 if not found."""
        self.report_at(self.line(*key_path) or 1, 1, code, message)

    def report_at(self, line: int, col: int, code: str, message: str) -> None:
        self.problems.append(Problem(self.path, line, col, code, message))

    def parse(self, data: dict[str, Any]) -> list[Sprite]:
        for key in data:
            if key not in _TOP_LEVEL_KEYS:
                self.report("E001", f"unknown field {key!r}", key)
        canvas = self._canvas(data)
        if canvas is None:
            return []
        outline, auto_outline = self._outline(data, canvas)
        grounded = self._flag(data, "grounded")
        resolved = self._frames(data.get("frames"), canvas)
        anims = self._anims(data.get("anim", {}), resolved)
        swaps = self._variants(data.get("variants", {}))

        frames = tuple(frame for frame in resolved.values() if frame is not None)
        if not frames:
            return []
        if auto_outline:
            # Only now, on each frame's final interior: any earlier and a
            # derived frame would edit its parent's outline.
            frames = tuple(replace(frame, rows=add_outline(frame.rows, canvas.outline_key)) for frame in frames)
        sprite = Sprite(
            id=self.path.name.removesuffix(SUFFIX),
            source=self.path,
            canvas=canvas,
            frames=frames,
            anims=anims,
            outline=canvas.outline is not None and outline,
            grounded=canvas.grounded and grounded,
            variant_of=None,
            auto_outline=auto_outline,
        )
        return [sprite, *(_variant(sprite, name, swap) for name, swap in swaps.items())]

    def _canvas(self, data: dict[str, Any]) -> Canvas | None:
        name = data.get("canvas")
        if not isinstance(name, str):
            self.report("E001", "canvas is required and must be the name of a canvas class", "canvas")
            return None
        canvas = self.project.canvases.get(name)
        if canvas is None:
            expected = ", ".join(self.project.canvases)
            self.report("E101", f"unknown canvas class {name!r} (expected one of {expected})", "canvas")
        return canvas

    def _outline(self, data: dict[str, Any], canvas: Canvas) -> tuple[bool, bool]:
        """Whether the sprite asks for the outline rule, and whether the tool draws the outline.

        A value that cannot be used is reported and read as `true`.
        """
        value = data.get("outline", True)
        if isinstance(value, bool):
            return value, False
        if value != "auto":
            self.report("E001", 'outline must be true, false or "auto"', "outline")
        elif canvas.outline_key is None:
            self.report("E001", f'outline = "auto" needs an outline rule on canvas class {canvas.name!r}', "outline")
        else:
            return True, True
        return True, False

    def _flag(self, data: dict[str, Any], key: str) -> bool:
        value = data.get(key, True)
        if not isinstance(value, bool):
            self.report("E001", f"{key} must be true or false", key)
            return True
        return value

    # --- frames ---

    def _frames(self, raw: Any, canvas: Canvas) -> dict[str, Frame | None]:
        """Every frame name in the file, in file order; None for a frame that failed."""
        if not isinstance(raw, dict) or not raw:
            self.report("E001", "frames is required and must be a table with at least one frame", "frames")
            return {}
        resolved: dict[str, Frame | None] = {}
        pending: dict[str, _Derived] = {}
        for name, value in raw.items():
            resolved[name] = None
            if not _FRAME_NAME_RE.fullmatch(name):
                self.report("E001", f"bad frame name {name!r}: use a-z, 0-9 and _", "frames", name)
            elif isinstance(value, str):
                resolved[name] = self._grid(name, value, canvas)
            elif isinstance(value, dict):
                derived = self._derived(name, value, raw, canvas)
                if derived is not None:
                    pending[name] = derived
            else:
                self.report("E001", f"frame {name!r} must be a grid string or a table with from, rows or runs", "frames", name)
        self._resolve(pending, resolved, canvas)
        return resolved

    def _grid(self, name: str, value: str, canvas: Canvas) -> Frame | None:
        rows = value.split("\n")
        if rows[-1] == "":
            # The newline before the closing delimiter does not add a row.
            rows.pop()
        key = ("frames", name)
        opening = self.keys.get(key, 1)
        first_row = self.first_rows.get(key, 0)

        check = _RowCheck(self, name, canvas)
        if len(rows) != canvas.height:
            check.ok = False
            self.report_at(opening, 1, "E102", f"frame {name!r}: {len(rows)} rows, expected {canvas.height}")
        for index, row in enumerate(rows):
            check.row(index, row, first_row + index if first_row else None)
        check.finish(opening)
        return Frame(name=name, rows=tuple(rows), line=first_row, literal=True) if check.ok else None

    def _derived(self, name: str, table: dict[str, Any], frames: dict[str, Any], canvas: Canvas) -> _Derived | None:
        """Check a frame table's own fields; None if any of them is wrong."""
        key = ("frames", name)
        problems_before = len(self.problems)

        for field in table:
            if field not in _FRAME_KEYS:
                self.report("E001", f"frame {name!r}: unknown field {field!r}", *key, field)

        if not any(field in table for field in ("from", "rows", "runs")):
            self.report("E001", f"frame {name!r}: needs from, rows or runs", *key)

        parent = table.get("from")
        if parent is None:
            pass
        elif not isinstance(parent, str):
            self.report("E001", f"frame {name!r}: from must be a frame name", *key, "from")
        elif parent not in frames:
            self.report("E105", f"frame {name!r}: from names unknown frame {parent!r}", *key, "from")

        # One check for `rows` and `runs`, so that they share the frame's E104 cap.
        check = _RowCheck(self, name, canvas)
        last = canvas.height - 1

        rows: dict[int, str] = {}
        overrides = table.get("rows", {})
        rows_line = self.line(*key, "rows") or 1
        if not isinstance(overrides, dict):
            self.report("E001", f"frame {name!r}: rows must be a table of row index to row", *key, "rows")
        else:
            for index_text, row in overrides.items():
                if not _ROW_INDEX_RE.fullmatch(index_text) or int(index_text) > last:
                    message = f"frame {name!r}: bad rows index {index_text!r} (expected 0 to {last})"
                    self.report_at(rows_line, 1, "E105", message)
                elif not isinstance(row, str):
                    self.report_at(rows_line, 1, "E001", f"frame {name!r} row {index_text}: must be a string")
                else:
                    check.row(int(index_text), row, None, rows_line)
                    rows[int(index_text)] = row

        runs: dict[int, list[tuple[int, str]]] = {}
        placed = table.get("runs", {})
        runs_line = self.line(*key, "runs") or 1
        if not isinstance(placed, dict):
            message = f'frame {name!r}: runs must be a table of row index to a list of [column, "pixels"] pairs'
            self.report("E001", message, *key, "runs")
        else:
            for index_text, row_runs in placed.items():
                # The row's own key in the table form, the `runs` key in the inline form.
                row_line = self.line(*key, "runs", index_text) or 1
                if not _ROW_INDEX_RE.fullmatch(index_text) or int(index_text) > last:
                    message = f"frame {name!r}: bad runs index {index_text!r} (expected 0 to {last})"
                    self.report_at(row_line, 1, "E105", message)
                elif not isinstance(row_runs, list) or not all(_is_run(run) for run in row_runs):
                    message = f'frame {name!r} row {index_text}: runs must be a list of [column, "pixels"] pairs'
                    self.report_at(row_line, 1, "E001", message)
                else:
                    for col, text in row_runs:
                        check.run(int(index_text), col, text, row_line)
                    runs[int(index_text)] = [(col, text) for col, text in row_runs]
        check.finish(rows_line if "rows" in table else runs_line)

        shift = table.get("shift", [0, 0])
        if not isinstance(shift, list) or len(shift) != 2 or not all(_is_int(item) for item in shift):
            self.report("E001", f"frame {name!r}: shift must be a list of two integers", *key, "shift")

        flip = table.get("flip", False)
        if not isinstance(flip, bool):
            self.report("E001", f"frame {name!r}: flip must be true or false", *key, "flip")

        if len(self.problems) > problems_before:
            return None
        # A frame written only as `[frames.<name>.runs]` has no line of its own.
        line = self.line(*key, "rows") if "rows" in table else self.line(*key) or self.line(*key, "runs")
        return _Derived(parent=parent, rows=rows, runs=runs, shift=(shift[0], shift[1]), flip=flip, line=line)

    def _resolve(self, pending: dict[str, _Derived], resolved: dict[str, Frame | None], canvas: Canvas) -> None:
        """Fill `resolved` for the derived frames in `pending`, parents first.

        A frame with no `from` starts from a transparent canvas. A frame whose
        `from` chain reaches a failed frame stays None without a problem of
        its own. A cycle is reported once, at its first frame in
        file order.
        """
        order = {name: index for index, name in enumerate(resolved)}
        done: set[str] = set()
        for start in pending:
            chain: list[str] = []
            name = start
            while name in pending and name not in done and name not in chain:
                chain.append(name)
                name = pending[name].parent

            if name in chain:
                cycle = chain[chain.index(name) :]
                first = min(cycle, key=order.__getitem__)
                at = cycle.index(first)
                loop = " -> ".join([*cycle[at:], *cycle[:at], first])
                self.report("E105", f"frame {first!r}: from cycle ({loop})", "frames", first, "from")
                done.update(chain)
                continue

            for child in reversed(chain):
                derived = pending[child]
                if derived.parent is None:
                    base: tuple[str, ...] | None = (TRANSPARENT * canvas.width,) * canvas.height
                else:
                    parent = resolved[derived.parent]
                    base = parent.rows if parent is not None else None
                if base is not None:
                    rows = derived.apply(base, canvas)
                    resolved[child] = Frame(
                        name=child,
                        rows=rows,
                        line=derived.line,
                        literal=False,
                        parent=derived.parent,
                        shift=derived.shift,
                        flip=derived.flip,
                    )
                done.add(child)


    # --- animations and variants ---

    def _anims(self, raw: Any, frames: dict[str, Frame | None]) -> tuple[Anim, ...]:
        if not isinstance(raw, dict):
            self.report("E001", "anim must be a table of [anim.<name>] tables", "anim")
            return ()
        anims = []
        for name, table in raw.items():
            key = ("anim", name)
            if not isinstance(table, dict):
                self.report("E001", f"anim {name!r} must be a table", *key)
                continue
            problems_before = len(self.problems)
            for field in table:
                if field not in _ANIM_KEYS:
                    self.report("E001", f"anim {name!r}: unknown field {field!r}", *key, field)

            names = table.get("frames")
            if not isinstance(names, list) or not names or not all(isinstance(item, str) for item in names):
                message = f"anim {name!r}: frames is required and must be a list of frame names"
                self.report("E001", message, *key, "frames")
                names = []
            for frame in dict.fromkeys(names):
                if frame not in frames:
                    self.report("E105", f"anim {name!r}: unknown frame {frame!r}", *key, "frames")

            ms = table.get("ms")
            if not _is_int(ms) or ms < 1:
                self.report("E001", f"anim {name!r}: ms is required and must be a positive integer", *key, "ms")

            loop = table.get("loop", True)
            if not isinstance(loop, bool):
                self.report("E001", f"anim {name!r}: loop must be true or false", *key, "loop")

            # A frame that failed has its own problem; the animation just goes.
            if len(self.problems) == problems_before and all(frames[frame] is not None for frame in names):
                anims.append(Anim(name=name, frames=tuple(names), ms=ms, loop=loop))
        return tuple(anims)

    def _variants(self, raw: Any) -> dict[str, dict[int, str]]:
        """The translation table of each valid variant, by variant name."""
        if not isinstance(raw, dict):
            self.report("E001", "variants must be a table of [variants.<name>] tables", "variants")
            return {}
        swaps = {}
        for name, table in raw.items():
            key = ("variants", name)
            if not isinstance(table, dict):
                self.report("E001", f"variant {name!r} must be a table", *key)
                continue
            problems_before = len(self.problems)
            if not ID_RE.fullmatch(name):
                # The name becomes part of a sprite id.
                self.report("E001", f"bad variant name {name!r}: use a-z, 0-9 and _", *key)
            for field in table:
                if field not in _VARIANT_KEYS:
                    self.report("E001", f"variant {name!r}: unknown field {field!r}", *key, field)

            swap = table.get("swap")
            if not isinstance(swap, dict) or not all(isinstance(target, str) for target in swap.values()):
                message = f"variant {name!r}: swap is required and must be a table of palette key to palette key"
                self.report("E001", message, *key, "swap")
                continue
            for palette_key in dict.fromkeys(item for pair in swap.items() for item in pair):
                if palette_key not in self.project.palette:
                    message = f"variant {name!r}: swap key {palette_key!r} is not in the palette"
                    self.report("E107", message, *key, "swap")

            if len(self.problems) == problems_before:
                swaps[name] = str.maketrans(swap)
        return swaps


def _variant(base: Sprite, name: str, swap: dict[int, str]) -> Sprite:
    """`base` with every palette key swapped at once."""
    frames = tuple(replace(frame, rows=tuple(row.translate(swap) for row in frame.rows)) for frame in base.frames)
    return replace(base, id=f"{base.id}_{name}", frames=frames, variant_of=base.id)


class _RowCheck:
    """Reports the problems in the rows and runs of one frame, capping E104."""

    def __init__(self, parser: _Parser, frame: str, canvas: Canvas) -> None:
        self.parser = parser
        self.frame = frame
        self.width = canvas.width
        self.ok = True
        self.unknown_keys = 0

    def row(self, index: int, text: str, line: int | None, fallback_line: int = 1) -> None:
        """Check one row. `line` is the row's own file line, when it has one.

        Without it the problems go to `fallback_line`, column 1, and the
        message says which frame and row.
        """
        where = f"frame {self.frame!r} row {index}"
        stripped = text.rstrip()
        if stripped != text:
            self._report(line, len(stripped) + 1, fallback_line, "E103", f"{where}: trailing whitespace")
        elif len(text) != self.width:
            col = min(len(text), self.width) + 1
            message = f"{where}: {len(text)} wide, expected {self.width}"
            self._report(line, col, fallback_line, "E103", message)

        for offset, key in self._unknown(stripped):
            message = f"unknown palette key {key!r}" + ("" if line else f" in {where}")
            self._report(line, offset + 1, fallback_line, "E104", message)

    def run(self, index: int, col: int, text: str, line: int) -> None:
        """Check one run of row `index`, starting at column `col`, reporting at `line`."""
        where = f"frame {self.frame!r} row {index}"
        if not text:
            self._report(None, 1, line, "E001", f"{where}: run at col {col} has no pixels")
        elif col < 0 or col + len(text) > self.width:
            message = f"{where}: run at col {col} is {len(text)} wide, canvas is {self.width} wide"
            self._report(None, 1, line, "E103", message)

        for offset, key in self._unknown(text):
            self._report(None, 1, line, "E104", f"unknown palette key {key!r} in {where}, col {col + offset}")

    def finish(self, line: int) -> None:
        """Report how many E104 problems the cap left out, at `line`."""
        extra = self.unknown_keys - MAX_E104_PER_FRAME
        if extra > 0:
            noun = "key" if extra == 1 else "keys"
            self.parser.report_at(line, 1, "E104", f"{extra} more unknown palette {noun} in frame {self.frame!r}")

    def _unknown(self, text: str) -> Iterator[tuple[int, str]]:
        """Count the unknown keys in `text`, yielding each one under the cap with its offset."""
        for offset, key in enumerate(text):
            if key == TRANSPARENT or key in self.parser.project.palette:
                continue
            self.ok = False
            self.unknown_keys += 1
            if self.unknown_keys <= MAX_E104_PER_FRAME:
                yield offset, key

    def _report(self, line: int | None, col: int, fallback_line: int, code: str, message: str) -> None:
        self.ok = False
        if line:
            self.parser.report_at(line, col, code, message)
        else:
            self.parser.report_at(fallback_line, 1, code, message)
