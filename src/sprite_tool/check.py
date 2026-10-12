"""Checks that need a resolved grid, and checks on PNG files.

`spritefile` has already reported what it could not parse and left those
frames out, so every frame here is the canvas size and uses palette keys only.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from fnmatch import fnmatchcase
from pathlib import Path

from PIL import Image

from .export import select
from .model import Canvas, Frame, Problem, Project, Sprite, hex_colour
from .project import CONFIG_NAME

TRANSPARENT = "."
MAX_E201_PER_FRAME = 10
MAX_E302_PER_FILE = 10


def run(project: Project, sprites: Sequence[Sprite]) -> list[Problem]:
    """E003, E106, E108, E201, E202, W001 to W005 and W007 for the loaded sprites.

    A variant gets only E003 and E201, so that a fault in its base sprite is
    not reported again for each variant. W006 is the parser's.
    """
    problems = _shared_colours(project)
    problems += _duplicate_ids(project, sprites)
    problems += _file_name_clashes(sprites)
    problems += _selection_problems(project, sprites)
    by_id = _by_id(sprites)
    originals = {(sprite.source, sprite.id): sprite for sprite in sprites if sprite.variant_of is None}
    for sprite in sprites:
        base, fault = layer_base(sprite, by_id)
        if sprite.variant_of is None:
            if fault is not None:
                line = sprite.over_line
                problems.append(Problem(sprite.source, line, 1 if line else 0, "E108", fault))
            problems += _check_sprite(sprite, base)
            problems += _step_problems(sprite, base)
        else:
            problems += _check_variant(sprite, originals.get((sprite.source, sprite.variant_of)), base)
    return problems


def _by_id(sprites: Sequence[Sprite]) -> dict[str, Sprite]:
    """The first sprite of each id, as a reference to an id finds it."""
    by_id: dict[str, Sprite] = {}
    for sprite in sprites:
        by_id.setdefault(sprite.id, sprite)
    return by_id


# --- layers -----------------------------------------------------------------


def layer_base(sprite: Sprite, by_id: dict[str, Sprite]) -> tuple[Sprite | None, str | None]:
    """The sprite that `sprite` is drawn over, or None and why its `over` is bad.

    Both are None for a sprite that is not a layer. A variant of a layer has
    its sprite's base.
    """
    if sprite.over is None:
        return None, None
    base = by_id.get(sprite.over)
    if base is None:
        return None, f"over names unknown sprite {sprite.over!r}"
    if sprite.over in (sprite.id, sprite.variant_of):
        return None, f"over names {sprite.over!r}, the sprite itself"
    if base.over is not None:
        return None, f"over names {sprite.over!r}, which is itself a layer"
    if base.canvas.name != sprite.canvas.name:
        message = f"over names {sprite.over!r}, which is on canvas class {base.canvas.name!r}, not {sprite.canvas.name!r}"
        return None, message
    return base, None


def bases(sprites: Sequence[Sprite]) -> dict[str, Sprite]:
    """Each layer's base, by the layer's id. A layer whose `over` is bad is left out."""
    by_id = _by_id(sprites)
    found = {}
    for sprite in sprites:
        base, _ = layer_base(sprite, by_id)
        if base is not None:
            found.setdefault(sprite.id, base)
    return found


def paired(base: Sprite, frame_name: str) -> Frame:
    """The frame of `base` that a layer's frame called `frame_name` is drawn
    over: the one of the same name, else the default frame."""
    return next((frame for frame in base.frames if frame.name == frame_name), base.frames[0])


def _under(base: Sprite | None, frame: Frame) -> tuple[str, ...] | None:
    return paired(base, frame.name).rows if base is not None else None


def _step_problems(layer: Sprite, base: Sprite | None) -> list[Problem]:
    """W007 for each animation that a layer and its base both have and that
    differs in frame count or lengths. Frame names are each sprite's own."""
    if base is None:
        return []
    theirs = {anim.name: anim for anim in base.anims}
    problems = []
    for anim in layer.anims:
        other = theirs.get(anim.name)
        if other is not None and anim.durations != other.durations:
            message = (
                f"anim {anim.name!r}: {_lengths(anim.durations, 'frames of')}, but {base.id!r} plays"
                f" {_lengths(other.durations, 'of')}; the layers will drift"
            )
            problems.append(Problem(layer.source, anim.line, 1 if anim.line else 0, "W007", message))
    return problems


