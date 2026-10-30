"""Named points: `[points]`, `[frame_points]`, how derived frames carry them, and their exports."""

import json
from pathlib import Path

import pytest

from conftest import write_project
from sprite_tool import render
from sprite_tool.cli import main
from sprite_tool.export import frames as frames_export
from sprite_tool.export import godot as godot_export
from sprite_tool.export import phaser as phaser_export
from sprite_tool.model import ExportTarget, format_problem
from sprite_tool.project import load
from sprite_tool.spritefile import load_all

CONFIG = """\
version = 1

[canvas.unit]
size = [32, 32]
anchor = [16, 32]

[canvas.tiny]
size = [6, 5]
anchor = [0, 0]
"""

PALETTE = """\
[colors]
k = "#000000"
w = "#ffffff"
r = "#ff0000"
"""

# A 32x32 literal frame: a bar on row 31 and a pixel at the grip.
GRID = "\n".join(["." * 32] * 19 + ["." * 25 + "k" + "." * 6] + ["." * 32] * 11 + ["k" * 32])
WARRIOR = f'''\
canvas = "unit"

[points]
grip = [25, 19]

[frames]
idle_0 = """
{GRID}
"""
'''


@pytest.fixture
def project(tmp_path):
    loaded, problems = load(write_project(tmp_path / "sprites", CONFIG, PALETTE))
    assert problems == []
    return loaded


def load_text(project, text, name="warrior.sprite.toml"):
    path = project.root / name
    path.write_text(text, encoding="utf-8")
    sprites, problems = load_all(project, [path])
    return {sprite.id: sprite for sprite in sprites}, [format_problem(problem, project.root) for problem in problems]


def points_of(project, text, sprite_id="warrior"):
    """Each frame's points as a dict, by frame name, and the problems."""
    sprites, problems = load_text(project, text)
    sprite = sprites.get(sprite_id)
    found = {frame.name: dict(frame.points) for frame in sprite.frames} if sprite else {}
    return found, problems


def derived(body: str) -> str:
    return WARRIOR + f'\n[frames.next]\nfrom = "idle_0"\n{body}'


# --- A58: declaring, and the exports ------------------------------------------


def test_a58_a_literal_frame_has_the_sprites_points(project):
    found, problems = points_of(project, WARRIOR)
    assert problems == []
    assert found == {"idle_0": {"grip": (25, 19)}}


def target(kind: str, name: str) -> ExportTarget:
    # Exporters never touch the disk.
    return ExportTarget(type=kind, out=Path("/nowhere"), name=name, res_path="res://sprites", padding=1)


def exported(project, text, kind):
    sprites, problems = load_text(project, text)
    assert [problem for problem in problems if " E" in problem] == []
    chosen = sorted(sprites.values(), key=lambda sprite: sprite.id)
    images = render.render_all(chosen, project.palette)
    exporter = {"phaser": phaser_export, "frames": frames_export, "godot": godot_export}[kind]
    name = "sprites" if kind == "frames" else "atlas"
    return exporter.export(chosen, images, target(kind, name))


def test_a58_phaser_puts_the_points_on_the_frame_as_pixel_centres(project):
    atlas = json.loads(exported(project, WARRIOR, "phaser")["atlas.json"])
    assert atlas["frames"]["warrior/idle_0"]["points"] == {"grip": [25.5, 19.5]}


@pytest.mark.parametrize(("kind", "index"), [("frames", "sprites.json"), ("godot", "atlas.json")])
def test_a58_the_indexes_have_points_by_frame(project, kind, index):
    entry = json.loads(exported(project, WARRIOR, kind)[index])["warrior"]
    assert entry["points"] == {"idle_0": {"grip": [25.5, 19.5]}}


def test_points_are_written_in_name_order_and_only_for_frames_that_have_any(project):
    text = WARRIOR.replace("grip = [25, 19]\n", "grip = [25, 19]\nchest = [16, 15]\n")
    text += '\n[frames.bare]\nfrom = "idle_0"\nshift = [0, -20]\n'
    files = exported(project, text, "phaser")
    atlas = files["atlas.json"].decode("utf-8")
    assert atlas.index('"chest"') < atlas.index('"grip"')
    frames = json.loads(atlas)["frames"]
    # `shift` carried both points off the top of the canvas.
    assert "points" not in frames["warrior/bare"]
    index = json.loads(exported(project, text, "godot")["atlas.json"])["warrior"]
    assert list(index["points"]) == ["idle_0"]


