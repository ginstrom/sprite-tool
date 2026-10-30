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

from .model import TINT_MODES, Anim, Canvas, Frame, Problem, Project, Sprite, Tint
from .project import resolve_colour

SUFFIX = ".sprite.toml"
TRANSPARENT = "."
MAX_E104_PER_FRAME = 10

_TOP_LEVEL_KEYS = (
    "canvas",
    "frames",
    "anim",
    "variants",
    "outline",
    "grounded",
    "build",
    "over",
    "unoutlined",
    "points",
    "frame_points",
    "tints",
)
_TINT_KEYS = ("colour", "mode")
_FRAME_KEYS = ("from", "move", "mirror", "rows", "runs", "shift", "flip")
_ANIM_KEYS = ("frames", "ms", "loop", "like", "rest")
_MOVE_KEYS = ("rows", "cols", "by")
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
    file order, those of a `like` after the rest. Sprites whose ids clash are
    all returned.
    """
    sprites: list[Sprite] = []
    problems: list[Problem] = []
    for path in discover(project.root) if paths is None else paths:
        found, bad = _load_file(Path(path), project)
        sprites.extend(found)
        problems.extend(bad)
    sprites.sort(key=lambda sprite: sprite.id)
    sprites, bad = _resolve_likes(sprites)
    sprites, more = _resolve_rests(sprites)
    return sprites, problems + bad + more


def _resolve_likes(sprites: Sequence[Sprite]) -> tuple[list[Sprite], list[Problem]]:
    """Give each sprite the animations it takes from another with `like`.

    An animation is looked up by sprite id among the sprites as they were
    parsed, so it must be written out where it is taken from, and the result
    does not depend on file order. One that cannot be taken is left out and
    stays in `anim_likes`. A variant's problems are its sprite's, and are not
    reported again.
    """
    by_id: dict[str, Sprite] = {}
    for sprite in sprites:
        by_id.setdefault(sprite.id, sprite)
    resolved: list[Sprite] = []
    problems: list[Problem] = []
    for sprite in sprites:
        frames = {frame.name for frame in sprite.frames}
        anims = list(sprite.anims)
        failed = []
        for name, source_id, line in sprite.anim_likes:
            found, messages = _like(name, source_id, by_id, frames)
            if found is None:
                failed.append((name, source_id, line))
                if sprite.variant_of is None:
                    problems += [Problem(sprite.source, line, 1 if line else 0, "E105", message) for message in messages]
            else:
                anims.append(replace(found, line=line))
        if sprite.anim_likes:
            sprite = replace(sprite, anims=tuple(anims), anim_likes=tuple(failed))
        resolved.append(sprite)
    return resolved, problems


def _resolve_rests(sprites: Sequence[Sprite]) -> tuple[list[Sprite], list[Problem]]:
    """Give each layer the animations it rests through with `rest = true`.

    Runs after `_resolve_likes`, so a base's animation taken with `like` can
    be rested through. A rest becomes one entry, the layer's default frame,
    as long as the whole of the base's animation and looping as it does. A
    layer whose `over` is bad is check's E108 and keeps its rests pending.
    """
    by_id: dict[str, Sprite] = {}
    for sprite in sprites:
        by_id.setdefault(sprite.id, sprite)
    resolved: list[Sprite] = []
    problems: list[Problem] = []
    for sprite in sprites:
        base = by_id.get(sprite.over) if sprite.over is not None else None
        if not sprite.anim_rests or base is None or sprite.over in (sprite.id, sprite.variant_of):
            resolved.append(sprite)
            continue
        anims = list(sprite.anims)
        failed = []
        for name, line in sprite.anim_rests:
            theirs = next((anim for anim in base.anims if anim.name == name), None)
            if theirs is None:
                failed.append((name, line))
                if sprite.variant_of is None:
                    message = f"anim {name!r}: rest, but {base.id!r} has no animation {name!r}"
                    problems.append(Problem(sprite.source, line, 1 if line else 0, "E105", message))
                continue
            total = sum(theirs.durations)
            anims.append(
                Anim(name=name, frames=(sprite.frames[0].name,), ms=total, loop=theirs.loop, line=line, rest=True)
            )
        resolved.append(replace(sprite, anims=tuple(anims), anim_rests=tuple(failed)))
    return resolved, problems


def _like(name: str, source_id: str, by_id: dict[str, Sprite], frames: set[str]) -> tuple[Anim | None, list[str]]:
    """The animation `name` of sprite `source_id`, or why it cannot be taken."""
    source = by_id.get(source_id)
    if source is None:
        return None, [f"anim {name!r}: like names unknown sprite {source_id!r}"]
    anim = next((anim for anim in source.anims if anim.name == name), None)
    if anim is None:
        if any(pending == name for pending, _, _ in source.anim_likes):
            message = f"anim {name!r}: animation {name!r} of {source_id!r} is itself like; name the sprite that writes it out"
            return None, [message]
        return None, [f"anim {name!r}: {source_id!r} has no animation {name!r}"]
    missing = [frame for frame in dict.fromkeys(anim.frames) if frame not in frames]
    if missing:
        return None, [f"anim {name!r} like {source_id!r}: this sprite has no frame {frame!r}" for frame in missing]
    return anim, []


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


def add_outline(rows: tuple[str, ...], key: str, unoutlined: frozenset[str] = frozenset()) -> tuple[str, ...]:
    """`rows` with `key` on every transparent pixel directly above, below,
    left or right of a drawn one whose key is not in `unoutlined`.

    One pass over the rows as given: the new pixels grow no outline of their
    own, and diagonals do not count, so corners come out rounded.
    """
    height = len(rows)
    width = len(rows[0]) if rows else 0

    def drawn(r: int, c: int) -> bool:
        return 0 <= r < height and 0 <= c < width and rows[r][c] != TRANSPARENT and rows[r][c] not in unoutlined

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


def _is_int_pair(value: Any) -> bool:
    return isinstance(value, list) and len(value) == 2 and all(_is_int(item) for item in value)


@dataclass(frozen=True)
class _Move:
    """One `move`: the rectangle of inclusive `rows` and `cols`, and how far it goes."""

    rows: tuple[int, int]
    cols: tuple[int, int]
    by: tuple[int, int]


# A grid of anything: palette keys when it is a frame's rows, parent positions
# when it is a frame's origins. The moves below work on either, which is what
# keeps the two from disagreeing.
_Grid = list[list[Any]]


def _moved(grid: _Grid, move: _Move, blank: Any) -> tuple[_Grid, list[Any]]:
    """`grid` with the rectangle of `move` cut out and written back at its
    offset, and the cells that left the canvas."""
    (top, bottom), (left, right), (dx, dy) = move.rows, move.cols, move.by
    height, width = len(grid), len(grid[0])
    result = [list(row) for row in grid]
    for r in range(top, bottom + 1):
        for c in range(left, right + 1):
            result[r][c] = blank
    dropped = []
    for r in range(top, bottom + 1):
        for c in range(left, right + 1):
            if 0 <= r + dy < height and 0 <= c + dx < width:
                result[r + dy][c + dx] = grid[r][c]
            else:
                dropped.append(grid[r][c])
    return result, dropped


def _mirrored(grid: _Grid, rect: _Move) -> _Grid:
    """`grid` with each row of the rectangle of `rect` reversed within its
    columns. `rect.by` is not used."""
    (top, bottom), (left, right) = rect.rows, rect.cols
    result = [list(row) for row in grid]
    for r in range(top, bottom + 1):
        result[r][left : right + 1] = grid[r][left : right + 1][::-1]
    return result


def _inside(move: _Move, col: int, row: int) -> bool:
    return move.rows[0] <= row <= move.rows[1] and move.cols[0] <= col <= move.cols[1]


@dataclass(frozen=True)
class _Derived:
    """A frame table whose own fields are valid; `parent` is not resolved yet.

    With no `parent` the frame starts from a transparent canvas.
    """

    parent: str | None
    moves: tuple[_Move, ...]
    mirrors: tuple[_Move, ...]
    rows: dict[int, str]
    runs: dict[int, list[tuple[int, str]]]
    shift: tuple[int, int]
    flip: bool
    line: int

    def apply(
        self, parent_rows: tuple[str, ...], canvas: Canvas
    ) -> tuple[tuple[str, ...], tuple[tuple[tuple[int, int] | None, ...], ...], tuple[tuple[str, int], ...]]:
        """`move`, then `mirror`, then `rows`, then `runs`, then `shift`, then `flip`.

        Returns the rows, where in the parent each pixel came from, and what
        each `move` and `shift` pushed off the canvas.
        """

        def edit(rows: _Grid) -> None:
            for index, row in self.rows.items():
                rows[index] = list(row)
            for index, runs in self.runs.items():
                for col, text in runs:
                    rows[index][col : col + len(text)] = text

        rows, lost = self._transform([list(row) for row in parent_rows], TRANSPARENT, edit)
        positions = [[(r, c) for c in range(canvas.width)] for r in range(canvas.height)]
        origins, _ = self._transform(positions, None, None)
        return (
            tuple("".join(row) for row in rows),
            tuple(tuple(row) for row in origins),
            tuple((what, count) for what, count in lost if count),
        )

    def _transform(self, grid: _Grid, blank: Any, edit: Any) -> tuple[_Grid, list[tuple[str, int]]]:
        """Run the operations on `grid`. `edit` stands for `rows` and `runs`,
        which change what a cell holds and not where it came from. Also
        returns, for each move and the shift, how many cells that were not
        `blank` left the canvas."""
        lost = []
        for move in self.moves:
            grid, dropped = _moved(grid, move, blank)
            lost.append((f"move by {list(move.by)}", sum(1 for cell in dropped if cell != blank)))
        for mirror in self.mirrors:
            grid = _mirrored(grid, mirror)
        if edit is not None:
            edit(grid)
        if self.shift != (0, 0):
            whole = _Move((0, len(grid) - 1), (0, len(grid[0]) - 1), self.shift)
            grid, dropped = _moved(grid, whole, blank)
            lost.append((f"shift {list(self.shift)}", sum(1 for cell in dropped if cell != blank)))
        if self.flip:
            grid = [row[::-1] for row in grid]
        return grid, lost

    def carry(
        self, points: dict[str, tuple[int, int]], canvas: Canvas
    ) -> tuple[dict[str, tuple[int, int]], list[tuple[str, str]]]:
        """Each point `(col, row)` taken where the operations take the pixel
        under it, in the order `_transform` runs them. A point is not a cell:
        pixels moved onto it do not move it. Returns the points still on the
        canvas, and the operation and name of each that left it."""
        lost: list[tuple[str, str]] = []

        def step(found: dict[str, tuple[int, int]], what: str, where: Any) -> dict[str, tuple[int, int]]:
            kept = {}
            for name, (col, row) in found.items():
                col, row = where(col, row)
                if 0 <= col < canvas.width and 0 <= row < canvas.height:
                    kept[name] = (col, row)
                else:
                    lost.append((what, name))
            return kept

        # Each `where` is used at once, inside its own iteration.
        for move in self.moves:
            dx, dy = move.by
            points = step(
                points,
                f"move by {list(move.by)}",
                lambda c, r: (c + dx, r + dy) if _inside(move, c, r) else (c, r),
            )
        for mirror in self.mirrors:
            left, right = mirror.cols
            points = step(points, "mirror", lambda c, r: (left + right - c, r) if _inside(mirror, c, r) else (c, r))
        if self.shift != (0, 0):
            dx, dy = self.shift
            points = step(points, f"shift {list(self.shift)}", lambda c, r: (c + dx, r + dy))
        if self.flip:
            points = step(points, "flip", lambda c, r: (canvas.width - 1 - c, r))
        return points, lost


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
        over = self._over(data)
        outline, auto_outline = self._outline(data, canvas, over is not None)
        unoutlined = self._unoutlined(data)
        grounded = self._flag(data, "grounded")
        build = self._flag(data, "build")
        points = self._points(data.get("points", {}), canvas, ("points",), "points")
        frame_points = self._frame_points(data.get("frame_points", {}), data.get("frames"), canvas)
        resolved = self._frames(data.get("frames"), canvas, points, frame_points)
        anims, likes, rests = self._anims(data.get("anim", {}), resolved, over is not None)
        swaps = self._variants(data.get("variants", {}))
        tints = self._tints(data.get("tints", {}))

        frames = tuple(frame for frame in resolved.values() if frame is not None)
        if not frames:
            return []
        for frame in frames:
            for what, lost in frame.lost:
                noun = "pixel" if lost == 1 else "pixels"
                message = f"frame {frame.name!r}: {what} pushes {lost} drawn {noun} off the canvas"
                self.report_at(frame.line or 1, 1, "W006", message)
            for what, name in frame.points_lost:
                message = f"frame {frame.name!r}: {what} takes point {name!r} off the canvas"
                self.report_at(frame.line or 1, 1, "W008", message)
        if auto_outline:
            # Only now, on each frame's final interior: any earlier and a
            # derived frame would edit its parent's outline.
            frames = tuple(
                replace(frame, rows=add_outline(frame.rows, canvas.outline_key, unoutlined)) for frame in frames
            )
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
            build=build,
            over=over,
            over_line=self.line("over") if over is not None else 0,
            unoutlined=unoutlined,
            anim_likes=likes,
            anim_rests=rests,
            tints=tints,
            tints_line=self.line("tints") if tints else 0,
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

    def _over(self, data: dict[str, Any]) -> str | None:
        value = data.get("over")
        if value is not None and not isinstance(value, str):
            self.report("E001", "over must be a sprite id", "over")
            return None
        return value

    def _unoutlined(self, data: dict[str, Any]) -> frozenset[str]:
        value = data.get("unoutlined", [])
        if not isinstance(value, list) or not all(isinstance(key, str) and len(key) == 1 for key in value):
            self.report("E001", "unoutlined must be a list of palette keys", "unoutlined")
            return frozenset()
        for key in dict.fromkeys(value):
            if key not in self.project.palette:
                self.report("E107", f"unoutlined key {key!r} is not in the palette", "unoutlined")
        return frozenset(key for key in value if key in self.project.palette)

    def _outline(self, data: dict[str, Any], canvas: Canvas, layer: bool) -> tuple[bool, bool]:
        """Whether the sprite asks for the outline rule, and whether the tool draws the outline.

        A value that cannot be used is reported and read as `true`.
        """
        value = data.get("outline", True)
        if isinstance(value, bool):
            return value, False
        if value != "auto":
            self.report("E001", 'outline must be true, false or "auto"', "outline")
        elif layer:
            self.report("E001", 'outline = "auto" cannot be used with over; draw the layer\'s outline', "outline")
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

    # --- tints ---

    def _tints(self, raw: Any) -> tuple[tuple[str, Tint], ...]:
        """The good tints of `tints`, sorted by name, with an E110 for each that is not."""
        if not isinstance(raw, dict):
            self.report("E110", "tints must be a table of name = colour", "tints")
            return ()
        tints = {}
        for name, value in raw.items():
            # An inline table's keys are not found: then the line of `tints`.
            line = self.line("tints", name) or self.line("tints") or 1
            if not ID_RE.fullmatch(name):
                self.report_at(line, 1, "E110", f"tints: bad tint name {name!r}: use a-z, 0-9 and _")
                continue
            fault, tint = self._tint(name, value)
            if fault is not None:
                self.report_at(line, 1, "E110", f"tints: tint {name!r} {fault}")
            else:
                tints[name] = tint
        return tuple(sorted(tints.items()))

    def _tint(self, name: str, value: Any) -> tuple[str | None, Tint | None]:
        """One tint's value as a `Tint`, or what is wrong with it."""
        mode = "multiply"
        if isinstance(value, dict):
            unknown = [key for key in value if key not in _TINT_KEYS]
            if unknown:
                return f"has unknown key {unknown[0]!r} (expected colour and mode)", None
            if "colour" not in value:
                return "needs a colour", None
            mode = value.get("mode", mode)
            if mode not in TINT_MODES:
                return f"mode must be {' or '.join(map(repr, TINT_MODES))}", None
            value = value["colour"]
        elif not isinstance(value, str):
            return "must be a colour or a table { colour = ..., mode = ... }", None
        rgba = resolve_colour(value, self.project.palette) if isinstance(value, str) else None
        if rgba is None:
            return f"colour {value!r} must be #rrggbb, #rrggbbaa or a palette key", None
        return None, Tint(rgba, mode, name)

    # --- points ---

    def _points(
        self, raw: Any, canvas: Canvas, key: tuple[str, ...], where: str
    ) -> dict[str, tuple[int, int]]:
        """The good points of one `[points]` or `[frame_points.<frame>]` table,
        `name -> (col, row)`, with an E109 for each that is not."""
        if not isinstance(raw, dict):
            self.report("E109", f"{where} must be a table of name = [col, row]", *key)
            return {}
        points = {}
        for name, value in raw.items():
            if not ID_RE.fullmatch(name):
                self.report("E109", f"{where}: bad point name {name!r}: use a-z, 0-9 and _", *key, name)
            elif not _is_int_pair(value):
                self.report("E109", f"{where}: point {name!r} must be [col, row], two integers", *key, name)
            elif not (0 <= value[0] < canvas.width and 0 <= value[1] < canvas.height):
                size = f"{canvas.width}x{canvas.height}"
                self.report("E109", f"{where}: point {name!r} {value} is outside the {size} canvas", *key, name)
            else:
                points[name] = (value[0], value[1])
        return points

    def _frame_points(
        self, raw: Any, frames: Any, canvas: Canvas
    ) -> dict[str, dict[str, tuple[int, int]]]:
        """The good points of each `[frame_points.<frame>]`, by frame name."""
        if not isinstance(raw, dict):
            self.report("E109", "frame_points must be a table of [frame_points.<frame>] tables", "frame_points")
            return {}
        names = frames if isinstance(frames, dict) else {}
        found = {}
        for frame, table in raw.items():
            if frame not in names:
                self.report("E109", f"frame_points names unknown frame {frame!r}", "frame_points", frame)
                continue
            found[frame] = self._points(table, canvas, ("frame_points", frame), f"frame_points.{frame}")
        return found

    # --- frames ---

    def _frames(
        self,
        raw: Any,
        canvas: Canvas,
        points: dict[str, tuple[int, int]],
        frame_points: dict[str, dict[str, tuple[int, int]]],
    ) -> dict[str, Frame | None]:
        """Every frame name in the file, in file order; None for a frame that failed.

        `points` are those of every root frame; `frame_points` those a frame
        sets for itself, by frame name, which its derived frames inherit."""
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
                frame = self._grid(name, value, canvas)
                if frame is not None:
                    frame = replace(frame, points=_sorted_points({**points, **frame_points.get(name, {})}))
                resolved[name] = frame
            elif isinstance(value, dict):
                derived = self._derived(name, value, raw, canvas)
                if derived is not None:
                    pending[name] = derived
            else:
                self.report("E001", f"frame {name!r} must be a grid string or a table with from, rows, runs or move", "frames", name)
        self._resolve(pending, resolved, canvas, points, frame_points)
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

        if not any(field in table for field in ("from", "rows", "runs", "move", "mirror")):
            self.report("E001", f"frame {name!r}: needs from, rows, runs, move or mirror", *key)

        parent = table.get("from")
        if parent is None:
            pass
        elif not isinstance(parent, str):
            self.report("E001", f"frame {name!r}: from must be a frame name", *key, "from")
        elif parent not in frames:
            self.report("E105", f"frame {name!r}: from names unknown frame {parent!r}", *key, "from")

        moves = self._moves(name, table.get("move", []), canvas)
        mirrors = self._moves(name, table.get("mirror", []), canvas, "mirror")

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
        return _Derived(
            parent=parent,
            moves=moves,
            mirrors=mirrors,
            rows=rows,
            runs=runs,
            shift=(shift[0], shift[1]),
            flip=flip,
            line=line,
        )

    def _moves(self, name: str, raw: Any, canvas: Canvas, kind: str = "move") -> tuple[_Move, ...]:
        """The moves of a frame table, reporting each that cannot be used.

        With `kind` "mirror", the rectangles of its `mirror`, which take no
        `by`; a mirror that cannot be used is E105, as a bad range is."""
        key = ("frames", name, kind)
        where = f"frame {name!r}: "
        mirror = kind == "mirror"
        # What a mirror holds is checked as its ranges are; a move's shape is E001.
        shape = "E105" if mirror else "E001"
        tables = [raw] if isinstance(raw, dict) else raw
        if not isinstance(tables, list) or not all(isinstance(table, dict) for table in tables):
            self.report("E001", where + f"{kind} must be a table or a list of tables", *key)
            return ()
        moves = []
        for table in tables:
            unknown = [field for field in table if field not in _MOVE_KEYS or (mirror and field == "by")]
            if unknown:
                what = "has no by" if unknown[0] == "by" else f"has unknown key {unknown[0]!r}"
                self.report(shape, where + f"{kind} {what}", *key)
                continue
            if "rows" not in table and "cols" not in table:
                hint = "flip to mirror" if mirror else "shift to move"
                self.report(shape, where + f"{kind} needs rows or cols (use {hint} the whole frame)", *key)
                continue
            if not mirror and not _is_int_pair(table.get("by")):
                self.report("E001", where + "move needs by = [dx, dy], two integers", *key)
                continue
            ranges = []
            for field, size in (("rows", canvas.height), ("cols", canvas.width)):
                value = table.get(field, [0, size - 1])
                if not _is_int_pair(value):
                    self.report("E001", where + f"{kind} {field} must be [first, last], two integers", *key)
                elif not 0 <= value[0] <= value[1] < size:
                    message = where + f"bad {kind} {field} {value} (expected 0 to {size - 1}, first <= last)"
                    self.report("E105", message, *key)
                else:
                    ranges.append((value[0], value[1]))
            if len(ranges) == 2:
                moves.append(_Move(rows=ranges[0], cols=ranges[1], by=tuple(table.get("by", (0, 0)))))
        return tuple(moves)

    def _resolve(
        self,
        pending: dict[str, _Derived],
        resolved: dict[str, Frame | None],
        canvas: Canvas,
        points: dict[str, tuple[int, int]],
        frame_points: dict[str, dict[str, tuple[int, int]]],
    ) -> None:
        """Fill `resolved` for the derived frames in `pending`, parents first.

        A frame with a parent carries the parent's points through its
        operations; one without has `points`. Then its own `frame_points` apply.

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
                    carried, points_lost = dict(points), []
                else:
                    parent = resolved[derived.parent]
                    base = parent.rows if parent is not None else None
                    inherited = dict(parent.points) if parent is not None else {}
                    carried, points_lost = derived.carry(inherited, canvas)
                if base is not None:
                    rows, origins, lost = derived.apply(base, canvas)
                    own = frame_points.get(child, {})
                    resolved[child] = Frame(
                        name=child,
                        rows=rows,
                        line=derived.line,
                        literal=False,
                        parent=derived.parent,
                        origins=origins if derived.parent is not None else None,
                        lost=lost,
                        points=_sorted_points({**carried, **own}),
                        # A point the frame puts back itself was meant to leave.
                        points_lost=tuple((what, name) for what, name in points_lost if name not in own),
                    )
                done.add(child)


    # --- animations and variants ---

    def _anims(
        self, raw: Any, frames: dict[str, Frame | None], layer: bool = False
    ) -> tuple[tuple[Anim, ...], tuple[tuple[str, str, int], ...], tuple[tuple[str, int], ...]]:
        """The animations written out, name, sprite id and line of each `like`,
        and name and line of each `rest`. `layer`: the sprite has `over`."""
        if not isinstance(raw, dict):
            self.report("E001", "anim must be a table of [anim.<name>] tables", "anim")
            return (), (), ()
        anims = []
        likes = []
        rests = []
        for name, table in raw.items():
            key = ("anim", name)
            if not isinstance(table, dict):
                self.report("E001", f"anim {name!r} must be a table", *key)
                continue
            if "rest" in table:
                if len(table) > 1:
                    self.report("E001", f"anim {name!r}: rest takes no other field", *key, "rest")
                elif table["rest"] is not True:
                    self.report("E001", f"anim {name!r}: rest must be true", *key, "rest")
                elif not layer:
                    self.report("E001", f"anim {name!r}: rest is only for a layer, a sprite with over", *key, "rest")
                else:
                    rests.append((name, self.line(*key, "rest")))
                continue
            if "like" in table:
                if len(table) > 1:
                    self.report("E001", f"anim {name!r}: like takes no other field", *key, "like")
                elif not isinstance(table["like"], str):
                    self.report("E001", f"anim {name!r}: like must be a sprite id", *key, "like")
                else:
                    likes.append((name, table["like"], self.line(*key, "like")))
                continue
            problems_before = len(self.problems)
            for field in table:
                if field not in _ANIM_KEYS:
                    self.report("E001", f"anim {name!r}: unknown field {field!r}", *key, field)

            entries = table.get("frames")
            if not isinstance(entries, list) or not entries:
                message = f"anim {name!r}: frames is required and must be a list of frame names"
                self.report("E001", message, *key, "frames")
                entries = []
            # A frame name, and its own length when the entry gives one.
            parsed: list[tuple[str, int | None]] = []
            for position, entry in enumerate(entries, start=1):
                if isinstance(entry, str):
                    parsed.append((entry, None))
                elif (
                    isinstance(entry, dict)
                    and set(entry) == {"frame", "ms"}
                    and isinstance(entry["frame"], str)
                    and _is_int(entry["ms"])
                    and entry["ms"] >= 1
                ):
                    parsed.append((entry["frame"], entry["ms"]))
                else:
                    message = (
                        f"anim {name!r}: frames entry {position} must be a frame name"
                        ' or { frame = "...", ms = ... }'
                    )
                    self.report("E001", message, *key, "frames")
            names = [frame for frame, _ in parsed]
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
                durations = tuple(ms if own is None else own for _, own in parsed)
                anims.append(
                    Anim(name=name, frames=tuple(names), ms=ms, loop=loop, durations=durations, line=self.line(*key))
                )
        return tuple(anims), tuple(likes), tuple(rests)

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


def _sorted_points(points: dict[str, tuple[int, int]]) -> tuple[tuple[str, tuple[int, int]], ...]:
    return tuple(sorted(points.items()))


def _variant(base: Sprite, name: str, swap: dict[int, str]) -> Sprite:
    """`base` with every palette key swapped at once."""
    frames = tuple(replace(frame, rows=tuple(row.translate(swap) for row in frame.rows)) for frame in base.frames)
    unoutlined = frozenset(key.translate(swap) for key in base.unoutlined)
    return replace(base, id=f"{base.id}_{name}", frames=frames, variant_of=base.id, unoutlined=unoutlined)


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
