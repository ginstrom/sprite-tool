# Step 11: Golden files, documentation and acceptance

- **Plan index:** [index.md](index.md)
- **Source design:** [docs/designs/sprite-tool.md](../../designs/sprite-tool.md), sections 5.6, 6, 7

## Objective

Lock the tool's output with golden files, prove determinism and speed, write
the user documentation, and run the manual acceptance checks in both engines.

## Requirements and context

- **Q1.** The same inputs produce byte-identical PNG, JSON and `.tres` files.
- **Q5.** A full build of 200 sprites completes in under 2 seconds on a laptop.
- **A8.** Running `sprite build` twice produces byte-identical output directories.
- **A14.** A project with a 32x32 `unit` sprite and a 16x16 `tile` sprite builds; both appear in one atlas at their own sizes.
- **A7 (manual half).** The Godot export loads in Godot 4.7 as a `SpriteFrames` resource and plays.
- The design requires `examples/demo` output committed under `tests/golden/`, with `build --check` against it passing.
- Installation documented in the design: `uv tool install git+https://github.com/ginstrom/sprite-tool`.
- Generated files are meant to be committed to the game repository, guarded by `sprite build --check` in each game's `make check`.

## Dependencies and prerequisites

All earlier steps. What this step relies on:

- **Steps 05 to 07:** `sprite build [--check] [--adopt]` with `frames`, `phaser` and `godot` targets. `examples/demo/sprite-tool.toml` has three `[[export]]` blocks writing to `out/frames`, `out/phaser` and `out/godot` (ignored by `examples/demo/.gitignore`). Each output directory holds a `.sprite-tool-manifest.json`. `build --check` prints `up to date: ...` and exits 0 when nothing differs, or `E401` lines and exits 1.
- **Step 03:** `sprite check`; demo sprites `warrior` (with variant `red`), `goblin`, `ground_light`.
- **Steps 08 to 10:** `preview`, `init`, `new`, `guide`, `import`.
- **Step 01:** `Makefile` with `test` and `check`; `AGENTS.md`; `README.md` (existing, says "design only").
- **Environment for manual checks:** sibling repositories `~/play/yomi` (Phaser 4, Vite, Node in a Podman container) and `~/play/fantasy-tactics` (Godot 4.7). Work only in scratch copies. Changing either game is a non-goal.

## Scope and implementation guidance

### Golden files (plan decision P12)

- `tests/golden/{frames,phaser,godot}/` (proposed): committed copies of the demo's three output directories, manifests included.
- `make golden`: build the demo and copy `examples/demo/out/*` over `tests/golden/`. Run it only when an output change is intended, and review the diff.
- Golden test: copy `examples/demo/` to `tmp_path`, copy `tests/golden/*` into its `out/`, run `sprite build --check`, expect exit 0.
- Golden PNG bytes depend on the Pillow minor version pinned in `pyproject.toml`. Say so in `AGENTS.md`: a Pillow bump means regenerating golden files.

### Further tests

- **A8:** copy the demo to two directories under `tmp_path`, build each, and compare every file byte for byte, manifests included. Also build twice in one directory and compare before and after.
- **A14:** in the built demo, the Phaser and Godot indexes show `warrior` at 32x32 and `ground_light` at 16x16 in the same sheet.
- **Q5:** generate a project of 200 sprites under `tmp_path` (copies of a demo unit under different ids, with all three targets), time one in-process `build`, and assert it finishes within a bound that tolerates slow machines (for example 5 seconds). Record the actual time on the author's laptop in the completion log; the target is under 2 seconds. If it misses, profile before optimising; PNG encoding and per-file overhead are the likely costs.
- **Clean output audit:** no generated file in `tests/golden/` contains an absolute path, a timestamp or the tool version.

### Makefile

`check` runs the tests and `uv run sprite check --project examples/demo`.

### Documentation

- `README.md` (exists): replace the "design only" status. Cover what the tool is for and when not to use it, installation, a quick start (`init`, edit, `check`, `preview`, `build`), the command table, the three export targets and how each game loads them, the manifest and `--adopt`, committing generated files with `build --check` as a guard, and a link to the design.
- `AGENTS.md` (exists from step 01): confirm it covers running tests, the shared constraints, the golden-file procedure and the module boundaries (exporters return bytes and never touch the disk; only `project.py` reads config and palette).
- Keep `sprite guide` as the agent-facing reference for drawing; the README should point to it and not duplicate the format in full.

### Manual acceptance

Record each result in the index completion log.

1. **Phaser (A6).** Already done in step 06. Confirm its result is in the completion log, and that the README states how to set the origin if `pivot` turned out not to be read.
2. **Godot (A7).** Add a `godot` target pointing into a scratch copy of fantasy-tactics' `assets/sprites` with the matching `res_path`, build, open `warrior.tres` in the editor, and play `idle` in an `AnimatedSprite2D`. Confirm Godot does not rewrite the `.tres` on open in a way that would make `build --check` fail later; if it does, record what changed.
3. **Agent trial.** In a fresh session, ask an agent to add one new unit to a copy of `examples/demo` using only `sprite guide`. It should reach a clean `build` without reading the design or the source. Record what it got wrong, and fix the guide text if the cause is there.

### Exclusions

No changes committed to either game repository. No new features.

## Verification

- `make check` passes from a clean clone (`git clone`, `uv sync`, `make check`).
- `uv run sprite build --project examples/demo` twice, then `git status` is clean.
- `make golden` on an unchanged tree produces no diff.
- The three manual results are recorded.

## Completion criteria

- [ ] `tests/golden/` committed; golden, A8, A14 and Q5 tests pass.
- [ ] `make golden` and `make check` work as described.
- [ ] README and AGENTS.md updated.
- [ ] Manual acceptance results for Godot and the agent trial recorded, and the step 06 Phaser result confirmed, with any follow-up fixes made.
- [ ] Every acceptance criterion A1 to A15 traced to a passing test or a recorded manual result.
- [ ] Index: all steps `done`, completion log filled in.
