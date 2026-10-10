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
