import json
import os
from pathlib import Path

import pytest

from sprite_tool import manifest
from sprite_tool.manifest import MANIFEST_NAME
from sprite_tool.model import ExportTarget
from sprite_tool.project import ConfigError


def frames_target(out: Path) -> ExportTarget:
    return ExportTarget(type="frames", out=out, name=None, res_path=None, padding=0)


def atlas_target(out: Path, name: str = "atlas") -> ExportTarget:
    return ExportTarget(type="phaser", out=out, name=name, res_path=None, padding=1)


def build(out: Path, files: dict[str, bytes], adopt: bool = False) -> None:
    """One `frames` target written to `out`, the way `sprite build` does it."""
    plans = manifest.plan([(frames_target(out), files)])
    if not adopt:
        manifest.check_ownership(plans)
    manifest.apply(plans)


def tree(root: Path) -> dict[str, bytes]:
    """Every file under `root`, by relative path."""
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def read_manifest(out: Path) -> dict:
    return json.loads((out / MANIFEST_NAME).read_text(encoding="utf-8"))


# --- json helper ------------------------------------------------------------


def test_json_bytes_is_sorted_indented_and_newline_terminated():
    assert manifest.json_bytes({"b": [1, 2], "a": {"z": True, "y": None}}) == (
        b'{\n  "a": {\n    "y": null,\n    "z": true\n  },\n  "b": [\n    1,\n    2\n  ]\n}\n'
    )


def test_json_bytes_does_not_depend_on_insertion_order():
    assert manifest.json_bytes({"a": 1, "b": 2}) == manifest.json_bytes({"b": 2, "a": 1})


# --- writing ----------------------------------------------------------------


def test_apply_creates_the_directory_and_writes_files_and_manifest(tmp_path):
    out = tmp_path / "deep" / "out"
    build(out, {"b.png": b"B", "a.png": b"A"})

    assert tree(out) == {
        "a.png": b"A",
        "b.png": b"B",
        MANIFEST_NAME: manifest.json_bytes({"targets": {"frames": ["a.png", "b.png"]}, "version": 1}),
    }


def test_manifest_keys_atlas_targets_by_type_and_name(tmp_path):
    plans = manifest.plan(
        [(frames_target(tmp_path), {"a.png": b"A"}), (atlas_target(tmp_path, "units"), {"units.json": b"{}"})]
    )
    manifest.apply(plans)
    assert read_manifest(tmp_path)["targets"] == {"frames": ["a.png"], "phaser:units": ["units.json"]}


def test_files_in_subdirectories_are_written(tmp_path):
    build(tmp_path, {"units/a.png": b"A"})
    assert (tmp_path / "units" / "a.png").read_bytes() == b"A"


def test_each_output_directory_gets_its_own_manifest(tmp_path):
    plans = manifest.plan(
        [(frames_target(tmp_path / "one"), {"a.png": b"A"}), (frames_target(tmp_path / "two"), {"b.png": b"B"})]
    )
    manifest.apply(plans)
    assert read_manifest(tmp_path / "one")["targets"] == {"frames": ["a.png"]}
    assert read_manifest(tmp_path / "two")["targets"] == {"frames": ["b.png"]}


def test_changed_files_are_overwritten(tmp_path):
    build(tmp_path, {"a.png": b"old"})
    build(tmp_path, {"a.png": b"new"})
    assert (tmp_path / "a.png").read_bytes() == b"new"


def test_unchanged_files_are_not_rewritten(tmp_path):
    files = {"a.png": b"A", "b.png": b"B"}
    build(tmp_path, files)
    long_ago = 1_000_000_000
    for path in tmp_path.iterdir():
        os.utime(path, (long_ago, long_ago))

    build(tmp_path, {**files, "b.png": b"changed"})

    assert (tmp_path / "a.png").stat().st_mtime == long_ago
    assert (tmp_path / MANIFEST_NAME).stat().st_mtime == long_ago
    assert (tmp_path / "b.png").stat().st_mtime != long_ago


