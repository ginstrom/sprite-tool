import io

from PIL import Image

from conftest import make_frame, make_sprite, pixels
from sprite_tool.export.atlas import compose_sheet
from sprite_tool.model import Color, Placement
from sprite_tool.pack import pack
from sprite_tool.render import png_bytes, render_all

CLEAR = (0, 0, 0, 0)

PALETTE = {
    "k": Color(key="k", rgba=(0, 0, 0, 255), name=None),
    "w": Color(key="w", rgba=(255, 255, 255, 255), name=None),
    "r": Color(key="r", rgba=(255, 0, 0, 255), name=None),
    "g": Color(key="g", rgba=(0x11, 0x22, 0x33, 0x80), name=None),
}


def solid(key, width, height):
    return tuple(key * width for _ in range(height))


def sprites():
    """A 4x3 two-frame sprite, a taller 6x8 one and a 2x2 one. No frame is
    fully transparent, so a frame pasted in the wrong place shows."""
    hero = make_sprite(
        "hero",
        make_frame("idle_0", "kw.g", "w..k", "gkkw"),
        make_frame("idle_1", "rrrr", "r..r", "rrrr"),
    )
    tower = make_sprite("tower", make_frame("idle_0", *solid("w", 6, 8)))
    dot = make_sprite("dot", make_frame("idle_0", "kr", "rk"))
    return [hero, tower, dot]


def compose(sprite_list, padding):
    images = render_all(sprite_list, PALETTE)
    data, size, placements = compose_sheet(sprite_list, images, padding)
    return images, Image.open(io.BytesIO(data)), size, placements


def box(p):
    return (p.x, p.y, p.x + p.w, p.y + p.h)


def test_layout_is_the_packers_for_the_frames_in_file_order():
    sprite_list = sprites()

    _, _, size, placements = compose(sprite_list, padding=1)

    items = [
        ("hero", "idle_0", 4, 3),
        ("hero", "idle_1", 4, 3),
        ("tower", "idle_0", 6, 8),
        ("dot", "idle_0", 2, 2),
    ]
    width, height, expected = pack(items, padding=1)
    assert size == (width, height)
    assert placements == expected
    assert placements[0] == Placement("tower", "idle_0", 1, 1, 6, 8)


def test_sheet_is_an_rgba_png_of_the_reported_size():
    _, sheet, size, _ = compose(sprites(), padding=1)

    assert sheet.format == "PNG"
    assert sheet.mode == "RGBA"
    assert sheet.size == size


def test_each_placement_rectangle_holds_its_rendered_frame():
    images, sheet, _, placements = compose(sprites(), padding=1)

    assert len(placements) == 4
    for p in placements:
        assert pixels(sheet.crop(box(p))) == pixels(images[(p.sprite_id, p.frame)])


def test_everything_outside_the_placements_is_transparent():
    _, sheet, _, placements = compose(sprites(), padding=2)

    for p in placements:
        sheet.paste(CLEAR, box(p))
    assert set(pixels(sheet)) == {CLEAR}


def test_semi_transparent_pixels_are_copied_not_blended():
    glass = make_sprite("glass", make_frame("idle_0", "gg", "gg"))

    _, sheet, _, placements = compose([glass], padding=0)

    assert set(pixels(sheet.crop(box(placements[0])))) == {(0x11, 0x22, 0x33, 0x80)}


def test_padding_zero_packs_edge_to_edge():
    a = make_sprite("a", make_frame("idle_0", *solid("k", 32, 32)))
    b = make_sprite("b", make_frame("idle_0", *solid("w", 32, 32)))

    _, sheet, size, placements = compose([a, b], padding=0)

    assert size == (64, 32)
    assert [(p.x, p.y) for p in placements] == [(0, 0), (32, 0)]
    assert set(pixels(sheet)) == {(0, 0, 0, 255), (255, 255, 255, 255)}


def test_bytes_do_not_depend_on_the_order_of_sprites():
    sprite_list = sprites()
    images = render_all(sprite_list, PALETTE)

    forward = compose_sheet(sprite_list, images, 1)
    backward = compose_sheet(sprite_list[::-1], images, 1)

    assert forward == backward


def test_bytes_come_from_png_bytes():
    images, sheet, _, _ = compose(sprites(), padding=1)

    data, _, _ = compose_sheet(sprites(), images, 1)

    assert data == png_bytes(sheet)


def test_no_sprites_gives_an_empty_transparent_sheet():
    data, size, placements = compose_sheet([], {}, 1)

    sheet = Image.open(io.BytesIO(data))
    assert size == sheet.size == (64, 2)
    assert placements == []
    assert set(pixels(sheet)) == {CLEAR}
