from dataclasses import replace

from conftest import make_frame, make_sprite
from sprite_tool.export.index import bounds, sprite_entry, union
from sprite_tool.model import Canvas

# --- bounds -----------------------------------------------------------------


def test_bounds_is_the_smallest_box_round_every_drawn_pixel():
    assert bounds(("....", ".kw.", ".k..", "....")) == [1, 1, 2, 2]


def test_bounds_of_a_full_grid_is_the_grid():
    assert bounds(("kw", "wk", "kk")) == [0, 0, 2, 3]


def test_bounds_of_one_pixel_is_one_by_one():
    assert bounds(("...", "...", "..k")) == [2, 2, 1, 1]


def test_bounds_spans_separate_shapes():
    assert bounds(("k....", ".....", "....w")) == [0, 0, 5, 3]


def test_bounds_of_a_grid_with_nothing_drawn_is_all_zero():
    assert bounds(("...", "...")) == [0, 0, 0, 0]
    assert bounds(()) == [0, 0, 0, 0]


# --- union ------------------------------------------------------------------


def test_union_covers_every_box():
    assert union([[1, 2, 3, 4], [0, 5, 2, 6]]) == [0, 2, 4, 9]


def test_union_of_one_box_is_that_box():
    assert union([[4, 3, 26, 29]]) == [4, 3, 26, 29]


def test_union_skips_empty_boxes():
    assert union([[0, 0, 0, 0], [5, 6, 2, 2]]) == [5, 6, 2, 2]


def test_union_of_nothing_is_all_zero():
    assert union([]) == [0, 0, 0, 0]
    assert union([[0, 0, 0, 0]]) == [0, 0, 0, 0]


# --- sprite_entry -----------------------------------------------------------


def test_sprite_entry_has_the_canvas_facts_and_the_box_of_every_frame():
    hero = make_sprite("hero", make_frame("a", "....", ".k..", "...."), make_frame("b", "....", "....", "..w."))
    canvas = Canvas(
        name="unit", width=4, height=3, anchor=(2, 3), display_scale=3, outline=None, grounded=False
    )
    assert sprite_entry(replace(hero, canvas=canvas)) == {
        "anchor": [2, 3],
        "anims": {},
        "bounds": [1, 1, 2, 2],
        "canvas": "unit",
        "display_scale": 3,
        "size": [4, 3],
    }


def test_sprite_entry_has_the_animations_sorted_by_name_with_each_frames_length():
    from sprite_tool.model import Anim

    hero = make_sprite("hero", make_frame("a", "k"), make_frame("b", "w"))
    walk = Anim(name="walk", frames=("a", "b"), ms=100, loop=True)
    idle = Anim(name="idle", frames=("a", "a", "b"), ms=1000, loop=False, durations=(1000, 1000, 150))
    entry = sprite_entry(replace(hero, anims=(walk, idle)))
    assert list(entry["anims"]) == ["idle", "walk"]
    assert entry["anims"]["idle"] == {
        "frames": [{"frame": "a", "ms": 1000}, {"frame": "a", "ms": 1000}, {"frame": "b", "ms": 150}],
        "loop": False,
    }
    assert entry["anims"]["walk"]["frames"] == [{"frame": "a", "ms": 100}, {"frame": "b", "ms": 100}]


def test_sprite_entry_of_a_layer_says_what_it_is_over():
    hat = make_sprite("hat", make_frame("a", "k"))
    assert "over" not in sprite_entry(hat)
    assert sprite_entry(replace(hat, over="hero"))["over"] == "hero"