@pytest.mark.parametrize("kind", ["phaser", "frames", "godot"])
def test_a64_a_sprite_without_points_exports_no_points_key(project, kind):
    files = exported(project, WARRIOR.replace("[points]\ngrip = [25, 19]\n", ""), kind)
    assert all(b'"points"' not in data for name, data in files.items() if name.endswith(".json"))


def test_a58_build_writes_the_points_into_every_target(tmp_path, capsys):
    config = CONFIG + (
        '\n[[export]]\ntype = "frames"\nout = "out/frames"\n'
        '\n[[export]]\ntype = "phaser"\nout = "out/phaser"\nname = "atlas"\n'
        '\n[[export]]\ntype = "godot"\nout = "out/godot"\nname = "atlas"\nres_path = "res://sprites"\n'
    )
    root = write_project(tmp_path / "game", config, PALETTE)
    (root / "warrior.sprite.toml").write_text(WARRIOR, encoding="utf-8")
    assert main(["build", "--project", str(root)]) == 0
    capsys.readouterr()
    atlas = json.loads((root / "out" / "phaser" / "atlas.json").read_text(encoding="utf-8"))
    assert atlas["frames"]["warrior/idle_0"]["points"] == {"grip": [25.5, 19.5]}
    for index in (root / "out" / "frames" / "sprites.json", root / "out" / "godot" / "atlas.json"):
        assert json.loads(index.read_text(encoding="utf-8"))["warrior"]["points"] == {"idle_0": {"grip": [25.5, 19.5]}}


# --- A59, A60: derived frames carry their parent's points ----------------------


@pytest.mark.parametrize(
    ("body", "grip"),
    [
        ("shift = [0, 1]", (25, 20)),
        ("flip = true", (6, 19)),
        ("move = { rows = [0, 23], by = [0, 1] }", (25, 20)),
        ('rows = { 19 = "' + "." * 32 + '" }', (25, 19)),
        ('runs = { 19 = [[25, "."]] }', (25, 19)),
        ("move = { rows = [0, 23], by = [0, 1] }\nshift = [2, 0]\nflip = true", (4, 20)),
    ],
)
def test_a59_a_derived_frame_carries_the_point_as_its_pixel_moves(project, body, grip):
    found, problems = points_of(project, derived(body))
    assert [problem for problem in problems if " E" in problem] == []
    assert found["next"] == {"grip": grip}


def test_a59_a_point_outside_a_move_stays_where_it_was(project):
    text = WARRIOR.replace("grip = [25, 19]\n", "grip = [25, 19]\nfoot = [12, 28]\n")
    text += '\n[frames.next]\nfrom = "idle_0"\nmove = { rows = [0, 23], by = [0, 1] }\n'
    found, _ = points_of(project, text)
    assert found["next"] == {"foot": (12, 28), "grip": (25, 20)}


def test_a_point_is_not_moved_by_pixels_moved_onto_it(project):
    """Row 24 is outside the move; row 23 lands on it. The point there stays."""
    text = WARRIOR.replace("grip = [25, 19]\n", "knee = [12, 24]\n")
    text += '\n[frames.next]\nfrom = "idle_0"\nmove = { rows = [0, 23], by = [0, 1] }\n'
    found, _ = points_of(project, text)
    assert found["next"] == {"knee": (12, 24)}


def test_a_grandchild_carries_the_childs_points(project):
    text = derived("shift = [0, 1]") + '\n[frames.last]\nfrom = "next"\nshift = [1, 0]\n'
    found, _ = points_of(project, text)
    assert found["last"] == {"grip": (26, 20)}


def test_a_derived_frame_with_no_from_has_the_sprites_points(project):
    text = WARRIOR + '\n[frames.drawn.runs]\n31 = [[0, "kkkk"]]\n'
    found, _ = points_of(project, text)
    assert found["drawn"] == {"grip": (25, 19)}


