"""Frame lengths, `like`, and `sprite preview --anim`."""

import json
import shutil
from pathlib import Path

import pytest
from PIL import Image

from conftest import write_project
from sprite_tool import check, preview
from sprite_tool.cli import main
from sprite_tool.model import Anim, format_problem
from sprite_tool.preview import CHAR_WIDTH, GAP, LABEL_GAP, LINE_HEIGHT, MARGIN
from sprite_tool.project import load
from sprite_tool.spritefile import load_all

DEMO = Path(__file__).parent.parent / "examples" / "demo"

CONFIG = """\
version = 1

[canvas.unit]
size = [4, 3]
anchor = [2, 3]
display_scale = 2

[preview]
scale = 5
background = "#3a3a3a"

[[export]]
type = "frames"
out = "out/frames"

[[export]]
type = "phaser"
out = "out/phaser"
"""

PALETTE = """\
[colors]
k = "#000000"
w = "#ffffff"
r = "#ff0000"
"""

BACKGROUND = (0x3A, 0x3A, 0x3A, 255)
BLACK, WHITE, RED = (0, 0, 0, 255), (255, 255, 255, 255), (255, 0, 0, 255)

# `[anim.idle]` is on line 15.
HERO = '''\
canvas = "unit"

[frames]
a = """
kk..
kk..
....
"""
b = """
....
ww..
ww..
"""

[anim.idle]
frames = ["a", { frame = "b", ms = 150 }]
ms = 500
'''

# The same frame names, drawn in the other half of the canvas.
HAT = '''\
canvas = "unit"
over = "hero"

[frames]
a = """
..r.
....
....
"""
b = """
....
..r.
....
"""

'''


@pytest.fixture
def root(tmp_path, monkeypatch) -> Path:
    path = write_project(tmp_path / "sprites", CONFIG, PALETTE)
    monkeypatch.chdir(path)
    return path


def loaded(root: Path, files: dict[str, str]):
    """Write the sprite files and load them: the project, the sprites by id and every problem as a line."""
    for name, text in files.items():
        (root / name).write_text(text, encoding="utf-8")
    project, problems = load(root)
    sprites, more = load_all(project)
    problems += more + check.run(project, sprites)
    return project, {sprite.id: sprite for sprite in sprites}, sorted(format_problem(problem, root) for problem in problems)


def anims(sprite) -> dict[str, tuple]:
    return {anim.name: (anim.frames, anim.durations, anim.ms, anim.loop) for anim in sprite.anims}


# --- frame lengths ------------------------------------------------------------


def test_an_animation_without_durations_gives_every_frame_its_ms():
    assert Anim(name="idle", frames=("a", "b"), ms=400, loop=True).durations == (400, 400)


def test_an_entry_is_a_frame_name_or_a_table_with_its_own_length(root):
    _, sprites, found = loaded(root, {"hero.sprite.toml": HERO})
    assert found == []
    assert anims(sprites["hero"]) == {"idle": (("a", "b"), (500, 150), 500, True)}
    assert sprites["hero"].anims[0].line == 15


@pytest.mark.parametrize(
    "entry",
    ['{ frame = "b" }', '{ frame = "b", ms = 0 }', '{ frame = "b", ms = "150" }', '{ frame = "b", ms = 150, x = 1 }', "3"],
)
def test_a_malformed_entry_is_e001_naming_its_position(root, entry):
    _, sprites, found = loaded(root, {"hero.sprite.toml": HERO.replace('{ frame = "b", ms = 150 }', entry)})
    assert found[0] == (
        "hero.sprite.toml:16:1: E001 anim 'idle': frames entry 2 must be a frame name"
        ' or { frame = "...", ms = ... }'
    )
    assert sprites["hero"].anims == ()


def test_a_frame_named_in_a_table_entry_is_known_and_counts_as_used(root):
    _, _, found = loaded(root, {"hero.sprite.toml": HERO})
    assert not any("W002" in line for line in found)
    _, _, found = loaded(root, {"hero.sprite.toml": HERO.replace('frame = "b"', 'frame = "c"')})
    assert found == ["hero.sprite.toml:16:1: E105 anim 'idle': unknown frame 'c'"]


def test_a48_a56_a_build_writes_each_frames_length(root):
    loaded(root, {"hero.sprite.toml": HERO, "hat.sprite.toml": HAT + '[anim.idle]\nlike = "hero"\n'})
    assert main(["build"]) == 0

    exported = json.loads((root / "out" / "phaser" / "atlas.anims.json").read_text(encoding="utf-8"))["anims"]
    assert {anim["key"]: [frame["duration"] for frame in anim["frames"]] for anim in exported} == {
        "hat/idle": [500, 150],
        "hero/idle": [500, 150],
    }
    assert [frame["frame"] for frame in exported[0]["frames"]] == ["hat/a", "hat/b"]

    index = json.loads((root / "out" / "frames" / "sprites.json").read_text(encoding="utf-8"))
    idle = {"frames": [{"frame": "a", "ms": 500}, {"frame": "b", "ms": 150}], "loop": True}
    assert index["hero"]["anims"] == {"idle": idle}
    assert index["hat"]["anims"] == {"idle": idle}
    assert index["hat"]["over"] == "hero"
    assert "over" not in index["hero"]


