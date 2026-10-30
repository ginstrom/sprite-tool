import shutil
from dataclasses import replace
from pathlib import Path

import pytest

from conftest import make_frame, make_sprite
from sprite_tool import project as project_module
from sprite_tool import spritefile
from sprite_tool.cli import main
from sprite_tool.textview import frame_text

DEMO = Path(__file__).parent.parent / "examples" / "demo"


@pytest.fixture
def demo(tmp_path: Path, monkeypatch) -> Path:
    """A copy of the demo project, as the current directory."""
    root = tmp_path / "demo"
    shutil.copytree(DEMO, root, ignore=shutil.ignore_patterns("out", ".preview"))
    monkeypatch.chdir(root)
    return root


@pytest.fixture(scope="module")
def loaded():
    """The demo's sprites by id. Read only."""
    project, problems = project_module.load(DEMO)
    sprites, more = spritefile.load_all(project)
    assert not problems and not more
    return {sprite.id: sprite for sprite in sprites}


def files(root: Path) -> dict[str, bytes]:
    return {path.relative_to(root).as_posix(): path.read_bytes() for path in sorted(root.rglob("*")) if path.is_file()}


def show(*argv: str) -> int:
    return main(["show", *argv])


def blocks(out: str) -> list[list[str]]:
    """The blocks of `show` output, each as its lines."""
    return [block.splitlines() for block in out.removesuffix("\n").split("\n\n")]


# --- frame_text -----------------------------------------------------------------


def test_a_small_frame_has_a_header_one_ruler_line_and_numbered_rows():
    sprite = make_sprite("gem", make_frame("main", ".kkkk.", "kbwwbk", "kbBBbk", ".kkkk."))
    assert frame_text(sprite, sprite.frames[0]) == (
        "gem main  tiny 6x4\n"
        "   012345\n"
        "0  .kkkk.\n"
        "1  kbwwbk\n"
        "2  kbBBbk\n"
        "3  .kkkk.\n"
    )


def test_a_canvas_exactly_ten_wide_has_no_tens_line():
    sprite = make_sprite("bar", make_frame("main", "k" * 10))
    assert frame_text(sprite, sprite.frames[0]).splitlines() == ["bar main  tiny 10x1", "   0123456789", "0  kkkkkkkkkk"]


def test_a_wider_canvas_has_the_tens_digits_above_the_units_from_column_10():
    sprite = make_sprite("bar", make_frame("main", "k" * 21))
    assert frame_text(sprite, sprite.frames[0]).splitlines() == [
        "bar main  tiny 21x1",
        "             11111111112",
        "   012345678901234567890",
        "0  kkkkkkkkkkkkkkkkkkkkk",
    ]


def test_row_numbers_are_right_aligned_to_the_widest():
    rows = ["k."] * 32
    sprite = make_sprite("tall", make_frame("main", *rows))
    lines = frame_text(sprite, sprite.frames[0]).splitlines()
    assert lines[1] == "    01"
    assert lines[2] == " 0  k."
    assert lines[11] == " 9  k."
    assert lines[12] == "10  k."
    assert lines[-1] == "31  k."
    assert len(lines) == 34


def test_the_rows_are_the_frames_rows_and_no_line_has_trailing_whitespace(loaded):
    for sprite in loaded.values():
        for frame in sprite.frames:
            text = frame_text(sprite, frame)
            lines = text.splitlines()
            assert text.endswith("\n") and all(line == line.rstrip() for line in lines)
            height = len(frame.rows)
            assert tuple(line.split()[1] for line in lines[3 : 3 + height]) == frame.rows
            assert lines[3 + height :] == [f"point {name} {col},{row}" for name, (col, row) in frame.points]
            assert lines[0] == f"{sprite.id} {frame.name}  {sprite.canvas.name} {sprite.canvas.width}x{sprite.canvas.height}"


def test_the_text_view_does_not_import_image_code():
    import subprocess
    import sys

    code = "import sys, sprite_tool.textview; print(sorted(m for m in sys.modules if m.startswith(('PIL', 'sprite_tool.preview'))))"
    assert subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True).stdout == "[]\n"


# --- show on the demo -----------------------------------------------------------


