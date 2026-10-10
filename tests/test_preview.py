import shutil
from dataclasses import replace
from pathlib import Path

import pytest
from PIL import Image

from sprite_tool import preview, render, spritefile
from sprite_tool import project as project_module
from sprite_tool.cli import main
from sprite_tool.preview import CHAR_WIDTH, GAP, GRID_MARGIN, LABEL_GAP, LINE_HEIGHT, MARGIN, SHEET_COLUMNS

DEMO = Path(__file__).parent.parent / "examples" / "demo"

BACKGROUND = (0x3A, 0x3A, 0x3A, 255)
OUTLINE = (0x1A, 0x1C, 0x2C, 255)
ORANGE = (0xEF, 0x7D, 0x57, 255)
BLUE, RED = (0x3B, 0x5D, 0xC9, 255), (0xB1, 0x3E, 0x53, 255)
LIGHT_GREEN = (0xA7, 0xF0, 0x70, 255)


@pytest.fixture
def demo(tmp_path: Path, monkeypatch) -> Path:
    """A copy of the demo project, as the current directory."""
    root = tmp_path / "demo"
    shutil.copytree(DEMO, root, ignore=shutil.ignore_patterns("out", ".preview"))
    monkeypatch.chdir(root)
    return root


@pytest.fixture(scope="module")
def loaded():
    """The demo project and its sprites by id. Read only."""
    project, problems = project_module.load(DEMO)
    sprites, more = spritefile.load_all(project)
    assert not problems and not more
    return project, {sprite.id: sprite for sprite in sprites}


def sprite_image(loaded, sprite_id: str, **options) -> Image.Image:
    project, sprites = loaded
    sprite = sprites[sprite_id]
    variants = [other for other in sprites.values() if other.variant_of == sprite_id]
    return preview.sprite_preview(project, sprite, variants, **options)


# Sprite preview


def test_one_frame_is_the_canvas_upscaled_inside_the_margin(loaded):
    image = sprite_image(loaded, "goblin", scale=6)
    assert image.size == (32 * 6 + 2 * MARGIN, 32 * 6 + 2 * MARGIN)


def test_frames_run_left_to_right_and_variants_follow_on_further_rows(loaded):
    image = sprite_image(loaded, "warrior", scale=6)
    assert image.size == (2 * 32 * 6 + GAP + 2 * MARGIN, 2 * 32 * 6 + GAP + 2 * MARGIN)
    # Row 14, column 10 of the warrior is `b`, which the `red` variant swaps for `r`.
    x, y = MARGIN + 10 * 6 + 3, MARGIN + 14 * 6 + 3
    step = 32 * 6 + GAP
    assert image.getpixel((x, y)) == BLUE
    assert image.getpixel((x + step, y)) == BLUE
    assert image.getpixel((x, y + step)) == RED
    assert image.getpixel((x + step, y + step)) == RED


def test_second_frame_is_drawn_in_the_second_column(loaded):
    # `idle_1` differs from `idle_0` in row 9: column 17 is `o` instead of `k`.
    image = sprite_image(loaded, "warrior", scale=6)
    x, y = MARGIN + 17 * 6 + 3, MARGIN + 9 * 6 + 3
    assert image.getpixel((x, y)) == OUTLINE
    assert image.getpixel((x + 32 * 6 + GAP, y)) == ORANGE


def test_scale_changes_the_size(loaded):
    image = sprite_image(loaded, "warrior", scale=3)
    assert image.size == (2 * 32 * 3 + GAP + 2 * MARGIN, 2 * 32 * 3 + GAP + 2 * MARGIN)


def test_art_pixels_are_solid_blocks_on_the_background(loaded):
    """Nearest neighbour: every pixel of an upscaled art pixel has its colour."""
    image = sprite_image(loaded, "goblin", scale=6)
    project, sprites = loaded
    rows = sprites["goblin"].frames[0].rows
    row, col = next((r, c) for r, line in enumerate(rows) for c, key in enumerate(line) if key == "k")
    block = image.crop((MARGIN + col * 6, MARGIN + row * 6, MARGIN + col * 6 + 6, MARGIN + row * 6 + 6))
    assert block.getcolors() == [(36, OUTLINE)]
    assert rows[0][0] == "."
    assert image.getpixel((MARGIN + 3, MARGIN + 3)) == BACKGROUND
    assert image.getpixel((0, 0)) == BACKGROUND


