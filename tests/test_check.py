from pathlib import Path

import pytest
from PIL import Image

from conftest import write_project
from sprite_tool import check
from sprite_tool.model import format_problem
from sprite_tool.project import load
from sprite_tool.spritefile import load_all

# `unit` is 5 wide and 4 high so that a width/height mix-up shows.
CONFIG = """\
version = 1

[canvas.unit]
size = [5, 4]
anchor = [2, 4]
outline = ["k"]
grounded = true

[canvas.plain]
size = [5, 4]
anchor = [0, 0]
"""

PALETTE = """\
[colors]
k = "#000000"
w = "#ffffff"
b = "#0000ff"
r = "#ff0000"
"""

# `idle_0 = """` is on line 4, so row n is on line 5 + n.
HERO = '''\
canvas = "unit"

[frames]
idle_0 = """
.kkk.
kwwwk
kbbbk
.kkk.
"""
'''


def load_project(root: Path, config: str = CONFIG, palette: str = PALETTE):
    project, problems = load(write_project(root, config, palette))
    assert problems == []
    return project


@pytest.fixture
def project(tmp_path):
    return load_project(tmp_path / "sprites")


def write_sprite(project, text, name="hero.sprite.toml") -> Path:
    path = project.root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def run_files(project, files: dict[str, str]):
    """Write the sprite files, load them all and run the checks.

    The files must parse cleanly, so every problem returned is from `check`.
    """
    for name, text in files.items():
        write_sprite(project, text, name)
    sprites, problems = load_all(project)
    assert problems == []
    return check.run(project, sprites)


def run_text(project, text):
    return run_files(project, {"hero.sprite.toml": text})


def positions(problems):
    return [(problem.line, problem.col, problem.code) for problem in problems]


def lines(project, problems):
    return [format_problem(problem, project.root) for problem in problems]


def test_clean_sprite_has_no_problems(project):
    assert run_text(project, HERO) == []


# --- E106 fully transparent ---------------------------------------------------


def test_fully_transparent_frame_is_e106_at_its_first_row(project):
    text = HERO + 'empty = """\n.....\n.....\n.....\n.....\n"""\n'
    problems = run_text(project, text)
    assert positions(problems) == [(11, 1, "E106")]
    assert problems[0].message == "frame 'empty' is fully transparent"


def test_fully_transparent_frame_is_not_also_ungrounded(project):
    text = 'canvas = "unit"\n\n[frames]\nempty = """\n.....\n.....\n.....\n.....\n"""\n'
    assert [problem.code for problem in run_text(project, text)] == ["E106"]


# --- E201 outline -------------------------------------------------------------


def test_edge_pixel_that_is_not_an_outline_key_is_e201(project):
    problems = run_text(project, HERO.replace("kbbbk", "kbbbw"))
    assert lines(project, problems) == [
        "hero.sprite.toml:7:5: E201 frame 'idle_0': 'w' touches transparency, expected outline key 'k'"
    ]


def test_canvas_edge_counts_as_transparent(project):
    text = HERO.replace(".kkk.\nkwwwk", "kkbkk\nkwwwk")
    assert positions(run_text(project, text)) == [(5, 3, "E201")]


def test_interior_pixels_need_no_outline_key(project):
    # Every non-outline pixel has four non-transparent neighbours.
    assert run_text(project, HERO.replace("kwwwk", "kbwrk")) == []


def test_outline_lists_every_allowed_key(tmp_path):
    project = load_project(tmp_path, CONFIG.replace('outline = ["k"]', 'outline = ["k", "b"]'))
    problems = run_text(project, HERO.replace(".kkk.\nkwwwk", ".kbk.\nkwwww"))
    assert positions(problems) == [(6, 5, "E201")]
    assert problems[0].message.endswith("expected outline key 'b' or 'k'")


def test_sprite_can_opt_out_of_the_outline_rule(project):
    assert run_text(project, "outline = false\n" + HERO.replace("kbbbk", "kbbbw")) == []


def test_canvas_without_an_outline_rule_is_not_checked(project):
    text = HERO.replace('"unit"', '"plain"').replace("kbbbk", "wbbbw")
    assert run_text(project, text) == []


def test_e201_in_a_derived_frame_is_at_its_definition_with_row_and_col(project):
    text = HERO + '\n[frames.idle_1]\nfrom = "idle_0"\nrows = { 2 = "kbbbw" }\n'
    problems = run_text(project, text)
    assert lines(project, problems) == [
        "hero.sprite.toml:13:1: E201 frame 'idle_1' row 2, col 4: 'w' touches transparency, expected outline key 'k'"
    ]


def test_e201_is_capped_at_ten_per_frame_then_a_count(project):
    # The 14 pixels on the canvas edge all fail; the 6 inside do not.
    text = HERO.replace(".kkk.\nkwwwk\nkbbbk\n.kkk.", "wwwww\nwwwww\nwwwww\nwwwww")
    problems = run_text(project, text)
    assert [problem.code for problem in problems] == ["E201"] * 11
    assert positions(problems[:10]) == [
        (5, 1, "E201"), (5, 2, "E201"), (5, 3, "E201"), (5, 4, "E201"), (5, 5, "E201"),
        (6, 1, "E201"), (6, 5, "E201"),
        (7, 1, "E201"), (7, 5, "E201"),
        (8, 1, "E201"),
    ]  # fmt: skip
    assert positions(problems[10:]) == [(5, 1, "E201")]
    assert problems[10].message == "4 more outline problems in frame 'idle_0'"


