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
    "slime.png",
    "sprites.json",
    "warrior.png",
    "warrior__idle_0.png",
    "warrior__idle_1.png",
    "warrior_red.png",
    "warrior_red__idle_0.png",
    "warrior_red__idle_1.png",
]
DEMO_PNGS = [name for name in DEMO_FILES if name.endswith(".png")]

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
    assert captured.out == "built: 5 sprites, 7 frames, 1 target\n"
    assert captured.err == ""

    out = demo / "out" / "frames"
    assert sorted(tree(out)) == sorted(DEMO_FILES)
    manifest = json.loads((out / MANIFEST_NAME).read_text(encoding="utf-8"))
    assert manifest == {"targets": {"frames:sprites": sorted(DEMO_FILES[1:])}, "version": 1}


def test_frames_are_full_canvas_size(demo):
    run(demo)
    out = demo / "out" / "frames"
    assert image(out / "ground_light.png").size == (16, 16)
    for name in DEMO_PNGS:
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
    before = {name: pixels(image(out / name)) for name in DEMO_PNGS}
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
    assert capsys.readouterr().out.endswith("built: 5 sprites, 7 frames, 1 target\n")
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
    assert capsys.readouterr().out == "built: 5 sprites, 7 frames, 0 targets\n"
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
    assert lines[1] == "built: 5 sprites, 7 frames, 1 target"
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

    assert capsys.readouterr().out == "built: 3 sprites, 3 frames, 1 target\n"
    assert sorted(tree(out)) == sorted(
        [MANIFEST_NAME, "goblin.png", "ground_light.png", "notes.txt", "slime.png", "sprites.json"]
    )
    assert (out / "notes.txt").read_text() == "mine"


def test_an_unowned_file_blocks_the_build(demo, capsys):
    out = demo / "out" / "frames"
    out.mkdir(parents=True)
    (out / "goblin.png").write_bytes(b"hand made")

    assert run(demo) == 2

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("error: ")
    assert captured.err == (
        f"error: {out / 'goblin.png'} already exists and was not written by sprite-tool"
        " (use --adopt <id>... for those sprites, or --adopt for all)\n"
    )
    assert tree(out) == {"goblin.png": b"hand made"}


def test_adopt_takes_ownership_of_existing_files(demo, capsys):
    out = demo / "out" / "frames"
    out.mkdir(parents=True)
    (out / "goblin.png").write_bytes(b"hand made")

    assert run(demo, "--adopt") == 0

    assert capsys.readouterr().out == f"adopted {out / 'goblin.png'}\nbuilt: 5 sprites, 7 frames, 1 target\n"
    assert image(out / "goblin.png").size == (32, 32)
    manifest = json.loads((out / MANIFEST_NAME).read_text(encoding="utf-8"))
    assert "goblin.png" in manifest["targets"]["frames:sprites"]
    assert run(demo) == 0


def hand_made(root: Path, *names: str) -> Path:
    """Put files the tool did not write in `out/frames`, and return that directory."""
    out = root / "out" / "frames"
    out.mkdir(parents=True, exist_ok=True)
    for name in names:
        (out / name).write_bytes(b"hand made")
    return out


def test_a23_adopting_one_id_stops_at_the_file_of_another_and_writes_nothing(demo, capsys):
    out = hand_made(demo, "goblin.png", "warrior.png")

    assert run(demo, "--adopt", "warrior") == 2

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == (
        f"error: {out / 'goblin.png'} already exists and was not written by sprite-tool"
        " (use --adopt <id>... for those sprites, or --adopt for all)\n"
    )
    assert tree(out) == {"goblin.png": b"hand made", "warrior.png": b"hand made"}