def test_a56_the_demo_warrior_has_its_animation_in_the_frames_index(tmp_path):
    demo = tmp_path / "demo"
    shutil.copytree(DEMO, demo, ignore=shutil.ignore_patterns("out", ".preview"))
    assert main(["build", "--project", str(demo)]) == 0
    index = json.loads((demo / "out" / "frames" / "sprites.json").read_text(encoding="utf-8"))
    assert index["warrior"]["anims"]["idle"] == {
        "frames": [{"frame": "idle_0", "ms": 400}, {"frame": "idle_1", "ms": 400}],
        "loop": True,
    }
    assert index["goblin"]["anims"] == {}


# --- A52, A53: like -----------------------------------------------------------


@pytest.mark.parametrize("name", ["cap.sprite.toml", "zz/visor.sprite.toml"])
def test_a52_like_takes_the_animation_of_the_same_name_whatever_the_file_order(root, name):
    """`cap` sorts before `hero` and `visor` after it."""
    (root / "zz").mkdir()
    _, sprites, found = loaded(root, {"hero.sprite.toml": HERO, name: HAT + '[anim.idle]\nlike = "hero"\n'})
    assert found == []
    layer = sprites[Path(name).name.removesuffix(".sprite.toml")]
    assert anims(layer) == anims(sprites["hero"]) == {"idle": (("a", "b"), (500, 150), 500, True)}
    assert layer.anim_likes == ()


def test_a52_changing_the_source_changes_both(root):
    hero = HERO.replace("ms = 500", "ms = 300\nloop = false")
    _, sprites, _ = loaded(root, {"hero.sprite.toml": hero, "hat.sprite.toml": HAT + '[anim.idle]\nlike = "hero"\n'})
    assert anims(sprites["hat"]) == anims(sprites["hero"]) == {"idle": (("a", "b"), (300, 150), 300, False)}


def test_a_variant_has_the_resolved_animation_of_its_sprite(root):
    hat = HAT + '[anim.idle]\nlike = "hero"\n\n[variants.pale]\nswap = { r = "w" }\n'
    _, sprites, found = loaded(root, {"hero.sprite.toml": HERO, "hat.sprite.toml": hat})
    assert found == []
    assert anims(sprites["hat_pale"]) == anims(sprites["hero"])


def test_an_animation_written_out_stands_beside_one_taken_with_like(root):
    hat = HAT + '[anim.wave]\nframes = ["b"]\nms = 90\n\n[anim.idle]\nlike = "hero"\n'
    _, sprites, found = loaded(root, {"hero.sprite.toml": HERO, "hat.sprite.toml": hat})
    assert found == []
    assert sorted(anims(sprites["hat"])) == ["idle", "wave"]


def like_problems(root: Path, files: dict[str, str]) -> list[str]:
    files = {"hero.sprite.toml": HERO, **files}
    return [line for line in loaded(root, files)[2] if " E105 " in line or " E001 " in line]


def test_a53_like_naming_an_unknown_sprite_is_e105(root):
    assert like_problems(root, {"hat.sprite.toml": HAT + '[anim.idle]\nlike = "hreo"\n'}) == [
        "hat.sprite.toml:17:1: E105 anim 'idle': like names unknown sprite 'hreo'"
    ]


def test_a53_like_naming_a_sprite_without_that_animation_is_e105(root):
    assert like_problems(root, {"hat.sprite.toml": HAT + '[anim.walk]\nlike = "hero"\n'}) == [
        "hat.sprite.toml:17:1: E105 anim 'walk': 'hero' has no animation 'walk'"
    ]


def test_a53_like_naming_an_animation_that_is_itself_like_is_e105(root):
    files = {
        "hat.sprite.toml": HAT + '[anim.idle]\nlike = "hero"\n',
        "plume.sprite.toml": HAT.replace('over = "hero"\n', "") + '[anim.idle]\nlike = "hat"\n',
    }
    assert like_problems(root, files) == [
        "plume.sprite.toml:16:1: E105 anim 'idle': animation 'idle' of 'hat' is itself like;"
        " name the sprite that writes it out"
    ]


def test_a53_like_with_frames_this_sprite_lacks_is_e105(root):
    hat = HAT.replace('b = """', 'c = """') + '[anim.idle]\nlike = "hero"\n'
    assert like_problems(root, {"hat.sprite.toml": hat}) == [
        "hat.sprite.toml:17:1: E105 anim 'idle' like 'hero': this sprite has no frame 'b'"
    ]


