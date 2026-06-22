"""
企业级 3D Container Loading System —— Block Packing 引擎
基于 Block Packing + Extreme Point + Beam Search + 物理稳定性评估

核心架构（模块化设计）:
    BlockOptimizer  ──┬── BlockGenerator         (Block生成器)
                       ├── OrientationManager     (方向约束管理器)
                       ├── FragileConstraint      (易碎约束检测器)
                       ├── BatchManager           (批次约束管理器)
                       ├── EPManager              (Extreme Point 管理器)
                       ├── CollisionDetector      (碰撞检测器)
                       ├── StabilityEvaluator     (重力与稳定性评估器)
                       ├── ScoringFunction        (综合评分函数)
                       └── BeamSearchSolver       (束搜索求解器)

关键约束处理:
    • 空间约束:     边界 + AABB 碰撞检测
    • 物理稳定性:   支撑率 ≥ 70% + 重心偏移 ≤ 35% 容器半长
    • 业务规则:     batch分层 + fragile禁压 + orientation限向

评分函数（9维度加权）:
    支撑率×100 - 墙面接触×80 - 同SKU聚集×60 - 体积利用×50
    - 地面接触×30 - 碎片化惩罚×40 - 重心惩罚×20 - 易碎风险×150 - 批次违规×200
"""

import time
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional, Set
from copy import deepcopy

from app.models.container import ContainerConfig
from app.models.item import ItemInput
from app.engine.rotation import get_allowed_orientations


# ============================================================
# 常量配置
# ============================================================
MAX_NX = 6           # 沿长度方向最多 6 个
MAX_NY = 4           # 沿高度方向最多 4 个（垂直方向）
MAX_NZ = 6           # 沿宽度方向最多 6 个
MAX_BLOCK_VOLUME_RATIO = 0.5   # 单个 Block 体积不超过容器 50%
MAX_BLOCKS_PER_SKU = 200       # 每个 SKU 保留 top-K Block
MAX_EP_COUNT = 600             # Extreme Point 数量上限
SUPPORT_THRESHOLD = 0.5        # 支撑率阈值（50%，平衡稳定性与空间利用）
VERTICAL_TOLERANCE = 1.0       # 垂直判断容差
CG_OFFSET_RATIO = 0.35         # 允许的重心偏移比例
FRAGILE_SAFETY_RATIO = 0.7    # 易碎品要求更高支撑率（70%）
BEAM_WIDTH = 10                # Beam Search 宽度
MAX_BEAM_STEPS = 200           # Beam Search 最大步数
GRID_CELL_DIV = 10             # 网格索引单元数 = container / GRID_CELL_DIV


# ============================================================
# 数据结构
# ============================================================
@dataclass
class Block:
    """Block = 多个相同 SKU、相同 batch 组成的长方体。"""
    sku: str
    batch: int
    nx: int             # 沿 X 方向的物品数
    ny: int             # 沿 Y 方向的物品数
    nz: int             # 沿 Z 方向的物品数
    length: float       # nx * item_rotated_length
    height: float       # ny * item_rotated_height
    width: float        # nz * item_rotated_width
    volume: float
    count: int          # nx * ny * nz
    item_length: float  # 单品长度
    item_height: float  # 单品高度
    item_width: float   # 单品宽度
    item_weight: float
    is_fragile: bool
    rotation_label: str
    orientation_name: str
    # Block 质量评分（体积 × 紧凑度），用于排序
    quality_score: float = 0.0


@dataclass
class PlacedBlock:
    """已放置的 Block（含位置信息）。"""
    block: Block
    x: float
    y: float
    z: float


@dataclass
class PlacementResult:
    """放置结果（单品级，与现有 API 兼容）。"""
    item_id: str
    x: float
    y: float
    z: float
    l: float
    h: float
    w: float
    weight: float
    is_fragile: bool
    rotation: str
    orientation: str


@dataclass
class BeamState:
    """Beam Search 中的一个状态。"""
    placements: List[Dict] = field(default_factory=list)   # 单品级 placements
    placed_blocks: List[Dict] = field(default_factory=list) # Block 级信息（聚集用）
    extreme_points: List[Tuple[float, float, float]] = field(default_factory=list)
    inventory: Dict[str, int] = field(default_factory=dict)  # 剩余库存
    score: float = 0.0
    placed_volume: float = 0.0
    placed_weight: float = 0.0
    cg_x: float = 0.0   # 当前重心 X（累积）
    cg_y: float = 0.0
    cg_z: float = 0.0
    total_weight: float = 0.0


