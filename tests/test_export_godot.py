import io
import json
import os
import re
import shutil
import subprocess
from dataclasses import replace
from pathlib import Path

import pytest
from PIL import Image

from conftest import make_frame, make_sprite, pixels
from sprite_tool import spritefile
from sprite_tool.cli import main
from sprite_tool.export import EXPORTERS
from sprite_tool.export import godot as godot_export
from sprite_tool.manifest import MANIFEST_NAME
from sprite_tool.model import Anim, Color, ExportTarget
from sprite_tool.project import load
from sprite_tool.render import render_all

DEMO = Path(__file__).parent.parent / "examples" / "demo"

PALETTE = {
    "k": Color(key="k", rgba=(0, 0, 0, 255), name=None),
    "w": Color(key="w", rgba=(255, 255, 255, 255), name=None),
}

SPRITE_IDS = ["goblin", "ground_light", "warrior", "warrior_red"]

# The example in the design, section 4.7.
WARRIOR_TRES = """\
[gd_resource type="SpriteFrames" load_steps=4 format=3]

[ext_resource type="Texture2D" path="res://assets/sprites/atlas.png" id="1"]

[sub_resource type="AtlasTexture" id="warrior_idle_0"]
atlas = ExtResource("1")
region = Rect2(1, 1, 32, 32)

[sub_resource type="AtlasTexture" id="warrior_idle_1"]
atlas = ExtResource("1")
region = Rect2(34, 1, 32, 32)

[resource]
animations = [{
"frames": [{
"duration": 1.0,
"texture": SubResource("warrior_idle_0")
}, {
"duration": 1.0,
"texture": SubResource("warrior_idle_1")
}],
"loop": true,
"name": &"idle",
"speed": 2.5
}]
"""

HEADER_RE = re.compile(r'\[gd_resource type="SpriteFrames" load_steps=(\d+) format=3\]\n')
SUB_RE = re.compile(
    r'\[sub_resource type="AtlasTexture" id="([^"]+)"\]\n'
    r'atlas = ExtResource\("1"\)\n'
    r"region = Rect2\((\d+), (\d+), (\d+), (\d+)\)\n"
)
ANIM_RE = re.compile(r'\{\n"frames": \[(.*?)\],\n"loop": (true|false),\n"name": &"([^"]*)",\n"speed": ([0-9.]+)\n\}', re.S)
TEXTURE_RE = re.compile(r'\{\n"duration": 1\.0,\n"texture": SubResource\("([^"]+)"\)\n\}')


def target(name: str = "atlas", padding: int = 1, res_path: str = "res://assets/sprites") -> ExportTarget:
    return ExportTarget(type="godot", out=Path("/nowhere"), name=name, res_path=res_path, padding=padding)


def sheet(files: dict[str, bytes], name: str = "atlas") -> Image.Image:
    return Image.open(io.BytesIO(files[f"{name}.png"])).convert("RGBA")


def export(*sprites, **options) -> dict[str, bytes]:
    return godot_export.export(sprites, render_all(sprites, PALETTE), target(**options))


def parse(tres: bytes) -> dict:
    """The parts of a `.tres` the exporter writes: `load_steps`, the texture
    path, each sub-resource's region by id, and the animations."""
    text = tres.decode("utf-8")
    return {
        "load_steps": int(HEADER_RE.match(text).group(1)),
        "path": re.search(r'\[ext_resource type="Texture2D" path="([^"]*)" id="1"\]', text).group(1),
        "regions": {match[1]: tuple(int(n) for n in match.groups()[1:]) for match in SUB_RE.finditer(text)},
        "anims": [
            {"frames": TEXTURE_RE.findall(frames), "loop": loop == "true", "name": name, "speed": speed}
            for frames, loop, name, speed in ANIM_RE.findall(text.split("[resource]\n")[1])
        ],
    }


def hero(*anims: Anim, sprite_id: str = "hero"):
    sprite = make_sprite(sprite_id, make_frame("a", "kw", "wk"), make_frame("b", "ww", "kk"))
    return replace(sprite, anims=anims)


