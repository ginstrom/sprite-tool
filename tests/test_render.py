import io
import struct
from pathlib import Path

from PIL import Image

from sprite_tool.model import Canvas, Color, Frame, Sprite
from sprite_tool.render import png_bytes, render, render_all

BLACK = (0, 0, 0, 255)
WHITE = (255, 255, 255, 255)
GLASS = (0x11, 0x22, 0x33, 0x80)
CLEAR = (0, 0, 0, 0)

PALETTE = {
    "k": Color(key="k", rgba=BLACK, name="outline"),
    "w": Color(key="w", rgba=WHITE, name=None),
    # Written as "#11223380" in a palette file.
    "g": Color(key="g", rgba=GLASS, name="glass"),
}


def frame(name, *rows):
    return Frame(name=name, rows=tuple(rows), line=0, literal=True)


def sprite(sprite_id, *frames):
    canvas = Canvas(
        name="tiny",
        width=len(frames[0].rows[0]),
        height=len(frames[0].rows),
        anchor=(0, 0),
        display_scale=1,
        outline=None,
        grounded=False,
    )
    return Sprite(
        id=sprite_id,
        source=Path(f"{sprite_id}.sprite.toml"),
        canvas=canvas,
        frames=tuple(frames),
        anims=(),
        outline=False,
        grounded=False,
        variant_of=None,
    )


def pixels(image):
    return list(image.get_flattened_data())


def chunk_types(data):
    """The chunk type of every chunk in a PNG, in file order."""
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    types = []
    pos = 8
    while pos < len(data):
        (length,) = struct.unpack(">I", data[pos : pos + 4])
        types.append(data[pos + 4 : pos + 8].decode("ascii"))
        pos += 12 + length
    return types


# The grid is 4 wide and 3 high so that a width/height mix-up shows.
def test_render_gives_one_pixel_per_character():
    image = render(frame("idle_0", "kw.g", "....", "gkkw"), PALETTE)

    assert image.mode == "RGBA"
    assert image.size == (4, 3)
    assert pixels(image) == [
        BLACK, WHITE, CLEAR, GLASS,
        CLEAR, CLEAR, CLEAR, CLEAR,
        GLASS, BLACK, BLACK, WHITE,
    ]  # fmt: skip


def test_render_all_is_keyed_by_sprite_id_and_frame_name():
    hero = sprite("hero", frame("idle_0", "kw"), frame("idle_1", "wk"))
    rock = sprite("rock", frame("idle_0", "gg"))

    images = render_all([hero, rock], PALETTE)

    assert sorted(images) == [("hero", "idle_0"), ("hero", "idle_1"), ("rock", "idle_0")]
    assert pixels(images[("hero", "idle_1")]) == [WHITE, BLACK]
    assert pixels(images[("rock", "idle_0")]) == [GLASS, GLASS]


def test_png_bytes_round_trips_the_pixels():
    image = render(frame("idle_0", "kw.g", "....", "gkkw"), PALETTE)

    decoded = Image.open(io.BytesIO(png_bytes(image)))

    assert decoded.mode == "RGBA"
    assert decoded.size == (4, 3)
    assert pixels(decoded) == pixels(image)


def test_png_bytes_is_identical_for_equal_images():
    first = render(frame("idle_0", "kw.g", "....", "gkkw"), PALETTE)
    second = render(frame("other", "kw.g", "....", "gkkw"), PALETTE)

    assert png_bytes(first) == png_bytes(second)


def test_png_bytes_writes_no_metadata_chunks():
    image = render(frame("idle_0", "kw.g", "....", "gkkw"), PALETTE)
    # What an image opened from a file by `import` or `preview` may carry.
    image.info["dpi"] = (72, 72)
    image.info["icc_profile"] = b"not a real profile"
    image.info["Comment"] = "made by hand"

    assert chunk_types(png_bytes(image)) == ["IHDR", "IDAT", "IEND"]


def test_png_bytes_encodes_other_modes_as_rgba():
    image = Image.new("RGB", (2, 1), (255, 0, 0))

    decoded = Image.open(io.BytesIO(png_bytes(image)))

    assert decoded.mode == "RGBA"
    assert pixels(decoded) == [(255, 0, 0, 255), (255, 0, 0, 255)]
