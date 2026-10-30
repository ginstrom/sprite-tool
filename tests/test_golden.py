import json
import re
import shutil
import struct
import time
from importlib.metadata import version
from pathlib import Path

import pytest

from sprite_tool.cli import main

REPO = Path(__file__).parent.parent
DEMO = REPO / "examples" / "demo"
GOLDEN = Path(__file__).parent / "golden"

TARGETS = ["frames", "godot", "phaser"]

# The design's target is 2 seconds on a laptop; the bound allows for a slow machine.
SPEED_SPRITES = 200
SPEED_BOUND_SECONDS = 5.0


def copy_demo(root: Path) -> Path:
    """A copy of the demo's sources at `root`, with nothing built."""
    shutil.copytree(DEMO, root, ignore=shutil.ignore_patterns("out", ".preview"))
    return root


def build(root: Path, *flags: str) -> int:
    return main(["build", *flags, "--project", str(root)])


def tree(root: Path) -> dict[str, bytes]:
    """Every file under `root`, by relative path."""
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def chunk_types(png: bytes) -> list[str]:
    types, at = [], 8
    while at < len(png):
        (length,) = struct.unpack(">I", png[at : at + 4])
        types.append(png[at + 4 : at + 8].decode("ascii"))
        at += 12 + length
    return types


@pytest.fixture
def built(tmp_path: Path) -> Path:
    """The `out/` directory of a freshly built copy of the demo."""
    root = copy_demo(tmp_path / "demo")
    assert build(root) == 0
    return root / "out"


def test_golden_holds_the_three_targets():
    assert sorted(path.name for path in GOLDEN.iterdir()) == TARGETS


def test_build_check_passes_against_the_golden_files(tmp_path, capsys):
    root = copy_demo(tmp_path / "demo")
    shutil.copytree(GOLDEN, root / "out")

    assert build(root, "--check") == 0
    assert capsys.readouterr().out == "up to date: 7 sprites, 12 frames, 3 targets\n"


def test_a_fresh_build_of_the_demo_is_the_golden_files_byte_for_byte(built):
    fresh, golden = tree(built), tree(GOLDEN)
    assert sorted(fresh) == sorted(golden)
    assert [name for name in fresh if fresh[name] != golden[name]] == []


def test_a8_two_copies_of_the_demo_build_to_identical_bytes(tmp_path):
    first, second = copy_demo(tmp_path / "one" / "demo"), copy_demo(tmp_path / "two" / "elsewhere")
    assert build(first) == 0
    assert build(second) == 0

    assert tree(first / "out") == tree(second / "out")
    assert len(tree(first / "out")) == 31


def test_a8_a_second_build_in_place_changes_no_byte(built):
    before = tree(built)
    assert build(built.parent) == 0
    assert tree(built) == before


def test_a14_unit_and_tile_are_in_one_sheet_at_their_own_sizes(built):
    phaser = json.loads((built / "phaser" / "atlas.json").read_text(encoding="utf-8"))
    assert phaser["meta"]["image"] == "atlas.png"
    sizes = {key: (entry["frame"]["w"], entry["frame"]["h"]) for key, entry in phaser["frames"].items()}
    assert sizes["warrior/idle_0"] == (32, 32)
    assert sizes["ground_light/main"] == (16, 16)

    godot = json.loads((built / "godot" / "atlas.json").read_text(encoding="utf-8"))
    assert godot["warrior"]["size"] == [32, 32]
    assert godot["warrior"]["frames"]["idle_0"][2:] == [32, 32]
    assert godot["ground_light"]["size"] == [16, 16]
    assert godot["ground_light"]["frames"]["main"][2:] == [16, 16]
    for sprite_id in ("warrior", "ground_light"):
        tres = (built / "godot" / f"{sprite_id}.tres").read_text(encoding="utf-8")
        assert 'path="res://sprites/atlas.png"' in tres


def test_golden_text_files_hold_no_path_timestamp_or_tool_version():
    texts = {name: data.decode("utf-8") for name, data in tree(GOLDEN).items() if not name.endswith(".png")}
    assert len(texts) == 14
    tool_version = version("sprite-tool")
    forbidden = [
        re.compile(r"(?<![:/\w])/\w"),  # an absolute POSIX path (`res://` is not one)
        re.compile(r"[A-Za-z]:\\"),  # a Windows path
        re.compile(r"\d{4}-\d{2}-\d{2}"),  # a date
        re.compile(r"\d{2}:\d{2}:\d{2}"),  # a time of day
        re.compile(r"\d{9,}"),  # seconds since the epoch
        re.compile(re.escape(tool_version)),
        re.compile(r"sprite.tool \d|generated (by|on|at)", re.IGNORECASE),
    ]
    found = [
        (name, pattern.pattern, match.group())
        for name, text in texts.items()
        for pattern in forbidden
        if (match := pattern.search(text))
    ]
    assert found == []


def test_golden_pngs_hold_only_image_data():
    pngs = {name: data for name, data in tree(GOLDEN).items() if name.endswith(".png")}
    assert len(pngs) == 17
    for name, data in pngs.items():
        assert chunk_types(data) == ["IHDR", "IDAT", "IEND"], name


def test_q5_two_hundred_sprites_build_within_the_time_bound(tmp_path, capsys):
    root = copy_demo(tmp_path / "many")
    unit = (root / "units" / "goblin.sprite.toml").read_text(encoding="utf-8")
    shutil.rmtree(root / "units")
    shutil.rmtree(root / "tiles")
    shutil.rmtree(root / "effects")
    (root / "units").mkdir()
    for number in range(SPEED_SPRITES):
        (root / "units" / f"goblin_{number:03}.sprite.toml").write_text(unit, encoding="utf-8")

    started = time.perf_counter()
    status = build(root)
    seconds = time.perf_counter() - started

    assert status == 0
    assert capsys.readouterr().out == f"built: {SPEED_SPRITES} sprites, {SPEED_SPRITES} frames, 3 targets\n"
    assert len(list((root / "out" / "godot").glob("*.tres"))) == SPEED_SPRITES
    print(f"built {SPEED_SPRITES} sprites in {seconds:.3f} s")
    assert seconds < SPEED_BOUND_SECONDS