@pytest.fixture(scope="module")
def demo():
    """The demo project's sprites, their rendered frames and the exported files."""
    project, problems = load(DEMO)
    sprites, sprite_problems = spritefile.load_all(project)
    assert problems == [] and sprite_problems == []
    images = render_all(sprites, project.palette)
    return sprites, images, godot_export.export(sprites, images, target())


@pytest.fixture(scope="module")
def index(demo) -> dict:
    return json.loads(demo[2]["atlas.json"])


def test_godot_exporter_is_registered():
    assert EXPORTERS["godot"] is godot_export.export


def test_exports_a_sheet_an_index_and_one_resource_per_sprite(demo):
    assert sorted(demo[2]) == ["atlas.json", "atlas.png", *(f"{sprite_id}.tres" for sprite_id in SPRITE_IDS)]


# --- <id>.tres --------------------------------------------------------------


def test_two_frame_sprite_gives_the_resource_in_the_design_byte_for_byte():
    row = "k" * 32
    sprite = make_sprite("warrior", make_frame("idle_0", *[row] * 32), make_frame("idle_1", *["w" * 32] * 32))
    sprite = replace(sprite, anims=(Anim(name="idle", frames=("idle_0", "idle_1"), ms=400, loop=True),))
    assert export(sprite)["warrior.tres"].decode("utf-8") == WARRIOR_TRES


def test_load_steps_is_the_sub_resource_count_plus_two(demo):
    sprites, _, files = demo
    for sprite in sprites:
        parsed = parse(files[f"{sprite.id}.tres"])
        assert len(parsed["regions"]) == len(sprite.frames), sprite.id
        assert parsed["load_steps"] == len(sprite.frames) + 2, sprite.id


def test_each_region_holds_the_rendered_frame(demo):
    sprites, images, files = demo
    packed = sheet(files)
    for sprite in sprites:
        regions = parse(files[f"{sprite.id}.tres"])["regions"]
        assert list(regions) == [f"{sprite.id}_{frame.name}" for frame in sprite.frames]
        for frame in sprite.frames:
            x, y, w, h = regions[f"{sprite.id}_{frame.name}"]
            assert pixels(packed.crop((x, y, x + w, y + h))) == pixels(images[sprite.id, frame.name])


def test_animations_match_the_sprite(demo):
    sprites, _, files = demo
    for sprite in sprites:
        if not sprite.anims:
            continue
        assert parse(files[f"{sprite.id}.tres"])["anims"] == [
            {
                "frames": [f"{sprite.id}_{frame}" for frame in anim.frames],
                "loop": anim.loop,
                "name": anim.name,
                "speed": "2.5",
            }
            for anim in sprite.anims
        ], sprite.id


def test_a_sprite_with_no_animations_gets_a_looping_default_of_all_its_frames(demo):
    assert parse(demo[2]["goblin.tres"])["anims"] == [
        {"frames": ["goblin_main"], "loop": True, "name": "default", "speed": "1.0"}
    ]
    assert parse(export(hero())["hero.tres"])["anims"] == [
        {"frames": ["hero_a", "hero_b"], "loop": True, "name": "default", "speed": "1.0"}
    ]


def test_a5_the_red_variant_has_its_own_resource_with_recoloured_frames(demo):
    packed = sheet(demo[2])

    def cut(sprite_id):
        x, y, w, h = parse(demo[2][f"{sprite_id}.tres"])["regions"][f"{sprite_id}_idle_0"]
        return pixels(packed.crop((x, y, x + w, y + h)))

    assert cut("warrior_red") != cut("warrior")
    assert [anim["name"] for anim in parse(demo[2]["warrior_red.tres"])["anims"]] == ["idle"]


def test_an_animation_that_does_not_loop_is_written_as_false():
    files = export(hero(Anim(name="hit", frames=("a", "b"), ms=80, loop=False)))
    assert parse(files["hero.tres"])["anims"] == [
        {"frames": ["hero_a", "hero_b"], "loop": False, "name": "hit", "speed": "12.5"}
    ]


