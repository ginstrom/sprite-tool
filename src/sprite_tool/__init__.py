"""sprite-tool: text sprite definitions to pixel art for Godot 4 and Phaser."""

from importlib import metadata

try:
    __version__ = metadata.version("sprite-tool")
except metadata.PackageNotFoundError:  # run from a source tree that is not installed
    __version__ = "unknown"
