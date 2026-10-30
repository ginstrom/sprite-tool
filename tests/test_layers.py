"""Layers (`over`), `unoutlined`, and a layer's animation against its base's."""

from pathlib import Path

import pytest
from PIL import Image

from conftest import write_project
from sprite_tool import check, preview
from sprite_tool.cli import main
from sprite_tool.model import format_problem
from sprite_tool.preview import CHAR_WIDTH, GAP, GRID_MARGIN, MARGIN
from sprite_tool.project import load
from sprite_tool.spritefile import add_outline, load_all

CONFIG = """\
version = 1

[canvas.unit]
size = [5, 5]
anchor = [2, 5]
display_scale = 2
outline = ["k"]
grounded = true

[canvas.tile]
size = [5, 5]
anchor = [0, 0]

[preview]
scale = 4
background = "#3a3a3a"
"""

PALETTE = """\
[colors]
k = "#000000"
w = "#ffffff"
b = "#0000ff"
r = "#ff0000"
"""

BACKGROUND = (0x3A, 0x3A, 0x3A, 255)
BLACK, WHITE, RED = (0, 0, 0, 255), (255, 255, 255, 255), (255, 0, 0, 255)

# The body. In `idle_1` it is a pixel lower, so (0, 2) is drawn only in `idle_0`.
HERO = '''\
canvas = "unit"

[frames]
idle_0 = """
.kkk.
kwwwk
kwwwk
kwwwk
.kkk.
"""
idle_1 = """
.....
.kkk.
kwwwk
kwwwk
.kkk.
"""

[anim.idle]
frames = ["idle_0", "idle_1"]
ms = 500
'''

# A red pixel on the body's chest: it touches only pixels the body draws.
# `idle_0 = """` is on line 5, so row n is on line 6 + n.
HAT = '''\
canvas = "unit"
over = "hero"

[frames]
idle_0 = """
.....
..r..
.....
.....
.....
"""
'''


@pytest.fixture
def root(tmp_path, monkeypatch) -> Path:
    path = write_project(tmp_path / "sprites", CONFIG, PALETTE)
    monkeypatch.chdir(path)
    return path


def loaded(root: Path, files: dict[str, str]):
    """Write the sprite files and load them: the project, the sprites by id and every problem as a line.

    W009 is left out: these layers rest through the base's animations on
    purpose, and W009 has tests of its own (`test_rest.py`)."""
    for name, text in files.items():
        (root / name).write_text(text, encoding="utf-8")
    project, problems = load(root)
    sprites, more = load_all(project)
    problems += more + check.run(project, sprites)
    problems = [problem for problem in problems if problem.code != "W009"]
    return project, {sprite.id: sprite for sprite in sprites}, sorted(format_problem(problem, root) for problem in problems)


def problems(root: Path, hat: str, hero: str = HERO) -> list[str]:
    return loaded(root, {"hero.sprite.toml": hero, "hat.sprite.toml": hat})[2]


# --- A44, A45: the rules on a layer -------------------------------------------


def test_a44_a_layer_that_touches_only_its_base_passes_with_the_outline_rule_on(root):
    assert problems(root, HAT) == []


def test_a45_a_layer_need_not_stand_on_the_bottom_row(root):
    """`HAT` has an empty bottom row on a grounded class and no `grounded = false`."""
    _, sprites, found = loaded(root, {"hero.sprite.toml": HERO, "hat.sprite.toml": HAT})
    assert sprites["hat"].grounded
    assert found == []


def test_the_same_sprite_alone_fails_both_rules(root):
    assert problems(root, HAT.replace('over = "hero"\n', "\n")) == [
        "hat.sprite.toml:10:1: E202 frame 'idle_0': bottom row is empty, sprite must stand on it",
        "hat.sprite.toml:7:3: E201 frame 'idle_0': 'r' touches transparency, expected outline key 'k'",
    ]


def test_a44_a_pixel_where_the_base_is_transparent_is_one_e201_at_that_pixel(root):
    hat = HAT.replace(".....\n..r..", "r....\n.....")
    assert problems(root, hat) == [
        "hat.sprite.toml:6:1: E201 frame 'idle_0': 'r' touches transparency over 'hero', expected outline key 'k'"
    ]


