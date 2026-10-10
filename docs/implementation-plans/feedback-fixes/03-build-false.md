# Step 03: `build = false`

- **Plan:** [index.md](index.md)
- **Design:** [feedback-fixes.md](../../designs/feedback-fixes.md), sections 4.5, 5.1 and 5.5
- **Requirement:** R17. **Criterion:** A25.

## Objective

A sprite file can keep itself out of the build. It is still checked and
previewed.

```toml
canvas = "unit"
build = false
```

## Dependencies

None in behaviour. It edits `_Parser.parse` in
`src/sprite_tool/spritefile.py` and the `Sprite` dataclass in
`src/sprite_tool/model.py`, which steps 01 and 02 also edit, so the plan runs
it after them. It can be built on 0.2.0 as it stands.

## Constraints

- Python 3.11 or later; Pillow is the only runtime dependency and `pytest` the only dev dependency. Add nothing.
- Tests need no display or network and write only under `tmp_path`, never into `examples/demo/` or `tests/golden/`. Tests that build copy the demo to `tmp_path` first (`copy_demo` in `tests/test_golden.py`, the `demo` fixture in `tests/test_build.py`).
- Success prints one summary line; each problem is one line.
- Export files are created, overwritten and deleted only through `manifest.py`.
- Every 0.2.0 project builds exactly as before.
- Do not change `examples/demo/` or `tests/golden/` in this step.

## Behaviour to implement

- `build` at the top of a sprite file. Default `true`. Any value that is not a bool is E001 (`build must be true or false`, as `_Parser._flag` words `outline` and `grounded` today).
- The sprite and its variants are parsed, checked, counted in the `ok:` line of `sprite check`, drawn by `sprite preview <id>` and shown on the contact sheet. A fault in it fails `check` and therefore `build`, like any sprite.
- `sprite build` leaves it and its variants out of every target and every index, and out of the counts in the `built:` and `up to date:` lines. Files exported for it by an earlier build are removed as stale.
- Its id is still its file stem and must be unique: two files with one stem are E003 whether or not either says `build = false`.

## Implementation guidance

- `model.py`: `Sprite.build: bool = True`, last in the dataclass with a default (plan decision P2). Variants inherit it through `dataclasses.replace` in `spritefile._variant`.
- `spritefile.py`: `_TOP_LEVEL_KEYS` gains `build`; `_Parser.parse` reads it with `_flag` and passes it to `Sprite`.
- `cli.py`, `_build`: there is one line that drops blank sprites before rendering (`sprites = [sprite for sprite in sprites if not check.is_blank(sprite)]`). Filter `sprite.build` in the same place. Everything after it (rendering, exporters, the counts) uses that list, and `manifest` removes the stale files on its own, because a file in the manifest that is no longer generated is deleted by `manifest.apply` and reported by `manifest.compare`.
- No change to `check.py`, `preview.py` or the exporters.

Not in this step: the guide's line about `build = false` (step 07), a demo
sprite that uses it (step 05), hiding such sprites on the contact sheet (the
design keeps them there).

## Verification

**A25**, as tests in `tests/test_build.py` (and `tests/test_spritefile.py`
for the field), on a copy of the demo with one extra sprite that says
`build = false`:

- `sprite check` counts it: the `ok:` line goes up by one sprite and its frames.
- `sprite preview <id>` writes its image and exits 0.
- After `sprite build` with all three target types configured, no file whose name starts with its id is in any output directory, and its id is not a key in the godot index (`<name>.json`) or in the Phaser atlas frames. The `built:` line does not count it.
- A variant of a `build = false` sprite is left out too.
- Build once with the sprite exported, add `build = false`, build again: its PNGs are gone, other files are untouched, and `build --check` is clean.
- A second file with the same stem in another directory is still E003.
- A fault in it (for example an unknown palette key) makes `sprite build` exit 1 and write nothing.
- `build = "no"` is E001 at the `build` line.

Commands: `uv run pytest tests/test_build.py tests/test_spritefile.py`, then
`make check`. Expected: all pass, and `make check` ends with
`ok: 4 sprites, 6 frames`.

## Completion criteria

- [ ] A25 has passing tests covering each clause above.
- [ ] Every earlier test still passes.
- [ ] `git status` shows no change under `examples/demo/` or `tests/golden/`.
- [ ] `make check` passes.
- [ ] The step's row in [index.md](index.md) is `done`, with a completion log entry (date, commit, test result).

**Handed to later steps:** `Sprite.build`, and `cli._build` exporting only
sprites with `build` set (step 04 validates adopt ids against that list;
steps 05 and 07 rely on the file field).
