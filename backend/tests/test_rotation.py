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
    result = get_allowed_orientations(100, 80, 50, [])
    assert len(result) == 3


def test_allowed_orientations_forbid_height():
    result = get_allowed_orientations(100, 80, 50, ["height"])
    assert len(result) == 1
    assert result[0][2] == "height_vertical"


def test_allowed_orientations_forbid_width():
    result = get_allowed_orientations(100, 80, 50, ["width"])
    assert len(result) == 1
    assert result[0][2] == "width_vertical"


def test_allowed_orientations_forbid_length():
    result = get_allowed_orientations(100, 80, 50, ["length"])
    assert len(result) == 1
    assert result[0][2] == "length_vertical"


def test_allowed_orientations_multiple_forbidden():
    result = get_allowed_orientations(100, 80, 50, ["height", "width"])
    assert len(result) == 0


def test_allowed_orientations_all_forbidden_returns_empty():
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

