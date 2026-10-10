from pathlib import Path

import pytest
from PIL import Image

from sprite_tool import importer
from sprite_tool.model import Canvas, Color, Problem

K, W, B = (0, 0, 0, 255), (255, 255, 255, 255), (0, 0, 255, 255)
GLASS = (0, 255, 0, 128)
CLEAR = (0, 0, 0, 0)

PALETTE = {
    "k": Color("k", K, "outline"),
    "w": Color("w", W, None),
    "b": Color("b", B, None),
    "g": Color("g", GLASS, None),
}

PNG = Path("art/hero.png")


def canvas(width: int, height: int, anchor: tuple[int, int] = (0, 0)) -> Canvas:
    return Canvas("unit", width, height, anchor, display_scale=1, outline=None, grounded=False)


def image(*rows: list[tuple[int, int, int, int]]) -> Image.Image:
    """An RGBA image from rows of pixels."""
    made = Image.new("RGBA", (len(rows[0]), len(rows)))
    made.putdata([pixel for row in rows for pixel in row])
    return made


def convert(source: Image.Image, target: Canvas, **options) -> importer.Imported:
    return importer.to_rows(source, target, PALETTE, PNG, **options)


# --- colour mapping -----------------------------------------------------------


def test_each_pixel_becomes_the_key_with_exactly_that_colour():
    result = convert(image([K, W, B], [B, GLASS, K]), canvas(3, 2))
    assert result.rows == ("kwb", "bgk")
    assert result.problems == []
    assert result.snapped == []


def test_alpha_zero_is_transparent_whatever_its_rgb():
    result = convert(image([(255, 0, 255, 0), K], [CLEAR, (0, 0, 255, 0)]), canvas(2, 2))
    assert result.rows == (".k", "..")
    assert result.problems == []


def test_alpha_is_part_of_the_match():
    # The palette has this green at alpha 128 only.
    result = convert(image([(0, 255, 0, 255), GLASS]), canvas(2, 1))
    assert result.rows == ()
    assert result.problems == [
        Problem(PNG, 0, 0, "E302", "colour #00ff00 is not in the palette", pixel=True)
    ]


def test_keys_that_share_a_colour_give_the_first_in_palette_order():
    palette = {"z": Color("z", W, None), "a": Color("a", W, None)}
    assert importer.to_rows(image([W]), canvas(1, 1), palette, PNG).rows == ("z",)


@pytest.mark.parametrize("mode", ["RGB", "P", "L"])
def test_other_image_modes_are_read_as_rgba(mode):
    source = image([K, W], [W, K]).convert(mode)
    assert convert(source, canvas(2, 2)).rows == ("kw", "wk")


def test_off_palette_pixels_are_e302_at_their_source_coordinates():
    pink, red = (255, 0, 255, 255), (255, 0, 0, 255)
    result = convert(image([K, K, K], [K, K, pink], [red, K, K]), canvas(3, 3))
    assert result.rows == ()
    assert result.problems == [
        Problem(PNG, 1, 2, "E302", "colour #ff00ff is not in the palette", pixel=True),
        Problem(PNG, 2, 0, "E302", "colour #ff0000 is not in the palette", pixel=True),
    ]


def test_e302_lists_ten_pixels_then_a_count():
    pink = (255, 0, 255, 255)
    result = convert(image([pink] * 4, [pink] * 4, [pink] * 4), canvas(4, 3))
    assert [(problem.col, problem.line) for problem in result.problems[:10]] == [
        (x, y) for y in range(3) for x in range(4)
    ][:10]
    assert result.problems[10:] == [Problem(PNG, 0, 0, "E302", "2 more pixels not in the palette")]


# --- placement ----------------------------------------------------------------


def test_a_smaller_image_stands_bottom_centre_on_the_anchor():
    result = convert(image([K, W], [B, K]), canvas(6, 4, anchor=(3, 4)))
    assert result.rows == ("......", "......", "..kw..", "..bk..")


def test_an_odd_width_puts_the_extra_column_right_of_the_anchor():
    result = convert(image([K, W, B]), canvas(6, 2, anchor=(3, 2)))
    assert result.rows == ("......", "..kwb.")


def test_an_anchor_at_the_origin_places_the_image_top_left():
    result = convert(image([K, W], [B, K]), canvas(6, 4, anchor=(0, 0)))
    assert result.rows == ("kw....", "bk....", "......", "......")


def test_an_image_that_would_overhang_is_moved_inside_the_canvas():
    # Centred on x = 5 the image would cover columns 4 to 6 of a 6-wide canvas.
    result = convert(image([K, W, B]), canvas(6, 2, anchor=(5, 1)))
    assert result.rows == ("...kwb", "......")


def test_a_canvas_sized_image_fills_the_canvas():
    result = convert(image([K, W], [B, K]), canvas(2, 2, anchor=(1, 2)))
    assert result.rows == ("kw", "bk")


