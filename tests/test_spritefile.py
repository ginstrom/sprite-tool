from pathlib import Path

import pytest

from conftest import write_project
from sprite_tool.model import format_problem
from sprite_tool.project import load
from sprite_tool.spritefile import discover, load_all

# `tiny` and `plain` are 4 wide and 3 high so that a width/height mix-up shows.
CONFIG = """\
version = 1

[canvas.tiny]
size = [4, 3]
anchor = [2, 3]
outline = ["k"]
grounded = true

[canvas.plain]
size = [4, 3]
anchor = [0, 0]

[canvas.tile]
size = [16, 16]
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
TINY = '''\
canvas = "tiny"

[frames]
idle_0 = """
.kk.
kwwk
kbbk
"""
'''


@pytest.fixture
def project(tmp_path):
    loaded, problems = load(write_project(tmp_path / "sprites", CONFIG, PALETTE))
    assert problems == []
    return loaded


def write_sprite(project, text, name="hero.sprite.toml") -> Path:
    path = project.root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def load_text(project, text, name="hero.sprite.toml"):
    """Write one sprite file and load only that file."""
    return load_all(project, [write_sprite(project, text, name)])


def positions(problems):
    return [(problem.line, problem.col, problem.code) for problem in problems]


def frame_rows(sprite, name):
    return next(frame.rows for frame in sprite.frames if frame.name == name)


# --- discovery ------------------------------------------------------------


def test_discover_finds_sprite_files_in_subdirectories_sorted(project):
    write_sprite(project, TINY, "units/warrior.sprite.toml")
    write_sprite(project, TINY, "tiles/ground.sprite.toml")
    write_sprite(project, TINY, "arrow.sprite.toml")
    (project.root / "units" / "notes.toml").write_text("x = 1\n", encoding="utf-8")

    assert discover(project.root) == [
        project.root / "arrow.sprite.toml",
        project.root / "tiles" / "ground.sprite.toml",
        project.root / "units" / "warrior.sprite.toml",
    ]


def test_load_all_discovers_files_and_sorts_sprites_by_id(project):
    write_sprite(project, TINY, "units/warrior.sprite.toml")
    write_sprite(project, TINY, "tiles/ground.sprite.toml")
    write_sprite(project, TINY, "arrow.sprite.toml")

    sprites, problems = load_all(project)

    assert problems == []
    assert [sprite.id for sprite in sprites] == ["arrow", "ground", "warrior"]
    assert sprites[2].source == project.root / "units" / "warrior.sprite.toml"


def test_load_all_returns_every_sprite_when_ids_clash(project):
    write_sprite(project, TINY, "a/hero.sprite.toml")
    write_sprite(project, TINY, "b/hero.sprite.toml")

    sprites, problems = load_all(project)

    assert problems == []
    assert [sprite.id for sprite in sprites] == ["hero", "hero"]


def test_load_all_reads_only_the_given_paths(project):
    write_sprite(project, TINY, "arrow.sprite.toml")
    wanted = write_sprite(project, TINY, "hero.sprite.toml")

    sprites, _ = load_all(project, [wanted])

    assert [sprite.id for sprite in sprites] == ["hero"]


# --- literal grids --------------------------------------------------------


def test_grid_frame_becomes_a_literal_frame(project):
    sprites, problems = load_text(project, TINY)

    assert problems == []
    (sprite,) = sprites
    assert sprite.id == "hero"
    assert sprite.canvas == project.canvases["tiny"]
    assert sprite.variant_of is None
    assert sprite.anims == ()
    (frame,) = sprite.frames
    assert frame.name == "idle_0"
    assert frame.rows == (".kk.", "kwwk", "kbbk")
    assert frame.literal is True
    assert frame.line == 5


def test_frames_keep_file_order(project):
    text = TINY + 'walk = """\n....\n.kk.\nkwwk\n"""\nattack = """\n....\n....\nkkkk\n"""\n'
    (sprite,), problems = load_text(project, text)

    assert problems == []
    assert [frame.name for frame in sprite.frames] == ["idle_0", "walk", "attack"]
    assert [frame.line for frame in sprite.frames] == [5, 10, 15]


def test_single_quoted_grid_is_located(project):
    text = "canvas = \"tiny\"\n[frames]\nmain = '''\n.kk.\nkwwk\nkbbk\n'''\n"
    (sprite,), problems = load_text(project, text)

    assert problems == []
    assert sprite.frames[0].line == 4


def test_canvas_rules_apply_by_default(project):
    (sprite,), _ = load_text(project, TINY)
    assert sprite.outline is True
    assert sprite.grounded is True


def test_sprite_can_opt_out_of_canvas_rules(project):
    (sprite,), problems = load_text(project, "outline = false\ngrounded = false\n" + TINY)
    assert problems == []
    assert sprite.outline is False
    assert sprite.grounded is False


def test_flags_are_false_when_the_canvas_has_no_rule(project):
    (sprite,), problems = load_text(project, TINY.replace('"tiny"', '"plain"'))
    assert problems == []
    assert sprite.outline is False
    assert sprite.grounded is False


# --- E001 -----------------------------------------------------------------


def test_invalid_toml_is_e001_and_yields_no_sprite(project):
    sprites, problems = load_text(project, 'canvas = "tiny"\n[frames\n')

    assert sprites == []
    assert positions(problems) == [(2, 8, "E001")]
    assert problems[0].path == project.root / "hero.sprite.toml"


def test_unknown_top_level_field_is_e001(project):
    sprites, problems = load_text(project, 'canvas = "tiny"\nsize = 3\n' + TINY.split("\n", 1)[1])

    assert positions(problems) == [(2, 1, "E001")]
    assert "'size'" in problems[0].message
    assert [sprite.id for sprite in sprites] == ["hero"]


@pytest.mark.parametrize("line", ["outline = 1", 'grounded = "no"'])
def test_wrongly_typed_flag_is_e001(project, line):
    _, problems = load_text(project, line + "\n" + TINY)
    assert positions(problems) == [(1, 1, "E001")]


def test_missing_canvas_is_e001_and_yields_no_sprite(project):
    sprites, problems = load_text(project, TINY.split("\n", 1)[1])
    assert sprites == []
    assert positions(problems) == [(1, 1, "E001")]


def test_bad_frame_name_is_e001_and_drops_the_frame(project):
    text = TINY + '"Idle-1" = """\n....\n....\nkkkk\n"""\n'
    (sprite,), problems = load_text(project, text)

    assert positions(problems) == [(9, 1, "E001")]
    assert "'Idle-1'" in problems[0].message
    assert [frame.name for frame in sprite.frames] == ["idle_0"]


def test_frame_of_the_wrong_type_is_e001(project):
    (sprite,), problems = load_text(project, TINY + "walk = 3\n")
    assert positions(problems) == [(9, 1, "E001")]
    assert [frame.name for frame in sprite.frames] == ["idle_0"]


def test_file_without_frames_is_e001_and_yields_no_sprite(project):
    sprites, problems = load_text(project, 'canvas = "tiny"\n')
    assert sprites == []
    assert positions(problems) == [(1, 1, "E001")]


# --- E101 -----------------------------------------------------------------


def test_unknown_canvas_is_e101_and_yields_no_sprite(project):
    sprites, problems = load_text(project, "# a warrior\n" + TINY.replace('"tiny"', '"huge"'))

    assert sprites == []
    assert positions(problems) == [(2, 1, "E101")]
    assert "'huge'" in problems[0].message


# --- E102 -----------------------------------------------------------------


def test_wrong_row_count_is_e102_at_the_opening_line(project):
    sprites, problems = load_text(project, TINY.replace("kbbk\n", ""))

    assert sprites == []
    assert positions(problems) == [(4, 1, "E102")]
    assert "idle_0" in problems[0].message


def test_wrong_row_count_still_reports_the_rows_it_has(project):
    _, problems = load_text(project, TINY.replace("kbbk\n", "kbbkk\nk?bk\n"))

    assert positions(problems) == [(4, 1, "E102"), (7, 5, "E103"), (8, 2, "E104")]


# --- E103 -----------------------------------------------------------------


def test_long_row_is_e103_one_past_the_expected_width(project):
    sprites, problems = load_text(project, TINY.replace("kwwk", "kwwwwk"))

    assert sprites == []
    assert positions(problems) == [(6, 5, "E103")]
    assert "idle_0" in problems[0].message


def test_short_row_is_e103_one_past_its_last_character(project):
    _, problems = load_text(project, TINY.replace("kwwk", "kw"))
    assert positions(problems) == [(6, 3, "E103")]


def test_trailing_whitespace_is_e103_at_the_first_whitespace_character(project):
    _, problems = load_text(project, TINY.replace("kwwk", "kwwk  "))
    assert positions(problems) == [(6, 5, "E103")]
    assert "trailing whitespace" in problems[0].message


def test_e103_is_reported_once_per_row(project):
    _, problems = load_text(project, TINY.replace(".kk.", ".kk").replace("kbbk", "kbbkk \t"))
    assert positions(problems) == [(5, 4, "E103"), (7, 6, "E103")]


# --- E104 -----------------------------------------------------------------


def test_unknown_palette_key_is_e104_per_pixel(project):
    sprites, problems = load_text(project, TINY.replace("kwwk", "kxwy"))

    assert sprites == []
    assert positions(problems) == [(6, 2, "E104"), (6, 4, "E104")]
    assert problems[0].message == "unknown palette key 'x'"


def test_worked_position_example(project):
    rows = ["." * 16] * 16
    rows[3] = "." * 13 + "x" + ".."
    text = '# units/warrior\ncanvas = "tile"\n\n[frames]\nidle_0 = """\n' + "\n".join(rows) + '\n"""\n'

    _, problems = load_text(project, text, "units/warrior.sprite.toml")

    assert [format_problem(problem, project.root) for problem in problems] == [
        "units/warrior.sprite.toml:9:14: E104 unknown palette key 'x'"
    ]


def test_e104_is_capped_at_ten_per_frame_then_a_count(project):
    _, problems = load_text(project, TINY.replace(".kk.", "????").replace("kwwk", "????").replace("kbbk", "????"))

    assert [problem.code for problem in problems] == ["E104"] * 11
    assert positions(problems)[:10] == [(5 + n // 4, 1 + n % 4, "E104") for n in range(10)]
    assert positions(problems)[10] == (4, 1, "E104")
    assert problems[10].message == "2 more unknown palette keys in frame 'idle_0'"


def test_e104_cap_is_per_frame(project):
    bad = '"""\n????\n????\n????\n"""\n'
    _, problems = load_text(project, 'canvas = "tiny"\n[frames]\na = ' + bad + "b = " + bad)
    assert len(problems) == 22


# --- partial results ------------------------------------------------------


def test_file_with_one_bad_frame_keeps_its_good_frames(project):
    text = TINY + 'walk = """\n....\n.zz.\nkwwk\n"""\nattack = """\n....\n....\nkkkk\n"""\n'
    (sprite,), problems = load_text(project, text)

    assert positions(problems) == [(11, 2, "E104"), (11, 3, "E104")]
    assert [frame.name for frame in sprite.frames] == ["idle_0", "attack"]


def test_file_with_no_good_frame_yields_no_sprite(project):
    sprites, problems = load_text(project, TINY.replace("kwwk", "k??k"))
    assert sprites == []
    assert len(problems) == 2


def test_a_bad_file_does_not_stop_the_next_file(project):
    write_sprite(project, "not toml [", "a.sprite.toml")
    write_sprite(project, TINY, "b.sprite.toml")

    sprites, problems = load_all(project)

    assert [sprite.id for sprite in sprites] == ["b"]
    assert [problem.path.name for problem in problems] == ["a.sprite.toml"]


def test_unreadable_file_is_e001(project):
    path = project.root / "ghost.sprite.toml"
    sprites, problems = load_all(project, [path])

    assert sprites == []
    assert [(problem.path, problem.code) for problem in problems] == [(path, "E001")]


# --- derived frames -------------------------------------------------------

# idle_0 opens on line 4; `[frames.next]` is on line 10.
BASE = TINY.replace(".kk.\nkwwk\nkbbk", "k...\nkw..\nkbw.") + "\n[frames.next]\n"


def derived(project, body, text=BASE):
    return load_text(project, text + body)


def test_from_with_rows_equals_the_hand_written_grid(project):
    """A4, at the grid level."""
    text = BASE.replace("\n[frames.next]", 'full = """\nk...\nkbb.\nkbw.\n"""\n\n[frames.next]')
    (sprite,), problems = derived(project, 'from = "idle_0"\nrows = { 1 = "kbb." }\n', text)

    assert problems == []
    assert frame_rows(sprite, "next") == frame_rows(sprite, "full") == ("k...", "kbb.", "kbw.")


def test_derived_frame_is_not_literal_and_points_at_its_rows_key(project):
    (sprite,), _ = derived(project, 'from = "idle_0"\nrows = { 1 = "kbb." }\n')
    frame = sprite.frames[1]
    assert (frame.name, frame.literal, frame.line) == ("next", False, 12)


def test_derived_frame_without_rows_points_at_its_table_header(project):
    (sprite,), _ = derived(project, 'from = "idle_0"\nflip = true\n')
    assert (sprite.frames[1].literal, sprite.frames[1].line) == (False, 10)


def test_plain_copy_has_the_parent_rows(project):
    (sprite,), problems = derived(project, 'from = "idle_0"\n')
    assert problems == []
    assert frame_rows(sprite, "next") == ("k...", "kw..", "kbw.")


@pytest.mark.parametrize(
    "shift, expected",
    [
        ("[1, 0]", (".k..", ".kw.", ".kbw")),
        ("[2, 0]", ("..k.", "..kw", "..kb")),
        ("[-1, 0]", ("....", "w...", "bw..")),
        ("[0, 1]", ("....", "k...", "kw..")),
        ("[0, -2]", ("kbw.", "....", "....")),
        ("[1, -1]", (".kw.", ".kbw", "....")),
        ("[9, 0]", ("....", "....", "....")),
        ("[0, -9]", ("....", "....", "....")),
        ("[0, 0]", ("k...", "kw..", "kbw.")),
    ],
)
def test_shift_moves_pixels_and_drops_those_leaving_the_canvas(project, shift, expected):
    (sprite,), problems = derived(project, f'from = "idle_0"\nshift = {shift}\n')
    assert problems == []
    assert frame_rows(sprite, "next") == expected


def test_flip_mirrors_horizontally(project):
    (sprite,), _ = derived(project, 'from = "idle_0"\nflip = true\n')
    assert frame_rows(sprite, "next") == ("...k", "..wk", ".wbk")


def test_rows_then_shift_then_flip(project):
    # rows:  k... / rrrr / kbw.    shift [1, 0]:  .k.. / .rrr / .kbw    flip:  ..k. / rrr. / wbk.
    (sprite,), problems = derived(project, 'flip = true\nshift = [1, 0]\nrows = { 1 = "rrrr" }\nfrom = "idle_0"\n')
    assert problems == []
    assert frame_rows(sprite, "next") == ("..k.", "rrr.", "wbk.")


def test_chain_of_two_derived_frames(project):
    body = 'from = "idle_0"\nshift = [1, 0]\n\n[frames.last]\nfrom = "next"\nrows = { 0 = "rrrr" }\nflip = true\n'
    (sprite,), problems = derived(project, body)

    assert problems == []
    assert [frame.name for frame in sprite.frames] == ["idle_0", "next", "last"]
    assert frame_rows(sprite, "last") == ("rrrr", ".wk.", "wbk.")


def test_derived_frame_may_come_before_its_parent(project):
    text = 'canvas = "tiny"\n\n[frames.first]\nfrom = "second"\nflip = true\n\n[frames]\nsecond = """\nk...\n....\n....\n"""\n'
    (sprite,), problems = load_text(project, text)

    assert problems == []
    assert [frame.name for frame in sprite.frames] == ["first", "second"]
    assert frame_rows(sprite, "first") == ("...k", "....", "....")


def test_inline_table_frame_is_reported_at_its_own_line(project):
    text = TINY + 'next = { from = "idle_0", rows = { 1 = "k??k" } }\n'
    (sprite,), problems = load_text(project, text)

    assert positions(problems) == [(9, 1, "E104"), (9, 1, "E104")]
    assert [frame.name for frame in sprite.frames] == ["idle_0"]


# --- E105 and other derived frame problems ---------------------------------


def test_from_naming_a_missing_frame_is_e105(project):
    (sprite,), problems = derived(project, "flip = true\nfrom = \"idle_9\"\n")

    assert positions(problems) == [(12, 1, "E105")]
    assert "'next'" in problems[0].message and "'idle_9'" in problems[0].message
    assert [frame.name for frame in sprite.frames] == ["idle_0"]


@pytest.mark.parametrize("index", ["3", "-1", "x", "1.5"])
def test_bad_rows_index_is_e105(project, index):
    (sprite,), problems = derived(project, f'from = "idle_0"\nrows = {{ "{index}" = "kbb." }}\n')

    assert positions(problems) == [(12, 1, "E105")]
    assert "'next'" in problems[0].message
    assert [frame.name for frame in sprite.frames] == ["idle_0"]


def test_from_cycle_is_e105_once_at_its_first_frame(project):
    text = (
        'canvas = "tiny"\n\n[frames.a]\nfrom = "b"\n\n[frames.b]\nfrom = "c"\n\n[frames.c]\nfrom = "a"\n'
        '\n[frames]\nok = """\nk...\n....\n....\n"""\n'
    )
    (sprite,), problems = load_text(project, text)

    assert positions(problems) == [(4, 1, "E105")]
    assert "a -> b -> c -> a" in problems[0].message
    assert [frame.name for frame in sprite.frames] == ["ok"]


def test_frame_derived_from_itself_is_e105(project):
    _, problems = derived(project, 'from = "next"\n')
    assert positions(problems) == [(11, 1, "E105")]


def test_frame_leading_into_a_cycle_is_dropped_without_its_own_problem(project):
    body = 'from = "a"\n\n[frames.a]\nfrom = "b"\n\n[frames.b]\nfrom = "a"\n'
    (sprite,), problems = derived(project, body)

    assert positions(problems) == [(14, 1, "E105")]
    assert [frame.name for frame in sprite.frames] == ["idle_0"]


def test_frame_derived_from_a_failed_frame_is_dropped_silently(project):
    text = BASE.replace("kw..", "k?..").replace("\n[frames.next]", 'ok = """\nk...\n....\n....\n"""\n\n[frames.next]')
    (sprite,), problems = derived(project, 'from = "idle_0"\n', text)

    assert positions(problems) == [(6, 2, "E104")]
    assert [frame.name for frame in sprite.frames] == ["ok"]


def test_replacement_row_problems_are_reported_at_the_rows_key(project):
    (sprite,), problems = derived(project, 'from = "idle_0"\nrows = { 0 = "kbb", 2 = "k?w." }\n')

    assert positions(problems) == [(12, 1, "E103"), (12, 1, "E104")]
    assert "'next'" in problems[0].message and "row 0" in problems[0].message
    assert problems[1].message == "unknown palette key '?' in frame 'next' row 2"
    assert [frame.name for frame in sprite.frames] == ["idle_0"]


@pytest.mark.parametrize(
    "body, line",
    [
        ("flip = true\n", 10),
        ("from = 3\n", 11),
        ('from = "idle_0"\nrows = "kbb."\n', 12),
        ('from = "idle_0"\nrows = { 1 = 7 }\n', 12),
        ('from = "idle_0"\nshift = [1]\n', 12),
        ('from = "idle_0"\nshift = [1, 0.5]\n', 12),
        ('from = "idle_0"\nshift = [true, 0]\n', 12),
        ('from = "idle_0"\nflip = "yes"\n', 12),
        ('from = "idle_0"\nrotate = 90\n', 12),
    ],
)
def test_wrongly_typed_or_unknown_derived_field_is_e001(project, body, line):
    (sprite,), problems = derived(project, body)

    assert positions(problems) == [(line, 1, "E001")]
    assert "'next'" in problems[0].message
    assert [frame.name for frame in sprite.frames] == ["idle_0"]


# --- animations -----------------------------------------------------------

# The bad `rows` key is on line 17 and `[anim.idle]` on line 19.
TWO_FRAMES = TINY + 'idle_1 = """\n....\nkwwk\nkbbk\n"""\n\n[frames.bad]\nfrom = "idle_0"\nrows = { 0 = "????" }\n'
ANIM = TWO_FRAMES + "\n[anim.idle]\n"


def test_two_frames_fixture_lines(project):
    (sprite,), problems = load_text(project, ANIM + 'frames = ["idle_0"]\nms = 100\n')
    assert positions(problems) == [(17, 1, "E104")] * 4
    assert sprite.anims[0].name == "idle"


def anims(project, body):
    (sprite,), problems = load_text(project, ANIM + body)
    return sprite.anims, [problem for problem in problems if problem.line > 17]


def test_animation_is_parsed(project):
    from sprite_tool.model import Anim

    found, problems = anims(project, 'frames = ["idle_0", "idle_1", "idle_0"]\nms = 400\nloop = false\n')

    assert problems == []
    assert found == (Anim(name="idle", frames=("idle_0", "idle_1", "idle_0"), ms=400, loop=False),)


def test_animation_loops_by_default(project):
    found, _ = anims(project, 'frames = ["idle_0"]\nms = 400\n')
    assert found[0].loop is True


def test_animations_keep_file_order(project):
    body = 'frames = ["idle_0"]\nms = 400\n\n[anim.attack]\nframes = ["idle_1"]\nms = 80\n'
    found, problems = anims(project, body)
    assert problems == []
    assert [anim.name for anim in found] == ["idle", "attack"]


def test_animation_naming_a_missing_frame_is_e105(project):
    found, problems = anims(project, 'ms = 400\nframes = ["idle_0", "idle_7"]\n')

    assert positions(problems) == [(21, 1, "E105")]
    assert "'idle'" in problems[0].message and "'idle_7'" in problems[0].message
    assert found == ()


def test_animation_naming_a_failed_frame_is_dropped_silently(project):
    found, problems = anims(project, 'frames = ["idle_0", "bad"]\nms = 400\n')
    assert problems == []
    assert found == ()


@pytest.mark.parametrize(
    "body, line",
    [
        ("ms = 400\n", 19),
        ('frames = "idle_0"\nms = 400\n', 20),
        ("frames = []\nms = 400\n", 20),
        ("frames = [1]\nms = 400\n", 20),
        ('frames = ["idle_0"]\n', 19),
        ('frames = ["idle_0"]\nms = 0\n', 21),
        ('frames = ["idle_0"]\nms = 1.5\n', 21),
        ('frames = ["idle_0"]\nms = true\n', 21),
        ('frames = ["idle_0"]\nms = 400\nloop = 1\n', 22),
        ('frames = ["idle_0"]\nms = 400\nfps = 12\n', 22),
    ],
)
def test_wrongly_typed_or_unknown_animation_field_is_e001(project, body, line):
    found, problems = anims(project, body)

    assert positions(problems) == [(line, 1, "E001")]
    assert "'idle'" in problems[0].message
    assert found == ()


# --- variants -------------------------------------------------------------

# `[variants.red]` is on line 18.
VARIANT = (
    TINY
    + '\n[frames.flipped]\nfrom = "idle_0"\nrows = { 2 = "kb.." }\n'
    + '\n[anim.idle]\nframes = ["idle_0", "flipped"]\nms = 400\n'
    + "\n[variants.red]\n"
)


def test_variant_is_a_sprite_with_swapped_rows(project):
    sprites, problems = load_text(project, VARIANT + 'swap = { b = "r" }\n')

    assert problems == []
    base, red = sprites
    assert (base.id, base.variant_of) == ("hero", None)
    assert (red.id, red.variant_of) == ("hero_red", "hero")
    assert frame_rows(base, "idle_0") == (".kk.", "kwwk", "kbbk")
    assert frame_rows(red, "idle_0") == (".kk.", "kwwk", "krrk")
    assert frame_rows(red, "flipped") == (".kk.", "kwwk", "kr..")


def test_variant_keeps_everything_else_from_its_base(project):
    (base, red), _ = load_text(project, VARIANT + 'swap = { b = "r" }\n')

    assert red.anims == base.anims != ()
    assert (red.source, red.canvas, red.outline, red.grounded) == (base.source, base.canvas, True, True)
    assert [(f.name, f.line, f.literal) for f in red.frames] == [(f.name, f.line, f.literal) for f in base.frames]


def test_swap_is_applied_once_and_simultaneously(project):
    (_, red), problems = load_text(project, VARIANT + 'swap = { b = "w", w = "b" }\n')

    assert problems == []
    assert frame_rows(red, "idle_0") == (".kk.", "kbbk", "kwwk")


def test_each_variant_is_its_own_sprite(project):
    sprites, problems = load_text(project, VARIANT + 'swap = { b = "r" }\n\n[variants.pale]\nswap = { b = "w" }\n')

    assert problems == []
    assert [(sprite.id, sprite.variant_of) for sprite in sprites] == [
        ("hero", None),
        ("hero_pale", "hero"),
        ("hero_red", "hero"),
    ]


def test_swap_naming_keys_outside_the_palette_is_e107(project):
    sprites, problems = load_text(project, VARIANT + 'swap = { b = "R", Z = "r", w = "." }\n')

    assert positions(problems) == [(19, 1, "E107")] * 3
    assert [problem.message.split("swap key ")[1][:3] for problem in problems] == ["'R'", "'Z'", "'.'"]
    assert "'red'" in problems[0].message
    assert [sprite.id for sprite in sprites] == ["hero"]


@pytest.mark.parametrize(
    "body, line",
    [
        ("", 18),
        ('swap = "b"\n', 19),
        ("swap = { b = 1 }\n", 19),
        ('swap = { b = "r" }\ntint = "#ff0000"\n', 20),
    ],
)
def test_wrongly_typed_or_unknown_variant_field_is_e001(project, body, line):
    sprites, problems = load_text(project, VARIANT + body)

    assert positions(problems) == [(line, 1, "E001")]
    assert "'red'" in problems[0].message
    assert [sprite.id for sprite in sprites] == ["hero"]


def test_variant_of_a_file_with_no_good_frame_is_not_produced(project):
    sprites, problems = load_text(project, VARIANT.replace(".kk.", ".??.") + 'swap = { b = "r" }\n')
    assert sprites == []
    assert {problem.code for problem in problems} == {"E104"}


# --- bad input never raises -------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "",
        "canvas = 3\n",
        'canvas = "tiny"\nframes = 3\n',
        'canvas = "tiny"\nframes = []\n',
        'canvas = "tiny"\n[frames]\n',
        'canvas = "tiny"\n[frames]\nmain = ""\n',
        'canvas = "tiny"\n[frames]\nmain = "k"\n',
        'canvas = "tiny"\n[frames]\nmain = []\n',
        'canvas = "tiny"\n[frames]\nmain = """\n\n\n\n\n"""\n',
        'canvas = "tiny"\n[frames]\nmain = """\néééé\n\t\n \n"""\n',
        'canvas = "tiny"\nframes.main = """\n????\n????\n"""\n',
        'canvas = "tiny"\n[frames.main]\n',
        'canvas = "tiny"\n[frames.main]\nfrom = "main"\nrows = { "²" = 1 }\nshift = "x"\nflip = 0\n',
        'canvas = "tiny"\n[frames.main]\nfrom = []\nrows = []\nshift = [[], {}]\n',
        'canvas = "tiny"\n[[frames.main]]\nfrom = "x"\n',
        TINY + "anim = 3\nvariants = 3\n",
        TINY + "\n[anim]\nidle = 3\n\n[variants]\nred = 3\n",
        TINY + "\n[anim.idle]\nframes = [[]]\nms = []\nloop = []\n\n[variants.red]\nswap = []\n",
        TINY + '\n[variants.red]\nswap = { bb = "rr", "" = "" }\n',
        TINY + "\n[[anim]]\nx = 1\n\n[[variants]]\nx = 1\n",
    ],
)
def test_bad_input_is_reported_and_never_raises(project, text):
    sprites, problems = load_text(project, text)

    assert problems != []
    assert all(problem.code[0] == "E" and problem.line >= 1 and problem.col >= 1 for problem in problems)
    assert [sprite.variant_of for sprite in sprites] in ([], [None])
