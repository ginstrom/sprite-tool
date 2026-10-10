import io
from pathlib import Path

from PIL import Image

from conftest import make_frame, make_sprite, pixels
from sprite_tool.export import EXPORTERS
from sprite_tool.export import frames as frames_export
from sprite_tool.model import Color, ExportTarget
from sprite_tool.render import png_bytes, render_all

PALETTE = {
    "k": Color(key="k", rgba=(0, 0, 0, 255), name=None),
    "w": Color(key="w", rgba=(255, 255, 255, 255), name=None),
}

TARGET = ExportTarget(type="frames", out=Path("/nowhere"), name=None, res_path=None, padding=0)


def export(*sprites):
    return frames_export.export(sprites, render_all(sprites, PALETTE), TARGET)


def test_frames_exporter_is_registered():
    assert EXPORTERS["frames"] is frames_export.export


def test_single_frame_sprite_gives_one_file():
    files = export(make_sprite("dot", make_frame("main", "kw", "wk")))
    assert sorted(files) == ["dot.png"]


def test_multi_frame_sprite_gives_the_default_and_every_frame():
    hero = make_sprite("hero", make_frame("idle_0", "kw", "wk"), make_frame("idle_1", "ww", "kk"))
    files = export(hero)
    assert sorted(files) == ["hero.png", "hero__idle_0.png", "hero__idle_1.png"]
    assert files["hero.png"] == files["hero__idle_0.png"]
    assert files["hero__idle_0.png"] != files["hero__idle_1.png"]


def test_files_are_full_canvas_pngs_from_png_bytes():
    hero = make_sprite("hero", make_frame("idle_0", "k.w", "...", "...", "w.k"))
    files = export(hero)
    image = Image.open(io.BytesIO(files["hero.png"]))
    assert image.size == (3, 4)
    assert pixels(image)[:3] == [(0, 0, 0, 255), (0, 0, 0, 0), (255, 255, 255, 255)]
    assert files["hero.png"] == png_bytes(render_all([hero], PALETTE)["hero", "idle_0"])


def test_no_sprites_gives_no_files():
    assert export() == {}
