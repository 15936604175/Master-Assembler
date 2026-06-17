"""
Pareto / NSGA-II Multi-Objective Optimization Module

Uses NSGA-II (Non-Dominated Sorting Genetic Algorithm II) to optimize
container loading with three objectives:
1. Maximize volume utilization
2. Maximize stability (support ratio)
3. Maximize center-of-gravity balance

Returns Pareto-optimal solutions for trade-off analysis.
"""

import random
import copy
from typing import List, Tuple, Dict, Optional
from dataclasses import dataclass, field
from app.models.container import ContainerConfig
from app.models.item import ItemInput
from app.engine.feasibility import VerificationReport
from app.engine.optimizer_base import OptimizerBase


@dataclass
class NSGAConfig:
    population_size: int = 60
    generations: int = 80
    crossover_rate: float = 0.85
    mutation_rate: float = 0.2
    elite_count: int = 5
    tournament_size: int = 3
    seed_ratio: float = 0.2


@dataclass
class NSGASolution:
    chromosome: List[int]
    placements: List[Dict]
    objectives: List[float]
    rank: int = 0
    crowding_distance: float = 0.0
    feasible: bool = True


@dataclass
class NSGAResult:
    solutions: List[NSGASolution]
    pareto_front: List[NSGASolution]
    generations: int


