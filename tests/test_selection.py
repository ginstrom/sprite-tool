"""Which sprites a target exports: `canvases`, `include` and `exclude`."""

import json
import shutil
from dataclasses import replace
from pathlib import Path

import pytest

from conftest import MINIMAL_CONFIG, make_frame, make_sprite, write_project
from sprite_tool.cli import main
from sprite_tool.export import select
from sprite_tool.model import ExportTarget
from sprite_tool.project import ConfigError, load

DEMO = Path(__file__).parent.parent / "examples" / "demo"

FRAMES = '\n[[export]]\ntype = "frames"\nout = "out/frames"\n'
PHASER = '\n[[export]]\ntype = "phaser"\nout = "out/phaser"\nname = "atlas"\n'


def set_exports(root: Path, exports: str) -> None:
    """Replace every `[[export]]` block in the project's config with `exports`."""
    config = root / "sprite-tool.toml"
    kept = config.read_text(encoding="utf-8").split("[[export]]")[0].rstrip()
    config.write_text(f"{kept}\n{exports}", encoding="utf-8")


@pytest.fixture
def demo(tmp_path: Path, monkeypatch) -> Path:
    """A copy of the demo project, with its three targets, as the current directory."""
    root = tmp_path / "demo"
    shutil.copytree(DEMO, root, ignore=shutil.ignore_patterns("out", ".preview"))
    monkeypatch.chdir(root)
    return root


def build(capsys, *flags: str) -> tuple[int, list[str]]:
    code = main(["build", *flags])
    return code, capsys.readouterr().out.splitlines()


def atlas_ids(root: Path) -> set[str]:
    atlas = json.loads((root / "out" / "phaser" / "atlas.json").read_text(encoding="utf-8"))
    return {key.split("/")[0] for key in atlas["frames"]}


def frames_ids(root: Path) -> list[str]:
    return sorted(json.loads((root / "out" / "frames" / "sprites.json").read_text(encoding="utf-8")))


# --- select -------------------------------------------------------------------


def target(**selection) -> ExportTarget:
    return ExportTarget(type="frames", out=Path("/nowhere"), name="sprites", res_path=None, padding=0, **selection)


def sprites():
    """`gear_sword`, its variant and `warrior` on `unit`; `gear_icon` and `ground` on `tile`."""
    made = [make_sprite(name, make_frame("main", "k")) for name in ("gear_icon", "gear_sword", "ground", "warrior")]
    unit = replace(made[0].canvas, name="unit")
    tile = replace(made[0].canvas, name="tile")
    classes = {"gear_icon": tile, "gear_sword": unit, "ground": tile, "warrior": unit}
    made = [replace(sprite, canvas=classes[sprite.id]) for sprite in made]
    ember = replace(made[1], id="gear_sword_ember", variant_of="gear_sword")
    return [*made, ember]


def selected(**selection) -> list[str]:
    return sorted(sprite.id for sprite in select(sprites(), target(**selection)))


def test_a_target_with_no_selection_exports_every_sprite():
    assert selected() == ["gear_icon", "gear_sword", "gear_sword_ember", "ground", "warrior"]


def test_canvases_selects_by_class():
    assert selected(canvases=frozenset({"unit"})) == ["gear_sword", "gear_sword_ember", "warrior"]
    assert selected(canvases=frozenset({"unit", "tile"})) == selected()


def test_include_selects_by_id_pattern_and_a_variant_is_matched_by_its_own_id():
    assert selected(include=("gear_*",)) == ["gear_icon", "gear_sword", "gear_sword_ember"]
    assert selected(include=("*_ember",)) == ["gear_sword_ember"]
    assert selected(include=("warrior", "gr?und")) == ["ground", "warrior"]
    # The whole id, and case as written.
    assert selected(include=("gear",)) == []
    assert selected(include=("WARRIOR",)) == []


def test_exclude_drops_by_id_pattern():
    assert selected(exclude=("gear_*",)) == ["ground", "warrior"]
    assert selected(exclude=("[gw]*",)) == []


def test_the_three_keys_together_must_all_agree():
    assert selected(canvases=frozenset({"unit"}), include=("gear_*",), exclude=("*_ember",)) == ["gear_sword"]


# --- A38: config --------------------------------------------------------------


def config_error(tmp_path: Path, lines: str) -> str:
    root = write_project(tmp_path / "p", MINIMAL_CONFIG + FRAMES + PHASER + lines)
    with pytest.raises(ConfigError) as error:
        load(root)
    return str(error.value)


def test_the_selection_keys_are_loaded(tmp_path):
    lines = 'canvases = ["unit"]\ninclude = ["gear_*", "warrior"]\nexclude = ["sample_*"]\n'
    project, _ = load(write_project(tmp_path / "p", MINIMAL_CONFIG + FRAMES + PHASER + lines))
    plain, chosen = project.exports
    assert (plain.canvases, plain.include, plain.exclude) == (None, None, ())
    assert (chosen.canvases, chosen.include, chosen.exclude) == (
        frozenset({"unit"}),
        ("gear_*", "warrior"),
        ("sample_*",),
    )


def test_an_empty_exclude_is_allowed(tmp_path):
    project, _ = load(write_project(tmp_path / "p", MINIMAL_CONFIG + FRAMES + "exclude = []\n"))
    assert project.exports[0].exclude == ()


