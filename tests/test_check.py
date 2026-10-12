from pathlib import Path

import pytest
from PIL import Image

from conftest import write_project
from sprite_tool import check, render
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
    A shift that loses pixels is the parser's warning and is let through.
    """
    for name, text in files.items():
        write_sprite(project, text, name)
    sprites, problems = load_all(project)
    assert [problem for problem in problems if problem.code != "W006"] == []
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
    text = HERO + 'empty = """\n.....\n.....\n.....\n.....\n"""\n'
    assert [problem.code for problem in run_text(project, text)] == ["E106"]


# --- W003 blank sprite ---------------------------------------------------------

BLANK = 'canvas = "unit"\n\n[frames]\nmain = """\n.....\n.....\n.....\n.....\n"""\n'


def test_sprite_with_nothing_drawn_is_w003_only(project):
    problems = run_text(project, BLANK + '[frames.other]\nfrom = "main"\n')
    assert positions(problems) == [(5, 1, "W003")]
    assert problems[0].message == "sprite 'hero' is blank (nothing drawn yet); it is left out of the build"


def test_is_blank(project):
    sprites, _ = load_all(project, [write_sprite(project, BLANK), write_sprite(project, HERO, "drawn.sprite.toml")])
    assert {sprite.id: check.is_blank(sprite) for sprite in sprites} == {"drawn": False, "hero": True}


# --- E201 in derived frames ----------------------------------------------------

# Row 1 ends in `w`, which touches the canvas edge: one fault at row 1, col 4.
FAULTY = 'canvas = "unit"\n\n[frames]\nidle_0 = """\n.kkk.\nkwwww\nkbbbk\n.kkk.\n"""\n'


def test_fault_carried_into_derived_frames_is_reported_once(project):
    text = FAULTY + (
        '[frames.same]\nfrom = "idle_0"\n'
        '[frames.flipped]\nfrom = "idle_0"\nflip = true\n'
        '[frames.chained]\nfrom = "flipped"\nrows = { 2 = "kbbbk" }\n'
    )
    assert positions(run_text(project, text)) == [(6, 5, "E201")]


def test_fault_a_derived_frame_adds_is_still_reported(project):
    text = HERO + '[frames.idle_1]\nfrom = "idle_0"\nrows = { 1 = "kwwww" }\n'
    problems = run_text(project, text)
    assert [problem.code for problem in problems] == ["E201"]
    assert "frame 'idle_1' row 1, col 4" in problems[0].message


def test_fault_a_shift_exposes_is_still_reported(project):
    """Shifted right, the `w` of row 1 lands on the canvas edge, where the parent had `k`."""
    text = HERO + '[frames.idle_1]\nfrom = "idle_0"\nshift = [1, 0]\n'
    messages = [problem.message for problem in run_text(project, text) if problem.code == "E201"]
    assert len(messages) == 2  # rows 1 and 2, col 4
    assert all("frame 'idle_1'" in message and "col 4" in message for message in messages)


def test_shifted_copy_of_a_fault_is_not_reported_again(project):
    # The fault moves from col 3 to col 2 with the shift.
    text = 'canvas = "unit"\n\n[frames]\nidle_0 = """\n.kkk.\n.kkw.\n.kkk.\n.kkk.\n"""\n'
    text += '[frames.idle_1]\nfrom = "idle_0"\nshift = [-1, 0]\n'
    assert positions(run_text(project, text)) == [(6, 4, "E201")]


# --- E003 loose PNG names ------------------------------------------------------


def test_sprite_id_that_is_another_sprites_frame_file_is_e003(project):
    hero = write_sprite(project, HERO + '[frames.idle_1]\nfrom = "idle_0"\n')
    clash = write_sprite(project, HERO, "hero__idle_1.sprite.toml")
    sprites, problems = load_all(project, [hero, clash])
    problems += check.run(project, sprites)
    assert [(problem.path, problem.code, problem.message) for problem in problems] == [
        (
            clash,
            "E003",
            "sprite id 'hero__idle_1' clashes with frame 'idle_1' of sprite 'hero' (both export as hero__idle_1.png)",
        )
    ]


def test_single_frame_sprite_writes_no_frame_files_so_nothing_clashes(project):
    sprites, problems = load_all(
        project, [write_sprite(project, HERO), write_sprite(project, HERO, "hero__idle_0.sprite.toml")]
    )
    assert problems + check.run(project, sprites) == []


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


# --- PNG checks ---------------------------------------------------------------

BLACK = (0, 0, 0, 255)
BLUE = (0, 0, 255, 255)
CLEAR = (0, 0, 0, 0)


def write_png(path: Path, size=(5, 4), fill=CLEAR, **pixels) -> Path:
    """Write an RGBA PNG; `pixels` maps names like `x3y1` to colours."""
    image = Image.new("RGBA", size, fill)
    for name, colour in pixels.items():
        x, y = name[1:].split("y")
        image.putpixel((int(x), int(y)), colour)
    image.save(path)
    return path


def check_png(project, path, canvas="unit"):
    return check.check_png(project, path, project.canvases[canvas])


def test_png_in_palette_colours_at_the_canvas_size_is_clean(project):
    path = write_png(project.root / "hero.png", x0y0=BLACK, x4y3=BLUE)
    assert check_png(project, path) == []


def test_png_of_the_wrong_size_is_e301(project):
    path = write_png(project.root / "hero.png", size=(4, 5))
    assert lines(project, check_png(project, path)) == [
        "hero.png: E301 image is 4x5, canvas 'unit' is 5x4"
    ]


def test_off_palette_pixel_is_e302_at_x_y(project):
    path = write_png(project.root / "hero.png", x3y1=(255, 0, 255, 255))
    assert lines(project, check_png(project, path)) == [
        "hero.png:3,1: E302 colour #ff00ff is not in the palette"
    ]


def test_off_palette_pixel_at_the_origin_keeps_its_position(project):
    path = write_png(project.root / "hero.png", x0y0=(1, 2, 3, 255))
    assert lines(project, check_png(project, path)) == [
        "hero.png:0,0: E302 colour #010203 is not in the palette"
    ]


def test_alpha_zero_pixel_is_transparent_whatever_its_rgb(project):
    path = write_png(project.root / "hero.png", fill=(255, 0, 255, 0), x1y1=(9, 9, 9, 0))
    assert check_png(project, path) == []


def test_palette_colour_with_another_alpha_is_e302(project):
    path = write_png(project.root / "hero.png", x2y2=(0, 0, 255, 128))
    assert lines(project, check_png(project, path)) == [
        "hero.png:2,2: E302 colour #0000ff80 is not in the palette"
    ]


def test_png_without_an_alpha_channel_is_read_as_opaque(project):
    path = project.root / "hero.png"
    Image.new("RGB", (5, 4), (0, 0, 255)).save(path)
    assert check_png(project, path) == []


def test_wrong_size_and_off_palette_pixels_are_both_reported(project):
    path = write_png(project.root / "hero.png", size=(2, 2), x1y0=(255, 0, 255, 255))
    assert [problem.code for problem in check_png(project, path)] == ["E301", "E302"]


def test_e302_is_capped_at_ten_per_file_then_a_count(project):
    path = write_png(project.root / "hero.png", fill=(255, 0, 255, 255))
    problems = check_png(project, path)
    assert [problem.code for problem in problems] == ["E302"] * 11
    assert lines(project, problems[:6]) == [
        f"hero.png:{x},{y}: E302 colour #ff00ff is not in the palette"
        for x, y in [(0, 0), (1, 0), (2, 0), (3, 0), (4, 0), (0, 1)]
    ]
    assert lines(project, problems[10:]) == ["hero.png: E302 10 more pixels not in the palette"]


def test_file_that_is_not_an_image_is_e001(project):
    path = project.root / "hero.png"
    path.write_text("not a png", encoding="utf-8")
    problems = check_png(project, path)
    assert positions(problems) == [(0, 0, "E001")]
    assert problems[0].message.startswith("cannot read image")


def test_missing_png_is_e001(project):
    assert positions(check_png(project, project.root / "nope.png")) == [(0, 0, "E001")]


# --- automatic outline --------------------------------------------------------

# `unit` is 7 wide and 6 high: room for a shape with a leg gap and its outline.
AUTO_CONFIG = """\
version = 1

