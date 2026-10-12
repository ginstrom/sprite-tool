import io
import json
from dataclasses import replace
from pathlib import Path

from PIL import Image

from conftest import make_frame, make_sprite, pixels
from sprite_tool.export import EXPORTERS
from sprite_tool.export import frames as frames_export
from sprite_tool.model import Canvas, Color, ExportTarget
from sprite_tool.render import png_bytes, render_all

PALETTE = {
    "k": Color(key="k", rgba=(0, 0, 0, 255), name=None),
    "w": Color(key="w", rgba=(255, 255, 255, 255), name=None),
}

TARGET = ExportTarget(type="frames", out=Path("/nowhere"), name="sprites", res_path=None, padding=0)


def export(*sprites, target=TARGET):
    return frames_export.export(sprites, render_all(sprites, PALETTE), target)


def index(*sprites):
    return json.loads(export(*sprites)["sprites.json"])


def test_frames_exporter_is_registered():
    assert EXPORTERS["frames"] is frames_export.export


def test_single_frame_sprite_gives_one_file():
    files = export(make_sprite("dot", make_frame("main", "kw", "wk")))
    assert sorted(files) == ["dot.png", "sprites.json"]


def test_multi_frame_sprite_gives_the_default_and_every_frame():
    hero = make_sprite("hero", make_frame("idle_0", "kw", "wk"), make_frame("idle_1", "ww", "kk"))
    files = export(hero)
    assert sorted(files) == ["hero.png", "hero__idle_0.png", "hero__idle_1.png", "sprites.json"]
    assert files["hero.png"] == files["hero__idle_0.png"]
    assert files["hero__idle_0.png"] != files["hero__idle_1.png"]


def test_files_are_full_canvas_pngs_from_png_bytes():
    hero = make_sprite("hero", make_frame("idle_0", "k.w", "...", "...", "w.k"))
    files = export(hero)
    image = Image.open(io.BytesIO(files["hero.png"]))
    assert image.size == (3, 4)
    assert pixels(image)[:3] == [(0, 0, 0, 255), (0, 0, 0, 0), (255, 255, 255, 255)]
    assert files["hero.png"] == png_bytes(render_all([hero], PALETTE)["hero", "idle_0"])


def test_no_sprites_gives_an_empty_index_and_no_images():
    assert export() == {"sprites.json": b"{}\n"}


# --- the index --------------------------------------------------------------


def test_index_entry_of_a_one_frame_sprite():
    dot = make_sprite("dot", make_frame("main", "....", ".kw.", ".k..", "...."))
    canvas = Canvas(name="unit", width=4, height=4, anchor=(2, 4), display_scale=3, outline=None, grounded=False)
    assert index(replace(dot, canvas=canvas)) == {
        "dot": {
            "anchor": [2, 4],
            "anims": {},
            "bounds": [1, 1, 2, 2],
            "canvas": "unit",
            "display_scale": 3,
            "file": "dot.png",
            "frames": {"main": {"bounds": [1, 1, 2, 2], "file": "dot.png"}},
            "size": [4, 4],
        }
    }


def test_index_frames_of_a_multi_frame_sprite_name_their_own_files_and_boxes():
    hero = make_sprite("hero", make_frame("idle_0", "k...", "....", "...."), make_frame("idle_1", "....", "....", "..ww"))
    entry = index(hero)["hero"]
    assert entry["file"] == "hero.png"
    assert entry["frames"] == {
        "idle_0": {"bounds": [0, 0, 1, 1], "file": "hero__idle_0.png"},
        "idle_1": {"bounds": [2, 2, 2, 1], "file": "hero__idle_1.png"},
    }
    assert entry["bounds"] == [0, 0, 4, 3]


def test_index_has_one_entry_per_sprite_and_every_file_it_names_is_exported():
    dot = make_sprite("dot", make_frame("main", "kw", "wk"))
    hero = make_sprite("hero", make_frame("a", "kw", "wk"), make_frame("b", "ww", "kk"))
    files = export(hero, dot)
    listed = json.loads(files["sprites.json"])
    assert sorted(listed) == ["dot", "hero"]
    named = {entry["file"] for entry in listed.values()}
    named |= {frame["file"] for entry in listed.values() for frame in entry["frames"].values()}
    assert named == files.keys() - {"sprites.json"}


def test_index_is_named_after_the_target():
    files = export(make_sprite("dot", make_frame("main", "k")), target=replace(TARGET, name="units"))
    assert sorted(files) == ["dot.png", "units.json"]


def test_index_is_sorted_indented_and_ends_with_a_newline():
    files = export(make_sprite("zed", make_frame("main", "k")), make_sprite("abe", make_frame("main", "k")))
    text = files["sprites.json"].decode("ascii")
    assert text == json.dumps(json.loads(text), indent=2, sort_keys=True) + "\n"