def test_a60_a_point_carried_off_the_canvas_is_dropped_with_w008_beside_w006(project):
    text = WARRIOR.replace("grip = [25, 19]\n", "grip = [25, 19]\nfoot = [3, 31]\n")
    text += '\n[frames.next]\nfrom = "idle_0"\nshift = [0, 1]\n\n[frames.after]\nfrom = "next"\nshift = [1, 0]\n'
    found, problems = points_of(project, text)
    assert found["next"] == {"grip": (25, 20)}
    assert found["after"] == {"grip": (26, 20)}
    assert problems == [
        "warrior.sprite.toml:43:1: W006 frame 'next': shift [0, 1] pushes 32 drawn pixels off the canvas",
        "warrior.sprite.toml:43:1: W008 frame 'next': shift [0, 1] takes point 'foot' off the canvas",
    ]


def test_w008_names_the_operation_that_dropped_the_point(project):
    text = WARRIOR.replace("grip = [25, 19]\n", "edge = [0, 2]\n")
    text += '\n[frames.next]\nfrom = "idle_0"\nmove = { cols = [0, 3], by = [-1, 0] }\n'
    _, problems = points_of(project, text)
    assert "W008 frame 'next': move by [-1, 0] takes point 'edge' off the canvas" in " ".join(problems)


def test_frame_points_that_put_a_dropped_point_back_silence_w008(project):
    text = derived("shift = [0, 13]") + "\n[frame_points.next]\ngrip = [25, 31]\n"
    found, problems = points_of(project, text)
    assert found["next"] == {"grip": (25, 31)}
    assert not any("W008" in problem for problem in problems)


def test_carry_agrees_with_origins_for_every_pixel(project):
    """A point on every pixel of a small canvas. Wherever a frame's pixel came
    from a parent pixel, the point on that parent pixel is now on it."""
    names = {(c, r): f"p{c}_{r}" for r in range(5) for c in range(6)}
    points = "".join(f"{name} = [{c}, {r}]\n" for (c, r), name in names.items())
    frames = {
        "a": "move = [{ rows = [1, 2], cols = [0, 3], by = [1, 1] }, { cols = [4, 5], by = [0, -1] }]",
        "b": "mirror = { rows = [0, 3], cols = [1, 4] }\nshift = [1, -1]\nflip = true",
        "c": "move = { rows = [0, 4], cols = [2, 3], by = [-2, 0] }\nmirror = [{ cols = [0, 5] }, { rows = [2, 2] }]",
        "d": 'runs = { 0 = [[0, "kw"]] }\nshift = [-1, 2]',
    }
    text = 'canvas = "tiny"\n\n[points]\n' + points + '\n[frames]\nidle_0 = """\n' + "kwrkw.\n" * 5 + '"""\n'
    for name, body in frames.items():
        text += f'\n[frames.{name}]\nfrom = "idle_0"\n{body}\n'
    sprites, problems = load_text(project, text, "gem.sprite.toml")
    assert [problem for problem in problems if " E" in problem] == []
    for frame in sprites["gem"].frames[1:]:
        found = dict(frame.points)
        for r, row in enumerate(frame.origins):
            for c, origin in enumerate(row):
                if origin is not None:
                    parent_r, parent_c = origin
                    assert found[names[parent_c, parent_r]] == (c, r), (frame.name, c, r)


# --- A61: [frame_points] ------------------------------------------------------


ATTACK = WARRIOR + '''
[frames.attack_0]
from = "idle_0"
rows = { 17 = "''' + "." * 27 + '''k....", 19 = "''' + "." * 32 + '''" }

[frames.attack_1]
from = "attack_0"
shift = [1, 0]

[frame_points.attack_0]
grip = [27, 17]
muzzle = [30, 17]
'''


def test_a61_frame_points_replace_the_inherited_point_and_derived_frames_carry_them(project):
    found, problems = points_of(project, ATTACK)
    assert [problem for problem in problems if "W006" not in problem] == []
    assert found["idle_0"] == {"grip": (25, 19)}
    assert found["attack_0"] == {"grip": (27, 17), "muzzle": (30, 17)}
    assert found["attack_1"] == {"grip": (28, 17), "muzzle": (31, 17)}


def test_a61_frame_points_on_a_literal_frame(project):
    text = WARRIOR + "\n[frame_points.idle_0]\ngrip = [27, 17]\n"
    found, problems = points_of(project, text)
    assert problems == []
    assert found["idle_0"] == {"grip": (27, 17)}


