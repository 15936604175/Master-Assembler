import pytest
from app.engine.packer import EPacker
from app.models.container import ContainerConfig
from app.models.item import ItemInput


def test_packer_single_item():
    packer = EPacker()
    container = ContainerConfig(length=100, width=100, height=100, max_weight=1000)
    items = [ItemInput(id="A", length=50, width=40, height=30, weight=5, quantity=1)]
    result = packer.pack(container, items)
    assert result.success is True
    assert len(result.placements) == 1
    assert result.unplaced_items == []


def test_packer_multiple_same_items():
    packer = EPacker()
    container = ContainerConfig(length=200, width=200, height=200, max_weight=5000)
    items = [ItemInput(id="A", length=100, width=100, height=100, weight=10, quantity=4)]
    result = packer.pack(container, items)
    assert result.success is True
    assert len(result.placements) > 0


def test_packer_exceeds_weight():
    packer = EPacker()
    container = ContainerConfig(length=1000, width=1000, height=1000, max_weight=10)
    items = [ItemInput(id="A", length=50, width=50, height=50, weight=100, quantity=1)]
    result = packer.pack(container, items)
    assert result.success is True
    assert len(result.unplaced_items) > 0


def test_packer_item_too_large():
    packer = EPacker()
    container = ContainerConfig(length=100, width=100, height=100, max_weight=1000)
    items = [ItemInput(id="A", length=200, width=200, height=200, weight=10, quantity=1)]
    result = packer.pack(container, items)
    assert result.success is True
    assert len(result.unplaced_items) > 0


def test_packer_utilization_benchmark():
    packer = EPacker()
    container = ContainerConfig(length=1000, width=1000, height=1000, max_weight=50000)
    items = [
        ItemInput(id="A", length=200, width=200, height=200, weight=10, quantity=80),
    ]
    result = packer.pack(container, items)
    # 200mm cubes in 1000mm container: 5*5*5=125 max. 80 items = 64% theoretical max
    # EP algorithm should achieve at least 50%
    assert result.container_utilization >= 0.5, f"Utilization {result.container_utilization} too low"


def test_packer_center_of_gravity():
    packer = EPacker()
    container = ContainerConfig(length=100, width=100, height=100, max_weight=1000)
    items = [ItemInput(id="A", length=50, width=40, height=30, weight=10, quantity=1)]
    result = packer.pack(container, items)
    cg = result.center_of_gravity
    # CG should be at the center of the single item
    assert abs(cg.x - 25.0) < 0.1
    assert abs(cg.y - 15.0) < 0.1
    assert abs(cg.z - 20.0) < 0.1


def test_packer_no_items():
    packer = EPacker()
    container = ContainerConfig(length=100, width=100, height=100, max_weight=1000)
    result = packer.pack(container, [])
    assert result.success is True
    assert len(result.placements) == 0
    assert result.container_utilization == 0.0
