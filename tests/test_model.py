import dataclasses
from pathlib import Path

import pytest

from sprite_tool.model import Canvas, Color, Problem, format_problem


def test_dataclasses_are_frozen():
    color = Color(key="k", rgba=(26, 28, 44, 255), name="outline")
    with pytest.raises(dataclasses.FrozenInstanceError):
        color.key = "w"


def test_canvas_fields():
    canvas = Canvas(
        name="unit",
        width=32,
        height=32,
        anchor=(16, 32),
        display_scale=2,
        outline=frozenset({"k"}),
        grounded=True,
    )
    assert (canvas.width, canvas.height, canvas.display_scale) == (32, 32, 2)


def test_format_problem_with_position(tmp_path):
    problem = Problem(
        path=tmp_path / "units" / "warrior.sprite.toml",
        line=9,
        col=14,
        code="E104",
        message="unknown palette key 'x'",
    )
    assert (
        format_problem(problem, tmp_path)
        == "units/warrior.sprite.toml:9:14: E104 unknown palette key 'x'"
    )


def test_format_problem_without_position(tmp_path):
    problem = Problem(
        path=tmp_path / "out" / "atlas.png",
        line=0,
        col=0,
        code="E401",
        message="generated file missing",
    )
    assert format_problem(problem, tmp_path) == "out/atlas.png: E401 generated file missing"


def test_format_problem_outside_root_prints_path_as_given(tmp_path):
    root = tmp_path / "project"
    outside = tmp_path / "elsewhere" / "hero.png"
    problem = Problem(path=outside, line=0, col=0, code="E301", message="wrong size")
    assert format_problem(problem, root) == f"{outside}: E301 wrong size"


def test_format_problem_relative_path_outside_root_is_unchanged(tmp_path):
    problem = Problem(
        path=Path("../art/hero.png"), line=0, col=0, code="E301", message="wrong size"
    )
    assert format_problem(problem, tmp_path) == "../art/hero.png: E301 wrong size"