[canvas.unit]
size = [7, 6]
anchor = [3, 6]
outline = ["k"]
grounded = true
"""

# `main = """` is on line 5, so row n is on line 6 + n.
AUTO = '''\
canvas = "unit"
outline = "auto"

[frames]
main = """
.......
..www..
.wwbww.
..www..
..w.w..
.......
"""
'''

BY_HAND = '''\
canvas = "unit"

[frames]
main = """
..kkk..
.kwwwk.
kwwbwwk
.kwwwk.
.kwkwk.
..k.k..
"""
'''

EDGE_B = "'b' is on the canvas edge; with outline = \"auto\" keep the interior 1 pixel inside"
EDGE_W = EDGE_B.replace("'b'", "'w'")


@pytest.fixture
def auto_project(tmp_path):
    return load_project(tmp_path / "sprites", AUTO_CONFIG)


def test_a16_auto_outlined_sprite_passes_and_renders_as_its_hand_outlined_twin(auto_project):
    files = {"auto.sprite.toml": AUTO, "by_hand.sprite.toml": BY_HAND}
    assert run_files(auto_project, files) == []

    auto, by_hand = load_all(auto_project)[0]
    png = [render.png_bytes(render.render(sprite.frames[0], auto_project.palette)) for sprite in (auto, by_hand)]
    assert auto.auto_outline and not by_hand.auto_outline
    assert png[0] == png[1]


def test_a17_interior_pixel_on_the_canvas_edge_of_an_auto_sprite_is_e201_at_that_pixel(auto_project):
    problems = run_text(auto_project, AUTO.replace(".wwbww.", "bwwbww."))
    assert lines(auto_project, problems) == [f"hero.sprite.toml:8:1: E201 frame 'main': {EDGE_B}"]


def test_interior_on_the_bottom_row_of_an_auto_sprite_is_e201_for_each_pixel(auto_project):
    problems = run_text(auto_project, AUTO.replace("..w.w..\n.......", "..w.w..\n..w.w.."))
    assert positions(problems) == [(11, 3, "E201"), (11, 5, "E201")]
    assert all(problem.message.endswith(EDGE_W) for problem in problems)


def test_edge_fault_in_a_runs_frame_of_an_auto_sprite_names_its_row_and_col(auto_project):
    text = (
        'canvas = "unit"\noutline = "auto"\n\n[frames.main.runs]\n'
        '1 = [[2, "www"]]\n2 = [[0, "bwwbww"]]\n3 = [[2, "www"]]\n4 = [[2, "w"], [4, "w"]]\n'
    )
    problems = run_text(auto_project, text)
    assert lines(auto_project, problems) == [
        f"hero.sprite.toml:4:1: E201 frame 'main' row 2, col 0: {EDGE_B}"
    ]


def test_edge_fault_of_an_auto_sprite_is_not_repeated_in_a_derived_frame(auto_project):
    text = AUTO.replace(".wwbww.", "bwwbww.") + '\n[frames.blink]\nfrom = "main"\nrows = { 1 = "..wbw.." }\n'
    assert positions(run_text(auto_project, text)) == [(8, 1, "E201")]


def test_frame_shifted_onto_the_edge_of_an_auto_sprite_is_e201_at_its_definition(auto_project):
    text = AUTO + '\n[frames.lean]\nfrom = "main"\nshift = [-1, 0]\n'
    problems = run_text(auto_project, text)
    assert lines(auto_project, problems) == [
        f"hero.sprite.toml:14:1: E201 frame 'lean' row 2, col 0: {EDGE_W}"
    ]


def test_variant_that_recolours_the_auto_outline_is_e201_with_the_variant_wording(auto_project):
    problems = run_text(auto_project, AUTO + '\n[variants.pale]\nswap = { k = "w" }\n')
    assert len(problems) == 11
    assert format_problem(problems[0], auto_project.root) == (
        "hero.sprite.toml:6:3: E201 variant 'hero_pale' frame 'main': "
        "'w' touches transparency, expected outline key 'k'"
    )


def test_variant_of_an_auto_sprite_that_keeps_the_outline_key_passes(auto_project):
    assert run_text(auto_project, AUTO + '\n[variants.red]\nswap = { b = "r" }\n') == []