def test_a53_like_beside_another_field_is_e001(root):
    assert like_problems(root, {"hat.sprite.toml": HAT + '[anim.idle]\nlike = "hero"\nms = 200\n'}) == [
        "hat.sprite.toml:17:1: E001 anim 'idle': like takes no other field"
    ]


def test_like_that_is_not_a_string_is_e001(root):
    assert like_problems(root, {"hat.sprite.toml": HAT + "[anim.idle]\nlike = 3\n"}) == [
        "hat.sprite.toml:17:1: E001 anim 'idle': like must be a sprite id"
    ]


def test_a_failed_like_is_left_out_and_reported_once_for_a_sprite_with_variants(root):
    hat = HAT + '[anim.idle]\nlike = "hreo"\n\n[variants.pale]\nswap = { r = "w" }\n'
    _, sprites, found = loaded(root, {"hero.sprite.toml": HERO, "hat.sprite.toml": hat})
    assert [line for line in found if "E105" in line] == [
        "hat.sprite.toml:17:1: E105 anim 'idle': like names unknown sprite 'hreo'"
    ]
    assert sprites["hat"].anims == sprites["hat_pale"].anims == ()


def test_checking_one_file_resolves_a_like_into_a_file_not_named(root, capsys):
    loaded(root, {"hero.sprite.toml": HERO, "hat.sprite.toml": HAT + '[anim.idle]\nlike = "hero"\n'})
    assert main(["check", "hat.sprite.toml"]) == 0
    assert capsys.readouterr().out == "ok: 1 sprite, 2 frames\n"


# --- A50: the strip and the GIF -----------------------------------------------


def test_the_strip_has_a_tile_for_each_entry_in_play_order_a_repeat_drawn_again(root):
    hero = HERO.replace('frames = ["a", { frame = "b", ms = 150 }]', 'frames = ["b", "b", "a"]')
    project, sprites, _ = loaded(root, {"hero.sprite.toml": hero})
    sprite = sprites["hero"]
    frames = preview.anim_frames(project, sprite, sprite.anims[0], None, 5)
    assert [(tile.size, ms) for tile, ms in frames] == [((20, 15), 500)] * 3

    strip = preview.anim_strip(project, sprite, sprite.anims[0], None, 5)
    # A tile is 20 wide; its label `500 ms` is 36.
    cell = len("500 ms") * CHAR_WIDTH
    assert strip.size == (2 * MARGIN + 3 * cell + 2 * GAP, 2 * MARGIN + 15 + LABEL_GAP + 2 * LINE_HEIGHT)
    left = MARGIN + (cell - 20) // 2
    # `b` is white in its lower rows, `a` black in its upper ones.
    assert [strip.getpixel((left + index * (cell + GAP) + 2, MARGIN + 12)) for index in range(3)] == [WHITE, WHITE, BACKGROUND]
    assert strip.getpixel((left + 2 * (cell + GAP) + 2, MARGIN + 2)) == BLACK


def test_the_strip_labels_each_tile_with_its_name_and_length(root):
    project, sprites, _ = loaded(root, {"hero.sprite.toml": HERO})
    sprite = sprites["hero"]
    strip = preview.anim_strip(project, sprite, sprite.anims[0], None, 5)
    labels = strip.crop((0, MARGIN + 15 + LABEL_GAP, strip.width, strip.height - MARGIN))
    assert len(labels.getcolors()) > 1
    assert labels.height == 2 * LINE_HEIGHT


def test_a_layers_strip_draws_each_entry_over_the_base_frame_of_the_same_name(root):
    project, sprites, found = loaded(
        root, {"hero.sprite.toml": HERO, "hat.sprite.toml": HAT + '[anim.idle]\nlike = "hero"\n'}
    )
    assert found == []
    hat = sprites["hat"]
    first, second = (tile for tile, _ in preview.anim_frames(project, hat, hat.anims[0], sprites["hero"], 5))
    assert (first.getpixel((2, 2)), first.getpixel((12, 2))) == (BLACK, RED)
    assert (second.getpixel((2, 7)), second.getpixel((12, 7)), second.getpixel((2, 2))) == (WHITE, RED, BACKGROUND)


def test_gif_lengths_are_rounded_to_a_hundredth_and_floored():
    assert [preview.gif_ms(ms) for ms in (1, 15, 20, 154, 155, 400)] == [20, 20, 20, 150, 160, 400]


def gif(path: Path) -> tuple[list[int], object]:
    """The length of each frame of a GIF, and its loop count (None: plays once)."""
    with Image.open(path) as opened:
        lengths = []
        for index in range(getattr(opened, "n_frames", 1)):
            opened.seek(index)
            lengths.append(opened.info.get("duration"))
        return lengths, opened.info.get("loop")