def test_a23_adopting_every_id_with_a_file_builds_and_names_each_adopted_file(demo, capsys, monkeypatch):
    out = hand_made(demo, "goblin.png", "warrior.png")
    monkeypatch.chdir(demo)

    assert run(demo, "--adopt", "warrior", "goblin") == 0

    assert capsys.readouterr().out.splitlines() == [
        "adopted out/frames/goblin.png",
        "adopted out/frames/warrior.png",
        "built: 5 sprites, 7 frames, 1 target",
    ]
    assert sorted(tree(out)) == sorted(DEMO_FILES)
    assert image(out / "warrior.png").size == (32, 32)


def test_a24_adopting_an_unknown_id_exits_2_and_writes_nothing(demo, capsys):
    out = hand_made(demo, "goblin.png")

    assert run(demo, "--adopt", "nosuch") == 2

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "error: unknown sprite id 'nosuch' (sprites: goblin, ground_light, slime, warrior, warrior_red)\n"
    assert tree(out) == {"goblin.png": b"hand made"}


def test_an_unknown_adopt_id_is_reported_even_when_no_file_needs_adopting(demo, capsys):
    assert run(demo, "--adopt", "goblin", "nosuch") == 2
    assert "unknown sprite id 'nosuch'" in capsys.readouterr().err
    assert not (demo / "out").exists()


def test_bare_adopt_names_every_file_it_took_sorted_by_directory_then_name(demo, capsys):
    set_exports(demo, FRAMES + FRAMES.replace("out/frames", "out/more"))
    out = hand_made(demo, "warrior__idle_0.png", "goblin.png")
    more = demo / "out" / "more"
    more.mkdir()
    (more / "ground_light.png").write_bytes(b"hand made")

    assert run(demo, "--adopt") == 0

    assert capsys.readouterr().out.splitlines() == [
        f"adopted {out / 'goblin.png'}",
        f"adopted {out / 'warrior__idle_0.png'}",
        f"adopted {more / 'ground_light.png'}",
        "built: 5 sprites, 7 frames, 2 targets",
    ]


def test_adopt_names_nothing_when_there_was_nothing_to_take(demo, capsys):
    hand_made(demo, "goblin.png")
    run(demo, "--adopt", "goblin")
    capsys.readouterr()

    for flags in ([], ["--adopt"], ["--adopt", "goblin"]):
        assert run(demo, *flags) == 0
        assert capsys.readouterr().out == "built: 5 sprites, 7 frames, 1 target\n"


def test_adopting_a_sprite_does_not_take_its_variants_files(demo, capsys):
    out = hand_made(demo, "warrior.png", "warrior__idle_1.png", "warrior_red.png", "warrior_red__idle_0.png")
    before = tree(out)

    assert run(demo, "--adopt", "warrior") == 2

    assert capsys.readouterr().err == (
        f"error: {out / 'warrior_red.png'} and 1 more already exist and were not written by sprite-tool"
        " (use --adopt <id>... for those sprites, or --adopt for all)\n"
    )
    assert tree(out) == before


def test_a_variant_is_adopted_by_its_own_id(demo, capsys):
    out = hand_made(demo, "warrior_red.png", "warrior_red__idle_0.png")

    assert run(demo, "--adopt", "warrior_red") == 0

    assert capsys.readouterr().out.splitlines() == [
        f"adopted {out / 'warrior_red.png'}",
        f"adopted {out / 'warrior_red__idle_0.png'}",
        "built: 5 sprites, 7 frames, 1 target",
    ]


def test_adopt_warnings_come_before_the_adopted_lines(demo, capsys):
    out = hand_made(demo, "goblin.png")
    assert main(["new", "ghost", "--canvas", "unit", "--project", str(demo)]) == 0
    capsys.readouterr()

    assert run(demo, "--adopt", "goblin") == 0

    warning, adopted, summary = capsys.readouterr().out.splitlines()
    assert "ghost.sprite.toml" in warning
    assert adopted == f"adopted {out / 'goblin.png'}"
    assert summary == "built: 5 sprites, 7 frames, 1 target"


