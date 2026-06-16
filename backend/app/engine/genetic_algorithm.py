"""
Genetic Algorithm Module for Container Loading Optimization

Features:
- Chromosome encoding: item order + rotation index for each item
- Multi-objective fitness: utilization, stability, CG balance
- Tournament selection, order crossover, swap/rotate mutation
- Elitism: preserve top N individuals
- Seed population from Extreme Point greedy solution
"""

import random
import copy
from typing import List, Tuple, Dict, Optional
from dataclasses import dataclass
from app.models.container import ContainerConfig
from app.models.item import ItemInput
from app.engine.feasibility import VerificationReport
from app.engine.optimizer_base import OptimizerBase


@dataclass
class GAConfig:
    population_size: int = 80
    generations: int = 150
    crossover_rate: float = 0.8
    mutation_rate: float = 0.15
    elite_count: int = 5
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
        placements = self._decode(chromosome)
        if not placements:
            return FitnessResult(
                utilization=0.0, stability=0.0, cg_balance=0.0,
                raw_score=-999.0,
                report=VerificationReport(False, False, False, False),
            )

        report = self.verifier.verify(placements)
        utilization, stability, cg_balance = self.evaluate_objectives(placements)
        raw_score = self.score_placements(placements)

        return FitnessResult(
            utilization=utilization,
            stability=stability,
            cg_balance=cg_balance,
            raw_score=raw_score,
            report=report,
        )

    def _tournament_select(self, population: List[List[int]],
                           fitnesses: List[FitnessResult]) -> List[int]:
        if not population:
            return []
        indices = random.sample(range(len(population)), min(self.config.tournament_size, len(population)))
        best_idx = max(indices, key=lambda i: fitnesses[i].raw_score)
        return population[best_idx]

    def _uniform_crossover(self, p1: List[int], p2: List[int]) -> Tuple[List[int], List[int]]:
        """Uniform crossover for rotation-index chromosomes."""
        size = len(p1)
        if size < 1:
            return p1[:], p2[:]
        c1, c2 = p1[:], p2[:]
        for i in range(size):
            if random.random() < 0.5:
                c1[i], c2[i] = c2[i], c1[i]
        return c1, c2

    def _mutate_swap(self, chromosome: List[int]) -> List[int]:
        chrom = chromosome[:]
        if len(chrom) < 2:
            return chrom
        i, j = random.sample(range(len(chrom)), 2)
        chrom[i], chrom[j] = chrom[j], chrom[i]
        return chrom

    def _mutate_rotate(self, chromosome: List[int]) -> List[int]:
        chrom = chromosome[:]
        if not chrom:
            return chrom
        idx = random.randint(0, len(chrom) - 1)
        allowed = self.allowed_rotations[idx]
        if len(allowed) <= 1:
            return chrom
        current = chrom[idx]
        other = [r for r in allowed if r != current]
        if other:
            chrom[idx] = random.choice(other)
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

    def _evolve(self, population: List[List[int]], fitnesses: List[FitnessResult]) -> List[List[int]]:
        elite_size = min(self.config.elite_count, len(population) // 2)
        elite_indices = sorted(range(len(fitnesses)), key=lambda i: fitnesses[i].raw_score, reverse=True)[:elite_size]
        elites = [population[i][:] for i in elite_indices]
        new_population: List[List[int]] = list(elites)

        while len(new_population) < self.config.population_size:
            p1 = self._tournament_select(population, fitnesses)
            p2 = self._tournament_select(population, fitnesses)
            if random.random() < self.config.crossover_rate:
                c1, c2 = self._uniform_crossover(p1, p2)
            else:
                c1, c2 = p1[:], p2[:]
            if random.random() < self.config.mutation_rate:
                mut_type = random.choice(["swap", "rotate", "insert"])
                if mut_type == "swap":
                    c1 = self._mutate_swap(c1)
                elif mut_type == "rotate":
                    c1 = self._mutate_rotate(c1)
                else:
                    c1 = self._mutate_insert(c1)
            if random.random() < self.config.mutation_rate:
                mut_type = random.choice(["swap", "rotate", "insert"])
                if mut_type == "swap":
                    c2 = self._mutate_swap(c2)
                elif mut_type == "rotate":
                    c2 = self._mutate_rotate(c2)
                else:
                    c2 = self._mutate_insert(c2)
            new_population.append(c1)
            if len(new_population) < self.config.population_size:
                new_population.append(c2)

        return new_population[:self.config.population_size]

    def run(self) -> Tuple[List[Dict], FitnessResult, int]:
        if self.n == 0:
            return [], FitnessResult(0, 0, 0, 0, VerificationReport(True, True, True, True)), 0

        n_to_use = min(self.n, 200)
        greedy = self._greedy_chromosome()[:n_to_use]
        population: List[List[int]] = [greedy]
        for _ in range(self.config.population_size - 1):
            population.append(self._random_chromosome()[:n_to_use])

        best_overall: Optional[List[int]] = None
        best_overall_fitness: Optional[FitnessResult] = None
        stagnant_generations = 0

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

        placements = self._decode(best_overall)
        return placements, best_overall_fitness, gen + 1
