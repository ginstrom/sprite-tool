from pathlib import Path

from sprite_tool import spritefile
from sprite_tool.cli import main
from sprite_tool.project import load

DEMO = Path(__file__).parent.parent / "examples" / "demo"


def test_demo_project_checks_clean(capsys):
    assert main(["check", "--project", str(DEMO)]) == 0
    captured = capsys.readouterr()
    assert captured.out == "ok: 4 sprites, 6 frames\n"
    assert captured.err == ""


def test_demo_project_has_the_sprites_later_steps_rely_on():
    project, problems = load(DEMO)
    assert problems == []
    assert [(target.type, target.out, target.name, target.res_path) for target in project.exports] == [
        ("frames", DEMO / "out" / "frames", None, None),
        ("phaser", DEMO / "out" / "phaser", "atlas", None),
        ("godot", DEMO / "out" / "godot", "atlas", "res://sprites"),
    ]
    assert len(project.palette) == 16
    sprites, problems = spritefile.load_all(project)
    assert problems == []
    by_id = {sprite.id: sprite for sprite in sprites}
    assert sorted(by_id) == ["goblin", "ground_light", "warrior", "warrior_red"]

    warrior = by_id["warrior"]
    assert (warrior.canvas.name, warrior.canvas.width, warrior.canvas.height) == ("unit", 32, 32)
    assert [(frame.name, frame.literal) for frame in warrior.frames] == [("idle_0", True), ("idle_1", False)]
    assert [(anim.name, anim.frames, anim.ms) for anim in warrior.anims] == [("idle", ("idle_0", "idle_1"), 400)]
    assert warrior.frames[0].rows != warrior.frames[1].rows

    red = by_id["warrior_red"]
    assert red.variant_of == "warrior"
    assert red.frames[0].rows != warrior.frames[0].rows

    assert (by_id["goblin"].canvas.name, len(by_id["goblin"].frames), by_id["goblin"].anims) == ("unit", 1, ())
    assert (by_id["ground_light"].canvas.name, by_id["ground_light"].canvas.width) == ("tile", 16)


def test_demo_gitignore_covers_previews_and_build_output():
    assert (DEMO / ".gitignore").read_text(encoding="utf-8").split() == [".preview/", "out/"]
