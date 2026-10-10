"""Checks that need a resolved grid, and checks on PNG files.

`spritefile` has already reported what it could not parse and left those
frames out, so every frame here is the canvas size and uses palette keys only.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from pathlib import Path

from PIL import Image

from .model import Canvas, Frame, Problem, Project, Sprite, hex_colour

TRANSPARENT = "."
MAX_E201_PER_FRAME = 10
MAX_E302_PER_FILE = 10


def run(project: Project, sprites: Sequence[Sprite]) -> list[Problem]:
    """E003, E106, E201, E202, W001 and W002 for the loaded sprites.

    A variant gets only E003 and E201, so that a fault in its base sprite is
    not reported again for each variant.
    """
    problems = _shared_colours(project)
    problems += _duplicate_ids(project, sprites)
    bases = {(sprite.source, sprite.id): sprite for sprite in sprites if sprite.variant_of is None}
    for sprite in sprites:
        if sprite.variant_of is None:
            problems += _check_sprite(sprite)
        else:
            problems += _check_variant(sprite, bases.get((sprite.source, sprite.variant_of)))
    return problems


def _quoted(keys: Sequence[str], last: str) -> str:
    """`'a'`, `'a' and 'b'`, `'a', 'b' and 'c'`, with `last` as the final word."""
    names = [repr(key) for key in keys]
    if len(names) == 1:
        return names[0]
    return f"{', '.join(names[:-1])} {last} {names[-1]}"


# --- palette and ids --------------------------------------------------------


def _shared_colours(project: Project) -> list[Problem]:
    keys_by_colour: dict[tuple[int, int, int, int], list[str]] = {}
    for color in project.palette.values():
        keys_by_colour.setdefault(color.rgba, []).append(color.key)
    problems = []
    for rgba, keys in keys_by_colour.items():
        if len(keys) > 1:
            message = f"palette keys {_quoted(keys, 'and')} share the colour {hex_colour(rgba)}"
            problems.append(Problem(project.palette_path, 0, 0, "W001", message))
    return problems


def _duplicate_ids(project: Project, sprites: Sequence[Sprite]) -> list[Problem]:
    sources: dict[str, set[Path]] = {}
    for sprite in sprites:
        sources.setdefault(sprite.id, set()).add(sprite.source)
    problems = []
    for sprite_id, paths in sorted(sources.items()):
        for path in sorted(paths) if len(paths) > 1 else ():
            others = ", ".join(_shown(other, project.root) for other in sorted(paths - {path}))
            problems.append(Problem(path, 0, 0, "E003", f"duplicate sprite id {sprite_id!r}, also in {others}"))
    return problems


def _shown(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)


# --- sprites ----------------------------------------------------------------


def _check_sprite(sprite: Sprite) -> list[Problem]:
    problems = []
    for frame in sprite.frames:
        where = f"frame {frame.name!r}"
        if all(key == TRANSPARENT for row in frame.rows for key in row):
            problems.append(_at_frame(sprite, frame, "E106", f"{where} is fully transparent"))
            continue
        if sprite.outline:
            problems += _outline_problems(sprite, frame, where, _outline_faults(sprite, frame))
        if sprite.grounded and frame.rows[-1].strip(TRANSPARENT) == "":
            message = f"{where}: bottom row is empty, sprite must stand on it"
            line = frame.line + len(frame.rows) - 1 if frame.literal and frame.line else frame.line
            problems.append(Problem(sprite.source, line, 1 if line else 0, "E202", message))

    if sprite.anims:
        used = {name for anim in sprite.anims for name in anim.frames}
        unused = [frame for frame in sprite.frames if frame.name not in used]
        if unused:
            names = ", ".join(frame.name for frame in unused)
            problems.append(_at_frame(sprite, unused[0], "W002", f"frames not used by any animation: {names}"))
    return problems


def _check_variant(variant: Sprite, base: Sprite | None) -> list[Problem]:
    """E201 where the swap broke the outline; the base's own faults are left out."""
    if not variant.outline:
        return []
    base_frames = {frame.name: frame for frame in base.frames} if base else {}
    problems = []
    for frame in variant.frames:
        base_frame = base_frames.get(frame.name)
        in_base = set(_outline_faults(base, base_frame)) if base and base_frame else set()
        faults = [fault for fault in _outline_faults(variant, frame) if fault not in in_base]
        where = f"variant {variant.id!r} frame {frame.name!r}"
        problems += _outline_problems(variant, frame, where, faults)
    return problems