# --- cleanup ----------------------------------------------------------------


def test_files_no_longer_produced_are_deleted_and_others_left_alone(tmp_path):
    build(tmp_path, {"a.png": b"A", "b.png": b"B"})
    (tmp_path / "notes.txt").write_text("mine")

    build(tmp_path, {"a.png": b"A"})

    assert sorted(tree(tmp_path)) == sorted([MANIFEST_NAME, "a.png", "notes.txt"])
    assert read_manifest(tmp_path)["targets"] == {"frames": ["a.png"]}


def test_files_of_a_target_removed_from_a_shared_directory_are_deleted(tmp_path):
    both = [(frames_target(tmp_path), {"a.png": b"A"}), (atlas_target(tmp_path), {"atlas.json": b"{}"})]
    manifest.apply(manifest.plan(both))

    manifest.apply(manifest.plan(both[:1]))

    assert sorted(tree(tmp_path)) == [MANIFEST_NAME, "a.png"]


def test_a_listed_file_that_is_already_gone_is_not_an_error(tmp_path):
    build(tmp_path, {"a.png": b"A", "b.png": b"B"})
    (tmp_path / "b.png").unlink()
    build(tmp_path, {"a.png": b"A"})
    assert sorted(tree(tmp_path)) == [MANIFEST_NAME, "a.png"]


# --- ownership --------------------------------------------------------------


def test_an_existing_file_not_in_the_manifest_blocks_the_build(tmp_path):
    (tmp_path / "goblin.png").write_bytes(b"hand made")
    before = tree(tmp_path)

    with pytest.raises(ConfigError) as excinfo:
        build(tmp_path, {"goblin.png": b"G", "warrior.png": b"W"})

    assert "goblin.png" in str(excinfo.value)
    assert "--adopt" in str(excinfo.value)
    assert tree(tmp_path) == before


def test_an_unowned_file_with_the_same_bytes_still_blocks(tmp_path):
    (tmp_path / "goblin.png").write_bytes(b"G")
    with pytest.raises(ConfigError):
        build(tmp_path, {"goblin.png": b"G"})


def test_ownership_is_checked_in_every_directory_before_anything_is_written(tmp_path):
    (tmp_path / "two").mkdir()
    (tmp_path / "two" / "b.png").write_bytes(b"hand made")
    plans = manifest.plan(
        [(frames_target(tmp_path / "one"), {"a.png": b"A"}), (frames_target(tmp_path / "two"), {"b.png": b"B"})]
    )
    with pytest.raises(ConfigError):
        manifest.check_ownership(plans)
    assert tree(tmp_path) == {"two/b.png": b"hand made"}


def test_several_unowned_files_are_summarised_in_one_line(tmp_path):
    for name in ("a.png", "b.png", "c.png"):
        (tmp_path / name).write_bytes(b"hand made")
    with pytest.raises(ConfigError) as excinfo:
        build(tmp_path, {"a.png": b"A", "b.png": b"B", "c.png": b"C"})
    message = str(excinfo.value)
    assert "a.png" in message and "2 more" in message
    assert "\n" not in message


def test_adopt_takes_ownership_and_overwrites(tmp_path):
    (tmp_path / "goblin.png").write_bytes(b"hand made")
    build(tmp_path, {"goblin.png": b"G"}, adopt=True)
    assert (tmp_path / "goblin.png").read_bytes() == b"G"
    assert read_manifest(tmp_path)["targets"] == {"frames": ["goblin.png"]}
    # Owned now, so the next build needs no flag.
    build(tmp_path, {"goblin.png": b"G2"})


def test_owned_files_are_overwritten_without_adopt(tmp_path):
    build(tmp_path, {"goblin.png": b"G"})
    manifest.check_ownership(manifest.plan([(frames_target(tmp_path), {"goblin.png": b"G2"})]))


# --- adopting by sprite id --------------------------------------------------


