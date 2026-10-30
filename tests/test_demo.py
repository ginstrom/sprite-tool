from pathlib import Path

from sprite_tool import spritefile
from sprite_tool.cli import main
from sprite_tool.project import load

DEMO = Path(__file__).parent.parent / "examples" / "demo"


def test_demo_project_checks_clean(capsys):
    assert main(["check", "--project", str(DEMO)]) == 0
    captured = capsys.readouterr()
    assert captured.out == "ok: 8 sprites, 13 frames\n"
    assert captured.err == ""


def test_demo_project_has_the_sprites_later_steps_rely_on():
    project, problems = load(DEMO)
    assert problems == []
    assert [(target.type, target.out, target.name, target.res_path) for target in project.exports] == [
        ("frames", DEMO / "out" / "frames", "sprites", None),
        ("phaser", DEMO / "out" / "phaser", "atlas", None),
        ("godot", DEMO / "out" / "godot", "atlas", "res://sprites"),
    ]
    assert len(project.palette) == 16
    sprites, problems = spritefile.load_all(project)
    assert problems == []
    by_id = {sprite.id: sprite for sprite in sprites}
    assert sorted(by_id) == [
        "arrow", "goblin", "ground_light", "sample_slime", "slime", "spark", "warrior", "warrior_red"
    ]

    warrior = by_id["warrior"]
    assert (warrior.canvas.name, warrior.canvas.width, warrior.canvas.height) == ("unit", 32, 32)
    assert [(frame.name, frame.literal) for frame in warrior.frames] == [("idle_0", True), ("idle_1", False)]
    assert [(anim.name, anim.frames, anim.ms) for anim in warrior.anims] == [("idle", ("idle_0", "idle_1"), 400)]
    assert warrior.frames[0].rows != warrior.frames[1].rows

    red = by_id["warrior_red"]
    assert red.variant_of == "warrior"
    assert red.frames[0].rows != warrior.frames[0].rows

    slime, sample = by_id["slime"], by_id["sample_slime"]
    assert (slime.auto_outline, slime.build, slime.frames[0].literal) == (True, True, False)
    assert (sample.auto_outline, sample.build, sample.frames[0].literal) == (False, False, True)
    assert sample.frames[0].rows == slime.frames[0].rows

    assert (by_id["goblin"].canvas.name, len(by_id["goblin"].frames), by_id["goblin"].anims) == ("unit", 1, ())
    assert (by_id["ground_light"].canvas.name, by_id["ground_light"].canvas.width) == ("tile", 16)

    assert [frame.points for frame in warrior.frames] == [(("grip", (25, 18)),)] * 2
    assert [frame.points for frame in red.frames] == [(("grip", (25, 18)),)] * 2


def test_a68_the_demo_has_an_arrow_and_a_spark_on_the_effect_class():
    project, _ = load(DEMO)
    effect = project.canvases["effect"]
    assert (effect.width, effect.height, effect.anchor, effect.outline, effect.grounded) == (16, 16, (8, 8), None, False)
    sprites, _ = spritefile.load_all(project)
    by_id = {sprite.id: sprite for sprite in sprites}

    arrow = by_id["arrow"]
    (frame,) = arrow.frames
    assert arrow.canvas.name == "effect"
    # The tip is the rightmost drawn pixel, on the anchor's row: the arrow points right.
    tip_col, tip_row = dict(frame.points)["tip"]
    assert frame.rows[tip_row][tip_col] != "."
    assert max(len(row.rstrip(".")) for row in frame.rows) == tip_col + 1
    assert tip_row == effect.anchor[1]

    spark = by_id["spark"]
    (burst,) = spark.anims
    assert (spark.canvas.name, burst.name, burst.loop) == ("effect", "burst", False)
    assert burst.durations[-1] < burst.durations[0]


def test_demo_gitignore_covers_previews_and_build_output():
    assert (DEMO / ".gitignore").read_text(encoding="utf-8").split() == [".preview/", "out/"]
