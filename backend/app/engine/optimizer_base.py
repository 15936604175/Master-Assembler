"""
Shared base class for container loading optimizers.

Eliminates code duplication between GeneticOptimizer, LocalSearchOptimizer,
and NSGAOptimizer by providing common methods:
- _expand_instances: expand ItemInput into ItemInstance list
- _build_rotation_constraints: pre-compute allowed rotations per instance
- _decode: decode chromosome (instance permutation) to placement dicts
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
from app.engine.space_cutter import Space


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
                    forbidden_horizontal_dims=item.forbidden_horizontal_dims,
                ))
        instances.sort(key=lambda x: (
            x.batch_number,
            -(x.length * x.width * x.height),
            -x.weight,
        ))
        return instances

    def _build_rotation_constraints(self):
        """Pre-compute allowed rotation indices per instance.

        Each orientation (e.g. height_vertical) maps to 2 rotations in all_rots
        (swapping the two horizontal dimensions). We include both so the optimizer
        can explore the full search space.
        """
        self.allowed_rotations: List[List[int]] = []
        for inst in self.instances:
            all_rots = get_all_rotations(inst.length, inst.width, inst.height)
            allowed_orientations = get_allowed_orientations(
                inst.length, inst.width, inst.height,
                inst.forbidden_horizontal_dims,
            )
            allowed_indices = []
            for (rl, rw, rh), _, _ in allowed_orientations:
                for idx, (al, aw, ah) in enumerate(all_rots):
                    if (abs(ah - rh) < 0.01 and
                        ((abs(al - rl) < 0.01 and abs(aw - rw) < 0.01) or
                         (abs(al - rw) < 0.01 and abs(aw - rl) < 0.01))):
                        if idx not in allowed_indices:
                            allowed_indices.append(idx)
            self.allowed_rotations.append(allowed_indices)

    def _all_rotations_for(self, inst_idx: int) -> List[Tuple[float, float, float]]:
        """Return the 6 possible rotations for instance at index."""
        inst = self.instances[inst_idx]
        return get_all_rotations(inst.length, inst.width, inst.height)

    def _init_packer(self) -> EPacker:
        """Create a fully-initialized EPacker for decoding (no items placed yet)."""
        from app.engine.packer import _generate_floor_eps, FAST_EP_COUNT
        packer = EPacker()
        packer.container = (self.container.length, self.container.height, self.container.width)
        packer.container_volume = self.container.length * self.container.height * self.container.width
        packer.max_weight = self.container.max_weight
        packer.placements = []
        packer.extreme_points = _generate_floor_eps(
            self.container.length, self.container.height, self.container.width,
            grid_step=max(300.0, self.container.length / 10)
        )[:FAST_EP_COUNT]
        packer.remaining_spaces = [
            Space(0, 0, 0, self.container.length, self.container.height, self.container.width)
        ]
        packer.placed_weight = 0.0
        packer.placed_volume = 0.0
        return packer

    def _decode(self, chromosome: List[int]) -> Tuple[List[Dict], List[ItemInstance]]:
        """Decode chromosome (instance index permutation) into placement dicts.

        Each gene is an index into self.instances. Items are placed in the order
        given by the chromosome; rotation is chosen automatically by the packer's
        evaluate_placement. Items that cannot be placed are collected and returned.

        Returns (placements, unplaced_instances).
        """
        packer = self._init_packer()
        unplaced: List[ItemInstance] = []

        for inst_idx in chromosome:
            if inst_idx < 0 or inst_idx >= self.n:
                continue
            inst = self.instances[inst_idx]
            if packer.placed_weight + inst.weight > self.container.max_weight:
                unplaced.append(inst)
                continue
            if not packer._try_place(inst, fast_mode=True):
                unplaced.append(inst)
                continue

        return packer.placements, unplaced

    def _random_chromosome(self) -> List[int]:
        """Generate a random permutation chromosome (instance indices)."""
        if self.n == 0:
            return []
        order = list(range(self.n))
        random.shuffle(order)
        return order

    def _greedy_chromosome(self) -> List[int]:
        """Generate a greedy chromosome using EPacker.

        Returns a permutation of instance indices following the greedy placement
        order. Placed items come first (in placement order), unplaced items are
        appended at the end.
        """
        packer = EPacker()
        packer.pack(self.container, self.items)
        placements = packer.placements

        available: Dict[str, List[int]] = {}
        for i, inst in enumerate(self.instances):
            available.setdefault(inst.item_id, []).append(i)

        order: List[int] = []
        used: set = set()
        for p in placements:
            iid = p["item_id"]
            if iid in available and available[iid]:
                idx = available[iid].pop(0)
                order.append(idx)
                used.add(idx)

        for i in range(self.n):
            if i not in used:
                order.append(i)

        return order

    def _fast_greedy_chromosome(self) -> List[int]:
        """Generate a greedy chromosome quickly without running full packer.

        Simply returns the default sorted order (large items first).
        """
        return list(range(self.n))

    def evaluate_objectives(self, placements: List[Dict]
                            ) -> Tuple[float, float, float]:
        """Evaluate (utilization, stability, cg_balance) for a placement list."""
        if not placements:
            return 0.0, 0.0, 0.0

        container_vol = self.container.length * self.container.height * self.container.width
        placed_vol = sum(p["l"] * p["h"] * p["w"] for p in placements)
        utilization = placed_vol / container_vol if container_vol > 0 else 0.0

        total_w = sum(p.get("weight", 0) for p in placements)
        if total_w > 0:
            cg_x = sum(p.get("weight", 0) * (p["x"] + p["l"] / 2) for p in placements) / total_w
            cg_y = sum(p.get("weight", 0) * (p["y"] + p["h"] / 2) for p in placements) / total_w
            cg_z = sum(p.get("weight", 0) * (p["z"] + p["w"] / 2) for p in placements) / total_w
        else:
            total_vol = sum(p["l"] * p["h"] * p["w"] for p in placements)
            if total_vol > 0:
                cg_x = sum((p["x"] + p["l"] / 2) * p["l"] * p["h"] * p["w"] for p in placements) / total_vol
                cg_y = sum((p["y"] + p["h"] / 2) * p["l"] * p["h"] * p["w"] for p in placements) / total_vol
                cg_z = sum((p["z"] + p["w"] / 2) * p["l"] * p["h"] * p["w"] for p in placements) / total_vol
            else:
                cg_x = cg_y = cg_z = 0.0

        offset_x = abs(cg_x - self.container.length / 2) / (self.container.length / 2) if self.container.length > 0 else 0
        offset_y = abs(cg_y - self.container.height / 2) / (self.container.height / 2) if self.container.height > 0 else 0
        offset_z = abs(cg_z - self.container.width / 2) / (self.container.width / 2) if self.container.width > 0 else 0
        cg_deviation = min(1.0, (offset_x ** 2 + offset_y ** 2 + offset_z ** 2) ** 0.5 / (3 ** 0.5))
        cg_balance = max(0.0, 1.0 - cg_deviation * 3)

        stability = max(0.0, min(1.0, 0.7 * cg_balance + 0.3 * utilization))

        return utilization, stability, cg_balance

    def score_placements(self, placements: List[Dict],
                        weights: Tuple[float, float, float] = (0.6, 0.1, 0.3)
                        ) -> float:
        """Compute weighted fitness score: utilization + stability + CG balance."""
        u, s, cg = self.evaluate_objectives(placements)
        return weights[0] * u + weights[1] * s + weights[2] * cg
