import tomllib
from importlib import resources
from pathlib import Path

import pytest

from sprite_tool.cli import main
from sprite_tool.project import load

DEMO = Path(__file__).parent.parent / "examples" / "demo"

INIT_FILES = [".gitignore", "palette.toml", "sprite-tool.toml", "units/warrior.sprite.toml"]


def files(root: Path) -> dict[str, bytes]:
    """Every file under `root`, by relative path."""
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


@pytest.fixture
def empty(tmp_path: Path, monkeypatch) -> Path:
    """An empty directory, made the current directory."""
    root = tmp_path / "game"
    root.mkdir()
    monkeypatch.chdir(root)
    return root


# --- init ---------------------------------------------------------------------


def test_a1_init_then_build_in_an_empty_directory(empty, capsys):
    assert main(["init"]) == 0
    captured = capsys.readouterr()
    assert captured.out == "created . (3 files)\n"
    assert captured.err == ""

    assert main(["build"]) == 0
    assert capsys.readouterr().out == "built: 2 sprites, 4 frames, 1 target\n"
    assert list((empty / "out").glob("*.png"))


def test_init_writes_four_files(empty):
    assert main(["init"]) == 0
    assert sorted(files(empty)) == INIT_FILES
    assert (empty / ".gitignore").read_text(encoding="utf-8") == ".preview/\n"


def test_init_creates_the_named_directory(empty, capsys):
    assert main(["init", "art/sprites"]) == 0
    assert capsys.readouterr().out == "created art/sprites (3 files)\n"
    assert sorted(files(empty / "art" / "sprites")) == INIT_FILES
    assert sorted(files(empty)) == [f"art/sprites/{name}" for name in INIT_FILES]


def test_second_init_exits_2_and_changes_nothing(empty, capsys):
    assert main(["init"]) == 0
    (empty / "palette.toml").write_text("# edited\n", encoding="utf-8")
    before = files(empty)
    capsys.readouterr()

    assert main(["init"]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "error: sprite-tool.toml already exists\n"
    assert files(empty) == before


@pytest.mark.parametrize("existing", ["palette.toml", "units/warrior.sprite.toml"])
def test_init_does_not_overwrite_other_files(empty, capsys, existing):
    path = empty / existing
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("mine\n", encoding="utf-8")

    assert main(["init"]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == f"error: {existing} already exists\n"
    assert files(empty) == {existing: b"mine\n"}


def test_init_refusal_names_the_directory(empty, capsys):
    assert main(["init", "sprites"]) == 0
    capsys.readouterr()
    assert main(["init", "sprites"]) == 2
    assert capsys.readouterr().err == "error: sprites/sprite-tool.toml already exists\n"


def test_init_leaves_an_existing_gitignore_alone(empty, capsys):
    (empty / ".gitignore").write_text("node_modules/\n", encoding="utf-8")
    assert main(["init"]) == 0
    assert capsys.readouterr().out == "created . (3 files)\n"
    assert (empty / ".gitignore").read_text(encoding="utf-8") == "node_modules/\n"


def test_init_on_a_file_exits_2(empty, capsys):
    (empty / "sprites").write_text("", encoding="utf-8")
    assert main(["init", "sprites"]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("error: ")
    assert files(empty) == {"sprites": b""}


def test_new_project_passes_check(empty, capsys):
    assert main(["init"]) == 0
    capsys.readouterr()
    assert main(["check"]) == 0
    assert capsys.readouterr().out == "ok: 2 sprites, 4 frames\n"


def test_template_config(empty):
    assert main(["init"]) == 0
    project, problems = load(empty)
    assert problems == []
    assert project.palette_path == empty / "palette.toml"

    unit, tile = project.canvases["unit"], project.canvases["tile"]
    assert list(project.canvases) == ["unit", "tile"]
    assert (unit.width, unit.height, unit.anchor, unit.display_scale) == (32, 32, (16, 32), 2)
    assert (unit.outline, unit.grounded) == (frozenset({"k"}), True)
    assert (tile.width, tile.height, tile.anchor, tile.display_scale) == (16, 16, (0, 0), 4)
    assert (tile.outline, tile.grounded) == (None, False)
    assert (project.preview.scale, project.preview.background) == (6, (0x3A, 0x3A, 0x3A, 255))
    assert [(target.type, target.out) for target in project.exports] == [("frames", empty / "out")]

    text = (empty / "sprite-tool.toml").read_text(encoding="utf-8")
    assert tomllib.loads(text)["palette"] == "palette.toml"
    assert '# type = "phaser"' in text
    assert '# type = "godot"' in text


def test_commented_out_export_hints_are_valid_config(empty):
    assert main(["init"]) == 0
    config = empty / "sprite-tool.toml"
    lines = config.read_text(encoding="utf-8").splitlines()
    start = next(index for index, line in enumerate(lines) if line == "# [[export]]")
    enabled = [line[2:] if line.startswith("# ") else line for line in lines[start:]]
    config.write_text("\n".join(lines[:start] + enabled) + "\n", encoding="utf-8")

    project, _ = load(empty)
    assert [target.type for target in project.exports] == ["frames", "phaser", "godot"]


TEMPLATE_COPIES = {"palette.toml": "palette.toml", "warrior.sprite.toml": "units/warrior.sprite.toml"}


@pytest.mark.parametrize("template", TEMPLATE_COPIES)
def test_templates_match_the_demo(template):
    packaged = resources.files("sprite_tool").joinpath("templates", template).read_bytes()
    assert packaged == (DEMO / TEMPLATE_COPIES[template]).read_bytes()


@pytest.mark.parametrize("name", ["sprite-tool.toml", "palette.toml", "warrior.sprite.toml", "gitignore"])
def test_templates_ship_in_the_package(name):
    assert resources.files("sprite_tool").joinpath("templates", name).read_text(encoding="utf-8")