def test_a_sprite_that_is_not_exported_is_an_unknown_adopt_id(demo, capsys):
    add_scout(demo)
    assert main(["new", "ghost", "--canvas", "unit", "--project", str(demo)]) == 0
    capsys.readouterr()

    for sprite_id in ("scout", "scout_pale", "ghost"):
        assert run(demo, "--adopt", sprite_id) == 2
        captured = capsys.readouterr()
        assert captured.out == ""
        assert captured.err == (
            f"error: unknown sprite id {sprite_id!r} (sprites: goblin, ground_light, slime, warrior, warrior_red)\n"
        )
    assert not (demo / "out").exists()


def test_check_failures_come_before_an_unknown_adopt_id(demo, capsys):
    break_goblin(demo)

    assert run(demo, "--adopt", "nosuch") == 1

    captured = capsys.readouterr()
    assert captured.err == ""
    assert captured.out.splitlines()[-1] == "1 error, 0 warnings in 1 file"


def test_check_ignores_adopt_and_its_ids(demo, capsys):
    out = hand_made(demo, "goblin.png")

    assert run(demo, "--check", "--adopt", "nosuch") == 1

    captured = capsys.readouterr()
    assert captured.err == ""
    assert "out/frames/goblin.png: E401 stale" in captured.out.splitlines()
    assert "adopted" not in captured.out
    assert tree(out) == {"goblin.png": b"hand made"}

    run(demo, "--adopt")
    capsys.readouterr()
    assert run(demo, "--check", "--adopt", "nosuch") == 0
    assert capsys.readouterr().out == "up to date: 5 sprites, 7 frames, 1 target\n"


def test_build_help_describes_adopt(capsys):
    with pytest.raises(SystemExit):
        main(["build", "--help"])
    text = " ".join(capsys.readouterr().out.split())
    assert "--adopt [id ...]" in text
    assert "overwrite existing files the tool did not write: all of them, or only those of the given sprite ids" in text


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

    assert capsys.readouterr().out == "built: 5 sprites, 7 frames, 2 targets\n"
    out = demo / "out" / "frames"
    assert sorted(tree(out)) == sorted([*DEMO_FILES, "atlas.json"])
    manifest = json.loads((out / MANIFEST_NAME).read_text(encoding="utf-8"))
    assert manifest["targets"] == {"frames:sprites": sorted(DEMO_FILES[1:]), "phaser:atlas": ["atlas.json"]}


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
    assert captured.out == "up to date: 5 sprites, 7 frames, 1 target\n"
    assert captured.err == ""
    assert tree(demo) == before


def test_check_before_the_first_build_reports_every_file_missing(demo, capsys):
    assert run(demo, "--check") == 1
    lines = capsys.readouterr().out.splitlines()
    assert lines[:-1] == [f"out/frames/{name}: E401 missing" for name in sorted(DEMO_FILES)]
    assert lines[-1] == "11 errors, 0 warnings in 11 files"
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
        "out/frames/sprites.json: E401 stale",
        "3 errors, 0 warnings in 3 files",
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
    assert capsys.readouterr().out.splitlines()[-1] == "11 errors, 1 warning in 12 files"


def test_a_sprite_named_like_another_sprites_frame_file_stops_the_build(demo, capsys):
    """`warrior__idle_0.png` would be both that sprite and a frame of `warrior`."""
    goblin = demo / "units" / "goblin.sprite.toml"
    (demo / "units" / "warrior__idle_0.sprite.toml").write_bytes(goblin.read_bytes())
    assert main(["build", "--project", str(demo)]) == 1
    out = capsys.readouterr().out
    assert "E003 sprite id 'warrior__idle_0' clashes with frame 'idle_0' of sprite 'warrior'" in out
    assert not (demo / "out").exists()


# --- the index --------------------------------------------------------------


def frames_index(root: Path, name: str = "sprites") -> dict:
    return json.loads((root / "out" / "frames" / f"{name}.json").read_text(encoding="utf-8"))