def test_a50_preview_anim_prints_two_paths_and_writes_the_strip_and_the_gif(root, capsys):
    loaded(root, {"hero.sprite.toml": HERO})
    assert main(["preview", "hero", "--anim", "idle"]) == 0
    captured = capsys.readouterr()
    assert captured.out == ".preview/hero.anim-idle.png\n.preview/hero.anim-idle.gif\n"
    assert captured.err == ""

    with Image.open(root / ".preview" / "hero.anim-idle.png") as strip:
        cell = len("500 ms") * CHAR_WIDTH
        assert strip.size == (2 * MARGIN + 2 * cell + GAP, 2 * MARGIN + 15 + LABEL_GAP + 2 * LINE_HEIGHT)
    assert gif(root / ".preview" / "hero.anim-idle.gif") == ([500, 150], 0)
    with Image.open(root / ".preview" / "hero.anim-idle.gif") as opened:
        assert opened.size == (20, 15)
        assert opened.convert("RGBA").getpixel((2, 2)) == BLACK


def test_a50_the_demo_warriors_idle(tmp_path, monkeypatch, capsys):
    demo = tmp_path / "demo"
    shutil.copytree(DEMO, demo, ignore=shutil.ignore_patterns("out", ".preview"))
    monkeypatch.chdir(demo)
    assert main(["preview", "warrior", "--anim", "idle"]) == 0
    assert capsys.readouterr().out == ".preview/warrior.anim-idle.png\n.preview/warrior.anim-idle.gif\n"
    with Image.open(demo / ".preview" / "warrior.anim-idle.png") as strip:
        assert strip.size == (2 * MARGIN + 2 * 32 * 6 + GAP, 2 * MARGIN + 32 * 6 + LABEL_GAP + 2 * LINE_HEIGHT)
    assert gif(demo / ".preview" / "warrior.anim-idle.gif") == ([400, 400], 0)


def test_an_animation_that_does_not_loop_plays_once_and_scale_applies_to_both(root, capsys):
    loaded(root, {"hero.sprite.toml": HERO + "loop = false\n"})
    assert main(["preview", "hero", "--anim", "idle", "--scale", "display"]) == 0
    capsys.readouterr()
    path = root / ".preview" / "hero.anim-idle.gif"
    assert gif(path) == ([500, 150], None)
    with Image.open(path) as opened:
        assert opened.size == (8, 6)
    with Image.open(root / ".preview" / "hero.anim-idle.png") as strip:
        assert strip.height == 2 * MARGIN + 6 + LABEL_GAP + 2 * LINE_HEIGHT


def test_several_ids_give_one_strip_and_a_gif_each(root, capsys):
    loaded(root, {"hero.sprite.toml": HERO, "hat.sprite.toml": HAT + '[anim.idle]\nlike = "hero"\n'})
    assert main(["preview", "hero", "hat", "--anim", "idle"]) == 0
    assert capsys.readouterr().out.splitlines() == [
        ".preview/hero+hat.anim-idle.png",
        ".preview/hero.anim-idle.gif",
        ".preview/hat.anim-idle.gif",
    ]
    with Image.open(root / ".preview" / "hero+hat.anim-idle.png") as strip:
        assert strip.height == 2 * (2 * MARGIN + 15 + LABEL_GAP + 2 * LINE_HEIGHT)
    # The layer's GIF is drawn over the body.
    with Image.open(root / ".preview" / "hat.anim-idle.gif") as opened:
        assert opened.convert("RGBA").getpixel((2, 2)) == BLACK


# --- A51: usage errors --------------------------------------------------------


@pytest.mark.parametrize(
    "arguments, message",
    [
        (["hero", "--anim", "blink"], "error: sprite 'hero' has no animation 'blink' (animations: idle)\n"),
        (["hat", "--anim", "idle"], "error: sprite 'hat' has no animation 'idle' (animations: none)\n"),
        (["hero", "--anim", "idle", "--grid"], "error: --anim cannot be used with --grid\n"),
        (["hero", "--anim", "idle", "--on", "hero"], "error: --anim cannot be used with --on\n"),
        (["hero", "--anim", "idle", "--sheet"], "error: --anim cannot be used with --sheet\n"),
        (["--anim", "idle"], "error: --anim needs a sprite id\n"),
    ],
)
def test_a51_anim_usage_errors_exit_2(root, capsys, arguments, message):
    loaded(root, {"hero.sprite.toml": HERO, "hat.sprite.toml": HAT})
    assert main(["preview", *arguments]) == 2
    captured = capsys.readouterr()
    assert (captured.out, captured.err) == ("", message)
    assert not (root / ".preview").exists()