def test_a28_show_prints_the_resolved_default_frame_and_writes_nothing(demo, capsys, loaded):
    before = files(demo)
    assert show("slime") == 0
    captured = capsys.readouterr()
    assert captured.err == ""
    lines = captured.out.splitlines()
    assert lines[0] == "slime main  unit 32x32"
    assert lines[1] == "              1111111111222222222233"
    assert lines[2] == "    01234567890123456789012345678901"
    assert len(lines) == 3 + 32
    assert [line[:2] for line in lines[3:]] == [f"{row:>2}" for row in range(32)]
    assert tuple(line[4:] for line in lines[3:]) == loaded["slime"].frames[0].rows
    # Outline the tool drew: the source has nothing on row 16, and no `k` anywhere.
    assert "k" not in (demo / "units" / "slime.sprite.toml").read_text(encoding="utf-8").split("[frames", 1)[1]
    assert lines[3 + 16] == "16  ...........kk......kk..........."
    assert files(demo) == before
    assert not (demo / ".preview").exists()


def test_a29_a_grid_and_the_same_picture_as_runs_print_the_same(demo, capsys):
    (demo / "as_grid.sprite.toml").write_text(
        'canvas = "tile"\n\n[frames]\nmain = """\n' + ("." * 16 + "\n") * 5 + "....kwwk....o...\n" + ("." * 16 + "\n") * 10 + '"""\n',
        encoding="utf-8",
    )
    (demo / "as_runs.sprite.toml").write_text(
        'canvas = "tile"\n\n[frames.main.runs]\n5 = [[4, "kwwk"], [12, "o"]]\n', encoding="utf-8"
    )
    assert show("as_grid") == 0
    as_grid = capsys.readouterr().out
    assert show("as_runs") == 0
    as_runs = capsys.readouterr().out
    assert as_grid.startswith("as_grid main  tile 16x16\n")
    assert as_runs == as_grid.replace("as_grid", "as_runs", 1)
    assert " 5  ....kwwk....o...\n" in as_grid


def test_a30_only_the_default_frame_is_shown_unless_told(demo, capsys, loaded):
    warrior = {frame.name: frame.rows for frame in loaded["warrior"].frames}
    assert show("warrior") == 0
    (only,) = blocks(capsys.readouterr().out)
    assert only[0] == "warrior idle_0  unit 32x32"
    assert tuple(line[4:] for line in only[3:-1]) == warrior["idle_0"]
    assert only[-1] == "point grip 25,18"

    assert show("warrior", "--frame", "idle_1") == 0
    (only,) = blocks(capsys.readouterr().out)
    assert only[0] == "warrior idle_1  unit 32x32"
    assert tuple(line[4:] for line in only[3:-1]) == warrior["idle_1"]
    assert warrior["idle_1"] != warrior["idle_0"]


def test_a30_several_frames_and_all(demo, capsys):
    assert show("warrior", "--frame", "idle_1", "--frame", "idle_0", "--frame", "idle_1") == 0
    out = capsys.readouterr().out
    assert [block[0].split()[1] for block in blocks(out)] == ["idle_1", "idle_0"]
    # One blank line between blocks, none at the end.
    assert out.count("\n\n") == 1 and out.endswith("point grip 25,18\n") and not out.endswith("\n\n")

    assert show("warrior", "--all") == 0
    assert [block[0].split("  ")[0] for block in blocks(capsys.readouterr().out)] == ["warrior idle_0", "warrior idle_1"]


def test_a30_a_variant_shows_its_swapped_keys_and_the_base_does_not(demo, capsys):
    assert show("warrior_red") == 0
    (red,) = blocks(capsys.readouterr().out)
    assert show("warrior") == 0
    (base,) = blocks(capsys.readouterr().out)
    assert red[0] == "warrior_red idle_0  unit 32x32"
    assert red[3 + 14] == "14  .......kkkrRRRrrcrrrrrkkrwk....."
    assert base[3 + 14] == "14  .......kkkbBBBbbcbbbbbkkbwk....."


def test_several_ids_are_shown_in_the_order_given_with_repeats_dropped(demo, capsys):
    assert show("slime", "goblin", "slime") == 0
    assert [block[0].split()[0] for block in blocks(capsys.readouterr().out)] == ["slime", "goblin"]


def test_a_sprite_that_is_not_built_is_shown(demo, capsys):
    assert "build = false" in (demo / "units" / "sample_slime.sprite.toml").read_text(encoding="utf-8")
    assert show("sample_slime") == 0
    assert capsys.readouterr().out.startswith("sample_slime ")


def test_a_blank_sprite_is_a_grid_of_dots_and_its_warning_is_not_printed(demo, capsys):
    assert main(["new", "gem", "--canvas", "tile", "--runs"]) == 0
    capsys.readouterr()
    assert show("gem") == 0
    lines = capsys.readouterr().out.splitlines()
    assert lines[0] == "gem main  tile 16x16"
    assert [line[4:] for line in lines[3:]] == ["." * 16] * 16


