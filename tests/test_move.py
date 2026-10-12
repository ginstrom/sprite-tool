"""`move` in a frame table, and the warning for pixels pushed off the canvas."""

import pytest

from conftest import write_project
from sprite_tool import check
from sprite_tool.model import format_problem
from sprite_tool.project import load
from sprite_tool.spritefile import load_all

CONFIG = """\
version = 1

[canvas.plain]
size = [4, 4]
anchor = [0, 0]

[canvas.tall]
size = [2, 32]
anchor = [0, 0]

[canvas.unit]
size = [5, 5]
anchor = [2, 5]
outline = ["k"]
grounded = true
"""

PALETTE = """\
[colors]
k = "#000000"
w = "#ffffff"
b = "#0000ff"
r = "#ff0000"
"""

# `[frames.next]` is on line 11, so the first line of a body is line 12.
BASE = '''\
canvas = "plain"

[frames]
idle_0 = """
kw..
bb..
r...
....
"""

[frames.next]
'''


@pytest.fixture
def project(tmp_path):
    loaded, problems = load(write_project(tmp_path / "sprites", CONFIG, PALETTE))
    assert problems == []
    return loaded


def load_text(project, text, name="hero.sprite.toml"):
    path = project.root / name
    path.write_text(text, encoding="utf-8")
    return load_all(project, [path])


def moved(project, body, text=BASE):
    """The rows of `next` and the problems, for a frame table with `body`."""
    sprites, problems = load_text(project, text + body)
    rows = next((frame.rows for sprite in sprites[:1] for frame in sprite.frames if frame.name == "next"), None)
    return rows, problems


def lines(project, problems):
    return [format_problem(problem, project.root) for problem in problems]


# --- what a move does ---------------------------------------------------------


def test_a_range_of_rows_moves_down_and_replaces_what_was_there(project):
    rows, problems = moved(project, 'from = "idle_0"\nmove = { rows = [0, 1], by = [0, 1] }\n')
    assert problems == []
    assert rows == ("....", "kw..", "bb..", "....")


def test_a_range_of_columns_moves_right(project):
    rows, problems = moved(project, 'from = "idle_0"\nmove = { cols = [0, 0], by = [2, 0] }\n')
    assert problems == []
    assert rows == (".wk.", ".bb.", "..r.", "....")


def test_a41_rows_and_cols_change_only_the_two_rectangles(project):
    rows, problems = moved(project, 'from = "idle_0"\nmove = { rows = [0, 0], cols = [0, 1], by = [2, 2] }\n')
    assert problems == []
    assert rows == ("....", "bb..", "r.kw", "....")


def test_a_move_writes_its_transparent_cells(project):
    """The blank bottom row replaces the row above it, and nothing is lost by that."""
    rows, problems = moved(project, 'from = "idle_0"\nmove = { rows = [3, 3], by = [0, -1] }\n')
    assert problems == []
    assert rows == ("kw..", "bb..", "....", "....")


def test_a41_two_moves_in_a_list_apply_in_order(project):
    body = 'from = "idle_0"\nmove = [{ rows = [0, 0], by = [0, 3] }, { rows = [3, 3], by = [1, 0] }]\n'
    rows, problems = moved(project, body)
    assert problems == []
    assert rows == ("....", "bb..", "r...", ".kw.")


def test_a40_a_breath_moves_everything_above_the_shins_a_pixel_lower(project):
    grid = ["k." if index % 2 == 0 else ".w" for index in range(29)] + ["bb", "rr", "kk"]
    text = 'canvas = "tall"\n\n[frames]\nidle_0 = """\n' + "\n".join(grid) + '\n"""\n\n[frames.next]\n'
    rows, problems = moved(project, 'from = "idle_0"\nmove = { rows = [0, 27], by = [0, 1] }\n', text)

    assert problems == []
    assert rows[0] == ".."
    assert rows[1:29] == tuple(grid[0:28])
    assert rows[29:] == tuple(grid[29:])


