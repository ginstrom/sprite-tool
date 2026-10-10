import json
import os
import re
import shutil
import tomllib
from pathlib import Path

import pytest
from PIL import Image

from conftest import pixels
from sprite_tool.cli import main
from sprite_tool.export import EXPORTERS
from sprite_tool.manifest import MANIFEST_NAME

DEMO = Path(__file__).parent.parent / "examples" / "demo"

FRAMES = '\n[[export]]\ntype = "frames"\nout = "out/frames"\n'

DEMO_FILES = [
    MANIFEST_NAME,
    "goblin.png",
    "ground_light.png",
    "warrior.png",
    "warrior__idle_0.png",
    "warrior__idle_1.png",
    "warrior_red.png",
    "warrior_red__idle_0.png",
    "warrior_red__idle_1.png",
]

BLUE, DARK_BLUE = (0x3B, 0x5D, 0xC9, 255), (0x29, 0x36, 0x6F, 255)
RED, DARK_RED = (0xB1, 0x3E, 0x53, 255), (0x5D, 0x27, 0x5D, 255)


def set_exports(root: Path, exports: str) -> None:
    """Replace every `[[export]]` block in the project's config with `exports`."""
    config = root / "sprite-tool.toml"
    kept = config.read_text(encoding="utf-8").split("[[export]]")[0].rstrip()
    config.write_text(f"{kept}\n{exports}", encoding="utf-8")


@pytest.fixture
def demo(tmp_path: Path) -> Path:
    """A copy of the demo project with one `frames` target, `out/frames`."""
    root = tmp_path / "demo"
    shutil.copytree(DEMO, root, ignore=shutil.ignore_patterns("out", ".preview"))
    set_exports(root, FRAMES)
    return root


def run(root: Path, *flags: str) -> int:
    return main(["build", *flags, "--project", str(root)])


def tree(root: Path) -> dict[str, bytes]:
    """Every file under `root`, by relative path."""
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def image(path: Path) -> Image.Image:
    with Image.open(path) as opened:
        return opened.convert("RGBA")


