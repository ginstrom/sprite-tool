# Step 05: Export index, demo sprites and golden files

- **Plan:** [index.md](index.md)
- **Design:** [feedback-fixes.md](../../designs/feedback-fixes.md), sections 4.3, 5.4, 5.7 and 6
- **Requirement:** R15, and the demo coverage of R13, R14 and R17. **Criteria:** A21, A22. Quality constraint Q1.

## Objective

The `frames` target writes a JSON index of sprite data, the `godot` index
gains `canvas` and `bounds`, the demo gains two sprites that put runs,
`outline = "auto"` and `build = false` under the golden test, and
`tests/golden/` is regenerated once.

This is the only step that changes generated output (plan decision P1).

## Dependencies

The index work needs nothing from earlier steps. The demo sprites need:

- **Step 01:** a frame may be written as `[frames.main.runs]` with no `from`; each row is `<index> = [[<column>, "<pixels>"], ...]`.
- **Step 02:** `outline = "auto"` at the top of a sprite file; the tool draws the outline with the first key of the class's `outline` list (`k` for the demo's `unit` class). The interior must stay one pixel inside the canvas edge.
- **Step 03:** `build = false` at the top of a sprite file; `cli._build` leaves that sprite out of every target and count.

If any of those is not done, stop after the index work and mark the step
blocked; do not run `make golden` twice.

Existing code (inspected at 0.2.0):

- `src/sprite_tool/export/frames.py`: `export(sprites, images, target)` returns `<id>.png` per sprite and `<id>__<frame>.png` per frame for sprites with more than one frame.
- `src/sprite_tool/export/godot.py`: `_index_entry` writes `anchor`, `display_scale`, `frames` (name to `[x, y, w, h]` on the sheet) and `size`.
- `src/sprite_tool/project.py`, `_load_export`: `name` is rejected on a `frames` target and `ExportTarget.name` is `None` for it.
- `src/sprite_tool/manifest.py`: `json_bytes` is the one JSON encoder for generated files; `target_key` is `frames` when the name is `None`, else `type:name`; `plan` raises `ConfigError` when two targets write one file name in one directory.
- `Makefile`: `make golden` builds `examples/demo` and replaces `tests/golden/` with `examples/demo/out/`.

## Constraints

- Python 3.11 or later; Pillow is the only runtime dependency and `pytest` the only dev dependency. Add nothing.
- Tests need no display or network and write only under `tmp_path`; they copy the demo before building it.
- **Determinism.** Same inputs, byte-identical files. Sorted iteration; no timestamps, absolute paths or tool version in generated files. All JSON goes through `manifest.json_bytes`.
- An exporter returns `{relative path: bytes}` and never touches the disk.
- Every 0.2.0 project builds unchanged apart from the new index file in a `frames` target. The godot index keeps its existing keys and their shape.
- **Golden files.** Run `make golden` once, after everything below is in place, read `git diff tests/golden`, and commit it with the code. If the golden test fails for a reason you did not intend, fix the code; do not regenerate.
- The demo warrior and palette stay as they are: `src/sprite_tool/templates/` holds copies and a test fails if they differ.

## Behaviour to implement

### The frames index

The `frames` target also writes `<name>.json`. `name` is now accepted on a
`frames` target and defaults to `sprites`.

```json
{
  "goblin": {
    "anchor": [16, 32],
    "bounds": [5, 10, 22, 22],
    "canvas": "unit",
    "display_scale": 3,
    "file": "goblin.png",
    "frames": {
      "main": { "bounds": [5, 10, 22, 22], "file": "goblin.png" }
    },
    "size": [32, 32]
  }
}
```

(The numbers are from the design's example, not the demo. `json_bytes`
writes each list element on its own line.)

- One entry per exported sprite, variants included, keyed by sprite id.
- `canvas` is the class name; `size` is `[width, height]`; `anchor` and `display_scale` are the class's.
- `bounds` is `[x, y, width, height]` in canvas pixels, top-left origin: the smallest rectangle holding every pixel that is not `.`. A frame's `bounds` covers that frame. The sprite's covers all its frames, so it does not move with the animation.
- `file` on the sprite is `<id>.png`. A frame's `file` is `<id>__<frame>.png` when the sprite has more than one frame, else `<id>.png`.

### The godot index

Two more keys per sprite: `canvas` and `bounds` (the sprite-level box).

### Consequences to carry through

- The manifest key for a frames target changes from `frames` to `frames:sprites`, because `target_key` includes the name. Ownership is unaffected: owned files are the union across keys, so a 0.2.0 manifest still protects its files.
- `build --check` compares the index like any generated file. That is what flags a config change (`display_scale`, `anchor`) the exports have not caught up with.
- A `frames` and a `godot` target both named `sprites` in one directory both write `sprites.json`; `manifest.plan` already turns that into a config error (exit 2).

### Demo sprites

In `examples/demo/units/`:

