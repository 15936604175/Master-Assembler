import pytest
from app.engine.space_cutter import (
    Space, cut_space, remove_degenerate_spaces
)


def test_cut_space_along_x():
    original = Space(0, 0, 0, 100, 100, 100)
    item_box = (0, 0, 0, 40, 30, 20)
    result = cut_space(original, item_box)
    assert len(result) == 3
    assert any(s.x == 40 and s.y == 0 and s.z == 0 and abs(s.l - 60) < 0.01 for s in result)
    assert any(s.x == 0 and s.y == 30 and s.z == 0 and abs(s.h - 70) < 0.01 for s in result)
    assert any(s.x == 0 and s.y == 0 and s.z == 20 and abs(s.w - 80) < 0.01 for s in result)


def test_cut_space_no_intersection():
    original = Space(0, 0, 0, 100, 100, 100)
    item_box = (200, 200, 200, 10, 10, 10)
    result = cut_space(original, item_box)
    assert len(result) == 1
    assert result[0] == original


def test_cut_space_item_contained():
    """Item inside but not at origin - should still produce 3 spaces"""
    original = Space(0, 0, 0, 200, 200, 200)
    item_box = (50, 50, 50, 100, 100, 100)
    result = cut_space(original, item_box)
    assert len(result) >= 1


def test_remove_degenerate_spaces():
    spaces = [
        Space(0, 0, 0, 100, 1, 100),
        Space(0, 0, 0, 100, 100, 100),
    ]
    result = remove_degenerate_spaces(spaces, min_size=5)
    assert len(result) == 1
    assert result[0].h == 100


def test_remove_all_degenerate():
    spaces = [
        Space(0, 0, 0, 3, 3, 3),
        Space(0, 0, 0, 2, 2, 2),
    ]
    result = remove_degenerate_spaces(spaces, min_size=5)
    assert len(result) == 0
