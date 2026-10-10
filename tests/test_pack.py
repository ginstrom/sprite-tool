import random

import pytest

from sprite_tool.model import Placement
from sprite_tool.pack import pack

SEEDS = range(40)
SIZES = [(32, 32), (16, 16), (16, 32), (48, 24), (8, 8), (100, 20)]


def generated_sprites(seed):
    """Up to 12 sprites, each a list of items in frame order. All frames of a
    sprite share one size, as they share one canvas."""
    rng = random.Random(seed)
    sprites = []
    for n in range(rng.randint(1, 12)):
        w, h = rng.choice(SIZES)
        sprites.append([(f"s{n:02}", f"f{i}", w, h) for i in range(rng.randint(1, 6))])
    return sprites


def flatten(sprites):
    return [item for sprite in sprites for item in sprite]


def generated(seed):
    rng = random.Random(seed)
    return flatten(generated_sprites(seed)), rng.choice([0, 1, 2, 4])


def is_power_of_two(n):
    return n > 0 and n & (n - 1) == 0


def test_worked_example():
    items = [("hero", "idle_0", 32, 32), ("hero", "idle_1", 32, 32)]

    assert pack(items, padding=1) == (
        128,
        34,
        [
            Placement(sprite_id="hero", frame="idle_0", x=1, y=1, w=32, h=32),
            Placement(sprite_id="hero", frame="idle_1", x=34, y=1, w=32, h=32),
        ],
    )


def test_padding_defaults_to_one():
    items = [("hero", "idle_0", 32, 32), ("hero", "idle_1", 32, 32)]

    assert pack(items) == pack(items, padding=1)


def test_a_new_shelf_starts_when_the_next_frame_would_pass_the_sheet_width():
    items = [("hero", f"f{i}", 32, 32) for i in range(4)]

    width, height, placements = pack(items, padding=1)

    # Three fit on a 128-wide sheet (1 + 3 * 33 = 100); a fourth would end at 133.
    assert (width, height) == (128, 67)
    assert [(p.x, p.y) for p in placements] == [(1, 1), (34, 1), (67, 1), (1, 34)]


def test_taller_frames_are_placed_first():
    items = [
        ("grass", "idle_0", 16, 16),
        ("hero", "idle_0", 32, 32),
        ("water", "idle_0", 16, 16),
        ("zed", "idle_0", 32, 32),
    ]

    width, height, placements = pack(items, padding=1)

    assert [p.sprite_id for p in placements] == ["hero", "zed", "grass", "water"]
    assert (width, height) == (128, 34)
    assert [(p.x, p.y, p.w, p.h) for p in placements] == [
        (1, 1, 32, 32),
        (34, 1, 32, 32),
        (67, 1, 16, 16),
        (84, 1, 16, 16),
    ]


def test_sprites_of_one_height_are_ordered_by_id_and_frames_keep_their_order():
    items = [
        ("zed", "walk_1", 16, 16),
        ("zed", "walk_0", 16, 16),
        ("amy", "b", 16, 16),
        ("amy", "a", 16, 16),
    ]

    _, _, placements = pack(items)

    assert [(p.sprite_id, p.frame) for p in placements] == [
        ("amy", "b"),
        ("amy", "a"),
        ("zed", "walk_1"),
        ("zed", "walk_0"),
    ]


def test_padding_zero_packs_edge_to_edge():
    items = [("hero", f"f{i}", 32, 32) for i in range(4)]

    assert pack(items, padding=0) == (
        64,
        64,
        [
            Placement("hero", "f0", 0, 0, 32, 32),
            Placement("hero", "f1", 32, 0, 32, 32),
            Placement("hero", "f2", 0, 32, 32, 32),
            Placement("hero", "f3", 32, 32, 32, 32),
        ],
    )


def test_the_sheet_widens_until_it_is_no_taller_than_wide():
    items = [("hero", f"f{i}", 32, 32) for i in range(5)]

    # At 64 wide, padding 0, five frames need three shelves: 96 high.
    width, height, _ = pack(items, padding=0)

    assert (width, height) == (128, 64)


def test_a_frame_wider_than_64_widens_the_sheet():
    width, height, placements = pack([("boss", "idle_0", 100, 20)], padding=1)

    assert (width, height) == (128, 22)
    assert placements == [Placement("boss", "idle_0", 1, 1, 100, 20)]


@pytest.mark.parametrize("padding", [0, 1, 3])
def test_empty_input_gives_a_minimal_sheet(padding):
    # At least one pixel high so that the sheet is always a valid image.
    assert pack([], padding=padding) == (64, max(1, 2 * padding), [])


def test_negative_padding_is_refused():
    with pytest.raises(ValueError):
        pack([("hero", "idle_0", 32, 32)], padding=-1)


@pytest.mark.parametrize("seed", SEEDS)
def test_every_item_is_placed_once_at_its_own_size(seed):
    items, padding = generated(seed)

    _, _, placements = pack(items, padding)

    assert sorted((p.sprite_id, p.frame, p.w, p.h) for p in placements) == sorted(items)


@pytest.mark.parametrize("seed", SEEDS)
def test_sheet_width_is_a_power_of_two_and_height_is_no_greater(seed):
    items, padding = generated(seed)

    width, height, _ = pack(items, padding)

    assert is_power_of_two(width)
    assert width >= 64
    assert 0 < height <= width


@pytest.mark.parametrize("seed", SEEDS)
def test_sheet_width_is_the_smallest_that_qualifies(seed):
    items, padding = generated(seed)

    width, _, _ = pack(items, padding)

    if width > 64:
        # Half the width must fail: a frame does not fit, or the sheet is too tall.
        half = width // 2
        too_wide = any(w + 2 * padding > half for _, _, w, _ in items)
        assert too_wide or shelf_height(items, padding, half) > half


def shelf_height(items, padding, width):
    """Independent restatement of the packing rules, for the height only."""
    ordered = sorted(items, key=lambda item: (-item[3], item[0]))
    x = y = padding
    shelf = 0
    for _, _, w, h in ordered:
        if x + w + padding > width:
            x, y, shelf = padding, y + shelf + padding, 0
        shelf = max(shelf, h)
        x += w + padding
    return y + shelf + padding


@pytest.mark.parametrize("seed", SEEDS)
def test_everything_is_inside_the_sheet_and_padded_from_its_edge(seed):
    items, padding = generated(seed)

    width, height, placements = pack(items, padding)

    for p in placements:
        assert p.x >= padding and p.y >= padding
        assert p.x + p.w + padding <= width
        assert p.y + p.h + padding <= height


@pytest.mark.parametrize("seed", SEEDS)
def test_placements_are_at_least_padding_apart(seed):
    items, padding = generated(seed)

    _, _, placements = pack(items, padding)

    # Growing each rectangle by `padding` on its right and bottom and finding
    # no overlap means every pair is at least `padding` apart on one axis.
    for i, a in enumerate(placements):
        for b in placements[i + 1 :]:
            apart = (
                a.x + a.w + padding <= b.x
                or b.x + b.w + padding <= a.x
                or a.y + a.h + padding <= b.y
                or b.y + b.h + padding <= a.y
            )
            assert apart, (a, b)


@pytest.mark.parametrize("seed", SEEDS)
def test_the_order_of_sprites_in_the_input_does_not_matter(seed):
    sprites = generated_sprites(seed)
    shuffled = list(sprites)
    random.Random(seed + 1000).shuffle(shuffled)

    assert pack(flatten(shuffled)) == pack(flatten(sprites))