def test_a61_a_point_only_in_frame_points_is_only_on_that_frame_and_its_derived_frames(project):
    text = ATTACK + '\n[frames.idle_1]\nfrom = "idle_0"\nshift = [0, 1]\n'
    found, _ = points_of(project, text)
    assert "muzzle" not in found["idle_0"] and "muzzle" not in found["idle_1"]
    assert "muzzle" in found["attack_0"] and "muzzle" in found["attack_1"]


def test_a_sprite_with_frame_points_and_no_points_table(project):
    text = WARRIOR.replace("[points]\ngrip = [25, 19]\n", "") + "\n[frame_points.idle_0]\ntip = [0, 31]\n"
    found, problems = points_of(project, text)
    assert problems == []
    assert found == {"idle_0": {"tip": (0, 31)}}


# --- A62: variants -----------------------------------------------------------


def test_a62_a_variant_has_its_sprites_points_frame_for_frame(project):
    text = ATTACK + '\n[variants.red]\nswap = { k = "r" }\n'
    sprites, _ = load_text(project, text)
    warrior, red = sprites["warrior"], sprites["warrior_red"]
    assert [frame.points for frame in red.frames] == [frame.points for frame in warrior.frames]
    files = exported(project, text, "phaser")
    frames = json.loads(files["atlas.json"])["frames"]
    for frame in warrior.frames:
        assert frames[f"warrior_red/{frame.name}"]["points"] == frames[f"warrior/{frame.name}"]["points"]


# --- A63: E109 ------------------------------------------------------------------


@pytest.mark.parametrize(
    ("table", "message"),
    [
        ("Grip = [1, 1]", "points: bad point name 'Grip': use a-z, 0-9 and _"),
        ("grip = [1]", "points: point 'grip' must be [col, row], two integers"),
        ("grip = [1.5, 2]", "points: point 'grip' must be [col, row], two integers"),
        ('grip = "25, 19"', "points: point 'grip' must be [col, row], two integers"),
        ("grip = [32, 0]", "points: point 'grip' [32, 0] is outside the 32x32 canvas"),
        ("grip = [0, -1]", "points: point 'grip' [0, -1] is outside the 32x32 canvas"),
    ],
)
def test_a63_a_bad_point_is_one_e109_and_the_sprite_still_loads(project, table, message):
    text = WARRIOR.replace("grip = [25, 19]\n", f"{table}\nchest = [16, 15]\n")
    found, problems = points_of(project, text)
    assert problems == [f"warrior.sprite.toml:4:1: E109 {message}"]
    assert found == {"idle_0": {"chest": (16, 15)}}


def test_a63_frame_points_naming_an_unknown_frame_is_e109(project):
    found, problems = points_of(project, WARRIOR + "\n[frame_points.nosuch]\ngrip = [1, 1]\n")
    assert problems == ["warrior.sprite.toml:42:1: E109 frame_points names unknown frame 'nosuch'"]
    assert found == {"idle_0": {"grip": (25, 19)}}


def test_a_bad_point_in_frame_points_names_its_table(project):
    _, problems = points_of(project, WARRIOR + "\n[frame_points.idle_0]\ngrip = [99, 1]\n")
    assert problems == ["warrior.sprite.toml:43:1: E109 frame_points.idle_0: point 'grip' [99, 1] is outside the 32x32 canvas"]


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ('points = "grip"\n', "E109 points must be a table of name = [col, row]"),
        ('frame_points = 3\n', "E109 frame_points must be a table of [frame_points.<frame>] tables"),
        ('frame_points = { idle_0 = 3 }\n', "E109 frame_points.idle_0 must be a table of name = [col, row]"),
    ],
)
def test_tables_of_the_wrong_kind_are_e109(project, text, message):
    found, problems = points_of(project, text + WARRIOR.replace("[points]\ngrip = [25, 19]\n", ""))
    assert [problem.split(": ", 1)[1] for problem in problems] == [message]
    assert found == {"idle_0": {}}


def test_a_point_on_a_frame_that_failed_is_not_reported_again(project):
    text = WARRIOR + '\n[frames.broken]\nfrom = "nosuch"\n\n[frame_points.broken]\ngrip = [1, 1]\n'
    _, problems = points_of(project, text)
    assert [problem.split(": ", 1)[1] for problem in problems] == ["E105 frame 'broken': from names unknown frame 'nosuch'"]
