"""Dataclasses shared by all modules."""

from __future__ import annotations

import os
from dataclasses import dataclass
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
    `parent`, `shift` and `flip` say how it was made from another frame.
    line=0: position unknown.
    """

    name: str
    rows: tuple[str, ...]
    line: int
    literal: bool
    parent: str | None = None
    shift: tuple[int, int] = (0, 0)
    flip: bool = False


@dataclass(frozen=True)
class Anim:
    name: str
    frames: tuple[str, ...]
    ms: int
    loop: bool


@dataclass(frozen=True)
class Sprite:
    """`frames[0]` is the default frame.

    outline / grounded: whether the canvas rule applies after per-sprite opt-out.
    variant_of: the base sprite id for a variant, else None.
    auto_outline: the file says `outline = "auto"`; the frames already hold
    the outline the tool drew.
    build: False for a sprite that is checked and previewed and never exported.
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
    """`out` is absolute, resolved against the config file's directory."""

    type: str
    out: Path
    name: str | None
    res_path: str | None
    padding: int


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