def test_show_from_outside_the_project_takes_project(demo, capsys, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert show("slime", "--project", str(demo)) == 0
    assert capsys.readouterr().out.startswith("slime main  unit 32x32\n")


# --- usage errors ---------------------------------------------------------------


def test_a31_an_unknown_id_names_the_known_ones(demo, capsys):
    assert show("slime", "nosuch") == 2
    captured = capsys.readouterr()
    known = "(sprites: arrow, goblin, ground_light, orb, sample_slime, slime, spark, warrior, warrior_red)"
    assert (captured.out, captured.err) == ("", f"error: unknown sprite id 'nosuch' {known}\n")


def test_a31_an_unknown_frame_names_the_sprites_frames(demo, capsys):
    assert show("warrior", "--frame", "nosuch") == 2
    captured = capsys.readouterr()
    assert (captured.out, captured.err) == ("", "error: sprite 'warrior' has no frame 'nosuch' (frames: idle_0, idle_1)\n")


def test_a_frame_must_exist_in_every_id_given(demo, capsys):
    assert show("warrior", "slime", "--frame", "idle_1") == 2
    captured = capsys.readouterr()
    assert (captured.out, captured.err) == ("", "error: sprite 'slime' has no frame 'idle_1' (frames: main)\n")


def test_frame_with_all_is_a_usage_error(demo, capsys):
    assert show("warrior", "--frame", "idle_1", "--all") == 2
    captured = capsys.readouterr()
    assert (captured.out, captured.err) == ("", "error: --frame cannot be used with --all\n")


def test_outside_a_project_is_a_usage_error(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    assert show("goblin") == 2
    assert capsys.readouterr().err.startswith("error: no sprite-tool.toml found")


# --- problems -------------------------------------------------------------------


def break_sprite(root: Path, name: str) -> None:
    """Give the sprite an unknown palette key in its first row (E104)."""
    path = next(root.rglob(name + ".sprite.toml"))
    text = path.read_text(encoding="utf-8")
    start = text.index('"""\n') + 4
    path.write_text(text[:start] + "?" + text[start + 1 :], encoding="utf-8")


def test_a32_an_outline_fault_is_printed_and_the_grid_is_still_shown(demo, capsys):
    path = demo / "units" / "goblin.sprite.toml"
    path.write_text(path.read_text(encoding="utf-8").replace("k", "w", 1), encoding="utf-8")
    assert show("goblin") == 0
    lines = capsys.readouterr().out.splitlines()
    assert "units/goblin.sprite.toml:" in lines[0] and "E201 frame 'main': 'w' touches transparency" in lines[0]
    assert lines[1] == "1 error, 0 warnings in 1 file"
    assert lines[2] == "goblin main  unit 32x32"
    assert len(lines) == 2 + 3 + 32


def test_a32_an_unknown_palette_key_is_printed_and_no_grid_is_shown(demo, capsys):
    break_sprite(demo, "goblin")
    assert show("goblin") == 1
    captured = capsys.readouterr()
    assert captured.out.splitlines() == [
        "units/goblin.sprite.toml:6:1: E104 unknown palette key '?'",
        "1 error, 0 warnings in 1 file",
    ]
    assert captured.err == ""


def test_an_error_in_one_id_stops_the_others(demo, capsys):
    break_sprite(demo, "goblin")
    assert show("warrior", "goblin") == 1
    assert "warrior idle_0" not in capsys.readouterr().out


def test_a_broken_file_that_was_not_named_does_not_show_up(demo, capsys):
    break_sprite(demo, "goblin")
    assert show("warrior") == 0
    out = capsys.readouterr().out
    assert out.startswith("warrior idle_0  unit 32x32\n") and "E104" not in out
    assert len(out.splitlines()) == 3 + 32 + 1  # the grip


def test_a_bad_palette_prints_its_problems_and_no_grid(demo, capsys):
    palette = demo / "palette.toml"
    palette.write_text(palette.read_text(encoding="utf-8").replace("#1a1c2c", "black"), encoding="utf-8")
    assert show("goblin") == 1
    out = capsys.readouterr().out
    assert "palette.toml:3:1: E002" in out and "goblin main" not in out


# --- 0.6: points and --diff -----------------------------------------------------


def add_to_warrior(demo: Path, text: str) -> None:
    path = demo / "units" / "warrior.sprite.toml"
    path.write_text(path.read_text(encoding="utf-8") + text, encoding="utf-8")


def test_a65_points_follow_the_grid_one_line_each_in_name_order(demo, capsys):
    path = demo / "units" / "warrior.sprite.toml"
    path.write_text(path.read_text(encoding="utf-8").replace("grip = [25, 18]", "grip = [25, 18]\nchest = [16, 15]"))
    assert show("warrior", "goblin") == 0
    warrior, goblin = blocks(capsys.readouterr().out)
    assert warrior[3 + 32 :] == ["point chest 16,15", "point grip 25,18"]
    # Nothing extra for a sprite without points.
    assert len(goblin) == 3 + 32


def test_frame_text_lists_a_frames_own_points():
    sprite = make_sprite("gem", replace(make_frame("main", "kk", "kk"), points=(("a", (0, 1)), ("b", (1, 0)))))
    assert frame_text(sprite, sprite.frames[0]).splitlines()[-2:] == ["point a 0,1", "point b 1,0"]


# The right leg, rows 25 to 31 and columns 17 to 23, a pixel to the right.
WALK = '\n[frames.walk_1]\nfrom = "idle_0"\nmove = { rows = [25, 31], cols = [17, 23], by = [1, 0] }\n'


def test_a73_diff_prints_only_the_changed_rows_each_with_a_marker_line(demo, capsys, loaded):
    add_to_warrior(demo, WALK)
    assert show("warrior", "--frame", "walk_1", "--diff") == 0
    lines = capsys.readouterr().out.splitlines()
    assert lines[:3] == [
        "warrior walk_1 vs idle_0  unit 32x32",
        "              1111111111222222222233",
        "    01234567890123456789012345678901",
    ]
    rows = lines[3:-1]
    assert [line[:4] for line in rows[::2]] == [f"{row}  " for row in range(25, 32)]
    assert rows[0] == "25  ..........kDDDDk..kDDDDk........"
    assert rows[1] == "    " + " " * 17 + "^^   ^^"
    idle = loaded["warrior"].frames[0].rows
    for numbered, marks in zip(rows[::2], rows[1::2]):
        row = int(numbered[:2])
        changed = [col for col, (new, old) in enumerate(zip(numbered[4:], idle[row])) if new != old]
        assert [col - 4 for col, mark in enumerate(marks) if mark == "^"] == changed
        assert marks == marks.rstrip()
    assert lines[-1] == "point grip 25,18"


def test_a73_diff_with_a_frame_name_compares_with_that_frame(demo, capsys):
    add_to_warrior(demo, WALK)
    assert show("warrior", "--frame", "walk_1", "--diff", "idle_1") == 0
    lines = capsys.readouterr().out.splitlines()
    assert lines[0] == "warrior walk_1 vs idle_1  unit 32x32"
    # `idle_1` also differs from `idle_0` on row 9.
    assert [line[:2] for line in lines[3:-1:2]] == [" 9", "25", "26", "27", "28", "29", "30", "31"]


def test_a74_equal_frames_print_the_header_and_no_rows_differ(demo, capsys):
    assert show("warrior", "--frame", "idle_0", "--diff", "idle_0") == 0
    assert capsys.readouterr().out.splitlines()[:2] == ["warrior idle_0 vs idle_0  unit 32x32", "no rows differ"]


def test_diff_takes_several_ids_that_each_have_the_frame(demo, capsys):
    add_to_warrior(demo, WALK)
    assert show("warrior", "warrior_red", "--frame", "walk_1", "--diff") == 0
    assert [block[0] for block in blocks(capsys.readouterr().out)] == [
        "warrior walk_1 vs idle_0  unit 32x32",
        "warrior_red walk_1 vs idle_0  unit 32x32",
    ]


@pytest.mark.parametrize(
    ("argv", "message"),
    [
        (["warrior", "--frame", "idle_0", "--diff"], "frame 'idle_0' of 'warrior' has no from; name a frame to compare with: --diff <frame>"),
        (["warrior", "--frame", "idle_1", "--diff", "nosuch"], "sprite 'warrior' has no frame 'nosuch' (frames: idle_0, idle_1)"),
        (["warrior", "--diff"], "--diff needs exactly one --frame"),
        (["warrior", "--frame", "idle_0", "--frame", "idle_1", "--diff"], "--diff needs exactly one --frame"),
        (["warrior", "--all", "--diff"], "--diff cannot be used with --all"),
    ],
)
def test_a74_diff_refusals_exit_2(demo, capsys, argv, message):
    assert show(*argv) == 2
    captured = capsys.readouterr()
    assert (captured.out, captured.err) == ("", f"error: {message}\n")