@pytest.mark.parametrize("size", [(7, 4), (6, 5)], ids=["too wide", "too high"])
def test_an_image_larger_than_the_canvas_is_e301(size):
    result = convert(Image.new("RGBA", size, K), canvas(6, 4))
    assert result.rows == ()
    width, height = size
    assert result.problems == [
        Problem(PNG, 0, 0, "E301", f"image is {width}x{height}, canvas 'unit' is 6x4")
    ]


def test_e301_and_e302_are_reported_together():
    result = convert(Image.new("RGBA", (7, 1), (255, 0, 255, 255)), canvas(6, 4))
    assert [problem.code for problem in result.problems] == ["E301"] + ["E302"] * 7


# --- scale --------------------------------------------------------------------


def test_scale_repeats_each_source_pixel():
    result = convert(image([K, W], [B, CLEAR]), canvas(4, 4), scale=2)
    assert result.rows == ("kkww", "kkww", "bb..", "bb..")


def test_scale_is_applied_before_placement():
    result = convert(image([K, W]), canvas(6, 4, anchor=(3, 4)), scale=2)
    assert result.rows == ("......", "......", ".kkww.", ".kkww.")


def test_the_scaled_size_is_what_must_fit():
    result = convert(image([K, W]), canvas(3, 3), scale=2)
    assert result.problems == [
        Problem(PNG, 0, 0, "E301", "image is 4x2 at --scale 2, canvas 'unit' is 3x3")
    ]


def test_e302_coordinates_are_those_of_the_unscaled_image():
    result = convert(image([K, (255, 0, 255, 255)]), canvas(4, 2), scale=2)
    assert [(problem.col, problem.line) for problem in result.problems] == [(1, 0)]


# --- snap ---------------------------------------------------------------------


def test_snap_maps_an_unmatched_pixel_to_the_nearest_colour_in_rgb():
    near_black, near_white, near_blue = (10, 5, 20, 255), (250, 240, 255, 255), (30, 20, 200, 255)
    result = convert(image([near_black, near_white, near_blue, K]), canvas(4, 1), snap=True)
    assert result.rows == ("kwbk",)
    assert result.problems == []


def test_snap_reports_each_distinct_source_colour_sorted_with_its_count():
    near_black, near_white = (10, 5, 20, 255), (250, 240, 255, 255)
    result = convert(
        image([near_white, near_black, near_white], [K, near_white, W]), canvas(3, 2), snap=True
    )
    assert result.rows == ("wkw", "kww")
    assert result.snapped == ["#0a0514 -> k (#000000) x1", "#faf0ff -> w (#ffffff) x3"]


def test_snap_makes_alpha_below_128_transparent_and_keeps_the_rest():
    faint, solid = (0, 0, 255, 100), (0, 0, 255, 128)
    result = convert(image([faint, solid, faint]), canvas(3, 1), snap=True)
    assert result.rows == (".b.",)
    assert result.snapped == [
        "#0000ff64 -> . (transparent) x2",
        "#0000ff80 -> b (#0000ff) x1",
    ]


def test_snap_leaves_exact_matches_alone_and_out_of_the_report():
    result = convert(image([GLASS, K, CLEAR]), canvas(3, 1), snap=True)
    assert result.rows == ("gk.",)
    assert result.snapped == []


def test_snap_ties_go_to_the_first_key_in_palette_order():
    palette = {"w": Color("w", W, None), "k": Color("k", K, None)}
    grey = (128, 128, 128, 255)
    palette["m"] = Color("m", (128, 128, 0, 255), None)
    palette["n"] = Color("n", (128, 0, 128, 255), None)
    assert importer.to_rows(image([grey]), canvas(1, 1), palette, PNG, snap=True).rows == ("m",)


def test_snap_still_fails_an_oversize_image():
    result = convert(Image.new("RGBA", (7, 1), (255, 0, 255, 255)), canvas(6, 4), snap=True)
    assert result.rows == ()
    assert [problem.code for problem in result.problems] == ["E301"]


# --- reading the file ---------------------------------------------------------


def test_import_png_reads_the_file(tmp_path):
    path = tmp_path / "hero.png"
    image([K, W]).save(path)
    result = importer.import_png(path, canvas(2, 1), PALETTE)
    assert result.rows == ("kw",)


@pytest.mark.parametrize("content", [None, b"not a png"], ids=["missing", "not an image"])
def test_a_file_that_cannot_be_read_is_e001(tmp_path, content):
    path = tmp_path / "hero.png"
    if content is not None:
        path.write_bytes(content)
    result = importer.import_png(path, canvas(2, 1), PALETTE)
    assert result.rows == ()
    assert [(p.path, p.line, p.code) for p in result.problems] == [(path, 0, "E001")]
    assert result.problems[0].message.startswith("cannot read image: ")


# --- the sprite file ----------------------------------------------------------


def test_sprite_text_is_one_frame_named_main():
    assert importer.sprite_text("unit", ("kw.", ".bk")) == (
        'canvas = "unit"\n\n[frames]\nmain = """\nkw.\n.bk\n"""\n'
    )
