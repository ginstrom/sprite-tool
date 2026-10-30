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


# Game size

# The demo's `unit` class: 32 pixels square, drawn by the game at `display_scale` 2.
ENLARGED, GAME = 32 * 6, 32 * 2


def test_one_frame_is_followed_by_the_same_frame_at_game_size(loaded):
    image = sprite_image(loaded, "goblin", scale=6, display=True)
    assert image.size == (2 * MARGIN + ENLARGED + GAP + GAME, 2 * MARGIN + ENLARGED)


def test_game_size_frames_follow_all_the_enlarged_ones(loaded):
    image = sprite_image(loaded, "warrior", scale=6, display=True)
    width = 2 * MARGIN + 2 * ENLARGED + GAP + GAP + 2 * GAME + GAP
    # The height is set by the enlarged frames: the sprite's row and its variant's.
    assert image.size == (width, 2 * ENLARGED + GAP + 2 * MARGIN)
    plain = sprite_image(loaded, "warrior", scale=6)
    assert image.crop((0, 0, plain.width - MARGIN, plain.height)).tobytes() == (
        plain.crop((0, 0, plain.width - MARGIN, plain.height)).tobytes()
    )


def test_game_size_frames_are_top_aligned_with_each_art_pixel_a_block(loaded):
    image = sprite_image(loaded, "warrior", scale=6, display=True)
    left = MARGIN + 2 * (ENLARGED + GAP)
    # Row 14, column 10 of the warrior is `b`.
    assert image.crop((left + 10 * 2, MARGIN + 14 * 2, left + 11 * 2, MARGIN + 15 * 2)).getcolors() == [(4, BLUE)]
    # `idle_1` differs from `idle_0` in row 9: column 17 is `o` instead of `k`.
    x, y = left + 17 * 2, MARGIN + 9 * 2
    assert image.getpixel((x, y)) == OUTLINE
    assert image.getpixel((x + GAME + GAP, y)) == ORANGE
    # Both frames of the row are the ones a preview at the game's scale draws.
    game = sprite_image(loaded, "warrior", scale=2)
    row = (2 * GAME + GAP, GAME)
    assert image.crop((left, MARGIN, left + row[0], MARGIN + row[1])).tobytes() == (
        game.crop((MARGIN, MARGIN, MARGIN + row[0], MARGIN + row[1])).tobytes()
    )
    # Under them, as far as the bottom of the enlarged row, is background.
    under = image.crop((left, MARGIN + GAME, image.width, MARGIN + ENLARGED))
    assert under.getcolors() == [(under.width * under.height, BACKGROUND)]


def test_gap_between_the_enlarged_and_the_game_size_frames_is_background(loaded):
    image = sprite_image(loaded, "warrior", scale=6, display=True)
    left = MARGIN + 2 * ENLARGED + GAP
    gap = image.crop((left, 0, left + GAP, image.height))
    assert gap.getcolors() == [(GAP * image.height, BACKGROUND)]


def test_variant_rows_carry_their_own_game_size_frames(loaded):
    image = sprite_image(loaded, "warrior", scale=6, display=True)
    x, y = MARGIN + 2 * (ENLARGED + GAP) + 10 * 2, MARGIN + ENLARGED + GAP + 14 * 2
    assert image.getpixel((x, y)) == RED
    assert image.getpixel((x + GAME + GAP, y)) == RED


def test_game_size_frames_are_left_out_when_the_scales_are_equal(loaded):
    assert sprite_image(loaded, "warrior", scale=2, display=True).tobytes() == (
        sprite_image(loaded, "warrior", scale=2).tobytes()
    )


def test_game_size_frames_may_be_the_larger_ones(loaded):
    """A preview scale under `display_scale` still gets them; the taller group sets the height."""
    image = sprite_image(loaded, "goblin", scale=1, display=True)
    assert image.size == (2 * MARGIN + 32 + GAP + GAME, 2 * MARGIN + GAME)


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
# The demo's sprites on the `unit` canvas; a sprite with `build = false` is on the sheet too.
UNIT_IDS = ["goblin", "sample_slime", "slime", "warrior", "warrior_red"]