def test_e201_cap_is_per_frame(project):
    grid = "wwwww\n" * 4
    text = f'canvas = "unit"\n\n[frames]\na = """\n{grid}"""\nb = """\n{grid}"""\n'
    assert len(run_text(project, text)) == 22


# --- E202 grounded ------------------------------------------------------------


def test_empty_bottom_row_is_e202_at_that_row(project):
    problems = run_text(project, HERO.replace(".kkk.\nkwwwk\nkbbbk\n.kkk.", ".kkk.\nkwwwk\n.kkk.\n....."))
    assert positions(problems) == [(8, 1, "E202")]
    assert problems[0].message == "frame 'idle_0': bottom row is empty, sprite must stand on it"


def test_e202_in_a_derived_frame_is_at_its_definition(project):
    text = "outline = false\n" + HERO + '\n[frames.idle_1]\nfrom = "idle_0"\nshift = [0, -1]\n'
    assert positions(run_text(project, text)) == [(12, 1, "E202")]


def test_sprite_can_opt_out_of_the_grounded_rule(project):
    text = "grounded = false\n" + HERO.replace(".kkk.\nkwwwk\nkbbbk\n.kkk.", ".kkk.\nkwwwk\n.kkk.\n.....")
    assert run_text(project, text) == []


def test_canvas_without_a_grounded_rule_is_not_checked(project):
    text = HERO.replace('"unit"', '"plain"').replace("kbbbk\n.kkk.", ".kkk.\n.....")
    assert run_text(project, text) == []


# --- variants -----------------------------------------------------------------

RED = '\n[variants.red]\nswap = { b = "r" }\n'


def test_variant_that_recolours_the_outline_is_e201_naming_the_variant(project):
    problems = run_text(project, HERO + '\n[variants.pale]\nswap = { k = "w" }\n')
    assert len(problems) == 10
    assert format_problem(problems[0], project.root) == (
        "hero.sprite.toml:5:2: E201 variant 'hero_pale' frame 'idle_0': "
        "'w' touches transparency, expected outline key 'k'"
    )


def test_outline_fault_in_the_base_is_not_repeated_for_its_variants(project):
    problems = run_text(project, HERO.replace("kbbbk", "kbbbw") + RED)
    assert positions(problems) == [(7, 5, "E201")]
    assert "variant" not in problems[0].message


def test_variants_do_not_repeat_e106_e202_or_w002(project):
    text = (
        HERO.replace("kbbbk\n.kkk.", ".kkk.\n.....")
        + 'empty = """\n.....\n.....\n.....\n.....\n"""\n'
        + '\n[anim.idle]\nframes = ["idle_0"]\nms = 100\n'
        + RED
    )
    assert sorted(problem.code for problem in run_text(project, text)) == ["E106", "E202", "W002"]


# --- E003 duplicate ids -------------------------------------------------------


def test_two_files_with_the_same_stem_are_e003_at_each_file(project):
    problems = run_files(project, {"units/hero.sprite.toml": HERO, "items/hero.sprite.toml": HERO})
    assert lines(project, problems) == [
        "items/hero.sprite.toml: E003 duplicate sprite id 'hero', also in units/hero.sprite.toml",
        "units/hero.sprite.toml: E003 duplicate sprite id 'hero', also in items/hero.sprite.toml",
    ]


def test_variant_id_equal_to_another_sprite_id_is_e003(project):
    problems = run_files(project, {"hero.sprite.toml": HERO + RED, "hero_red.sprite.toml": HERO})
    assert lines(project, problems) == [
        "hero.sprite.toml: E003 duplicate sprite id 'hero_red', also in hero_red.sprite.toml",
        "hero_red.sprite.toml: E003 duplicate sprite id 'hero_red', also in hero.sprite.toml",
    ]


def test_distinct_ids_are_not_e003(project):
    assert run_files(project, {"hero.sprite.toml": HERO + RED, "orc.sprite.toml": HERO}) == []


# --- W001 shared palette colour -----------------------------------------------


def test_two_palette_keys_with_one_colour_are_w001_at_the_palette_file(tmp_path):
    project = load_project(tmp_path, palette=PALETTE + 'x = "#0000ffff"\ny = "#0000ff"\nz = "#0000ff80"\n')
    assert lines(project, run_text(project, HERO)) == [
        "palette.toml: W001 palette keys 'b', 'x' and 'y' share the colour #0000ff"
    ]


# --- W002 unused frames -------------------------------------------------------

SPARE = 'spare = """\n.kkk.\nkwwwk\nkbbbk\n.kkk.\n"""\nextra = """\n.kkk.\nkrrrk\nkbbbk\n.kkk.\n"""\n'


def test_frames_in_no_animation_are_w002_at_the_first_of_them(project):
    problems = run_text(project, HERO + SPARE + '\n[anim.idle]\nframes = ["idle_0"]\nms = 100\n')
    assert positions(problems) == [(11, 1, "W002")]
    assert problems[0].message == "frames not used by any animation: spare, extra"


def test_sprite_without_animations_has_no_w002(project):
    assert run_text(project, HERO + SPARE) == []


def test_frame_used_by_any_animation_is_not_w002(project):
    anims = '\n[anim.a]\nframes = ["idle_0", "spare"]\nms = 100\n\n[anim.b]\nframes = ["extra"]\nms = 100\n'
    assert run_text(project, HERO + SPARE + anims) == []
