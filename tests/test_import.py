import shutil
from pathlib import Path

import pytest
from PIL import Image

from conftest import pixels
from sprite_tool import render, spritefile
from sprite_tool import project as project_module
from sprite_tool.cli import main

DEMO = Path(__file__).parent.parent / "examples" / "demo"

OUTLINE = (0x1A, 0x1C, 0x2C, 255)
WHITE = (0xF4, 0xF4, 0xF4, 255)
RED = (0xB1, 0x3E, 0x53, 255)
PINK = (255, 0, 255, 255)
CLEAR = (0, 0, 0, 0)


@pytest.fixture
def demo(tmp_path: Path, monkeypatch) -> Path:
    """A copy of the demo project, as the current directory."""
    root = tmp_path / "demo"
    shutil.copytree(DEMO, root, ignore=shutil.ignore_patterns("out", ".preview"))
    monkeypatch.chdir(root)
    return root


def files(root: Path) -> dict[str, bytes]:
    """Every file under `root`, by relative path."""
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def write_png(path: Path, size: tuple[int, int], fill=CLEAR, mode: str = "RGBA", **dots) -> Path:
    """Write a PNG of one colour; `dots` maps names like `x3y1` to other colours."""
    image = Image.new("RGBA", size, fill)
    for name, colour in dots.items():
        x, y = name[1:].split("y")
        image.putpixel((int(x), int(y)), colour)
    image.convert(mode).save(path)
    return path


def run(capsys, *argv: str) -> tuple[int, list[str], str]:
    code = main(["import", *argv])
    captured = capsys.readouterr()
    return code, captured.out.splitlines(), captured.err


def frame_image(root: Path, sprite_id: str) -> Image.Image:
    """The first frame of a sprite in the project at `root`, rendered."""
    project, problems = project_module.load(root)
    sprites, more = spritefile.load_all(project)
    assert not problems and not more
    sprite = next(sprite for sprite in sprites if sprite.id == sprite_id)
    return render.render(sprite.frames[0], project.palette)


def rows(root: Path, sprite_id: str) -> list[str]:
    """The grid of an imported sprite file, as written."""
    text = (root / f"{sprite_id}.sprite.toml").read_text(encoding="utf-8")
    start = 'canvas = "'
    assert text.startswith(start) and text.endswith('"""\n')
    return text.split('main = """\n')[1].removesuffix('"""\n').splitlines()


# --- round trip ---------------------------------------------------------------


def test_a10_an_imported_png_renders_back_to_the_identical_image(demo, capsys):
    goblin = frame_image(demo, "goblin")
    goblin.save(demo / "goblin_copy.png")

    assert run(capsys, "goblin_copy.png", "--canvas", "unit") == (0, ["goblin_copy.sprite.toml"], "")

    copy = frame_image(demo, "goblin_copy")
    assert copy.size == (32, 32)
    assert pixels(copy) == pixels(goblin)


def test_the_written_file_is_one_literal_frame_named_main(demo, capsys):
    write_png(demo / "dot.png", (16, 16), fill=OUTLINE, x1y0=WHITE)
    assert run(capsys, "dot.png", "--canvas", "tile")[0] == 0

    project, _ = project_module.load(demo)
    sprites, problems = spritefile.load_all(project, [demo / "dot.sprite.toml"])
    assert problems == []
    (sprite,) = sprites
    assert (sprite.id, sprite.canvas.name, sprite.anims) == ("dot", "tile", ())
    assert [(frame.name, frame.literal) for frame in sprite.frames] == [("main", True)]
    assert rows(demo, "dot") == ["kw" + "k" * 14] + ["k" * 16] * 15


def test_id_names_the_sprite(demo, capsys):
    write_png(demo / "Old Art (1).png", (16, 16), fill=OUTLINE)
    assert run(capsys, "Old Art (1).png", "--canvas", "tile", "--id", "rock") == (0, ["rock.sprite.toml"], "")
    assert (demo / "rock.sprite.toml").is_file()


def test_the_file_goes_to_the_project_root_wherever_the_png_is(demo, tmp_path, monkeypatch, capsys):
    png = write_png(tmp_path / "rock.png", (16, 16), fill=OUTLINE)
    monkeypatch.chdir(demo / "units")
    assert run(capsys, str(png), "--canvas", "tile") == (0, ["../rock.sprite.toml"], "")
    assert (demo / "rock.sprite.toml").is_file()

    monkeypatch.chdir(tmp_path)
    assert run(capsys, "rock.png", "--canvas", "tile", "--id", "stone", "--project", "demo") == (
        0,
        ["demo/stone.sprite.toml"],
        "",
    )


# --- scale and placement ------------------------------------------------------