def _lengths(durations: Sequence[int], word: str) -> str:
    """`2 frames of 600, 600 ms`."""
    return f"{len(durations)} {word} {', '.join(map(str, durations))} ms"


# --- what the targets export ------------------------------------------------


def is_built(sprite: Sprite) -> bool:
    """Whether a build exports the sprite, to the targets that select it."""
    return sprite.build and not is_blank(sprite)


def _selection_problems(project: Project, sprites: Sequence[Sprite]) -> list[Problem]:
    """W004 for a pattern that matches no sprite id, W005 for a sprite no target exports."""
    config = project.root / CONFIG_NAME
    ids = sorted({sprite.id for sprite in sprites})
    problems = []
    for number, target in enumerate(project.exports, start=1):
        for key, patterns in (("include", target.include or ()), ("exclude", target.exclude)):
            for pattern in dict.fromkeys(patterns):
                if not any(fnmatchcase(sprite_id, pattern) for sprite_id in ids):
                    message = f"export {number} ({target.type}): {key} pattern {pattern!r} matches no sprite"
                    problems.append(Problem(config, 0, 0, "W004", message))
    if project.exports:
        built = [sprite for sprite in sprites if is_built(sprite)]
        exported = {sprite.id for target in project.exports for sprite in select(built, target)}
        for sprite in built:
            if sprite.id not in exported:
                message = f"sprite {sprite.id!r} is in no export target; set build = false if that is meant"
                problems.append(Problem(sprite.source, 0, 0, "W005", message))
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


def _file_name_clashes(sprites: Sequence[Sprite]) -> list[Problem]:
    """E003 where a sprite id is also `<id>__<frame>` of another sprite: the
    `frames` target would write both to one file."""
    ids = {sprite.id: sprite for sprite in sprites}
    problems = []
    for sprite in sprites:
        if len(sprite.frames) < 2:
            continue
        for frame in sprite.frames:
            other = ids.get(f"{sprite.id}__{frame.name}")
            if other is not None:
                message = (
                    f"sprite id {other.id!r} clashes with frame {frame.name!r} of sprite {sprite.id!r}"
                    f" (both export as {other.id}.png)"
                )
                problems.append(Problem(other.source, 0, 0, "E003", message))
    return problems


def _shown(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)


# --- sprites ----------------------------------------------------------------


def is_blank(sprite: Sprite) -> bool:
    """Whether nothing has been drawn yet: every frame is fully transparent.

    This is what `sprite new` writes. A blank sprite is a warning and is left
    out of the build, so a sprite that is still to be drawn does not stop the
    others from building.
    """
    return all(_is_clear(frame) for frame in sprite.frames)


def _is_clear(frame: Frame) -> bool:
    return all(key == TRANSPARENT for row in frame.rows for key in row)


def _check_sprite(sprite: Sprite, base: Sprite | None = None) -> list[Problem]:
    """`base` is the sprite a layer is drawn over: the outline rule is then
    checked on the two together, and the layer need not stand on the bottom row."""
    if is_blank(sprite):
        message = f"sprite {sprite.id!r} is blank (nothing drawn yet); it is left out of the build"
        return [_at_frame(sprite, sprite.frames[0], "W003", message)]
    problems = []
    frames = {frame.name: frame for frame in sprite.frames}
    for frame in sprite.frames:
        where = f"frame {frame.name!r}"
        if _is_clear(frame):
            problems.append(_at_frame(sprite, frame, "E106", f"{where} is fully transparent"))
            continue
        if sprite.outline:
            inherited = _inherited_faults(sprite, frame, frames, base)
            faults = [fault for fault in _outline_faults(sprite, frame, _under(base, frame)) if fault not in inherited]
            problems += _outline_problems(sprite, frame, where, faults, base)
        if sprite.grounded and base is None and frame.rows[-1].strip(TRANSPARENT) == "":
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


