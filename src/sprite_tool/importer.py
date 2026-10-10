"""A PNG to a single-frame sprite file."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

from . import check
from .model import Canvas, Color, Problem, hex_colour

TRANSPARENT = "."

# With `snap`, an unmatched pixel below this alpha becomes transparent.
SNAP_ALPHA = 128

Rgba = tuple[int, int, int, int]


@dataclass(frozen=True)
class Imported:
    """`rows` is the canvas-sized grid, or empty when `problems` holds an error.

    snapped: one report line per distinct source colour that `snap` changed.
    """

    rows: tuple[str, ...]
    problems: list[Problem]
    snapped: list[str]


def import_png(
    path: Path, canvas: Canvas, palette: Mapping[str, Color], *, scale: int = 1, snap: bool = False
) -> Imported:
    """`to_rows` for an image file; E001 if it cannot be read."""
    try:
        with Image.open(path) as opened:
            image = opened.convert("RGBA")
    except (OSError, ValueError, SyntaxError) as exc:
        return Imported((), [Problem(path, 0, 0, "E001", f"cannot read image: {exc}")], [])
    return to_rows(image, canvas, palette, path, scale=scale, snap=snap)


def to_rows(
    image: Image.Image,
    canvas: Canvas,
    palette: Mapping[str, Color],
    path: Path,
    *,
    scale: int = 1,
    snap: bool = False,
) -> Imported:
    """Map each pixel to a palette key and place the image on the canvas.

    The image is enlarged `scale` times first. E301 if it is then larger than
    the canvas; E302 for each pixel with no exact palette match, at its
    position in the image as given. `path` is only used in the problems.
    """
    image = image.convert("RGBA")
    problems = []
    width, height = image.width * scale, image.height * scale
    if width > canvas.width or height > canvas.height:
        scaled = f" at --scale {scale}" if scale != 1 else ""
        message = f"image is {width}x{height}{scaled}, canvas {canvas.name!r} is {canvas.width}x{canvas.height}"
        problems.append(Problem(path, 0, 0, "E301", message))

    # The first key in palette order wins a shared colour.
    exact: dict[Rgba, str] = {}
    for color in palette.values():
        exact.setdefault(color.rgba, color.key)

    keys = []
    unmatched = []
    snaps: dict[Rgba, tuple[str, int]] = {}
    for index, rgba in enumerate(image.get_flattened_data()):
        if rgba[3] == 0:
            key = TRANSPARENT
        elif rgba in exact:
            key = exact[rgba]
        elif snap and palette:
            key, seen = snaps.get(rgba) or (_nearest(rgba, palette), 0)
            snaps[rgba] = key, seen + 1
        else:
            y, x = divmod(index, image.width)
            unmatched.append((x, y, rgba))
            key = TRANSPARENT
        keys.append(key)
    problems += check.off_palette_problems(path, unmatched)
    if problems:
        return Imported((), problems, [])

    left, top = _origin((width, height), canvas)
    source = ["".join(keys[start : start + image.width]) for start in range(0, len(keys), image.width)]
    rows = [TRANSPARENT * canvas.width] * top
    for row in source:
        wide = "".join(key * scale for key in row)
        rows += [TRANSPARENT * left + wide + TRANSPARENT * (canvas.width - left - width)] * scale
    rows += [TRANSPARENT * canvas.width] * (canvas.height - top - height)

    snapped = [
        f"{hex_colour(rgba)} -> {key} ({_described(key, palette)}) x{seen}"
        for rgba, (key, seen) in sorted(snaps.items())
    ]
    return Imported(tuple(rows), [], snapped)


def sprite_text(canvas_name: str, rows: tuple[str, ...]) -> str:
    """The sprite file for one frame, `main`, holding `rows`."""
    grid = "".join(row + "\n" for row in rows)
    return f'canvas = "{canvas_name}"\n\n[frames]\nmain = """\n{grid}"""\n'


def _nearest(rgba: Rgba, palette: Mapping[str, Color]) -> str:
    """The key nearest in RGB, the first in palette order on a tie; '.' for a faint pixel."""
    if rgba[3] < SNAP_ALPHA:
        return TRANSPARENT

    def distance(color: Color) -> int:
        return sum((a - b) ** 2 for a, b in zip(rgba[:3], color.rgba[:3]))

    return min(palette.values(), key=distance).key


def _described(key: str, palette: Mapping[str, Color]) -> str:
    return "transparent" if key == TRANSPARENT else hex_colour(palette[key].rgba)


def _origin(size: tuple[int, int], canvas: Canvas) -> tuple[int, int]:
    """Top-left of an image whose bottom-centre is on the anchor, kept inside the canvas."""
    width, height = size
    left = canvas.anchor[0] - width // 2
    top = canvas.anchor[1] - height
    return (
        max(0, min(left, canvas.width - width)),
        max(0, min(top, canvas.height - height)),
    )