def test_a21_the_frames_target_writes_an_index_of_sprite_data(demo):
    assert run(demo) == 0

    index = frames_index(demo)
    assert sorted(index) == ["goblin", "ground_light", "slime", "warrior", "warrior_red"]
    assert index["goblin"] == {
        "anchor": [16, 32],
        "anims": {},
        "bounds": [4, 3, 26, 29],
        "canvas": "unit",
        "display_scale": 2,
        "file": "goblin.png",
        "frames": {"main": {"bounds": [4, 3, 26, 29], "file": "goblin.png"}},
        "size": [32, 32],
    }
    assert index["ground_light"]["canvas"] == "tile"
    assert index["ground_light"]["display_scale"] == 4


def test_a21_bounds_is_the_box_of_the_pixels_in_the_exported_image(demo):
    run(demo)
    out = demo / "out" / "frames"
    for sprite_id, entry in frames_index(demo).items():
        for frame in entry["frames"].values():
            left, top, right, bottom = image(out / frame["file"]).getbbox()
            assert frame["bounds"] == [left, top, right - left, bottom - top], sprite_id


def test_index_frames_of_a_sprite_with_several_frames_name_their_own_files(demo):
    run(demo)
    index = frames_index(demo)
    for sprite_id in ("warrior", "warrior_red"):
        entry = index[sprite_id]
        assert entry["file"] == f"{sprite_id}.png"
        assert {name: frame["file"] for name, frame in entry["frames"].items()} == {
            "idle_0": f"{sprite_id}__idle_0.png",
            "idle_1": f"{sprite_id}__idle_1.png",
        }


def test_index_bounds_of_a_sprite_covers_all_its_frames(demo):
    edit(
        demo / "units" / "warrior.sprite.toml",
        "[anim.idle]",
        '[frames.reach]\nfrom = "idle_0"\nruns = { 9 = [[1, "kkkkkk"]] }\n\n[anim.idle]',
    )
    assert run(demo) == 0

    entry = frames_index(demo)["warrior"]
    assert entry["frames"]["idle_0"]["bounds"] == [7, 1, 22, 31]
    assert entry["frames"]["reach"]["bounds"] == [1, 1, 28, 31]
    assert entry["bounds"] == [1, 1, 28, 31]


def test_a22_build_check_flags_the_index_after_a_display_scale_edit(demo, capsys):
    run(demo)
    edit(demo / "sprite-tool.toml", "display_scale = 2", "display_scale = 3")
    capsys.readouterr()

    assert run(demo, "--check") == 1

    assert capsys.readouterr().out.splitlines() == [
        "out/frames/sprites.json: E401 stale",
        "1 error, 0 warnings in 1 file",
    ]


def test_a_frames_target_names_its_index(demo):
    set_exports(demo, FRAMES + 'name = "units"\n')
    assert run(demo) == 0

    out = demo / "out" / "frames"
    assert sorted(frames_index(demo, "units")) == ["goblin", "ground_light", "slime", "warrior", "warrior_red"]
    assert not (out / "sprites.json").exists()
    manifest = json.loads((out / MANIFEST_NAME).read_text(encoding="utf-8"))
    assert list(manifest["targets"]) == ["frames:units"]


def test_a_frames_and_a_godot_target_with_one_name_in_one_directory_is_a_config_error(demo, capsys):
    godot = '\n[[export]]\ntype = "godot"\nout = "out/frames"\nname = "sprites"\nres_path = "res://sprites"\n'
    set_exports(demo, FRAMES + godot)

    assert run(demo) == 2

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("error: export targets 'frames:sprites' and 'godot:sprites' both write sprites.json")
    assert not (demo / "out").exists()