def test_a_fault_in_a_runs_frame_has_its_row_and_column_in_the_message(root):
    hat = 'canvas = "unit"\nover = "hero"\n\n[frames.idle_0.runs]\n0 = [[0, "r"]]\n'
    assert problems(root, hat) == [
        "hat.sprite.toml:4:1: E201 frame 'idle_0' row 0, col 0: 'r' touches transparency over 'hero',"
        " expected outline key 'k'"
    ]


def test_an_outline_key_of_the_layer_may_touch_transparency(root):
    assert problems(root, HAT.replace(".....\n..r..", "k....\n..r..")) == []


def test_a_frame_is_paired_with_the_base_frame_of_the_same_name(root):
    """(1, 2) is inside the body in `idle_0`. In `idle_1` it is the top of the
    body, with nothing above it."""
    lower = '"""\n.....\n..r..\n.....\n.....\n.....\n"""\n'
    below = '"""\n.....\n.....\n..r..\n.....\n.....\n"""\n'
    assert problems(root, f'canvas = "unit"\nover = "hero"\n\n[frames]\nidle_0 = {lower}idle_1 = {below}') == []
    assert problems(root, f'canvas = "unit"\nover = "hero"\n\n[frames]\nidle_0 = {lower}idle_1 = {lower}') == [
        "hat.sprite.toml:14:3: E201 frame 'idle_1': 'r' touches transparency over 'hero', expected outline key 'k'"
    ]


def test_a_frame_with_no_namesake_is_paired_with_the_default_frame(root):
    lower = '"""\n.....\n..r..\n.....\n.....\n.....\n"""\n'
    assert problems(root, f'canvas = "unit"\nover = "hero"\n\n[frames]\nrest = {lower}') == []


def test_outline_false_still_switches_the_rule_off(root):
    hat = "outline = false\n" + HAT.replace(".....\n..r..", "r....\n.....")
    assert problems(root, hat) == []


def test_a_variant_of_a_layer_is_a_layer_over_the_same_base(root):
    project, sprites, found = loaded(
        root, {"hero.sprite.toml": HERO, "hat.sprite.toml": HAT + '\n[variants.blue]\nswap = { r = "b" }\n'}
    )
    assert found == []
    assert sprites["hat_blue"].over == "hero"
    assert check.bases(list(sprites.values())) == {"hat": sprites["hero"], "hat_blue": sprites["hero"]}


def test_a_variant_that_swaps_away_the_layers_outline_is_e201_over_the_base(root):
    hat = HAT.replace(".....\n..r..", "k....\n..r..") + '\n[variants.bare]\nswap = { k = "w" }\n'
    assert problems(root, hat) == [
        "hat.sprite.toml:6:1: E201 variant 'hat_bare' frame 'idle_0': 'w' touches transparency over 'hero',"
        " expected outline key 'k'"
    ]


def test_a_base_that_is_not_built_is_allowed(root):
    assert problems(root, HAT, "build = false\n" + HERO) == []


# --- A46: a bad `over` --------------------------------------------------------


def over_problems(root: Path, files: dict[str, str]) -> list[str]:
    return [line for line in loaded(root, files)[2] if " E108 " in line or " E001 " in line]


def test_a46_over_naming_an_unknown_sprite_is_e108(root):
    files = {"hero.sprite.toml": HERO, "hat.sprite.toml": HAT.replace('"hero"', '"hreo"')}
    assert over_problems(root, files) == ["hat.sprite.toml:2:1: E108 over names unknown sprite 'hreo'"]


def test_a46_over_naming_the_sprite_itself_is_e108(root):
    files = {"hat.sprite.toml": HAT.replace('"hero"', '"hat"')}
    assert over_problems(root, files) == ["hat.sprite.toml:2:1: E108 over names 'hat', the sprite itself"]


def test_a46_over_naming_a_layer_is_e108(root):
    files = {"hero.sprite.toml": HERO, "hat.sprite.toml": HAT, "plume.sprite.toml": HAT.replace('"hero"', '"hat"')}
    assert over_problems(root, files) == ["plume.sprite.toml:2:1: E108 over names 'hat', which is itself a layer"]


