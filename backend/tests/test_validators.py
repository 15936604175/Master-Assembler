import pytest
from app.validators.item_validator import validate_items, validate_request
from app.models.container import ContainerConfig
from app.models.item import ItemInput


def test_validate_valid_items():
    container = ContainerConfig(
        length=1000, width=1000, height=1000, max_weight=1000
    )
    items = [ItemInput(id="A", length=100, width=100, height=100,
                       weight=10, quantity=1)]
    is_valid, errors = validate_items(items, container)
    assert is_valid is True
    assert len(errors) == 0


def test_validate_total_weight_exceeded():
    container = ContainerConfig(
        length=1000, width=1000, height=1000, max_weight=50
    )
    items = [ItemInput(id="A", length=100, width=100, height=100,
                       weight=30, quantity=2)]
    is_valid, errors = validate_items(items, container)
    assert is_valid is False
    assert any("重量" in e or "weight" in e.lower() for e in errors)


def test_validate_item_larger_than_container():
    container = ContainerConfig(
        length=100, width=100, height=100, max_weight=1000
    )
    items = [ItemInput(id="A", length=200, width=200, height=200,
                       weight=10, quantity=1)]
    is_valid, errors = validate_items(items, container)
    assert is_valid is False
    assert len(errors) > 0


def test_validate_request_empty_items():
    container = ContainerConfig(
        length=100, width=100, height=100, max_weight=1000
    )
    is_valid, errors = validate_request(container, [])
    assert is_valid is False
    assert len(errors) > 0


def test_validate_request_valid():
    container = ContainerConfig(
        length=1000, width=1000, height=1000, max_weight=1000
    )
    items = [ItemInput(id="A", length=100, width=100, height=100,
                       weight=10, quantity=1)]
    is_valid, errors = validate_request(container, items)
    assert is_valid is True
    assert len(errors) == 0


def test_validate_duplicate_ids():
    container = ContainerConfig(
        length=1000, width=1000, height=1000, max_weight=1000
    )
    items = [
        ItemInput(id="A", length=100, width=100, height=100,
                  weight=10, quantity=1),
        ItemInput(id="A", length=50, width=50, height=50,
                  weight=5, quantity=2),
    ]
    is_valid, errors = validate_items(items, container)
    assert is_valid is False
    assert any("重复" in e or "duplicate" in e.lower() or "repeat" in e.lower()
               for e in errors)
