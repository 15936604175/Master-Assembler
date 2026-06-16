import time
from typing import List, Dict, Tuple, Optional
from app.models.container import ContainerConfig
from app.models.item import ItemInput, ItemInstance
from app.models.solution import (
    OptimizeResponse, Placement, UnplacedItem, CGPoint, Stats, SolutionMetrics
)
from app.engine.rotation import get_allowed_orientations, get_orientation_for_rotation
from app.engine.extreme_point import (
    generate_new_eps, is_valid_ep, evaluate_placement,
    check_overlap, check_support, check_cg_stability
)
from app.engine.space_cutter import Space, cut_space, remove_degenerate_spaces


class EPacker:
    def __init__(self):
        self.placements: List[Dict] = []
        self.extreme_points: List[tuple] = [(0.0, 0.0, 0.0)]
        self.remaining_spaces: List[Space] = []
        self.placed_weight: float = 0.0
        self.placed_volume: float = 0.0
        self.container: Tuple[float, float, float] = (0, 0, 0)

    def pack(self, container: ContainerConfig, items: List[ItemInput]) -> OptimizeResponse:
        start_time = time.time()
        self.container = (container.length, container.height, container.width)
        container_volume = container.length * container.height * container.width
        self.placed_weight = 0.0
        self.placed_volume = 0.0
        self.placements = []
        self.extreme_points = [(0.0, 0.0, 0.0)]
        self.remaining_spaces = [
            Space(0, 0, 0, container.length, container.height, container.width)
        ]

        max_weight = container.max_weight
        instances: List[ItemInstance] = []

        for item in items:
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

        instances.sort(
            key=lambda x: (
                x.batch_number,
                -(x.length * x.width * x.height),
                -x.weight,
            )
        )

        unplaced_map: Dict[str, int] = {}
        unplaced_reasons: Dict[str, str] = {}
        for inst in instances:
            if self.placed_weight + inst.weight > max_weight:
                unplaced_map[inst.item_id] = unplaced_map.get(inst.item_id, 0) + 1
                unplaced_reasons[inst.item_id] = "超过最大载重"
                continue

            placed = self._try_place(inst)
            if not placed:
                unplaced_map[inst.item_id] = unplaced_map.get(inst.item_id, 0) + 1
                if inst.item_id not in unplaced_reasons:
                    unplaced_reasons[inst.item_id] = "空间不足或无法满足支撑条件"

        elapsed = (time.time() - start_time) * 1000

        placements_out = [
            Placement(
                item_id=p["item_id"],
                x=round(p["x"], 2),
                y=round(p["y"], 2),
                z=round(p["z"], 2),
                length=round(p["l"], 2),
                width=round(p["w"], 2),
                height=round(p["h"], 2),
                rotation=p["rotation"],
                orientation=p.get("orientation"),
                is_fragile=p.get("is_fragile", False),
            )
            for p in self.placements
        ]

        unplaced_out = [
            UnplacedItem(
                item_id=uid,
                quantity=qty,
                reason=unplaced_reasons.get(uid, "空间不足"),
            )
            for uid, qty in unplaced_map.items()
        ]

        cg = self._calc_center_of_gravity()
        total_placed = len(self.placements)
        total_unplaced = sum(unplaced_map.values())

        volume_util = self.placed_volume / container_volume if container_volume > 0 else 0.0
        weight_util = self.placed_weight / max_weight if max_weight > 0 else 0.0

        avg_support = self._calc_avg_support()
        fragile_violations = self._calc_fragile_violations()

        metrics = SolutionMetrics(
            avg_support_ratio=round(avg_support, 4),
            cg_offset_x=round(abs(cg[0] - container.length / 2), 2),
            cg_offset_z=round(abs(cg[2] - container.width / 2), 2),
            fragile_violations=fragile_violations,
        )

        cg_deviation = self._calc_cg_deviation_ratio(cg, container)

        return OptimizeResponse(
            success=True,
            container_utilization=round(volume_util, 4),
            weight_utilization=round(weight_util, 4),
            total_weight=round(self.placed_weight, 2),
            placements=placements_out,
            unplaced_items=unplaced_out,
            center_of_gravity=CGPoint(
                x=round(cg[0], 2),
                y=round(cg[1], 2),
                z=round(cg[2], 2),
            ),
            stats=Stats(
                total_items_placed=total_placed,
                total_items_unplaced=total_unplaced,
                algorithm_time_ms=round(elapsed, 2),
            ),
            metrics=metrics,
            cg_deviation_ratio=round(cg_deviation, 4),
        )

    def _try_place(self, item: ItemInstance) -> bool:
        best_score = -float("inf")
        best_placement: Optional[Tuple[float, float, float, float, float, float]] = None
        best_rot = ""
        best_orientation = ""
        best_metrics: Dict = {}

        allowed_orientations = get_allowed_orientations(
            item.length, item.width, item.height,
            item.forbidden_horizontal_dim,
        )

        for (rot_l, rot_w, rot_h), rot_label, orientation_name in allowed_orientations:
            item_size = (rot_l, rot_h, rot_w)
            for ep in self.extreme_points:
                if not is_valid_ep(ep, item_size, self.container):
                    continue
                ex, ey, ez = ep
                if check_overlap(ex, ey, ez, rot_l, rot_h, rot_w, self.placements):
                    continue
                _, is_supported = check_support(
                    ex, ey, ez, rot_l, rot_h, rot_w, self.placements
                )
                if not is_supported:
                    continue
                _, is_cg_ok = check_cg_stability(
                    ex, ey, ez, rot_l, rot_h, rot_w, item.weight,
                    self.placements, self.container
                )
                max_cg_weight = self.container[0] * 0.1
                if not is_cg_ok and len(self.placements) > 5 and self.placed_weight > max_cg_weight:
                    continue

                score, metrics = evaluate_placement(
                    ep, item_size, self.container, self.placements,
                    weight=item.weight, is_fragile=item.is_fragile
                )
                if score > best_score:
                    best_score = score
                    best_placement = (ex, ey, ez, rot_l, rot_h, rot_w)
                    best_rot = rot_label
                    best_orientation = orientation_name
                    best_metrics = metrics

        if best_placement is None:
            return False

        x, y, z, l, h, w = best_placement

        self.placements.append({
            "item_id": item.item_id,
            "x": x, "y": y, "z": z,
            "l": l, "h": h, "w": w,
            "weight": item.weight,
            "is_fragile": item.is_fragile,
            "rotation": best_rot,
            "orientation": best_orientation,
        })
        self.placed_weight += item.weight
        self.placed_volume += l * h * w

        new_eps = generate_new_eps(x, y, z, l, h, w)
        seen = set()
        unique_eps = []
        for ep in self.extreme_points:
            key = (round(ep[0], 2), round(ep[1], 2), round(ep[2], 2))
            if key not in seen:
                seen.add(key)
                unique_eps.append(ep)
        for nep in new_eps:
            key = (round(nep[0], 2), round(nep[1], 2), round(nep[2], 2))
            if key not in seen:
                seen.add(key)
                unique_eps.append(nep)
        self.extreme_points = unique_eps

        item_box = (x, y, z, l, h, w)
        new_spaces = []
        for space in self.remaining_spaces:
            new_spaces.extend(cut_space(space, item_box))
        self.remaining_spaces = remove_degenerate_spaces(new_spaces, min_size=10.0)

        return True

    def _calc_center_of_gravity(self) -> Tuple[float, float, float]:
        if not self.placements:
            return (0.0, 0.0, 0.0)
        total_w = sum(p["weight"] for p in self.placements)
        if total_w == 0:
            return (0.0, 0.0, 0.0)
        cx = sum(p["weight"] * (p["x"] + p["l"] / 2) for p in self.placements) / total_w
        cy = sum(p["weight"] * (p["y"] + p["h"] / 2) for p in self.placements) / total_w
        cz = sum(p["weight"] * (p["z"] + p["w"] / 2) for p in self.placements) / total_w
        return (cx, cy, cz)

    def _calc_avg_support(self) -> float:
        if not self.placements:
            return 1.0
        total = 0.0
        count = 0
        for i, p in enumerate(self.placements):
            others = [op for j, op in enumerate(self.placements) if j != i]
            ratio, _ = check_support(
                p["x"], p["y"], p["z"], p["l"], p["h"], p["w"], others
            )
            total += ratio
            count += 1
        return total / count if count > 0 else 1.0

    def _calc_fragile_violations(self) -> int:
        from app.engine.extreme_point import VERTICAL_TOLERANCE
        violations = 0
        for fragile in self.placements:
            if not fragile.get("is_fragile"):
                continue
            fx, fy, fz = fragile["x"], fragile["y"], fragile["z"]
            fl, fh, fw = fragile["l"], fragile["h"], fragile["w"]
            f_top = fy + fh
            for p in self.placements:
                if p is fragile:
                    continue
                if abs(p["y"] - f_top) > VERTICAL_TOLERANCE:
                    continue
                overlap_x = max(0, min(fx + fl, p["x"] + p["l"]) - max(fx, p["x"]))
                overlap_z = max(0, min(fz + fw, p["z"] + p["w"]) - max(fz, p["z"]))
                if overlap_x * overlap_z > 0:
                    violations += 1
        return violations

    def _calc_cg_deviation_ratio(self, cg: Tuple[float, float, float],
                                  container: ContainerConfig) -> float:
        """Calculate CG deviation as ratio (0-1), 0=perfect center, 1=max deviation."""
        if not self.placements:
            return 0.0
        cx_center = container.length / 2
        cz_center = container.width / 2
        cy_center = container.height / 2

        offset_x = abs(cg[0] - cx_center) / (container.length / 2) if container.length > 0 else 0
        offset_y = abs(cg[1] - cy_center) / (container.height / 2) if container.height > 0 else 0
        offset_z = abs(cg[2] - cz_center) / (container.width / 2) if container.width > 0 else 0

        euclidean_dist = (offset_x ** 2 + offset_y ** 2 + offset_z ** 2) ** 0.5
        return min(1.0, euclidean_dist / (3 ** 0.5))
