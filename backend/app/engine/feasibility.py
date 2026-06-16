"""
Feasibility Verifier Module

Validates packing solutions against all constraints:
- Geometric feasibility: items within bounds, no overlaps, support conditions
- Physical feasibility: weight limits, CG safety, fragile item safety
- Orientation feasibility: forbidden_horizontal_dim constraints
- Stability scoring
"""

from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass, field
from app.models.container import ContainerConfig
from app.models.item import ItemInput
from app.engine.extreme_point import (
    SUPPORT_THRESHOLD, VERTICAL_TOLERANCE,
    check_overlap, check_support
)


@dataclass
class VerificationReport:
    """Detailed verification report for a packing solution."""
    is_feasible: bool
    geometry_ok: bool
    physics_ok: bool
    orientation_ok: bool
    stability_score: float = 0.0
    support_score: float = 0.0
    cg_deviation_ratio: float = 0.0
    fragile_violations: int = 0
    orientation_violations: int = 0
    messages: List[str] = field(default_factory=list)


class FeasibilityVerifier:
    def __init__(self, container: ContainerConfig, items: List[ItemInput]):
        self.container = container
        self.container_dims = (container.length, container.height, container.width)
        self.max_weight = container.max_weight

        # Build item lookup by ID
        self.item_specs: Dict[str, Dict] = {}
        for item in items:
            self.item_specs[item.id] = {
                "length": item.length,
                "width": item.width,
                "height": item.height,
                "weight": item.weight,
                "is_fragile": item.is_fragile or False,
                "batch_number": item.batch_number or 0,
                "forbidden_horizontal_dim": item.forbidden_horizontal_dim,
            }

    def verify(self, placements: List[Dict]) -> VerificationReport:
        """
        Full feasibility verification of a packing solution.
        placements: list of dicts with keys: item_id, x, y, z, l, h, w, weight,
                    is_fragile, orientation (optional)
        """
        report = VerificationReport(
            is_feasible=True,
            geometry_ok=True,
            physics_ok=True,
            orientation_ok=True,
        )

        if not placements:
            report.is_feasible = True
            report.messages.append("空方案，视为可行")
            return report

        # 1. Geometry checks
        geometry_ok, geom_msgs = self._verify_geometry(placements)
        report.geometry_ok = geometry_ok
        report.messages.extend(geom_msgs)

        # 2. Physics checks
        physics_ok, physics_msgs, total_weight = self._verify_physics(placements)
        report.physics_ok = physics_ok
        report.messages.extend(physics_msgs)

        # 3. Orientation checks
        orientation_ok, orient_msgs = self._verify_orientation(placements)
        report.orientation_ok = orientation_ok
        report.orientation_violations = self._count_orientation_violations(placements)
        report.messages.extend(orient_msgs)

        # 4. Stability scoring
        report.stability_score = self._calc_stability_score(placements)
        support_score, avg_support = self._calc_support_score(placements)
        report.support_score = support_score

        # 5. CG deviation
        report.cg_deviation_ratio = self._calc_cg_deviation(placements)

        # 6. Fragile violations
        report.fragile_violations = self._calc_fragile_violations(placements)

        report.is_feasible = geometry_ok and physics_ok and orientation_ok

        return report

    def _verify_geometry(self, placements: List[Dict]) -> Tuple[bool, List[str]]:
        """Check all items within bounds and no overlaps."""
        messages = []
        ok = True

        for i, p in enumerate(placements):
            x, y, z = p["x"], p["y"], p["z"]
            l, h, w = p["l"], p["h"], p["w"]
            cl, ch, cw = self.container_dims

            # Boundary check
            if x < -0.001 or y < -0.001 or z < -0.001:
                messages.append(f"[几何] 商品 {p['item_id']} 坐标为负")
                ok = False
            if x + l > cl + 0.001 or y + h > ch + 0.001 or z + w > cw + 0.001:
                messages.append(f"[几何] 商品 {p['item_id']} 超出容器边界")
                ok = False

            # Overlap check (with items placed before)
            others = [op for j, op in enumerate(placements) if j < i]
            if check_overlap(x, y, z, l, h, w, others):
                messages.append(f"[几何] 商品 {p['item_id']} 与已放置物品重叠")
                ok = False

            # Support check (if not on floor)
            if y > VERTICAL_TOLERANCE:
                _, is_supported = check_support(x, y, z, l, h, w, others)
                if not is_supported:
                    messages.append(f"[几何] 商品 {p['item_id']} 底部支撑不足 (支持率 {SUPPORT_THRESHOLD*100}% 需要)")

        return ok, messages

    def _verify_physics(self, placements: List[Dict]) -> Tuple[bool, List[str], float]:
        """Check weight limits and CG safety."""
        messages = []
        total_weight = sum(p.get("weight", 0) for p in placements)

        if total_weight > self.max_weight + 0.001:
            messages.append(f"[物理] 总重量 {total_weight:.1f}kg 超过限制 {self.max_weight}kg")
            return False, messages, total_weight

        cg_deviation = self._calc_cg_deviation(placements)
        if cg_deviation > 0.15:
            messages.append(f"[物理] 重心偏离度过大: {cg_deviation:.3f} (> 0.15)")

        return True, messages, total_weight

    def _verify_orientation(self, placements: List[Dict]) -> Tuple[bool, List[str]]:
        """Check forbidden_horizontal_dim constraints."""
        violations = self._count_orientation_violations(placements)
        ok = violations == 0
        messages = []
        for p in placements:
            item_id = p["item_id"]
            spec = self.item_specs.get(item_id)
            if not spec:
                continue
            forbidden = spec.get("forbidden_horizontal_dim")
            if not forbidden:
                continue
            orientation = p.get("orientation", "")
            if orientation == "height_vertical":
                horizontal = {"height", "width", "length"} - {"height"}
            elif orientation == "width_vertical":
                horizontal = {"height", "width", "length"} - {"width"}
            elif orientation == "length_vertical":
                horizontal = {"height", "width", "length"} - {"length"}
            else:
                continue
            if forbidden in horizontal:
                messages.append(
                    f"[朝向] 商品 {item_id} 禁止水平维度 '{forbidden}' 但实际为水平"
                )

        return ok, messages

    def _count_orientation_violations(self, placements: List[Dict]) -> int:
        """
        Count violations: if a dimension is forbidden from being horizontal,
        it must NOT appear as a horizontal dimension in the placement.

        orientation names:
          - "height_vertical": height is vertical → width and length are horizontal → ok for "forbidden_horizontal_dim=width" or "forbidden_horizontal_dim=length"
          - "width_vertical": width is vertical → height and length are horizontal → ok for "forbidden_horizontal_dim=length"
          - "length_vertical": length is vertical → height and width are horizontal → ok for none of the three
        """
        count = 0
        for p in placements:
            item_id = p["item_id"]
            spec = self.item_specs.get(item_id)
            if not spec:
                continue
            forbidden = spec.get("forbidden_horizontal_dim")
            if not forbidden:
                continue
            orientation = p.get("orientation", "")
            # Determine which dimensions are horizontal
            if orientation == "height_vertical":
                horizontal = {"height", "width", "length"} - {"height"}
            elif orientation == "width_vertical":
                horizontal = {"height", "width", "length"} - {"width"}
            elif orientation == "length_vertical":
                horizontal = {"height", "width", "length"} - {"length"}
            else:
                continue
            if forbidden in horizontal:
                count += 1
        return count

    def _calc_support_score(self, placements: List[Dict]) -> Tuple[float, float]:
        """Calculate average support ratio across all placements."""
        if not placements:
            return 1.0, 1.0

        total = 0.0
        count = 0
        for i, p in enumerate(placements):
            if p["y"] <= VERTICAL_TOLERANCE:
                total += 1.0
            else:
                others = [op for j, op in enumerate(placements) if j != i]
                ratio, _ = check_support(p["x"], p["y"], p["z"], p["l"], p["h"], p["w"], others)
                total += ratio
            count += 1

        avg = total / count if count > 0 else 1.0
        return avg, avg

    def _calc_stability_score(self, placements: List[Dict]) -> float:
        """
        Stability score formula from design spec:
        S = 0.4 * 支撑率 + 0.3 * (1 - 重心高度/容器高度) + 0.3 * (1 - (层数-1)/最大层数)
        """
        support_score, _ = self._calc_support_score(placements)

        if not placements:
            return 1.0

        cg = self._calc_center_of_gravity(placements)
        height_ratio = 0.0
        if self.container.height > 0:
            height_ratio = cg[1] / self.container.height

        layers = self._count_layers(placements)
        max_layers = self.container.height / min(
            p["h"] for p in placements
        ) if placements else 1
        layer_ratio = 1.0 - (layers - 1) / max(max_layers, 1) if max_layers > 1 else 0.0

        score = 0.4 * support_score + 0.3 * (1 - height_ratio) + 0.3 * layer_ratio
        return round(max(0.0, min(1.0, score)), 4)

    def _count_layers(self, placements: List[Dict]) -> int:
        """Count distinct vertical layers (by y coordinate)."""
        if not placements:
            return 0
        eps = VERTICAL_TOLERANCE * 2
        layer_ys = sorted(set(round(p["y"] / eps) * eps for p in placements))
        return len(layer_ys)

    def _calc_cg_deviation(self, placements: List[Dict]) -> float:
        """Calculate CG deviation ratio (0-1)."""
        if not placements:
            return 0.0

        cg = self._calc_center_of_gravity(placements)
        cx_center = self.container.length / 2
        cy_center = self.container.height / 2
        cz_center = self.container.width / 2

        offset_x = abs(cg[0] - cx_center) / (self.container.length / 2) if self.container.length > 0 else 0
        offset_y = abs(cg[1] - cy_center) / (self.container.height / 2) if self.container.height > 0 else 0
        offset_z = abs(cg[2] - cz_center) / (self.container.width / 2) if self.container.width > 0 else 0

        euclidean_dist = (offset_x ** 2 + offset_y ** 2 + offset_z ** 2) ** 0.5
        return min(1.0, euclidean_dist / (3 ** 0.5))

    def _calc_fragile_violations(self, placements: List[Dict]) -> int:
        """Count how many items are placed on top of fragile items."""
        violations = 0
        for fragile in placements:
            if not fragile.get("is_fragile"):
                continue
            fx, fy, fz = fragile["x"], fragile["y"], fragile["z"]
            fl, fh, fw = fragile["l"], fragile["h"], fragile["w"]
            f_top = fy + fh

            for p in placements:
                if p is fragile:
                    continue
                if abs(p["y"] - f_top) > VERTICAL_TOLERANCE:
                    continue
                overlap_x = max(0, min(fx + fl, p["x"] + p["l"]) - max(fx, p["x"]))
                overlap_z = max(0, min(fz + fw, p["z"] + p["w"]) - max(fz, p["z"]))
                if overlap_x * overlap_z > 0:
                    violations += 1

        return violations

    def _calc_center_of_gravity(self, placements: List[Dict]) -> Tuple[float, float, float]:
        """Calculate center of gravity of all placed items."""
        if not placements:
            return (0.0, 0.0, 0.0)
        total_w = sum(p.get("weight", 0) for p in placements)
        if total_w <= 0:
            return (0.0, 0.0, 0.0)

        cx = sum(p["weight"] * (p["x"] + p["l"] / 2) for p in placements) / total_w
        cy = sum(p["weight"] * (p["y"] + p["h"] / 2) for p in placements) / total_w
        cz = sum(p["weight"] * (p["z"] + p["w"] / 2) for p in placements) / total_w
        return (cx, cy, cz)