@pytest.mark.parametrize(
    ("ms", "speed"),
    [(1000, "1.0"), (500, "2.0"), (400, "2.5"), (100, "10.0"), (300, "3.3333333333333335"), (2000, "0.5")],
)
def test_speed_is_frames_per_second_with_a_decimal_point(ms, speed):
    files = export(hero(Anim(name="idle", frames=("a",), ms=ms, loop=True)))
    assert f'"speed": {speed}\n' in files["hero.tres"].decode("utf-8")


def test_animations_are_ordered_by_name_and_keep_their_frame_order():
    walk = Anim(name="walk", frames=("b", "a", "b"), ms=100, loop=True)
    idle = Anim(name="idle", frames=("a",), ms=100, loop=True)
    anims = parse(export(hero(walk, idle))["hero.tres"])["anims"]
    assert [anim["name"] for anim in anims] == ["idle", "walk"]
    assert anims[1]["frames"] == ["hero_b", "hero_a", "hero_b"]


def test_a_frame_in_no_animation_still_has_a_sub_resource():
    parsed = parse(export(hero(Anim(name="idle", frames=("a",), ms=100, loop=True)))["hero.tres"])
    assert list(parsed["regions"]) == ["hero_a", "hero_b"]
    assert parsed["load_steps"] == 4


def test_quotes_and_backslashes_in_an_animation_name_are_escaped():
    files = export(hero(Anim(name='say "hi"\\now', frames=("a",), ms=100, loop=True)))
    assert '"name": &"say \\"hi\\"\\\\now",\n' in files["hero.tres"].decode("utf-8")


def test_resources_use_newlines_end_with_one_and_carry_no_uid(demo):
    for sprite_id in SPRITE_IDS:
        text = demo[2][f"{sprite_id}.tres"].decode("utf-8")
        assert text.endswith("}]\n") and not text.endswith("\n\n")
        assert "\r" not in text
        assert "uid" not in text


# --- the texture path -------------------------------------------------------


def test_the_texture_path_is_the_res_path_and_the_sheet_name():
    files = export(hero(), name="units", res_path="res://art")
    assert sorted(files) == ["hero.tres", "units.json", "units.png"]
    assert parse(files["hero.tres"])["path"] == "res://art/units.png"


@pytest.mark.parametrize("res_path", ["res://", "res://art/"])
def test_a_res_path_ending_in_a_slash_gets_no_second_one(res_path):
    assert parse(export(hero(), res_path=res_path)["hero.tres"])["path"] == f"{res_path}atlas.png"


# --- atlas.json -------------------------------------------------------------


def test_index_has_anchor_size_display_scale_and_frames_for_every_sprite(demo, index):
    sprites, _, files = demo
    assert sorted(index) == SPRITE_IDS
    for sprite in sprites:
        entry = index[sprite.id]
        regions = parse(files[f"{sprite.id}.tres"])["regions"]
        assert sorted(entry) == ["anchor", "display_scale", "frames", "size"]
        assert entry["anchor"] == list(sprite.canvas.anchor)
        assert entry["display_scale"] == sprite.canvas.display_scale
        assert entry["size"] == [sprite.canvas.width, sprite.canvas.height]
        assert entry["frames"] == {
            frame.name: list(regions[f"{sprite.id}_{frame.name}"]) for frame in sprite.frames
        }


def test_index_values_for_the_demo_warrior_and_tile(index):
    assert index["warrior"]["anchor"] == [16, 32]
    assert index["warrior"]["display_scale"] == 2
    assert index["warrior"]["size"] == [32, 32]
    assert sorted(index["warrior"]["frames"]) == ["idle_0", "idle_1"]
    assert index["ground_light"]["anchor"] == [0, 0]
    assert index["ground_light"]["display_scale"] == 4


