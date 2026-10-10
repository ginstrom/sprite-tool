import subprocess
import sys
from importlib import metadata

import pytest

from conftest import VALID_CONFIG, write_project
from sprite_tool import cli
from sprite_tool.cli import main

SUBCOMMANDS = ["init", "guide", "new", "check", "preview", "build", "import"]

def test_help_lists_all_subcommands(capsys):
    with pytest.raises(SystemExit) as excinfo:
        main(["--help"])
    assert excinfo.value.code == 0
    out = capsys.readouterr().out
    for name in SUBCOMMANDS:
        assert name in out


def test_version_matches_the_package_metadata(capsys):
    with pytest.raises(SystemExit) as excinfo:
        main(["--version"])
    assert excinfo.value.code == 0
    assert capsys.readouterr().out == f"sprite {metadata.version('sprite-tool')}\n"


def test_parsed_arguments():
    args = cli.build_parser().parse_args(
        ["import", "hero.png", "--canvas", "unit", "--id", "hero", "--scale", "4", "--snap"]
    )
    assert (args.png, args.canvas, args.id, args.scale, args.snap, args.project) == (
        "hero.png", "unit", "hero", 4, True, None,
    )  # fmt: skip
    args = cli.build_parser().parse_args(["preview", "a", "b", "--on", "grass"])
    assert (args.ids, args.on, args.scale, args.grid, args.sheet) == (["a", "b"], "grass", None, False, False)
    args = cli.build_parser().parse_args(["check", "x.png", "--canvas", "tile"])
    assert (args.paths, args.canvas) == (["x.png"], "tile")
    args = cli.build_parser().parse_args(["build"])
    assert (args.check, args.adopt) == (False, None)
    assert cli.build_parser().parse_args(["build", "--adopt"]).adopt == []
    assert cli.build_parser().parse_args(["build", "--adopt", "a", "b", "--check"]).adopt == ["a", "b"]
    args = cli.build_parser().parse_args(["new", "orc", "--canvas", "unit"])
    assert (args.id, args.canvas, args.dir) == ("orc", "unit", None)
    assert cli.build_parser().parse_args(["init"]).dir == "."


USAGE_ERRORS = {
    "no subcommand": [],
    "unknown subcommand": ["paint"],
    "unknown flag": ["build", "--fast"],
    "new without canvas": ["new", "orc"],
    "new without id": ["new", "--canvas", "unit"],
    "import without canvas": ["import", "hero.png"],
    "import without png": ["import", "--canvas", "unit"],
    "scale not an integer": ["preview", "--scale", "big"],
    "scale zero": ["preview", "--scale", "0"],
    "init takes no project": ["init", "--project", "p"],
}


@pytest.mark.parametrize("argv", USAGE_ERRORS.values(), ids=USAGE_ERRORS.keys())
def test_usage_errors_exit_2(argv, capsys):
    with pytest.raises(SystemExit) as excinfo:
        main(argv)
    assert excinfo.value.code == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err != ""


def test_import_help_says_scale_enlarges_the_png(capsys):
    with pytest.raises(SystemExit):
        main(["import", "--help"])
    out = " ".join(capsys.readouterr().out.split())
    assert "enlarge the PNG N times before importing" in out
    assert "shrink" not in out


# --- project resolution helper ---------------------------------------------


@pytest.fixture
def build_loads_project(monkeypatch):
    """Replace the `build` stub with a handler that only resolves the project."""
    loaded = []

    def handler(args):
        loaded.append(cli.load_project(args))
        return 0

    monkeypatch.setitem(cli.HANDLERS, "build", handler)
    return loaded


def test_no_project_found_exits_2(tmp_path, monkeypatch, capsys, build_loads_project):
    monkeypatch.chdir(tmp_path)
    assert main(["build"]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("error: ")
    assert "sprite-tool.toml" in captured.err
    assert captured.err.count("\n") == 1


def test_project_is_found_from_a_subdirectory(project_dir, monkeypatch, build_loads_project):
    nested = project_dir / "units"
    nested.mkdir()
    monkeypatch.chdir(nested)

    assert main(["build"]) == 0
    project, problems = build_loads_project[0]
    assert project.root == project_dir
    assert problems == []


def test_project_flag_overrides_the_current_directory(project_dir, tmp_path, monkeypatch, build_loads_project):
    monkeypatch.chdir(tmp_path)
    assert main(["build", "--project", str(project_dir)]) == 0
    assert build_loads_project[0][0].root == project_dir


def test_project_flag_does_not_walk_up(project_dir, monkeypatch, capsys, build_loads_project):
    nested = project_dir / "units"
    nested.mkdir()
    assert main(["build", "--project", str(nested)]) == 2
    assert "sprite-tool.toml" in capsys.readouterr().err


def test_config_error_exits_2_with_message_on_stderr(tmp_path, capsys, build_loads_project):
    root = write_project(tmp_path, VALID_CONFIG.replace("version = 1", "version = 2"))
    assert main(["build", "--project", str(root)]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("error: ")
    assert "version" in captured.err


def test_palette_problems_are_returned_to_the_handler(tmp_path, build_loads_project):
    root = write_project(tmp_path, palette='[colors]\nab = "#000000"\n')
    assert main(["build", "--project", str(root)]) == 0
    _, problems = build_loads_project[0]
    assert [p.code for p in problems] == ["E002"]


# --- installed entry points -------------------------------------------------


def test_python_dash_m_runs_the_cli(tmp_path):
    result = subprocess.run(
        [sys.executable, "-m", "sprite_tool", "build"], cwd=tmp_path, capture_output=True, text=True
    )
    assert result.returncode == 2
    assert result.stdout == ""
    assert result.stderr.startswith("error: ")
