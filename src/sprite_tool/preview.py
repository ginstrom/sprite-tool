"""Preview images: a sprite's frames upscaled, with an optional pixel grid; a
sprite standing on a tile; a contact sheet of every sprite; and an animation
as a labelled strip and as the frames of a GIF.

Each can be drawn under a tint, the colour a game draws the sprite in; only
the sprite's own pixels are tinted. `panels` puts the images of one sprite
under several tints side by side.

A layer (a sprite with `over`) is drawn over its base wherever it is drawn:
each function takes the base, or `bases`, the base of each layer by the
layer's id, as `check.bases` gives it.

Previews are for looking at. They are not exports: nothing here is
byte-stable across Pillow versions, and nothing goes through the manifest.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from sprite_tool import render
from sprite_tool.check import paired
from sprite_tool.model import Anim, Frame, Project, Sprite, Tint

# Background border around every preview image.
MARGIN = 8
# Space between frames, and between rows of frames.
GAP = 8
# Space left of and above a gridded frame, for the row and column indices.
GRID_MARGIN = 20
# Every row and column whose index is a multiple of this is labelled.
GRID_LABEL_EVERY = 4
# Common enlargement for `--on` when `--scale` is not given.
ON_TILE_SCALE = 2
# Most sprites in one row of the contact sheet.
SHEET_COLUMNS = 8
# Space between a sprite on the contact sheet and the id under it.
LABEL_GAP = 2

# Pillow's built-in bitmap font: fixed width, no font file, no FreeType.
_FONT = ImageFont.load_default_imagefont()
CHAR_WIDTH = 6
LINE_HEIGHT = 11

# What `--points` draws each point's pixel in: muted palettes do not use it.
POINT_MARKER = (0xFF, 0x00, 0xFF, 0xFF)

# The shortest frame of a GIF that viewers honour, and the unit GIF counts time in.
GIF_MIN_MS = 20
GIF_TICK_MS = 10

Colour = tuple[int, int, int, int]
NO_BASES: Mapping[str, Sprite] = {}


def tinted(image: Image.Image, tint: Tint | None) -> Image.Image:
    """An RGBA image as a game draws it under `tint`, on 8-bit channels.

    multiply: each channel, alpha included, becomes `round(pixel * tint / 255)`.
    fill: the colour becomes the tint's, the alpha is multiplied as above.
    """
    if tint is None:
        return image
    tables = [[(value * channel + 127) // 255 for value in range(256)] for channel in tint.colour]
    if tint.mode == "fill":
        tables[:3] = [[channel] * 256 for channel in tint.colour[:3]]
    return image.point([entry for table in tables for entry in table])


def tint_label(tint: Tint | None) -> str:
    """What a panel drawn under `tint` is labelled: its label, `none` for no tint."""
    if tint is None:
        return "none"
    return tint.label + (" fill" if tint.mode == "fill" else "")


def drawn(
    project: Project,
    sprite: Sprite,
    frame: Frame,
    base: Sprite | None = None,
    points: bool = False,
    tint: Tint | None = None,
) -> Image.Image:
    """The frame's image under `tint`; for a layer, over the frame of `base`
    it is paired with, which is not tinted. With `points`, each point's pixel
    is `POINT_MARKER`, one sprite pixel at any scale."""
    art = tinted(render.render(frame, project.palette), tint)
    if base is not None:
        art = Image.alpha_composite(render.render(paired(base, frame.name), project.palette), art)
    if points:
        for _, position in frame.points:
            art.putpixel(position, POINT_MARKER)
    return art


def sprite_preview(
    project: Project,
    sprite: Sprite,
    variants: Iterable[Sprite],
    scale: int,
    grid: bool = False,
    display: bool = False,
    base: Sprite | None = None,
    points: bool = False,
    tint: Tint | None = None,
) -> Image.Image:
    """Every frame of `sprite` left to right, then one row per variant, by id.
    A layer and its variants are drawn over `base`. `points`: mark them.
    `tint`: every row is drawn under it.

    With `display`, each row's frames follow again at the class's
    `display_scale`, the size the game draws them, top-aligned and without the
    grid. They are left out when that is `scale`.
    """
    rows = [sprite, *sorted(variants, key=lambda variant: variant.id)]
    # Each group is every row's tiles at one size; the groups stand side by side.
    arts = [[drawn(project, row, frame, base, points, tint) for frame in row.frames] for row in rows]
    groups = [[[_frame_tile(project, art, scale, grid) for art in row] for row in arts]]
    game_scale = sprite.canvas.display_scale
    if display and game_scale != scale:
        groups.append([[_frame_tile(project, art, game_scale, False) for art in row] for row in arts])
    columns = max(len(row.frames) for row in rows)
    sizes = [group[0][0].size for group in groups]
    row_h = max(tile_h for _, tile_h in sizes)
    # Where each group starts: after the group before it and a gap.
    lefts = [MARGIN]
    for tile_w, _ in sizes:
        lefts.append(lefts[-1] + columns * (tile_w + GAP))
    image = Image.new(
        "RGBA",
        (lefts[-1] - GAP + MARGIN, 2 * MARGIN + len(rows) * row_h + (len(rows) - 1) * GAP),
        project.preview.background,
    )
    for group, left, (tile_w, _) in zip(groups, lefts, sizes):
        for r, row in enumerate(group):
            for c, tile in enumerate(row):
                image.paste(tile, (left + c * (tile_w + GAP), MARGIN + r * (row_h + GAP)))
    return image


def stack(project: Project, images: Iterable[Image.Image]) -> Image.Image:
    """The images one under another, left aligned, on the preview background.

    Each already has its own margin, so nothing is added between them. One
    image is returned as it is.
    """
    images = list(images)
    if len(images) == 1:
        return images[0]
    result = Image.new(
        "RGBA", (max(image.width for image in images), sum(image.height for image in images)), project.preview.background
    )
    y = 0
    for image in images:
        result.paste(image, (0, y))
        y += image.height
    return result


def panels(project: Project, labelled: Sequence[tuple[str, Image.Image]]) -> Image.Image:
    """The images left to right on the preview background, each under its
    label. A panel is as wide as the wider of its image and its label with a
    margin each side; the images keep their own margins."""
    background = project.preview.background
    widths = [max(image.width, len(label) * CHAR_WIDTH + 2 * MARGIN) for label, image in labelled]
    top = MARGIN + LINE_HEIGHT + LABEL_GAP
    result = Image.new("RGBA", (sum(widths), top + max(image.height for _, image in labelled)), background)
    draw = ImageDraw.Draw(result)
    x = 0
    for (label, image), width in zip(labelled, widths):
        draw.text((x + MARGIN, MARGIN), label, font=_FONT, fill=_ink(background))
        result.paste(image, (x, top))
        x += width
    return result


def on_tile(
    project: Project,
    sprite: Sprite,
    tile: Sprite,
    scale: int,
    bases: Mapping[str, Sprite] = NO_BASES,
    points: bool = False,
    tint: Tint | None = None,
) -> Image.Image:
    """The default frame of `sprite` standing on the default frame of `tile`.

    Each is enlarged by its class's `display_scale` times `scale`, and the
    sprite's anchor is put on the bottom centre of the tile. `points`: mark
    the sprite's. `tint`: the sprite's, never the tile's.
    """
    ground = _display(project, tile, scale, bases.get(tile.id))
    figure = _display(project, sprite, scale, bases.get(sprite.id), points, tint)
    factor = sprite.canvas.display_scale * scale
    # Positions with the tile's top left at the origin.
    figure_x = ground.width // 2 - sprite.canvas.anchor[0] * factor
    figure_y = ground.height - sprite.canvas.anchor[1] * factor
    left, top = min(0, figure_x), min(0, figure_y)
    right, bottom = max(ground.width, figure_x + figure.width), max(ground.height, figure_y + figure.height)
    image = Image.new("RGBA", (2 * MARGIN + right - left, 2 * MARGIN + bottom - top), project.preview.background)
    image.alpha_composite(ground, (MARGIN - left, MARGIN - top))
    image.alpha_composite(figure, (MARGIN - left + figure_x, MARGIN - top + figure_y))
    return image


def contact_sheet(
    project: Project, sprites: Iterable[Sprite], bases: Mapping[str, Sprite] = NO_BASES
) -> Image.Image:
    """Every sprite's default frame at its class's `display_scale`, with its id
    underneath, and after a sprite with tints its default frame under each,
    with the tint's name underneath. Classes are in config order, each
    starting a new row; sprites are sorted by id."""
    sprites = list(sprites)
    background = project.preview.background
    # sprite, tint, label, cell x, cell y, cell width
    cells: list[tuple[Sprite, Tint | None, str, int, int, int]] = []
    width, y = 0, MARGIN
    for name in project.canvases:
        group = sorted((sprite for sprite in sprites if sprite.canvas.name == name), key=lambda sprite: sprite.id)
        if not group:
            continue
        entries = [
            entry
            for sprite in group
            for entry in [(sprite, None, sprite.id), *((sprite, tint, tint.label) for _, tint in sprite.tints)]
        ]
        canvas = group[0].canvas
        cell_w = max(canvas.width * canvas.display_scale, *(len(label) * CHAR_WIDTH for _, _, label in entries))
        cell_h = canvas.height * canvas.display_scale + LABEL_GAP + LINE_HEIGHT
        for index, (sprite, tint, label) in enumerate(entries):
            row, column = divmod(index, SHEET_COLUMNS)
            cells.append((sprite, tint, label, MARGIN + column * (cell_w + GAP), y + row * (cell_h + GAP), cell_w))
        columns = min(len(entries), SHEET_COLUMNS)
        rows = -(-len(entries) // SHEET_COLUMNS)
        width = max(width, columns * cell_w + (columns - 1) * GAP)
        y += rows * (cell_h + GAP)

    height = y - GAP - MARGIN if cells else 0
    image = Image.new("RGBA", (2 * MARGIN + width, 2 * MARGIN + height), background)
    draw = ImageDraw.Draw(image)
    for sprite, tint, label, x, cell_y, cell_w in cells:
        art = _display(project, sprite, 1, bases.get(sprite.id), tint=tint)
        image.alpha_composite(art, (x + (cell_w - art.width) // 2, cell_y))
        label_x = x + (cell_w - len(label) * CHAR_WIDTH) // 2
        draw.text((label_x, cell_y + art.height + LABEL_GAP), label, font=_FONT, fill=_ink(background))
    return image


def anim_frames(
    project: Project,
    sprite: Sprite,
    anim: Anim,
    base: Sprite | None,
    scale: int,
    points: bool = False,
    tint: Tint | None = None,
) -> list[tuple[Image.Image, int]]:
    """A tile and its length in ms for each entry of `anim`, in play order.

    A tile is the frame on the preview background, `scale` times larger, a
    layer's over the frame of `base` with the same name. `points`: mark them.
    `tint`: the sprite's pixels are drawn under it.
    """
    frames = {frame.name: frame for frame in sprite.frames}
    tiles = {
        name: _frame_tile(project, drawn(project, sprite, frames[name], base, points, tint), scale, False)
        for name in dict.fromkeys(anim.frames)
    }
    return [(tiles[name], ms) for name, ms in zip(anim.frames, anim.durations)]


def anim_strip(
    project: Project,
    sprite: Sprite,
    anim: Anim,
    base: Sprite | None,
    scale: int,
    points: bool = False,
    tint: Tint | None = None,
) -> Image.Image:
    """The tiles of `anim` left to right in play order, each over its frame's
    name and, on a second line, its length. A cell is as wide as the wider of
    its tile and its label."""
    background = project.preview.background
    cells = []  # tile, label lines, cell width
    for (tile, ms), name in zip(anim_frames(project, sprite, anim, base, scale, points, tint), anim.frames):
        labels = [name, f"{ms} ms"]
        cells.append((tile, labels, max(tile.width, *(len(label) * CHAR_WIDTH for label in labels))))
    tile_h = cells[0][0].height
    width = sum(cell_w for _, _, cell_w in cells) + (len(cells) - 1) * GAP
    height = tile_h + LABEL_GAP + 2 * LINE_HEIGHT
    image = Image.new("RGBA", (2 * MARGIN + width, 2 * MARGIN + height), background)
    draw = ImageDraw.Draw(image)
    x = MARGIN
    for tile, labels, cell_w in cells:
        image.paste(tile, (x + (cell_w - tile.width) // 2, MARGIN))
        for index, label in enumerate(labels):
            label_x = x + (cell_w - len(label) * CHAR_WIDTH) // 2
            label_y = MARGIN + tile_h + LABEL_GAP + index * LINE_HEIGHT
            draw.text((label_x, label_y), label, font=_FONT, fill=_ink(background))
        x += cell_w + GAP
    return image


def anim_panels(
    project: Project, labelled: Sequence[tuple[str, Sequence[tuple[Image.Image, int]]]]
) -> list[tuple[Image.Image, int]]:
    """The frames of one animation under several tints, `(label, anim_frames)`,
    as one frame list: each frame has every tint's tile side by side under
    its label, so they play in step."""
    played = zip(*(frames for _, frames in labelled))
    return [
        (panels(project, [(label, _framed(project, tile)) for (label, _), (tile, _) in zip(labelled, step)]), step[0][1])
        for step in played
    ]


def gif_ms(ms: int) -> int:
    """A frame length as a GIF can hold it: to the nearest hundredth of a
    second, and no shorter than viewers honour."""
    return max(GIF_MIN_MS, (ms + GIF_TICK_MS // 2) // GIF_TICK_MS * GIF_TICK_MS)


def save_gif(path: Path, frames: Sequence[tuple[Image.Image, int]], loop: bool) -> None:
    """Write `frames`, tiles and their lengths in ms, as an animated GIF that
    loops forever or plays once.

    Pillow writes a tile equal to the one before it as more time on that one,
    so a repeated frame plays the same and is not a frame of its own.
    """
    tiles = [tile.convert("RGB") for tile, _ in frames]
    options: dict[str, object] = {"loop": 0} if loop else {}
    tiles[0].save(
        path,
        format="GIF",
        save_all=True,
        append_images=tiles[1:],
        duration=[gif_ms(ms) for _, ms in frames],
        **options,
    )


def _display(
    project: Project,
    sprite: Sprite,
    scale: int,
    base: Sprite | None = None,
    points: bool = False,
    tint: Tint | None = None,
) -> Image.Image:
    """The sprite's default frame at its class's `display_scale` times `scale`."""
    art = drawn(project, sprite, sprite.frames[0], base, points, tint)
    return _enlarge(art, sprite.canvas.display_scale * scale)


def _frame_tile(project: Project, art: Image.Image, scale: int, grid: bool) -> Image.Image:
    """One frame's image on the background, `scale` times larger, with the grid if asked."""
    background = project.preview.background
    if not grid:
        return _on_background(_enlarge(art, scale), background)

    # Each art pixel is a cell of `scale` pixels plus a one-pixel line on its
    # left and top, so the lines hide none of the art.
    pitch = scale + 1
    width, height = art.width * pitch + 1, art.height * pitch + 1
    ink = _ink(background)
    line = tuple((a + b) // 2 for a, b in zip(background[:3], ink[:3])) + (255,)
    tile = Image.new("RGBA", (GRID_MARGIN + width, GRID_MARGIN + height), background)
    tile.paste(_on_background(_enlarge(art, pitch), background), (GRID_MARGIN, GRID_MARGIN))
    draw = ImageDraw.Draw(tile)
    for col in range(art.width + 1):
        x = GRID_MARGIN + col * pitch
        draw.line([(x, GRID_MARGIN), (x, GRID_MARGIN + height - 1)], fill=line)
    for row in range(art.height + 1):
        y = GRID_MARGIN + row * pitch
        draw.line([(GRID_MARGIN, y), (GRID_MARGIN + width - 1, y)], fill=line)

    # Zero-based indices, centred on their cell: columns above, rows to the left.
    for index in range(0, max(art.width, art.height), GRID_LABEL_EVERY):
        label = str(index)
        label_w = len(label) * CHAR_WIDTH
        centre = GRID_MARGIN + index * pitch + 1 + scale // 2
        if index < art.width:
            draw.text((centre - label_w // 2, GRID_MARGIN - 1 - LINE_HEIGHT), label, font=_FONT, fill=ink)
        if index < art.height:
            draw.text((GRID_MARGIN - 2 - label_w, centre - LINE_HEIGHT // 2), label, font=_FONT, fill=ink)
    return tile


def _framed(project: Project, image: Image.Image) -> Image.Image:
    """`image` with a `MARGIN` of background all round."""
    framed = Image.new("RGBA", (image.width + 2 * MARGIN, image.height + 2 * MARGIN), project.preview.background)
    framed.paste(image, (MARGIN, MARGIN))
    return framed


def _enlarge(image: Image.Image, factor: int) -> Image.Image:
    return image.resize((image.width * factor, image.height * factor), Image.Resampling.NEAREST)


def _on_background(image: Image.Image, background: Colour) -> Image.Image:
    return Image.alpha_composite(Image.new("RGBA", image.size, background), image)


def _ink(background: Colour) -> Colour:
    """Black or white, whichever stands out against `background`."""
    red, green, blue, _ = background
    light = 299 * red + 587 * green + 114 * blue > 128 * 1000
    return (0, 0, 0, 255) if light else (255, 255, 255, 255)
