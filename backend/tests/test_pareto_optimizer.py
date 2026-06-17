import pytest
from app.engine.pareto_optimizer import NSGAOptimizer, NSGAConfig, NSGASolution
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
    assert config.generations == 80
    assert config.elite_count == 5


def test_nsga_random_chromosome(container, items):
    nsga = NSGAOptimizer(container, items)
    chrom = nsga._random_chromosome()
    assert len(chrom) == nsga.n
    assert sorted(chrom) == list(range(nsga.n))


def test_nsga_greedy_chromosome(container, items):
    nsga = NSGAOptimizer(container, items)
    chrom = nsga._greedy_chromosome()
    assert len(chrom) == nsga.n
    assert sorted(chrom) == list(range(nsga.n))


def test_nsga_decode(container, items):
    nsga = NSGAOptimizer(container, items)
    chrom = nsga._random_chromosome()
    placements, unplaced = nsga._decode(chrom)
    assert isinstance(placements, list)
    assert isinstance(unplaced, list)
    assert len(placements) + len(unplaced) == nsga.n


def test_nsga_evaluate(container, items):
    nsga = NSGAOptimizer(container, items)
    chrom = nsga._random_chromosome()
    sol = nsga._evaluate_solution(chrom)
    assert sol is None or isinstance(sol, NSGASolution)
    if sol is not None:
        assert len(sol.objectives) == 3


def test_nsga_non_dominated_sort(container, items):
    nsga = NSGAOptimizer(container, items)
    sols = [
        NSGASolution(chromosome=[0], placements=[], objectives=[0.5, 0.5, 0.5]),
        NSGASolution(chromosome=[1], placements=[], objectives=[0.8, 0.8, 0.8]),
        NSGASolution(chromosome=[2], placements=[], objectives=[0.6, 0.9, 0.7]),
    ]
    fronts = nsga._non_dominated_sort(sols)
    assert len(fronts) >= 1
    assert len(fronts[0]) >= 1


def test_nsga_crowding_distance(container, items):
    nsga = NSGAOptimizer(container, items)
    sols = [
        NSGASolution(chromosome=[0], placements=[], objectives=[0.5, 0.5, 0.5]),
        NSGASolution(chromosome=[1], placements=[], objectives=[0.8, 0.8, 0.8]),
        NSGASolution(chromosome=[2], placements=[], objectives=[0.6, 0.9, 0.7]),
        NSGASolution(chromosome=[3], placements=[], objectives=[0.7, 0.6, 0.65]),
    ]
    nsga._crowding_distance(sols)
    for s in sols:
        assert s.crowding_distance >= 0


def test_nsga_run(container, items):
    nsga = NSGAOptimizer(
        container, items,
        NSGAConfig(population_size=20, generations=10, elite_count=5)
    )
    result = nsga.run()
    assert hasattr(result, 'solutions')
    assert hasattr(result, 'pareto_front')
    assert hasattr(result, 'generations')


def test_nsga_returns_pareto_front(container, items):
    nsga = NSGAOptimizer(
        container, items,
        NSGAConfig(population_size=30, generations=15)
    )
    result = nsga.run()
    assert len(result.solutions) >= 0
    assert len(result.pareto_front) >= 1


def test_nsga_selection(container, items):
    nsga = NSGAOptimizer(container, items, NSGAConfig(population_size=10, generations=5))
    sols = [
        NSGASolution(
            chromosome=nsga._random_chromosome(),
            placements=[],
            objectives=[0.5 + i * 0.05, 0.5 + i * 0.03, 0.5 + i * 0.02],
            rank=0,
        )
        for i in range(10)
    ]
    selected = nsga._tournament_select(sols)
    assert len(selected) == nsga.n


def test_nsga_crossover(container, items):
    nsga = NSGAOptimizer(container, items)
    p1 = nsga._random_chromosome()
    p2 = nsga._random_chromosome()
    c1 = nsga._order_crossover(p1, p2)
    assert len(c1) == len(p1)
    assert sorted(c1) == list(range(nsga.n))


def test_nsga_mutate(container, items):
    nsga = NSGAOptimizer(container, items)
    chrom = nsga._random_chromosome()
    mutated = nsga._mutate(chrom)
    assert len(mutated) == len(chrom)
    assert sorted(mutated) == list(range(nsga.n))


def test_nsga_empty_items(container):
    nsga = NSGAOptimizer(container, [])
    result = nsga.run()
    assert result.solutions == []
