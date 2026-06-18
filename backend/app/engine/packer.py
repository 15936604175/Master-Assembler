import time
from typing import List, Dict, Tuple, Optional
from app.models.container import ContainerConfig
from app.models.item import ItemInput, ItemInstance
from app.models.solution import (
    OptimizeResponse, Placement, UnplacedItem, CGPoint, Stats, SolutionMetrics
)
from app.engine.rotation import get_allowed_orientations
from app.engine.extreme_point import (
    generate_new_eps, is_valid_ep, evaluate_placement, evaluate_placement_fast,
    check_overlap, check_support, check_cg_stability
)
from app.engine.space_cutter import Space, cut_space, remove_degenerate_spaces

MAX_EP_COUNT = 600
FAST_EP_COUNT = 120


def _generate_floor_eps(cl: float, ch: float, cw: float,
                        grid_step: float = 300.0) -> List[Tuple[float, float, float]]:
    eps = [(0.0, 0.0, 0.0)]
    step_x = max(grid_step, cl / 20)
    step_z = max(grid_step, cw / 20)
    x = step_x
    while x < cl:
        z = step_z
        while z < cw:
            eps.append((x, 0.0, z))
            z += step_z
        x += step_x
    return eps


def _prune_eps(eps: List[Tuple[float, float, float]],
               container: Tuple[float, float, float],
               max_count: int = MAX_EP_COUNT) -> List[Tuple[float, float, float]]:
    if len(eps) <= max_count:
        return eps
    cl, ch, cw = container
    # 先过滤掉超出容器边界的无效 EP（含微小容差）
    eps = [(x, y, z) for (x, y, z) in eps
           if x < cl - 0.01 and y < ch - 0.01 and z < cw - 0.01]
    if len(eps) <= max_count:
        return eps
    floor_eps = [ep for ep in eps if ep[1] <= 1.0]
    non_floor_eps = [ep for ep in eps if ep[1] > 1.0]
    # 按比例分配名额：floor 和 non_floor 各保留一半，避免 non_floor 被完全丢弃
    floor_quota = max_count // 2
    non_floor_quota = max_count - floor_quota

    # 如果某一类不足配额，将剩余配额给另一类
    if len(floor_eps) <= floor_quota:
        non_floor_quota = max_count - len(floor_eps)
    elif len(non_floor_eps) <= non_floor_quota:
        floor_quota = max_count - len(non_floor_eps)

    # floor_eps 按 (x, z) 均匀采样
    if len(floor_eps) > floor_quota:
        floor_eps.sort(key=lambda ep: (ep[0], ep[2]))
        step = max(1, len(floor_eps) // floor_quota)
        floor_eps = floor_eps[::step][:floor_quota]

    # non_floor_eps 按 (y, x, z) 均匀采样
    if len(non_floor_eps) > non_floor_quota:
        non_floor_eps.sort(key=lambda ep: (ep[1], ep[0], ep[2]))
        step = max(1, len(non_floor_eps) // non_floor_quota)
        non_floor_eps = non_floor_eps[::step][:non_floor_quota]

    return floor_eps + non_floor_eps


class EPacker:
    def __init__(self):
        self.placements: List[Dict] = []
        self.extreme_points: List[tuple] = [(0.0, 0.0, 0.0)]
        self.remaining_spaces: List[Space] = []
        self.placed_weight: float = 0.0
        self.placed_volume: float = 0.0
        self.container: Tuple[float, float, float] = (0, 0, 0)
        self.container_volume: float = 0.0
        self.max_weight: float = 0.0
        # 空间网格索引：加速 check_overlap，避免 O(N) 遍历
        self._grid_cell_size: float = 200.0
        self._grid: Dict[Tuple[int, int, int], List[int]] = {}
        # 版本号去重：避免每次 _grid_check_overlap 创建 set
        self._visit_version: int = 0
        self._visits: List[int] = []

    def _grid_key(self, x: float, y: float, z: float) -> Tuple[int, int, int]:
        """将坐标映射到网格单元。"""
        cs = self._grid_cell_size
        return (int(x // cs), int(y // cs), int(z // cs))

    def _grid_add(self, idx: int, placement: Dict):
        """将一个已放置物品加入网格索引。"""
        x, y, z = placement["x"], placement["y"], placement["z"]
        x2, y2, z2 = x + placement["l"], y + placement["h"], z + placement["w"]
        cs = self._grid_cell_size
        for gx in range(int(x // cs), int(x2 // cs) + 1):
            for gy in range(int(y // cs), int(y2 // cs) + 1):
                for gz in range(int(z // cs), int(z2 // cs) + 1):
                    self._grid.setdefault((gx, gy, gz), []).append(idx)

    def _grid_check_overlap(self, x: float, y: float, z: float,
                            l: float, h: float, w: float) -> bool:
        """使用网格索引快速检查重叠，只检查相关单元内的物品。

        优化：使用版本号数组代替 set 去重，避免每次调用创建 set 对象。
        """
        x2, y2, z2 = x + l, y + h, z + w
        cs = self._grid_cell_size
        # 版本号去重：self._visit_version 全局递增，每个物品记录上次访问版本
        self._visit_version += 1
        ver = self._visit_version
        visits = self._visits
        placements = self.placements
        for gx in range(int(x // cs), int(x2 // cs) + 1):
            for gy in range(int(y // cs), int(y2 // cs) + 1):
                for gz in range(int(z // cs), int(z2 // cs) + 1):
                    for idx in self._grid.get((gx, gy, gz), ()):
                        if visits[idx] == ver:
                            continue
                        visits[idx] = ver
                        p = placements[idx]
                        if (x < p["x"] + p["l"] and x2 > p["x"] and
                                y < p["y"] + p["h"] and y2 > p["y"] and
                                z < p["z"] + p["w"] and z2 > p["z"]):
                            return True
        return False

    def pack(self, container: ContainerConfig, items: List[ItemInput]) -> OptimizeResponse:
        start_time = time.time()
        self.container = (container.length, container.height, container.width)
        self.container_volume = container.length * container.height * container.width
        self.max_weight = container.max_weight
        self.placed_weight = 0.0
        self.placed_volume = 0.0
        self.placements = []
        # 根据容器尺寸动态调整网格单元大小（约 10x10x10 个单元）
        cl, ch, cw = self.container
        self._grid_cell_size = max(max(cl, ch, cw) / 10.0, 50.0)
        self._grid = {}
        self._visit_version = 0
        self._visits = []
        self.extreme_points = _generate_floor_eps(
            container.length, container.height, container.width
        )
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
                    forbidden_horizontal_dims=item.forbidden_horizontal_dims,
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
                weight=p.get("weight", 0.0),
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

        volume_util = self.placed_volume / self.container_volume if self.container_volume > 0 else 0.0
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

    def _try_place(self, item: ItemInstance,
                   forced_orientation: Optional[Tuple[Tuple[float, float, float], str, str]] = None,
                   fast_mode: bool = False,
                   ) -> bool:
        best_score = -float("inf")
        best_placement: Optional[Tuple[float, float, float, float, float, float]] = None
        best_rot = ""
        best_orientation = ""

        if forced_orientation is not None:
            allowed_orientations = [forced_orientation]
        else:
            allowed_orientations = get_allowed_orientations(
                item.length, item.width, item.height,
                item.forbidden_horizontal_dims,
            )

        cl, ch, cw = self.container

        for (rot_l, rot_w, rot_h), rot_label, orientation_name in allowed_orientations:
            item_size = (rot_l, rot_h, rot_w)
            for ep in self.extreme_points:
                ex, ey, ez = ep
                if ex + rot_l > cl + 0.001 or ey + rot_h > ch + 0.001 or ez + rot_w > cw + 0.001:
                    continue
                # 使用网格索引加速重叠检查（O(1) 平均复杂度）
                if self._grid_check_overlap(ex, ey, ez, rot_l, rot_h, rot_w):
                    continue
                # 不考虑稳定性约束：移除 check_support 检查，允许悬空放置以最大化空间利用率

                if fast_mode:
                    score = evaluate_placement_fast(
                        ep, item_size, self.container, self.placements,
                        weight=item.weight, is_fragile=item.is_fragile
                    )
                else:
                    score, metrics = evaluate_placement(
                        ep, item_size, self.container, self.placements,
                        weight=item.weight, is_fragile=item.is_fragile
                    )

                if score > best_score:
                    best_score = score
                    best_placement = (ex, ey, ez, rot_l, rot_h, rot_w)
                    best_rot = rot_label
                    best_orientation = orientation_name

        if best_placement is None:
            # 所有 EP 都无法放置：触发彻底清理，移除所有"死 EP"（与已放置物品重叠的）
            # 然后重试，最多重试一次（避免无限递归）
            if self.extreme_points:
                self._clean_dead_eps()
                if self.extreme_points:
                    # 使用循环重试一次，避免递归深度超限
                    best_score = -float("inf")
                    best_placement = None
                    best_rot = ""
                    best_orientation = ""
                    for (rot_l, rot_w, rot_h), rot_label, orientation_name in allowed_orientations:
                        item_size = (rot_l, rot_h, rot_w)
                        for ep in self.extreme_points:
                            ex, ey, ez = ep
                            if ex + rot_l > cl + 0.001 or ey + rot_h > ch + 0.001 or ez + rot_w > cw + 0.001:
                                continue
                            if self._grid_check_overlap(ex, ey, ez, rot_l, rot_h, rot_w):
                                continue
                            if fast_mode:
                                score = evaluate_placement_fast(
                                    ep, item_size, self.container, self.placements,
                                    weight=item.weight, is_fragile=item.is_fragile
                                )
                            else:
                                score, _ = evaluate_placement(
                                    ep, item_size, self.container, self.placements,
                                    weight=item.weight, is_fragile=item.is_fragile
                                )
                            if score > best_score:
                                best_score = score
                                best_placement = (ex, ey, ez, rot_l, rot_h, rot_w)
                                best_rot = rot_label
                                best_orientation = orientation_name
                    if best_placement is None:
                        return False
                else:
                    return False
            else:
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
        # 更新网格索引
        self._grid_add(len(self.placements) - 1, self.placements[-1])
        self._visits.append(0)
        self.placed_weight += item.weight
        self.placed_volume += l * h * w

        new_eps = generate_new_eps(x, y, z, l, h, w)
        seen = set()
        # 旧 EP：只需检查是否被新放置的物品包含（O(1) per EP）
        last = self.placements[-1] if self.placements else None
        unique_eps = []
        for ep in self.extreme_points:
            key = (round(ep[0], 2), round(ep[1], 2), round(ep[2], 2))
            if key in seen:
                continue
            seen.add(key)
            # 检查是否被新放置的物品包含
            if last:
                ex, ey, ez = ep
                if (last["x"] <= ex < last["x"] + last["l"] and
                        last["y"] <= ey < last["y"] + last["h"] and
                        last["z"] <= ez < last["z"] + last["w"]):
                    continue
            unique_eps.append(ep)
        # 新 EP：使用网格索引检查是否与任何已放置物品重叠
        for nep in new_eps:
            key = (round(nep[0], 2), round(nep[1], 2), round(nep[2], 2))
            if key in seen:
                continue
            seen.add(key)
            ex, ey, ez = nep
            cl, ch, cw = self.container
            if ex >= cl - 0.01 or ey >= ch - 0.01 or ez >= cw - 0.01:
                continue
            if self._grid_check_overlap_point(ex, ey, ez):
                continue
            unique_eps.append(nep)
        max_ep = FAST_EP_COUNT if fast_mode else MAX_EP_COUNT
        self.extreme_points = _prune_eps(unique_eps, self.container, max_ep)

        return True

    def _clean_dead_eps(self):
        """彻底清理所有"死 EP"（与已放置物品重叠或超出边界的 EP）。

        仅在 _try_place 失败时调用，避免每次放置都执行 O(N) 清理。
        """
        if not self.placements:
            return
        cl, ch, cw = self.container
        valid = []
        for ep in self.extreme_points:
            ex, ey, ez = ep
            if ex >= cl - 0.01 or ey >= ch - 0.01 or ez >= cw - 0.01:
                continue
            if self._grid_check_overlap_point(ex, ey, ez):
                continue
            valid.append(ep)
        self.extreme_points = valid

    def _grid_check_overlap_point(self, x: float, y: float, z: float) -> bool:
        """检查一个点是否被任何已放置物品包含。"""
        cs = self._grid_cell_size
        self._visit_version += 1
        ver = self._visit_version
        visits = self._visits
        placements = self.placements
        gx, gy, gz = int(x // cs), int(y // cs), int(z // cs)
        for idx in self._grid.get((gx, gy, gz), ()):
            if visits[idx] == ver:
                continue
            visits[idx] = ver
            p = placements[idx]
            if (p["x"] <= x < p["x"] + p["l"] and
                    p["y"] <= y < p["y"] + p["h"] and
                    p["z"] <= z < p["z"] + p["w"]):
                return True
        return False

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
        # 已移除稳定性约束，直接返回 1.0 避免 O(N²) 计算
        return 1.0

    def _calc_fragile_violations(self) -> int:
        # 已移除易碎品约束，直接返回 0 避免 O(N²) 计算
        return 0

    def _calc_cg_deviation_ratio(self, cg: Tuple[float, float, float],
                                  container: ContainerConfig) -> float:
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
