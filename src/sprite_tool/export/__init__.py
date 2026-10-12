"""Export targets. An exporter turns rendered sprites into file contents and
never touches the disk; `manifest` does the writing."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from fnmatch import fnmatchcase

from PIL import Image

from sprite_tool.model import ExportTarget, Sprite

from . import frames, godot, phaser

# Maps a path relative to `target.out` to the content of that file.
Exporter = Callable[
    [Sequence[Sprite], Mapping[tuple[str, str], Image.Image], ExportTarget], dict[str, bytes]
]

# One entry per target type that can be built.
EXPORTERS: dict[str, Exporter] = {
    "frames": frames.export,
    "godot": godot.export,
    "phaser": phaser.export,
}


def select(sprites: Sequence[Sprite], target: ExportTarget) -> list[Sprite]:
    """The sprites of `sprites` that `target` exports: those of its `canvases`
    whose id matches a pattern of `include` and none of `exclude`. A key the
    target leaves out restricts nothing. `sprites` are those a build exports
    at all."""

    def matches(sprite: Sprite, patterns: Sequence[str]) -> bool:
        return any(fnmatchcase(sprite.id, pattern) for pattern in patterns)

    return [
        sprite
        for sprite in sprites
        if (target.canvases is None or sprite.canvas.name in target.canvases)
        and (target.include is None or matches(sprite, target.include))
        and not matches(sprite, target.exclude)
    ]