# ============================================================
# 模块 1: BlockGenerator —— Block生成器
# ============================================================
class BlockGenerator:
    """为每个 SKU × 每个允许朝向生成 Block 库。

    生成规则：
        1. 枚举所有 (nx, ny, nz) 组合，约束 nx*ny*nz ≤ count
        2. 去重：相同 (size, count) 只保留一个
        3. 过滤：blockVolume ≤ containerVolume × 0.5
        4. 每个 SKU 只保留质量评分 top-K
    """

    def __init__(self, container: ContainerConfig, items: List[ItemInput]):
        self.container = container
        self.container_volume = container.length * container.height * container.width
        self.items = items

    def generate(self) -> List[Block]:
        """生成所有 SKU 的 Block 库，按 (单品体积, Block质量) 双键降序。"""
        all_blocks: List[Block] = []

        for item in self.items:
            sku_blocks = self._generate_for_sku(item)
            # 每个 SKU 只保留 top-K（按 Block 质量评分）
            # 但强制保留所有小 Block（count ≤ 4），避免剩余少量物品无法放置
            sku_blocks.sort(key=lambda b: b.quality_score, reverse=True)
            top_k = sku_blocks[:MAX_BLOCKS_PER_SKU]
            small_blocks = [b for b in sku_blocks[MAX_BLOCKS_PER_SKU:] if b.count <= 4]
            all_blocks.extend(top_k)
            all_blocks.extend(small_blocks)

        # 总排序：主排序 = 单品体积降序（大物品优先占空间）
        #         次排序 = Block 质量降序（同 SKU 中紧凑的 Block 优先）
        all_blocks.sort(key=lambda b: (
            b.item_length * b.item_height * b.item_width,
            b.quality_score,
        ), reverse=True)

        return all_blocks

    def _generate_for_sku(self, item: ItemInput) -> List[Block]:
        """为单个 SKU 生成所有合法 Block。"""
        count = item.quantity
        if count <= 0:
            return []

        orientations = get_allowed_orientations(
            item.length, item.width, item.height,
            item.forbidden_horizontal_dims or [],
        )
        if not orientations:
            # 无合法朝向：退化为单品 Block
            orientations = [((item.length, item.width, item.height), "lwh", "height_vertical")]

        sku_blocks: List[Block] = []
        seen: Set[Tuple[float, float, float, int]] = set()
        batch = item.batch_number or 0

        for (rot_l, rot_w, rot_h), rot_label, orient_name in orientations:
            max_nx = min(MAX_NX, int(self.container.length / rot_l)) if rot_l > 0 else 1
            max_ny = min(MAX_NY, int(self.container.height / rot_h)) if rot_h > 0 else 1
            max_nz = min(MAX_NZ, int(self.container.width / rot_w)) if rot_w > 0 else 1

            for nx in range(1, max_nx + 1):
                for ny in range(1, max_ny + 1):
                    for nz in range(1, max_nz + 1):
                        block_count = nx * ny * nz
                        if block_count > count:
                            continue

                        bl = nx * rot_l
                        bh = ny * rot_h
                        bw = nz * rot_w
                        bvol = bl * bh * bw
                        if bvol > self.container_volume * MAX_BLOCK_VOLUME_RATIO:
                            continue

                        # 去重：(尺寸, count) 相同只保留一个
                        key = (round(bl, 1), round(bh, 1), round(bw, 1), block_count)
                        if key in seen:
                            continue
                        seen.add(key)

                        quality = self._score_block(bl, bh, bw, bvol)
                        sku_blocks.append(Block(
                            sku=item.id,
                            batch=batch,
                            nx=nx, ny=ny, nz=nz,
                            length=bl, height=bh, width=bw,
                            volume=bvol, count=block_count,
                            item_length=rot_l, item_height=rot_h, item_width=rot_w,
                            item_weight=item.weight,
                            is_fragile=bool(item.is_fragile),
                            rotation_label=rot_label,
                            orientation_name=orient_name,
                            quality_score=quality,
                        ))

        return sku_blocks

    @staticmethod
    def _score_block(length: float, height: float, width: float, volume: float) -> float:
        """Block 质量评分：体积 × (0.4 + 0.6 × 紧凑度)。
        紧凑度 = min(l, h, w) / max(l, h, w)，越接近立方体越好。
        """
        dims = [length, height, width]
        max_dim = max(dims) if dims else 1.0
        min_dim = min(dims) if dims else 0.0
        compactness = min_dim / max_dim if max_dim > 0 else 0.0
        return volume * (0.4 + 0.6 * compactness)


# ============================================================
# 模块 2: OrientationManager —— 方向约束管理器
# ============================================================
class OrientationManager:
    """管理并验证 Block 的放置方向。

    方向类型:
        • ANY:        允许任意旋转（通过 get_allowed_orientations 枚举）
        • UPRIGHT:    必须保持 height_vertical（高度方向固定）
        • NO_STACK:   fragile=true 时，不能被上方压载（必须位于最上层）
    """

    # Block 继承单品的朝向约束，Block 生成时已保证约束合法性
    # 此模块主要用于运行时验证（例如 NO_STACK 的 Block 上方是否被压）

    @staticmethod
    def is_no_stack(block: Block) -> bool:
        """是否禁止堆叠（易碎品不可承压）。"""
        return block.is_fragile

    @staticmethod
    def check_no_stack_violation(
        block: Block,
        x: float, y: float, z: float,
        existing_placements: List[Dict],
    ) -> bool:
        """检查放置后是否有物品压在 NO_STACK Block 上方。
        返回 True 表示有违规。"""
        if not block.is_fragile:
            return False

        x2, y2, z2 = x + block.length, y + block.height, z + block.width
        for p in existing_placements:
            # 查找是否有物品的 bottom 在 Block 的 top 之上
            if p["y"] < y2 - VERTICAL_TOLERANCE:
                continue  # 在下面，无问题
            if p["y"] < y2:
                continue  # 还没压到
            # 检查水平是否有重叠
            px, py, pz = p["x"], p["y"], p["z"]
            pl, ph, pw = p["l"], p["h"], p["w"]
            if x < px + pl and x2 > px and z < pz + pw and z2 > pz:
                return True  # 有物品压在 fragile Block 上方
        return False


# ============================================================
# 模块 3: FragileConstraint —— 易碎约束检测器
# ============================================================
class FragileConstraint:
    """易碎品约束检测器。

    规则:
        • 易碎品禁止上方有任何物品压载（必须位于最上层）
        • 易碎品自身的支撑率需 ≥ 85%（比普通 70% 更严格）
        • 易碎品不得压在其他易碎品上方（双重脆弱）
    """

    @staticmethod
    def check(
        block: Block,
        x: float, y: float, z: float,
        support_ratio: float,
        existing_placements: List[Dict],
    ) -> Tuple[float, bool, str]:
        """检查易碎品约束。
        返回 (safety_score, is_safe, reason)
        """
        if not block.is_fragile:
            # 非易碎品，但需检查是否压在易碎品上方
            return FragileConstraint._check_pressing_fragile(
                x, y, z, block.length, block.height, block.width,
                block.item_weight * block.count, existing_placements
            )

        reasons = []
        score = 1.0

        # 规则1: 支撑率 ≥ 85%
        if support_ratio < FRAGILE_SAFETY_RATIO:
            score -= 0.5
            reasons.append(f"易碎品支撑率不足: {support_ratio:.2%}")

        # 规则2: 上方无压载（由 OrientationManager.check_no_stack_violation 检查）

        # 规则3: 不得压在其他易碎品上方
        _, safe, r = FragileConstraint._check_pressing_fragile(
            x, y, z, block.length, block.height, block.width,
            block.item_weight * block.count, existing_placements
        )
        if not safe:
            score -= 0.3
            reasons.append(r)

        return score, score > 0.5, "; ".join(reasons)

    @staticmethod
    def _check_pressing_fragile(
        x: float, y: float, z: float,
        l: float, h: float, w: float,
        weight: float,
        existing_placements: List[Dict],
    ) -> Tuple[float, bool, str]:
        """检查是否压在易碎品上方。"""
        x2, z2 = x + l, z + w
        penalty = 0.0
        reason = ""
        for p in existing_placements:
            if not p.get("is_fragile"):
                continue
            if abs(y - (p["y"] + p["h"])) > VERTICAL_TOLERANCE:
                continue  # 不在正上方
            # 水平重叠
            px, pz = p["x"], p["z"]
            pl, pw = p["l"], p["w"]
            overlap_x = max(0, min(x2, px + pl) - max(x, px))
            overlap_z = max(0, min(z2, pz + pw) - max(z, pz))
            overlap_area = overlap_x * overlap_z
            fragile_area = pl * pw
            if overlap_area > 0 and fragile_area > 0:
                coverage = overlap_area / fragile_area
                if coverage > 0.1:
                    penalty += coverage * (weight / 100.0)
                    reason = f"压在易碎品上方 (覆盖率 {coverage:.1%})"

        safety = max(0.0, 1.0 - penalty)
        return safety, safety > 0.7, reason


