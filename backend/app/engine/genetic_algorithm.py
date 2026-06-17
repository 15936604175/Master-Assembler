"""
Genetic Algorithm Module for Container Loading Optimization

Features:
- Chromosome encoding: instance index permutation (placement order)
- Multi-objective fitness: utilization, stability, CG balance
- Tournament selection, order crossover (OX), swap/insert/reverse mutation
- Elitism: preserve top N individuals
- Seed population from Extreme Point greedy solution
"""

import random
from typing import List, Tuple, Dict, Optional
from dataclasses import dataclass
from app.models.container import ContainerConfig
from app.models.item import ItemInput
from app.engine.feasibility import VerificationReport
from app.engine.optimizer_base import OptimizerBase


@dataclass
class GAConfig:
    population_size: int = 30
    generations: int = 40
    crossover_rate: float = 0.8
    mutation_rate: float = 0.2
    elite_count: int = 3
    tournament_size: int = 3
    seed_ratio: float = 0.3


@dataclass
class FitnessResult:
    utilization: float
    stability: float
    cg_balance: float
    raw_score: float
    report: VerificationReport


class GeneticOptimizer(OptimizerBase):
    """GA-based container loading optimizer."""

    def __init__(self, container: ContainerConfig, items: List[ItemInput],
                 config: Optional[GAConfig] = None):
        super().__init__(container, items)
        self.config = config or GAConfig()
        self.best_chromosome: Optional[List[int]] = None
        self.best_fitness: Optional[FitnessResult] = None

    def _evaluate(self, chromosome: List[int]) -> FitnessResult:
        """Evaluate fitness of a chromosome."""
        placements, _ = self._decode(chromosome)
        if not placements:
            return FitnessResult(
                utilization=0.0, stability=0.0, cg_balance=0.0,
                raw_score=-999.0,
                report=VerificationReport(False, False, False, False),
            )

        utilization, stability, cg_balance = self.evaluate_objectives(placements)
        raw_score = self.score_placements(placements)

        return FitnessResult(
            utilization=utilization,
            stability=stability,
            cg_balance=cg_balance,
            raw_score=raw_score,
            report=VerificationReport(True, True, True, True),
        )

    def _tournament_select(self, population: List[List[int]],
                           fitnesses: List[FitnessResult]) -> List[int]:
        if not population:
            return []
        indices = random.sample(range(len(population)), min(self.config.tournament_size, len(population)))
        best_idx = max(indices, key=lambda i: fitnesses[i].raw_score)
        return population[best_idx]

    def _order_crossover(self, p1: List[int], p2: List[int]) -> Tuple[List[int], List[int]]:
        """Order crossover (OX) for permutation chromosomes."""
        size = len(p1)
        if size < 2:
            return p1[:], p2[:]
        a, b = sorted(random.sample(range(size), 2))
        c1 = [None] * size
        c2 = [None] * size
        c1[a:b + 1] = p1[a:b + 1]
        c2[a:b + 1] = p2[a:b + 1]
        seg1 = set(c1[a:b + 1])
        seg2 = set(c2[a:b + 1])
        fill1 = [x for x in p2 if x not in seg1]
        fill2 = [x for x in p1 if x not in seg2]
        idx1 = 0
        idx2 = 0
        for i in range(size):
            if c1[i] is None:
                c1[i] = fill1[idx1]
                idx1 += 1
            if c2[i] is None:
                c2[i] = fill2[idx2]
                idx2 += 1
        return c1, c2

    def _mutate_swap(self, chromosome: List[int]) -> List[int]:
        chrom = chromosome[:]
        if len(chrom) < 2:
            return chrom
        i, j = random.sample(range(len(chrom)), 2)
        chrom[i], chrom[j] = chrom[j], chrom[i]
        return chrom

    def _mutate_insert(self, chromosome: List[int]) -> List[int]:
        chrom = chromosome[:]
        if len(chrom) < 2:
            return chrom
        i = random.randint(0, len(chrom) - 1)
        gene = chrom.pop(i)
        j = random.randint(0, len(chrom))
        chrom.insert(j, gene)
        return chrom

    def _mutate_reverse(self, chromosome: List[int]) -> List[int]:
        chrom = chromosome[:]
        if len(chrom) < 2:
            return chrom
        i, j = sorted(random.sample(range(len(chrom)), 2))
        chrom[i:j + 1] = reversed(chrom[i:j + 1])
        return chrom

    def _evolve(self, population: List[List[int]], fitnesses: List[FitnessResult]) -> List[List[int]]:
        elite_size = min(self.config.elite_count, len(population) // 2)
        elite_indices = sorted(range(len(fitnesses)), key=lambda i: fitnesses[i].raw_score, reverse=True)[:elite_size]
        elites = [population[i][:] for i in elite_indices]
        new_population: List[List[int]] = list(elites)

        while len(new_population) < self.config.population_size:
            p1 = self._tournament_select(population, fitnesses)
            p2 = self._tournament_select(population, fitnesses)
            if random.random() < self.config.crossover_rate:
                c1, c2 = self._order_crossover(p1, p2)
            else:
                c1, c2 = p1[:], p2[:]
            if random.random() < self.config.mutation_rate:
                mut_type = random.choice(["swap", "insert", "reverse"])
                if mut_type == "swap":
                    c1 = self._mutate_swap(c1)
                elif mut_type == "insert":
                    c1 = self._mutate_insert(c1)
                else:
                    c1 = self._mutate_reverse(c1)
            if random.random() < self.config.mutation_rate:
                mut_type = random.choice(["swap", "insert", "reverse"])
                if mut_type == "swap":
                    c2 = self._mutate_swap(c2)
                elif mut_type == "insert":
                    c2 = self._mutate_insert(c2)
                else:
                    c2 = self._mutate_reverse(c2)
            new_population.append(c1)
            if len(new_population) < self.config.population_size:
                new_population.append(c2)

        return new_population[:self.config.population_size]

    def run(self) -> Tuple[List[Dict], FitnessResult, int]:
        if self.n == 0:
            return [], FitnessResult(0, 0, 0, 0, VerificationReport(True, True, True, True)), 0

        greedy = self._greedy_chromosome()
        population: List[List[int]] = [greedy]
        for _ in range(self.config.population_size - 1):
            population.append(self._random_chromosome())

        best_overall: Optional[List[int]] = None
        best_overall_fitness: Optional[FitnessResult] = None
        stagnant_generations = 0

        gen = 0
        for gen in range(self.config.generations):
            fitnesses = [self._evaluate(chrom) for chrom in population]

            gen_best_idx = max(range(len(fitnesses)), key=lambda i: fitnesses[i].raw_score)
            if best_overall is None or fitnesses[gen_best_idx].raw_score > best_overall_fitness.raw_score:
                best_overall = population[gen_best_idx][:]
                best_overall_fitness = fitnesses[gen_best_idx]
                stagnant_generations = 0
            else:
                stagnant_generations += 1

            if stagnant_generations >= 30:
                break

            population = self._evolve(population, fitnesses)

        self.best_chromosome = best_overall
        self.best_fitness = best_overall_fitness

        if best_overall is None:
            return [], FitnessResult(0, 0, 0, 0, VerificationReport(False, False, False, False)), 0

        placements, _ = self._decode(best_overall)
        return placements, best_overall_fitness, gen + 1