def test_gap_between_frames_is_background(loaded):
    image = sprite_image(loaded, "warrior", scale=6)
    gap = image.crop((MARGIN + 32 * 6, 0, MARGIN + 32 * 6 + GAP, image.height))
    assert gap.getcolors() == [(GAP * image.height, BACKGROUND)]


def test_a_variant_previewed_directly_is_one_row(loaded):
    image = sprite_image(loaded, "warrior_red", scale=6)
    assert image.size == (2 * 32 * 6 + GAP + 2 * MARGIN, 32 * 6 + 2 * MARGIN)
    assert image.getpixel((MARGIN + 10 * 6 + 3, MARGIN + 14 * 6 + 3)) == RED


def test_variant_rows_are_sorted_by_id(loaded):
    project, sprites = loaded
    warrior, red = sprites["warrior"], sprites["warrior_red"]
    assert preview.sprite_preview(project, warrior, [red, warrior], scale=2).tobytes() == (
        preview.sprite_preview(project, warrior, [warrior, red], scale=2).tobytes()
    )


# Grid


def test_grid_adds_the_margin_and_one_line_per_pixel_boundary(loaded):
    image = sprite_image(loaded, "goblin", scale=6, grid=True)
    side = GRID_MARGIN + 32 * 7 + 1
    assert image.size == (side + 2 * MARGIN, side + 2 * MARGIN)


def test_grid_lines_separate_whole_art_pixels(loaded):
    image = sprite_image(loaded, "goblin", scale=6, grid=True)
    project, sprites = loaded
    rows = sprites["goblin"].frames[0].rows
    row, col = next((r, c) for r, line in enumerate(rows) for c, key in enumerate(line) if key == "k")
    left, top = MARGIN + GRID_MARGIN + col * 7, MARGIN + GRID_MARGIN + row * 7
    # The cell keeps all `scale` pixels of the art; the lines are extra.
    assert image.crop((left + 1, top + 1, left + 7, top + 7)).getcolors() == [(36, OUTLINE)]
    line = image.getpixel((left, top + 3))
    assert line not in (OUTLINE, BACKGROUND)
    assert image.getpixel((left + 3, top)) == line
    # The grid is closed on the right and at the bottom.
    edge = MARGIN + GRID_MARGIN + 32 * 7
    assert image.getpixel((edge, MARGIN + GRID_MARGIN + 3)) == line
    assert image.getpixel((MARGIN + GRID_MARGIN + 3, edge)) == line


def label_ink(image: Image.Image, box: tuple[int, int, int, int]) -> int:
    """How many pixels in `box` are not background."""
    return sum(count for count, colour in image.crop(box).getcolors() if colour != BACKGROUND)


def test_every_fourth_row_and_column_is_labelled_in_the_margin(loaded):
    image = sprite_image(loaded, "goblin", scale=6, grid=True)
    origin = MARGIN + GRID_MARGIN
    for index in range(32):
        start = origin + index * 7 + 1
        column_label = label_ink(image, (start, MARGIN, start + 6, origin))
        row_label = label_ink(image, (MARGIN, start, origin, start + 6))
        if index % 4 == 0:
            assert column_label and row_label, index
        elif index % 4 == 2:
            assert not column_label and not row_label, index


def test_labels_are_the_zero_based_indices(loaded):
    """The label over column 8 is the text `8`, drawn in the built-in font."""
    from PIL import ImageDraw, ImageFont

    image = sprite_image(loaded, "goblin", scale=6, grid=True)
    expected = Image.new("RGBA", (6, 11), BACKGROUND)
    ImageDraw.Draw(expected).text((0, 0), "8", font=ImageFont.load_default_imagefont(), fill=(255, 255, 255, 255))
    centre = MARGIN + GRID_MARGIN + 8 * 7 + 4
    found = image.crop((centre - 3, MARGIN + GRID_MARGIN - 12, centre + 3, MARGIN + GRID_MARGIN - 1))
    assert found.tobytes() == expected.tobytes()