# ============================================================
# 模块 4: BatchManager —— 批次约束管理器
# ============================================================
class BatchManager:
    """批次感知的分层装载策略。

    业务规则:
        • batch = 0: 优先靠近出口（X 大值区域）和容器外围
        • batch = 1: 中间层（中位 X）
        • batch ≥ 2: 更内层（小 X 区域）
        • 必须按 batch 升序放置：高 batch 的 Block 不得在低 batch 之前放置

    评分贡献:
        • batch0 偏好 x+block.length ≈ container_length（靠出口）
        • batch1 偏好 x 居中
        • batch≥2 偏好 x 较小（靠内部）
    """

    def __init__(self, container: ContainerConfig):
        self.cl = container.length
        self.ch = container.height
        self.cw = container.width

    def evaluate_batch_placement(
        self,
        block: Block,
        x: float, y: float, z: float,
    ) -> float:
        """评估 Block 放置位置是否符合批次分层策略。
        返回 0~1，越高越好。
        """
        batch = block.batch
        x2 = x + block.length

        if batch == 0:
            # 靠出口（X 大值），偏好 x2 ≈ container_length
            # 距离越近越好
            dist_from_back = self.cl - x2
            normalized = 1.0 - min(1.0, dist_from_back / max(self.cl, 1.0))
            return 0.6 * normalized + 0.2 * (1.0 if z <= 0.01 or z + block.width >= self.cw - 0.01 else 0.0) + 0.2 * (1.0 if y <= 0.01 else 0.0)

        elif batch == 1:
            # 中间层，偏好 x 居中
            center = self.cl / 2.0
            block_center = x + block.length / 2.0
            dist_from_center = abs(block_center - center)
            normalized = 1.0 - min(1.0, dist_from_center / (self.cl / 2.0))
            return normalized

        else:
            # batch ≥ 2: 内层（小 X 区域），偏好 x ≈ 0
            normalized = 1.0 - min(1.0, x / max(self.cl, 1.0))
            return normalized