@pytest.mark.parametrize(
    "name, sprite_id, expected",
    [
        ("warrior.png", "warrior", True),
        ("warrior__idle_0.png", "warrior", True),
        ("warrior.tres", "warrior", True),
        ("warrior_red.png", "warrior", False),
        ("warrior_red__idle_0.png", "warrior", False),
        ("warrior_red.png", "warrior_red", True),
        ("warrior_red__idle_0.png", "warrior_red", True),
        ("warriors.png", "warrior", False),
        ("atlas.png", "warrior", False),
        ("atlas.json", "warrior", False),
        ("sprites.json", "warrior", False),
        ("sprites.json", "sprite", False),
    ],
)
def test_a_file_belongs_to_the_id_before_its_first_dot_or_double_underscore(name, sprite_id, expected):
    assert manifest.belongs_to(name, frozenset({sprite_id})) is expected


def test_a_file_belongs_to_any_of_several_ids_and_to_none_of_no_ids():
    assert manifest.belongs_to("goblin.png", frozenset({"warrior", "goblin"}))
    assert not manifest.belongs_to("goblin.png", frozenset())


def unowned_plans(out: Path, *names: str) -> list[manifest.Plan]:
    """A plan for `names` in `out`, each of which is already there and unowned."""
    for name in names:
        (out / name).write_bytes(b"hand made")
    return manifest.plan([(frames_target(out), {name: b"new" for name in names})])


def test_ownership_passes_when_every_unowned_file_belongs_to_an_adopted_id(tmp_path):
    plans = unowned_plans(tmp_path, "goblin.png", "warrior.png", "warrior__idle_0.png")
    manifest.check_ownership(plans, frozenset({"warrior", "goblin"}))


def test_ownership_names_the_one_file_no_adopted_id_covers(tmp_path):
    plans = unowned_plans(tmp_path, "goblin.png", "warrior.png")
    with pytest.raises(ConfigError) as excinfo:
        manifest.check_ownership(plans, frozenset({"goblin"}))
    assert str(excinfo.value) == (
        f"{tmp_path / 'warrior.png'} already exists and was not written by sprite-tool"
        " (use --adopt <id>... for those sprites, or --adopt for all)"
    )


def test_ownership_counts_only_the_files_no_adopted_id_covers(tmp_path):
    plans = unowned_plans(tmp_path, "atlas.png", "goblin.png", "warrior.png", "warrior_red.png", "sprites.json")
    with pytest.raises(ConfigError) as excinfo:
        manifest.check_ownership(plans, frozenset({"warrior"}))
    assert str(excinfo.value) == (
        f"{tmp_path / 'atlas.png'} and 3 more already exist and were not written by sprite-tool"
        " (use --adopt <id>... for those sprites, or --adopt for all)"
    )


def test_ownership_with_no_ids_adopts_nothing(tmp_path):
    plans = unowned_plans(tmp_path, "goblin.png")
    for adopt_ids in (None, frozenset()):
        with pytest.raises(ConfigError, match="goblin.png already exists"):
            manifest.check_ownership(plans, adopt_ids)


def test_ownership_with_ids_is_checked_in_every_directory(tmp_path):
    (tmp_path / "one").mkdir()
    (tmp_path / "two").mkdir()
    (tmp_path / "one" / "warrior.png").write_bytes(b"hand made")
    (tmp_path / "two" / "goblin.png").write_bytes(b"hand made")
    plans = manifest.plan(
        [
            (frames_target(tmp_path / "one"), {"warrior.png": b"W"}),
            (frames_target(tmp_path / "two"), {"goblin.png": b"G"}),
        ]
    )
    with pytest.raises(ConfigError, match="goblin.png already exists"):
        manifest.check_ownership(plans, frozenset({"warrior"}))


# --- shared directories -----------------------------------------------------


