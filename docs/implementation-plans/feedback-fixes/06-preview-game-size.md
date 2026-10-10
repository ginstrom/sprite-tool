# Step 06: Preview at game size

- **Plan:** [index.md](index.md)
- **Design:** [feedback-fixes.md](../../designs/feedback-fixes.md), sections 4.7 and 5.6
- **Requirement:** R19. **Criterion:** A27.

## Objective

`sprite preview <id>` shows each frame at game size beside the enlarged one,
and `--scale display` draws at game size only.

## Dependencies

None. It can run at any point, including in parallel with steps 01 to 05. It
edits `src/sprite_tool/preview.py`, `cli._preview` and the `preview`
arguments in `cli.build_parser`; no other step touches those.

Existing code (inspected at 0.2.0):

- `preview.sprite_preview(project, sprite, variants, scale, grid=False)` lays out one row per sprite (the sprite, then each variant by id), every frame a tile of the same size, with `MARGIN` (8) around and `GAP` (8) between tiles and rows.
- `preview._frame_tile(project, frame, scale, grid)` makes one tile; without `grid` it is the frame enlarged on the background.
- `preview.on_tile(project, sprite, tile, scale)` enlarges each by its class's `display_scale` times `scale`.
- `cli._preview`: `scale = args.scale or project.preview.scale`, or `preview_module.ON_TILE_SCALE` (2) with `--on`. `--scale` is parsed by `cli._positive_int`.
- `preview.stack` puts several sprites' images one under another.

## Constraints

- Python 3.11 or later; Pillow is the only runtime dependency and `pytest` the only dev dependency. Add nothing.
- Tests need no display or network and write only under `tmp_path`. Preview tests compare image sizes and pixels, using the layout constants in `preview.py`.
- A clean run prints only the paths written. Usage errors are `error: <message>` on stderr, exit 2.
- Previews are written straight to `.preview/`, not through the manifest, and are exempt from byte-stability.
- File names do not change (`<ids>.plain.png`, `<ids>.grid.png`, `<ids>.on-<tile-id>.png`, `sheet.png`).

## Behaviour to implement

- `sprite preview <id>` without `--grid` or `--on`: each row (the sprite, then each variant) shows its frames enlarged by the preview scale (`--scale N`, else `[preview] scale`), then a gap, then the same frames at the class's `display_scale`, top-aligned. The game-size frames are left out when the two scales are equal.
- `--scale` takes a positive integer or the word `display`. `display` uses each sprite's own class's `display_scale`, so the image holds only the game-size frames, and several ids of different classes each get their own scale.
- With `--on`, `--scale display` means a common factor of 1: the pair exactly as the game draws them.
- `--scale display` with `--grid` is a usage error, exit 2, whether or not `--on` is given (plan decision P11). A grid at 2x or 3x cannot be read.
- `--grid` with a number is unchanged: no game-size frames.
- The contact sheet is unchanged; it ignores `--scale` today.

Image width for one sprite with `n` frames of width `W`, preview scale `s`
and display scale `d ≠ s`:

`2·MARGIN + n·W·s + (n−1)·GAP + GAP + n·W·d + (n−1)·GAP`

Height is unchanged, set by the enlarged frames.

## Implementation guidance

- `sprite_preview` gains `display: bool = False`. When set and `scale != sprite.canvas.display_scale`, each row is its enlarged tiles followed by plain tiles at `display_scale`. Column positions have to be computed per group, since the two groups have different tile sizes; today one `tile_w` serves the whole image. Keeping the default `False` leaves the existing direct calls in `tests/test_preview.py` valid.
- A new argparse type for `--scale` returns an `int` or the string `"display"`. `cli._preview` resolves it per sprite, and passes `display=True` for the plain (no `--grid`, no `--on`) case.
- Return the `--grid` conflict through `cli._usage_error`, so `main` returns 2 as the tests expect, and update the `--scale` help text.
- CLI-level tests that assert the size of a plain preview of a demo unit will change, because the demo's `unit` class has `display_scale = 2` and the preview scale is 6: `test_a9_preview_writes_one_png_and_prints_only_its_path`, `test_preview_of_a_sprite_shows_its_frames_and_variants`, `test_scale_flag_overrides_the_configured_scale` and `test_several_ids_are_one_image_in_the_order_given` in `tests/test_preview.py` are the likely ones.

Not in this step: the README's preview section and the base design's
sections 4.5 and 4.8 (step 08).

## Verification

In `tests/test_preview.py`:

- `sprite_preview(..., display=True)` with unequal scales: the width formula above for one frame and for two; height as before; the game-size frames are top-aligned and each art pixel is a `d`-pixel block; the gap between the groups is background.
- With equal scales, `display=True` gives the same image as `display=False`.
- Variant rows carry their own game-size frames.
- **A27.** `sprite preview warrior` on a copy of the demo writes an image whose width is the enlarged frames plus the same frames at `display_scale`. `sprite preview warrior --scale display` writes only the game-size frames (width `2·MARGIN + n·W·d + (n−1)·GAP`).
- `--scale display` for two ids of different classes (`warrior` and `ground_light`): each part is drawn at its own class's scale.
- `--scale display --grid` exits 2 and writes nothing. `--scale 0` and `--scale big` are still argparse errors.
- `--on ground_light --scale display` equals `on_tile(..., scale=1)`.
- `--grid` with and without `--scale N` is unchanged.

Commands: `uv run pytest tests/test_preview.py tests/test_cli.py`, then
`make check`. Look at one image yourself as well:
`uv run sprite preview warrior --project examples/demo` and open the path it
prints (`examples/demo/.preview/` is ignored by git).

## Completion criteria

- [ ] A27 has a passing test for both halves.
- [ ] Every earlier test passes, with the changed sizes updated.
- [ ] `make check` passes.
- [ ] The step's row in [index.md](index.md) is `done`, with a completion log entry (date, commit, test result).

**Handed to later steps:** `--scale display` and the wider default preview
(step 08 documents them).