@pytest.mark.parametrize(
    "lines, message",
    [
        (
            'canvases = ["nosuch"]\n',
            "sprite-tool.toml: export 2: canvases names unknown canvas class 'nosuch' (expected one of unit)",
        ),
        ("include = []\n", "sprite-tool.toml: export 2: include must not be empty (it would select no sprite)"),
        ("canvases = []\n", "sprite-tool.toml: export 2: canvases must not be empty (it would select no sprite)"),
        ('include = "x"\n', "sprite-tool.toml: export 2: include must be a list of non-empty strings"),
        ('exclude = ["a", 3]\n', "sprite-tool.toml: export 2: exclude must be a list of non-empty strings"),
        ('canvases = [""]\n', "sprite-tool.toml: export 2: canvases must be a list of non-empty strings"),
    ],
)
def test_a38_a_bad_selection_names_the_export_and_the_key(tmp_path, lines, message):
    assert config_error(tmp_path, lines) == message


def test_a38_a_bad_selection_exits_2(tmp_path, capsys):
    root = write_project(tmp_path / "p", MINIMAL_CONFIG + FRAMES + "include = []\n")
    assert main(["check", "--project", str(root)]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "error: sprite-tool.toml: export 1: include must not be empty (it would select no sprite)\n"


# --- A36, A37: builds ---------------------------------------------------------


def edit_config(root: Path, old: str, new: str) -> None:
    config = root / "sprite-tool.toml"
    text = config.read_text(encoding="utf-8")
    assert old in text
    config.write_text(text.replace(old, new), encoding="utf-8")


def test_a36_canvases_on_one_target_leaves_the_others_whole(demo, capsys):
    edit_config(demo, 'out = "out/phaser"\n', 'out = "out/phaser"\ncanvases = ["unit"]\n')
    assert build(capsys) == (0, ["built: 5 sprites, 7 frames, 3 targets"])
    assert atlas_ids(demo) == {"goblin", "slime", "warrior", "warrior_red"}
    assert frames_ids(demo) == ["goblin", "ground_light", "slime", "warrior", "warrior_red"]
    assert (demo / "out" / "godot" / "ground_light.tres").is_file()


def test_a37_a_sprite_dropped_from_a_target_is_stale_and_then_removed(demo, capsys):
    set_exports(demo, FRAMES + PHASER)
    assert build(capsys) == (0, ["built: 5 sprites, 7 frames, 2 targets"])
    assert (demo / "out" / "frames" / "slime.png").is_file()

    edit_config(demo, 'out = "out/frames"\n', 'out = "out/frames"\nexclude = ["slime*"]\n')
    code, lines = build(capsys, "--check")
    assert code == 1
    assert "out/frames/slime.png: E401 no longer generated" in lines
    assert not any(line.startswith("out/phaser/") for line in lines)

    assert build(capsys) == (0, ["built: 5 sprites, 7 frames, 2 targets"])
    assert not (demo / "out" / "frames" / "slime.png").exists()
    assert "slime" not in frames_ids(demo)
    assert "slime" in atlas_ids(demo)
    assert build(capsys, "--check") == (0, ["up to date: 5 sprites, 7 frames, 2 targets"])


def test_the_summary_counts_the_sprites_some_target_exports(demo, capsys):
    set_exports(demo, FRAMES + 'canvases = ["tile"]\n')
    code, lines = build(capsys)
    assert code == 0
    assert lines[-1] == "built: 1 sprite, 1 frame, 1 target"
    assert frames_ids(demo) == ["ground_light"]


def test_adopt_takes_only_the_id_of_a_sprite_some_target_exports(demo, capsys):
    set_exports(demo, FRAMES + 'canvases = ["tile"]\n')
    assert main(["build", "--adopt", "goblin"]) == 2
    assert capsys.readouterr().err == "error: unknown sprite id 'goblin' (sprites: ground_light)\n"


# --- A39: warnings ------------------------------------------------------------


def test_a39_a_pattern_that_matches_no_sprite_is_w004(demo, capsys):
    set_exports(demo, FRAMES + PHASER + 'include = ["gaer_*", "warrior*"]\nexclude = ["nothing"]\n')
    assert main(["check"]) == 0
    assert capsys.readouterr().out.splitlines() == [
        "sprite-tool.toml: W004 export 2 (phaser): include pattern 'gaer_*' matches no sprite",
        "sprite-tool.toml: W004 export 2 (phaser): exclude pattern 'nothing' matches no sprite",
        "ok: 6 sprites, 8 frames",
    ]


def test_a39_a_sprite_in_no_target_is_w005_at_its_file(demo, capsys):
    set_exports(demo, FRAMES + 'canvases = ["unit"]\nexclude = ["warrior_red"]\n')
    assert main(["check"]) == 0
    assert capsys.readouterr().out.splitlines() == [
        "tiles/ground_light.sprite.toml: W005 sprite 'ground_light' is in no export target;"
        " set build = false if that is meant",
        "units/warrior.sprite.toml: W005 sprite 'warrior_red' is in no export target;"
        " set build = false if that is meant",
        "ok: 6 sprites, 8 frames",
    ]
    # A warning does not stop the build either.
    code, lines = build(capsys)
    assert (code, lines[-1]) == (0, "built: 3 sprites, 4 frames, 1 target")


def test_a_sprite_that_is_not_built_is_not_w005(demo, capsys):
    """`sample_slime` says `build = false`, and `include` leaves it out as well."""
    set_exports(demo, FRAMES + 'exclude = ["sample_*"]\n')
    assert main(["check"]) == 0
    assert capsys.readouterr().out == "ok: 6 sprites, 8 frames\n"


def test_no_w005_without_a_selection_or_without_targets(demo, capsys):
    assert main(["check"]) == 0
    assert capsys.readouterr().out == "ok: 6 sprites, 8 frames\n"
    set_exports(demo, "")
    assert main(["check"]) == 0
    assert capsys.readouterr().out == "ok: 6 sprites, 8 frames\n"