def test_a46_over_naming_a_sprite_of_another_class_is_e108(root):
    files = {"ground.sprite.toml": HERO.replace('"unit"', '"tile"'), "hat.sprite.toml": HAT.replace('"hero"', '"ground"')}
    assert over_problems(root, files) == [
        "hat.sprite.toml:2:1: E108 over names 'ground', which is on canvas class 'tile', not 'unit'"
    ]


def test_a46_over_with_auto_outline_is_e001(root):
    files = {"hero.sprite.toml": HERO, "hat.sprite.toml": 'outline = "auto"\n' + HAT}
    assert over_problems(root, files) == [
        "hat.sprite.toml:1:1: E001 outline = \"auto\" cannot be used with over; draw the layer's outline"
    ]


def test_over_that_is_not_a_string_is_e001(root):
    files = {"hero.sprite.toml": HERO, "hat.sprite.toml": HAT.replace('"hero"', "3")}
    assert over_problems(root, files) == ["hat.sprite.toml:2:1: E001 over must be a sprite id"]


def test_a_layer_with_a_bad_over_is_checked_as_a_plain_sprite_and_reported_once_with_variants(root):
    hat = HAT.replace('"hero"', '"hreo"') + '\n[variants.blue]\nswap = { r = "b" }\n'
    project, sprites, found = loaded(root, {"hero.sprite.toml": HERO, "hat.sprite.toml": hat})
    assert found == [
        "hat.sprite.toml:10:1: E202 frame 'idle_0': bottom row is empty, sprite must stand on it",
        "hat.sprite.toml:2:1: E108 over names unknown sprite 'hreo'",
        "hat.sprite.toml:7:3: E201 frame 'idle_0': 'r' touches transparency, expected outline key 'k'",
    ]
    assert check.bases(list(sprites.values())) == {}


# --- A54: a layer's animation out of step with its base's ---------------------

TWO_FRAMES = HAT + 'idle_1 = """\n.....\n.....\n..r..\n.....\n.....\n"""\n'


def test_a54_lengths_that_differ_are_w007_naming_both(root):
    hat = TWO_FRAMES + '\n[anim.idle]\nframes = ["idle_0", "idle_1"]\nms = 600\n'
    assert problems(root, hat) == [
        "hat.sprite.toml:20:1: W007 anim 'idle': 2 frames of 600, 600 ms, but 'hero' plays 2 of 500, 500 ms;"
        " the layers will drift"
    ]


def test_a_frame_count_that_differs_is_w007(root):
    hat = TWO_FRAMES + '\n[anim.idle]\nframes = ["idle_0", "idle_1", "idle_0"]\nms = 500\n'
    assert problems(root, hat) == [
        "hat.sprite.toml:20:1: W007 anim 'idle': 3 frames of 500, 500, 500 ms, but 'hero' plays 2 of 500, 500 ms;"
        " the layers will drift"
    ]


def test_animations_in_step_and_animations_only_one_has_are_not_reported(root):
    hat = TWO_FRAMES + '\n[anim.idle]\nframes = ["idle_1", "idle_0"]\nms = 500\n\n[anim.wave]\nframes = ["idle_0"]\nms = 90\n'
    assert problems(root, hat) == []


def test_a_like_animation_is_in_step_by_construction(root):
    assert problems(root, TWO_FRAMES + '\n[anim.idle]\nlike = "hero"\n') == []


def test_a_per_frame_length_is_what_is_compared(root):
    hat = TWO_FRAMES + '\n[anim.idle]\nframes = ["idle_0", { frame = "idle_1", ms = 400 }]\nms = 500\n'
    assert problems(root, hat) == [
        "hat.sprite.toml:20:1: W007 anim 'idle': 2 frames of 500, 400 ms, but 'hero' plays 2 of 500, 500 ms;"
        " the layers will drift"
    ]


# --- A47: previews of a layer -------------------------------------------------


def previewed(root: Path, hat: str = TWO_FRAMES):
    project, sprites, found = loaded(root, {"hero.sprite.toml": HERO, "hat.sprite.toml": hat})
    assert found == []
    return project, sprites


