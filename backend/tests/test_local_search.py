import pytest
from app.engine.local_search import LocalSearchOptimizer, LSConfig
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


def test_ls_initialization(container, items):
    ls = LocalSearchOptimizer(container, items)
    assert ls.n > 0
    assert ls.seed is not None
    assert len(ls.seed) == ls.n


def test_ls_config_defaults():
    config = LSConfig()
    assert config.max_iterations == 200
    assert config.strategy == "best"
    assert config.initial_temp == 1.0
    assert config.cooling_rate == 0.995


def test_ls_run(container, items):
    ls = LocalSearchOptimizer(
        container, items,
        LSConfig(max_iterations=50, no_improve_limit=10)
    )
    result = ls.run()
    assert hasattr(result, 'placements')
    assert hasattr(result, 'utilization')
    assert hasattr(result, 'iterations_run')
    assert result.iterations_run > 0


def test_ls_best_strategy(container, items):
    ls = LocalSearchOptimizer(container, items, LSConfig(strategy="best"))
    result = ls.run()
    assert result.placements is not None


def test_ls_simulated_annealing(container, items):
    ls = LocalSearchOptimizer(
        container, items,
        LSConfig(initial_temp=5.0, cooling_rate=0.95, max_iterations=30)
    )
    result = ls.run()
    assert hasattr(result, 'temperature')
    assert result.temperature >= 0


def test_ls_neighborhood_swap(container, items):
    ls = LocalSearchOptimizer(container, items)
    chrom = ls._greedy_chromosome()
    neighbor = ls._neighbor_swap(chrom)
    assert len(neighbor) == ls.n
    assert sorted(neighbor) == list(range(ls.n))


def test_ls_neighborhood_insert(container, items):
    ls = LocalSearchOptimizer(container, items)
    chrom = ls._greedy_chromosome()
    neighbor = ls._neighbor_insert(chrom)
    assert len(neighbor) == ls.n
    assert sorted(neighbor) == list(range(ls.n))


def test_ls_neighborhood_reverse(container, items):
    ls = LocalSearchOptimizer(container, items)
    chrom = ls._greedy_chromosome()
    neighbor = ls._neighbor_reverse(chrom)
    assert len(neighbor) == ls.n
    assert sorted(neighbor) == list(range(ls.n))


def test_ls_neighborhood_block(container, items):
    ls = LocalSearchOptimizer(container, items)
    chrom = ls._greedy_chromosome()
    neighbor = ls._neighbor_block_move(chrom)
    assert len(neighbor) == ls.n
    assert sorted(neighbor) == list(range(ls.n))


def test_ls_empty_items(container):
    ls = LocalSearchOptimizer(container, [])
    result = ls.run()
    assert result.placements == []


def test_ls_empty_chromosome(container):
    ls = LocalSearchOptimizer(container, [])
    assert ls.seed == []


def test_ls_target_utilization(container, items):
    ls = LocalSearchOptimizer(container, items, LSConfig(max_iterations=30))
    result = ls.run()
    assert result.utilization <= 1.0