def art_at(project, sprite, factor: int, image: Image.Image, at: tuple[int, int]) -> bool:
    """Whether `image` shows the sprite's default frame at `at`, on the background."""
    size = (sprite.canvas.width * factor, sprite.canvas.height * factor)
    expected = composite(project, size, sprite, (0, 0), factor, sprite, (0, 0), factor)
    return image.crop((*at, at[0] + size[0], at[1] + size[1])).tobytes() == expected.tobytes()


def test_sheet_groups_by_canvas_class_and_sorts_by_id(loaded):
    project, sprites = loaded
    image = preview.contact_sheet(project, list(sprites.values())[::-1])
    # Units: five cells as wide as the label `sample_slime`. Tile: one as wide as `ground_light`.
    # Effects: cells as wide as the art, 16 pixels at 2x, under a shorter row; the orb's
    # three tints follow it.
    unit_w, tile_w, effect_w = 12 * CHAR_WIDTH, 12 * CHAR_WIDTH, 32
    effect_h = 32 + LABEL_GAP + LINE_HEIGHT
    assert image.size == (2 * MARGIN + 5 * unit_w + 4 * GAP, 2 * MARGIN + 2 * CELL_H + effect_h + 2 * GAP)
    for column, sprite_id in enumerate(UNIT_IDS):
        at = (MARGIN + column * (unit_w + GAP) + (unit_w - 64) // 2, MARGIN)
        assert art_at(project, sprites[sprite_id], 2, image, at), sprite_id
    at = (MARGIN + (tile_w - 64) // 2, MARGIN + CELL_H + GAP)
    assert art_at(project, sprites["ground_light"], 4, image, at)
    for column, sprite_id in [(0, "arrow"), (1, "orb"), (5, "spark")]:
        at = (MARGIN + column * (effect_w + GAP), MARGIN + 2 * (CELL_H + GAP))
        assert art_at(project, sprites[sprite_id], 2, image, at), sprite_id


def test_sheet_draws_each_id_under_its_sprite(loaded):
    from PIL import ImageDraw, ImageFont

    project, sprites = loaded
    image = preview.contact_sheet(project, sprites.values())
    unit_w = 12 * CHAR_WIDTH
    for column, sprite_id in enumerate(UNIT_IDS):
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


# The command


def run(*argv: str) -> int:
    return main(["preview", *argv])


def previews(root: Path) -> list[str]:
    directory = root / ".preview"
    return sorted(path.name for path in directory.iterdir()) if directory.exists() else []


def break_sprite(root: Path, name: str) -> None:
    """Give the sprite an unknown palette key in its first row (E104)."""
    path = next(root.rglob(name + ".sprite.toml"))
    text = path.read_text(encoding="utf-8")
    start = text.index('"""\n') + 4
    path.write_text(text[:start] + "?" + text[start + 1 :], encoding="utf-8")


def test_a9_preview_writes_one_png_and_prints_only_its_path(demo, capsys):
    assert run("goblin") == 0
    captured = capsys.readouterr()
    assert (captured.out, captured.err) == (".preview/goblin.plain.png\n", "")
    assert previews(demo) == ["goblin.plain.png"]
    with Image.open(demo / ".preview" / "goblin.plain.png") as image:
        # The demo's configured scale is 6, and the frame follows at game size.
        assert image.size == (2 * MARGIN + ENLARGED + GAP + GAME, 2 * MARGIN + ENLARGED)


def test_preview_of_a_sprite_shows_its_frames_and_variants(demo, loaded):
    assert run("warrior") == 0
    with Image.open(demo / ".preview" / "warrior.plain.png") as image:
        assert image.convert("RGBA").tobytes() == sprite_image(loaded, "warrior", scale=6, display=True).tobytes()


def test_a27_preview_is_the_enlarged_frames_then_the_same_frames_at_game_size(demo):
    assert run("warrior") == 0
    with Image.open(demo / ".preview" / "warrior.plain.png") as image:
        enlarged, game = 2 * ENLARGED + GAP, 2 * GAME + GAP
        assert image.width == 2 * MARGIN + enlarged + GAP + game


def test_a27_scale_display_draws_only_the_game_size_frames(demo, loaded, capsys):
    assert run("warrior", "--scale", "display") == 0
    assert capsys.readouterr().out == ".preview/warrior.plain.png\n"
    with Image.open(demo / ".preview" / "warrior.plain.png") as image:
        assert image.width == 2 * MARGIN + 2 * GAME + GAP
        assert image.convert("RGBA").tobytes() == sprite_image(loaded, "warrior", scale=2).tobytes()


def test_scale_display_draws_each_sprite_at_its_own_class_scale(demo, loaded):
    """The unit class is drawn at 2 and the tile class at 4."""
    assert run("warrior", "ground_light", "--scale", "display") == 0
    project, _ = loaded
    parts = [sprite_image(loaded, "warrior", scale=2), sprite_image(loaded, "ground_light", scale=4)]
    assert parts[1].size == (16 * 4 + 2 * MARGIN, 16 * 4 + 2 * MARGIN)
    with Image.open(demo / ".preview" / "warrior+ground_light.plain.png") as image:
        assert image.convert("RGBA").tobytes() == preview.stack(project, parts).tobytes()


def test_preview_of_a_variant_shows_only_the_variant(demo, loaded):
    assert run("warrior_red") == 0
    with Image.open(demo / ".preview" / "warrior_red.plain.png") as image:
        assert image.size == (2 * MARGIN + 2 * ENLARGED + GAP + GAP + 2 * GAME + GAP, ENLARGED + 2 * MARGIN)


def test_scale_flag_overrides_the_configured_scale(demo):
    assert run("goblin", "--scale", "3") == 0
    with Image.open(demo / ".preview" / "goblin.plain.png") as image:
        assert image.size == (2 * MARGIN + 32 * 3 + GAP + GAME, 32 * 3 + 2 * MARGIN)


def test_scale_equal_to_the_display_scale_draws_the_frames_once(demo):
    assert run("goblin", "--scale", "2") == 0
    with Image.open(demo / ".preview" / "goblin.plain.png") as image:
        assert image.size == (GAME + 2 * MARGIN, GAME + 2 * MARGIN)


def test_grid_flag_draws_the_grid(demo, loaded, capsys):
    assert run("goblin", "--grid") == 0
    assert capsys.readouterr().out == ".preview/goblin.grid.png\n"
    with Image.open(demo / ".preview" / "goblin.grid.png") as image:
        assert image.convert("RGBA").tobytes() == sprite_image(loaded, "goblin", scale=6, grid=True).tobytes()


def test_grid_with_a_scale_has_no_game_size_frames(demo, loaded):
    assert run("goblin", "--grid", "--scale", "3") == 0
    with Image.open(demo / ".preview" / "goblin.grid.png") as image:
        assert image.convert("RGBA").tobytes() == sprite_image(loaded, "goblin", scale=3, grid=True).tobytes()


@pytest.mark.parametrize("more", [[], ["--on", "ground_light"]], ids=["alone", "with --on"])
def test_scale_display_with_grid_is_a_usage_error(demo, capsys, more):
    assert run("goblin", "--scale", "display", "--grid", *more) == 2
    captured = capsys.readouterr()
    assert (captured.out, captured.err) == ("", "error: --scale display cannot be used with --grid\n")
    assert previews(demo) == []


def test_each_kind_of_preview_has_its_own_file(demo):
    assert run("goblin") == 0
    assert run("goblin", "--grid") == 0
    assert run("goblin", "--on", "ground_light") == 0
    assert previews(demo) == ["goblin.grid.png", "goblin.on-ground_light.png", "goblin.plain.png"]


def test_several_ids_are_one_image_in_the_order_given(demo, capsys, loaded):
    assert run("warrior", "goblin", "warrior") == 0
    assert capsys.readouterr().out == ".preview/warrior+goblin.plain.png\n"
    assert previews(demo) == ["warrior+goblin.plain.png"]
    warrior = sprite_image(loaded, "warrior", scale=6, display=True)
    goblin = sprite_image(loaded, "goblin", scale=6, display=True)
    with Image.open(demo / ".preview" / "warrior+goblin.plain.png") as image:
        image = image.convert("RGBA")
        assert image.size == (warrior.width, warrior.height + goblin.height)
        assert image.crop((0, 0, *warrior.size)).tobytes() == warrior.tobytes()
        below = image.crop((0, warrior.height, goblin.width, warrior.height + goblin.height))
        assert below.tobytes() == goblin.tobytes()
        # The goblin has fewer frames; the space beside it is background.
        assert image.getpixel((image.width - 1, image.height - 1)) == BACKGROUND


def test_very_many_ids_get_a_short_file_name(demo, capsys):
    ids = ["goblin", "warrior", "warrior_red", "ground_light"]
    sources = {name: next(demo.rglob(name.removesuffix("_red") + ".sprite.toml")) for name in ids}
    extra = []
    for index in range(12):
        name = f"goblin_copy_number_{index:02}"
        (demo / f"{name}.sprite.toml").write_bytes(sources["goblin"].read_bytes())
        extra.append(name)
    assert run(*extra) == 0
    assert capsys.readouterr().out == ".preview/goblin_copy_number_00+11more.plain.png\n"


def test_a15_on_writes_the_unit_on_the_tile(demo, capsys, loaded):
    assert run("warrior", "--on", "ground_light") == 0
    assert capsys.readouterr().out == ".preview/warrior.on-ground_light.png\n"
    assert previews(demo) == ["warrior.on-ground_light.png"]
    project, sprites = loaded
    with Image.open(demo / ".preview" / "warrior.on-ground_light.png") as image:
        # Tile 16 * 4 * 2 square and unit 32 * 2 * 2 square: the default common factor is 2.
        assert image.size == (128 + 2 * MARGIN, 128 + 2 * MARGIN)
        expected = preview.on_tile(project, sprites["warrior"], sprites["ground_light"], scale=2)
        assert image.convert("RGBA").tobytes() == expected.tobytes()


def test_on_takes_scale_as_the_common_factor_and_ignores_grid(demo):
    assert run("warrior", "--on", "ground_light", "--scale", "1", "--grid") == 0
    with Image.open(demo / ".preview" / "warrior.on-ground_light.png") as image:
        assert image.size == (64 + 2 * MARGIN, 64 + 2 * MARGIN)


def test_on_with_scale_display_is_the_pair_as_the_game_draws_them(demo, loaded):
    assert run("warrior", "--on", "ground_light", "--scale", "display") == 0
    project, sprites = loaded
    with Image.open(demo / ".preview" / "warrior.on-ground_light.png") as image:
        expected = preview.on_tile(project, sprites["warrior"], sprites["ground_light"], scale=1)
        assert image.convert("RGBA").tobytes() == expected.tobytes()


def test_the_contact_sheet_ignores_scale(demo, loaded):
    assert run("--scale", "display") == 0
    project, sprites = loaded
    with Image.open(demo / ".preview" / "sheet.png") as image:
        assert image.convert("RGBA").tobytes() == preview.contact_sheet(project, sprites.values()).tobytes()


def test_no_ids_writes_the_contact_sheet(demo, capsys, loaded):
    assert run() == 0
    assert capsys.readouterr().out == ".preview/sheet.png\n"
    assert previews(demo) == ["sheet.png"]
    project, sprites = loaded
    with Image.open(demo / ".preview" / "sheet.png") as image:
        assert image.convert("RGBA").tobytes() == preview.contact_sheet(project, sprites.values()).tobytes()


def test_sheet_with_an_id_writes_both(demo, capsys):
    assert run("goblin", "--sheet") == 0
    assert capsys.readouterr().out == ".preview/goblin.plain.png\n.preview/sheet.png\n"
    assert previews(demo) == ["goblin.plain.png", "sheet.png"]


def test_paths_are_absolute_from_outside_the_project(demo, capsys, tmp_path, monkeypatch):
    (tmp_path / "elsewhere").mkdir()
    monkeypatch.chdir(tmp_path / "elsewhere")
    assert run("goblin", "--project", str(demo)) == 0
    assert capsys.readouterr().out == f"{demo / '.preview' / 'goblin.plain.png'}\n"


def test_paths_are_relative_to_a_subdirectory_of_the_project(demo, capsys, monkeypatch):
    monkeypatch.chdir(demo / "units")
    assert run("goblin") == 0
    assert capsys.readouterr().out == "../.preview/goblin.plain.png\n"


def test_project_is_found_from_the_directory_above_it(demo, capsys, monkeypatch):
    monkeypatch.chdir(demo.parent)
    assert run("goblin") == 0
    assert capsys.readouterr().out == f"{demo.name}/.preview/goblin.plain.png\n"


def test_warnings_are_not_printed(demo, capsys):
    """Output is paths only: a frame that no animation uses (W002) does not add a line."""
    with (demo / "units" / "warrior.sprite.toml").open("a", encoding="utf-8") as sprite:
        sprite.write('\n[frames.idle_2]\nfrom = "idle_0"\n')
    assert main(["check"]) == 0
    assert "W002" in capsys.readouterr().out
    assert run("warrior") == 0
    assert capsys.readouterr().out == ".preview/warrior.plain.png\n"


def test_a_sprite_with_an_error_prints_the_problems_and_writes_nothing(demo, capsys):
    break_sprite(demo, "goblin")
    assert run("goblin") == 1
    captured = capsys.readouterr()
    assert captured.out.splitlines() == [
        "units/goblin.sprite.toml:6:1: E104 unknown palette key '?'",
        "1 error, 0 warnings in 1 file",
    ]
    assert captured.err == ""
    assert previews(demo) == []


def break_outline(root: Path, name: str) -> None:
    """Replace the first outline pixel of the sprite with white (E201)."""
    path = next(root.rglob(name + ".sprite.toml"))
    text = path.read_text(encoding="utf-8")
    path.write_text(text.replace("k", "w", 1), encoding="utf-8")


def test_a_style_error_is_printed_and_the_preview_is_still_written(demo, capsys):
    """The sprite can be drawn, and looking at it is how the fault gets fixed."""
    break_outline(demo, "goblin")
    assert run("goblin", "--grid") == 0
    lines = capsys.readouterr().out.splitlines()
    assert len(lines) == 3
    assert "units/goblin.sprite.toml:" in lines[0] and "E201 frame 'main': 'w' touches transparency" in lines[0]
    assert lines[1:] == ["1 error, 0 warnings in 1 file", ".preview/goblin.grid.png"]
    assert previews(demo) == ["goblin.grid.png"]


def test_a_blank_sprite_can_be_previewed(demo, capsys):
    assert main(["new", "kobold", "--canvas", "unit"]) == 0
    capsys.readouterr()
    assert run("kobold") == 0
    assert capsys.readouterr().out == ".preview/kobold.plain.png\n"


def test_a_style_error_does_not_stop_the_contact_sheet(demo, capsys):
    break_outline(demo, "goblin")
    assert run() == 0
    assert capsys.readouterr().out.splitlines()[-1] == ".preview/sheet.png"
    assert previews(demo) == ["sheet.png"]


def test_an_error_in_one_requested_sprite_stops_the_others(demo, capsys):
    break_sprite(demo, "goblin")
    assert run("warrior", "goblin") == 1
    assert previews(demo) == []


def test_an_error_in_another_sprite_does_not_stop_the_preview(demo, capsys):
    break_sprite(demo, "goblin")
    assert run("warrior") == 0
    assert capsys.readouterr().out == ".preview/warrior.plain.png\n"


def test_an_error_in_the_tile_stops_an_on_preview(demo, capsys):
    break_sprite(demo, "ground_light")
    assert run("warrior", "--on", "ground_light") == 1
    assert "tiles/ground_light.sprite.toml" in capsys.readouterr().out
    assert previews(demo) == []


def test_an_error_anywhere_stops_the_contact_sheet(demo, capsys):
    break_sprite(demo, "goblin")
    assert run("warrior", "--sheet") == 1
    assert "E104" in capsys.readouterr().out
    assert previews(demo) == []


def test_a_bad_palette_prints_its_problems_and_writes_nothing(demo, capsys):
    palette = demo / "palette.toml"
    palette.write_text(palette.read_text(encoding="utf-8").replace("#1a1c2c", "black"), encoding="utf-8")
    assert run("goblin") == 1
    assert "palette.toml:3:1: E002" in capsys.readouterr().out
    assert previews(demo) == []


@pytest.mark.parametrize(
    "argv, name",
    [(["orc"], "orc"), (["goblin", "orc"], "orc"), (["goblin", "--on", "lava"], "lava"), (["--on", "lava"], "lava")],
)
def test_unknown_id_is_a_usage_error(demo, capsys, argv, name):
    assert run(*argv) == 2
    captured = capsys.readouterr()
    known = "(sprites: arrow, goblin, ground_light, orb, sample_slime, slime, spark, warrior, warrior_red)"
    assert (captured.out, captured.err) == ("", f"error: unknown sprite id '{name}' {known}\n")
    assert previews(demo) == []


def test_outside_a_project_is_a_usage_error(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    assert run("goblin") == 2
    assert capsys.readouterr().err.startswith("error: no sprite-tool.toml found")


def test_a_preview_directory_that_cannot_be_made_is_exit_2(demo, capsys):
    (demo / ".preview").write_text("in the way", encoding="utf-8")
    assert run("goblin") == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("error: cannot write preview: ")


# --- 0.6: --points --------------------------------------------------------------


def test_a66_drawn_marks_each_point_pixel_and_nothing_else(loaded):
    project, sprites = loaded
    warrior = sprites["warrior"]
    plain = preview.drawn(project, warrior, warrior.frames[0])
    marked = preview.drawn(project, warrior, warrior.frames[0], points=True)
    differ = [(x, y) for y in range(32) for x in range(32) if plain.getpixel((x, y)) != marked.getpixel((x, y))]
    assert differ == [(25, 18)]
    assert marked.getpixel((25, 18)) == preview.POINT_MARKER


def preview_file(argv: list[str], capsys) -> Image.Image:
    assert main(["preview", *argv]) == 0
    (path,) = capsys.readouterr().out.split()
    return Image.open(path).convert("RGBA")


def test_a66_preview_points_marks_the_point_in_every_frame_tile(demo, capsys):
    scale = 3
    plain = preview_file(["warrior", "--scale", str(scale)], capsys)
    marked = preview_file(["warrior", "--scale", str(scale), "--points"], capsys)
    assert plain.size == marked.size
    tile = 32 * scale + GAP
    # Both frames, in the warrior's row and its red variant's.
    for column in range(2):
        for row in range(2):
            x, y = MARGIN + column * tile + 25 * scale, MARGIN + row * tile + 18 * scale
            assert marked.getpixel((x, y)) == preview.POINT_MARKER
            assert plain.getpixel((x, y)) != preview.POINT_MARKER
    changed = {
        marked.getpixel((x, y))
        for y in range(marked.height)
        for x in range(marked.width)
        if marked.getpixel((x, y)) != plain.getpixel((x, y))
    }
    assert changed == {preview.POINT_MARKER}


def test_a66_without_points_the_preview_has_no_marker(demo, capsys):
    image = preview_file(["warrior", "arrow"], capsys)
    assert preview.POINT_MARKER not in set(image.get_flattened_data())


@pytest.mark.parametrize("flags", [["--grid"], ["--on", "ground_light"], ["--anim", "idle"]])
def test_points_combine_with_grid_on_and_anim(demo, capsys, flags):
    assert main(["preview", "warrior", "--points", *flags]) == 0
    first = capsys.readouterr().out.split()[0]
    assert preview.POINT_MARKER in set(Image.open(first).convert("RGBA").get_flattened_data())
