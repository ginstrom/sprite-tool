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
    assert (captured.out, captured.err) == (".preview/goblin.png\n", "")
    assert previews(demo) == ["goblin.png"]
    with Image.open(demo / ".preview" / "goblin.png") as image:
        # The demo's configured scale is 6.
        assert image.size == (32 * 6 + 2 * MARGIN, 32 * 6 + 2 * MARGIN)


def test_preview_of_a_sprite_shows_its_frames_and_variants(demo, loaded):
    assert run("warrior") == 0
    with Image.open(demo / ".preview" / "warrior.png") as image:
        assert image.convert("RGBA").tobytes() == sprite_image(loaded, "warrior", scale=6).tobytes()


def test_preview_of_a_variant_shows_only_the_variant(demo, loaded):
    assert run("warrior_red") == 0
    with Image.open(demo / ".preview" / "warrior_red.png") as image:
        assert image.size == (2 * 32 * 6 + GAP + 2 * MARGIN, 32 * 6 + 2 * MARGIN)


def test_scale_flag_overrides_the_configured_scale(demo):
    assert run("goblin", "--scale", "3") == 0
    with Image.open(demo / ".preview" / "goblin.png") as image:
        assert image.size == (32 * 3 + 2 * MARGIN, 32 * 3 + 2 * MARGIN)


def test_grid_flag_draws_the_grid(demo, loaded):
    assert run("goblin", "--grid") == 0
    with Image.open(demo / ".preview" / "goblin.png") as image:
        assert image.convert("RGBA").tobytes() == sprite_image(loaded, "goblin", scale=6, grid=True).tobytes()


def test_several_ids_write_one_file_each_in_the_order_given(demo, capsys):
    assert run("warrior", "goblin", "warrior") == 0
    assert capsys.readouterr().out == ".preview/warrior.png\n.preview/goblin.png\n"
    assert previews(demo) == ["goblin.png", "warrior.png"]


def test_a15_on_writes_the_unit_on_the_tile(demo, capsys, loaded):
    assert run("warrior", "--on", "ground_light") == 0
    assert capsys.readouterr().out == ".preview/warrior.png\n"
    assert previews(demo) == ["warrior.png"]
    project, sprites = loaded
    with Image.open(demo / ".preview" / "warrior.png") as image:
        # Tile 16 * 4 * 2 square and unit 32 * 2 * 2 square: the default common factor is 2.
        assert image.size == (128 + 2 * MARGIN, 128 + 2 * MARGIN)
        expected = preview.on_tile(project, sprites["warrior"], sprites["ground_light"], scale=2)
        assert image.convert("RGBA").tobytes() == expected.tobytes()


def test_on_takes_scale_as_the_common_factor_and_ignores_grid(demo):
    assert run("warrior", "--on", "ground_light", "--scale", "1", "--grid") == 0
    with Image.open(demo / ".preview" / "warrior.png") as image:
        assert image.size == (64 + 2 * MARGIN, 64 + 2 * MARGIN)


def test_no_ids_writes_the_contact_sheet(demo, capsys, loaded):
    assert run() == 0
    assert capsys.readouterr().out == ".preview/sheet.png\n"
    assert previews(demo) == ["sheet.png"]
    project, sprites = loaded
    with Image.open(demo / ".preview" / "sheet.png") as image:
        assert image.convert("RGBA").tobytes() == preview.contact_sheet(project, sprites.values()).tobytes()


def test_sheet_with_an_id_writes_both(demo, capsys):
    assert run("goblin", "--sheet") == 0
    assert capsys.readouterr().out == ".preview/goblin.png\n.preview/sheet.png\n"
    assert previews(demo) == ["goblin.png", "sheet.png"]


def test_paths_are_absolute_from_outside_the_project(demo, capsys, tmp_path, monkeypatch):
    (tmp_path / "elsewhere").mkdir()
    monkeypatch.chdir(tmp_path / "elsewhere")
    assert run("goblin", "--project", str(demo)) == 0
    assert capsys.readouterr().out == f"{demo / '.preview' / 'goblin.png'}\n"


def test_paths_are_relative_to_a_subdirectory_of_the_project(demo, capsys, monkeypatch):
    monkeypatch.chdir(demo / "units")
    assert run("goblin") == 0
    assert capsys.readouterr().out == "../.preview/goblin.png\n"


def test_warnings_are_not_printed(demo, capsys):
    """Output is paths only: a frame that no animation uses (W002) does not add a line."""
    with (demo / "units" / "warrior.sprite.toml").open("a", encoding="utf-8") as sprite:
        sprite.write('\n[frames.idle_2]\nfrom = "idle_0"\n')
    assert main(["check"]) == 0
    assert "W002" in capsys.readouterr().out
    assert run("warrior") == 0
    assert capsys.readouterr().out == ".preview/warrior.png\n"


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


def test_an_error_in_one_requested_sprite_stops_the_others(demo, capsys):
    break_sprite(demo, "goblin")
    assert run("warrior", "goblin") == 1
    assert previews(demo) == []


def test_an_error_in_another_sprite_does_not_stop_the_preview(demo, capsys):
    break_sprite(demo, "goblin")
    assert run("warrior") == 0
    assert capsys.readouterr().out == ".preview/warrior.png\n"


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
    assert (captured.out, captured.err) == ("", f"error: unknown sprite id '{name}'\n")
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
