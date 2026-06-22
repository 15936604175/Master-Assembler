import pytest
from app.engine.rotation import get_all_rotations, get_allowed_orientations, get_orientation_for_rotation


def test_get_all_rotations_returns_six():
    result = get_all_rotations(100, 80, 50)
    assert len(result) == 6


def test_get_all_rotations_contents():
    result = get_all_rotations(100, 80, 50)
    expected = [
        (100, 80, 50), (100, 50, 80),
        (80, 100, 50), (80, 50, 100),
        (50, 100, 80), (50, 80, 100),
    ]
    for r in expected:
        assert r in result


def test_get_all_rotations_cube():
    result = get_all_rotations(50, 50, 50)
    assert len(result) == 6
    for r in result:
        assert r == (50, 50, 50)


def test_allowed_orientations_no_constraint():
    """无约束时返回 3 个朝向。"""
    result = get_allowed_orientations(100, 80, 50, [])
    assert len(result) == 3
    orient_names = [o[2] for o in result]
    assert "height_vertical" in orient_names
    assert "width_vertical" in orient_names
    assert "length_vertical" in orient_names


def test_allowed_orientations_forbid_height():
    """禁止 height 垂直 → 只允许 width_vertical 和 length_vertical。"""
    result = get_allowed_orientations(100, 80, 50, ["height"])
    assert len(result) == 2
    orient_names = [o[2] for o in result]
    assert "height_vertical" not in orient_names
    assert "width_vertical" in orient_names
    assert "length_vertical" in orient_names


def test_allowed_orientations_forbid_width():
    """禁止 width 垂直 → 只允许 height_vertical 和 length_vertical。"""
    result = get_allowed_orientations(100, 80, 50, ["width"])
    assert len(result) == 2
    orient_names = [o[2] for o in result]
    assert "height_vertical" in orient_names
    assert "width_vertical" not in orient_names
    assert "length_vertical" in orient_names


def test_allowed_orientations_forbid_length():
    """禁止 length 垂直 → 只允许 height_vertical 和 width_vertical。"""
    result = get_allowed_orientations(100, 80, 50, ["length"])
    assert len(result) == 2
    orient_names = [o[2] for o in result]
    assert "height_vertical" in orient_names
    assert "width_vertical" in orient_names
    assert "length_vertical" not in orient_names


def test_allowed_orientations_multiple_forbidden():
    """禁止 height 和 width 垂直 → 只允许 length_vertical。"""
    result = get_allowed_orientations(100, 80, 50, ["height", "width"])
    assert len(result) == 1
    assert result[0][2] == "length_vertical"


def test_allowed_orientations_all_forbidden_returns_empty():
    """禁止全部维度垂直 → 无合法朝向。"""
    result = get_allowed_orientations(100, 80, 50, ["height", "width", "length"])
    assert len(result) == 0


def test_orientation_for_rotation_height_vertical():
    orient = get_orientation_for_rotation(100, 80, 50, 100, 80, 50)
    assert orient == "height_vertical"


def test_orientation_for_rotation_width_vertical():
    orient = get_orientation_for_rotation(100, 80, 50, 100, 50, 80)
    assert orient == "width_vertical"


def test_orientation_for_rotation_length_vertical():
    # With (200, 80, 50), rot_h=200 equals original length → length_vertical
    orient = get_orientation_for_rotation(200, 80, 50, 50, 200, 80)
    assert orient == "width_vertical"
    # When rot_h matches length
    orient2 = get_orientation_for_rotation(200, 80, 50, 80, 50, 200)
    assert orient2 == "length_vertical"