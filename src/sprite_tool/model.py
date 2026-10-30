"""Dataclasses shared by all modules."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Color:
    key: str
    rgba: tuple[int, int, int, int]
    name: str | None


@dataclass(frozen=True)
class Canvas:
    name: str
    width: int
    height: int
    anchor: tuple[int, int]
    display_scale: int
    outline: frozenset[str] | None
    grounded: bool
    # The first key of the outline list, which `outline = "auto"` draws with.
    outline_key: str | None = None


@dataclass(frozen=True)
class Frame:
    """A resolved frame: `rows` is the full grid, palette keys and '.' only.

    literal=True: the frame was written as a grid; `line` is the 1-based file
    line of row 0, so row r, column c is at (line + r, c + 1).
    literal=False: derived frame; `line` is the line of its definition, and
    `parent` is the frame it was made from, if any.
    line=0: position unknown.
    origins: for a derived frame with a parent, the parent pixel `(row, col)`
    each pixel of this frame came from; None for a pixel that came from
    nowhere (vacated by a move or a shift). `rows` and `runs` leave a pixel's
    origin as it was.
    lost: for each `shift` or `move` that dropped drawn pixels off the canvas,
    its description (`"shift [0, 1]"`) and the count.
    points: the frame's named points, `(name, (col, row))`, sorted by name.
    points_lost: for each point this frame's own operations took off the
    canvas, the operation's description and the point's name.
    """

    name: str
    rows: tuple[str, ...]
    line: int
    literal: bool
    parent: str | None = None
    origins: tuple[tuple[tuple[int, int] | None, ...], ...] | None = None
    lost: tuple[tuple[str, int], ...] = ()
    points: tuple[tuple[str, tuple[int, int]], ...] = ()
    points_lost: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class Anim:
    """`durations` has the length in ms of each entry of `frames`; left empty,
    every entry gets `ms`. `line` is the file line of the animation, 0 when
    unknown; it is not part of what makes two animations equal. `rest`: a
    layer's `rest = true`, its default frame held for as long as its base's
    animation of the same name plays.
    """

    name: str
    frames: tuple[str, ...]
    ms: int
    loop: bool
    durations: tuple[int, ...] = ()
    line: int = field(default=0, compare=False)
    rest: bool = False

    def __post_init__(self) -> None:
        if not self.durations:
            object.__setattr__(self, "durations", (self.ms,) * len(self.frames))


@dataclass(frozen=True)
class Sprite:
    """`frames[0]` is the default frame.

    outline / grounded: whether the canvas rule applies after per-sprite opt-out.
    variant_of: the base sprite id for a variant, else None.
    auto_outline: the file says `outline = "auto"`; the frames already hold
    the outline the tool drew.
    build: False for a sprite that is checked and previewed and never exported.
    over: the id of the sprite this one is drawn over (its base), which makes
    this sprite a layer; `over_line` is the file line that says so.
    unoutlined: palette keys that take no outline.
    anim_likes: animation name, sprite id and file line of each `like` that
    `spritefile.load_all` has not resolved (yet, or because it failed).
    anim_rests: animation name and file line of each `rest = true` not resolved.
    """

    id: str
    source: Path
    canvas: Canvas
    frames: tuple[Frame, ...]
    anims: tuple[Anim, ...]
    outline: bool
    grounded: bool
    variant_of: str | None
    auto_outline: bool = False
    build: bool = True
    over: str | None = None
    over_line: int = 0
    unoutlined: frozenset[str] = frozenset()
    anim_likes: tuple[tuple[str, str, int], ...] = ()
    anim_rests: tuple[tuple[str, int], ...] = ()


@dataclass(frozen=True)
class Problem:
    """line=0: no position. pixel=True: a pixel of an image, `col` is x and
    `line` is y, both zero-based."""

    path: Path
    line: int
    col: int
    code: str
    message: str
    pixel: bool = False


@dataclass(frozen=True)
class Placement:
    sprite_id: str
    frame: str
    x: int
    y: int
    w: int
    h: int


@dataclass(frozen=True)
class ExportTarget:
    """`out` is absolute, resolved against the config file's directory.

    canvases, include, exclude: which sprites the target exports
    (`export.select`). None for `canvases` or `include` is no restriction.
    """

    type: str
    out: Path
    name: str | None
    res_path: str | None
    padding: int
    canvases: frozenset[str] | None = None
    include: tuple[str, ...] | None = None
    exclude: tuple[str, ...] = ()


@dataclass(frozen=True)
class PreviewConfig:
    scale: int
    background: tuple[int, int, int, int]


@dataclass(frozen=True)
class Project:
    """`palette` and `canvases` keep file order."""

    root: Path
    palette_path: Path
    palette: dict[str, Color]
    canvases: dict[str, Canvas]
    preview: PreviewConfig
    exports: tuple[ExportTarget, ...]


def hex_colour(rgba: tuple[int, int, int, int]) -> str:
    """`#rrggbb`, or `#rrggbbaa` when the colour is not opaque."""
    digits = "".join(f"{channel:02x}" for channel in rgba)
    return "#" + (digits[:6] if rgba[3] == 255 else digits)


def shown_path(path: Path, root: Path, cwd: Path | None = None) -> str:
    """`path` as the user would type it.

    Relative to `cwd` when that is inside the project or holds the path, so
    the text can be passed straight back to a command or opened. Otherwise
    relative to `root` when under it, else as given.
    """
    if cwd is not None and path.is_absolute() and (path.is_relative_to(cwd) or cwd.is_relative_to(root)):
        return Path(os.path.relpath(path, cwd)).as_posix()
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)


def format_problem(problem: Problem, root: Path, cwd: Path | None = None) -> str:
    """One output line for a problem, with its path as `shown_path` gives it."""
    shown = shown_path(problem.path, root, cwd)
    if problem.pixel:
        return f"{shown}:{problem.col},{problem.line}: {problem.code} {problem.message}"
    if problem.line == 0:
        return f"{shown}: {problem.code} {problem.message}"
    return f"{shown}:{problem.line}:{problem.col}: {problem.code} {problem.message}"