def test_a47_each_frame_of_a_layer_is_drawn_over_the_base_frame_of_the_same_name(root):
    project, sprites = previewed(root)
    image = preview.sprite_preview(project, sprites["hat"], [], 4, base=sprites["hero"])
    alone = preview.sprite_preview(project, sprites["hat"], [], 4)
    assert image.size == alone.size == (2 * MARGIN + 2 * 20 + GAP, 2 * MARGIN + 20)

    def at(frame: int, row: int, col: int) -> tuple[int, ...]:
        return image.getpixel((MARGIN + frame * (20 + GAP) + col * 4 + 1, MARGIN + row * 4 + 1))

    # (0, 2) is the body's outline in `idle_0` and nothing in `idle_1`.
    assert (at(0, 0, 2), at(1, 0, 2)) == (BLACK, BACKGROUND)
    # The layer's own pixel, and the body showing where the layer is transparent.
    assert (at(0, 1, 2), at(0, 2, 2)) == (RED, WHITE)
    assert (at(1, 2, 2), at(1, 3, 2)) == (RED, WHITE)
    assert alone.getpixel((MARGIN + 2 * 4 + 1, MARGIN + 2 * 4 + 1)) == BACKGROUND


def test_a47_the_grid_and_the_game_size_frames_are_composed_too(root):
    project, sprites = previewed(root)
    image = preview.sprite_preview(project, sprites["hat"], [], 4, grid=True, base=sprites["hero"])
    assert image.size == preview.sprite_preview(project, sprites["hat"], [], 4, grid=True).size
    # A cell is 4 pixels and a line; the second cell down, third across.
    assert image.getpixel((MARGIN + GRID_MARGIN + 2 * 5 + 2, MARGIN + GRID_MARGIN + 1 * 5 + 2)) == RED
    assert image.getpixel((MARGIN + GRID_MARGIN + 2 * 5 + 2, MARGIN + GRID_MARGIN + 2 * 5 + 2)) == WHITE

    image = preview.sprite_preview(project, sprites["hat"], [], 4, display=True, base=sprites["hero"])
    left = MARGIN + 2 * (20 + GAP)
    assert image.getpixel((left + 2 * 2, MARGIN + 2 * 2)) == WHITE


def test_a47_the_contact_sheet_and_on_draw_a_layer_over_its_base(root):
    project, sprites = previewed(root)
    everything = list(sprites.values())
    bases = check.bases(everything)

    sheet = preview.contact_sheet(project, everything, bases)
    assert sheet.size == preview.contact_sheet(project, everything).size
    # `hat` is the first cell: 10 pixels wide at display scale 2, centred in a
    # cell as wide as the longer label, `hero`.
    left = MARGIN + (len("hero") * CHAR_WIDTH - 10) // 2
    assert sheet.getpixel((left + 2 * 2, MARGIN + 2 * 2)) == WHITE
    assert sheet.getpixel((left + 2 * 2, MARGIN + 1 * 2)) == RED

    standing = preview.on_tile(project, sprites["hat"], sprites["hero"], 2, bases)
    assert standing.size == preview.on_tile(project, sprites["hat"], sprites["hero"], 2).size


def test_a47_sprite_preview_of_a_layer_writes_it_over_its_base(root, capsys):
    previewed(root)
    assert main(["preview", "hat"]) == 0
    assert capsys.readouterr().out == ".preview/hat.plain.png\n"
    with Image.open(root / ".preview" / "hat.plain.png") as opened:
        image = opened.convert("RGBA")
    assert image.getpixel((MARGIN + 2 * 4 + 1, MARGIN + 2 * 4 + 1)) == WHITE
    assert image.getpixel((MARGIN + 2 * 4 + 1, MARGIN + 1 * 4 + 1)) == RED


def test_sprite_show_prints_the_layer_alone(root, capsys):
    previewed(root)
    assert main(["show", "hat"]) == 0
    assert capsys.readouterr().out.splitlines()[2:] == ["0  .....", "1  ..r..", "2  .....", "3  .....", "4  ....."]


