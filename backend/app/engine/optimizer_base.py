"""
Shared base class for container loading optimizers.

Eliminates code duplication between GeneticOptimizer, LocalSearchOptimizer,
and NSGAOptimizer by providing common methods:
- _expand_instances: expand ItemInput into ItemInstance list
- _build_rotation_constraints: pre-compute allowed rotations per instance
- _decode: decode chromosome to placement dicts
- _greedy_chromosome: generate initial chromosome from greedy packer
- _all_rotations: constant list of 6 rotations
"""

import random
from typing import List, Dict, Optional, Tuple
from app.models.container import ContainerConfig
from app.models.item import ItemInput, ItemInstance
from app.engine.packer import EPacker
from app.engine.feasibility import FeasibilityVerifier
from app.engine.rotation import get_all_rotations, get_allowed_orientations


class OptimizerBase:
    """Shared base providing common infrastructure for all optimizers."""

    def __init__(self, container: ContainerConfig, items: List[ItemInput]):
        self.container = container
        self.items = items
        self.instances: List[ItemInstance] = self._expand_instances()
        self.allowed_rotations: List[List[int]] = []
        self._build_rotation_constraints()
        self.verifier = FeasibilityVerifier(container, items)
        self.n = len(self.instances)

    def _expand_instances(self) -> List[ItemInstance]:
        instances: List[ItemInstance] = []
        for item in self.items:
            for _ in range(item.quantity):
                instances.append(ItemInstance(
                    item_id=item.id,
                    length=item.length,
                    width=item.width,
                    height=item.height,
                    weight=item.weight,
                    is_fragile=bool(item.is_fragile),
                    batch_number=item.batch_number or 0,
                    forbidden_horizontal_dim=item.forbidden_horizontal_dim,
                ))
        instances.sort(key=lambda x: (
            x.batch_number,
            -(x.length * x.width * x.height),
            -x.weight,
        ))
        return instances

    def _build_rotation_constraints(self):
        """Pre-compute allowed rotation indices per instance."""
        self.allowed_rotations: List[List[int]] = []
        for inst in self.instances:
            all_rots = get_all_rotations(inst.length, inst.width, inst.height)
            allowed_orientations = get_allowed_orientations(
                inst.length, inst.width, inst.height,
                inst.forbidden_horizontal_dim,
            )
            allowed_indices = []
            for (rl, rw, rh), _, _ in allowed_orientations:
                for idx, (al, aw, ah) in enumerate(all_rots):
                    if abs(al - rl) < 0.01 and abs(aw - rw) < 0.01 and abs(ah - rh) < 0.01:
                        allowed_indices.append(idx)
                        break
            self.allowed_rotations.append(allowed_indices)

    def _all_rotations_for(self, inst_idx: int) -> List[Tuple[float, float, float]]:
        """Return the 6 possible rotations for instance at index."""
        inst = self.instances[inst_idx]
        return get_all_rotations(inst.length, inst.width, inst.height)

    def _decode(self, chromosome: List[int]) -> List[Dict]:
        """Decode chromosome (rotation indices) into placement dicts."""
        packer = EPacker()
        packer.container = (self.container.length, self.container.height, self.container.width)
        packer.container_volume = self.container.length * self.container.height * self.container.width
        for inst_idx, rot_idx in enumerate(chromosome):
            allowed = self.allowed_rotations[inst_idx]
            if not allowed:
                continue
            actual_rot = allowed[rot_idx % len(allowed)]
            inst = self.instances[inst_idx]
            rot_l, rot_w, rot_h = get_all_rotations(inst.length, inst.width, inst.height)[actual_rot]

            modified = ItemInstance(
                item_id=inst.item_id,
                length=rot_l,
                width=rot_w,
                height=rot_h,
                weight=inst.weight,
                is_fragile=inst.is_fragile,
                batch_number=inst.batch_number,
                forbidden_horizontal_dim=inst.forbidden_horizontal_dim,
            )
            if not packer._try_place(modified):
                break
        return packer.placements

    def _random_chromosome(self) -> List[int]:
        """Generate a random chromosome respecting rotation constraints."""
        if self.n == 0:
            return []
        return [random.choice(self.allowed_rotations[i]) for i in range(self.n)]

    def _greedy_chromosome(self) -> List[int]:
        """Generate a greedy chromosome using EPacker."""
        packer = EPacker()
        packer.pack(self.container, self.items)
        placements = packer.placements

        chromosome: List[int] = []
        for inst_idx, inst in enumerate(self.instances):
            all_rots = get_all_rotations(inst.length, inst.width, inst.height)
            rot_l, rot_w, rot_h = inst.length, inst.width, inst.height

            for placed in placements:
                if placed["item_id"] == inst.item_id:
                    rot_l, rot_w, rot_h = placed["l"], placed["w"], placed["h"]
                    break

            rot_idx = 0
            for idx, (al, aw, ah) in enumerate(all_rots):
                if abs(al - rot_l) < 0.01 and abs(aw - rot_w) < 0.01 and abs(ah - rot_h) < 0.01:
                    rot_idx = idx
                    break

            allowed = self.allowed_rotations[inst_idx]
            if rot_idx not in allowed:
                rot_idx = allowed[0] if allowed else 0
            chromosome.append(rot_idx)

        return chromosome

    def evaluate_objectives(self, placements: List[Dict]
                            ) -> Tuple[float, float, float]:
        """Evaluate (utilization, stability, cg_balance) for a placement list."""
        if not placements:
            return 0.0, 0.0, 0.0

        report = self.verifier.verify(placements)
        container_vol = self.container.length * self.container.height * self.container.width
        placed_vol = sum(p["l"] * p["h"] * p["w"] for p in placements)
        utilization = placed_vol / container_vol if container_vol > 0 else 0.0
        stability = report.stability_score
        cg_balance = max(0.0, 1.0 - report.cg_deviation_ratio * 3)
        return utilization, stability, cg_balance

    def score_placements(self, placements: List[Dict],
                        weights: Tuple[float, float, float] = (0.5, 0.3, 0.2)
                        ) -> float:
        """Compute weighted fitness score."""
        u, s, cg = self.evaluate_objectives(placements)
        return weights[0] * u + weights[1] * s + weights[2] * cg
