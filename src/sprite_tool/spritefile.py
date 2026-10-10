"""Parse `*.sprite.toml` files into sprites.

Bad art never raises: each problem becomes a `Problem` and parsing carries on
with the next frame or file. A frame that did not resolve is left out of its
sprite, and a file with no resolved frame gives no sprite.
"""

from __future__ import annotations

import re
import tomllib
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from .model import Canvas, Frame, Problem, Project, Sprite

SUFFIX = ".sprite.toml"
TRANSPARENT = "."
MAX_E104_PER_FRAME = 10

_TOP_LEVEL_KEYS = ("canvas", "frames", "anim", "variants", "outline", "grounded")
_FRAME_NAME_RE = re.compile(r"[a-z0-9_]+")
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
    parser = _Parser(path, text, project)
    return parser.parse(data), parser.problems


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
        outline = self._flag(data, "outline")
        grounded = self._flag(data, "grounded")
        resolved = self._frames(data.get("frames"), canvas)

        frames = tuple(frame for frame in resolved.values() if frame is not None)
        if not frames:
            return []
        sprite = Sprite(
            id=self.path.name.removesuffix(SUFFIX),
            source=self.path,
            canvas=canvas,
            frames=frames,
            anims=(),
            outline=canvas.outline is not None and outline,
            grounded=canvas.grounded and grounded,
            variant_of=None,
        )
        return [sprite]

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
        for name, value in raw.items():
            resolved[name] = None
            if not _FRAME_NAME_RE.fullmatch(name):
                self.report("E001", f"bad frame name {name!r}: use a-z, 0-9 and _", "frames", name)
            elif isinstance(value, str):
                resolved[name] = self._grid(name, value, canvas)
            else:
                self.report("E001", f"frame {name!r} must be a grid string or a table with from", "frames", name)
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


class _RowCheck:
    """Reports E103 and E104 for the rows of one frame, capping E104."""

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

        for offset, key in enumerate(stripped):
            if key == TRANSPARENT or key in self.parser.project.palette:
                continue
            self.unknown_keys += 1
            if self.unknown_keys <= MAX_E104_PER_FRAME:
                message = f"unknown palette key {key!r}" + ("" if line else f" in {where}")
                self._report(line, offset + 1, fallback_line, "E104", message)
            self.ok = False

    def finish(self, line: int) -> None:
        """Report how many E104 problems the cap left out, at `line`."""
        extra = self.unknown_keys - MAX_E104_PER_FRAME
        if extra > 0:
            noun = "key" if extra == 1 else "keys"
            self.parser.report_at(line, 1, "E104", f"{extra} more unknown palette {noun} in frame {self.frame!r}")

    def _report(self, line: int | None, col: int, fallback_line: int, code: str, message: str) -> None:
        self.ok = False
        if line:
            self.parser.report_at(line, col, code, message)
        else:
            self.parser.report_at(fallback_line, 1, code, message)
