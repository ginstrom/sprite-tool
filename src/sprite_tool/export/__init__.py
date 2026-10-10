"""Export targets. An exporter turns rendered sprites into file contents and
never touches the disk; `manifest` does the writing."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence

from PIL import Image

from sprite_tool.model import ExportTarget, Sprite

from . import frames, phaser

# Maps a path relative to `target.out` to the content of that file.
Exporter = Callable[
    [Sequence[Sprite], Mapping[tuple[str, str], Image.Image], ExportTarget], dict[str, bytes]
]

# One entry per target type that can be built.
EXPORTERS: dict[str, Exporter] = {
    "frames": frames.export,
    "phaser": phaser.export,
}