- One new unit drawn as `[frames.main.runs]` with `outline = "auto"`. Keep it small and recognisable; it is example art that `sprite init` users will read. It must pass `sprite check` on the `unit` class (32x32, `grounded`, outline `k`): interior from column 1 to 30, bottom interior row 30 so the outline lands on row 31.
- One sprite with `build = false`, with its own id (for example `sample_<something>`), so it is checked and absent from `out/`.

Look at both with `uv run sprite preview <id> --project examples/demo`
before regenerating golden files.

## Implementation guidance

- `src/sprite_tool/export/index.py` (*proposed*, does not exist):
  - `bounds(rows)` returning `[x, y, w, h]`, computed from the text rows, not from images. For a grid with no drawn pixel it returns `[0, 0, 0, 0]` (plan decision P10).
  - `union(boxes)`, skipping zero-width boxes.
  - `sprite_entry(sprite)` returning the keys both indexes share: `anchor`, `bounds`, `canvas`, `display_scale`, `size`.
- `export/frames.py` adds `<name>.json`, each entry `sprite_entry` plus `file` and `frames`.
- `export/godot.py` builds its entry from `sprite_entry` plus its `frames` rectangles.
- `project._load_export` allows `name` on `frames` and defaults it to `"sprites"`; it must be a non-empty string, as for the atlas targets. `ExportTarget.name` stays `str | None` in the model.
- Tests across the suite hard-code the demo's contents. With two more source sprites, one of them exported, expect to update at least these (found by `grep -rn "4 sprites\|6 frames" tests/`):
  - `tests/test_demo.py`: the `ok:` line, the sorted id list, and the frames target's name (`None` becomes `"sprites"`).
  - `tests/test_golden.py`: the `up to date:` line, `len(tree(...)) == 20`, `len(texts) == 10`, `len(pngs) == 10`.
  - `tests/test_build.py`, `tests/test_export_phaser.py`, `tests/test_export_godot.py` (including its `SPRITE_IDS` list): the `built:` lines.
  - `tests/test_manifest.py` and any test that reads the frames manifest key.
  - `tests/test_preview.py` tests of the contact sheet, if they list the demo's ids.
- `test_golden_text_files_hold_no_path_timestamp_or_tool_version` must still pass with `sprites.json` among the text files.

Not in this step: the guide's Exports section (step 07); the base design's
section 4.7 and the README (step 08); an index for the Phaser target (design
question 1, left out).

## Verification

In `tests/test_export_frames.py`, `tests/test_export_godot.py`,
`tests/test_build.py`, `tests/test_project.py`, and a new
`tests/test_export_index.py` for the pure functions:

- `bounds` and `union` on small grids, including the empty one.
- **A21.** After `sprite build` on a copy of the demo, the frames directory holds `sprites.json`. The goblin entry has `canvas`, `size`, `anchor`, `display_scale`, `file`, and a `bounds` smaller than its canvas. (Computed from `goblin.sprite.toml` at 0.2.0, the box is `[4, 3, 26, 29]`.)
- A one-frame sprite's frame `file` is `<id>.png`; the warrior's are `warrior__idle_0.png` and `warrior__idle_1.png`; the sprite's `bounds` is the union of its frames'.
- `warrior_red` has its own entry.
- The godot index has `canvas` and `bounds`, and `anchor`, `display_scale`, `frames` and `size` exactly as before.
- **A22.** After a build, changing `display_scale` in the copy's config and running `sprite build --check` exits 1 with an E401 line naming `sprites.json`.
- `name = "units"` on a frames target writes `units.json`. A `frames` and a `godot` target both named `sprites` with one `out` is exit 2.
- The new auto-outline demo sprite is in all three targets; the `build = false` one is in none and in neither index.
- A directory built by 0.2.0 (manifest key `frames`, no index) builds without `--adopt`, and afterwards the manifest has only the key `frames:sprites`. If a hand-made `sprites.json` is already there, the build stops with the unowned-file message.

Then:

1. `make golden`
2. `git diff --stat tests/golden` and read the text diffs. Expected: a new `frames/sprites.json`; `canvas` and `bounds` added in `godot/atlas.json`; the frames manifest key renamed and the new files listed; new PNG and `.tres` files for the new unit; the Phaser and godot sheets and atlas rectangles changed by the extra sprite. Nothing for the `build = false` sprite.
3. `make check`. Expected: all pass, ending with the demo's new `ok:` line.
4. `uv run sprite build --project examples/demo` twice, then `git status`: clean.

## Completion criteria

- [ ] A21 and A22 each have a passing test.
- [ ] `tests/golden/` regenerated once, its diff read, and committed with the change.
- [ ] The demo has a runs and auto-outline unit and a `build = false` sprite, and checks clean.
- [ ] `make check` passes; two builds of the demo leave `git status` clean.
- [ ] The step's row in [index.md](index.md) is `done`, with a completion log entry (date, commit, test result, the number of golden files, and the demo's new `ok:` line).

**Handed to later steps:** the file `<name>.json` in a frames target with
`name` defaulting to `sprites` (step 07 prints it in the guide's Exports
section), the demo's new sprite count (steps 07 and 08 quote it), and
`export/index.py` (step 08 adds it to the layout in `AGENTS.md`).