def as_built_by_0_2_0(root: Path) -> Path:
    """Build, then put `out/frames` back to what 0.2.0 left: no index, and the manifest key `frames`."""
    assert run(root) == 0
    out = root / "out" / "frames"
    (out / "sprites.json").unlink()
    files = sorted(name for name in DEMO_FILES[1:] if name != "sprites.json")
    (out / MANIFEST_NAME).write_text(json.dumps({"targets": {"frames": files}, "version": 1}), encoding="utf-8")
    return out


def test_a_directory_built_by_0_2_0_builds_without_adopt_and_gets_the_new_manifest_key(demo, capsys):
    out = as_built_by_0_2_0(demo)
    capsys.readouterr()

    assert run(demo) == 0

    assert capsys.readouterr().out == "built: 5 sprites, 7 frames, 1 target\n"
    assert sorted(tree(out)) == sorted(DEMO_FILES)
    manifest = json.loads((out / MANIFEST_NAME).read_text(encoding="utf-8"))
    assert manifest == {"targets": {"frames:sprites": sorted(DEMO_FILES[1:])}, "version": 1}


def test_a_hand_made_index_in_a_directory_built_by_0_2_0_blocks_the_build(demo, capsys):
    out = as_built_by_0_2_0(demo)
    (out / "sprites.json").write_text("mine", encoding="utf-8")
    capsys.readouterr()

    assert run(demo) == 2

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == (
        f"error: {out / 'sprites.json'} already exists and was not written by sprite-tool"
        " (use --adopt <id>... for those sprites, or --adopt for all)\n"
    )
    assert (out / "sprites.json").read_text(encoding="utf-8") == "mine"


# --- build = false ----------------------------------------------------------

ALL_TARGETS = (
    FRAMES
    + '\n[[export]]\ntype = "phaser"\nout = "out/phaser"\nname = "atlas"\n'
    + '\n[[export]]\ntype = "godot"\nout = "out/godot"\nname = "atlas"\nres_path = "res://sprites"\n'
)


def add_scout(root: Path, head: str = "build = false\n") -> Path:
    """Add `scout`, a copy of the goblin with a `pale` variant, with `head` above it."""
    goblin = (root / "units" / "goblin.sprite.toml").read_text(encoding="utf-8")
    path = root / "units" / "scout.sprite.toml"
    path.write_text(f'{head}{goblin}\n[variants.pale]\nswap = {{ G = "g" }}\n', encoding="utf-8")
    return path


def test_a25_a_sprite_with_build_false_is_counted_by_check(demo, capsys):
    add_scout(demo)

    assert main(["check", "--project", str(demo)]) == 0
    assert capsys.readouterr().out == "ok: 8 sprites, 10 frames\n"


def test_a25_a_sprite_with_build_false_is_previewed(demo, capsys):
    add_scout(demo)

    assert main(["preview", "scout", "--project", str(demo)]) == 0
    (written,) = capsys.readouterr().out.splitlines()
    assert "scout" in written
    assert list((demo / ".preview").iterdir()) != []


def test_a25_a_sprite_with_build_false_and_its_variant_are_in_no_target_and_no_index(demo, capsys):
    set_exports(demo, ALL_TARGETS)
    add_scout(demo)

    assert run(demo) == 0

    assert capsys.readouterr().out == "built: 5 sprites, 7 frames, 3 targets\n"
    out = demo / "out"
    assert [name for name in tree(out) if Path(name).name.startswith("scout")] == []
    assert sorted(tree(out / "frames")) == sorted(DEMO_FILES)
    index = json.loads((out / "godot" / "atlas.json").read_text(encoding="utf-8"))
    assert sorted(index) == ["goblin", "ground_light", "slime", "warrior", "warrior_red"]
    atlas = json.loads((out / "phaser" / "atlas.json").read_text(encoding="utf-8"))
    assert [name for name in atlas["frames"] if name.startswith("scout")] == []
    anims = (out / "phaser" / "atlas.anims.json").read_text(encoding="utf-8")
    assert "scout" not in anims


