"""`mirror` in a frame table: part of a frame reversed left to right, in place."""

import pytest

from conftest import write_project
from sprite_tool import check
from sprite_tool.model import format_problem
from sprite_tool.project import load
from sprite_tool.spritefile import load_all

CONFIG = """\
version = 1

[canvas.plain]
size = [9, 8]
anchor = [0, 0]

[canvas.unit]
size = [5, 5]
anchor = [2, 5]
outline = ["k"]
"""

PALETTE = """\
[colors]
k = "#000000"
a = "#ff0000"
b = "#00ff00"
c = "#0000ff"
d = "#ffffff"
"""

ROWS = ["........."] * 5 + ["..ab.cd.."] + ["..ab.cd.."] + ["abcdabcda"]
# `[frames.next]` is on line 19, so its body starts on line 21, after `from`.
BASE = (
    'canvas = "plain"\n\n[points]\ninside = [3, 5]\nbelow = [3, 6]\n\n[frames]\nidle_0 = """\n'
    + "\n".join(ROWS)
    + '\n"""\n\n[frames.next]\nfrom = "idle_0"\n'
)


@pytest.fixture
def project(tmp_path):
    loaded, problems = load(write_project(tmp_path / "sprites", CONFIG, PALETTE))
    assert problems == []
    return loaded


def load_text(project, text):
    path = project.root / "hero.sprite.toml"
    path.write_text(text, encoding="utf-8")
    sprites, problems = load_all(project, [path])
    return sprites, [format_problem(problem, project.root) for problem in problems]


def mirrored(project, body):
    """The frame `next`, or None, and the problems, for a frame table with `body`."""
    sprites, problems = load_text(project, BASE + body)
    frame = next((frame for sprite in sprites[:1] for frame in sprite.frames if frame.name == "next"), None)
    return frame, problems


# --- A70: what a mirror does ---------------------------------------------------


def test_a70_a_rectangle_is_reversed_in_place(project):
    frame, problems = mirrored(project, "mirror = { rows = [5, 5], cols = [2, 6] }\n")
    assert problems == []
    assert frame.rows == tuple(ROWS[:5]) + ("..dc.ba..", "..ab.cd..", "abcdabcda")


def test_a70_without_rows_every_row_is_mirrored_in_those_columns(project):
    frame, _ = mirrored(project, "mirror = { cols = [2, 6] }\n")
    assert frame.rows == tuple(ROWS[:5]) + ("..dc.ba..", "..dc.ba..", "abcbadcda")


def test_a70_without_cols_the_whole_width_of_those_rows(project):
    frame, _ = mirrored(project, "mirror = { rows = [6, 7] }\n")
    assert frame.rows == tuple(ROWS[:6]) + ("..dc.ba..", "adcbadcba")


def test_a70_two_mirrors_apply_in_order(project):
    frame, _ = mirrored(project, "mirror = [{ rows = [7, 7], cols = [0, 3] }, { rows = [7, 7], cols = [2, 8] }]\n")
    # dcba abcda, then columns 2 to 8 of that reversed.
    assert frame.rows[7] == "dcadcbaab"


def test_mirror_runs_after_move_and_before_rows_and_runs(project):
    body = 'move = { rows = [5, 5], cols = [2, 3], by = [-2, 0] }\nmirror = { rows = [5, 5] }\nruns = { 5 = [[0, "c"]] }\n'
    frame, _ = mirrored(project, body)
    # Moved to "ab...cd..", mirrored to "..dc...ba", then patched at column 0.
    assert frame.rows[5] == "c.dc...ba"


def test_a_frame_of_only_a_mirror_needs_no_from(project):
    sprites, problems = load_text(
        project, 'canvas = "plain"\n\n[frames]\nidle_0 = """\n' + "\n".join(ROWS) + '\n"""\n\n[frames.next]\nmirror = { rows = [0, 0] }\n'
    )
    assert problems == []
    assert sprites[0].frames[1].rows == ("." * 9,) * 8


# --- A71: points and origins ----------------------------------------------------


def test_a71_a_point_inside_the_rectangle_is_mirrored_and_one_outside_stays(project):
    frame, _ = mirrored(project, "mirror = { rows = [5, 5], cols = [2, 6] }\n")
    assert dict(frame.points) == {"below": (3, 6), "inside": (5, 5)}


def test_a71_origins_name_the_parent_pixel_each_mirrored_pixel_came_from(project):
    frame, _ = mirrored(project, "mirror = { rows = [5, 5], cols = [2, 6] }\n")
    assert [frame.origins[5][c] for c in range(9)] == [(5, 0), (5, 1), (5, 6), (5, 5), (5, 4), (5, 3), (5, 2), (5, 7), (5, 8)]
    assert frame.origins[6] == tuple((6, c) for c in range(9))


def test_a71_an_inherited_outline_fault_is_reported_at_the_parent_only(project):
    """The `a` at row 1, col 1 of `idle_0` touches transparency. Mirrored, it
    is at col 3 of `next`, where the fault is the same one and is not reported."""
    text = (
        'canvas = "unit"\n\n[frames]\nidle_0 = """\n.kkk.\n.akkk\nkkkkk\nkkkkk\n.kkk.\n"""\n\n'
        '[frames.next]\nfrom = "idle_0"\nmirror = { rows = [1, 1], cols = [0, 4] }\n'
    )
    path = project.root / "unit.sprite.toml"
    path.write_text(text, encoding="utf-8")
    sprites, problems = load_all(project, [path])
    assert problems == []
    assert sprites[0].frames[1].rows[1] == "kkka."
    found = [format_problem(problem, project.root) for problem in check.run(project, sprites)]
    assert found == ["unit.sprite.toml:6:2: E201 frame 'idle_0': 'a' touches transparency, expected outline key 'k'"]


# --- A72: E105 ------------------------------------------------------------------


@pytest.mark.parametrize(
    ("body", "message"),
    [
        ("mirror = { rows = [5, 8] }", "bad mirror rows [5, 8] (expected 0 to 7, first <= last)"),
        ("mirror = { cols = [3, 9] }", "bad mirror cols [3, 9] (expected 0 to 8, first <= last)"),
        ("mirror = { cols = [4, 2] }", "bad mirror cols [4, 2] (expected 0 to 8, first <= last)"),
        ("mirror = { rows = [-1, 2] }", "bad mirror rows [-1, 2] (expected 0 to 7, first <= last)"),
        ("mirror = {}", "mirror needs rows or cols (use flip to mirror the whole frame)"),
        ("mirror = { rows = [1, 2], axis = 3 }", "mirror has unknown key 'axis'"),
        ("mirror = { rows = [1, 2], by = [1, 0] }", "mirror has no by"),
    ],
)
def test_a72_a_bad_mirror_is_one_e105_naming_the_frame(project, body, message):
    frame, problems = mirrored(project, body + "\n")
    assert problems == [f"hero.sprite.toml:21:1: E105 frame 'next': {message}"]
    assert frame is None


def test_a_mirror_that_is_not_a_table_is_e001(project):
    _, problems = mirrored(project, "mirror = 3\n")
    assert problems == ["hero.sprite.toml:21:1: E001 frame 'next': mirror must be a table or a list of tables"]
