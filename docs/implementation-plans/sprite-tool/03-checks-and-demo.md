# Step 03: Checks, `check` command and demo project

- **Plan index:** [index.md](index.md)
- **Source design:** [docs/designs/sprite-tool.md](../../designs/sprite-tool.md), sections 4.5, 4.6, 5.4

## Objective

Implement the checks that need a resolved grid, the PNG checks, and the
`sprite check` command with its output format. Create the example project in
`examples/demo/`, which later steps use as a test fixture.

## Requirements and context

- **R6.** `check` reports unknown palette keys, wrong dimensions and style-rule violations with file, line and column. It also checks PNG files for off-palette pixels and wrong dimensions.
- **Q2.** One line per problem on stdout; one summary line; no colour or banners.
- **A3.** A row too long, an unknown key and a missing outline pixel make `sprite check` exit 1 and print three problem lines with the correct `file:line:col`. *Plan decision P1:* the long row and unknown key are in one grid; the missing outline pixel is in a second frame of the same file, because a frame with parse problems is dropped before style checks.
- **A11.** `sprite check some.png --canvas unit` reports off-palette pixels by coordinate and a size mismatch.
- **A14 (part).** A 16-wide row in a 32x32 `unit` sprite is reported as E103.
- `E` codes fail the check (exit 1). `W` codes are printed and do not change the exit code.

### Command

`sprite check [paths...] [--canvas <class>] [--project <dir>]`

- With no paths, check every sprite file in the project.
- With paths, report only problems in those files. Still load every sprite file so duplicate ids are found.
- A `.png` path is checked as an image and needs `--canvas`; without it, exit 2.
- Success output: `ok: 12 sprites, 31 frames` (variants count as sprites). Warnings, if any, are printed before it.
- Failure output: problem lines sorted by path, line, column, code, then `2 errors, 1 warning in 2 files`. Exit 1.

### Problems this step reports

| Code | Problem |
|---|---|
| E003 | Duplicate sprite id, including variant ids. |
| E106 | Frame is fully transparent. |
| E201 | Outline rule violated at a pixel. At most 10 per frame, then one line with the remaining count. |
| E202 | Grounded rule violated. |
| E301 | PNG size does not match the canvas. |
| E302 | PNG pixel colour not in the palette, as `file.png:x,y: E302 ...` (zero-based). At most 10 per file, then a count. |
| W001 | Two palette keys share one colour. |
| W002 | Sprite has frames not used by any animation, when it declares at least one animation. |

- **Outline rule** (canvas `outline = ["k", ...]`, sprite not opted out). Every non-transparent pixel that touches a transparent pixel on one of its four sides must use a listed key. Outside the canvas counts as transparent. It runs on the final frame, after derivation and variant swaps, so a swap that recolours the outline to an unlisted key fails.
- **Grounded rule** (canvas `grounded = true`, sprite not opted out). The bottom row of every frame has at least one non-transparent pixel.
- **PNG checks.** A pixel with alpha 0 is transparent whatever its RGB. Any other pixel must match a palette colour exactly, including alpha.
- **Variants (plan decision P7).** For a sprite with `variant_of` set, run only E003 and E201, so one fault is not repeated per variant. Name the variant id in the E201 message.
- **Bad palette (plan decision P5).** If `project.load` returns any palette error, print those problems and the summary, exit 1, and do not check sprites.

## Dependencies and prerequisites

- **Step 01** provides `model.py` (`Color`, `Canvas`, `Frame`, `Sprite`, `Problem`, `Project`, `format_problem(problem, root)`), `project.load(root) -> tuple[Project, list[Problem]]`, and `cli.py` with a stub `check` handler and a helper that resolves and loads the project (exit 2 on config errors).
- **Step 02** provides `spritefile.load_all(project, paths=None) -> tuple[list[Sprite], list[Problem]]`. It reports E001, E101 to E105 and E107, expands variants into ordinary sprites, and drops frames that failed to resolve.
- **Positions.** `Frame.line` and `Frame.literal` from step 01: for a literal frame, pixel `(row r, col c)` is at file line `line + r`, column `c + 1`. For a derived frame, report at `line`, column 1, and put `row r, col c` in the message.
- Pillow is already a dependency (step 01).

## Scope and implementation guidance

### `src/sprite_tool/check.py` (proposed)

