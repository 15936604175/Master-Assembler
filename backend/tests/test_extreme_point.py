import pytest
from app.engine.extreme_point import (
    generate_new_eps, is_valid_ep, evaluate_placement,
    check_overlap, check_support, check_cg_stability,
    check_fragile_safety, SUPPORT_THRESHOLD,
)


def test_generate_new_eps():
    eps = generate_new_eps(10, 10, 10, 100, 50, 60)
    assert len(eps) == 3
    assert (110, 10, 10) in eps
    assert (10, 60, 10) in eps
    assert (10, 10, 70) in eps


def test_is_valid_ep_within_container():
    ep = (50, 50, 50)
    item_size = (30, 20, 40)
    container = (200, 200, 200)
    assert is_valid_ep(ep, item_size, container) is True


def test_is_valid_ep_outside_container():
    ep = (190, 190, 190)
    item_size = (30, 20, 40)
    container = (200, 200, 200)
    assert is_valid_ep(ep, item_size, container) is False


def test_is_valid_ep_exact_fit():
    ep = (170, 180, 160)
    item_size = (30, 20, 40)
    container = (200, 200, 200)
    assert is_valid_ep(ep, item_size, container) is True


def test_evaluate_placement_lower_better():
    placements = [
        ((0, 0, 0), (10, 10, 10)),
        ((0, 50, 0), (10, 10, 10)),
    ]
    results = [
        evaluate_placement(p[0], p[1], (100, 100, 100), [])
        for p in placements
    ]
    scores = [r[0] for r in results]
    assert scores[0] > scores[1]


def test_evaluate_placement_returns_metrics():
    score, metrics = evaluate_placement(
        (0, 0, 0), (10, 10, 10), (100, 100, 100), []
    )
    assert isinstance(score, float)
    assert score > 0
    assert "proximity" in metrics
    assert "support_ratio" in metrics
    assert "cg_score" in metrics
    assert "is_supported" in metrics
    assert "is_cg_ok" in metrics


def test_check_overlap_no_overlap():
    placements = [{"x": 0, "y": 0, "z": 0, "l": 50, "h": 50, "w": 50}]
    assert check_overlap(60, 60, 60, 20, 20, 20, placements) is False


def test_check_overlap_has_overlap():
    placements = [{"x": 0, "y": 0, "z": 0, "l": 50, "h": 50, "w": 50}]
    assert check_overlap(40, 40, 40, 20, 20, 20, placements) is True


def test_check_overlap_touching_not_overlap():
    placements = [{"x": 0, "y": 0, "z": 0, "l": 50, "h": 50, "w": 50}]
    assert check_overlap(50, 0, 0, 20, 20, 20, placements) is False


def test_check_support_on_floor():
    ratio, is_supported = check_support(0, 0, 0, 50, 30, 50, [])
    assert is_supported is True
    assert abs(ratio - 1.0) < 0.01


def test_check_support_on_existing_item():
    placements = [{"x": 0, "y": 0, "z": 0, "l": 100, "h": 20, "w": 100}]
    ratio, is_supported = check_support(0, 20, 0, 50, 30, 50, placements)
    assert is_supported is True
    assert ratio > SUPPORT_THRESHOLD


def test_check_support_partial_not_enough():
    placements = [{"x": 0, "y": 0, "z": 0, "l": 30, "h": 20, "w": 100}]
    ratio, is_supported = check_support(20, 20, 0, 50, 30, 50, placements)
    if ratio < SUPPORT_THRESHOLD:
        assert is_supported is False


def test_check_cg_stability_single_item():
    score, is_ok = check_cg_stability(
        0, 0, 0, 50, 30, 50, 10, [], (100, 100, 100)
    )
    assert is_ok is True
    assert 0 < score <= 1.0


def test_check_fragile_safety_no_fragile():
    placements = [{"x": 0, "y": 0, "z": 0, "l": 50, "h": 30, "w": 50,
                   "weight": 10, "is_fragile": False}]
    score, is_ok = check_fragile_safety(20, 30, 0, 50, 30, 50, 10, placements)
    assert is_ok is True
    assert abs(score - 1.0) < 0.01


def test_check_fragile_safety_heavy_on_fragile():
    placements = [{"x": 0, "y": 0, "z": 0, "l": 100, "h": 20, "w": 100,
                   "weight": 5, "is_fragile": True}]
    score, is_ok = check_fragile_safety(0, 20, 0, 100, 30, 100, 50, placements)
    assert is_ok is False
    assert score < 1.0


def test_support_threshold_value():
    assert SUPPORT_THRESHOLD == 0.6
