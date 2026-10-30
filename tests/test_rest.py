"""`rest = true` in a layer's animation, and W009 for a base animation a layer forgets."""

import json

import pytest

from conftest import write_project
from sprite_tool import check
from sprite_tool.cli import main
from sprite_tool.model import Anim, format_problem
from sprite_tool.project import load
from sprite_tool.spritefile import load_all

CONFIG = """\
version = 1

[canvas.unit]
size = [3, 3]
anchor = [1, 3]

[[export]]
type = "frames"
out = "out/frames"

[[export]]
type = "phaser"
out = "out/phaser"
name = "atlas"

[[export]]
type = "godot"
out = "out/godot"
name = "atlas"
res_path = "res://sprites"
"""

PALETTE = """\
[colors]
k = "#000000"
r = "#ff0000"
"""

WARRIOR = '''\
canvas = "unit"

[frames]
idle_0 = """
.k.
kkk
k.k
"""
walk_0 = """
.k.
kkk
.kk
"""
walk_1 = """
.k.
kkk
kk.
"""

[anim.idle]
frames = ["idle_0"]
ms = 600

[anim.walk]
frames = ["walk_0", "walk_1", "walk_0", "walk_1"]
ms = 140
'''

# `[anim.walk]` is on line 14 and `rest` on line 15.
SWORD = '''\
canvas = "unit"
over = "warrior"

[frames]
idle_0 = """
..r
..r
...
"""

[anim.idle]
like = "warrior"

[anim.walk]
rest = true
'''


@pytest.fixture
def root(tmp_path, monkeypatch):
    path = write_project(tmp_path / "sprites", CONFIG, PALETTE)
    monkeypatch.chdir(path)
    return path


def loaded(root, sword=SWORD, warrior=WARRIOR):
    (root / "warrior.sprite.toml").write_text(warrior, encoding="utf-8")
    (root / "gear_sword.sprite.toml").write_text(sword, encoding="utf-8")
    project, _ = load(root)
    sprites, problems = load_all(project)
    problems += check.run(project, sprites)
    lines = sorted(format_problem(problem, root) for problem in problems)
    return {sprite.id: sprite for sprite in sprites}, lines


# --- A75: what rest resolves to and how it is exported -------------------------


def test_a75_rest_holds_the_default_frame_for_the_whole_base_animation(root):
    sprites, problems = loaded(root)
    assert problems == []
    walk = next(anim for anim in sprites["gear_sword"].anims if anim.name == "walk")
    assert walk == Anim(name="walk", frames=("idle_0",), ms=560, loop=True, rest=True)
    assert walk.durations == (560,)
    assert walk.line == 15


def test_rest_follows_the_bases_looping(root):
    sprites, _ = loaded(root, warrior=WARRIOR.replace("ms = 140\n", "ms = 140\nloop = false\n"))
    walk = next(anim for anim in sprites["gear_sword"].anims if anim.name == "walk")
    assert (walk.loop, walk.durations) == (False, (560,))


def test_rest_can_follow_a_base_animation_taken_with_like(root, capsys):
    """The base takes `walk` from another sprite; a rest through it still has its length."""
    (root / "pattern.sprite.toml").write_text(WARRIOR, encoding="utf-8")
    warrior = WARRIOR.split("[anim.walk]")[0] + '[anim.walk]\nlike = "pattern"\n'
    sprites, problems = loaded(root, warrior=warrior)
    assert [line for line in problems if " E" in line] == []
    walk = next(anim for anim in sprites["gear_sword"].anims if anim.name == "walk")
    assert walk.durations == (560,)


def test_a75_phaser_exports_a_one_frame_animation_as_long_as_the_bases(root, capsys):
    loaded(root)
    assert main(["build"]) == 0
    capsys.readouterr()
    anims = {anim["key"]: anim for anim in json.loads((root / "out/phaser/atlas.anims.json").read_text())["anims"]}
    assert anims["gear_sword/walk"] == {
        "frames": [{"duration": 560, "frame": "gear_sword/idle_0", "key": "atlas"}],
        "key": "gear_sword/walk",
        "repeat": -1,
    }
    assert sum(frame["duration"] for frame in anims["warrior/walk"]["frames"]) == 560


@pytest.mark.parametrize("index", ["out/frames/sprites.json", "out/godot/atlas.json"])
def test_a75_the_indexes_list_the_rest_with_its_frame_and_length(root, capsys, index):
    loaded(root)
    assert main(["build"]) == 0
    capsys.readouterr()
    entry = json.loads((root / index).read_text())["gear_sword"]
    assert entry["anims"]["walk"] == {"frames": [{"frame": "idle_0", "ms": 560}], "loop": True}