def test_a14_units_and_the_tile_share_one_sheet_at_their_own_sizes(demo, index):
    width, height = sheet(demo[2]).size
    sizes = {}
    for sprite_id, entry in index.items():
        for x, y, w, h in entry["frames"].values():
            assert x + w <= width and y + h <= height
            sizes.setdefault(sprite_id, set()).add((w, h))
    assert sizes.pop("ground_light") == {(16, 16)}
    assert set().union(*sizes.values()) == {(32, 32)}


def test_index_is_sorted_indented_and_ends_with_a_newline(demo):
    text = demo[2]["atlas.json"].decode("ascii")
    assert text.endswith("}\n") and "\r" not in text
    assert text == json.dumps(json.loads(text), indent=2, sort_keys=True) + "\n"


def test_no_sprites_gives_an_empty_sheet_and_index():
    files = export()
    assert sorted(files) == ["atlas.json", "atlas.png"]
    assert files["atlas.json"] == b"{}\n"
    assert sheet(files).size == (64, 2)


# --- options and determinism ------------------------------------------------


def test_padding_is_honoured():
    dot = make_sprite("dot", make_frame("main", "kw", "wk"))
    assert parse(export(dot)["dot.tres"])["regions"] == {"dot_main": (1, 1, 2, 2)}
    assert parse(export(dot, padding=0)["dot.tres"])["regions"] == {"dot_main": (0, 0, 2, 2)}
    assert json.loads(export(dot, padding=0)["atlas.json"])["dot"]["frames"] == {"main": [0, 0, 2, 2]}


def test_exporting_twice_gives_identical_bytes(demo):
    sprites, images, files = demo
    assert godot_export.export(sprites, images, target()) == files


def test_sprite_order_does_not_change_the_output(demo):
    sprites, images, files = demo
    assert godot_export.export(list(reversed(sprites)), images, target()) == files


def test_the_sheet_is_the_one_the_phaser_target_packs(demo):
    sprites, images, files = demo
    phaser = EXPORTERS["phaser"](sprites, images, replace(target(), type="phaser", res_path=None))
    assert files["atlas.png"] == phaser["atlas.png"]


# --- through `sprite build` -------------------------------------------------


def copy_demo(root: Path, exports: str) -> Path:
    """A copy of the demo at `root` whose only `[[export]]` blocks are `exports`."""
    shutil.copytree(DEMO, root, ignore=shutil.ignore_patterns("out", ".preview"))
    config = root / "sprite-tool.toml"
    kept = config.read_text(encoding="utf-8").split("[[export]]")[0]
    config.write_text(kept + exports, encoding="utf-8")
    return root


def test_build_writes_the_godot_target(tmp_path, capsys):
    root = copy_demo(
        tmp_path / "demo",
        '[[export]]\ntype = "godot"\nout = "out/sprites"\nname = "units"\nres_path = "res://sprites"\npadding = 2\n',
    )

    assert main(["build", "--project", str(root)]) == 0
    assert capsys.readouterr().out == "built: 4 sprites, 6 frames, 1 target\n"
    out = root / "out" / "sprites"
    assert sorted(path.name for path in out.iterdir()) == sorted(
        [MANIFEST_NAME, "units.json", "units.png", *(f"{sprite_id}.tres" for sprite_id in SPRITE_IDS)]
    )
    assert parse((out / "warrior.tres").read_bytes())["path"] == "res://sprites/units.png"
    assert sorted(json.loads((out / "units.json").read_text(encoding="utf-8"))) == SPRITE_IDS

    before = {path.name: path.read_bytes() for path in out.iterdir()}
    assert main(["build", "--check", "--project", str(root)]) == 0
    assert main(["build", "--project", str(root)]) == 0
    assert {path.name: path.read_bytes() for path in out.iterdir()} == before


