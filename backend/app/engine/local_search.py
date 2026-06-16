"""
Local Search Optimization Module with Simulated Annealing

Takes a seed chromosome (from GA or greedy) and performs iterative
local search using:
- Item order swap
- Item rotation change
- Block move operations

Combined with simulated annealing to escape local optima.
"""

import random
import math
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from app.models.container import ContainerConfig
from app.models.item import ItemInput
from app.engine.feasibility import VerificationReport
from app.engine.optimizer_base import OptimizerBase


@dataclass
class LSConfig:
    max_iterations: int = 1000
    no_improve_limit: int = 50
    initial_temp: float = 1.0
    cooling_rate: float = 0.995
    strategy: str = "best"


@dataclass
class LSResult:
    placements: List[Dict]
    utilization: float
    stability: float
    cg_balance: float
    score: float
    iterations_run: int
    temperature: float
    feasible: bool


class LocalSearchOptimizer(OptimizerBase):
    """Local search + simulated annealing optimizer."""

    def __init__(self, container: ContainerConfig, items: List[ItemInput],
                 seed_chromosome: Optional[List[int]] = None,
                 config: Optional[LSConfig] = None):
        super().__init__(container, items)
        self.config = config or LSConfig()
        self.seed = seed_chromosome or self._greedy_chromosome()

    def _evaluate(self, chromosome: List[int]) -> Tuple[float, Optional[LSResult]]:
        placements = self._decode(chromosome)
        if not placements:
            return -999.0, None

        utilization, stability, cg_balance = self.evaluate_objectives(placements)
        score = self.score_placements(placements)
        report = self.verifier.verify(placements)

        result = LSResult(
            placements=placements,
            utilization=utilization,
            stability=stability,
            cg_balance=cg_balance,
            score=score,
            iterations_run=0,
            temperature=self.config.initial_temp,
            feasible=report.is_feasible,
        )
        return score, result

    def _neighbor_swap(self, chromosome: List[int]) -> List[int]:
        chrom = chromosome[:]
        if len(chrom) < 2:
            return chrom
        i, j = random.sample(range(len(chrom)), 2)
        chrom[i], chrom[j] = chrom[j], chrom[i]
        return chrom

    def _neighbor_rotate(self, chromosome: List[int]) -> List[int]:
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

    def _neighbor_insert(self, chromosome: List[int]) -> List[int]:
        chrom = chromosome[:]
        if len(chrom) < 2:
            return chrom
        i = random.randint(0, len(chrom) - 1)
        gene = chrom.pop(i)
        j = random.randint(0, len(chrom))
        chrom.insert(j, gene)
        return chrom

    def _neighbor_block_move(self, chromosome: List[int]) -> List[int]:
        chrom = chromosome[:]
        if len(chrom) < 4:
            return chrom
        block_size = random.randint(2, min(5, len(chrom) // 2))
        start = random.randint(0, len(chrom) - block_size)
        block = chrom[start:start + block_size]
        del chrom[start:start + block_size]
        insert_pos = random.randint(0, len(chrom))
        chrom[insert_pos:insert_pos] = block
        return chrom

    def _random_neighbor(self, chromosome: List[int]) -> List[int]:
        neighbor_type = random.choice(["swap", "rotate", "insert", "block"])
        if neighbor_type == "swap":
            return self._neighbor_swap(chromosome)
        elif neighbor_type == "rotate":
            return self._neighbor_rotate(chromosome)
        elif neighbor_type == "insert":
            return self._neighbor_insert(chromosome)
        else:
            return self._neighbor_block_move(chromosome)

    def run(self) -> LSResult:
        if self.n == 0:
            return LSResult([], 0, 0, 0, 0, 0, 0, True)

        n_to_use = min(self.n, 200)
        current_chrom = self.seed[:n_to_use]
        current_score, current_result = self._evaluate(current_chrom)

        if current_result is None:
            current_chrom = self._greedy_chromosome()[:n_to_use]
            current_score, current_result = self._evaluate(current_chrom)

        if current_result is None:
            return LSResult([], 0, 0, 0, -999, 0, 0, False)

        best_chrom = current_chrom[:]
        best_score = current_score
        best_result = current_result

        temp = self.config.initial_temp
        no_improve = 0

        for i in range(self.config.max_iterations):
            neighbor = self._random_neighbor(current_chrom)
            neighbor_score, neighbor_result = self._evaluate(neighbor)

            if neighbor_result is None:
                continue

            delta = neighbor_score - current_score

            if delta > 0 or random.random() < math.exp(delta / max(temp, 1e-10)):
                current_chrom = neighbor
                current_score = neighbor_score
                current_result = neighbor_result

                if current_score > best_score:
                    best_chrom = current_chrom[:]
                    best_score = current_score
                    best_result = current_result
                    no_improve = 0
                else:
                    no_improve += 1
            else:
                no_improve += 1

            temp *= self.config.cooling_rate

            if no_improve >= self.config.no_improve_limit:
                break

        best_result.iterations_run = i + 1
        best_result.temperature = temp
        return best_result