def test_grid_applies_to_every_frame_and_variant(loaded):
    image = sprite_image(loaded, "warrior", scale=6, grid=True)
    side = GRID_MARGIN + 32 * 7 + 1
    assert image.size == (2 * side + GAP + 2 * MARGIN, 2 * side + GAP + 2 * MARGIN)


def test_labels_are_readable_on_a_light_background(loaded):
    from sprite_tool.model import PreviewConfig

    project, sprites = loaded
    light = replace(project, preview=PreviewConfig(scale=6, background=(240, 240, 240, 255)))
    image = preview.sprite_preview(light, sprites["goblin"], [], scale=6, grid=True)
    colours = {colour for _, colour in image.crop((MARGIN, MARGIN, MARGIN + GRID_MARGIN, image.height)).getcolors()}
    assert (0, 0, 0, 255) in colours


# On a tile


def with_display_scale(sprite, display_scale: int):
    return replace(sprite, canvas=replace(sprite.canvas, display_scale=display_scale))


def composite(project, size, tile, tile_at, tile_factor, unit, unit_at, unit_factor) -> Image.Image:
    """What `on_tile` should draw, from explicit positions."""
    expected = Image.new("RGBA", size, BACKGROUND)
    for sprite, at, factor in ((tile, tile_at, tile_factor), (unit, unit_at, unit_factor)):
        art = render.render(sprite.frames[0], project.palette)
        art = art.resize((art.width * factor, art.height * factor), Image.Resampling.NEAREST)
        expected.alpha_composite(art, at)
    return expected


def test_a15_unit_stands_on_the_tile_each_at_its_own_display_scale(loaded):
    """Tile: 16 * 4 * 2 square. Unit: 32 * 2 * 2 square, anchor (16, 32) on the tile's bottom centre."""
    project, sprites = loaded
    unit, tile = sprites["warrior"], sprites["ground_light"]
    image = preview.on_tile(project, unit, tile, scale=2)
    assert image.size == (128 + 2 * MARGIN, 128 + 2 * MARGIN)
    at = (MARGIN, MARGIN)
    assert image.tobytes() == composite(project, image.size, tile, at, 8, unit, at, 4).tobytes()
    # The tile shows through the unit's transparent pixels, and the unit covers the tile.
    assert image.getpixel((MARGIN, MARGIN)) == LIGHT_GREEN
    assert image.getpixel((MARGIN + 10 * 4 + 2, MARGIN + 31 * 4 + 2)) == OUTLINE


def test_unit_anchor_is_at_the_bottom_centre_of_a_larger_tile(loaded):
    project, sprites = loaded
    unit, tile = sprites["warrior"], with_display_scale(sprites["ground_light"], 8)
    image = preview.on_tile(project, unit, tile, scale=2)
    # Tile 256 square. Unit 128 square: anchor column 64 on x = 128, anchor row 128 on y = 256.
    assert image.size == (256 + 2 * MARGIN, 256 + 2 * MARGIN)
    expected = composite(project, image.size, tile, (MARGIN, MARGIN), 16, unit, (MARGIN + 64, MARGIN + 128), 4)
    assert image.tobytes() == expected.tobytes()


def test_image_grows_to_show_a_unit_larger_than_the_tile(loaded):
    project, sprites = loaded
    unit, tile = sprites["warrior"], with_display_scale(sprites["ground_light"], 1)
    image = preview.on_tile(project, unit, tile, scale=2)
    # Tile 32 square. Unit 128 square, reaching 48 left of the tile and 96 above it.
    assert image.size == (128 + 2 * MARGIN, 128 + 2 * MARGIN)
    expected = composite(project, image.size, tile, (MARGIN + 48, MARGIN + 96), 2, unit, (MARGIN, MARGIN), 4)
    assert image.tobytes() == expected.tobytes()