def test_godot_and_frames_targets_share_a_directory(tmp_path, capsys):
    root = copy_demo(
        tmp_path / "demo",
        '[[export]]\ntype = "frames"\nout = "out"\n\n'
        '[[export]]\ntype = "godot"\nout = "out"\nname = "atlas"\nres_path = "res://out"\n',
    )

    assert main(["build", "--project", str(root)]) == 0
    assert capsys.readouterr().out == "built: 4 sprites, 6 frames, 2 targets\n"
    names = {path.name for path in (root / "out").iterdir()}
    assert {"atlas.png", "atlas.json", "warrior.tres", "warrior.png", "warrior__idle_0.png"} <= names


# --- in Godot (A7) ----------------------------------------------------------

GODOT = shutil.which("godot")
GODOT_TIMEOUT = 120

LOADER = """\
extends SceneTree

func _init() -> void:
    var failed := false
    for id in %s:
        var res = load("res://sprites/%%s.tres" %% id)
        if not (res is SpriteFrames):
            printerr("not a SpriteFrames: ", id)
            failed = true
            continue
        var names := Array(res.get_animation_names())
        names.sort()
        for anim in names:
            var region := Rect2()
            var tex = res.get_frame_texture(anim, 0)
            if tex is AtlasTexture and tex.atlas != null:
                region = tex.region
            else:
                printerr("frame without an atlas: ", id, " ", anim)
                failed = true
            print("ANIM %%s %%s %%d %%s %%s %%d,%%d,%%d,%%d" %% [
                id, anim, res.get_frame_count(anim), str(res.get_animation_speed(anim)),
                str(res.get_animation_loop(anim)),
                int(region.position.x), int(region.position.y), int(region.size.x), int(region.size.y),
            ])
    quit(1 if failed else 0)
"""


def godot(project: Path, home: Path, *args: str) -> subprocess.CompletedProcess:
    """Run Godot with `home` as the home directory, so that its settings, cache
    and the project's user data are written there and not to the real one."""
    env = {
        **os.environ,
        "HOME": str(home),
        "CFFIXED_USER_HOME": str(home),
        "XDG_DATA_HOME": str(home / "data"),
        "XDG_CONFIG_HOME": str(home / "config"),
        "XDG_CACHE_HOME": str(home / "cache"),
    }
    return subprocess.run(
        [GODOT, "--headless", "--path", str(project), *args],
        capture_output=True,
        text=True,
        timeout=GODOT_TIMEOUT,
        check=False,
        env=env,
    )


@pytest.mark.skipif(GODOT is None, reason="godot is not on PATH")
def test_a7_godot_loads_each_resource_as_sprite_frames(tmp_path, capsys):
    game = tmp_path / "game"
    game.mkdir()
    (game / "project.godot").write_text('config_version=5\n\n[application]\n\nconfig/name="sprite-tool A7"\n', "utf-8")
    root = copy_demo(
        tmp_path / "demo",
        '[[export]]\ntype = "godot"\nout = "../game/sprites"\nname = "atlas"\nres_path = "res://sprites"\n',
    )
    assert main(["build", "--project", str(root)]) == 0
    capsys.readouterr()
    index = json.loads((game / "sprites" / "atlas.json").read_text(encoding="utf-8"))
    (game / "load.gd").write_text(LOADER % json.dumps(SPRITE_IDS), encoding="utf-8")

    home = tmp_path / "home"
    home.mkdir()
    imported = godot(game, home, "--import")
    assert imported.returncode == 0, imported.stdout + imported.stderr
    loaded = godot(game, home, "--script", "res://load.gd")
    assert loaded.returncode == 0, loaded.stdout + loaded.stderr

    def region(sprite_id, frame):
        return ",".join(str(n) for n in index[sprite_id]["frames"][frame])

    assert [line for line in loaded.stdout.splitlines() if line.startswith("ANIM ")] == [
        f"ANIM goblin default 1 1.0 true {region('goblin', 'main')}",
        f"ANIM ground_light default 1 1.0 true {region('ground_light', 'main')}",
        f"ANIM warrior idle 2 2.5 true {region('warrior', 'idle_0')}",
        f"ANIM warrior_red idle 2 2.5 true {region('warrior_red', 'idle_0')}",
    ]
    assert "ERROR" not in loaded.stdout + loaded.stderr