def test_a_layer_with_a_bad_over_is_previewed_alone(root, capsys):
    hat = "outline = false\ngrounded = false\n" + HAT.replace('"hero"', '"hreo"')
    loaded(root, {"hero.sprite.toml": HERO, "hat.sprite.toml": hat})
    assert main(["preview", "hat"]) == 0
    assert capsys.readouterr().out.splitlines() == [
        "hat.sprite.toml:4:1: E108 over names unknown sprite 'hreo'",
        "1 error, 0 warnings in 1 file",
        ".preview/hat.plain.png",
    ]
    with Image.open(root / ".preview" / "hat.plain.png") as opened:
        image = opened.convert("RGBA")
    assert image.getpixel((MARGIN + 2 * 4 + 1, MARGIN + 1 * 4 + 1)) == RED
    assert image.getpixel((MARGIN + 2 * 4 + 1, MARGIN + 2 * 4 + 1)) == BACKGROUND


# --- A55: unoutlined ----------------------------------------------------------


def test_add_outline_draws_nothing_around_a_listed_pixel_standing_alone():
    rows = (".....", ".w...", ".....", "...b.", ".....")
    assert add_outline(rows, "k", frozenset("w")) == (".....", ".w...", "...k.", "..kbk", "...k.")


def test_add_outline_with_a_listed_pixel_touching_the_shape():
    """The smoke is outlined only where the shape's outline falls anyway."""
    rows = (".....", "..w..", "..b..", ".....", ".....")
    assert add_outline(rows, "k", frozenset("w")) == (".....", "..w..", ".kbk.", "..k..", ".....")


def test_add_outline_with_nothing_listed_is_as_before():
    rows = (".....", "..w..", "..b..", ".....", ".....")
    assert add_outline(rows, "k") == add_outline(rows, "k", frozenset()) == ("..k..", ".kwk.", ".kbk.", "..k..", ".....")


SMOKE = '''\
canvas = "unit"
grounded = false
unoutlined = ["w"]

[frames.main.runs]
0 = [[0, "w"]]
3 = [[2, "b"]]
'''


def test_a55_with_auto_a_lone_listed_pixel_renders_as_that_one_pixel(root):
    _, sprites, found = loaded(root, {"smoke.sprite.toml": 'outline = "auto"\n' + SMOKE})
    assert found == []
    assert sprites["smoke"].frames[0].rows == ("w....", ".....", "..k..", ".kbk.", "..k..")


def test_a55_without_auto_a_listed_pixel_touching_transparency_is_no_e201(root):
    _, _, found = loaded(root, {"smoke.sprite.toml": SMOKE})
    assert found == [
        "smoke.sprite.toml:5:1: E201 frame 'main' row 3, col 2: 'b' touches transparency, expected outline key 'k'"
    ]


def test_a_listed_pixel_counts_as_drawn_for_its_neighbours(root):
    smoke = SMOKE.replace('0 = [[0, "w"]]\n3 = [[2, "b"]]', '2 = [[2, "w"]]\n3 = [[1, "kbk"]]\n4 = [[2, "k"]]')
    assert loaded(root, {"smoke.sprite.toml": smoke})[2] == []


def test_a_variant_that_swaps_a_listed_key_keeps_it_unoutlined(root):
    smoke = 'outline = "auto"\n' + SMOKE + '\n[variants.red]\nswap = { w = "r" }\n'
    _, sprites, found = loaded(root, {"smoke.sprite.toml": smoke})
    assert found == []
    assert sprites["smoke_red"].unoutlined == frozenset("r")
    assert sprites["smoke_red"].frames[0].rows[0] == "r...."


@pytest.mark.parametrize("value", ['"w"', '["ww"]', "[1]"])
def test_unoutlined_that_is_not_a_list_of_keys_is_e001(root, value):
    _, _, found = loaded(root, {"smoke.sprite.toml": SMOKE.replace('["w"]', value)})
    assert "smoke.sprite.toml:3:1: E001 unoutlined must be a list of palette keys" in found


def test_an_unoutlined_key_that_is_not_in_the_palette_is_e107(root):
    _, _, found = loaded(root, {"smoke.sprite.toml": SMOKE.replace('["w"]', '["w", "x"]')})
    assert "smoke.sprite.toml:3:1: E107 unoutlined key 'x' is not in the palette" in found


def test_unoutlined_on_a_sprite_without_the_outline_rule_does_nothing(root):
    smoke = SMOKE.replace('"unit"', '"tile"').replace("grounded = false\n", "")
    assert loaded(root, {"smoke.sprite.toml": smoke})[2] == []