def test_on_tile_scale_is_a_common_factor(loaded):
    project, sprites = loaded
    image = preview.on_tile(project, sprites["goblin"], sprites["ground_light"], scale=1)
    assert image.size == (64 + 2 * MARGIN, 64 + 2 * MARGIN)


def test_on_tile_uses_the_default_frame(loaded):
    project, sprites = loaded
    unit = sprites["warrior"]
    second = replace(unit, frames=unit.frames[::-1])
    tile = sprites["ground_light"]
    assert preview.on_tile(project, unit, tile, 2).tobytes() != preview.on_tile(project, second, tile, 2).tobytes()


# Contact sheet

CELL_H = 64 + LABEL_GAP + LINE_HEIGHT


def art_at(project, sprite, factor: int, image: Image.Image, at: tuple[int, int]) -> bool:
    """Whether `image` shows the sprite's default frame at `at`, on the background."""
    size = (sprite.canvas.width * factor, sprite.canvas.height * factor)
    expected = composite(project, size, sprite, (0, 0), factor, sprite, (0, 0), factor)
    return image.crop((*at, at[0] + size[0], at[1] + size[1])).tobytes() == expected.tobytes()


def test_sheet_groups_by_canvas_class_and_sorts_by_id(loaded):
    project, sprites = loaded
    image = preview.contact_sheet(project, list(sprites.values())[::-1])
    # Units: three cells as wide as the label `warrior_red`. Tile: one as wide as `ground_light`.
    unit_w, tile_w = 11 * CHAR_WIDTH, 12 * CHAR_WIDTH
    assert image.size == (2 * MARGIN + 3 * unit_w + 2 * GAP, 2 * MARGIN + 2 * CELL_H + GAP)
    for column, sprite_id in enumerate(["goblin", "warrior", "warrior_red"]):
        at = (MARGIN + column * (unit_w + GAP) + (unit_w - 64) // 2, MARGIN)
        assert art_at(project, sprites[sprite_id], 2, image, at), sprite_id
    at = (MARGIN + (tile_w - 64) // 2, MARGIN + CELL_H + GAP)
    assert art_at(project, sprites["ground_light"], 4, image, at)


def test_sheet_draws_each_id_under_its_sprite(loaded):
    from PIL import ImageDraw, ImageFont

    project, sprites = loaded
    image = preview.contact_sheet(project, sprites.values())
    unit_w = 11 * CHAR_WIDTH
    for column, sprite_id in enumerate(["goblin", "warrior", "warrior_red"]):
        width = len(sprite_id) * CHAR_WIDTH
        expected = Image.new("RGBA", (width, LINE_HEIGHT), BACKGROUND)
        ImageDraw.Draw(expected).text((0, 0), sprite_id, font=ImageFont.load_default_imagefont(), fill=(255, 255, 255, 255))
        left = MARGIN + column * (unit_w + GAP) + (unit_w - width) // 2
        top = MARGIN + 64 + LABEL_GAP
        assert image.crop((left, top, left + width, top + LINE_HEIGHT)).tobytes() == expected.tobytes(), sprite_id


def test_sheet_wraps_a_large_class_onto_more_rows(loaded):
    project, sprites = loaded
    many = [replace(sprites["goblin"], id=f"g{index:02}") for index in range(SHEET_COLUMNS + 2)]
    image = preview.contact_sheet(project, many)
    assert image.size == (2 * MARGIN + SHEET_COLUMNS * 64 + (SHEET_COLUMNS - 1) * GAP, 2 * MARGIN + 2 * CELL_H + GAP)
    assert art_at(project, many[SHEET_COLUMNS + 1], 2, image, (MARGIN + 64 + GAP, MARGIN + CELL_H + GAP))


def test_sheet_of_no_sprites_is_a_small_blank_image(loaded):
    project, _ = loaded
    image = preview.contact_sheet(project, [])
    assert image.size == (2 * MARGIN, 2 * MARGIN)
    assert image.getcolors() == [(4 * MARGIN * MARGIN, BACKGROUND)]
