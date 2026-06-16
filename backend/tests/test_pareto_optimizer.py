import pytest
from app.engine.pareto_optimizer import NSGAOptimizer, NSGAConfig, Individual
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


def test_nsga_initialization(container, items):
    nsga = NSGAOptimizer(container, items)
    assert nsga.n > 0


def test_nsga_config_defaults():
    config = NSGAConfig()
    assert config.population_size == 60
    assert config.generations == 100
    assert config.elite_count == 10


def test_nsga_dominated():
    nsga = NSGAOptimizer.__new__(NSGAOptimizer)
    assert nsga._dominated((0.8, 0.9, 0.7), (0.7, 0.8, 0.6)) is True
    assert nsga._dominated((0.7, 0.8, 0.6), (0.8, 0.9, 0.7)) is False
    assert nsga._dominated((0.8, 0.8, 0.8), (0.8, 0.8, 0.8)) is False


def test_nsga_random_chromosome(container, items):
    nsga = NSGAOptimizer(container, items)
    chrom = nsga._random_chromosome()
    assert len(chrom) == nsga.n


def test_nsga_greedy_chromosome(container, items):
    nsga = NSGAOptimizer(container, items)
    chrom = nsga._greedy_chromosome()
    assert len(chrom) == nsga.n


def test_nsga_decode(container, items):
    nsga = NSGAOptimizer(container, items)
    chrom = nsga._random_chromosome()
    placements = nsga._decode(chrom)
    assert isinstance(placements, list)


def test_nsga_evaluate(container, items):
    nsga = NSGAOptimizer(container, items)
    chrom = nsga._random_chromosome()
    ind = nsga._evaluate(chrom)
    assert isinstance(ind, Individual)
    assert len(ind.objectives) == 3


def test_nsga_non_dominated_sort(container, items):
    nsga = NSGAOptimizer(container, items)
    inds = [
        Individual(chromosome=[0], objectives=(0.5, 0.5, 0.5)),
        Individual(chromosome=[1], objectives=(0.8, 0.8, 0.8)),
        Individual(chromosome=[2], objectives=(0.6, 0.9, 0.7)),
    ]
    fronts = nsga._non_dominated_sort(inds)
    assert len(fronts) >= 1
    assert len(fronts[0]) >= 1


def test_nsga_crowding_distance(container, items):
    nsga = NSGAOptimizer(container, items)
    inds = [
        Individual(chromosome=[0], objectives=(0.5, 0.5, 0.5)),
        Individual(chromosome=[1], objectives=(0.8, 0.8, 0.8)),
        Individual(chromosome=[2], objectives=(0.6, 0.9, 0.7)),
    ]
    nsga._crowding_distance(inds, [0, 1, 2])
    for ind in inds:
        assert ind.crowding_distance >= 0


def test_nsga_run(container, items):
    nsga = NSGAOptimizer(
        container, items,
        NSGAConfig(population_size=20, generations=10, elite_count=5)
    )
    result = nsga.run()
    assert hasattr(result, 'solutions')
    assert hasattr(result, 'extreme_util')
    assert hasattr(result, 'extreme_stability')
    assert hasattr(result, 'extreme_cg')
    assert hasattr(result, 'balanced')


def test_nsga_returns_pareto_front(container, items):
    nsga = NSGAOptimizer(
        container, items,
        NSGAConfig(population_size=30, generations=15)
    )
    result = nsga.run()
    assert len(result.solutions) >= 0
    assert result.pareto_count == len(result.solutions)


def test_nsga_selection(container, items):
    nsga = NSGAOptimizer(container, items, NSGAConfig(population_size=10, generations=5))
    inds = [
        Individual(chromosome=[i], objectives=(0.5 + i * 0.05, 0.5 + i * 0.03, 0.5 + i * 0.02))
        for i in range(10)
    ]
    selected = nsga._select(inds, 5)
    assert len(selected) == 5


def test_nsga_crossover(container, items):
    nsga = NSGAOptimizer(container, items)
    p1 = nsga._random_chromosome()
    p2 = nsga._random_chromosome()
    c1, c2 = nsga._crossover(p1, p2)
    assert len(c1) == len(p1)
    assert len(c2) == len(p2)


def test_nsga_mutate(container, items):
    nsga = NSGAOptimizer(container, items)
    chrom = nsga._random_chromosome()
    mutated = nsga._mutate(chrom)
    assert len(mutated) == len(chrom)


def test_nsga_empty_items(container):
    nsga = NSGAOptimizer(container, [])
    result = nsga.run()
    assert result.solutions == []
