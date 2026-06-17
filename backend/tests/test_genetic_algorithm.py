import pytest
from app.engine.genetic_algorithm import GeneticOptimizer, GAConfig
from app.engine.rotation import get_allowed_orientations
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


def test_ga_initialization(container, items):
    ga = GeneticOptimizer(container, items)
    assert ga.n > 0
    assert len(ga.allowed_rotations) == ga.n


def test_ga_config_defaults():
    config = GAConfig()
    assert config.population_size == 30
    assert config.generations == 40
    assert config.elite_count == 3


def test_ga_chromosome_length(container, items):
    ga = GeneticOptimizer(container, items, GAConfig(population_size=10, generations=5))
    chrom = ga._greedy_chromosome()
    assert len(chrom) == ga.n
    assert sorted(chrom) == list(range(ga.n))


def test_ga_random_chromosome(container, items):
    ga = GeneticOptimizer(container, items)
    chrom = ga._random_chromosome()
    assert len(chrom) == ga.n
    assert sorted(chrom) == list(range(ga.n))


def test_ga_decode_returns_placements(container, items):
    ga = GeneticOptimizer(container, items)
    chrom = ga._random_chromosome()
    placements, unplaced = ga._decode(chrom)
    assert isinstance(placements, list)
    assert isinstance(unplaced, list)
    assert len(placements) + len(unplaced) == ga.n


def test_ga_evaluate(container, items):
    ga = GeneticOptimizer(container, items)
    chrom = ga._random_chromosome()
    fitness = ga._evaluate(chrom)
    assert hasattr(fitness, 'utilization')
    assert hasattr(fitness, 'stability')
    assert hasattr(fitness, 'cg_balance')
    assert hasattr(fitness, 'raw_score')


def test_ga_run_returns_placements(container, items):
    ga = GeneticOptimizer(
        container, items,
        GAConfig(population_size=20, generations=10, elite_count=3, seed_ratio=0.3)
    )
    placements, fitness, generations = ga.run()
    assert isinstance(placements, list)
    assert generations > 0


def test_ga_tournament_selection(container, items):
    ga = GeneticOptimizer(container, items, GAConfig(population_size=10, generations=5))
    pop = [ga._random_chromosome() for _ in range(5)]
    fitnesses = [ga._evaluate(c) for c in pop]
    selected = ga._tournament_select(pop, fitnesses)
    assert len(selected) == ga.n


def test_ga_crossover(container, items):
    ga = GeneticOptimizer(container, items)
    p1 = ga._random_chromosome()
    p2 = ga._random_chromosome()
    c1, c2 = ga._order_crossover(p1, p2)
    assert len(c1) == len(p1)
    assert len(c2) == len(p2)
    assert sorted(c1) == list(range(ga.n))
    assert sorted(c2) == list(range(ga.n))


def test_ga_mutations(container, items):
    ga = GeneticOptimizer(container, items)
    chrom = ga._random_chromosome()
    assert len(ga._mutate_swap(chrom)) == ga.n
    assert len(ga._mutate_insert(chrom)) == ga.n
    assert len(ga._mutate_reverse(chrom)) == ga.n
    assert sorted(ga._mutate_swap(chrom)) == list(range(ga.n))


def test_ga_empty_items(container):
    ga = GeneticOptimizer(container, [])
    placements, fitness, generations = ga.run()
    assert placements == []
    assert generations == 0


def test_allowed_orientations(container):
    items_constrained = [
        ItemInput(id="X", length=100, width=60, height=40, weight=10, quantity=1,
                  forbidden_horizontal_dims=["height"]),
    ]
    ga = GeneticOptimizer(container, items_constrained,
                          GAConfig(population_size=5, generations=3))
    placements, fitness, _ = ga.run()
    assert isinstance(placements, list)
