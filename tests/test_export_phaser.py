import io
import json
import shutil
from dataclasses import replace
from pathlib import Path

import pytest
from PIL import Image

from conftest import make_frame, make_sprite, pixels
from sprite_tool import spritefile
from sprite_tool.cli import main
from sprite_tool.export import EXPORTERS
from sprite_tool.export import phaser as phaser_export
from sprite_tool.manifest import MANIFEST_NAME
from sprite_tool.model import Anim, Color, ExportTarget
from sprite_tool.project import load
from sprite_tool.render import render_all

DEMO = Path(__file__).parent.parent / "examples" / "demo"

PALETTE = {
    "k": Color(key="k", rgba=(0, 0, 0, 255), name=None),
    "w": Color(key="w", rgba=(255, 255, 255, 255), name=None),
}

FRAME_KEYS = [
    "arrow/main",
    "goblin/main",
    "ground_light/main",
    "orb/orb_0",
    "orb/orb_1",
    "slime/main",
    "spark/burst_0",
    "spark/burst_1",
    "spark/burst_2",
    "spark/burst_3",
    "warrior/idle_0",
    "warrior/idle_1",
    "warrior_red/idle_0",
    "warrior_red/idle_1",
]


def target(name: str = "atlas", padding: int = 1) -> ExportTarget:
    return ExportTarget(type="phaser", out=Path("/nowhere"), name=name, res_path=None, padding=padding)


def sheet(files: dict[str, bytes], name: str = "atlas") -> Image.Image:
    return Image.open(io.BytesIO(files[f"{name}.png"])).convert("RGBA")


def export(*sprites, **options) -> dict[str, bytes]:
    return phaser_export.export(sprites, render_all(sprites, PALETTE), target(**options))


@pytest.fixture(scope="module")
def demo():
    """The demo project's exported sprites, their rendered frames and the exported files."""
    project, problems = load(DEMO)
    sprites, sprite_problems = spritefile.load_all(project)
    assert problems == [] and sprite_problems == []
    sprites = [sprite for sprite in sprites if sprite.build]
    images = render_all(sprites, project.palette)
    return sprites, images, phaser_export.export(sprites, images, target())


@pytest.fixture(scope="module")
def atlas(demo) -> dict:
    return json.loads(demo[2]["atlas.json"])


@pytest.fixture(scope="module")
def anims(demo) -> dict:
    return {anim["key"]: anim for anim in json.loads(demo[2]["atlas.anims.json"])["anims"]}


def test_phaser_exporter_is_registered():
    assert EXPORTERS["phaser"] is phaser_export.export


def test_exports_a_sheet_an_atlas_and_an_animation_file(demo):
    assert sorted(demo[2]) == ["atlas.anims.json", "atlas.json", "atlas.png"]


# --- atlas.json -------------------------------------------------------------


def test_frame_keys_cover_every_sprite_and_frame_including_the_variant(atlas):
    assert sorted(atlas["frames"]) == FRAME_KEYS


def test_each_frame_has_exactly_the_json_hash_fields(atlas):
    for key, entry in atlas["frames"].items():
        size = entry["sourceSize"]
        fields = ["frame", "pivot", "rotated", "sourceSize", "spriteSourceSize", "trimmed"]
        # Only a frame with named points has `points` (the warrior's grip, the arrow's tip).
        if key.split("/")[0] in ("arrow", "warrior", "warrior_red"):
            fields.append("points")
        assert sorted(entry) == sorted(fields), key
        assert sorted(entry["frame"]) == ["h", "w", "x", "y"]
        assert sorted(entry["pivot"]) == ["x", "y"]
        assert sorted(size) == ["h", "w"]
        assert (entry["frame"]["w"], entry["frame"]["h"]) == (size["w"], size["h"])
        assert entry["spriteSourceSize"] == {"h": size["h"], "w": size["w"], "x": 0, "y": 0}
        assert entry["rotated"] is False
        assert entry["trimmed"] is False


def test_meta_has_the_sheet_size_and_nothing_extra(demo, atlas):
    width, height = sheet(demo[2]).size
    assert atlas["meta"] == {
        "app": "sprite-tool",
        "image": "atlas.png",
        "scale": "1",
        "size": {"h": height, "w": width},
    }
    assert sorted(atlas) == ["frames", "meta"]


