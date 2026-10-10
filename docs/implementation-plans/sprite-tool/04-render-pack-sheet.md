# Step 04: Render, pack and sheet composition

- **Plan index:** [index.md](index.md)
- **Source design:** [docs/designs/sprite-tool.md](../../designs/sprite-tool.md), sections 4.7 (Packing), 5.4, 5.6

## Objective

Provide the pure building blocks the exporters, previews and importer share:
frame rendering, deterministic PNG encoding, the shelf packer, and a helper
that composes an atlas sheet.

## Requirements and context

- **R8.** Atlas export packs all frames into one sheet deterministically, with padding between frames.
- **Q1.** The same inputs give byte-identical PNGs. Byte identity is only promised for one Pillow minor version (pinned to `>=12.3,<12.4`).
- Frames always export at full canvas size. No trimming, rotation or merging of identical frames (non-goals).

### Packing rules

1. Order frames by height descending, then sprite id, then frame order in the file.
2. Place left to right on a shelf; start a new shelf when the next frame would pass the sheet width.
3. Sheet width is the smallest power of two, at least 64, that makes the sheet no taller than it is wide. Sheet height is the used height, not rounded up.
4. `padding` (default 1) transparent pixels separate frames from each other and from the sheet edge.

Worked example: two 32x32 frames with padding 1 are placed at `(1, 1)` and
`(34, 1)` on a 128-wide sheet that is 34 high.

## Dependencies and prerequisites

- **Step 01** provides, in `src/sprite_tool/model.py`:
  - `Color(key, rgba: tuple[int, int, int, int], name)`
  - `Frame(name, rows: tuple[str, ...], line, literal)`; `rows` holds palette keys and `.` (transparent)
  - `Sprite(id, source, canvas, frames: tuple[Frame, ...], anims, outline, grounded, variant_of)`
  - `Canvas(name, width, height, anchor, display_scale, outline, grounded)`
  - `Placement(sprite_id, frame, x, y, w, h)`
- Pillow is already a dependency. This step does not need step 02 or 03; tests build `Frame` and `Sprite` objects directly.

## Scope and implementation guidance

All paths are proposed.

### `src/sprite_tool/render.py`

- `render(frame: Frame, palette: Mapping[str, Color]) -> PIL.Image.Image`: RGBA image, one pixel per character. `.` is `(0, 0, 0, 0)`. Assumes checked input.
- `render_all(sprites: Sequence[Sprite], palette) -> dict[tuple[str, str], Image]`: keyed by `(sprite_id, frame_name)`.
- `png_bytes(image) -> bytes`: the single place PNGs are encoded for export. RGBA mode, `optimize=False`, a fixed `compress_level`, no metadata chunks.

### `src/sprite_tool/pack.py`

- `pack(items: Sequence[tuple[str, str, int, int]], padding: int = 1) -> tuple[int, int, list[Placement]]`, where an item is `(sprite_id, frame_name, w, h)` and the result is `(sheet_w, sheet_h, placements)`.
- Knows nothing about images.
- *Plan decision P8:* callers pass each sprite's frames in file order. Sort stably by `(-h, sprite_id)` so that order is kept. The result must not depend on the order in which different sprites appear in the input.
- An empty input returns a `64 x (2 * padding)` sheet or similar minimal valid result; pick one and test it.

### `src/sprite_tool/export/__init__.py` and `export/atlas.py`

- Create the `export` package (empty `__init__.py`; step 05 adds the registry).
- `atlas.compose_sheet(sprites, images, padding) -> tuple[bytes, tuple[int, int], list[Placement]]`: build the pack items from `sprites` (frames in file order), call `pack`, paste each rendered frame onto a transparent RGBA sheet, and return `(png_bytes, (sheet_w, sheet_h), placements)`. Steps 06 and 07 both call this, so the two atlas targets share one layout.

### Exclusions

No disk writes, no CLI changes, no exporter modules.

## Verification

`make test` (`uv run pytest`); no network, display or disk writes outside
`tmp_path`. Proposed `tests/test_render.py`, `tests/test_pack.py`,
`tests/test_atlas.py`:

- Render: a small grid gives the expected pixel values, including a `#rrggbbaa` colour and transparency; image size equals the grid size.
- `png_bytes` called twice on equal images returns identical bytes, and the PNG holds no text or time chunks.
- Packer, property style over generated inputs (use `random` with fixed seeds; do not add a dependency):
  - no two placements overlap;
  - every placement is at least `padding` from its neighbours and from the sheet edge;
  - everything is inside the sheet;
  - width is a power of two of at least 64 and height is no greater than width;
  - shuffling the order of sprites in the input gives the same placements.
- The worked example above.
- Mixed sizes: 32x32 and 16x16 items pack with the taller ones first.
- `padding = 0` works.
- `compose_sheet`: cutting each placement rectangle from the sheet gives an image equal to the rendered frame; everything outside the placements is transparent.

## Completion criteria

- [ ] `render.render`, `render.render_all`, `render.png_bytes`, `pack.pack` and `export.atlas.compose_sheet` exist with the signatures above.
- [ ] Packer property tests pass.
- [ ] `make test` passes.
- [ ] Index status and completion log updated.