def _check_variant(variant: Sprite, original: Sprite | None, base: Sprite | None = None) -> list[Problem]:
    """E201 where the swap broke the outline; the faults of `original`, the
    sprite it is a variant of, are left out. `base` is what a layer is drawn over."""
    if not variant.outline:
        return []
    original_frames = {frame.name: frame for frame in original.frames} if original else {}
    problems = []
    for frame in variant.frames:
        under = _under(base, frame)
        original_frame = original_frames.get(frame.name)
        known = set(_outline_faults(original, original_frame, under)) if original and original_frame else set()
        known |= _inherited_faults(variant, frame, {frame.name: frame for frame in variant.frames}, base)
        faults = [fault for fault in _outline_faults(variant, frame, under) if fault not in known]
        where = f"variant {variant.id!r} frame {frame.name!r}"
        problems += _outline_problems(variant, frame, where, faults, base)
    return problems


def _at_frame(sprite: Sprite, frame: Frame, code: str, message: str) -> Problem:
    return Problem(sprite.source, frame.line, 1 if frame.line else 0, code, message)


def _outline_faults(sprite: Sprite, frame: Frame, under: Sequence[str] | None = None) -> Iterator[tuple[int, int]]:
    """(row, col) of each pixel that touches transparency without an outline key.

    `under` is the rows of the base frame a layer's frame is drawn over: a
    pixel next to one the base draws does not touch transparency. Keys the
    sprite lists as `unoutlined` are never at fault.
    """
    exempt = (sprite.canvas.outline or frozenset()) | sprite.unoutlined
    rows = frame.rows
    height, width = len(rows), len(rows[0])

    def is_clear(r: int, c: int) -> bool:
        if not (0 <= r < height and 0 <= c < width):
            return True
        return rows[r][c] == TRANSPARENT and (under is None or under[r][c] == TRANSPARENT)

    for r, row in enumerate(rows):
        for c, key in enumerate(row):
            if key == TRANSPARENT or key in exempt:
                continue
            if is_clear(r - 1, c) or is_clear(r + 1, c) or is_clear(r, c - 1) or is_clear(r, c + 1):
                yield r, c


def _inherited_faults(
    sprite: Sprite, frame: Frame, frames: dict[str, Frame], base: Sprite | None = None
) -> set[tuple[int, int]]:
    """Where the outline faults of a derived frame's parent land in `frame`.

    A fault that a derived frame only carries over is reported once, in the
    frame it comes from; fixing it there fixes every frame derived from it.
    """
    parent = frames.get(frame.parent) if frame.parent else None
    if parent is None or frame.origins is None:
        return set()
    faults = set(_outline_faults(sprite, parent, _under(base, parent)))
    return {
        (r, c) for r, row in enumerate(frame.origins) for c, origin in enumerate(row) if origin in faults
    }


def _outline_problems(
    sprite: Sprite, frame: Frame, where: str, faults: Sequence[tuple[int, int]], base: Sprite | None = None
) -> list[Problem]:
    """One E201 per fault, up to the cap, then one line with the remaining count."""
    faults = list(faults)
    expected = _quoted(sorted(sprite.canvas.outline or ()), "or")
    located = frame.literal and frame.line > 0
    # The tool drew the outline, so what is left is interior with no room for one.
    on_edge = sprite.auto_outline and sprite.variant_of is None
    over = f" over {base.id!r}" if base is not None else ""
    problems = []
    for r, c in faults[:MAX_E201_PER_FRAME]:
        key = frame.rows[r][c]
        if on_edge:
            what = f'{key!r} is on the canvas edge; with outline = "auto" keep the interior 1 pixel inside'
        else:
            what = f"{key!r} touches transparency{over}, expected outline key {expected}"
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
