import pytest
from app.engine.feasibility import FeasibilityVerifier
from app.models.container import ContainerConfig
from app.models.item import ItemInput


@pytest.fixture
def container():
    return ContainerConfig(length=200, width=200, height=200, max_weight=5000)


@pytest.fixture
def items():
    return [
        ItemInput(id="A", length=50, width=50, height=50, weight=10, quantity=3),
        ItemInput(id="B", length=30, width=30, height=30, weight=5, quantity=2),
    ]


def test_verifier_empty_placements(container, items):
    verifier = FeasibilityVerifier(container, items)
    report = verifier.verify([])
    assert report.is_feasible is True
    assert report.geometry_ok is True
    assert report.physics_ok is True


def test_verifier_valid_placements(container, items):
    verifier = FeasibilityVerifier(container, items)
    placements = [
        {"item_id": "A", "x": 0, "y": 0, "z": 0, "l": 50, "h": 50, "w": 50, "weight": 10},
        {"item_id": "A", "x": 50, "y": 0, "z": 0, "l": 50, "h": 50, "w": 50, "weight": 10},
        {"item_id": "A", "x": 0, "y": 50, "z": 0, "l": 50, "h": 50, "w": 50, "weight": 10},
        {"item_id": "B", "x": 50, "y": 50, "z": 0, "l": 30, "h": 30, "w": 30, "weight": 5},
    ]
    report = verifier.verify(placements)
    assert report.geometry_ok is True
    assert report.physics_ok is True
    assert report.is_feasible is True


def test_verifier_overlap_detection(container, items):
    verifier = FeasibilityVerifier(container, items)
    placements = [
        {"item_id": "A", "x": 0, "y": 0, "z": 0, "l": 50, "h": 50, "w": 50, "weight": 10},
        {"item_id": "A", "x": 30, "y": 0, "z": 0, "l": 50, "h": 50, "w": 50, "weight": 10},
    ]
    report = verifier.verify(placements)
    assert report.geometry_ok is False


def test_verifier_out_of_bounds(container, items):
    verifier = FeasibilityVerifier(container, items)
    placements = [
        {"item_id": "A", "x": 160, "y": 0, "z": 0, "l": 50, "h": 50, "w": 50, "weight": 10},
    ]
    report = verifier.verify(placements)
    assert report.geometry_ok is False


def test_verifier_weight_exceeded(container, items):
    heavy_container = ContainerConfig(length=100, width=100, height=100, max_weight=15)
    verifier = FeasibilityVerifier(heavy_container, items)
    placements = [
        {"item_id": "A", "x": 0, "y": 0, "z": 0, "l": 50, "h": 50, "w": 50, "weight": 10},
        {"item_id": "A", "x": 50, "y": 0, "z": 0, "l": 50, "h": 50, "w": 50, "weight": 10},
    ]
    report = verifier.verify(placements)
    assert report.physics_ok is False


def test_verifier_support_check(container, items):
    verifier = FeasibilityVerifier(container, items)
    placements = [
        {"item_id": "A", "x": 0, "y": 0, "z": 0, "l": 50, "h": 50, "w": 50, "weight": 10},
        {"item_id": "B", "x": 10, "y": 50, "z": 10, "l": 30, "h": 30, "w": 30, "weight": 5},
    ]
    report = verifier.verify(placements)
    assert report.support_score >= 0


def test_verifier_cg_deviation(container, items):
    verifier = FeasibilityVerifier(container, items)
    placements = [
        {"item_id": "A", "x": 0, "y": 0, "z": 0, "l": 50, "h": 50, "w": 50, "weight": 100},
    ]
    report = verifier.verify(placements)
    assert 0 <= report.cg_deviation_ratio <= 1


def test_verifier_stability_score(container, items):
    verifier = FeasibilityVerifier(container, items)
    placements = [
        {"item_id": "A", "x": 0, "y": 0, "z": 0, "l": 50, "h": 50, "w": 50, "weight": 10},
    ]
    report = verifier.verify(placements)
    assert 0 <= report.stability_score <= 1


def test_verifier_orientation_constraint(container):
    """
    forbidden_horizontal_dim='height' means height cannot be horizontal.
    - "height_vertical": height is vertical → VALID
    - "width_vertical": width is vertical → height is horizontal → INVALID
    """
    items_with_constraint = [
        ItemInput(id="X", length=100, width=50, height=30, weight=5, quantity=1,
                  forbidden_horizontal_dim="height"),
    ]
    verifier = FeasibilityVerifier(container, items_with_constraint)

    # Place on floor (y=0) and centered in X/Z; "height_vertical" is valid
    placements_valid = [
        {"item_id": "X", "x": 50, "y": 0, "z": 75, "l": 100, "h": 30, "w": 50,
         "weight": 5, "orientation": "height_vertical"},
    ]
    report = verifier.verify(placements_valid)
    assert report.orientation_ok is True

    # "width_vertical" makes height horizontal → violates forbidden='height'
    placements_invalid = [
        {"item_id": "X", "x": 50, "y": 0, "z": 75, "l": 100, "h": 50, "w": 30,
         "weight": 5, "orientation": "width_vertical"},
    ]
    report2 = verifier.verify(placements_invalid)
    assert report2.orientation_ok is False
    assert report2.orientation_violations >= 1


def test_verifier_fragile_violations(container):
    fragile_items = [
        ItemInput(id="F", length=50, width=50, height=50, weight=5, quantity=1, is_fragile=True),
        ItemInput(id="H", length=50, width=50, height=50, weight=50, quantity=1),
    ]
    verifier = FeasibilityVerifier(container, fragile_items)
    placements = [
        {"item_id": "F", "x": 0, "y": 0, "z": 0, "l": 50, "h": 50, "w": 50, "weight": 5, "is_fragile": True},
        {"item_id": "H", "x": 0, "y": 50, "z": 0, "l": 50, "h": 50, "w": 50, "weight": 50},
    ]
    report = verifier.verify(placements)
    assert report.fragile_violations >= 1