def test_move_then_rows_then_runs_then_shift_then_flip(project):
    # move:  .... / kw.. / r... / ....    rows:  rr.. / kw.. / r... / ....
    # runs:  rr.. / kwb. / r... / ....    shift [1, 0]:  .rr. / .kwb / .r.. / ....
    # flip:  .rr. / bwk. / ..r. / ....
    body = (
        'flip = true\nshift = [1, 0]\nruns = { 1 = [[2, "b"]] }\nrows = { 0 = "rr.." }\n'
        'move = { rows = [0, 0], by = [0, 1] }\nfrom = "idle_0"\n'
    )
    rows, problems = moved(project, body)
    assert problems == []
    assert rows == (".rr.", "bwk.", "..r.", "....")


def test_a_move_without_from_moves_a_blank_canvas(project):
    rows, problems = moved(project, "move = { rows = [0, 0], by = [0, 1] }\n")
    assert problems == []
    assert rows == ("....",) * 4


def test_with_auto_outline_the_interior_moves_and_the_outline_is_drawn_afterwards(project):
    text = 'canvas = "unit"\noutline = "auto"\ngrounded = false\n\n[frames]\nidle_0 = """\n.....\n..w..\n.....\n.....\n.....\n"""\n'
    text += '\n[frames.next]\nfrom = "idle_0"\nmove = { rows = [1, 1], by = [0, 2] }\n'
    rows, problems = moved(project, "", text)
    assert problems == []
    assert rows == (".....", ".....", "..k..", ".kwk.", "..k..")


# --- A42: problems ------------------------------------------------------------


@pytest.mark.parametrize(
    "move, code, message",
    [
        ("{ rows = [0, 9], by = [0, 1] }", "E105", "bad move rows [0, 9] (expected 0 to 3, first <= last)"),
        ("{ rows = [2, 1], by = [0, 1] }", "E105", "bad move rows [2, 1] (expected 0 to 3, first <= last)"),
        ("{ cols = [-1, 2], by = [0, 1] }", "E105", "bad move cols [-1, 2] (expected 0 to 3, first <= last)"),
        ("{ by = [0, 1] }", "E001", "move needs rows or cols (use shift to move the whole frame)"),
        ("{ rows = [0, 1] }", "E001", "move needs by = [dx, dy], two integers"),
        ("{ rows = [0, 1], by = [0, 1.5] }", "E001", "move needs by = [dx, dy], two integers"),
        ('{ rows = "top", by = [0, 1] }', "E001", "move rows must be [first, last], two integers"),
        ("{ cols = [1], by = [0, 1] }", "E001", "move cols must be [first, last], two integers"),
        ("{ rows = [0, 1], by = [0, 1], up = 1 }", "E001", "move has unknown key 'up'"),
        ("3", "E001", "move must be a table or a list of tables"),
        ("[[0, 1]]", "E001", "move must be a table or a list of tables"),
    ],
)
def test_a42_a_bad_move_is_one_line_naming_the_frame(project, move, code, message):
    rows, problems = moved(project, f'from = "idle_0"\nmove = {move}\n')
    assert rows is None
    assert lines(project, problems) == [f"hero.sprite.toml:13:1: {code} frame 'next': {message}"]


def test_a_frame_table_with_only_a_bad_field_still_says_what_it_needs(project):
    _, problems = moved(project, "flip = true\n")
    assert [problem.message for problem in problems] == ["frame 'next': needs from, rows, runs or move"]


# --- A43: pixels pushed off the canvas ----------------------------------------


def test_a43_a_shift_that_loses_pixels_is_w006_with_the_count(project):
    text = BASE.replace("r...\n....", "r...\nkk..")
    rows, problems = moved(project, 'from = "idle_0"\nshift = [0, 1]\n', text)
    assert rows == ("....", "kw..", "bb..", "r...")
    assert lines(project, problems) == [
        "hero.sprite.toml:11:1: W006 frame 'next': shift [0, 1] pushes 2 drawn pixels off the canvas"
    ]


