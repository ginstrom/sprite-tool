"""Preview images: a sprite's frames upscaled, with an optional pixel grid; a
sprite standing on a tile; and a contact sheet of every sprite.

Previews are for looking at. They are not exports: nothing here is
byte-stable across Pillow versions, and nothing goes through the manifest.
"""

from __future__ import annotations

from collections.abc import Iterable

from PIL import Image, ImageDraw, ImageFont

from sprite_tool import render
from sprite_tool.model import Frame, Project, Sprite

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

Colour = tuple[int, int, int, int]


def sprite_preview(
    project: Project,
    sprite: Sprite,
    variants: Iterable[Sprite],
    scale: int,
    grid: bool = False,
    display: bool = False,
) -> Image.Image:
    """Every frame of `sprite` left to right, then one row per variant, by id.

    With `display`, each row's frames follow again at the class's
    `display_scale`, the size the game draws them, top-aligned and without the
    grid. They are left out when that is `scale`.
    """
    rows = [sprite, *sorted(variants, key=lambda variant: variant.id)]
    # Each group is every row's tiles at one size; the groups stand side by side.
    groups = [[[_frame_tile(project, frame, scale, grid) for frame in row.frames] for row in rows]]
    game_scale = sprite.canvas.display_scale
    if display and game_scale != scale:
        groups.append([[_frame_tile(project, frame, game_scale, False) for frame in row.frames] for row in rows])
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


def on_tile(project: Project, sprite: Sprite, tile: Sprite, scale: int) -> Image.Image:
    """The default frame of `sprite` standing on the default frame of `tile`.

    Each is enlarged by its class's `display_scale` times `scale`, and the
    sprite's anchor is put on the bottom centre of the tile.
    """
    ground = _display(project, tile, scale)
    figure = _display(project, sprite, scale)
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


def contact_sheet(project: Project, sprites: Iterable[Sprite]) -> Image.Image:
    """Every sprite's default frame at its class's `display_scale`, with its id
    underneath. Classes are in config order, each starting a new row; sprites
    are sorted by id."""
    sprites = list(sprites)
    background = project.preview.background
    cells: list[tuple[Sprite, int, int, int]] = []  # sprite, cell x, cell y, cell width
    width, y = 0, MARGIN
    for name in project.canvases:
        group = sorted((sprite for sprite in sprites if sprite.canvas.name == name), key=lambda sprite: sprite.id)
        if not group:
            continue
        canvas = group[0].canvas
        cell_w = max(canvas.width * canvas.display_scale, *(len(sprite.id) * CHAR_WIDTH for sprite in group))
        cell_h = canvas.height * canvas.display_scale + LABEL_GAP + LINE_HEIGHT
        for index, sprite in enumerate(group):
            row, column = divmod(index, SHEET_COLUMNS)
            cells.append((sprite, MARGIN + column * (cell_w + GAP), y + row * (cell_h + GAP), cell_w))
        columns = min(len(group), SHEET_COLUMNS)
        rows = -(-len(group) // SHEET_COLUMNS)
        width = max(width, columns * cell_w + (columns - 1) * GAP)
        y += rows * (cell_h + GAP)

    height = y - GAP - MARGIN if cells else 0
    image = Image.new("RGBA", (2 * MARGIN + width, 2 * MARGIN + height), background)
    draw = ImageDraw.Draw(image)
    for sprite, x, cell_y, cell_w in cells:
        art = _display(project, sprite, 1)
        image.alpha_composite(art, (x + (cell_w - art.width) // 2, cell_y))
        label_x = x + (cell_w - len(sprite.id) * CHAR_WIDTH) // 2
        draw.text((label_x, cell_y + art.height + LABEL_GAP), sprite.id, font=_FONT, fill=_ink(background))
    return image


def _display(project: Project, sprite: Sprite, scale: int) -> Image.Image:
    """The sprite's default frame at its class's `display_scale` times `scale`."""
    art = render.render(sprite.frames[0], project.palette)
    return _enlarge(art, sprite.canvas.display_scale * scale)


def _frame_tile(project: Project, frame: Frame, scale: int, grid: bool) -> Image.Image:
    """One frame on the background, `scale` times larger, with the grid if asked."""
    background = project.preview.background
    art = render.render(frame, project.palette)
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


def _enlarge(image: Image.Image, factor: int) -> Image.Image:
    return image.resize((image.width * factor, image.height * factor), Image.Resampling.NEAREST)


def _on_background(image: Image.Image, background: Colour) -> Image.Image:
    return Image.alpha_composite(Image.new("RGBA", image.size, background), image)


def _ink(background: Colour) -> Colour:
    """Black or white, whichever stands out against `background`."""
    red, green, blue, _ = background
    light = 299 * red + 587 * green + 114 * blue > 128 * 1000
    return (0, 0, 0, 255) if light else (255, 255, 255, 255)