def edit(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    assert old in text
    path.write_text(text.replace(old, new), encoding="utf-8")


def blink_differently(root: Path) -> None:
    """Change one pixel of `warrior`'s derived frame, `idle_1`."""
    edit(root / "units" / "warrior.sprite.toml", "kddloyoyyok", "kddloooyyok")


def break_goblin(root: Path) -> None:
    edit(root / "units" / "goblin.sprite.toml", 'canvas = "unit"', 'canvas = "nope"')


# --- build ------------------------------------------------------------------


def test_build_writes_the_frames_target(demo, capsys):
    assert run(demo) == 0
    captured = capsys.readouterr()
    assert captured.out == "built: 4 sprites, 6 frames, 1 target\n"
    assert captured.err == ""

    out = demo / "out" / "frames"
    assert sorted(tree(out)) == sorted(DEMO_FILES)
    manifest = json.loads((out / MANIFEST_NAME).read_text(encoding="utf-8"))
    assert manifest == {"targets": {"frames": sorted(DEMO_FILES[1:])}, "version": 1}


def test_frames_are_full_canvas_size(demo):
    run(demo)
    out = demo / "out" / "frames"
    assert image(out / "ground_light.png").size == (16, 16)
    for name in DEMO_FILES[1:]:
        if name != "ground_light.png":
            assert image(out / name).size == (32, 32), name


def test_default_frame_file_is_the_first_frame(demo):
    run(demo)
    out = demo / "out" / "frames"
    assert (out / "warrior.png").read_bytes() == (out / "warrior__idle_0.png").read_bytes()
    assert (out / "warrior.png").read_bytes() != (out / "warrior__idle_1.png").read_bytes()


def test_a4_a_frame_derived_with_rows_renders_as_the_same_frame_written_in_full(demo):
    source = demo / "units" / "warrior.sprite.toml"
    frames = tomllib.loads(source.read_text(encoding="utf-8"))["frames"]
    rows = frames["idle_0"].strip("\n").split("\n")
    for index, row in frames["idle_1"]["rows"].items():
        rows[int(index)] = row
    full = "\n".join(rows)
    edit(source, "[frames.idle_1]", f'idle_full = """\n{full}\n"""\n\n[frames.idle_1]')

    assert run(demo) == 0

    out = demo / "out" / "frames"
    derived = (out / "warrior__idle_1.png").read_bytes()
    assert derived == (out / "warrior__idle_full.png").read_bytes()
    assert derived != (out / "warrior__idle_0.png").read_bytes()


def test_a18_a_frame_given_as_runs_renders_as_the_same_frame_written_as_a_grid(demo):
    source = demo / "units" / "warrior.sprite.toml"
    grid = tomllib.loads(source.read_text(encoding="utf-8"))["frames"]["idle_0"].strip("\n").split("\n")
    lines = ['canvas = "unit"', "", "[frames.main.runs]"]
    for index, row in enumerate(grid):
        runs = [[match.start(), match.group()] for match in re.finditer(r"[^.]+", row)]
        if runs:
            lines.append(f"{index} = {json.dumps(runs)}")
    (demo / "units" / "warrior_runs.sprite.toml").write_text("\n".join(lines) + "\n", encoding="utf-8")

    assert run(demo) == 0

    out = demo / "out" / "frames"
    assert (out / "warrior_runs.png").read_bytes() == (out / "warrior__idle_0.png").read_bytes()


def test_a19_a_frame_derived_with_runs_differs_from_its_parent_in_exactly_the_runs_pixels(demo):
    source = demo / "units" / "warrior.sprite.toml"
    edit(source, "[anim.idle]", '[frames.idle_2]\nfrom = "idle_0"\nruns = { 9 = [[13, "rrGGCC"]] }\n\n[anim.idle]')

    assert run(demo) == 0

    out = demo / "out" / "frames"
    parent = image(out / "warrior__idle_0.png")
    child = image(out / "warrior__idle_2.png")
    differing = [
        (x, y) for y in range(parent.height) for x in range(parent.width) if parent.getpixel((x, y)) != child.getpixel((x, y))
    ]
    assert differing == [(x, 9) for x in range(13, 19)]


def test_a5_red_variant_is_the_base_with_its_colours_swapped(demo):
    run(demo)
    out = demo / "out" / "frames"
    swap = {BLUE: RED, DARK_BLUE: DARK_RED}
    for name in ("", "__idle_0", "__idle_1"):
        base = pixels(image(out / f"warrior{name}.png"))
        red = pixels(image(out / f"warrior_red{name}.png"))
        assert BLUE in base and DARK_BLUE in base
        assert red == [swap.get(pixel, pixel) for pixel in base]


def test_a2_palette_change_recolours_that_key_and_nothing_else(demo):
    run(demo)
    out = demo / "out" / "frames"
    before = {name: pixels(image(out / name)) for name in DEMO_FILES[1:]}
    new = (0x12, 0x34, 0x56, 255)

    edit(demo / "palette.toml", "#3b5dc9", "#123456")
    assert run(demo) == 0

    for name, old_pixels in before.items():
        assert pixels(image(out / name)) == [new if pixel == BLUE else pixel for pixel in old_pixels], name
    assert BLUE in before["warrior.png"]
    assert BLUE not in before["warrior_red.png"]


def test_a_second_build_rewrites_no_file(demo, capsys):
    run(demo)
    out = demo / "out" / "frames"
    long_ago = 1_000_000_000
    for path in out.iterdir():
        os.utime(path, (long_ago, long_ago))

    assert run(demo) == 0
    assert capsys.readouterr().out.endswith("built: 4 sprites, 6 frames, 1 target\n")
    assert {path.name for path in out.iterdir() if path.stat().st_mtime != long_ago} == set()


def test_only_changed_files_are_rewritten(demo):
    run(demo)
    out = demo / "out" / "frames"
    long_ago = 1_000_000_000
    for path in out.iterdir():
        os.utime(path, (long_ago, long_ago))

    blink_differently(demo)
    run(demo)

    rewritten = {path.name for path in out.iterdir() if path.stat().st_mtime != long_ago}
    assert rewritten == {"warrior__idle_1.png", "warrior_red__idle_1.png"}


def test_zero_targets_is_valid(demo, capsys):
    set_exports(demo, "")
    assert run(demo) == 0
    assert capsys.readouterr().out == "built: 4 sprites, 6 frames, 0 targets\n"
    assert not (demo / "out").exists()


def test_out_may_be_outside_the_project(demo, tmp_path):
    set_exports(demo, '\n[[export]]\ntype = "frames"\nout = "../game/assets"\n')
    assert run(demo) == 0
    assert sorted(tree(tmp_path / "game" / "assets")) == sorted(DEMO_FILES)


def test_warnings_are_printed_and_do_not_stop_the_build(demo, capsys):
    edit(demo / "palette.toml", "[colors]", '[colors]\nz = "#f4f4f4"')
    assert run(demo) == 0
    lines = capsys.readouterr().out.splitlines()
    assert len(lines) == 2
    assert "W001" in lines[0]
    assert lines[1] == "built: 4 sprites, 6 frames, 1 target"
    assert (demo / "out" / "frames" / "goblin.png").exists()


# --- a failing check writes nothing -----------------------------------------


def test_failing_check_on_the_first_build_writes_nothing(demo, capsys):
    break_goblin(demo)
    assert run(demo) == 1
    out = capsys.readouterr().out
    assert "units/goblin.sprite.toml" in out
    assert out.splitlines()[-1] == "1 error, 0 warnings in 1 file"
    assert "built" not in out
    assert not (demo / "out").exists()


def test_failing_check_leaves_the_output_directory_unchanged(demo):
    run(demo)
    before = tree(demo / "out")

    blink_differently(demo)
    break_goblin(demo)

    assert run(demo) == 1
    assert tree(demo / "out") == before


def test_a_bad_palette_writes_nothing(demo, capsys):
    edit(demo / "palette.toml", "#3b5dc9", "blue")
    assert run(demo) == 1
    assert "E002" in capsys.readouterr().out
    assert not (demo / "out").exists()


# --- cleanup and ownership --------------------------------------------------


def test_a12_deleted_sprite_is_cleaned_up_and_other_files_are_left(demo, capsys):
    run(demo)
    out = demo / "out" / "frames"
    (out / "notes.txt").write_text("mine")

    (demo / "units" / "warrior.sprite.toml").unlink()
    capsys.readouterr()
    assert run(demo) == 0

    assert capsys.readouterr().out == "built: 2 sprites, 2 frames, 1 target\n"
    assert sorted(tree(out)) == sorted([MANIFEST_NAME, "goblin.png", "ground_light.png", "notes.txt"])
    assert (out / "notes.txt").read_text() == "mine"


def test_an_unowned_file_blocks_the_build(demo, capsys):
    out = demo / "out" / "frames"
    out.mkdir(parents=True)
    (out / "goblin.png").write_bytes(b"hand made")

    assert run(demo) == 2

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("error: ")
    assert "goblin.png" in captured.err
    assert captured.err.count("\n") == 1
    assert tree(out) == {"goblin.png": b"hand made"}


def test_adopt_takes_ownership_of_existing_files(demo, capsys):
    out = demo / "out" / "frames"
    out.mkdir(parents=True)
    (out / "goblin.png").write_bytes(b"hand made")

    assert run(demo, "--adopt") == 0

    assert capsys.readouterr().out == "built: 4 sprites, 6 frames, 1 target\n"
    assert image(out / "goblin.png").size == (32, 32)
    manifest = json.loads((out / MANIFEST_NAME).read_text(encoding="utf-8"))
    assert "goblin.png" in manifest["targets"]["frames"]
    assert run(demo) == 0


def test_an_unowned_file_in_one_directory_leaves_every_directory_untouched(demo):
    set_exports(demo, FRAMES + FRAMES.replace("out/frames", "out/more"))
    (demo / "out" / "more").mkdir(parents=True)
    (demo / "out" / "more" / "goblin.png").write_bytes(b"hand made")

    assert run(demo) == 2
    assert tree(demo / "out") == {"more/goblin.png": b"hand made"}


# --- several targets --------------------------------------------------------


def fake_atlas(sprites, images, target):
    return {f"{target.name}.json": b"{}\n"}


PHASER = '\n[[export]]\ntype = "phaser"\nout = "out/frames"\nname = "atlas"\n'


def test_two_targets_writing_the_same_file_in_one_directory_exit_2(demo, capsys):
    set_exports(demo, FRAMES + FRAMES)
    assert run(demo) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "frames" in captured.err and "goblin.png" in captured.err
    assert not (demo / "out").exists()


def test_two_targets_with_disjoint_files_share_a_directory(demo, capsys, monkeypatch):
    monkeypatch.setitem(EXPORTERS, "phaser", fake_atlas)
    set_exports(demo, FRAMES + PHASER)

    assert run(demo) == 0

    assert capsys.readouterr().out == "built: 4 sprites, 6 frames, 2 targets\n"
    out = demo / "out" / "frames"
    assert sorted(tree(out)) == sorted([*DEMO_FILES, "atlas.json"])
    manifest = json.loads((out / MANIFEST_NAME).read_text(encoding="utf-8"))
    assert manifest["targets"] == {"frames": sorted(DEMO_FILES[1:]), "phaser:atlas": ["atlas.json"]}


def test_a_target_type_with_no_exporter_is_a_config_error(demo, capsys, monkeypatch):
    monkeypatch.delitem(EXPORTERS, "phaser", raising=False)
    set_exports(demo, FRAMES + PHASER)

    assert run(demo) == 2

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("error: ")
    assert "phaser" in captured.err and "not available" in captured.err
    assert not (demo / "out").exists()


# --- build --check ----------------------------------------------------------


def test_check_is_clean_after_a_build(demo, capsys):
    run(demo)
    before = tree(demo)
    capsys.readouterr()

    assert run(demo, "--check") == 0

    captured = capsys.readouterr()
    assert captured.out == "up to date: 4 sprites, 6 frames, 1 target\n"
    assert captured.err == ""
    assert tree(demo) == before


def test_check_before_the_first_build_reports_every_file_missing(demo, capsys):
    assert run(demo, "--check") == 1
    lines = capsys.readouterr().out.splitlines()
    assert lines[:-1] == [f"out/frames/{name}: E401 missing" for name in sorted(DEMO_FILES)]
    assert lines[-1] == "9 errors, 0 warnings in 9 files"
    assert not (demo / "out").exists()


def test_check_reports_stale_files_after_a_sprite_is_edited(demo, capsys):
    run(demo)
    blink_differently(demo)
    before = tree(demo)
    capsys.readouterr()

    assert run(demo, "--check") == 1

    assert capsys.readouterr().out.splitlines() == [
        "out/frames/warrior__idle_1.png: E401 stale",
        "out/frames/warrior_red__idle_1.png: E401 stale",
        "2 errors, 0 warnings in 2 files",
    ]
    assert tree(demo) == before


def test_check_reports_a_deleted_output_file(demo, capsys):
    run(demo)
    (demo / "out" / "frames" / "goblin.png").unlink()
    before = tree(demo)
    capsys.readouterr()

    assert run(demo, "--check") == 1

    assert capsys.readouterr().out.splitlines() == [
        "out/frames/goblin.png: E401 missing",
        "1 error, 0 warnings in 1 file",
    ]
    assert tree(demo) == before


def test_check_reports_the_files_of_a_deleted_sprite(demo, capsys):
    run(demo)
    (demo / "units" / "goblin.sprite.toml").unlink()
    before = tree(demo)
    capsys.readouterr()

    assert run(demo, "--check") == 1

    assert capsys.readouterr().out.splitlines() == [
        f"out/frames/{MANIFEST_NAME}: E401 stale",
        "out/frames/goblin.png: E401 no longer generated",
        "2 errors, 0 warnings in 2 files",
    ]
    assert tree(demo) == before


def test_check_does_not_need_adopt_and_reports_unowned_files_as_stale(demo, capsys):
    out = demo / "out" / "frames"
    out.mkdir(parents=True)
    (out / "goblin.png").write_bytes(b"hand made")

    assert run(demo, "--check") == 1

    assert "out/frames/goblin.png: E401 stale" in capsys.readouterr().out.splitlines()
    assert tree(out) == {"goblin.png": b"hand made"}


def test_check_with_failing_sprites_reports_only_those(demo, capsys):
    break_goblin(demo)
    assert run(demo, "--check") == 1
    out = capsys.readouterr().out
    assert "E401" not in out
    assert out.splitlines()[-1] == "1 error, 0 warnings in 1 file"


def test_check_counts_warnings_in_the_summary(demo, capsys):
    edit(demo / "palette.toml", "[colors]", '[colors]\nz = "#f4f4f4"')
    assert run(demo, "--check") == 1
    assert capsys.readouterr().out.splitlines()[-1] == "9 errors, 1 warning in 10 files"


def test_a_sprite_named_like_another_sprites_frame_file_stops_the_build(demo, capsys):
    """`warrior__idle_0.png` would be both that sprite and a frame of `warrior`."""
    goblin = demo / "units" / "goblin.sprite.toml"
    (demo / "units" / "warrior__idle_0.sprite.toml").write_bytes(goblin.read_bytes())
    assert main(["build", "--project", str(demo)]) == 1
    out = capsys.readouterr().out
    assert "E003 sprite id 'warrior__idle_0' clashes with frame 'idle_0' of sprite 'warrior'" in out
    assert not (demo / "out").exists()