def test_scale_2_doubles_a_16_pixel_png_onto_the_unit_canvas(demo, capsys):
    write_png(demo / "small.png", (16, 16), x3y1=OUTLINE, x15y15=RED)
    assert run(capsys, "small.png", "--canvas", "unit", "--scale", "2") == (0, ["small.sprite.toml"], "")

    image = frame_image(demo, "small")
    assert image.size == (32, 32)
    filled = {(x, y): colour for y in range(32) for x in range(32) if (colour := image.getpixel((x, y)))[3]}
    assert filled == {
        **{(x, y): OUTLINE for x in (6, 7) for y in (2, 3)},
        **{(x, y): RED for x in (30, 31) for y in (30, 31)},
    }


def test_a_small_png_stands_bottom_centre_on_the_unit_anchor(demo, capsys):
    write_png(demo / "small.png", (10, 12), fill=OUTLINE)
    assert run(capsys, "small.png", "--canvas", "unit")[0] == 0
    # Anchor [16, 32]: columns 11 to 20, rows 20 to 31.
    assert rows(demo, "small") == ["." * 32] * 20 + ["." * 11 + "k" * 10 + "." * 11] * 12


def test_a_small_png_goes_top_left_on_the_tile_canvas(demo, capsys):
    write_png(demo / "small.png", (10, 12), fill=OUTLINE)
    assert run(capsys, "small.png", "--canvas", "tile")[0] == 0
    assert rows(demo, "small") == ["k" * 10 + "." * 6] * 12 + ["." * 16] * 4


def test_a_png_larger_than_the_canvas_is_e301_and_writes_nothing(demo, capsys):
    write_png(demo / "wide.png", (40, 32), fill=OUTLINE)
    before = files(demo)
    assert run(capsys, "wide.png", "--canvas", "unit") == (
        1,
        ["wide.png: E301 image is 40x32, canvas 'unit' is 32x32", "1 error, 0 warnings in 1 file"],
        "",
    )
    assert files(demo) == before


def test_scale_can_make_a_png_too_large(demo, capsys):
    write_png(demo / "tile.png", (16, 16), fill=OUTLINE)
    code, out, _ = run(capsys, "tile.png", "--canvas", "tile", "--scale", "2")
    assert (code, out[0]) == (1, "tile.png: E301 image is 32x32 at --scale 2, canvas 'tile' is 16x16")
    assert not (demo / "tile.sprite.toml").exists()


# --- colours ------------------------------------------------------------------


def test_an_off_palette_pixel_is_e302_and_writes_nothing(demo, capsys):
    write_png(demo / "odd.png", (32, 32), fill=OUTLINE, x5y9=PINK)
    before = files(demo)
    assert run(capsys, "odd.png", "--canvas", "unit") == (
        1,
        ["odd.png:5,9: E302 colour #ff00ff is not in the palette", "1 error, 0 warnings in 1 file"],
        "",
    )
    assert files(demo) == before


def test_more_than_ten_off_palette_pixels_end_in_a_count(demo, capsys):
    write_png(demo / "odd.png", (16, 16), fill=PINK)
    code, out, _ = run(capsys, "odd.png", "--canvas", "tile")
    assert code == 1
    assert sorted(out[:11]) == sorted(
        [f"odd.png:{x},0: E302 colour #ff00ff is not in the palette" for x in range(10)]
        + ["odd.png: E302 246 more pixels not in the palette"]
    )
    assert out[11:] == ["11 errors, 0 warnings in 1 file"]


def test_an_alpha_zero_pixel_is_transparent_whatever_its_rgb(demo, capsys):
    write_png(demo / "ghost.png", (16, 16), fill=(255, 0, 255, 0), x2y0=OUTLINE)
    assert run(capsys, "ghost.png", "--canvas", "tile") == (0, ["ghost.sprite.toml"], "")
    assert rows(demo, "ghost") == ["..k" + "." * 13] + ["." * 16] * 15


def test_snap_writes_the_file_and_reports_each_source_colour_before_the_path(demo, capsys):
    near_outline, near_white, faint = (0x20, 0x20, 0x30, 255), (0xFF, 0xFF, 0xFF, 255), (0xB1, 0x3E, 0x53, 100)
    write_png(
        demo / "rough.png",
        (16, 16),
        x0y0=near_white,
        x1y0=near_outline,
        x2y0=near_white,
        x3y0=faint,
        x4y0=RED,
        x5y0=(0xB1, 0x3E, 0x53, 128),
    )
    assert run(capsys, "rough.png", "--canvas", "tile", "--snap") == (
        0,
        [
            "#202030 -> k (#1a1c2c) x1",
            "#b13e5364 -> . (transparent) x1",
            "#b13e5380 -> r (#b13e53) x1",
            "#ffffff -> w (#f4f4f4) x2",
            "rough.sprite.toml",
        ],
        "",
    )
    assert rows(demo, "rough") == ["wkw.rr" + "." * 10] + ["." * 16] * 15


