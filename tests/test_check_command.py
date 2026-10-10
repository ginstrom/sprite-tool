from pathlib import Path

import pytest
from PIL import Image

from conftest import write_project
from sprite_tool import cli
from sprite_tool.cli import main
from sprite_tool.model import Problem

# `unit` is 5 wide and 4 high so that a width/height mix-up shows.
CONFIG = """\
version = 1

[canvas.unit]
size = [5, 4]
anchor = [2, 4]
outline = ["k"]
grounded = true

[canvas.big]
size = [32, 32]
anchor = [16, 32]
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

RED = '\n[variants.red]\nswap = { b = "r" }\n'
NO_OUTLINE = HERO.replace("kbbbk", "kbbbw")
SPARE_FRAME = HERO + 'spare = """\n.kkk.\nkwwwk\nkbbbk\n.kkk.\n"""\n\n[anim.idle]\nframes = ["idle_0"]\nms = 100\n'

# A3: a long row and an unknown key in one grid, a missing outline pixel in the next.
THREE_PROBLEMS = '''\
canvas = "unit"

[frames]
idle_0 = """
.kkk.
kwxwkk
kbbbk
.kkk.
"""
idle_1 = """
.kkk.
kwwwk
kbbbw
.kkk.
"""
'''


@pytest.fixture
def root(tmp_path):
    return write_project(tmp_path / "sprites", CONFIG, PALETTE)


def write(root: Path, name: str, text: str) -> Path:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def run(capsys, root: Path, *argv: str) -> tuple[int, list[str], str]:
    """Run `sprite check` on the project; return exit code, stdout lines and stderr."""
    code = main(["check", *argv, "--project", str(root)])
    captured = capsys.readouterr()
    return code, captured.out.splitlines(), captured.err


# --- whole project ------------------------------------------------------------


def test_clean_project_prints_one_summary_line(root, capsys):
    write(root, "units/hero.sprite.toml", HERO + RED)
    write(root, "orc.sprite.toml", SPARE_FRAME.replace("spare", "idle_1").replace('["idle_0"]', '["idle_0", "idle_1"]'))
    assert run(capsys, root) == (0, ["ok: 3 sprites, 4 frames"], "")


def test_summary_counts_are_singular_for_one(root, capsys):
    write(root, "hero.sprite.toml", HERO)
    assert run(capsys, root) == (0, ["ok: 1 sprite, 1 frame"], "")


def test_project_without_sprites_is_ok(root, capsys):
    assert run(capsys, root) == (0, ["ok: 0 sprites, 0 frames"], "")


def test_a3_three_problems_with_positions_then_the_summary(root, capsys):
    write(root, "units/warrior.sprite.toml", THREE_PROBLEMS)
    assert run(capsys, root) == (
        1,
        [
            "units/warrior.sprite.toml:6:3: E104 unknown palette key 'x'",
            "units/warrior.sprite.toml:6:6: E103 frame 'idle_0' row 1: 6 wide, expected 5",
            "units/warrior.sprite.toml:13:5: E201 frame 'idle_1': 'w' touches transparency, expected outline key 'k'",
            "3 errors, 0 warnings in 1 file",
        ],
        "",
    )


def test_a14_sixteen_wide_row_in_a_32x32_sprite_is_e103(root, capsys):
    rows = ["k" * 32] * 32
    rows[5] = "k" * 16
    write(root, "hero.sprite.toml", 'canvas = "big"\n\n[frames]\nmain = """\n' + "\n".join(rows) + '\n"""\n')
    assert run(capsys, root) == (
        1,
        ["hero.sprite.toml:10:17: E103 frame 'main' row 5: 16 wide, expected 32", "1 error, 0 warnings in 1 file"],
        "",
    )


def test_problems_are_sorted_by_path_line_and_column(root, capsys):
    write(root, "b.sprite.toml", HERO.replace(".kkk.\nkwwwk\nkbbbk", ".kkw.\nwwwwk\nkbbbw"))
    write(root, "a/z.sprite.toml", NO_OUTLINE)
    code, out, _ = run(capsys, root)
    assert code == 1
    assert [line.split(": ")[0] for line in out] == [
        "a/z.sprite.toml:7:5",
        "b.sprite.toml:5:4",
        "b.sprite.toml:6:1",
        "b.sprite.toml:7:5",
        "4 errors, 0 warnings in 2 files",
    ]


def test_warnings_are_printed_before_the_ok_line_and_exit_0(tmp_path, capsys):
    root = write_project(tmp_path, CONFIG, PALETTE + 'x = "#0000ff"\n')
    write(root, "hero.sprite.toml", SPARE_FRAME)
    assert run(capsys, root) == (
        0,
        [
            "hero.sprite.toml:11:1: W002 frames not used by any animation: spare",
            "palette.toml: W001 palette keys 'b' and 'x' share the colour #0000ff",
            "ok: 1 sprite, 2 frames",
        ],
        "",
    )


def test_summary_counts_errors_warnings_and_files(root, capsys):
    write(root, "hero.sprite.toml", SPARE_FRAME)
    write(root, "orc.sprite.toml", NO_OUTLINE)
    code, out, _ = run(capsys, root)
    assert code == 1
    assert out[-1] == "1 error, 1 warning in 2 files"


def test_duplicate_ids_fail_the_check(root, capsys):
    write(root, "units/hero.sprite.toml", HERO)
    write(root, "items/hero.sprite.toml", HERO)
    assert run(capsys, root) == (
        1,
        [
            "items/hero.sprite.toml: E003 duplicate sprite id 'hero', also in units/hero.sprite.toml",
            "units/hero.sprite.toml: E003 duplicate sprite id 'hero', also in items/hero.sprite.toml",
            "2 errors, 0 warnings in 2 files",
        ],
        "",
    )


def test_bad_palette_exits_1_and_sprites_are_not_checked(tmp_path, capsys):
    root = write_project(tmp_path, CONFIG, PALETTE + 'ab = "#000000"\nq = "red"\n')
    write(root, "hero.sprite.toml", THREE_PROBLEMS)
    code, out, err = run(capsys, root)
    assert (code, err) == (1, "")
    assert [line.split(" ")[:2] for line in out[:-1]] == [["palette.toml:6:1:", "E002"], ["palette.toml:7:1:", "E002"]]
    assert out[-1] == "2 errors, 0 warnings in 1 file"


def test_config_error_exits_2(tmp_path, capsys):
    root = write_project(tmp_path, CONFIG.replace("version = 1", "version = 2"), PALETTE)
    code, out, err = run(capsys, root)
    assert (code, out) == (2, [])
    assert err.startswith("error: ")


# --- given paths --------------------------------------------------------------


def test_given_file_reports_only_its_own_problems(root, capsys):
    write(root, "orc.sprite.toml", NO_OUTLINE)
    hero = write(root, "units/hero.sprite.toml", HERO + RED)
    assert run(capsys, root, str(hero)) == (0, ["ok: 2 sprites, 2 frames"], "")

    orc = root / "orc.sprite.toml"
    code, out, _ = run(capsys, root, str(orc))
    assert code == 1
    assert [line.split(": ")[0] for line in out] == ["orc.sprite.toml:7:5", "1 error, 0 warnings in 1 file"]


def test_given_file_is_resolved_against_the_current_directory(root, capsys, monkeypatch):
    write(root, "units/hero.sprite.toml", NO_OUTLINE)
    monkeypatch.chdir(root / "units")
    code = main(["check", "hero.sprite.toml"])
    assert code == 1
    assert capsys.readouterr().out.startswith("units/hero.sprite.toml:7:5: E201")


def test_given_file_still_finds_duplicate_ids_in_other_files(root, capsys):
    hero = write(root, "units/hero.sprite.toml", HERO)
    write(root, "items/hero.sprite.toml", HERO)
    assert run(capsys, root, str(hero)) == (
        1,
        [
            "units/hero.sprite.toml: E003 duplicate sprite id 'hero', also in items/hero.sprite.toml",
            "1 error, 0 warnings in 1 file",
        ],
        "",
    )


def test_given_file_does_not_hide_a_bad_palette(tmp_path, capsys):
    root = write_project(tmp_path, CONFIG, PALETTE + 'ab = "#000000"\n')
    hero = write(root, "hero.sprite.toml", HERO)
    code, out, _ = run(capsys, root, str(hero))
    assert code == 1
    assert out[0].startswith("palette.toml:6:1: E002")


def test_given_file_leaves_out_palette_warnings(tmp_path, capsys):
    root = write_project(tmp_path, CONFIG, PALETTE + 'x = "#0000ff"\n')
    hero = write(root, "hero.sprite.toml", HERO)
    assert run(capsys, root, str(hero)) == (0, ["ok: 1 sprite, 1 frame"], "")


def test_given_file_that_does_not_exist_is_a_problem_line(root, capsys):
    code, out, err = run(capsys, root, str(root / "nope.sprite.toml"))
    assert (code, err) == (1, "")
    assert out[0].startswith("nope.sprite.toml: E001 cannot read file")
    assert out[1] == "1 error, 0 warnings in 1 file"


def test_given_path_that_is_neither_a_sprite_file_nor_a_png_exits_2(root, capsys):
    code, out, err = run(capsys, root, str(write(root, "notes.txt", "hello")))
    assert (code, out) == (2, [])
    assert err.startswith("error: ") and "notes.txt" in err


# --- PNG paths ----------------------------------------------------------------


def write_png(path: Path, size=(5, 4), **pixels) -> Path:
    """Write a transparent RGBA PNG; `pixels` maps names like `x3y1` to colours."""
    image = Image.new("RGBA", size, (0, 0, 0, 0))
    for name, colour in pixels.items():
        x, y = name[1:].split("y")
        image.putpixel((int(x), int(y)), colour)
    image.save(path)
    return path


def test_a11_png_reports_size_mismatch_and_off_palette_pixels(root, capsys):
    png = write_png(root / "some.png", size=(6, 4), x3y1=(255, 0, 255, 255), x0y2=(0, 0, 255, 255))
    assert run(capsys, root, str(png), "--canvas", "unit") == (
        1,
        [
            "some.png: E301 image is 6x4, canvas 'unit' is 5x4",
            "some.png:3,1: E302 colour #ff00ff is not in the palette",
            "2 errors, 0 warnings in 1 file",
        ],
        "",
    )


def test_clean_png_is_counted_in_the_ok_line(root, capsys):
    write(root, "orc.sprite.toml", NO_OUTLINE)
    png = write_png(root / "some.png", x0y0=(0, 0, 0, 255))
    assert run(capsys, root, str(png), "--canvas", "unit") == (0, ["ok: 0 sprites, 0 frames, 1 image"], "")


def test_png_and_sprite_file_can_be_checked_together(root, capsys):
    hero = write(root, "hero.sprite.toml", HERO)
    png = write_png(root / "some.png")
    other = write_png(root / "other.png")
    assert run(capsys, root, str(png), str(hero), str(other), "--canvas", "unit") == (
        0,
        ["ok: 1 sprite, 1 frame, 2 images"],
        "",
    )


def test_png_without_canvas_exits_2(root, capsys):
    png = write_png(root / "some.png")
    code, out, err = run(capsys, root, str(png))
    assert (code, out) == (2, [])
    assert err == "error: --canvas <class> is required to check a PNG\n"


def test_png_with_an_unknown_canvas_exits_2(root, capsys):
    png = write_png(root / "some.png")
    code, out, err = run(capsys, root, str(png), "--canvas", "boss")
    assert (code, out) == (2, [])
    assert err == "error: unknown canvas class 'boss' (expected one of unit, big)\n"


# --- helpers for later commands -----------------------------------------------


def parse(root: Path, *argv: str):
    return cli.build_parser().parse_args([*argv, "--project", str(root)])


def test_load_checked_returns_project_sprites_and_sorted_problems(root):
    write(root, "b.sprite.toml", NO_OUTLINE)
    write(root, "a.sprite.toml", THREE_PROBLEMS)
    project, sprites, problems = cli.load_checked(parse(root, "build"))
    assert project.root == root
    assert [sprite.id for sprite in sprites] == ["a", "b"]
    assert [(problem.path.name, problem.line, problem.code) for problem in problems] == [
        ("a.sprite.toml", 6, "E104"),
        ("a.sprite.toml", 6, "E103"),
        ("a.sprite.toml", 13, "E201"),
        ("b.sprite.toml", 7, "E201"),
    ]


def test_load_checked_with_a_bad_palette_returns_no_sprites(tmp_path):
    root = write_project(tmp_path, CONFIG, PALETTE + 'ab = "#000000"\n')
    write(root, "hero.sprite.toml", THREE_PROBLEMS)
    _, sprites, problems = cli.load_checked(parse(root, "build"))
    assert sprites == []
    assert [problem.code for problem in problems] == ["E002"]


def test_report_prints_problems_and_the_failure_summary_and_returns_the_error_count(tmp_path, capsys):
    problems = [
        Problem(tmp_path / "b.sprite.toml", 3, 1, "E106", "second"),
        Problem(tmp_path / "a.sprite.toml", 9, 2, "W002", "first"),
        Problem(tmp_path / "b.sprite.toml", 0, 0, "E003", "top"),
    ]
    assert cli.report(problems, tmp_path) == 2
    assert capsys.readouterr().out.splitlines() == [
        "a.sprite.toml:9:2: W002 first",
        "b.sprite.toml: E003 top",
        "b.sprite.toml:3:1: E106 second",
        "2 errors, 1 warning in 2 files",
    ]


def test_report_prints_warnings_without_a_summary_when_there_are_no_errors(tmp_path, capsys):
    assert cli.report([Problem(tmp_path / "a.sprite.toml", 9, 2, "W002", "first")], tmp_path) == 0
    assert capsys.readouterr().out == "a.sprite.toml:9:2: W002 first\n"


def test_report_prints_nothing_for_no_problems(tmp_path, capsys):
    assert cli.report([], tmp_path) == 0
    assert capsys.readouterr().out == ""