class NSGAOptimizer(OptimizerBase):
    """NSGA-II multi-objective optimizer."""

    NUM_OBJECTIVES = 3

    def __init__(self, container: ContainerConfig, items: List[ItemInput],
                 config: Optional[NSGAConfig] = None):
        super().__init__(container, items)
        self.config = config or NSGAConfig()

    def _evaluate_solution(self, chromosome: List[int]) -> Optional[NSGASolution]:
        placements, _ = self._decode(chromosome)
        if not placements:
            return None

        utilization, stability, cg_balance = self.evaluate_objectives(placements)
        report = self.verifier.verify(placements)

        return NSGASolution(
            chromosome=chromosome,
            placements=placements,
            objectives=[utilization, stability, cg_balance],
            feasible=report.is_feasible,
        )

    def _non_dominated_sort(self, solutions: List[NSGASolution]) -> List[List[NSGASolution]]:
        """Fast non-dominated sort."""
        n = len(solutions)
        fronts: List[List[NSGASolution]] = []
        domination_count = [0] * n
        dominated = [[] for _ in range(n)]

        def dominates(a: List[float], b: List[float]) -> bool:
            at_least_one_greater = False
            for i in range(len(a)):
                if a[i] < b[i]:
                    return False
                if a[i] > b[i]:
                    at_least_one_greater = True
            return at_least_one_greater

        for i in range(n):
            for j in range(n):
                if i == j:
                    continue
                if dominates(solutions[i].objectives, solutions[j].objectives):
                    dominated[i].append(j)
                elif dominates(solutions[j].objectives, solutions[i].objectives):
                    domination_count[i] += 1

        current_front = [solutions[i] for i in range(n) if domination_count[i] == 0]
        if current_front:
            fronts.append(current_front)

        visited = set()
        while current_front:
            next_front = []
            current_indices = []
            for sol in current_front:
                for idx, s in enumerate(solutions):
                    if s is sol:
                        current_indices.append(idx)
                        break
            for ci in current_indices:
                for di in dominated[ci]:
                    domination_count[di] -= 1
                    if domination_count[di] == 0 and di not in visited:
                        next_front.append(solutions[di])
                        visited.add(di)
            if next_front:
                fronts.append(next_front)
            current_front = next_front if next_front else []

        return fronts

    def _crowding_distance(self, solutions: List[NSGASolution]) -> None:
        """Compute crowding distance in-place."""
        n = len(solutions)
        if n == 0:
            return
        if n == 1:
            solutions[0].crowding_distance = float("inf")
            return
        if n == 2:
            solutions[0].crowding_distance = float("inf")
            solutions[1].crowding_distance = float("inf")
            return

        for s in solutions:
            s.crowding_distance = 0.0

        for obj_idx in range(self.NUM_OBJECTIVES):
            solutions.sort(key=lambda s: s.objectives[obj_idx])
            min_val = solutions[0].objectives[obj_idx]
            max_val = solutions[-1].objectives[obj_idx]
            if max_val == min_val:
                continue
            solutions[0].crowding_distance = float("inf")
            solutions[-1].crowding_distance = float("inf")
            for i in range(1, n - 1):
                dist = (solutions[i + 1].objectives[obj_idx] - solutions[i - 1].objectives[obj_idx]) / (max_val - min_val)
                solutions[i].crowding_distance += dist

    def _tournament_select(self, population: List[NSGASolution]) -> List[int]:
        n = len(population)
        if n == 0:
            return []
        contenders = random.sample(population, min(self.config.tournament_size, n))
        def better(a: NSGASolution, b: NSGASolution) -> NSGASolution:
            if a.rank != b.rank:
                return a if a.rank < b.rank else b
            return a if a.crowding_distance >= b.crowding_distance else b
        best = contenders[0]
        for c in contenders[1:]:
            best = better(best, c)
        return best.chromosome[:]

    def _order_crossover(self, p1: List[int], p2: List[int]) -> List[int]:
        """Order crossover (OX) for permutation chromosomes."""
        size = len(p1)
        if size < 2:
            return p1[:]
        a, b = sorted(random.sample(range(size), 2))
        child = [None] * size
        child[a:b + 1] = p1[a:b + 1]
        seg = set(child[a:b + 1])
        fill = [x for x in p2 if x not in seg]
        idx = 0
        for i in range(size):
            if child[i] is None:
                child[i] = fill[idx]
                idx += 1
        return child

    def _mutate(self, chromosome: List[int]) -> List[int]:
        chrom = chromosome[:]
        if not chrom:
            return chrom
        mut_type = random.choice(["swap", "insert", "reverse"])
        if mut_type == "swap" and len(chrom) >= 2:
            i, j = random.sample(range(len(chrom)), 2)
            chrom[i], chrom[j] = chrom[j], chrom[i]
        elif mut_type == "insert" and len(chrom) >= 2:
            i = random.randint(0, len(chrom) - 1)
            gene = chrom.pop(i)
            j = random.randint(0, len(chrom))
            chrom.insert(j, gene)
        elif mut_type == "reverse" and len(chrom) >= 2:
            i, j = sorted(random.sample(range(len(chrom)), 2))
            chrom[i:j + 1] = reversed(chrom[i:j + 1])
        return chrom

    def run(self) -> NSGAResult:
        if self.n == 0:
            return NSGAResult([], [], 0)

        greedy = self._greedy_chromosome()
        initial_chromosomes: List[List[int]] = [greedy]
        for _ in range(self.config.population_size - 1):
            initial_chromosomes.append(self._random_chromosome())

        population: List[NSGASolution] = []
        for chrom in initial_chromosomes:
            sol = self._evaluate_solution(chrom)
            if sol:
                population.append(sol)

        if not population:
            return NSGAResult([], [], 0)

        best_per_gen: List[List[NSGASolution]] = []

        gen = 0
        for gen in range(self.config.generations):
            fronts = self._non_dominated_sort(population)
            for rank, front in enumerate(fronts):
                for sol in front:
                    sol.rank = rank
            for front in fronts:
                self._crowding_distance(front)

            gen_best = [s for s in population if s.rank == 0]
            best_per_gen.append(copy.deepcopy(gen_best))

            new_population: List[NSGASolution] = []
            for front in fronts:
                if len(new_population) + len(front) <= self.config.population_size:
                    new_population.extend(front)
                else:
                    front_sorted = sorted(front, key=lambda s: s.crowding_distance, reverse=True)
                    remaining = self.config.population_size - len(new_population)
                    new_population.extend(front_sorted[:remaining])
                    break

            offspring: List[NSGASolution] = []
            pool = population[:] + new_population[:]
            while len(offspring) < self.config.population_size:
                p1_chrom = self._tournament_select(pool)
                p2_chrom = self._tournament_select(pool)
                if random.random() < self.config.crossover_rate:
                    child1 = self._order_crossover(p1_chrom, p2_chrom)
                    child2 = self._order_crossover(p2_chrom, p1_chrom)
                else:
                    child1, child2 = p1_chrom[:], p2_chrom[:]
                if random.random() < self.config.mutation_rate:
                    child1 = self._mutate(child1)
                if random.random() < self.config.mutation_rate:
                    child2 = self._mutate(child2)

                s1 = self._evaluate_solution(child1)
                if s1:
                    offspring.append(s1)
                s2 = self._evaluate_solution(child2)
                if s2:
                    offspring.append(s2)

            combined = population + offspring
            fronts_combined = self._non_dominated_sort(combined)
            for rank, front in enumerate(fronts_combined):
                for sol in front:
                    sol.rank = rank
            for front in fronts_combined:
                self._crowding_distance(front)

            new_pop = []
            for front in fronts_combined:
                if len(new_pop) + len(front) <= self.config.population_size:
                    new_pop.extend(front)
                else:
                    front_sorted = sorted(front, key=lambda s: s.crowding_distance, reverse=True)
                    remaining = self.config.population_size - len(new_pop)
                    new_pop.extend(front_sorted[:remaining])
                    break
            population = new_pop

        fronts = self._non_dominated_sort(population)
        for rank, front in enumerate(fronts):
            for sol in front:
                sol.rank = rank

        pareto_front = fronts[0] if fronts else population
        return NSGAResult(population, pareto_front, gen + 1)
