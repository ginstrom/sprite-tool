# Step 01: Runs

- **Plan:** [index.md](index.md)
- **Design:** [feedback-fixes.md](../../designs/feedback-fixes.md), sections 4.2 and 5.2
- **Requirement:** R14. **Criteria:** A18, A19, A20.

## Objective

A frame table can place pixels by coordinate with `runs`, and no longer needs
`from`. After this step both of these parse:

```toml
[frames.idle_1]
from = "idle_0"
runs = { 9 = [[13, "ddsskh"]] }         # row 9, starting at column 13

[frames.main.runs]                      # a whole frame, no `from`
9  = [[13, "ddsskh"]]
10 = [[12, "dssssskh"], [24, "kk"]]
```

## Dependencies

None. Everything this step builds on exists in 0.2.0.

## Constraints

- Python 3.11 or later; Pillow is the only runtime dependency and `pytest` the only dev dependency. Add nothing.
- Tests need no display or network and write only under `tmp_path`, never into `examples/demo/` or `tests/golden/`.
- Each problem is one output line. Bad art never raises: it becomes a `Problem` and parsing carries on.
- Every 0.2.0 sprite file parses to the same sprite as before.
- Do not change `examples/demo/` or `tests/golden/` in this step.

## Behaviour to implement

- `runs` maps a zero-based row index to a list of runs. A run is `[column, "pixels"]`: a zero-based column and one or more characters, each a palette key or `.`. It replaces exactly those pixels. `.` writes transparency, which is how a derived frame erases.
- Runs in a row apply in list order, so a later run wins an overlap.
- A frame table's operations apply in the order `rows`, `runs`, `shift`, `flip`.
- `from` is optional. A table without it starts from a fully transparent canvas (`canvas.height` rows of `canvas.width` dots).
- A table with none of `from`, `rows` and `runs` is E001: `frame 'x': needs from, rows or runs`.

Problems:

| Case | Report |
|---|---|
| Row index not `0` to height − 1 | E105, worded as the existing `rows` message with `runs` in place of `rows` |
| A value that is not a list of `[integer, string]` pairs, or an empty string | E001 |
| Column outside the canvas, or the run passes the right edge | E103 `frame 'main' row 9: run at col 30 is 6 wide, canvas is 32 wide` |
| Unknown key | E104 `unknown palette key 'x' in frame 'main' row 9, col 15`. The column is the one on the canvas (run column plus offset). |

Each is reported at column 1 of the line of that row's key in the table form
(`9 = ...` under `[frames.main.runs]`), or of the line of `runs` in the
inline form. E104 shares the frame's cap of 10 (`MAX_E104_PER_FRAME`) with
any `rows` in the same table, with the usual `N more unknown palette keys`
line after it. A frame with any of these problems is dropped, as a frame with
a bad `rows` entry is today.

## Implementation guidance

All in `src/sprite_tool/spritefile.py` (inspected):

- `_FRAME_KEYS` gains `runs`.
- `_Derived.parent` becomes `str | None`, and it gains `runs: dict[int, list[tuple[int, str]]]`. `_Derived.apply` writes runs after rows and before shift.
- `_Parser._derived` stops requiring `from`, validates `runs`, and reports the "needs from, rows or runs" case. It creates one `_RowCheck` for `rows` today; use the same instance for runs so the E104 cap is shared. `_RowCheck.row` checks a full row against the canvas width, so it needs a way to check a fragment at a column offset without the width test.
- `_Parser._resolve` walks `pending[name].parent`; with no parent a frame resolves straight from the blank canvas. Its `Frame` has `literal=False`, `parent=None`.
- `_Parser._frames` reports `frame 'x' must be a grid string or a table with from` for a value of the wrong type. Reword it now that `from` is optional.
- **Line numbers.** `_scan` records a table header only under its own path, so for a file whose frame is written only as `[frames.main.runs]`, `("frames", "main")` has no line and `self.line("frames", "main")` returns 0. Give such a frame the line of its `runs` header, so that problems reported at the frame (`check._at_frame`) still have a position. In the table form `_scan` does record `("frames", "main", "runs", "9")`, which is the line a row's problems go to.

`model.Frame` does not change. Nothing outside `spritefile.py` needs to know
about runs: `Frame.rows` is still the final grid.

`check._inherited_faults` (inspected) already returns an empty set for a
frame with `parent=None`.

Not in this step: the guide text for runs (step 07), a demo sprite that uses
runs (step 05), `sprite new --runs` (an open question in the design).

## Verification

Add tests to `tests/test_spritefile.py`, which has the existing derived-frame
tests to follow, and a rendered comparison where the criterion says "renders"
(`tests/test_build.py` has `test_a4_a_frame_derived_with_rows_renders_as_the_same_frame_written_in_full` as a model).

- **A18.** A frame given as `runs` with no `from` renders identically to the same frame written as a full grid.
- **A19.** A derived frame with `runs = { 9 = [[13, "ddsskh"]] }` differs from its `from` frame in exactly those six pixels. (Pick keys the test palette has.)
- `.` in a run erases a parent pixel.
- Two overlapping runs in one row: the later wins.
- Order: a frame with `rows`, `runs`, `shift` and `flip` together gives the grid that applying them in that order by hand gives.
- **A20.** Each row of the problems table: code, line and message, in both the inline and the table form. A run that passes the right edge and a run with an unknown key are each one line naming frame, row and column.
- More than 10 unknown keys across `rows` and `runs` of one frame: 10 lines, then the count line.
- A table with none of `from`, `rows`, `runs`: the E001 above.
- A runs-only frame written as `[frames.main.runs]` has a non-zero `Frame.line`.

Commands: `uv run pytest tests/test_spritefile.py`, then `make check`.
Expected: all pass, and `make check` ends with `ok: 4 sprites, 6 frames`.

## Completion criteria

- [ ] A18, A19 and A20 each have a passing test.
- [ ] Every test that passed before this step still passes (900 before the step).
- [ ] `git status` shows no change under `examples/demo/` or `tests/golden/`.
- [ ] `make check` passes.
- [ ] The step's row in [index.md](index.md) is `done`, with a completion log entry (date, commit, test result).

**Handed to later steps:** sprite files may use `runs` and omit `from`
(steps 02, 05, 07 rely on it).