def test_each_frame_rectangle_holds_the_rendered_frame(demo, atlas):
    _, images, files = demo
    packed = sheet(files)
    for key, entry in atlas["frames"].items():
        rect = entry["frame"]
        cut = packed.crop((rect["x"], rect["y"], rect["x"] + rect["w"], rect["y"] + rect["h"]))
        sprite_id, frame = key.split("/")
        assert pixels(cut) == pixels(images[sprite_id, frame]), key


def test_pivot_is_the_anchor_as_a_fraction_of_the_canvas(atlas):
    assert atlas["frames"]["warrior/idle_0"]["pivot"] == {"x": 0.5, "y": 1.0}
    assert atlas["frames"]["goblin/main"]["pivot"] == {"x": 0.5, "y": 1.0}
    assert atlas["frames"]["ground_light/main"]["pivot"] == {"x": 0, "y": 0}


def test_pivot_is_written_as_a_decimal_even_when_whole(demo):
    text = demo[2]["atlas.json"].decode("ascii")
    assert '"y": 1.0' in text
    assert '"x": 0.0' in text


def test_a14_units_and_the_tile_share_one_sheet_at_their_own_sizes(atlas):
    sizes = {key: (entry["frame"]["w"], entry["frame"]["h"]) for key, entry in atlas["frames"].items()}
    for key in [key for key in sizes if key.split("/")[0] in ("ground_light", "arrow", "orb", "spark")]:
        assert sizes.pop(key) == (16, 16)
    assert set(sizes.values()) == {(32, 32)}


def test_a5_red_variant_frame_differs_from_the_base(demo, atlas):
    packed = sheet(demo[2])

    def cut(key):
        rect = atlas["frames"][key]["frame"]
        return pixels(packed.crop((rect["x"], rect["y"], rect["x"] + rect["w"], rect["y"] + rect["h"])))

    assert cut("warrior_red/idle_0") != cut("warrior/idle_0")


# --- atlas.anims.json -------------------------------------------------------


def test_demo_animations_are_the_warrior_idle_its_variant_the_orb_and_the_spark(demo, anims):
    assert sorted(json.loads(demo[2]["atlas.anims.json"])) == ["anims"]
    assert sorted(anims) == ["orb/pulse", "spark/burst", "warrior/idle", "warrior_red/idle"]
    assert anims["spark/burst"]["repeat"] == 0
    assert anims["warrior/idle"] == {
        "frames": [
            {"duration": 400, "frame": "warrior/idle_0", "key": "atlas"},
            {"duration": 400, "frame": "warrior/idle_1", "key": "atlas"},
        ],
        "key": "warrior/idle",
        "repeat": -1,
    }
    assert [frame["frame"] for frame in anims["warrior_red/idle"]["frames"]] == [
        "warrior_red/idle_0",
        "warrior_red/idle_1",
    ]
    assert anims["warrior_red/idle"]["repeat"] == -1


def test_every_animation_frame_is_a_key_in_the_atlas(atlas, anims):
    for anim in anims.values():
        for frame in anim["frames"]:
            assert frame["frame"] in atlas["frames"]


def hero(*anims: Anim, sprite_id: str = "hero"):
    sprite = make_sprite(sprite_id, make_frame("a", "kw", "wk"), make_frame("b", "ww", "kk"))
    return replace(sprite, anims=anims)


def exported_anims(files: dict[str, bytes], name: str = "atlas") -> list[dict]:
    return json.loads(files[f"{name}.anims.json"])["anims"]


def test_an_animation_that_does_not_loop_has_repeat_zero():
    files = export(hero(Anim(name="hit", frames=("a", "b"), ms=80, loop=False)))
    assert exported_anims(files) == [
        {
            "frames": [
                {"duration": 80, "frame": "hero/a", "key": "atlas"},
                {"duration": 80, "frame": "hero/b", "key": "atlas"},
            ],
            "key": "hero/hit",
            "repeat": 0,
        }
    ]


def test_animations_are_ordered_by_key_and_keep_their_frame_order():
    walk = Anim(name="walk", frames=("b", "a", "b"), ms=100, loop=True)
    idle = Anim(name="idle", frames=("a",), ms=100, loop=True)
    files = export(hero(walk, idle, sprite_id="zed"), hero(walk, idle, sprite_id="abe"))
    listed = exported_anims(files)
    assert [anim["key"] for anim in listed] == ["abe/idle", "abe/walk", "zed/idle", "zed/walk"]
    assert [frame["frame"] for frame in listed[1]["frames"]] == ["abe/b", "abe/a", "abe/b"]