def test_a43_the_same_shift_with_an_empty_bottom_row_loses_nothing(project):
    rows, problems = moved(project, 'from = "idle_0"\nshift = [0, 1]\n')
    assert rows == ("....", "kw..", "bb..", "r...")
    assert problems == []


def test_a_move_that_loses_pixels_is_w006_naming_its_by(project):
    rows, problems = moved(project, 'from = "idle_0"\nmove = { cols = [0, 1], by = [-1, 0] }\n')
    assert rows == ("w...", "b...", "....", "....")
    assert lines(project, problems) == [
        "hero.sprite.toml:11:1: W006 frame 'next': move by [-1, 0] pushes 3 drawn pixels off the canvas"
    ]


def test_one_lost_pixel_is_singular(project):
    _, problems = moved(project, 'from = "idle_0"\nshift = [0, -1]\n')
    assert [problem.message for problem in problems] == [
        "frame 'next': shift [0, -1] pushes 2 drawn pixels off the canvas"
    ]
    _, problems = moved(project, 'from = "idle_0"\nmove = { rows = [2, 2], by = [-1, 0] }\n')
    assert [problem.message for problem in problems] == [
        "frame 'next': move by [-1, 0] pushes 1 drawn pixel off the canvas"
    ]


def test_w006_is_given_once_for_a_sprite_with_variants(project):
    body = 'from = "idle_0"\nshift = [0, -1]\n\n[variants.red]\nswap = { b = "r" }\n\n[variants.pale]\nswap = { b = "w" }\n'
    sprites, problems = load_text(project, BASE + body)
    assert [sprite.id for sprite in sprites] == ["hero", "hero_pale", "hero_red"]
    assert [problem.code for problem in problems + check.run(project, sprites)] == ["W006"]


# --- origins: which outline faults a derived frame only carries over ----------

# A `w` on the top of the shape, with nothing above it.
FAULTY = '''\
canvas = "unit"

[frames]
idle_0 = """
.....
.kwk.
.kkk.
.kkk.
.kkk.
"""
'''

CLEAN = FAULTY.replace(".....\n.kwk.\n.kkk.", ".kkk.\n.kwk.\n.kwk.")


def checked(project, text):
    sprites, problems = load_text(project, text)
    return sorted(format_problem(problem, project.root) for problem in problems + check.run(project, sprites))


def test_a_fault_of_the_parent_is_not_reported_again_where_it_was_moved_to(project):
    text = FAULTY + '\n[frames.idle_1]\nfrom = "idle_0"\nmove = { rows = [1, 1], by = [0, 1] }\n'
    assert checked(project, text) == [
        "hero.sprite.toml:6:3: E201 frame 'idle_0': 'w' touches transparency, expected outline key 'k'"
    ]


def test_a_fault_a_move_creates_is_reported(project):
    """The top of the outline leaves the canvas, and the `w` under it is bare."""
    text = CLEAN + '\n[frames.idle_1]\nfrom = "idle_0"\nmove = { rows = [0, 0], by = [0, -1] }\n'
    assert checked(project, text) == [
        "hero.sprite.toml:12:1: E201 frame 'idle_1' row 1, col 2: 'w' touches transparency, expected outline key 'k'",
        "hero.sprite.toml:12:1: W006 frame 'idle_1': move by [0, -1] pushes 3 drawn pixels off the canvas",
    ]


def test_a_position_that_rows_rewrote_keeps_its_origin(project):
    """As before `origins`: the parent's fault at a position is not reported
    again in a frame that rewrote that position."""
    text = FAULTY + '\n[frames.idle_1]\nfrom = "idle_0"\nrows = { 1 = ".kbk." }\n'
    assert len(checked(project, text)) == 1
