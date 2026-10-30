"""Tints: the formula, `--tint` and `--tint-mode`, declared `tints`, their
exports, and W010."""

import json
import shutil
from dataclasses import replace
from fractions import Fraction
from pathlib import Path

import pytest
from PIL import Image, ImageDraw, ImageFont

from conftest import make_frame, make_sprite
from sprite_tool import check, guide, preview, render, spritefile
from sprite_tool import project as project_module
from sprite_tool.cli import main
from sprite_tool.export.index import sprite_entry
from sprite_tool.model import Tint, format_problem
from sprite_tool.preview import CHAR_WIDTH, GAP, LABEL_GAP, LINE_HEIGHT, MARGIN, POINT_MARKER

DEMO = Path(__file__).parent.parent / "examples" / "demo"

BACKGROUND = (0x3A, 0x3A, 0x3A, 255)
WHITE_KEY = (0xF4, 0xF4, 0xF4, 255)  # the demo's `w`
FIRE = (0xFF, 0x7A, 0x1A, 255)
# Where a panel's image starts, under its label line.
TOP = MARGIN + LINE_HEIGHT + LABEL_GAP
SCALE = 6  # the demo's [preview] scale


def multiply(pixel, tint):
    return tuple((p * t + 127) // 255 for p, t in zip(pixel, tint))


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


def run_preview(capsys, *argv: str) -> list[str]:
    assert main(["preview", *argv]) == 0
    return capsys.readouterr().out.split()


def open_rgba(path: str) -> Image.Image:
    with Image.open(path) as image:
        return image.convert("RGBA")


def orb_preview(loaded, tint: Tint | None = None) -> Image.Image:
    project, sprites = loaded
    return preview.sprite_preview(project, sprites["orb"], [], SCALE, display=True, tint=tint)


def panel(image: Image.Image, index: int, width: int, height: int) -> Image.Image:
    return image.crop((index * width, TOP, (index + 1) * width, TOP + height))


def label_at(image: Image.Image, x: int, y: int, text: str) -> bool:
    expected = Image.new("RGBA", (len(text) * CHAR_WIDTH, LINE_HEIGHT), BACKGROUND)
    ImageDraw.Draw(expected).text((0, 0), text, font=ImageFont.load_default_imagefont(), fill=(255, 255, 255, 255))
    found = image.crop((x, y, x + expected.width, y + LINE_HEIGHT))
    return found.tobytes() == expected.tobytes()


def panel_labelled(image: Image.Image, index: int, width: int, text: str) -> bool:
    return label_at(image, index * width + MARGIN, MARGIN, text)


# --- the formula --------------------------------------------------------------


def one_pixel(rgba) -> Image.Image:
    return Image.new("RGBA", (1, 1), rgba)


def test_a78_multiply_rounds_each_channel():
    assert preview.tinted(one_pixel(WHITE_KEY), Tint(FIRE)).getpixel((0, 0)) == (244, 117, 25, 255)


def test_a79_multiply_takes_alpha_too_and_white_is_the_identity():
    half = Tint((255, 255, 255, 0x80))
    assert preview.tinted(one_pixel(WHITE_KEY), half).getpixel((0, 0)) == (244, 244, 244, 128)
    for rgba in [WHITE_KEY, (1, 2, 3, 4), (0, 0, 0, 0), (255, 128, 7, 200)]:
        assert preview.tinted(one_pixel(rgba), Tint((255, 255, 255, 255))).getpixel((0, 0)) == rgba


def test_a_transparent_pixel_stays_transparent_in_either_mode():
    for mode in ("multiply", "fill"):
        assert preview.tinted(one_pixel((9, 9, 9, 0)), Tint(FIRE, mode)).getpixel((0, 0))[3] == 0


def test_a81_fill_takes_the_tints_colour_and_multiplies_alpha():
    assert preview.tinted(one_pixel((10, 20, 30, 255)), Tint((255, 255, 255, 255), "fill")).getpixel((0, 0)) == (
        255, 255, 255, 255
    )
    assert preview.tinted(one_pixel((10, 20, 30, 128)), Tint((1, 2, 3, 128), "fill")).getpixel((0, 0)) == (1, 2, 3, 64)


def test_no_tint_is_the_image_itself():
    image = one_pixel((1, 2, 3, 4))
    assert preview.tinted(image, None) is image


def test_the_table_is_round_of_pixel_times_tint_over_255_for_every_pair():
    values = Image.new("RGBA", (256, 1))
    values.putdata([(p, p, p, p) for p in range(256)])
    for t in range(256):
        out = preview.tinted(values, Tint((t, t, t, t))).get_flattened_data()
        assert [pixel[0] for pixel in out] == [round(Fraction(p * t, 255)) for p in range(256)], t
        assert all(len(set(pixel)) == 1 for pixel in out)


# --- colours ----------------------------------------------------------------


def test_resolve_colour_reads_hex_in_either_case_and_palette_keys(loaded):
    palette = loaded[0].palette
    assert project_module.resolve_colour("#ff7a1a", palette) == FIRE
    assert project_module.resolve_colour("#FF7A1A", palette) == FIRE
    assert project_module.resolve_colour("#ff7a1a80", palette) == (0xFF, 0x7A, 0x1A, 0x80)
    assert project_module.resolve_colour("C", palette) == (0x73, 0xEF, 0xF7, 255)


@pytest.mark.parametrize("text", ["?", "none", "#ff7a1", "zz", "", "#ff7a1a8"])
def test_resolve_colour_is_none_for_anything_else(loaded, text):
    assert project_module.resolve_colour(text, loaded[0].palette) is None


# --- --tint -----------------------------------------------------------------


def test_a78_one_tint_writes_one_labelled_panel_and_tints_every_drawn_pixel(demo, loaded, capsys):
    assert run_preview(capsys, "orb", "--tint", "#ff7a1a") == [".preview/orb.plain.tint-ff7a1a.png"]
    image = open_rgba(".preview/orb.plain.tint-ff7a1a.png")
    plain = orb_preview(loaded)
    assert image.size == (plain.width, TOP + plain.height)
    assert panel_labelled(image, 0, plain.width, "#ff7a1a")
    tinted = panel(image, 0, plain.width, plain.height)
    whites = 0
    for y in range(plain.height):
        for x in range(plain.width):
            before, after = plain.getpixel((x, y)), tinted.getpixel((x, y))
            if before == WHITE_KEY:
                whites += 1
                assert after == (244, 117, 25, 255)
            elif before == BACKGROUND:
                assert after == BACKGROUND
    assert whites
    # The w at row 7, column 7 of the first frame.
    assert image.getpixel((MARGIN + 7 * SCALE + 3, TOP + MARGIN + 7 * SCALE + 3)) == (244, 117, 25, 255)


def test_a79_white_is_the_untinted_drawing_and_alpha_halves(demo, loaded, capsys):
    (path,) = run_preview(capsys, "orb", "--tint", "#ffffff")
    plain = orb_preview(loaded)
    assert panel(open_rgba(path), 0, plain.width, plain.height).tobytes() == plain.tobytes()
    project, sprites = loaded
    art = preview.drawn(project, sprites["orb"], sprites["orb"].frames[0], tint=Tint((255, 255, 255, 0x80)))
    plain_art = render.render(sprites["orb"].frames[0], project.palette)
    for before, after in zip(plain_art.get_flattened_data(), art.get_flattened_data()):
        assert after == (before[:3] + (128,) if before[3] == 255 else before)


def test_a80_several_tints_are_panels_in_the_order_given(demo, loaded, capsys):
    assert run_preview(capsys, "orb", "--tint", "#ff7a1a, C,none") == [".preview/orb.plain.tints.png"]
    image = open_rgba(".preview/orb.plain.tints.png")
    plain = orb_preview(loaded)
    width = plain.width
    assert image.size == (3 * width, TOP + plain.height)
    for index, label in enumerate(["#ff7a1a", "C #73eff7", "none"]):
        assert panel_labelled(image, index, width, label), label
    (cyan,) = run_preview(capsys, "orb", "--tint", "#73eff7")
    assert cyan == ".preview/orb.plain.tint-73eff7.png"
    assert panel(image, 1, width, plain.height).tobytes() == panel(open_rgba(cyan), 0, width, plain.height).tobytes()
    assert panel(image, 2, width, plain.height).tobytes() == plain.tobytes()


def test_a_palette_key_writes_the_same_file_as_its_colour(demo, capsys):
    assert run_preview(capsys, "orb", "--tint", "C") == [".preview/orb.plain.tint-73eff7.png"]


def test_a_repeated_tint_is_drawn_once(demo, loaded, capsys):
    (path,) = run_preview(capsys, "orb", "--tint", "#ff7a1a,#ff7a1a")
    assert path == ".preview/orb.plain.tint-ff7a1a.png"
    assert open_rgba(path).width == orb_preview(loaded).width


def test_none_alone_and_a_translucent_tint_name_their_files(demo, capsys):
    assert run_preview(capsys, "orb", "--tint", "none") == [".preview/orb.plain.tint-none.png"]
    assert run_preview(capsys, "orb", "--tint", "#ff7a1a80") == [".preview/orb.plain.tint-ff7a1a80.png"]


def test_a81_fill_draws_every_drawn_pixel_in_the_colour(demo, loaded, capsys):
    assert run_preview(capsys, "orb", "--tint", "#ffffff", "--tint-mode", "fill") == [
        ".preview/orb.plain.tint-ffffff-fill.png"
    ]
    image = open_rgba(".preview/orb.plain.tint-ffffff-fill.png")
    plain = orb_preview(loaded)
    assert panel_labelled(image, 0, plain.width, "#ffffff fill")
    filled = panel(image, 0, plain.width, plain.height)
    for before, after in zip(plain.get_flattened_data(), filled.get_flattened_data()):
        assert after == (BACKGROUND if before == BACKGROUND else (255, 255, 255, 255))


def test_several_ids_are_stacked_each_in_its_own_panels(demo, loaded, capsys):
    project, sprites = loaded
    (path,) = run_preview(capsys, "orb", "arrow", "--tint", "#ff7a1a,none")
    assert path == ".preview/orb+arrow.plain.tints.png"
    image = open_rgba(path)
    orb_w = orb_preview(loaded).width
    arrow = preview.sprite_preview(project, sprites["arrow"], [], SCALE, display=True)
    assert image.size == (2 * orb_w, 2 * TOP + orb_preview(loaded).height + arrow.height)
    second = TOP + orb_preview(loaded).height
    assert label_at(image, arrow.width + MARGIN, second + MARGIN, "none")


# --- what is not tinted (A82) ---------------------------------------------------


def blank(sprite):
    return replace(sprite, frames=tuple(replace(frame, rows=("." * 16,) * 16) for frame in sprite.frames))


def test_a82_on_tints_the_sprite_and_never_the_tile(demo, loaded, capsys):
    project, sprites = loaded
    orb, tile = sprites["orb"], sprites["ground_light"]
    plain = preview.on_tile(project, orb, tile, preview.ON_TILE_SCALE)
    tinted = preview.on_tile(project, orb, tile, preview.ON_TILE_SCALE, tint=Tint(FIRE))
    tile_only = preview.on_tile(project, blank(orb), tile, preview.ON_TILE_SCALE)
    figure = {
        (x, y) for y in range(plain.height) for x in range(plain.width) if plain.getpixel((x, y)) != tile_only.getpixel((x, y))
    }
    changed = {
        (x, y) for y in range(plain.height) for x in range(plain.width) if plain.getpixel((x, y)) != tinted.getpixel((x, y))
    }
    assert changed and changed <= figure

    (path,) = run_preview(capsys, "orb", "--on", "ground_light", "--tint", "#ff7a1a")
    assert path == ".preview/orb.on-ground_light.tint-ff7a1a.png"
    assert panel(open_rgba(path), 0, tinted.width, tinted.height).tobytes() == tinted.tobytes()


def test_a82_grid_lines_are_not_tinted(loaded):
    project, sprites = loaded
    orb = sprites["orb"]
    plain = preview.sprite_preview(project, orb, [], SCALE, grid=True)
    tinted = preview.sprite_preview(project, orb, [], SCALE, grid=True, tint=Tint(FIRE))
    no_art = preview.sprite_preview(project, blank(orb), [], SCALE, grid=True)
    for y in range(plain.height):
        for x in range(plain.width):
            if plain.getpixel((x, y)) == no_art.getpixel((x, y)):
                assert tinted.getpixel((x, y)) == plain.getpixel((x, y))


def test_a82_the_points_marker_is_not_tinted(loaded):
    project, sprites = loaded
    arrow = sprites["arrow"]
    art = preview.drawn(project, arrow, arrow.frames[0], points=True, tint=Tint(FIRE))
    assert art.getpixel((14, 8)) == POINT_MARKER


def test_a82_a_layers_base_is_not_tinted(loaded):
    project, _ = loaded
    body = make_sprite("body", make_frame("main", "ww", "ww"))
    hat = replace(make_sprite("hat", make_frame("main", "w.", "..")), over="body")
    art = preview.drawn(project, hat, hat.frames[0], base=body, tint=Tint(FIRE))
    assert art.getpixel((0, 0)) == (244, 117, 25, 255)
    assert art.getpixel((1, 1)) == WHITE_KEY


def test_variant_rows_are_tinted_like_the_sprites_own(loaded):
    project, sprites = loaded
    warrior = sprites["warrior"]
    variants = [sprites["warrior_red"]]
    plain = preview.sprite_preview(project, warrior, variants, 3)
    tinted = preview.sprite_preview(project, warrior, variants, 3, tint=Tint(FIRE))
    # The second row: the red variant. Row 14, column 10 is `b` in the warrior, `r` in the variant.
    x, y = MARGIN + 10 * 3 + 1, MARGIN + 32 * 3 + GAP + 14 * 3 + 1
    assert tinted.getpixel((x, y)) == multiply(plain.getpixel((x, y)), FIRE)


# --- --anim (A83) -------------------------------------------------------------


def test_a83_anim_with_tints_is_a_strip_of_panels_and_one_gif_playing_them_in_step(demo, loaded, capsys):
    project, sprites = loaded
    orb, pulse = sprites["orb"], sprites["orb"].anims[0]
    green = (0x7E, 0xE0, 0x7E, 255)
    assert run_preview(capsys, "orb", "--anim", "pulse", "--tint", "#ff7a1a,#7ee07e") == [
        ".preview/orb.anim-pulse.tints.png",
        ".preview/orb.anim-pulse.tints.gif",
    ]
    strip = open_rgba(".preview/orb.anim-pulse.tints.png")
    for index, colour in enumerate([FIRE, green]):
        expected = preview.anim_strip(project, orb, pulse, None, SCALE, tint=Tint(colour))
        assert panel(strip, index, expected.width, expected.height).tobytes() == expected.tobytes()

    tile = 16 * SCALE
    width = tile + 2 * MARGIN
    with Image.open(".preview/orb.anim-pulse.tints.gif") as gif:
        assert gif.n_frames == 2
        for frame in range(2):
            gif.seek(frame)
            assert gif.info["duration"] == 100
            image = gif.convert("RGBA")
            assert image.size == (2 * width, TOP + tile + 2 * MARGIN)
            for index, (colour, label) in enumerate([(FIRE, "#ff7a1a"), (green, "#7ee07e")]):
                assert panel_labelled(image, index, width, label)
                # Row 7, column 7 is `w` in both frames.
                at = (index * width + MARGIN + 7 * SCALE + 3, TOP + MARGIN + 7 * SCALE + 3)
                assert image.getpixel(at) == multiply(WHITE_KEY, colour)


def test_anim_with_declared_tints_names_the_gif_as_before(demo, capsys):
    assert run_preview(capsys, "orb", "--anim", "pulse") == [
        ".preview/orb.anim-pulse.png",
        ".preview/orb.anim-pulse.gif",
    ]
    with Image.open(".preview/orb.anim-pulse.gif") as gif:
        # none, fire, flash fill and frost side by side.
        assert gif.width == 4 * (16 * SCALE + 2 * MARGIN)


# --- usage errors (A84) -------------------------------------------------------------


@pytest.mark.parametrize("text", ["#ff7a1", "zz", "?"])
def test_a84_a_bad_tint_exits_2_and_writes_nothing(demo, capsys, text):
    assert main(["preview", "orb", "--tint", text]) == 2
    captured = capsys.readouterr()
    assert captured.err == f"error: bad tint '{text}': expected #rrggbb, #rrggbbaa, a palette key or none\n"
    assert captured.out == ""
    assert not (demo / ".preview").exists()


def test_a84_a_bad_tint_among_good_ones_is_named(demo, capsys):
    assert main(["preview", "orb", "--tint", "#ff7a1a,zz"]) == 2
    assert "bad tint 'zz'" in capsys.readouterr().err


@pytest.mark.parametrize(
    "argv, message",
    [
        (["--tint", "#ff7a1a"], "--tint needs a sprite id"),
        (["--sheet", "--tint", "#ff7a1a"], "--tint needs a sprite id"),
        (["orb", "--tint-mode", "fill"], "--tint-mode needs --tint"),
    ],
)
def test_a84_tint_flags_without_what_they_need_exit_2(demo, capsys, argv, message):
    assert main(["preview", *argv]) == 2
    assert capsys.readouterr().err == f"error: {message}\n"
    assert not (demo / ".preview").exists()


# --- declared tints (A85, A88) ------------------------------------------------


ZAP = '''\
canvas = "effect"
{tints}

[frames.main.runs]
7 = [[6, "{keys}"]]

[variants.dim]
swap = {{ w = "l" }}
'''


def load_zap(root: Path, tints: str, keys: str = "wwll"):
    (root / "effects" / "zap.sprite.toml").write_text(ZAP.format(tints=tints, keys=keys), encoding="utf-8")
    project, problems = project_module.load(root)
    assert not problems
    sprites, problems = spritefile.load_all(project)
    found = {sprite.id: sprite for sprite in sprites}
    return project, found, [problem for problem in problems if problem.path.name == "zap.sprite.toml"]


def test_a85_declared_tints_load_in_name_order_and_the_variant_has_them(demo):
    _, sprites, problems = load_zap(
        demo, 'tints = { fire = "#ff7a1a", frost = "C", flash = { colour = "#ffffff", mode = "fill" } }'
    )
    assert problems == []
    assert sprites["zap"].tints == (
        ("fire", Tint(FIRE, "multiply", "fire")),
        ("flash", Tint((255, 255, 255, 255), "fill", "flash")),
        ("frost", Tint((0x73, 0xEF, 0xF7, 255), "multiply", "frost")),
    )
    assert sprites["zap"].tints_line == 2
    assert sprites["zap_dim"].tints == sprites["zap"].tints


def test_tints_may_be_a_table_and_an_empty_one_is_none(demo):
    _, sprites, problems = load_zap(demo, '[tints]\nfire = "#ff7a1a"\nflash = { colour = "w", mode = "fill" }\n')
    assert problems == []
    assert [name for name, _ in sprites["zap"].tints] == ["fire", "flash"]
    assert sprites["zap"].tints_line == 2
    _, sprites, problems = load_zap(demo, "tints = {}")
    assert (problems, sprites["zap"].tints, sprites["zap"].tints_line) == ([], (), 0)


@pytest.mark.parametrize(
    "tints, message",
    [
        ('tints = "fire"', "tints must be a table of name = colour"),
        ('tints = { Fire = "#ff7a1a" }', "tints: bad tint name 'Fire': use a-z, 0-9 and _"),
        ('tints = { fire = "#ff7a1" }', "tints: tint 'fire' colour '#ff7a1' must be #rrggbb, #rrggbbaa or a palette key"),
        ('tints = { fire = "?" }', "tints: tint 'fire' colour '?' must be #rrggbb, #rrggbbaa or a palette key"),
        ("tints = { fire = 3 }", "tints: tint 'fire' must be a colour or a table { colour = ..., mode = ... }"),
        (
            'tints = { fire = { colour = "#ff7a1a", mode = "add" } }',
            "tints: tint 'fire' mode must be 'multiply' or 'fill'",
        ),
        ('tints = { fire = { mode = "fill" } }', "tints: tint 'fire' needs a colour"),
        (
            'tints = { fire = { colour = "#ff7a1a", alpha = 1 } }',
            "tints: tint 'fire' has unknown key 'alpha' (expected colour and mode)",
        ),
        ('tints = { fire = "none" }', "tints: tint 'fire' colour 'none' must be #rrggbb, #rrggbbaa or a palette key"),
    ],
)
def test_a88_a_bad_tint_is_one_e110_and_the_sprite_loads_without_it(demo, tints, message):
    _, sprites, problems = load_zap(demo, tints.replace("{ fire", '{ frost = "C", fire') if "{ fire" in tints else tints)
    assert [(problem.code, problem.line, problem.message) for problem in problems] == [("E110", 2, message)]
    names = [name for name, _ in sprites["zap"].tints]
    assert "fire" not in names and "Fire" not in names
    if "{ fire" in tints:
        assert names == ["frost"]


def test_e110_stops_the_build(demo, capsys):
    load_zap(demo, 'tints = { fire = "zz" }')
    assert main(["build"]) == 1
    assert "E110" in capsys.readouterr().out


# --- W010 (A89) ---------------------------------------------------------------


def w010(root: Path, tints: str, keys: str):
    project, sprites, problems = load_zap(root, tints, keys)
    assert problems == []
    return [
        format_problem(problem, root)
        for problem in check.run(project, list(sprites.values()))
        if problem.code == "W010"
    ]


def test_a89_a_multiply_tinted_sprite_in_strong_colours_warns_once_naming_them(demo):
    assert w010(demo, 'tints = { fire = "#ff7a1a" }', "yywwooll") == [
        "effects/zap.sprite.toml:2:1: W010 tinted sprite draws with coloured keys o, y (chroma over 64);"
        " multiplying muddies them: draw tinted art in greys"
    ]


def test_a89_only_fill_tints_or_no_tints_give_no_w010(demo):
    assert w010(demo, 'tints = { flash = { colour = "#ffffff", mode = "fill" } }', "yyww") == []
    assert w010(demo, "", "yyww") == []


def test_a89_greys_and_dark_keys_pass_the_chroma_limit(demo):
    assert w010(demo, 'tints = { fire = "#ff7a1a" }', "wldDkR") == []
    for key in "rogGtBbcCy":
        assert len(w010(demo, 'tints = { fire = "#ff7a1a" }', key)) == 1, key


def test_the_demo_has_no_w010(loaded):
    project, sprites = loaded
    assert [problem for problem in check.run(project, list(sprites.values())) if problem.code == "W010"] == []


# --- previewing declared tints (A86) -------------------------------------------


def test_a86_a_sprite_with_declared_tints_is_drawn_untinted_then_under_each(demo, loaded, capsys):
    project, sprites = loaded
    assert run_preview(capsys, "orb") == [".preview/orb.plain.png"]
    image = open_rgba(".preview/orb.plain.png")
    plain = orb_preview(loaded)
    width = plain.width
    assert image.size == (4 * width, TOP + plain.height)
    labels = ["none", "fire", "flash fill", "frost"]
    tints = [None, *(tint for _, tint in sprites["orb"].tints)]
    for index, (label, tint) in enumerate(zip(labels, tints)):
        assert panel_labelled(image, index, width, label), label
        assert panel(image, index, width, plain.height).tobytes() == orb_preview(loaded, tint).tobytes(), label


def test_a86_tint_replaces_the_declared_tints(demo, loaded, capsys):
    (path,) = run_preview(capsys, "orb", "--tint", "#ffffff")
    assert open_rgba(path).width == orb_preview(loaded).width


def test_a86_the_contact_sheet_adds_a_cell_per_declared_tint(loaded):
    project, sprites = loaded
    image = preview.contact_sheet(project, sprites.values())
    cell_w, cell_h = 32, 64 + LABEL_GAP + LINE_HEIGHT
    effects_y = MARGIN + 2 * (cell_h + GAP)
    for column, label in enumerate(["arrow", "orb", "fire", "flash", "frost", "spark"]):
        x = MARGIN + column * (cell_w + GAP)
        assert label_at(image, x + (cell_w - len(label) * CHAR_WIDTH) // 2, effects_y + 32 + LABEL_GAP, label), label
    # Row 7, column 7 of the orb's default frame is `w`: plain in the orb's cell, tinted after it.
    y = effects_y + 7 * 2 + 1
    for column, colour in [(1, WHITE_KEY), (2, (244, 117, 25, 255)), (3, (255, 255, 255, 255))]:
        assert image.getpixel((MARGIN + column * (cell_w + GAP) + 7 * 2 + 1, y)) == colour


# --- compatibility (A90) ----------------------------------------------------


def test_a90_a_sprite_without_tints_is_drawn_with_no_panel(demo, loaded, capsys):
    project, sprites = loaded
    (path,) = run_preview(capsys, "spark")
    expected = preview.sprite_preview(project, sprites["spark"], [], SCALE, display=True)
    assert open_rgba(path).tobytes() == expected.tobytes()
    paths = run_preview(capsys, "spark", "--anim", "burst")
    assert paths == [".preview/spark.anim-burst.png", ".preview/spark.anim-burst.gif"]
    expected = preview.anim_strip(project, sprites["spark"], sprites["spark"].anims[0], None, SCALE)
    assert open_rgba(paths[0]).tobytes() == expected.tobytes()


# --- exports (A87) ----------------------------------------------------------


def test_a87_the_demo_indexes_list_the_orbs_tints_and_no_other_sprites(loaded):
    _, sprites = loaded
    assert sprite_entry(sprites["orb"])["tints"] == {
        "fire": {"colour": "#ff7a1a", "mode": "multiply"},
        "flash": {"colour": "#ffffff", "mode": "fill"},
        "frost": {"colour": "#73eff7", "mode": "multiply"},
    }
    assert [sprite_id for sprite_id, sprite in sprites.items() if "tints" in sprite_entry(sprite)] == ["orb"]


def test_a87_the_built_indexes_carry_tints(demo, capsys):
    assert main(["build"]) == 0
    frames = json.loads((demo / "out" / "frames" / "sprites.json").read_text(encoding="utf-8"))
    godot = json.loads((demo / "out" / "godot" / "atlas.json").read_text(encoding="utf-8"))
    assert frames["orb"]["tints"] == godot["orb"]["tints"]
    assert list(frames["orb"]["tints"]) == ["fire", "flash", "frost"]
    assert "tints" not in frames["spark"] and "tints" not in godot["spark"]
    phaser = (demo / "out" / "phaser" / "atlas.json").read_text(encoding="utf-8")
    assert "tints" not in phaser


def test_a_translucent_tint_is_exported_with_its_alpha():
    sprite = replace(make_sprite("zap", make_frame("main", "w")), tints=(("ghost", Tint((1, 2, 3, 0x80))),))
    assert sprite_entry(sprite)["tints"] == {"ghost": {"colour": "#01020380", "mode": "multiply"}}


# --- guide (A92) ------------------------------------------------------------


def test_a92_the_guide_documents_tints(loaded):
    project, _ = loaded
    text = guide.guide_text(project)
    for phrase in ["--tint", "--tint-mode fill", "tints = {", "W010", "lighter"]:
        assert phrase in text, phrase
    assert len(text.splitlines()) < 130