def test_no_animations_still_writes_the_file_with_an_empty_list():
    files = export(make_sprite("dot", make_frame("main", "kw", "wk")))
    assert files["atlas.anims.json"] == b'{\n  "anims": []\n}\n'


def test_no_sprites_gives_an_empty_atlas():
    files = export()
    atlas = json.loads(files["atlas.json"])
    assert atlas["frames"] == {}
    assert atlas["meta"]["size"] == {"h": 2, "w": 64}
    assert sheet(files).size == (64, 2)


# --- options and determinism ------------------------------------------------


def test_a_custom_name_is_used_for_the_files_the_image_and_the_texture_key():
    files = export(hero(Anim(name="idle", frames=("a",), ms=100, loop=True)), name="units")
    assert sorted(files) == ["units.anims.json", "units.json", "units.png"]
    assert json.loads(files["units.json"])["meta"]["image"] == "units.png"
    assert exported_anims(files, "units")[0]["frames"] == [{"duration": 100, "frame": "hero/a", "key": "units"}]


def test_padding_is_honoured():
    dot = make_sprite("dot", make_frame("main", "kw", "wk"))
    padded = json.loads(export(dot)["atlas.json"])
    tight = json.loads(export(dot, padding=0)["atlas.json"])
    assert padded["frames"]["dot/main"]["frame"] == {"h": 2, "w": 2, "x": 1, "y": 1}
    assert padded["meta"]["size"] == {"h": 4, "w": 64}
    assert tight["frames"]["dot/main"]["frame"] == {"h": 2, "w": 2, "x": 0, "y": 0}
    assert tight["meta"]["size"] == {"h": 2, "w": 64}


def test_exporting_twice_gives_identical_bytes(demo):
    sprites, images, files = demo
    assert phaser_export.export(sprites, images, target()) == files


def test_sprite_order_does_not_change_the_output(demo):
    sprites, images, files = demo
    assert phaser_export.export(list(reversed(sprites)), images, target()) == files


def test_json_files_are_sorted_indented_and_end_with_a_newline(demo):
    for name in ("atlas.json", "atlas.anims.json"):
        text = demo[2][name].decode("ascii")
        assert text.endswith("}\n") and "\r" not in text
        assert text == json.dumps(json.loads(text), indent=2, sort_keys=True) + "\n"


# --- through `sprite build` -------------------------------------------------


def test_build_writes_the_phaser_target(tmp_path, capsys):
    root = tmp_path / "demo"
    shutil.copytree(DEMO, root, ignore=shutil.ignore_patterns("out", ".preview"))
    config = root / "sprite-tool.toml"
    kept = config.read_text(encoding="utf-8").split("[[export]]")[0]
    config.write_text(
        kept + '[[export]]\ntype = "phaser"\nout = "out/sprites"\nname = "units"\npadding = 2\n',
        encoding="utf-8",
    )

    assert main(["build", "--project", str(root)]) == 0
    assert capsys.readouterr().out == "built: 8 sprites, 14 frames, 1 target\n"
    out = root / "out" / "sprites"
    assert sorted(path.name for path in out.iterdir()) == sorted(
        [MANIFEST_NAME, "units.anims.json", "units.json", "units.png"]
    )
    atlas = json.loads((out / "units.json").read_text(encoding="utf-8"))
    assert sorted(atlas["frames"]) == FRAME_KEYS
    with Image.open(out / "units.png") as packed:
        assert atlas["meta"]["size"] == {"h": packed.height, "w": packed.width}

    before = {path.name: path.read_bytes() for path in out.iterdir()}
    assert main(["build", "--check", "--project", str(root)]) == 0
    assert main(["build", "--project", str(root)]) == 0
    assert {path.name: path.read_bytes() for path in out.iterdir()} == before



def test_a48_each_frame_has_its_own_duration():
    anim = Anim(name="idle", frames=("a", "b"), ms=500, loop=True, durations=(500, 150))
    (exported,) = exported_anims(export(hero(anim)))
    assert [frame["duration"] for frame in exported["frames"]] == [500, 150]
