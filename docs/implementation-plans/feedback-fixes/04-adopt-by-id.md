# Step 04: Adopt by id

- **Plan:** [index.md](index.md)
- **Design:** [feedback-fixes.md](../../designs/feedback-fixes.md), sections 4.4 and 5.5
- **Requirement:** R16. **Criteria:** A23, A24. Touches quality constraint Q2.

## Objective

`sprite build --adopt [id ...]`. With ids, only those sprites' files are
taken over. Every adopted file is named in the output.

## Dependencies

- **Step 03 (`build = false`).** It adds `Sprite.build: bool` and makes `cli._build` drop sprites with `build = false` in the same line that drops blank sprites. Adopt ids are validated against the sprites left after that line. If step 03 is not done, validate against the list after the blank filter; the only thing lost is the test that a `build = false` sprite's id is unknown to `--adopt`.

Existing code (inspected at 0.2.0): `--adopt` is `action="store_true"` in
`cli.build_parser`; `cli._build` calls `manifest.check_ownership(plans)`
unless `args.check` or `args.adopt`; `manifest.Plan.unowned` lists generated
files that exist on disk and are not in the manifest;
`manifest.check_ownership` raises `ConfigError` for the first directory that
has any.

## Constraints

- Python 3.11 or later; Pillow is the only runtime dependency and `pytest` the only dev dependency. Add nothing.
- Tests need no display or network and write only under `tmp_path`.
- Output: one summary line, plus one `adopted` line per adopted file before it. No other new output. Usage errors are `error: <message>` on stderr, exit 2.
- Export files are created, overwritten and deleted only through `manifest.py`. `cli.py` prints; it does not write.
- Nothing is written unless every output directory passes the ownership check.
- Do not change `examples/demo/` or `tests/golden/` in this step.

## Behaviour to implement

| Form | Effect |
|---|---|
| no flag | As now: an existing file not in the manifest stops the build (exit 2). |
| `--adopt` | As now: every such file is overwritten and added to the manifest. |
| `--adopt warrior goblin` | Only files belonging to those ids are taken. Any other unowned file still stops the build, and nothing is written. |

- A file belongs to an id when its name up to the first `.` is the id, or its name starts with the id followed by `__`. That covers `warrior.png`, `warrior__idle_0.png` and `warrior.tres`. It does not cover `warrior_red.png`: a variant is named separately.
- Shared files (`atlas.png`, `atlas.json`, `sprites.json`) belong to no id and need the bare flag. There is no special case for a sprite that happens to be named `atlas` (plan decision P9).
- Each id must be a sprite in this build: one that is exported, variants included, so not a blank sprite and not one with `build = false`. Otherwise exit 2: `error: unknown sprite id 'nosuch' (sprites: goblin, warrior, ...)`, listing the ids sorted, in the form `cli._preview` already uses for an unknown id.
- Ids are validated after check failures are reported (a project with errors exits 1 first) and before the ownership check (plan decision P8).
- After writing, one line per adopted file, before the summary, with the path as the user would type it (`cli._from_cwd`), sorted by directory then name. This applies to the bare flag too.

  ```
  adopted ../public/assets/sprites/goblin.png
  adopted ../public/assets/sprites/warrior.png
  built: 8 sprites, 8 frames, 1 target
  ```

- The stop message, for the first directory with an unowned file that is not covered. `N` counts the uncovered files after the first (plan decision P6):
  - one file: `<path> already exists and was not written by sprite-tool (use --adopt <id>... for those sprites, or --adopt for all)`
  - more: `<path> and 2 more already exist and were not written by sprite-tool (use --adopt <id>... for those sprites, or --adopt for all)`
- Help text for `--adopt`: `overwrite existing files the tool did not write: all of them, or only those of the given sprite ids`.
- `--check` still ignores `--adopt`, ids included: they are not validated (plan decision P7).

## Implementation guidance

- `cli.build_parser`: `--adopt` becomes `nargs="*"`, default `None`, with a `metavar` such as `id`. `None` is no flag, `[]` is all, a non-empty list is those ids. `build` has no positional arguments, so this parses cleanly. `cli._build` tests `args.adopt` for truth today; an empty list is falsy, so that test must change.
- `manifest.belongs_to(name, ids)`: the naming rule above, on a file name relative to its output directory.
- `manifest.check_ownership(plans, adopt_ids)`: `adopt_ids` is `frozenset[str] | None`. `None` means nothing is adopted; raise for unowned files not covered by the ids. The bare flag keeps skipping the call, or passes a value that covers everything; either is fine as long as `manifest` holds the rule.
- `cli._build` collects each plan's `unowned` list before `manifest.apply` and prints the `adopted` lines after it. With ids, every unowned file that survives the check is by definition adopted.
- Warnings are printed by `report` before the `adopted` lines; leave that order.

Existing tests that assert the old stop message or call
`check_ownership(plans)` with one argument will need their expectations
updated: `tests/test_manifest.py` (the tests from
`test_an_existing_file_not_in_the_manifest_blocks_the_build` to
`test_adopt_takes_ownership_and_overwrites`) and `tests/test_build.py`
(`test_an_unowned_file_blocks_the_build`,
`test_adopt_takes_ownership_of_existing_files`, which will now also see
`adopted` lines).

Not in this step: the README's `--adopt` section and command table, and the
output rule in `AGENTS.md` (step 08); the guide's command list (step 07).

## Verification

Manifest level, in `tests/test_manifest.py`:

- `belongs_to` for `warrior.png`, `warrior__idle_0.png`, `warrior.tres` (true for `warrior`); `warrior_red.png` (false for `warrior`, true for `warrior_red`); `atlas.png` and `sprites.json` (false for any sprite id in the test).
- `check_ownership` with ids: passes when every unowned file is covered; raises naming the first uncovered file and the right count otherwise; both message forms.

CLI level, in `tests/test_build.py`, on a copy of the demo with one `frames`
target:

- **A23.** With unowned `warrior.png` and `goblin.png` in the output directory, `sprite build --adopt warrior` exits 2, names `goblin.png` on stderr, and writes nothing (the directory holds the same bytes as before and no manifest). `--adopt warrior goblin` exits 0 and prints one `adopted` line for each before the `built:` line.
- **A24.** `sprite build --adopt nosuch` exits 2 with the `unknown sprite id` message.
- Bare `--adopt` prints an `adopted` line for every file it took.
- A second build prints no `adopted` line.
- `--adopt warrior` does not take `warrior_red.png`.
- `--adopt <id of a build = false sprite>` exits 2 (needs step 03).
- `--check --adopt nosuch` behaves as `--check`.
- `sprite build --help` shows the new help text.

Commands: `uv run pytest tests/test_manifest.py tests/test_build.py`, then
`make check`.

## Completion criteria

- [ ] A23 and A24 each have a passing test.
- [ ] Every earlier test passes, with the stop-message expectations updated.
- [ ] `git status` shows no change under `examples/demo/` or `tests/golden/`.
- [ ] `make check` passes.
- [ ] The step's row in [index.md](index.md) is `done`, with a completion log entry (date, commit, test result).

**Handed to later steps:** the command form `build --adopt [<id>...]` and
the `adopted` output line (steps 07 and 08 document them).