def test_a25_build_check_does_not_count_a_sprite_with_build_false(demo, capsys):
    add_scout(demo)
    run(demo)
    capsys.readouterr()

    assert run(demo, "--check") == 0
    assert capsys.readouterr().out == "up to date: 5 sprites, 7 frames, 1 target\n"


def test_a25_adding_build_false_removes_the_sprites_files_and_leaves_the_others(demo, capsys):
    scout = add_scout(demo, head="")
    run(demo)
    out = demo / "out" / "frames"
    assert {"scout.png", "scout_pale.png"} <= set(tree(out))
    # The index listed the scout, so it is rewritten; the images are not.
    before = {name: (out / name).stat().st_mtime_ns for name in DEMO_PNGS}

    scout.write_text("build = false\n" + scout.read_text(encoding="utf-8"), encoding="utf-8")
    capsys.readouterr()
    assert run(demo) == 0

    assert capsys.readouterr().out == "built: 5 sprites, 7 frames, 1 target\n"
    assert sorted(tree(out)) == sorted(DEMO_FILES)
    assert {name: (out / name).stat().st_mtime_ns for name in before} == before
    assert run(demo, "--check") == 0
    assert capsys.readouterr().out == "up to date: 5 sprites, 7 frames, 1 target\n"


def test_a25_build_check_reports_the_exported_files_of_a_sprite_that_now_says_build_false(demo, capsys):
    scout = add_scout(demo, head="")
    run(demo)
    scout.write_text("build = false\n" + scout.read_text(encoding="utf-8"), encoding="utf-8")
    capsys.readouterr()

    assert run(demo, "--check") == 1
    out = capsys.readouterr().out
    assert "scout.png" in out and "scout_pale.png" in out
    assert "goblin.png" not in out


def test_a25_two_files_with_one_stem_are_e003_when_one_says_build_false(demo, capsys):
    add_scout(demo)
    (demo / "tiles" / "scout.sprite.toml").write_text(
        (demo / "tiles" / "ground_light.sprite.toml").read_text(encoding="utf-8"), encoding="utf-8"
    )

    assert run(demo) == 1
    out = capsys.readouterr().out
    assert "tiles/scout.sprite.toml: E003 duplicate sprite id 'scout', also in units/scout.sprite.toml" in out
    assert not (demo / "out").exists()


def test_a25_a_fault_in_a_sprite_with_build_false_fails_the_build_and_writes_nothing(demo, capsys):
    edit(add_scout(demo), "kyyok", "kyy?k")

    assert run(demo) == 1
    out = capsys.readouterr().out
    assert "units/scout.sprite.toml" in out and "E104" in out
    assert not (demo / "out").exists()


def test_a25_build_of_the_wrong_type_is_e001_at_the_build_line(demo, capsys):
    add_scout(demo, head='# not built\nbuild = "no"\n')

    assert run(demo) == 1
    assert "units/scout.sprite.toml:2:1: E001 build must be true or false" in capsys.readouterr().out


# --- the demo's own sprites -------------------------------------------------


def test_the_demos_auto_outlined_sprite_is_in_every_target_and_its_reference_copy_in_none(demo, capsys):
    set_exports(demo, ALL_TARGETS)

    assert run(demo) == 0

    assert capsys.readouterr().out == "built: 5 sprites, 7 frames, 3 targets\n"
    out = demo / "out"
    assert (out / "frames" / "slime.png").exists()
    assert (out / "godot" / "slime.tres").exists()
    atlas = json.loads((out / "phaser" / "atlas.json").read_text(encoding="utf-8"))
    assert "slime/main" in atlas["frames"]
    assert "slime" in frames_index(demo)
    godot = json.loads((out / "godot" / "atlas.json").read_text(encoding="utf-8"))
    assert "slime" in godot

    assert [name for name in tree(out) if "sample_slime" in name] == []
    assert "sample_slime" not in frames_index(demo) and "sample_slime" not in godot
    assert [name for name in atlas["frames"] if name.startswith("sample_slime")] == []