def test_two_targets_producing_the_same_file_in_one_directory_is_an_error(tmp_path):
    with pytest.raises(ConfigError) as excinfo:
        manifest.plan(
            [(frames_target(tmp_path), {"atlas.png": b"A"}), (atlas_target(tmp_path), {"atlas.png": b"B"})]
        )
    message = str(excinfo.value)
    assert "frames" in message and "phaser:atlas" in message and "atlas.png" in message
    assert not tmp_path.joinpath(MANIFEST_NAME).exists()


def test_the_same_file_name_in_different_directories_is_fine(tmp_path):
    plans = manifest.plan(
        [(frames_target(tmp_path / "one"), {"a.png": b"A"}), (frames_target(tmp_path / "two"), {"a.png": b"B"})]
    )
    assert len(plans) == 2


# --- a damaged manifest -----------------------------------------------------

BAD_MANIFESTS = {
    "not json": "{",
    "not an object": "[]",
    "wrong version": '{"targets": {}, "version": 2}',
    "no targets": '{"version": 1}',
    "targets not lists": '{"targets": {"frames": "a.png"}, "version": 1}',
    "entry not a string": '{"targets": {"frames": [1]}, "version": 1}',
    "entry leaves the directory": '{"targets": {"frames": ["../precious.txt"]}, "version": 1}',
    "entry is absolute": '{"targets": {"frames": ["/etc/hosts"]}, "version": 1}',
    "entry is the manifest": '{"targets": {"frames": ["%s"]}, "version": 1}' % MANIFEST_NAME,
}


@pytest.mark.parametrize("text", BAD_MANIFESTS.values(), ids=BAD_MANIFESTS.keys())
def test_a_manifest_that_cannot_be_trusted_stops_the_build(tmp_path, text):
    out = tmp_path / "out"
    out.mkdir()
    (out / MANIFEST_NAME).write_text(text, encoding="utf-8")
    (tmp_path / "precious.txt").write_text("keep")

    with pytest.raises(ConfigError) as excinfo:
        build(out, {"a.png": b"A"})

    assert MANIFEST_NAME in str(excinfo.value)
    assert (tmp_path / "precious.txt").read_text() == "keep"
    assert not (out / "a.png").exists()


# --- compare (build --check) ------------------------------------------------


def compare(out: Path, files: dict[str, bytes]) -> list[tuple[str, str, str]]:
    problems = manifest.compare(manifest.plan([(frames_target(out), files)]))
    assert all((problem.line, problem.col) == (0, 0) for problem in problems)
    return [(problem.path.relative_to(out).as_posix(), problem.code, problem.message) for problem in problems]


def test_compare_is_clean_after_a_build(tmp_path):
    files = {"a.png": b"A", "b.png": b"B"}
    build(tmp_path, files)
    assert compare(tmp_path, files) == []


def test_compare_reports_everything_missing_before_the_first_build(tmp_path):
    out = tmp_path / "out"
    assert compare(out, {"a.png": b"A"}) == [
        (MANIFEST_NAME, "E401", "missing"),
        ("a.png", "E401", "missing"),
    ]
    assert not out.exists()


def test_compare_reports_missing_stale_and_no_longer_generated(tmp_path):
    build(tmp_path, {"a.png": b"A", "b.png": b"B", "c.png": b"C", "d.png": b"D"})
    (tmp_path / "a.png").unlink()
    before = tree(tmp_path)

    assert compare(tmp_path, {"a.png": b"A", "b.png": b"changed", "c.png": b"C"}) == [
        (MANIFEST_NAME, "E401", "stale"),
        ("a.png", "E401", "missing"),
        ("b.png", "E401", "stale"),
        ("d.png", "E401", "no longer generated"),
    ]
    assert tree(tmp_path) == before


def test_compare_ignores_files_the_tool_does_not_own(tmp_path):
    build(tmp_path, {"a.png": b"A"})
    (tmp_path / "notes.txt").write_text("mine")
    assert compare(tmp_path, {"a.png": b"A"}) == []
