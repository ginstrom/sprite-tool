# sprite-tool 0.4: a text view, and runs that get found

- **Date:** 2026-10-12
- **Status:** Implemented in 0.4.0. Assumptions and
  non-blocking questions are in [section 8](#8-open-questions-and-assumptions).
- **Amends:** [sprite-tool.md](sprite-tool.md) (the base design) and follows
  [feedback-fixes.md](feedback-fixes.md) (release 0.3). Requirement and
  criterion ids continue their numbering (the last were R19 and A27). Where
  this document and the base design disagree, this document wins;
  [section 6](#6-consequences) lists the base sections to bring in line.
- **Source:** feedback from one session that used sprite-tool 0.3.0 to draw
  five item icons for Yomi (`~/play/yomi`, `art/icons/icon_{wand,ring,amulet,circlet,cloak}.sprite.toml`).
  The feedback was given in conversation, so each point is restated here,
  together with what inspection of that session showed about it.

## 1. Purpose

The session drew five 20x20 icons. They passed `sprite check` first time and
were built without trouble, but the agent did not write the sprite files: it
wrote a throwaway Python script that placed short strings at `x, y` and
dumped full grids. That is the failure release 0.3 was meant to end.

The agent then gave three points of feedback. Checked against the tool and
the session's transcript, they come out differently from how they were put:

| # | Feedback as given | What inspection showed |
|---|---|---|
| 1 | "The format has `runs` for derived frames but nothing similar for a base frame." | **Wrong.** A whole frame can be runs alone (`[frames.main.runs]`), and the guide the agent had read says so. The script's one helper, `put(g, x, y, "pixels")`, is a run. The feature was there and was not found. |
| 2 | "A line or ellipse primitive would help most" for diagonals and curves. | **Not supported.** The wand's diagonal was a nine-step loop placing two pixels a row, which is nine run lines. The ring's band was typed by hand as eight rows of text. No curve was computed anywhere in the script. |
| 3 | "`check` says the source is valid, not that it looks like anything"; a text rendering in the terminal would make a second look cheap. | **Holds.** There is no way to see a resolved frame without opening a PNG, and with `runs` and `outline = "auto"` the source no longer looks like the result. |

So the real problems are two: whole-frame runs are documented where an agent
does not look, and there is no text view of what a sprite file resolves to.
The outcome is a 0.4.0 release in which an agent that reads `sprite guide`
sees a whole frame drawn as runs in the example, can start a file in that
form, and can print any sprite's finished grid to the terminal.

## 2. Requirements and scope

### Functional requirements

| ID | Requirement | Feedback point |
|---|---|---|
| R20 | `sprite show <id>...` prints the resolved grid of a sprite's frame as text, with row and column numbers: the pixels `build` would export, after `rows`, `runs`, `shift`, `flip`, the automatic outline and variant swaps. It writes no file. | 3 |
| R21 | The guide's example sprite file contains a whole frame written as runs, the guide says when to choose runs over a grid, and it lists `sprite show`. | 1 |
| R22 | `sprite new <id> --canvas <class> --runs` writes a blank sprite file in runs form. | 1 |
| R23 | The places an agent meets before it draws say outright that pixels are placed with runs and not with a generator script: the guide, the note `sprite init` prints for the game's agent instructions, and `sprite --help`. | 1 |

### Quality constraints

The base design's Q1 to Q5 still hold. One is touched:

- **Q2 (token-friendly output).** `sprite show` prints a grid, which is many
  lines. Like `guide`, its output is what was asked for, not a report on a
  job done. It prints nothing else on success, and by default one frame per
  id, so the cost is the canvas height plus three lines.
- **Q3 (thin).** No new dependency and no drawing primitive. `show` does not
  use Pillow.

**Compatibility.** Every 0.3.0 project loads, checks and builds unchanged.
No generated file changes, so `build --check` stays clean across the upgrade
and the golden files are untouched.

### Non-goals

- **Line, ellipse or fill primitives.** They stay a non-goal of the base
  design. Point 2 above is the evidence: the one session that asked for them
  did not compute a single shape, and its diagonal is nine lines of runs.
- **A block placed at an offset** (a small grid with an `at = [x, y]`). Three
  of the five icons were drawn in the script as a block of rows put at one
  origin. Runs express the same thing with a column per row, and `show`
  gives back the aligned picture that the block form had. Revisit only if a
  session that knew about runs still reaches for a script.
- **Making runs the default of `sprite new`**, or choosing by canvas size
  (see question 1).
- **Converting a file between the grid and runs forms.**
- **Colour in the terminal** (ANSI blocks). It breaks Q2 and an agent reads
  the keys, not the colours.
- **`sprite preview --text`.** `preview` writes images and takes `--scale`,
  `--grid` and `--on`, none of which mean anything for text; a flag would
  need a usage error for each.
- **Changes in Yomi.** They have their own design in the Yomi repository,
  `docs/designs/sprite-drawing-guidance.md`.

### Acceptance criteria

| ID | Criterion | Covers |
|---|---|---|
| A28 | In the demo, `sprite show slime` exits 0, writes no file, and prints a header, a column ruler and 32 numbered rows. The rows equal the slime's resolved default frame, including outline pixels (`k`) that appear nowhere in its source. | R20 |
| A29 | A sprite written as a grid and the same picture written as runs print identical output apart from the id in the header. | R20 |
| A30 | `sprite show warrior` prints only the default frame. `--frame idle_1` prints that frame, `--all` prints every frame in file order, and `sprite show warrior_red` prints the variant's swapped keys. | R20 |
| A31 | `sprite show nosuch` and `sprite show warrior --frame nosuch` exit 2 with a message naming the known ids or frames, and print no grid. | R20 |
| A32 | A sprite whose only problem is an outline fault (E201) has the problem printed and its grid shown, exit 0. A sprite with an unknown palette key (E104) has the problem printed, no grid, exit 1. | R20 |
| A33 | `guide.EXAMPLE` contains a `[frames.<name>.runs]` table that is a whole frame, and the example still checks clean on a 6x4 canvas. `sprite guide` for the demo names `sprite show` and `new ... --runs` and is under 90 lines. | R21 |
| A34 | `sprite new gem --canvas icon --runs` writes a file holding `[frames.main.runs]` and no grid. `sprite check` reports it as W003 (blank) and nothing else. Adding one run line makes it a drawn sprite. | R22 |

| A35 | `sprite guide` contains the sentence of 4.4 that names a generator script. The note `sprite init` prints names `runs` and `sprite show`. `sprite --help` tells the reader to run `sprite guide` before drawing, and `sprite new --help` describes `--runs`. | R23 |

## 3. Current system

Inspected in the 0.3.0 source (commit `9aa7eaf`), in Yomi's `art/`, and in
the transcript of the session.

**What the session did**

- It ran `sprite guide --project art` and read two existing icon sources,
  both full grids. Yomi's guide is 83 lines; all of it was read.
- It wrote a script with `put(g, x, y, s)`, which writes the characters of
  `s` into row `y` from column `x` and skips spaces. Every pixel of all five
  icons went through that one function: a loop for the wand's diagonal and
  the amulet's chain, single calls for small details, and lists of
  hand-typed rows for the ring's band, the circlet and the cloak.
- The files it wrote are full 20x20 grids with `outline = "auto"`.
- It ran `check` once (clean), one `preview` of the five beside an existing
  icon, and `build`. It did not iterate on any icon.

**Why whole-frame runs were missed**

| Place | What it shows |
|---|---|
| `guide.EXAMPLE` | `runs` appears once, as operation 2 of a frame under the comment "a derived frame". The comment on `from` does say "optional ... without it, a blank canvas". |
| `guide._FORMAT` | Lines 7 and 8 of an eleven-line paragraph: "A whole frame can be runs alone, with no grid: `[frames.main.runs]`, then one line for each row that has pixels". Correct, and easy to pass over. |
| `cli._new` | Writes `[frames]` and a grid of dots. There is no runs form. The previous design left this as its question 2, to be decided "after the manual acceptance run shows which form an agent reaches for". |
| The game's sources | Every sprite in Yomi is a grid. Only the demo's `slime.sprite.toml` is drawn as runs. |
| Yomi's `art/CLAUDE.md` | Does not mention runs or `outline = "auto"`. It was written from the note `sprite init` prints (`cli.agent_note`), which says only how to install the tool and to run `sprite guide`. |
| `sprite --help` | Lists `guide` as "print the format reference, palette and canvas classes", third in a list of seven commands, with nothing to say it comes first. The session did not run it. |

Everything an agent copies from says "grid", and one sentence of prose says
otherwise.

**Seeing the result**

- `cli._preview` writes PNGs to `.preview/` and prints their paths. Looking
  means reading an image file.
- After parsing, `Frame.rows` is the final grid that is checked, rendered and
  exported (the invariant in section 5.2 of the previous design; the
  automatic outline is applied in `_Parser.parse`, variant swaps in
  `spritefile._variant`). Nothing prints it.
- `preview --grid` labels every fourth row and column in the image
  (`preview._frame_tile`).

**Relevant structure.** `cli.HANDLERS` has one entry per subcommand.
`cli._preview` resolves ids against sprites and against file stems (so a file
too broken to give a sprite is still a known id), narrows the problems to the
files involved, and treats the style codes (`_STYLE_CODES`: E106, E201, E202)
as printable but not fatal. `guide.EXAMPLE` is asserted to check clean by
`tests/test_init_new_guide.py`, and another test there finds the example's
one line that starts with `runs = `. The demo's guide prints 76 lines against
a limit of 80.

## 4. Proposed behavior

### 4.1 `sprite show` (R20)

```
sprite show <id>... [--frame <name>]... [--all] [--project <dir>]
```

For each id, in the order given (repeats dropped), it prints one block per
chosen frame. Blocks are separated by one blank line.

```
icon_ring base  icon 20x20
              1111111111
    01234567890123456789
 0  ....................
 1  ....................
 2  ....................
 3  ........kkkk........
 4  .......kRrrRk.......
 5  ......kRroorRk......
```

(and so on to row 19.)

- **Header:** `<sprite id> <frame name>`, two spaces, `<canvas class> <width>x<height>`.
- **Ruler:** the units digit of every column. Above it, when the canvas is
  wider than 10, the tens digit of every column from 10 on, with spaces over
  columns 0 to 9. Both lines are indented to the grid's first column.
- **Rows:** the zero-based row number, right-aligned to the width of the
  largest, two spaces, then the row exactly as it is in `Frame.rows`: palette
  keys and `.`.
- No line has trailing whitespace. Rows and columns count from 0, the same
  numbers `runs`, `rows` and the check messages use.

**Which frames.** With neither flag, the default frame (the first). Each
`--frame <name>` adds that frame; `--all` shows every frame in file order.
The two together are a usage error. A `--frame` name applies to every id
given and must exist in each.

**Variants.** A variant is a sprite with its own id, so `show warrior_red`
prints the swapped grid. `show warrior` prints the base only.

**Problems.** As `preview` does for the ids it is given:

| Case | Output | Exit |
|---|---|---|
| Clean | The blocks only. | 0 |
| Warnings only (a blank sprite, W003, among them) | The blocks only; warnings are not printed. A blank sprite prints a grid of dots. | 0 |
| Style problems only (E106, E201, E202) | The problems and the failure summary, then the blocks. | 0 |
| Any other error in a file involved | The problems and the summary; no block for any id. | 1 |
| Palette error | The problems and the summary. | 1 |
| Unknown id | `error: unknown sprite id 'nosuch' (sprites: ...)` on stderr. | 2 |
| Unknown frame | `error: sprite 'warrior' has no frame 'nosuch' (frames: idle_0, idle_1)` on stderr. | 2 |
| `--frame` with `--all` | `error: --frame cannot be used with --all` on stderr. | 2 |

A sprite with `build = false` is shown like any other.

**What it is for.** The loop becomes `check` until `ok`, `show` to see the
shape and count positions, `preview` for colour and game size, `build`. The
guide says so (4.2).

### 4.2 Guide (R21)

`EXAMPLE` gains a third frame, written as runs with no `from`, and the
animation lists it so the example still has no unused frame (W002):

```toml
[frames.idle_2.runs]       # a whole frame as runs, no grid: one line per row that has pixels
0 = [[1, "kkkk"]]          #    row = [[column, "pixels"], ...]; the rest stays transparent
1 = [[0, "kbwwbk"]]
2 = [[0, "k"], [1, "bBBb"], [5, "k"]]
3 = [[1, "kkkk"]]
[anim.idle]                # optional
frames = ["idle_0", "idle_1", "idle_2"]
```

In `_FORMAT`, the two lines that describe whole-frame runs in prose are
replaced by one line of advice:

```
Write a grid when the picture fills the canvas, runs when it is mostly empty or too wide to count
across. `sprite show <id>` prints either as the finished grid, outline included.
```

In `_COMMANDS`:

```
sprite new <id> --canvas <class> [--dir <subdir>] [--runs]
                                                    write a blank sprite file to draw in; --runs
                                                    starts it as runs, not a grid of dots
sprite show <id>... [--frame <name>] [--all]        print the finished grid as text, with row and
                                                    column numbers; the default frame unless told
```

The line limit for the demo's guide rises from 80 to 90.

### 4.3 `sprite new --runs` (R22)

```
sprite new gem --canvas icon --runs
```

writes

```toml
canvas = "icon"

[frames.main.runs]
# One line per row that has pixels, rows and columns from 0:
# <row> = [[<column>, "<pixels>"], ...]
```

- Without `--runs` the file is what 0.3.0 writes.
- The two comment lines are the only comments `new` writes. A table with
  nothing under it gives an agent nothing to copy, and the grid form shows
  its own shape.
- The file is a blank sprite: `check` reports W003 and `build` leaves it out,
  exactly as for the grid form (verified against 0.3.0 with this file in a
  copy of the demo).
- It does not set `outline = "auto"` (see the assumptions).
- Every other rule of `new` is unchanged: the id pattern, `--dir`, refusing
  an existing file or a used id, printing the path.

### 4.4 Saying it where it is read (R23)

The session touched four things before it drew: the game's own instructions
for `art/`, `sprite guide`, two existing sources, and nothing else. It never
ran `--help` or `sprite new`. More text in help reaches an agent only if it
runs help, so the weight goes on the first two, and each says the same thing
in words that name the mistake:

- **Guide**, as the last line of the advice in 4.2:

  ```
  Do not write a script to generate a grid: placing pixels at a row and column is what runs do.
  ```

  The session's agent read "a whole frame can be runs alone" and still
  scripted, because nothing joined that sentence to what it was about to do.
  This line is written for the moment of reaching for a script.
- **The `init` note** (`cli.agent_note`), which a game pastes into its agent
  instructions and which therefore loads without being asked for, gains one
  sentence:

  ```
  Draw with runs (`[frames.main.runs]`, pixels placed by row and column) or a grid, never with a
  script that generates one, and look at the result with `sprite show <id>`.
  ```

- **`sprite --help`** gains an epilog:
  `Run "sprite guide" before drawing: it has the file format, this project's palette and the commands.`
  The help line of `new` becomes `write a blank sprite file, as a grid or with --runs as runs`,
  and `show` is listed as `print a sprite's finished grid as text`.

Not proposed: a hint from `check` on a sprite whose grid is mostly dots. It
would fire on every existing sprite of every game, on each run, to tell the
author about a choice that is theirs to make.

## 5. Technical design

Paths are relative to the repository root. Files marked *proposed* do not
exist yet.

### 5.1 Text view (`src/sprite_tool/textview.py`, *proposed*)

- `frame_text(sprite: Sprite, frame: Frame) -> str`: the block of 4.1 for
  one frame, ending in a newline. A pure function of its arguments. It reads
  `sprite.id`, `sprite.canvas` and `frame.rows` and nothing else.
- No import of Pillow or of `preview.py`. It is its own module so that a
  text view never pulls in image code.
- Invariant: the rows printed are `frame.rows` unchanged. The module draws
  nothing and resolves nothing.

### 5.2 CLI (`src/sprite_tool/cli.py`)

- `_show(args)` and a `show` entry in `HANDLERS`. Parser: `ids` with
  `nargs="+"`, `--frame` with `action="append"`, `--all` as a flag, and the
  shared `--project` parent.
- The first half of `_preview` (palette failure, resolving each id against
  sprites and file stems, narrowing problems to the files involved, the
  style-code rule) is what `_show` needs too. Move it to one helper that
  both call, returning the sprites by id or an exit code, so the two
  commands cannot drift apart on what counts as fatal.
- `_show` then picks frames per sprite, checks `--frame` names against
  `sprite.frames` (exit 2 before printing any block), and prints the blocks
  joined by blank lines.
- `_new`: a `--runs` flag chooses between the grid text it builds now and
  the text of 4.3. The canvas size is not used in the runs form.

### 5.3 Guide (`src/sprite_tool/guide.py`)

The text of 4.2. `EXAMPLE` must stay a complete file that checks clean on a
6x4 canvas whose palette has `k`, `w`, `b`, `B`, `r` and `R`, on a class
with `outline = ["k"]`; the runs frame above is outlined in `k` throughout.

### 5.4 Help and the init note (`src/sprite_tool/cli.py`)

`agent_note` returns the sentence of 4.4 after its two existing ones;
`build_parser` gets the epilog and the changed help lines. The existing
test checks only how the note's line starts, so the new sentence needs a
test of its own.

### 5.5 Nothing else changes

No change to `spritefile.py`, `check.py`, `model.py`, the exporters, the
manifest, the templates or the demo. No new problem code.

## 6. Consequences

- **A second multi-line command.** `show` joins `guide` as a command whose
  output is its product. `AGENTS.md`'s output rule gains it: on success it
  prints the grid blocks and no summary line.
- **The guide grows** by about nine lines (five of example, four of
  commands), to about 85 for the demo and 92 for Yomi's 28-colour palette.
  Moving whole-frame runs from prose into the example is what buys the
  discovery.
- **Golden files are untouched.** No export, index or manifest changes.
- **A sprite file written by `new --runs`** is valid on 0.3.0 as well, since
  the form is already supported. Only the command is new.
- **Drawing primitives stay out.** This is the second session to end in a
  generator script. Both times the script placed strings at coordinates, and
  neither computed a shape. If a third session knows about runs and `show`
  and still scripts, the evidence will say what to add.
- **Tests that pin the example** need care: the test that isolates the line
  starting with `runs = ` still finds exactly one, since the new frame uses
  the table form.
- **Documents to update** when this is implemented: the base design's
  section 2 (Q2 wording, A13/A26 line limit), 4.5 (the command table: `new`,
  `show`), and its statement of what `new` writes; `README.md` (command
  table, a short section on `show`, the install tag); `AGENTS.md` (the output
  rule, `textview.py` in the layout, the link to this design and its plan);
  the version in `pyproject.toml` and `uv.lock`, to 0.4.0.
- **A game set up before 0.4 keeps its old note.** `init` prints the note
  once and the game owns the copy, so Yomi's `art/CLAUDE.md` does not change
  by upgrading. The README's upgrade section says to add the new sentence.
- **Yomi's own changes** are designed in the Yomi repository,
  `docs/designs/sprite-drawing-guidance.md`: its `art/CLAUDE.md` and
  variants for the items that share an icon. Only its move to `v0.4.0`
  waits on this work.

## 7. Verification

`make check`. Tests follow the existing constraints: no display, no network,
writes only under `tmp_path`.

| Area | Test | Criteria |
|---|---|---|
| Text view | `frame_text` on small canvases: header, units ruler, tens ruler only above width 10, row numbers aligned for heights of 4 and of 32, no trailing whitespace, rows equal to `frame.rows`. | A28 |
| `show` on the demo | The slime's output holds a `k` in a row and column its source leaves empty. A grid sprite and its runs twin (written under `tmp_path`) differ only in the header. Nothing is created under the project, `.preview/` included. | A28, A29 |
| Frames and variants | Default frame only; `--frame`; several `--frame`; `--all` in file order; a variant id shows swapped keys; a `build = false` sprite is shown. | A30 |
| Usage errors | Unknown id; unknown frame, with the frame list in the message; `--frame` with `--all`; no id given. Each exits 2 and prints no grid. | A31 |
| Problems | E201 only: problem lines, summary, then the block, exit 0. E104: problem lines, no block, exit 1. A palette error: exit 1. A clean sprite beside a broken file not named on the command line: the block only. | A32 |
| Guide | `EXAMPLE` checks clean and has a whole-frame runs table; `show` and `--runs` are named; the prose advice line is present; demo under 90 lines; the existing example tests pass. | A33 |
| `new --runs` | The file's exact text; W003 and nothing else from `check`; with one run line added, `check` counts a drawn sprite; `--dir`, an existing file and a used id behave as without the flag; without the flag the output is byte-identical to 0.3.0's. | A34 |
| Help and note | The guide's script sentence; `agent_note` names runs and `sprite show`; the top-level help's epilog; the help lines of `new` and `show`. | A35 |
| Golden and determinism | Existing tests, unchanged golden files. | Q1 |

**Manual acceptance.** In a scratch copy of Yomi's `art/`, have an agent
that has read only `sprite guide` draw one new 20x20 icon and one 32x32 unit.
It passes when no generator script is written, and when the agent uses
`sprite show` at least once before `build`. Which form it starts each file
in answers question 1.

## 8. Open questions and assumptions

Nothing here blocks planning.

### Assumptions

- **Discovery was the whole of point 1.** The agent's script and runs do the
  same thing, so it is assumed an agent that sees a runs frame in the
  example will write one. This rests on one session, and the manual
  acceptance run is what tests it.
- **One frame by default is the right economy.** Every sprite in Yomi has one
  frame, so the session gives no evidence about animated sprites. A
  four-frame unit shown whole is about 140 lines, which is why `--all` is
  asked for and not assumed.
- **A two-line ruler reads better than labels every fourth column.** The
  need is to count to an exact column, which the image grid's sparse labels
  serve less well.
- **`new --runs` should not set `outline = "auto"`.** The two go together in
  the demo's slime and in the session's icons, but one is a way of writing
  pixels and the other a rule about them, and a class with no outline rule
  would make the pair an error.

### Questions (non-blocking)

1. **Should runs be the default of `sprite new` on a large canvas?** A grid
   of 32 dotted rows is the weakest starting point the tool offers, and it
   is what `new` gives for a unit. Left as a flag here because changing the
   default changes what every existing project's agents see, on the evidence
   of one session that never ran `new` at all.
2. **Should `show` mark the pixels the tool drew?** Printing the automatic
   outline in a different character would show interior and outline apart,
   at the cost of the output no longer being the grid that is exported. Not
   proposed; the plain grid answers the question that was asked.
