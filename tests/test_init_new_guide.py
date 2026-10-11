import tomllib
from importlib import resources
from pathlib import Path

import pytest

from conftest import write_project
from sprite_tool import __version__
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
    assert captured.out.splitlines()[0] == "created . (3 files)"
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
    assert capsys.readouterr().out.splitlines()[0] == "created art/sprites (3 files)"
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
    assert capsys.readouterr().out.splitlines()[0] == "created . (3 files)"
    assert (empty / ".gitignore").read_text(encoding="utf-8") == "node_modules/\n"


@pytest.mark.parametrize(("argv", "command"), [(["init"], "sprite guide"), (["init", "art"], "sprite guide --project art")])
def test_init_prints_the_note_for_agents(empty, capsys, argv, command):
    assert main(argv) == 0
    lines = capsys.readouterr().out.splitlines()
    assert len(lines) == 2
    assert lines[1].startswith("for agents, add to AGENTS.md: ")
    assert f"git+https://github.com/ginstrom/sprite-tool@v{__version__}`" in lines[1]
    assert f"`{command}`" in lines[1]

    # The command in the note works from where `init` was run.
    assert main(command.split()[1:]) == 0


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


# --- new ----------------------------------------------------------------------


@pytest.fixture
def project(empty: Path, capsys) -> Path:
    """A freshly initialised project, as the current directory."""
    assert main(["init"]) == 0
    capsys.readouterr()
    return empty


def test_new_writes_a_blank_unit_and_prints_its_path(project, capsys):
    assert main(["new", "kobold", "--canvas", "unit", "--dir", "units"]) == 0
    captured = capsys.readouterr()
    assert captured.out == "units/kobold.sprite.toml\n"
    assert captured.err == ""

    text = (project / "units" / "kobold.sprite.toml").read_text(encoding="utf-8")
    data = tomllib.loads(text)
    assert data == {"canvas": "unit", "frames": {"main": ("." * 32 + "\n") * 32}}
    assert text.endswith('"""\n')


def test_a_new_sprite_checks_with_a_blank_warning_only(project, capsys):
    assert main(["new", "kobold", "--canvas", "unit", "--dir", "units"]) == 0
    path = capsys.readouterr().out.strip()

    assert main(["check", path]) == 0
    assert capsys.readouterr().out.splitlines() == [
        "units/kobold.sprite.toml:5:1: W003 sprite 'kobold' is blank (nothing drawn yet); it is left out of the build",
        "ok: 1 sprite, 1 frame",
    ]


def test_a_new_sprite_does_not_stop_the_build_and_is_not_exported(project, capsys):
    assert main(["new", "kobold", "--canvas", "unit"]) == 0
    capsys.readouterr()

    assert main(["build"]) == 0
    assert capsys.readouterr().out.splitlines() == [
        "kobold.sprite.toml:5:1: W003 sprite 'kobold' is blank (nothing drawn yet); it is left out of the build",
        "built: 2 sprites, 4 frames, 1 target",
    ]
    assert not list((project / "out").glob("kobold*"))


def test_new_tile_is_16_rows_of_16_in_the_project_root(project, capsys):
    assert main(["new", "grass", "--canvas", "tile"]) == 0
    assert capsys.readouterr().out == "grass.sprite.toml\n"
    rows = tomllib.loads((project / "grass.sprite.toml").read_text(encoding="utf-8"))["frames"]["main"]
    assert rows.splitlines() == ["." * 16] * 16


def test_new_creates_the_subdirectory(project, capsys):
    assert main(["new", "spark", "--canvas", "tile", "--dir", "effects/small"]) == 0
    assert capsys.readouterr().out == "effects/small/spark.sprite.toml\n"
    assert (project / "effects" / "small" / "spark.sprite.toml").is_file()


def test_new_dir_is_relative_to_the_project_not_the_current_directory(project, tmp_path, monkeypatch, capsys):
    (project / "units").mkdir(exist_ok=True)
    monkeypatch.chdir(project / "units")
    assert main(["new", "grass", "--canvas", "tile", "--dir", "tiles"]) == 0
    assert capsys.readouterr().out == "../tiles/grass.sprite.toml\n"
    assert (project / "tiles" / "grass.sprite.toml").is_file()

    monkeypatch.chdir(tmp_path)
    assert main(["new", "bat", "--canvas", "unit", "--project", str(project)]) == 0
    assert capsys.readouterr().out == "game/bat.sprite.toml\n"

    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    assert main(["new", "rat", "--canvas", "unit", "--project", str(project)]) == 0
    assert capsys.readouterr().out == f"{project / 'rat.sprite.toml'}\n"


NEW_REFUSALS = {
    "existing file": (["warrior", "--canvas", "unit", "--dir", "units"], "units/warrior.sprite.toml already exists"),
    "id used in another directory": (
        ["warrior", "--canvas", "unit"],
        "sprite id 'warrior' is already used by units/warrior.sprite.toml",
    ),
    "id used by a variant": (
        ["warrior_red", "--canvas", "unit"],
        "sprite id 'warrior_red' is already used by units/warrior.sprite.toml",
    ),
    "upper case id": (["Kobold", "--canvas", "unit"], "sprite id 'Kobold' must match [a-z0-9_]+"),
    "id with a path": (["units/kobold", "--canvas", "unit"], "sprite id 'units/kobold' must match [a-z0-9_]+"),
    "id with a trailing newline": (["kobold\n", "--canvas", "unit"], "sprite id 'kobold\\n' must match [a-z0-9_]+"),
    "empty id": (["", "--canvas", "unit"], "sprite id '' must match [a-z0-9_]+"),
    "unknown class": (["kobold", "--canvas", "boss"], "unknown canvas class 'boss' (expected one of unit, tile)"),
    "directory outside the project": (
        ["kobold", "--canvas", "unit", "--dir", "../elsewhere"],
        "--dir ../elsewhere is outside the project",
    ),
}


