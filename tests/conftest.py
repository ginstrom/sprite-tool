from pathlib import Path

import pytest
from PIL import Image

from sprite_tool.model import Canvas, Frame, Sprite

VALID_CONFIG = """\
version = 1
palette = "palette.toml"

[canvas.unit]
size = [32, 32]
anchor = [16, 32]
display_scale = 2
outline = ["k"]
grounded = true

[canvas.tile]
size = [16, 16]
anchor = [0, 0]
display_scale = 4

[preview]
scale = 6
background = "#3a3a3a"

[[export]]
type = "frames"
out = "../assets/frames"

[[export]]
type = "phaser"
out = "../public/assets/sprites"
name = "atlas"

[[export]]
type = "godot"
out = "out/godot"
name = "sheet"
res_path = "res://assets/sprites"
padding = 2
"""

VALID_PALETTE = """\
[colors]
k = { hex = "#1a1c2c", name = "outline" }
w = "#f4f4f4"
g = "#00ff0080"
"""

MINIMAL_CONFIG = """\
version = 1

[canvas.unit]
size = [32, 32]
anchor = [16, 32]
"""


def write_project(root: Path, config: str = VALID_CONFIG, palette: str | None = VALID_PALETTE) -> Path:
    """Write a project's config and palette under `root` and return `root`."""
    root.mkdir(parents=True, exist_ok=True)
    (root / "sprite-tool.toml").write_text(config, encoding="utf-8")
    if palette is not None:
        (root / "palette.toml").write_text(palette, encoding="utf-8")
    return root


@pytest.fixture
def project_dir(tmp_path: Path) -> Path:
    return write_project(tmp_path / "game" / "sprites")


def make_frame(name: str, *rows: str) -> Frame:
    return Frame(name=name, rows=tuple(rows), line=0, literal=True)


def make_sprite(sprite_id: str, *frames: Frame) -> Sprite:
    """A sprite on a canvas the size of its first frame, with no style rules."""
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


def pixels(image: Image.Image) -> list[tuple[int, ...]]:
    """Every pixel of `image`, row by row."""
    return list(image.get_flattened_data())
