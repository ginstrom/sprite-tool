"""Dataclasses shared by all modules."""

from __future__ import annotations

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


@dataclass(frozen=True)
class Frame:
    """A resolved frame: `rows` is the full grid, palette keys and '.' only.

    literal=True: the frame was written as a grid; `line` is the 1-based file
    line of row 0, so row r, column c is at (line + r, c + 1).
    literal=False: derived frame; `line` is the line of its definition.
    line=0: position unknown.
    """

    name: str
    rows: tuple[str, ...]
    line: int
    literal: bool


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
    """

    id: str
    source: Path
    canvas: Canvas
    frames: tuple[Frame, ...]
    anims: tuple[Anim, ...]
    outline: bool
    grounded: bool
    variant_of: str | None


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


def format_problem(problem: Problem, root: Path) -> str:
    """One output line for a problem; paths under `root` are shown relative to it."""
    try:
        shown = problem.path.relative_to(root).as_posix()
    except ValueError:
        shown = str(problem.path)
    if problem.pixel:
        return f"{shown}:{problem.col},{problem.line}: {problem.code} {problem.message}"
    if problem.line == 0:
        return f"{shown}: {problem.code} {problem.message}"
    return f"{shown}:{problem.line}:{problem.col}: {problem.code} {problem.message}"