def test_a75_godot_plays_the_rest_once_per_base_cycle(root, capsys):
    loaded(root)
    assert main(["build"]) == 0
    capsys.readouterr()
    tres = (root / "out/godot/gear_sword.tres").read_text()
    walk = tres.split('"name": &"walk"')[0].rsplit('"frames"', 1)[1]
    assert '"duration": 1.0' in walk and walk.count("SubResource") == 1


@pytest.mark.parametrize(
    ("table", "message"),
    [
        ("rest = true\nms = 100", "E001 anim 'walk': rest takes no other field"),
        ('rest = true\nlike = "warrior"', "E001 anim 'walk': rest takes no other field"),
        ("rest = false", "E001 anim 'walk': rest must be true"),
        ('rest = "yes"', "E001 anim 'walk': rest must be true"),
    ],
)
def test_a75_rest_beside_another_field_or_not_true_is_e001(root, table, message):
    _, problems = loaded(root, SWORD.replace("rest = true", table))
    assert [line.split(": ", 1)[1] for line in problems if " E" in line] == [message]


def test_a75_rest_on_a_sprite_that_is_not_a_layer_is_e001(root):
    _, problems = loaded(root, SWORD.replace('over = "warrior"\n', "").replace('[anim.idle]\nlike = "warrior"\n', ""))
    assert [line.split(": ", 1)[1] for line in problems if " E" in line] == [
        "E001 anim 'walk': rest is only for a layer, a sprite with over"
    ]


def test_rest_for_an_animation_the_base_does_not_have_is_e105(root):
    _, problems = loaded(root, SWORD + "\n[anim.jump]\nrest = true\n")
    assert [line for line in problems if " E" in line] == [
        "gear_sword.sprite.toml:18:1: E105 anim 'jump': rest, but 'warrior' has no animation 'jump'"
    ]


def test_a_variant_of_a_layer_rests_too(root):
    sprites, problems = loaded(root, SWORD + '\n[variants.blue]\nswap = { r = "k" }\n')
    assert problems == []
    assert [anim.name for anim in sprites["gear_sword_blue"].anims] == ["idle", "walk"]
    assert sprites["gear_sword_blue"].anims == sprites["gear_sword"].anims


def test_a_rest_with_a_bad_over_is_e108_only(root):
    _, problems = loaded(root, SWORD.replace('over = "warrior"', 'over = "nosuch"').replace('like = "warrior"', 'like = "nosuch"'))
    assert [line.split(": ", 1)[1] for line in problems if " E1" in line] == [
        "E105 anim 'idle': like names unknown sprite 'nosuch'",
        "E108 over names unknown sprite 'nosuch'",
    ]


# --- A76: W009, and no W007 for a rest -----------------------------------------


def test_a76_a_layer_missing_a_base_animation_is_w009(root):
    _, problems = loaded(root, SWORD.replace("[anim.walk]\nrest = true\n", ""))
    assert problems == [
        "gear_sword.sprite.toml:2:1: W009 anim 'walk': 'warrior' animates it and this layer does not;"
        " add [anim.walk] with like or rest = true"
    ]


def test_a76_one_w009_per_missing_animation_in_name_order(root):
    _, problems = loaded(root, 'canvas = "unit"\nover = "warrior"\n\n[frames]\nmain = """\n..r\n..r\n...\n"""\n')
    assert [line.split(": ", 1)[1].split(":")[0] for line in problems] == ["W009 anim 'idle'", "W009 anim 'walk'"]


def test_a76_a_rest_is_not_w007(root):
    sprites, problems = loaded(root)
    assert problems == []
    rest = next(anim for anim in sprites["gear_sword"].anims if anim.name == "walk")
    base = next(anim for anim in sprites["warrior"].anims if anim.name == "walk")
    assert rest.durations != base.durations


def test_a_layer_whose_like_failed_is_not_also_w009(root):
    _, problems = loaded(root, SWORD.replace('[anim.idle]\nlike = "warrior"', '[anim.idle]\nlike = "nosuch"'))
    assert [line.split(": ", 1)[1].split(" ")[0] for line in problems] == ["E105"]


def test_check_reports_w009_and_passes(root, capsys):
    loaded(root, SWORD.replace("[anim.walk]\nrest = true\n", ""))
    assert main(["check"]) == 0
    out = capsys.readouterr().out.splitlines()
    assert out[0].startswith("gear_sword.sprite.toml:2:1: W009 ")
    assert out[-1] == "ok: 2 sprites, 4 frames"