@pytest.mark.parametrize("argv, message", NEW_REFUSALS.values(), ids=NEW_REFUSALS.keys())
def test_new_refusals_exit_2_and_write_nothing(project, capsys, argv, message):
    before = files(project.parent)
    assert main(["new", *argv]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == f"error: {message}\n"
    assert files(project.parent) == before


def test_new_outside_a_project_exits_2(empty, capsys):
    assert main(["new", "kobold", "--canvas", "unit"]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "sprite-tool.toml" in captured.err
    assert files(empty) == {}


# --- guide --------------------------------------------------------------------


def guide(root: Path, capsys) -> str:
    assert main(["guide", "--project", str(root)]) == 0
    captured = capsys.readouterr()
    assert captured.err == ""
    return captured.out


def test_a13_demo_guide_is_short_and_lists_the_palette_and_canvas_classes(capsys):
    text = guide(DEMO, capsys)
    lines = text.splitlines()
    assert len(lines) < 60
    assert max(len(line) for line in lines) <= 100
    assert text.isascii()

    project, _ = load(DEMO)
    assert len(project.palette) == 16
    for color in project.palette.values():
        red, green, blue, _ = color.rgba
        assert f"{color.key} #{red:02x}{green:02x}{blue:02x} {color.name}" in text
    assert "unit  32x32  anchor 16,32  display scale 2  outline k, grounded" in lines
    assert "tile  16x16  anchor 0,0    display scale 4  no rules" in lines


def test_guide_prints_exactly_guide_text(capsys):
    from sprite_tool.guide import guide_text

    project, _ = load(DEMO)
    text = guide_text(project)
    assert guide(DEMO, capsys) == text
    assert text.endswith("\n") and not text.endswith("\n\n")
    assert all(line == line.rstrip() for line in text.splitlines())


@pytest.mark.parametrize(
    "phrase",
    [
        "'.' is transparent",
        "from =",
        "rows =",
        "shift =",
        "flip =",
        "in this order",
        "[anim.",
        "ms =",
        "[variants.",
        "swap =",
        "outline = false",
        "grounded = false",
        "count from 0",
        "sprite new <id> --canvas <class>",
        "sprite check",
        "sprite preview <id>... [--grid]",
        "sprite preview <id> --on <tile-id>",
        "sprite import <png> --canvas <class>",
        "facing right",
        "anchor x,y:",
        "default frame is",
        "[frames.idle_1.rows]",
        "sprite build",
    ],
)
def test_guide_covers_the_format_and_the_workflow(capsys, phrase):
    assert phrase in guide(DEMO, capsys)


def test_guide_example_is_a_valid_sprite_file_for_the_demo(tmp_path, capsys):
    """The example in the guide must not teach something `check` rejects."""
    import shutil

    from sprite_tool.guide import EXAMPLE

    root = tmp_path / "demo"
    shutil.copytree(DEMO, root, ignore=shutil.ignore_patterns("out", ".preview"))
    config = root / "sprite-tool.toml"
    config.write_text(
        config.read_text(encoding="utf-8") + '\n[canvas.icon]\nsize = [6, 4]\nanchor = [0, 0]\n', encoding="utf-8"
    )
    (root / "gem.sprite.toml").write_text(EXAMPLE.replace('canvas = "unit"', 'canvas = "icon"'), encoding="utf-8")
    assert EXAMPLE in guide(root, capsys)

    assert main(["check", "--project", str(root)]) == 0
    assert capsys.readouterr().out == "ok: 8 sprites, 12 frames\n"


def test_guide_reflects_the_project(tmp_path, capsys):
    config = """\
version = 1

[canvas.boss]
size = [48, 64]
anchor = [24, 64]
outline = ["k", "w"]

[canvas.fx]
size = [8, 8]
anchor = [4, 4]
display_scale = 3
grounded = true
"""
    palette = '[colors]\nk = { hex = "#1a1c2c", name = "outline" }\nw = "#f4f4f4"\ng = "#00ff0080"\n'
    root = write_project(tmp_path / "p", config, palette)
    lines = guide(root, capsys).splitlines()

    assert "boss  48x64  anchor 24,64  display scale 1  outline k w" in lines
    assert "fx    8x8    anchor 4,4    display scale 3  grounded" in lines
    legend = " ".join(" ".join(lines).split())
    assert "k #1a1c2c outline" in legend
    assert "w #f4f4f4" in legend
    assert "g #00ff0080" in legend


def test_guide_with_a_bad_palette_reports_it_and_exits_1(tmp_path, capsys):
    root = write_project(tmp_path / "p", palette='[colors]\nab = "#000000"\n')
    assert main(["guide", "--project", str(root)]) == 1
    out = capsys.readouterr().out.splitlines()
    assert out[0].startswith("palette.toml:2:1: E002 ")
    assert out[-1] == "1 error, 0 warnings in 1 file"
    assert len(out) == 2


def test_guide_outside_a_project_exits_2(empty, capsys):
    assert main(["guide"]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("error: ")
    assert "sprite-tool.toml" in captured.err


def test_guide_covers_what_the_agent_trial_had_to_guess(capsys):
    text = " ".join(guide(DEMO, capsys).split())
    assert "Diagonals do not count, so a part 1 or 2 pixels wide is all outline" in text
    assert "Sprite files may be anywhere in the project" in text
    assert "A replacement row is a full row" in text
    assert "Frame names are free" in text