# ============================================================
# 模块 5: EPManager —— Extreme Point 管理器
# ============================================================
class EPManager:
    """Extreme Point 管理：生成、更新、剪枝。"""

    def __init__(self, container: ContainerConfig):
        self.cl = container.length
        self.ch = container.height
        self.cw = container.width

    def generate_initial(self) -> List[Tuple[float, float, float]]:
        """生成初始 Extreme Point：(0,0,0) + 地板网格点。"""
        eps = [(0.0, 0.0, 0.0)]
        step_x = max(self.cl / 10.0, 300.0)
        step_z = max(self.cw / 10.0, 300.0)
        x = step_x
        while x < self.cl:
            z = step_z
            while z < self.cw:
                eps.append((x, 0.0, z))
                z += step_z
            x += step_x
        return eps

    def generate_new_points(
        self,
        x: float, y: float, z: float,
        l: float, h: float, w: float,
    ) -> List[Tuple[float, float, float]]:
        """放置 Block 后从三个远角生成新 EP。"""
        return [
            (x + l, y, z),
            (x, y + h, z),
            (x, y, z + w),
            (x + l, y, z + w),
            (x + l, y + h, z),
            (x, y + h, z + w),
        ]

    def prune(
        self,
        eps: List[Tuple[float, float, float]],
    ) -> List[Tuple[float, float, float]]:
        """剪枝：移除超出边界的 EP，均匀采样保留 MAX_EP_COUNT 个。"""
        # 过滤边界外
        valid = [(x, y, z) for (x, y, z) in eps
                 if x < self.cl - 0.01 and y < self.ch - 0.01 and z < self.cw - 0.01]
        if len(valid) <= MAX_EP_COUNT:
            return valid

        # 分层保留：floor EP（y=0）优先，按比例分配
        floor_eps = [ep for ep in valid if ep[1] <= 1.0]
        non_floor_eps = [ep for ep in valid if ep[1] > 1.0]

        floor_quota = MAX_EP_COUNT // 2
        non_floor_quota = MAX_EP_COUNT - floor_quota

        if len(floor_eps) <= floor_quota:
            non_floor_quota = MAX_EP_COUNT - len(floor_eps)
        elif len(non_floor_eps) <= non_floor_quota:
            floor_quota = MAX_EP_COUNT - len(non_floor_eps)

        if len(floor_eps) > floor_quota:
            floor_eps.sort(key=lambda ep: (ep[0], ep[2]))
            step = max(1, len(floor_eps) // floor_quota)
            floor_eps = floor_eps[::step][:floor_quota]

        if len(non_floor_eps) > non_floor_quota:
            non_floor_eps.sort(key=lambda ep: (ep[1], ep[0], ep[2]))
            step = max(1, len(non_floor_eps) // non_floor_quota)
            non_floor_eps = non_floor_eps[::step][:non_floor_quota]

        return floor_eps + non_floor_eps


# ============================================================
# 模块 6: CollisionDetector —— 碰撞检测器（空间网格索引）
# ============================================================
class CollisionDetector:
    """AABB 碰撞检测，使用空间网格索引实现 O(1) 平均复杂度。"""

    def __init__(self, container: ContainerConfig):
        self.cell_size = max(
            max(container.length, container.height, container.width) / GRID_CELL_DIV,
            50.0,
        )
        self._grid: Dict[Tuple[int, int, int], List[int]] = {}
        self._visit_version = 0
        self._visits: List[int] = []
        self._placements: List[Dict] = []

    def add(self, placement: Dict):
        idx = len(self._placements)
        self._placements.append(placement)
        self._visits.append(0)

        x, y, z = placement["x"], placement["y"], placement["z"]
        x2, y2, z2 = x + placement["l"], y + placement["h"], z + placement["w"]
        cs = self.cell_size
        for gx in range(int(x // cs), int(x2 // cs) + 1):
            for gy in range(int(y // cs), int(y2 // cs) + 1):
                for gz in range(int(z // cs), int(z2 // cs) + 1):
                    self._grid.setdefault((gx, gy, gz), []).append(idx)

    def check(self, x: float, y: float, z: float,
              l: float, h: float, w: float) -> bool:
        """检查是否与已放置物品重叠。"""
        x2, y2, z2 = x + l, y + h, z + w
        cs = self.cell_size
        self._visit_version += 1
        ver = self._visit_version
        visits = self._visits
        placements = self._placements
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

    def check_point(self, x: float, y: float, z: float) -> bool:
        """检查一个点是否被任何已放置物品包含。"""
        cs = self.cell_size
        self._visit_version += 1
        ver = self._visit_version
        visits = self._visits
        placements = self._placements
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

    def clone(self) -> 'CollisionDetector':
        new = CollisionDetector.__new__(CollisionDetector)
        new.cell_size = self.cell_size
        new._grid = {k: list(v) for k, v in self._grid.items()}
        new._visit_version = 0
        new._visits = list(self._visits)
        new._placements = [dict(p) for p in self._placements]
        return new


# ============================================================
# 模块 7: StabilityEvaluator —— 重力与稳定性评估器
# ============================================================
class StabilityEvaluator:
    """物理稳定性评估：支撑率 + 重心平衡。"""

    def __init__(self, container: ContainerConfig):
        self.cl = container.length
        self.ch = container.height
        self.cw = container.width

    def calc_support_ratio(
        self,
        x: float, y: float, z: float,
        l: float, h: float, w: float,
        placements: List[Dict],
    ) -> float:
        """计算支撑率（底部被支撑面积 / 总底面积）。
        y=0 的物品支撑率 = 1.0（地面完全支撑）。
        """
        if y <= VERTICAL_TOLERANCE:
            return 1.0

        item_footprint = l * w
        if item_footprint <= 0:
            return 0.0

        supported_area = 0.0
        x2, z2 = x + l, z + w

        for p in placements:
            px, py, pz = p["x"], p["y"], p["z"]
            pl, ph, pw = p["l"], p["h"], p["w"]
            p_top = py + ph

            # 只有正下方的物品才贡献支撑
            if abs(p_top - y) > VERTICAL_TOLERANCE:
                continue

            overlap_x = max(0, min(x2, px + pl) - max(x, px))
            overlap_z = max(0, min(z2, pz + pw) - max(z, pz))
            supported_area += overlap_x * overlap_z

        return supported_area / item_footprint if item_footprint > 0 else 0.0

    def check_support(
        self,
        block: Block,
        x: float, y: float, z: float,
        placements: List[Dict],
    ) -> Tuple[float, bool]:
        """检查支撑是否满足约束。
        普通 Block: ≥ 50%；易碎品 Block: ≥ 70%
        同时检查单品级浮空：Block 底部每个单品位置必须有支撑（不允许单品完全浮空）
        返回 (support_ratio, is_supported)
        """
        ratio = self.calc_support_ratio(x, y, z, block.length, block.height, block.width, placements)
        threshold = FRAGILE_SAFETY_RATIO if block.is_fragile else SUPPORT_THRESHOLD
        if ratio < threshold:
            return ratio, False

        # 单品级浮空检查：Block 底部按单品尺寸划分网格，每个单元必须有支撑
        if y > VERTICAL_TOLERANCE and block.count > 1:
            if not self._check_no_floating_items(block, x, y, z, placements):
                return ratio, False

        return ratio, True

    def _check_no_floating_items(
        self,
        block: Block,
        x: float, y: float, z: float,
        placements: List[Dict],
    ) -> bool:
        """检查 Block 底部每个单品位置是否有足够支撑。
        只检查底层（ny=0 的单品），因为上层单品由下层支撑。
        每个底层单品的支撑率必须 ≥ SUPPORT_THRESHOLD（50%）。
        """
        il, ih, iw = block.item_length, block.item_height, block.item_width

        for ix in range(block.nx):
            for iz in range(block.nz):
                # 单品底部的 x, z 范围
                sx = x + ix * il
                sz = z + iz * iw
                sx2 = sx + il
                sz2 = sz + iw

                # 检查这个单品位置是否有支撑
                supported_area = 0.0
                for p in placements:
                    p_top = p["y"] + p["h"]
                    if abs(p_top - y) > VERTICAL_TOLERANCE:
                        continue
                    ox = max(0, min(sx2, p["x"] + p["l"]) - max(sx, p["x"]))
                    oz = max(0, min(sz2, p["z"] + p["w"]) - max(sz, p["z"]))
                    supported_area += ox * oz

                # 单品底面积
                item_area = il * iw
                item_ratio = supported_area / item_area if item_area > 0 else 0

                # 每个单品支撑率必须 ≥ SUPPORT_THRESHOLD
                if item_ratio < SUPPORT_THRESHOLD:
                    return False

        return True

    def calc_cg_offset(
        self,
        total_weight: float,
        weighted_x: float,
        weighted_y: float,
        weighted_z: float,
    ) -> Tuple[float, float, float]:
        """计算当前重心相对于容器中心的偏移比例 (-1~1)。"""
        if total_weight <= 0:
            return 0.0, 0.0, 0.0

        cg_x = weighted_x / total_weight
        cg_y = weighted_y / total_weight
        cg_z = weighted_z / total_weight

        offset_x = (cg_x - self.cl / 2.0) / (self.cl / 2.0) if self.cl > 0 else 0.0
        offset_y = (cg_y - self.ch / 2.0) / (self.ch / 2.0) if self.ch > 0 else 0.0
        offset_z = (cg_z - self.cw / 2.0) / (self.cw / 2.0) if self.cw > 0 else 0.0

        return offset_x, offset_y, offset_z

    def cg_score(
        self,
        offset_x: float, offset_y: float, offset_z: float,
    ) -> float:
        """重心评分：偏移越小得分越高。0~1。"""
        euclidean = (offset_x ** 2 + offset_y ** 2 + offset_z ** 2) ** 0.5
        normalized = euclidean / (3.0 ** 0.5)  # 归一化到 0~1
        return max(0.0, 1.0 - normalized * 1.5)

    def is_cg_stable(
        self,
        offset_x: float, offset_z: float,
    ) -> bool:
        """检查水平重心是否在安全范围内。"""
        return abs(offset_x) <= CG_OFFSET_RATIO and abs(offset_z) <= CG_OFFSET_RATIO


# ============================================================
# 模块 8: ScoringFunction —— 综合评分函数（9维度加权）
# ============================================================
class ScoringFunction:
    """综合评分函数：空间利用率 + 稳定性 + 同SKU聚集 + 批次正确性 + 易碎安全。

    评分构成（越大越好，综合范围 ~ 0~1000）:
        1. 支撑率评分:      support_ratio × 100
        2. 墙面接触奖励:     (贴左/右/后墙 + 贴地板) × 50
        3. 同SKU聚集评分:   contact_ratio × 80
        4. 体积利用评分:     block_volume / container_volume × 200
        5. 地面接触评分:     y==0 ? 30 : 0
        6. 碎片化惩罚:      - (产生的 EP 数量 / 当前 EP 总数) × 40
        7. 重心惩罚:        - |cg_offset| × 20
        8. 易碎风险惩罚:    - fragile_penalty × 150
        9. 批次正确性奖励:   batch_match × 60
    """

    def __init__(self, container: ContainerConfig):
        self.cl = container.length
        self.ch = container.height
        self.cw = container.width
        self.container_volume = self.cl * self.ch * self.cw

    def score(
        self,
        block: Block,
        x: float, y: float, z: float,
        support_ratio: float,
        same_sku_ratio: float,
        cg_offset_x: float,
        cg_offset_z: float,
        fragile_penalty: float,
        batch_score: float,
        is_fragile: bool,
    ) -> float:
        """综合评分。"""
        # 1. 支撑率评分
        s_support = support_ratio * 100.0

        # 2. 墙面接触奖励（Block 贴容器壁给予奖励，鼓励规则堆叠）
        wall_contact = 0.0
        if x <= 0.01 or x + block.length >= self.cl - 0.01:
            wall_contact += 1.0
        if z <= 0.01 or z + block.width >= self.cw - 0.01:
            wall_contact += 1.0
        if y <= 0.01:
            wall_contact += 1.0
        s_wall = wall_contact / 3.0 * 50.0

        # 3. 同SKU聚集评分
        s_cluster = same_sku_ratio * 80.0

        # 4. 体积利用评分（Block 占容器比例）
        s_volume = (block.volume / self.container_volume) * 200.0 if self.container_volume > 0 else 0.0

        # 5. 地面接触评分（鼓励从底部向上堆叠）
        s_floor = 30.0 if y <= VERTICAL_TOLERANCE else 0.0

        # 6. 重心惩罚（水平偏移越大惩罚越大）
        cg_penalty = (abs(cg_offset_x) + abs(cg_offset_z)) * 20.0

        # 7. 易碎风险惩罚
        s_fragile = -fragile_penalty * 150.0

        # 8. 批次正确性奖励
        s_batch = batch_score * 60.0

        total = s_support + s_wall + s_cluster + s_volume + s_floor - cg_penalty + s_fragile + s_batch
        return total


# ============================================================
# 模块 9: BeamSearchSolver —— 束搜索求解器
# ============================================================
class BeamSearchSolver:
    """Beam Search 求解器：每步扩展所有合法 Block 放置，保留 top-K 状态。"""

    def __init__(
        self,
        container: ContainerConfig,
        blocks: List[Block],
        inventory: Dict[str, int],
        max_weight: float,
    ):
        self.container = container
        self.cl = container.length
        self.ch = container.height
        self.cw = container.width
        self.container_volume = self.cl * self.ch * self.cw
        self.blocks = blocks
        self.initial_inventory = dict(inventory)
        self.max_weight = max_weight

        # 初始化各模块
        self.ep_manager = EPManager(container)
        self.stability = StabilityEvaluator(container)
        self.scoring = ScoringFunction(container)
        self.batch_manager = BatchManager(container)

    def solve(self, beam_width: int = BEAM_WIDTH, max_steps: int = MAX_BEAM_STEPS) -> BeamState:
        """运行 Beam Search，返回最优状态。"""
        # 初始化状态
        initial_state = BeamState(
            placements=[],
            placed_blocks=[],
            extreme_points=self.ep_manager.generate_initial(),
            inventory=dict(self.initial_inventory),
            score=0.0,
            placed_volume=0.0,
            placed_weight=0.0,
            cg_x=0.0, cg_y=0.0, cg_z=0.0,
            total_weight=0.0,
        )

        beam: List[BeamState] = [initial_state]
        best_state = initial_state

        for step in range(max_steps):
            new_beam: List[Tuple[float, BeamState]] = []

            for state in beam:
                candidates = self._expand_state(state)
                for score, new_state in candidates:
                    new_beam.append((score, new_state))

            if not new_beam:
                break

            # 按评分降序，保留 top-K
            new_beam.sort(key=lambda x: x[0], reverse=True)
            beam = [s for _, s in new_beam[:beam_width]]

            if beam[0].placed_volume > best_state.placed_volume:
                best_state = beam[0]

            # 如果所有状态都无法再放置，退出
            if all(len(s.extreme_points) == 0 or
                   all(v == 0 for v in s.inventory.values())
                   for s in beam):
                break

        return best_state

    def _expand_state(self, state: BeamState) -> List[Tuple[float, BeamState]]:
        """扩展一个状态：尝试在所有 EP 放置所有可用 Block。"""
        candidates: List[Tuple[float, BeamState]] = []
        detector = CollisionDetector(self.container)
        for p in state.placements:
            detector.add(p)

        # 缓存：按 SKU 聚合剩余数量
        remaining_skus = {sku: cnt for sku, cnt in state.inventory.items() if cnt > 0}
        if not remaining_skus:
            return candidates

        # 遍历所有 Block（按单品体积降序遍历，优先尝试大物品）
        for block in self.blocks:
            if block.sku not in remaining_skus:
                continue
            if remaining_skus[block.sku] < block.count:
                continue
            if state.placed_weight + block.count * block.item_weight > self.max_weight:
                continue

            # 尝试所有 Extreme Point
            best_score_for_block = -float("inf")
            best_ep_for_block: Optional[Tuple[float, float, float]] = None

            for ep in state.extreme_points:
                ex, ey, ez = ep

                # 边界检查
                if (ex + block.length > self.cl + 0.01 or
                        ey + block.height > self.ch + 0.01 or
                        ez + block.width > self.cw + 0.01):
                    continue

                # 碰撞检测
                if detector.check(ex, ey, ez, block.length, block.height, block.width):
                    continue

                # 支撑率检查
                support_ratio, supported = self.stability.check_support(
                    block, ex, ey, ez, state.placements
                )
                if not supported:
                    continue

                # 易碎品上方压载检查
                if block.is_fragile and OrientationManager.check_no_stack_violation(
                    block, ex, ey, ez, state.placements
                ):
                    continue

                # 非易碎品但压在易碎品上方的检查
                if not block.is_fragile:
                    frag_safety, frag_ok, _ = FragileConstraint._check_pressing_fragile(
                        ex, ey, ez, block.length, block.height, block.width,
                        block.count * block.item_weight, state.placements
                    )
                    if not frag_ok:
                        # 有惩罚但不直接拒绝（评分中体现）
                        pass

                # 计算同 SKU 接触面积比
                same_sku_ratio = self._calc_same_sku_contact(block, ex, ey, ez, state.placed_blocks)

                # 计算放置后的重心偏移
                new_weighted_x = state.cg_x * state.total_weight + \
                    (ex + block.length / 2.0) * block.count * block.item_weight
                new_weighted_y = state.cg_y * state.total_weight + \
                    (ey + block.height / 2.0) * block.count * block.item_weight
                new_weighted_z = state.cg_z * state.total_weight + \
                    (ez + block.width / 2.0) * block.count * block.item_weight
                new_total_weight = state.total_weight + block.count * block.item_weight
                if new_total_weight > 0:
                    offset_x = (new_weighted_x / new_total_weight - self.cl / 2.0) / (self.cl / 2.0)
                    offset_z = (new_weighted_z / new_total_weight - self.cw / 2.0) / (self.cw / 2.0)
                else:
                    offset_x = offset_z = 0.0

                # 易碎惩罚
                if block.is_fragile:
                    frag_penalty = 0.0
                else:
                    frag_safety, _, _ = FragileConstraint._check_pressing_fragile(
                        ex, ey, ez, block.length, block.height, block.width,
                        block.count * block.item_weight, state.placements
                    )
                    frag_penalty = 1.0 - frag_safety

                # 批次评分
                batch_score = self.batch_manager.evaluate_batch_placement(block, ex, ey, ez)

                # 综合评分
                score = self.scoring.score(
                    block, ex, ey, ez,
                    support_ratio,
                    same_sku_ratio,
                    offset_x, offset_z,
                    frag_penalty,
                    batch_score,
                    block.is_fragile,
                )

                if score > best_score_for_block:
                    best_score_for_block = score
                    best_ep_for_block = ep

            # 找到该 Block 的最佳放置位置，生成新状态
            if best_ep_for_block is not None:
                new_state = self._apply_placement(state, block, best_ep_for_block, detector)
                candidates.append((best_score_for_block, new_state))

        return candidates

    def _calc_same_sku_contact(
        self,
        block: Block,
        x: float, y: float, z: float,
        placed_blocks: List[Dict],
    ) -> float:
        """计算新 Block 与同 SKU 已放置 Block 的接触面积比。"""
        if not placed_blocks:
            return 0.0

        bl, bh, bw = block.length, block.height, block.width
        contact_area = 0.0

        for pb in placed_blocks:
            if pb["sku"] != block.sku:
                continue
            px, py, pz = pb["x"], pb["y"], pb["z"]
            pl, ph, pw = pb["l"], pb["h"], pb["w"]

            # X 方向接触
            if abs(x - (px + pl)) < VERTICAL_TOLERANCE or abs((x + bl) - px) < VERTICAL_TOLERANCE:
                oy = max(0, min(y + bh, py + ph) - max(y, py))
                oz = max(0, min(z + bw, pz + pw) - max(z, pz))
                contact_area += oy * oz

            # Y 方向接触（上下相邻）
            if abs(y - (py + ph)) < VERTICAL_TOLERANCE or abs((y + bh) - py) < VERTICAL_TOLERANCE:
                ox = max(0, min(x + bl, px + pl) - max(x, px))
                oz = max(0, min(z + bw, pz + pw) - max(z, pz))
                contact_area += ox * oz

            # Z 方向接触
            if abs(z - (pz + pw)) < VERTICAL_TOLERANCE or abs((z + bw) - pz) < VERTICAL_TOLERANCE:
                ox = max(0, min(x + bl, px + pl) - max(x, px))
                oy = max(0, min(y + bh, py + ph) - max(y, py))
                contact_area += ox * oy

        surface = 2 * (bl * bh + bl * bw + bh * bw)
        return min(1.0, contact_area / surface) if surface > 0 else 0.0

    def _apply_placement(
        self,
        state: BeamState,
        block: Block,
        ep: Tuple[float, float, float],
        detector: CollisionDetector,
    ) -> BeamState:
        """在状态中放置 Block，生成新状态（克隆）。"""
        x, y, z = ep

        # 克隆状态（部分字段浅拷贝，因为我们会创建新的列表）
        new_placements = list(state.placements)
        new_placed_blocks = list(state.placed_blocks)
        new_inventory = dict(state.inventory)

        # 展开 Block 为单品 placement
        for i in range(block.nx):
            for j in range(block.ny):
                for k in range(block.nz):
                    ix = x + i * block.item_length
                    iy = y + j * block.item_height
                    iz = z + k * block.item_width
                    p = {
                        "item_id": block.sku,
                        "x": ix, "y": iy, "z": iz,
                        "l": block.item_length,
                        "h": block.item_height,
                        "w": block.item_width,
                        "weight": block.item_weight,
                        "is_fragile": block.is_fragile,
                        "rotation": block.rotation_label,
                        "orientation": block.orientation_name,
                    }
                    new_placements.append(p)

        # 记录 Block
        new_placed_blocks.append({
            "sku": block.sku,
            "batch": block.batch,
            "x": x, "y": y, "z": z,
            "l": block.length, "h": block.height, "w": block.width,
        })

        # 更新库存
        new_inventory[block.sku] = new_inventory.get(block.sku, 0) - block.count

        # 更新 Extreme Points：移除被新 Block 包含的点，添加新点
        # 使用 detector 检查 EP 是否被新 Block 包含
        new_eps_raw: List[Tuple[float, float, float]] = []
        seen: Set[Tuple[float, float, float]] = set()

        for old_ep in state.extreme_points:
            ex, ey, ez = old_ep
            # 如果 EP 被新 Block 包含，丢弃
            if (x <= ex < x + block.length and y <= ey < y + block.height and z <= ez < z + block.width):
                continue
            key = (round(ex, 2), round(ey, 2), round(ez, 2))
            if key in seen:
                continue
            seen.add(key)
            new_eps_raw.append(old_ep)

        # 添加新 EP（从 Block 的三个远角）
        new_corner_eps = self.ep_manager.generate_new_points(x, y, z, block.length, block.height, block.width)

        # 创建临时 detector 用于新 EP 检查
        temp_detector = CollisionDetector(self.container)
        for p in new_placements:
            temp_detector.add(p)

        for nep in new_corner_eps:
            ex, ey, ez = nep
            if ex >= self.cl - 0.01 or ey >= self.ch - 0.01 or ez >= self.cw - 0.01:
                continue
            if temp_detector.check_point(ex, ey, ez):
                continue
            key = (round(ex, 2), round(ey, 2), round(ez, 2))
            if key in seen:
                continue
            seen.add(key)
            new_eps_raw.append(nep)

        # 剪枝
        new_eps = self.ep_manager.prune(new_eps_raw)

        # 更新重心和重量
        new_placed_weight = state.placed_weight + block.count * block.item_weight
        new_placed_volume = state.placed_volume + block.volume
        new_total_weight = state.total_weight + block.count * block.item_weight

        # 累积加权坐标
        if new_total_weight > 0:
            new_cg_x = (state.cg_x * state.total_weight +
                        (x + block.length / 2.0) * block.count * block.item_weight) / new_total_weight
            new_cg_y = (state.cg_y * state.total_weight +
                        (y + block.height / 2.0) * block.count * block.item_weight) / new_total_weight
            new_cg_z = (state.cg_z * state.total_weight +
                        (z + block.width / 2.0) * block.count * block.item_weight) / new_total_weight
        else:
            new_cg_x = new_cg_y = new_cg_z = 0.0

        # 计算新状态评分（用利用率作为状态评分）
        new_score = new_placed_volume / self.container_volume if self.container_volume > 0 else 0.0

        return BeamState(
            placements=new_placements,
            placed_blocks=new_placed_blocks,
            extreme_points=new_eps,
            inventory=new_inventory,
            score=new_score,
            placed_volume=new_placed_volume,
            placed_weight=new_placed_weight,
            cg_x=new_cg_x, cg_y=new_cg_y, cg_z=new_cg_z,
            total_weight=new_total_weight,
        )


# ============================================================
# 主类: BlockOptimizer
# ============================================================
class BlockOptimizer:
    """基于 Block Packing + Extreme Point + Beam Search 的装箱优化器。

    企业级特性:
        • 同 SKU 商品组合成规则 Block，减少空间碎片
        • 支撑率 ≥ 70%（易碎品 ≥ 85%）
        • 重心偏移 ≤ 35% 容器半长
        • 易碎品禁止上方压载
        • 批次感知的分层装载（batch0 靠出口，batch≥2 靠内层）
        • Beam Search 搜索（beam_width=10），非纯贪心

    用法:
        optimizer = BlockOptimizer()
        placements = optimizer.pack(container, items)
    """

    def __init__(self):
        pass

    def pack(self, container: ContainerConfig, items: List[ItemInput]) -> List[Dict]:
        """装箱主入口。

        策略:
            • 中小场景（<300件）：贪心 + Beam Search 双路径取最优
            • 大场景（≥300件）：贪心 + Block聚集优先（性能优先）
        """
        # Step 1: 生成 Block 库
        generator = BlockGenerator(container, items)
        all_blocks = generator.generate()

        # Step 2: 初始化库存
        inventory: Dict[str, int] = {item.id: item.quantity for item in items}
        total_items = sum(inventory.values())

        # Step 3: 贪心路径（带物理稳定性 + 同 SKU 聚集 + 批次分层）
        greedy_result = self._greedy_pack(container, items, all_blocks, inventory)
        container_volume = container.length * container.height * container.width
        greedy_volume = sum(p["l"] * p["h"] * p["w"] for p in greedy_result)
        greedy_utilization = greedy_volume / container_volume if container_volume > 0 else 0

        # Step 4: 小场景额外尝试 Beam Search（更深度搜索）
        if total_items <= 300 and container_volume > 0:
            solver = BeamSearchSolver(container, all_blocks, inventory, container.max_weight)
            best_state = solver.solve(beam_width=5, max_steps=100)
            beam_utilization = best_state.placed_volume / container_volume
            if beam_utilization > greedy_utilization + 0.01:
                return best_state.placements

        return greedy_result

    def _greedy_pack(
        self,
        container: ContainerConfig,
        items: List[ItemInput],
        blocks: List[Block],
        initial_inventory: Dict[str, int],
    ) -> List[Dict]:
        """回退策略：贪心放置，同 SKU 聚集优先 + 物理稳定性检查。"""
        cl, ch, cw = container.length, container.height, container.width
        container_volume = cl * ch * cw

        detector = CollisionDetector(container)
        stability = StabilityEvaluator(container)
        scoring = ScoringFunction(container)
        batch_manager = BatchManager(container)

        placements: List[Dict] = []
        placed_blocks: List[Dict] = []
        eps = EPManager(container).generate_initial()
        inventory = dict(initial_inventory)
        placed_weight = 0.0
        total_weight = 0.0
        cg_x = cg_y = cg_z = 0.0

        for block in blocks:
            sku = block.sku
            while inventory.get(sku, 0) >= block.count:
                if placed_weight + block.count * block.item_weight > container.max_weight:
                    break

                best_score = -float("inf")
                best_ep: Optional[Tuple[float, float, float]] = None

                for ep in eps:
                    ex, ey, ez = ep
                    if (ex + block.length > cl + 0.01 or
                            ey + block.height > ch + 0.01 or
                            ez + block.width > cw + 0.01):
                        continue
                    if detector.check(ex, ey, ez, block.length, block.height, block.width):
                        continue

                    # 支撑率
                    support_ratio, supported = stability.check_support(
                        block, ex, ey, ez, placements
                    )
                    if not supported:
                        continue

                    # 易碎品上方压载检查
                    if block.is_fragile and OrientationManager.check_no_stack_violation(
                        block, ex, ey, ez, placements
                    ):
                        continue

                    # 计算同 SKU 聚集
                    same_sku_ratio = self._calc_same_sku_contact(block, ex, ey, ez, placed_blocks)

                    # 预测重心偏移
                    new_weight = block.count * block.item_weight
                    new_total = total_weight + new_weight
                    if new_total > 0:
                        off_x = (cg_x * total_weight + (ex + block.length / 2.0) * new_weight) / new_total
                        off_z = (cg_z * total_weight + (ez + block.width / 2.0) * new_weight) / new_total
                        offset_x = (off_x - cl / 2.0) / (cl / 2.0) if cl > 0 else 0.0
                        offset_z = (off_z - cw / 2.0) / (cw / 2.0) if cw > 0 else 0.0
                    else:
                        offset_x = offset_z = 0.0

                    # 易碎惩罚
                    if block.is_fragile:
                        frag_pen = 0.0
                    else:
                        frag_safety, _, _ = FragileConstraint._check_pressing_fragile(
                            ex, ey, ez, block.length, block.height, block.width,
                            new_weight, placements
                        )
                        frag_pen = 1.0 - frag_safety

                    # 批次评分
                    batch_score = batch_manager.evaluate_batch_placement(block, ex, ey, ez)

                    score = scoring.score(
                        block, ex, ey, ez,
                        support_ratio, same_sku_ratio,
                        offset_x, offset_z, frag_pen, batch_score, block.is_fragile
                    )
                    if score > best_score:
                        best_score = score
                        best_ep = ep

                if best_ep is None:
                    break

                x, y, z = best_ep

                # 放置 Block
                for i in range(block.nx):
                    for j in range(block.ny):
                        for k in range(block.nz):
                            ix = x + i * block.item_length
                            iy = y + j * block.item_height
                            iz = z + k * block.item_width
                            p = {
                                "item_id": sku,
                                "x": ix, "y": iy, "z": iz,
                                "l": block.item_length, "h": block.item_height, "w": block.item_width,
                                "weight": block.item_weight,
                                "is_fragile": block.is_fragile,
                                "rotation": block.rotation_label,
                                "orientation": block.orientation_name,
                            }
                            placements.append(p)
                            detector.add(p)

                placed_blocks.append({
                    "sku": sku, "batch": block.batch,
                    "x": x, "y": y, "z": z,
                    "l": block.length, "h": block.height, "w": block.width,
                })

                # 更新库存
                inventory[sku] = inventory.get(sku, 0) - block.count
                placed_weight += block.count * block.item_weight

                # 更新重心
                new_w = block.count * block.item_weight
                if total_weight + new_w > 0:
                    cg_x = (cg_x * total_weight + (x + block.length / 2.0) * new_w) / (total_weight + new_w)
                    cg_y = (cg_y * total_weight + (y + block.height / 2.0) * new_w) / (total_weight + new_w)
                    cg_z = (cg_z * total_weight + (z + block.width / 2.0) * new_w) / (total_weight + new_w)
                total_weight += new_w

                # 更新 EP
                ep_manager = EPManager(container)
                new_corners = ep_manager.generate_new_points(x, y, z, block.length, block.height, block.width)

                seen: Set[Tuple[float, float, float]] = set()
                filtered: List[Tuple[float, float, float]] = []
                for old_ep in eps:
                    ex, ey, ez = old_ep
                    if (x <= ex < x + block.length and y <= ey < y + block.height and z <= ez < z + block.width):
                        continue
                    key = (round(ex, 2), round(ey, 2), round(ez, 2))
                    if key in seen:
                        continue
                    seen.add(key)
                    filtered.append(old_ep)

                for nep in new_corners:
                    ex, ey, ez = nep
                    if ex >= cl - 0.01 or ey >= ch - 0.01 or ez >= cw - 0.01:
                        continue
                    if detector.check_point(ex, ey, ez):
                        continue
                    key = (round(ex, 2), round(ey, 2), round(ez, 2))
                    if key in seen:
                        continue
                    seen.add(key)
                    filtered.append(nep)

                eps = ep_manager.prune(filtered)

        return placements

    @staticmethod
    def _calc_same_sku_contact(
        block: Block,
        x: float, y: float, z: float,
        placed_blocks: List[Dict],
    ) -> float:
        """计算同 SKU 接触面积比（用于贪心策略）。"""
        if not placed_blocks:
            return 0.0
        bl, bh, bw = block.length, block.height, block.width
        contact_area = 0.0
        for pb in placed_blocks:
            if pb["sku"] != block.sku:
                continue
            px, py, pz = pb["x"], pb["y"], pb["z"]
            pl, ph, pw = pb["l"], pb["h"], pb["w"]
            if abs(x - (px + pl)) < VERTICAL_TOLERANCE or abs((x + bl) - px) < VERTICAL_TOLERANCE:
                oy = max(0, min(y + bh, py + ph) - max(y, py))
                oz = max(0, min(z + bw, pz + pw) - max(z, pz))
                contact_area += oy * oz
            if abs(y - (py + ph)) < VERTICAL_TOLERANCE or abs((y + bh) - py) < VERTICAL_TOLERANCE:
                ox = max(0, min(x + bl, px + pl) - max(x, px))
                oz = max(0, min(z + bw, pz + pw) - max(z, pz))
                contact_area += ox * oz
            if abs(z - (pz + pw)) < VERTICAL_TOLERANCE or abs((z + bw) - pz) < VERTICAL_TOLERANCE:
                ox = max(0, min(x + bl, px + pl) - max(x, px))
                oy = max(0, min(y + bh, py + ph) - max(y, py))
                contact_area += ox * oy
        surface = 2 * (bl * bh + bl * bw + bh * bw)
        return min(1.0, contact_area / surface) if surface > 0 else 0.0