def _at_frame(sprite: Sprite, frame: Frame, code: str, message: str) -> Problem:
    return Problem(sprite.source, frame.line, 1 if frame.line else 0, code, message)


def _outline_faults(sprite: Sprite, frame: Frame) -> Iterator[tuple[int, int]]:
    """(row, col) of each pixel that touches transparency without an outline key."""
    allowed = sprite.canvas.outline or frozenset()
    rows = frame.rows
    height, width = len(rows), len(rows[0])

    def is_clear(r: int, c: int) -> bool:
        return not (0 <= r < height and 0 <= c < width) or rows[r][c] == TRANSPARENT

    for r, row in enumerate(rows):
        for c, key in enumerate(row):
            if key == TRANSPARENT or key in allowed:
                continue
            if is_clear(r - 1, c) or is_clear(r + 1, c) or is_clear(r, c - 1) or is_clear(r, c + 1):
                yield r, c


def _outline_problems(sprite: Sprite, frame: Frame, where: str, faults: Sequence[tuple[int, int]]) -> list[Problem]:
    """One E201 per fault, up to the cap, then one line with the remaining count."""
    faults = list(faults)
    expected = _quoted(sorted(sprite.canvas.outline or ()), "or")
    located = frame.literal and frame.line > 0
    problems = []
    for r, c in faults[:MAX_E201_PER_FRAME]:
        key = frame.rows[r][c]
        what = f"{key!r} touches transparency, expected outline key {expected}"
        if located:
            problems.append(Problem(sprite.source, frame.line + r, c + 1, "E201", f"{where}: {what}"))
        else:
            problems.append(_at_frame(sprite, frame, "E201", f"{where} row {r}, col {c}: {what}"))
    extra = len(faults) - MAX_E201_PER_FRAME
    if extra > 0:
        noun = "problem" if extra == 1 else "problems"
        problems.append(_at_frame(sprite, frame, "E201", f"{extra} more outline {noun} in {where}"))
    return problems


# --- PNG files --------------------------------------------------------------


def check_png(project: Project, path: Path, canvas: Canvas) -> list[Problem]:
    """E301 and E302 for one image file; E001 if it cannot be read.

    An E302 problem is at a pixel: `col` is x and `line` is y.
    """
    try:
        with Image.open(path) as opened:
            image = opened.convert("RGBA")
    except (OSError, ValueError, SyntaxError) as exc:
        return [Problem(path, 0, 0, "E001", f"cannot read image: {exc}")]

    problems = []
    if image.size != (canvas.width, canvas.height):
        message = f"image is {image.width}x{image.height}, canvas {canvas.name!r} is {canvas.width}x{canvas.height}"
        problems.append(Problem(path, 0, 0, "E301", message))

    problems += off_palette_problems(
        path,
        [
            (*reversed(divmod(index, image.width)), rgba)
            for index, rgba in enumerate(image.get_flattened_data())
            if not is_palette_colour(project, rgba)
        ],
    )
    return problems


def off_palette_problems(path: Path, pixels: Sequence[tuple[int, int, tuple[int, int, int, int]]]) -> list[Problem]:
    """One E302 per `(x, y, colour)`, up to the cap, then one line with the remaining count."""
    problems = [
        Problem(path, y, x, "E302", f"colour {hex_colour(rgba)} is not in the palette", pixel=True)
        for x, y, rgba in pixels[:MAX_E302_PER_FILE]
    ]
    extra = len(pixels) - MAX_E302_PER_FILE
    if extra > 0:
        noun = "pixel" if extra == 1 else "pixels"
        problems.append(Problem(path, 0, 0, "E302", f"{extra} more {noun} not in the palette"))
    return problems


def is_palette_colour(project: Project, rgba: tuple[int, int, int, int]) -> bool:
    """Whether an image pixel is transparent (alpha 0) or exactly a palette colour."""
    return rgba[3] == 0 or any(color.rgba == rgba for color in project.palette.values())