def test_snap_with_nothing_to_snap_prints_only_the_path(demo, capsys):
    write_png(demo / "clean.png", (16, 16), fill=OUTLINE)
    assert run(capsys, "clean.png", "--canvas", "tile", "--snap") == (0, ["clean.sprite.toml"], "")


@pytest.mark.parametrize("mode", ["RGB", "P"])
def test_png_without_an_alpha_channel_is_imported(demo, capsys, mode):
    png = write_png(demo / "flat.png", (16, 16), fill=OUTLINE, mode=mode, x1y0=WHITE, x0y1=RED)
    with Image.open(png) as saved:
        assert saved.mode == mode
    assert run(capsys, "flat.png", "--canvas", "tile") == (0, ["flat.sprite.toml"], "")
    assert rows(demo, "flat")[:2] == ["kw" + "k" * 14, "r" + "k" * 15]


def test_the_result_is_not_checked_against_style_rules(demo, capsys):
    # Red touching transparency breaks the unit outline rule; `sprite check` reports it afterwards.
    write_png(demo / "blob.png", (4, 4), fill=RED)
    assert run(capsys, "blob.png", "--canvas", "unit") == (0, ["blob.sprite.toml"], "")
    assert main(["check", "blob.sprite.toml"]) == 1
    assert "E201" in capsys.readouterr().out


# --- refusals -----------------------------------------------------------------


REFUSALS = {
    "existing file": (["--canvas", "unit", "--id", "kobold"], "kobold.sprite.toml already exists"),
    "id used in another directory": (
        ["--canvas", "unit", "--id", "warrior"],
        "sprite id 'warrior' is already used by units/warrior.sprite.toml",
    ),
    "id used by a variant": (
        ["--canvas", "unit", "--id", "warrior_red"],
        "sprite id 'warrior_red' is already used by units/warrior.sprite.toml",
    ),
    "upper case id": (["--canvas", "unit", "--id", "Hero"], "sprite id 'Hero' must match [a-z0-9_]+"),
    "id with a path": (["--canvas", "unit", "--id", "units/hero"], "sprite id 'units/hero' must match [a-z0-9_]+"),
    "empty id": (["--canvas", "unit", "--id", ""], "sprite id '' must match [a-z0-9_]+"),
    "unknown class": (["--canvas", "boss"], "unknown canvas class 'boss' (expected one of unit, tile)"),
}


@pytest.mark.parametrize("argv, message", REFUSALS.values(), ids=REFUSALS.keys())
def test_refusals_exit_2_and_write_nothing(demo, capsys, argv, message):
    write_png(demo / "hero.png", (32, 32), fill=OUTLINE)
    (demo / "kobold.sprite.toml").write_text("mine\n", encoding="utf-8")
    before = files(demo)
    assert run(capsys, "hero.png", *argv) == (2, [], f"error: {message}\n")
    assert files(demo) == before


def test_a_file_stem_that_is_not_an_id_is_refused(demo, capsys):
    write_png(demo / "Hero-2.png", (32, 32), fill=OUTLINE)
    assert run(capsys, "Hero-2.png", "--canvas", "unit") == (
        2,
        [],
        "error: sprite id 'Hero-2' must match [a-z0-9_]+ (use --id <id>)\n",
    )


@pytest.mark.parametrize("content", [None, b"not a png"], ids=["missing", "not an image"])
def test_a_png_that_cannot_be_read_is_e001(demo, capsys, content):
    if content is not None:
        (demo / "hero.png").write_bytes(content)
    code, out, err = run(capsys, "hero.png", "--canvas", "unit")
    assert (code, err) == (1, "")
    assert out[0].startswith("hero.png: E001 cannot read image: ")
    assert out[1:] == ["1 error, 0 warnings in 1 file"]
    assert not (demo / "hero.sprite.toml").exists()


def test_a_bad_palette_is_reported_and_nothing_is_written(demo, capsys):
    write_png(demo / "hero.png", (32, 32), fill=OUTLINE)
    (demo / "palette.toml").write_text('[colors]\nab = "#000000"\n', encoding="utf-8")
    code, out, err = run(capsys, "hero.png", "--canvas", "unit")
    assert (code, err) == (1, "")
    assert out[0].startswith("palette.toml:2:1: E002 ")
    assert not (demo / "hero.sprite.toml").exists()


def test_outside_a_project_exits_2(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    write_png(tmp_path / "hero.png", (32, 32), fill=OUTLINE)
    code, out, err = run(capsys, "hero.png", "--canvas", "unit")
    assert (code, out) == (2, [])
    assert "sprite-tool.toml" in err
    assert files(tmp_path).keys() == {"hero.png"}
