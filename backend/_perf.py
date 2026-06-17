import sys, time
sys.path.insert(0, ".")

from app.engine.genetic_algorithm import GeneticOptimizer, GAConfig
from app.engine.local_search import LocalSearchOptimizer, LSConfig
from app.models.container import ContainerConfig
from app.models.item import ItemInput

container = ContainerConfig(length=5898, width=2352, height=2395, max_weight=28000)
items = [
    ItemInput(id="A", length=100, width=100, height=100, weight=10, quantity=50,
              is_fragile=False, batch_number=0, forbidden_horizontal_dims=[]),
    ItemInput(id="B", length=200, width=200, height=200, weight=10, quantity=20,
              is_fragile=False, batch_number=0, forbidden_horizontal_dims=[]),
]

ga = GeneticOptimizer(container, items, GAConfig(population_size=20, generations=30))

t0 = time.time()
chrom = ga._greedy_chromosome()
t1 = time.time()
placements, unplaced = ga._decode(chrom)
t2 = time.time()
print(f"Greedy chromosome: {t1-t0:.3f}s")
print(f"Single decode: {t2-t1:.3f}s, placed={len(placements)}, unplaced={len(unplaced)}")

t3 = time.time()
fitness = ga._evaluate(ga._random_chromosome())
t4 = time.time()
print(f"Single evaluate: {t4-t3:.3f}s")

print(f"\nEstimated GA total: {(t4-t3)*20*30:.1f}s")

t5 = time.time()
placements2, fit, gens = ga.run()
t6 = time.time()
print(f"GA run: {t6-t5:.1f}s, placed={len(placements2)}, gens={gens}")
