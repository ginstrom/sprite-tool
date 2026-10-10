# sprite-tool

An agent-friendly command-line tool for making 2D pixel sprites for turn-based
games.

The tool locks in the parts that must stay consistent (palette, canvas sizes,
style checks, sheet packing, engine metadata, previews) and leaves the drawing
open: each sprite is a small text file holding a character grid.

**Status:** design only. Nothing is implemented yet. See
[docs/designs/sprite-tool.md](docs/designs/sprite-tool.md).