- `run(project: Project, sprites: list[Sprite]) -> list[Problem]`: E003, E106, E201, E202, W001, W002.
- `check_png(project: Project, path: Path, canvas: Canvas) -> list[Problem]`: E301, E302. For these, `Problem.col` is x and `Problem.line` is y; extend `format_problem` (or format locally) to print `path:x,y:`.
- E003 is reported at each clashing file, line 0.
- W001 is reported at the palette file.

### `src/sprite_tool/cli.py` (exists after step 01)

Replace the `check` stub. Add two helpers that steps 05, 08 and 09 will call:

- `load_checked(args) -> tuple[Project, list[Sprite], list[Problem]]`: load the project, load all sprites, run `check.run`, return all problems sorted.
- `report(problems, root) -> int`: print each problem with `format_problem`, then the failure summary line if there are errors; return the error count. It prints warnings but no summary when there are no errors, so the caller can print its own success line.

### `examples/demo/` (proposed)

A complete small project. Sources only in this step; add no `[[export]]` blocks
(steps 05 to 07 add them).

- `sprite-tool.toml`: `version = 1`; `[canvas.unit]` `size = [32, 32]`, `anchor = [16, 32]`, `display_scale = 2`, `outline = ["k"]`, `grounded = true`; `[canvas.tile]` `size = [16, 16]`, `anchor = [0, 0]`, `display_scale = 4`; `[preview]` `scale = 6`, `background = "#3a3a3a"`.
- `palette.toml`: the Sweetie 16 palette with mnemonic keys and names. Suggested keys: `k` `#1a1c2c` outline, `R` `#5d275d`, `r` `#b13e53`, `o` `#ef7d57`, `y` `#ffcd75`, `g` `#a7f070`, `G` `#38b764`, `t` `#257179`, `B` `#29366f`, `b` `#3b5dc9`, `c` `#41a6f6`, `C` `#73eff7`, `w` `#f4f4f4`, `l` `#94b0c2`, `d` `#566c86`, `D` `#333c57`.
- `units/warrior.sprite.toml`: 32x32, facing right; frame `idle_0` as a full grid; `idle_1` derived with `from` + `rows`; `[anim.idle]` with both frames at `ms = 400`; `[variants.red]` with `swap = { b = "r", B = "R" }`.
- `units/goblin.sprite.toml`: 32x32, one frame, no animations.
- `tiles/ground_light.sprite.toml`: 16x16, one frame.
- `.gitignore` containing `.preview/` and `out/`.
- `sprite check --project examples/demo` must print `ok: 4 sprites, 6 frames` with no warnings.

### Exclusions

No rendering to files, no build, no preview.

## Verification

`make test` (`uv run pytest`). Tests copy fixtures to `tmp_path` when they need
to change them and never write into `examples/demo/`. No network or display.
Proposed `tests/test_check.py`:

- One fixture per code in the table; assert code, line and column.
- **A3:** the combined fixture gives exit 1, exactly three problem lines with correct positions, then the summary line.
- Outline: a pixel at the canvas edge counts as touching transparency; `outline = false` on the sprite suppresses E201; a variant whose swap recolours the outline gets E201 naming the variant; the E201 cap of 10 plus a count line.
- Grounded: empty bottom row fails; `grounded = false` suppresses it.
- Variants do not duplicate E106, E202 or W002.
- E003 for two files with the same stem, and for a variant id equal to another sprite's id.
- W001 and W002 print but exit 0.
- **A11:** a fixture PNG (written by the test with Pillow) of the wrong size gives E301; one with a single off-palette pixel gives `...:x,y: E302`; an alpha-0 pixel with any RGB passes. A `.png` path without `--canvas` exits 2.
- **A14 (part):** a 16-wide row in a `unit` sprite gives E103.
- A bad palette exits 1 and reports no sprite problems.
- `sprite check <one file>` reports only that file's problems.
- The demo project checks clean with the expected summary line.

## Completion criteria

- [ ] `check.run`, `check.check_png`, `cli.load_checked` and `cli.report` exist as described.
- [ ] `sprite check` output and exit codes match this file.
- [ ] `examples/demo/` exists and checks clean.
- [ ] A3, A11 and the E103 part of A14 have tests.
- [ ] `make test` passes.
- [ ] Index status and completion log updated.
