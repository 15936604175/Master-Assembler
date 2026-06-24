"""
企业级 3D Container Loading Solver —— 高级 Block Packing 引擎 (V2)
基于 Batch Corridor + Target Center + Sequence Penalty + Beam Search

核心创新（相比 BlockOptimizer V1）:
    1. Batch Corridor（动态走廊）: 根据各 batch 货量比例动态计算允许活动范围，
       而非固定切分。Corridor 之间允许重叠（20% 缓冲），避免硬边界导致空间浪费。
    2. Target Center（目标重心）: 每个 batch 计算期望重心位置，引导搜索自然形成
       Batch0 → Batch1 → Batch2 的顺序布局。
    3. Sequence Penalty（顺序惩罚）: Block 重心偏离 target_center 越远罚分越大。
    4. Corridor Penalty（走廊惩罚）: Block 超出 corridor 范围时按距离惩罚。
    5. Batch Separation Penalty（批次分离惩罚）: 避免高 batch 位于低 batch 之前。
    6. Batch Compactness Reward（批次紧凑奖励）: 同 batch 聚集度越高奖励越大。
    7. Beam Search（beam_width=20）: 每步保留 top-20 状态，非贪心选择。

评分函数（10 维度加权）:
    + 100 × supportScore         (支撑率)
    + 80  × utilizationScore     (体积利用率)
    + 60  × wallContactScore     (墙面接触)
    + 50  × sameSkuClusterScore  (同SKU聚集)
    + 40  × batchCompactnessScore(批次紧凑度)
    + 15  × cgCenterReward       (重心靠近中心奖励)
    - 60  × sequencePenalty      (顺序偏离惩罚)
    - 80  × corridorPenalty      (走廊越界惩罚)
    - 100 × orderViolationPenalty(批次顺序颠倒惩罚)
    - 50  × fragmentationPenalty (碎片化惩罚)
    - 20  × cgOffsetPenalty      (重心偏移惩罚)
"""

import time
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional, Set
from collections import defaultdict

from app.models.container import ContainerConfig
from app.models.item import ItemInput
from app.engine.rotation import get_allowed_orientations
from app.engine.block_optimizer import (
    Block, BlockGenerator, OrientationManager, FragileConstraint,
    EPManager, CollisionDetector, StabilityEvaluator,
    SUPPORT_THRESHOLD, FRAGILE_SAFETY_RATIO, VERTICAL_TOLERANCE,
    CG_OFFSET_RATIO, MAX_NX, MAX_NY, MAX_NZ, MAX_BLOCK_VOLUME_RATIO,
    MAX_BLOCKS_PER_SKU, MAX_EP_COUNT, GRID_CELL_DIV,
)


# ============================================================
# 常量配置（V2 专属）
# ============================================================
ADVANCED_BEAM_WIDTH = 20         # Beam Search 宽度（V2 更大）
ADVANCED_MAX_BEAM_STEPS = 150    # Beam Search 最大步数
CORRIDOR_EXPANSION_RATIO = 0.20  # Corridor 缓冲扩展比例（20%）

# 评分权重常量
SUPPORT_WEIGHT = 100.0          # 支撑率权重
VOLUME_WEIGHT = 80.0            # 体积利用率权重
WALL_CONTACT_WEIGHT = 60.0      # 墙面接触权重
SAME_SKU_CLUSTER_WEIGHT = 50.0  # 同SKU聚集权重
BATCH_COMPACTNESS_REWARD = 40.0  # 批次紧凑奖励权重
SEQUENCE_PENALTY_WEIGHT = 60.0   # 顺序偏离惩罚权重
CORRIDOR_PENALTY_WEIGHT = 80.0   # 走廊越界惩罚权重
ORDER_VIOLATION_PENALTY = 100.0  # 批次顺序颠倒惩罚（硬性）
FRAGMENTATION_PENALTY = 50.0     # 碎片化惩罚权重
CG_PENALTY_WEIGHT = 20.0         # 物理重心偏移惩罚权重（轻量引导，不干扰紧贴放置）
CG_CENTER_REWARD_WEIGHT = 15.0   # 物理重心靠近中心奖励权重
ADVANCED_CG_OFFSET_RATIO = 0.35  # 允许的重心偏移比例（容器半长）


# ============================================================
# 模块 A: BatchCorridorManager —— 动态走廊管理器
# ============================================================
@dataclass
class BatchCorridor:
    """批次走廊：定义该 batch 的允许活动范围（软约束）。"""
    batch_id: int
    preferred_min_x: float    # 期望最小 X（走廊左边界）
    preferred_max_x: float    # 期望最大 X（走廊右边界）
    target_center_x: float    # 目标重心 X
    total_volume: float       # 该 batch 总体积


class BatchCorridorManager:
    """根据各 batch 货量比例动态计算走廊，不采用固定切分。

    算法:
        1. 统计每个 batch 的总体积
        2. 按比例分配容器长度：expectedLength = ratio × containerLength
        3. 加入 20% 缓冲扩展，形成重叠走廊
        4. 计算 target_center_x 作为搜索引导
    """

    def __init__(self, container: ContainerConfig, items: List[ItemInput]):
        self.cl = container.length
        self.ch = container.height
        self.cw = container.width
        self.container_volume = self.cl * self.ch * self.cw
        self.corridors: Dict[int, BatchCorridor] = {}
        self._build_corridors(items)

    def _build_corridors(self, items: List[ItemInput]) -> None:
        """动态构建走廊。"""
        # 统计每个 batch 的总体积
        batch_volumes: Dict[int, float] = defaultdict(float)
        for item in items:
            batch = item.batch_number or 0
            vol = item.length * item.width * item.height * item.quantity
            batch_volumes[batch] += vol

        if not batch_volumes:
            return

        total_volume = sum(batch_volumes.values())
        if total_volume <= 0:
            return

        # 按 batch_id 排序
        sorted_batches = sorted(batch_volumes.keys())
        cl = self.cl

        # 累积分配：batch0 从 0 开始，batch1 接着 batch0，以此类推
        cumulative_x = 0.0
        for i, batch_id in enumerate(sorted_batches):
            vol = batch_volumes[batch_id]
            ratio = vol / total_volume
            expected_length = ratio * cl

            # 走廊范围（加入 20% 缓冲扩展，允许重叠）
            expansion = expected_length * CORRIDOR_EXPANSION_RATIO
            min_x = max(0.0, cumulative_x - expansion)
            max_x = min(cl, cumulative_x + expected_length + expansion)

            # 目标重心 = 走廊中心
            target_center = (cumulative_x + cumulative_x + expected_length) / 2.0

            self.corridors[batch_id] = BatchCorridor(
                batch_id=batch_id,
                preferred_min_x=min_x,
                preferred_max_x=max_x,
                target_center_x=target_center,
                total_volume=vol,
            )

            cumulative_x += expected_length

    def get_corridor(self, batch_id: int) -> Optional[BatchCorridor]:
        return self.corridors.get(batch_id)

    def evaluate_sequence_penalty(self, batch_id: int, block_center_x: float) -> float:
        """计算顺序偏离惩罚（0~1，越大惩罚越大）。
        Block 重心偏离 target_center 越远，惩罚越大。
        """
        corridor = self.get_corridor(batch_id)
        if not corridor:
            return 0.0

        distance = abs(block_center_x - corridor.target_center_x)
        # 归一化到容器半长
        normalized = distance / (self.cl / 2.0) if self.cl > 0 else 0.0
        return min(1.0, normalized)

    def evaluate_corridor_penalty(self, batch_id: int, block_center_x: float) -> float:
        """计算走廊越界惩罚（0~1，越大惩罚越大）。
        Block 重心在走廊内 → 0 惩罚
        Block 重心超出走廊 → 按超出距离惩罚
        """
        corridor = self.get_corridor(batch_id)
        if not corridor:
            return 0.0

        if corridor.preferred_min_x <= block_center_x <= corridor.preferred_max_x:
            return 0.0

        # 超出走廊
        if block_center_x < corridor.preferred_min_x:
            distance = corridor.preferred_min_x - block_center_x
        else:
            distance = block_center_x - corridor.preferred_max_x

        # 归一化到容器长度
        normalized = distance / self.cl if self.cl > 0 else 0.0
        return min(1.0, normalized)

    def evaluate_order_violation(
        self,
        batch_id: int,
        block_center_x: float,
        placed_blocks: List[Dict],
    ) -> float:
        """检查批次顺序颠倒：高 batch 是否位于低 batch 之前（X 更小）。
        返回惩罚值（0 = 无违规，1 = 严重违规）。

        业务规则:
            Batch0 应在前（小 X），Batch2 应在后（大 X）。
            如果高 batch 的中心 X < 低 batch 的中心 X，则顺序颠倒。
        """
        corridor = self.get_corridor(batch_id)
        if not corridor:
            return 0.0

        max_penalty = 0.0
        for pb in placed_blocks:
            pb_batch = pb.get("batch", 0)
            if pb_batch <= batch_id:
                continue  # 低 batch 或同 batch，无问题

            # pb_batch > batch_id，检查高 batch 是否在低 batch 之前
            pb_center_x = pb["x"] + pb["l"] / 2.0

            # 如果高 batch 的中心 X < 当前 block 的中心 X，说明高 batch 在前 → 顺序颠倒
            if pb_center_x < block_center_x:
                distance = block_center_x - pb_center_x
                normalized = distance / self.cl if self.cl > 0 else 0.0
                max_penalty = max(max_penalty, min(1.0, normalized))

        return max_penalty

    def evaluate_batch_compactness(
        self,
        batch_id: int,
        block: Block,
        x: float,
        placed_blocks: List[Dict],
    ) -> float:
        """计算批次紧凑度奖励（0~1）。
        同 batch 的 Block 聚集度越高，奖励越大。
        """
        same_batch_blocks = [pb for pb in placed_blocks if pb.get("batch", 0) == batch_id]
        if not same_batch_blocks:
            return 0.0

        bl = block.length
        contact_score = 0.0

        for pb in same_batch_blocks:
            px, pl = pb["x"], pb["l"]
            # X 方向接近度
            block_center_x = x + bl / 2.0
            pb_center_x = px + pl / 2.0
            x_distance = abs(block_center_x - pb_center_x)

            # 距离越近，紧凑度越高
            if x_distance < self.cl * 0.1:  # 在容器长度 10% 范围内
                contact_score += 1.0 - (x_distance / (self.cl * 0.1))

        # 归一化
        return min(1.0, contact_score / max(1, len(same_batch_blocks)))


# ============================================================
# 模块 B: AdvancedScoringFunction —— 高级评分函数（10 维度）
# ============================================================
class AdvancedScoringFunction:
    """高级综合评分函数：在 V1 基础上增加批次走廊、顺序惩罚和重心优化。

    评分构成（越大越好）:
        + 100 × supportScore          (支撑率)
        + 80  × utilizationScore      (体积利用率)
        + 60  × wallContactScore      (墙面接触)
        + 50  × sameSkuClusterScore   (同SKU聚集)
        + 40  × batchCompactnessScore (批次紧凑度)
        + 60  × cgCenterReward        (重心靠近中心奖励)
        - 60  × sequencePenalty       (顺序偏离惩罚)
        - 80  × corridorPenalty       (走廊越界惩罚)
        - 100 × orderViolationPenalty (批次顺序颠倒惩罚)
        - 50  × fragmentationPenalty  (碎片化惩罚)
        - 80  × cgOffsetPenalty       (重心偏移惩罚)
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
        batch_compactness: float,
        sequence_penalty: float,
        corridor_penalty: float,
        order_violation: float,
        fragmentation: float,
        cg_offset_x: float = 0.0,
        cg_offset_z: float = 0.0,
    ) -> float:
        """综合评分（含物理重心惩罚）。"""
        # 1. 支撑率评分
        s_support = support_ratio * SUPPORT_WEIGHT

        # 2. 体积利用评分
        s_volume = (block.volume / self.container_volume) * VOLUME_WEIGHT if self.container_volume > 0 else 0.0

        # 3. 墙面接触奖励
        wall_contact = 0.0
        if x <= 0.01 or x + block.length >= self.cl - 0.01:
            wall_contact += 1.0
        if z <= 0.01 or z + block.width >= self.cw - 0.01:
            wall_contact += 1.0
        if y <= 0.01:
            wall_contact += 1.0
        s_wall = (wall_contact / 3.0) * WALL_CONTACT_WEIGHT

        # 4. 同 SKU 聚集评分
        s_cluster = same_sku_ratio * SAME_SKU_CLUSTER_WEIGHT

        # 5. 批次紧凑度奖励
        s_batch_compact = batch_compactness * BATCH_COMPACTNESS_REWARD

        # 6. 顺序偏离惩罚
        p_sequence = sequence_penalty * SEQUENCE_PENALTY_WEIGHT

        # 7. 走廊越界惩罚
        p_corridor = corridor_penalty * CORRIDOR_PENALTY_WEIGHT

        # 8. 批次顺序颠倒惩罚（硬性）
        p_order = order_violation * ORDER_VIOLATION_PENALTY

        # 9. 碎片化惩罚
        p_frag = fragmentation * FRAGMENTATION_PENALTY

        # 10. 物理重心偏移惩罚（水平方向 X/Z）
        p_cg = (abs(cg_offset_x) + abs(cg_offset_z)) * CG_PENALTY_WEIGHT

        # 11. 物理重心靠近中心奖励（放置后重心越靠近中心，奖励越高）
        # cg_offset 范围 0~1（0=中心，1=边界），靠近中心时给予奖励
        cg_closeness = max(0.0, 1.0 - abs(cg_offset_x) - abs(cg_offset_z))
        s_cg_center = cg_closeness * CG_CENTER_REWARD_WEIGHT

        total = (s_support + s_volume + s_wall + s_cluster + s_batch_compact + s_cg_center
                 - p_sequence - p_corridor - p_order - p_frag - p_cg)
        return total


# ============================================================
# 模块 C: AdvancedBeamState —— 高级 Beam Search 状态
# ============================================================
@dataclass
class AdvancedBeamState:
    """高级 Beam Search 状态：包含批次分布与物理重心信息。"""
    placements: List[Dict] = field(default_factory=list)
    placed_blocks: List[Dict] = field(default_factory=list)
    extreme_points: List[Tuple[float, float, float]] = field(default_factory=list)
    inventory: Dict[str, int] = field(default_factory=dict)
    score: float = 0.0
    placed_volume: float = 0.0
    placed_weight: float = 0.0
    # 批次分布追踪
    batch_min_x: Dict[int, float] = field(default_factory=dict)  # 每个 batch 的最小 X
    batch_max_x: Dict[int, float] = field(default_factory=dict)  # 每个 batch 的最大 X
    batch_volume: Dict[int, float] = field(default_factory=dict)  # 每个 batch 已放置体积
    # 物理重心追踪（Block 层面累积加权坐标）
    cg_x: float = 0.0   # 当前重心 X（累积）
    cg_y: float = 0.0
    cg_z: float = 0.0
    total_weight: float = 0.0  # 已放置总重量


# ============================================================
# 模块 D: AdvancedBeamSearchSolver —— 高级束搜索求解器
# ============================================================
class AdvancedBeamSearchSolver:
    """高级 Beam Search 求解器：集成 Batch Corridor + Sequence Penalty。"""

    def __init__(
        self,
        container: ContainerConfig,
        blocks: List[Block],
        inventory: Dict[str, int],
        max_weight: float,
        corridor_manager: BatchCorridorManager,
    ):
        self.container = container
        self.cl = container.length
        self.ch = container.height
        self.cw = container.width
        self.container_volume = self.cl * self.ch * self.cw
        self.blocks = blocks
        self.initial_inventory = dict(inventory)
        self.max_weight = max_weight
        self.corridor_manager = corridor_manager

        # 复用 V1 的模块
        self.ep_manager = EPManager(container)
        self.stability = StabilityEvaluator(container)
        self.scoring = AdvancedScoringFunction(container)

    def solve(
        self,
        beam_width: int = ADVANCED_BEAM_WIDTH,
        max_steps: int = ADVANCED_MAX_BEAM_STEPS,
    ) -> AdvancedBeamState:
        """运行 Beam Search，返回最优状态。"""
        # 初始化状态
        initial_state = AdvancedBeamState(
            placements=[],
            placed_blocks=[],
            extreme_points=self.ep_manager.generate_initial(),
            inventory=dict(self.initial_inventory),
        )

        beam: List[AdvancedBeamState] = [initial_state]
        best_state = initial_state

        for step in range(max_steps):
            new_beam: List[Tuple[float, AdvancedBeamState]] = []

            for state in beam:
                candidates = self._expand_state(state)
                for score, new_state in candidates:
                    new_beam.append((score, new_state))

            if not new_beam:
                break

            # 按评分降序，保留 top-K
            new_beam.sort(key=lambda x: x[0], reverse=True)
            beam = [s for _, s in new_beam[:beam_width]]

            # 更新最优状态（以放置体积为主）
            if beam[0].placed_volume > best_state.placed_volume:
                best_state = beam[0]

            # 终止条件
            if all(len(s.extreme_points) == 0 or
                   all(v == 0 for v in s.inventory.values())
                   for s in beam):
                break

        return best_state

    def _expand_state(self, state: AdvancedBeamState) -> List[Tuple[float, AdvancedBeamState]]:
        """扩展一个状态。"""
        candidates: List[Tuple[float, AdvancedBeamState]] = []
        detector = CollisionDetector(self.container)
        for p in state.placements:
            detector.add(p)

        remaining_skus = {sku: cnt for sku, cnt in state.inventory.items() if cnt > 0}
        if not remaining_skus:
            return candidates

        # 遍历所有 Block
        for block in self.blocks:
            if block.sku not in remaining_skus:
                continue
            if remaining_skus[block.sku] < block.count:
                continue
            if state.placed_weight + block.count * block.item_weight > self.max_weight:
                continue

            best_score = -float("inf")
            best_ep: Optional[Tuple[float, float, float]] = None

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

                # 易碎品检查
                if block.is_fragile and OrientationManager.check_no_stack_violation(
                    block, ex, ey, ez, state.placements
                ):
                    continue

                # 计算各项评分
                block_center_x = ex + block.length / 2.0

                # 同 SKU 聚集
                same_sku_ratio = self._calc_same_sku_contact(block, ex, ey, ez, state.placed_blocks)

                # 批次紧凑度
                batch_compactness = self.corridor_manager.evaluate_batch_compactness(
                    block.batch, block, ex, state.placed_blocks
                )

                # 顺序偏离惩罚
                sequence_penalty = self.corridor_manager.evaluate_sequence_penalty(
                    block.batch, block_center_x
                )

                # 走廊越界惩罚
                corridor_penalty = self.corridor_manager.evaluate_corridor_penalty(
                    block.batch, block_center_x
                )

                # 批次顺序颠倒惩罚
                order_violation = self.corridor_manager.evaluate_order_violation(
                    block.batch, block_center_x, state.placed_blocks
                )

                # 碎片化（简化：用 EP 数量估计）
                fragmentation = min(1.0, len(state.extreme_points) / MAX_EP_COUNT)

                # 物理重心偏移预测（Block 层面，与 V1 一致）
                new_weight = block.count * block.item_weight
                new_total_weight = state.total_weight + new_weight
                if new_total_weight > 0:
                    new_weighted_x = state.cg_x * state.total_weight + \
                        (ex + block.length / 2.0) * new_weight
                    new_weighted_z = state.cg_z * state.total_weight + \
                        (ez + block.width / 2.0) * new_weight
                    cg_offset_x = (new_weighted_x / new_total_weight - self.cl / 2.0) / (self.cl / 2.0) if self.cl > 0 else 0.0
                    cg_offset_z = (new_weighted_z / new_total_weight - self.cw / 2.0) / (self.cw / 2.0) if self.cw > 0 else 0.0
                else:
                    cg_offset_x = cg_offset_z = 0.0

                # 综合评分
                score = self.scoring.score(
                    block, ex, ey, ez,
                    support_ratio,
                    same_sku_ratio,
                    batch_compactness,
                    sequence_penalty,
                    corridor_penalty,
                    order_violation,
                    fragmentation,
                    cg_offset_x,
                    cg_offset_z,
                )

                if score > best_score:
                    best_score = score
                    best_ep = ep

            if best_ep is not None:
                new_state = self._apply_placement(state, block, best_ep, detector)
                candidates.append((best_score, new_state))

        return candidates

    def _calc_same_sku_contact(
        self,
        block: Block,
        x: float, y: float, z: float,
        placed_blocks: List[Dict],
    ) -> float:
        """计算同 SKU 接触面积比。"""
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

    def _apply_placement(
        self,
        state: AdvancedBeamState,
        block: Block,
        ep: Tuple[float, float, float],
        detector: CollisionDetector,
    ) -> AdvancedBeamState:
        """在状态中放置 Block，生成新状态。"""
        x, y, z = ep

        new_placements = list(state.placements)
        new_placed_blocks = list(state.placed_blocks)
        new_inventory = dict(state.inventory)
        new_batch_min_x = dict(state.batch_min_x)
        new_batch_max_x = dict(state.batch_max_x)
        new_batch_volume = dict(state.batch_volume)

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
                        "l": block.item_length, "h": block.item_height, "w": block.item_width,
                        "weight": block.item_weight,
                        "is_fragile": block.is_fragile,
                        "rotation": block.rotation_label,
                        "orientation": block.orientation_name,
                    }
                    new_placements.append(p)

        # 记录 Block
        block_x2 = x + block.length
        new_placed_blocks.append({
            "sku": block.sku,
            "batch": block.batch,
            "x": x, "y": y, "z": z,
            "l": block.length, "h": block.height, "w": block.width,
        })

        # 更新库存
        new_inventory[block.sku] = new_inventory.get(block.sku, 0) - block.count

        # 更新批次分布
        batch = block.batch
        if batch not in new_batch_min_x:
            new_batch_min_x[batch] = x
            new_batch_max_x[batch] = block_x2
            new_batch_volume[batch] = block.volume
        else:
            new_batch_min_x[batch] = min(new_batch_min_x[batch], x)
            new_batch_max_x[batch] = max(new_batch_max_x[batch], block_x2)
            new_batch_volume[batch] = new_batch_volume.get(batch, 0) + block.volume

        # 更新 Extreme Points
        new_eps_raw: List[Tuple[float, float, float]] = []
        seen: Set[Tuple[float, float, float]] = set()

        for old_ep in state.extreme_points:
            ex, ey, ez = old_ep
            if (x <= ex < x + block.length and y <= ey < y + block.height and z <= ez < z + block.width):
                continue
            key = (round(ex, 2), round(ey, 2), round(ez, 2))
            if key in seen:
                continue
            seen.add(key)
            new_eps_raw.append(old_ep)

        new_corner_eps = self.ep_manager.generate_new_points(x, y, z, block.length, block.height, block.width)

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

        new_eps = self.ep_manager.prune(new_eps_raw)

        new_placed_weight = state.placed_weight + block.count * block.item_weight
        new_placed_volume = state.placed_volume + block.volume
        new_total_weight = state.total_weight + block.count * block.item_weight

        # 累积加权坐标（Block 层面重心，与 V1 一致）
        if new_total_weight > 0:
            new_cg_x = (state.cg_x * state.total_weight +
                        (x + block.length / 2.0) * block.count * block.item_weight) / new_total_weight
            new_cg_y = (state.cg_y * state.total_weight +
                        (y + block.height / 2.0) * block.count * block.item_weight) / new_total_weight
            new_cg_z = (state.cg_z * state.total_weight +
                        (z + block.width / 2.0) * block.count * block.item_weight) / new_total_weight
        else:
            new_cg_x = new_cg_y = new_cg_z = 0.0

        return AdvancedBeamState(
            placements=new_placements,
            placed_blocks=new_placed_blocks,
            extreme_points=new_eps,
            inventory=new_inventory,
            score=new_placed_volume / self.container_volume if self.container_volume > 0 else 0.0,
            placed_volume=new_placed_volume,
            placed_weight=new_placed_weight,
            batch_min_x=new_batch_min_x,
            batch_max_x=new_batch_max_x,
            batch_volume=new_batch_volume,
            cg_x=new_cg_x, cg_y=new_cg_y, cg_z=new_cg_z,
            total_weight=new_total_weight,
        )


# ============================================================
# 主类: AdvancedBlockOptimizer
# ============================================================
class AdvancedBlockOptimizer:
    """高级 Block Packing 优化器（V2）。

    相比 V1 的改进:
        • Batch Corridor 动态走廊（根据货量比例分配，允许重叠）
        • Target Center 目标重心引导
        • Sequence Penalty 顺序偏离惩罚
        • Corridor Penalty 走廊越界惩罚
        • Order Violation 批次顺序颠倒惩罚
        • Batch Compactness 批次紧凑度奖励
        • Beam Search beam_width=20（V1 是 10）

    用法:
        optimizer = AdvancedBlockOptimizer()
        placements = optimizer.pack(container, items)
    """

    def __init__(self):
        pass

    def pack(self, container: ContainerConfig, items: List[ItemInput]) -> List[Dict]:
        """装箱主入口。

        策略（双路径取最优，与 V1 一致）:
            • 贪心路径（总是运行）：带批次走廊评分，保证放置率
            • Beam Search（中小场景额外尝试）：更深度搜索，取更优解
            • 比较两条路径，返回放置数量更多 / 利用率更高的方案
        """
        # Step 1: 生成 Block 库
        generator = BlockGenerator(container, items)
        all_blocks = generator.generate()

        # Step 2: 初始化库存
        inventory: Dict[str, int] = {item.id: item.quantity for item in items}
        total_items = sum(inventory.values())

        # Step 3: 构建批次走廊
        corridor_manager = BatchCorridorManager(container, items)

        # Step 4: 贪心路径（总是运行，保证放置率）
        greedy_result = self._greedy_pack_with_corridor(
            container, items, all_blocks, inventory, corridor_manager
        )
        container_volume = container.length * container.height * container.width
        greedy_volume = sum(p["l"] * p["h"] * p["w"] for p in greedy_result)
        greedy_utilization = greedy_volume / container_volume if container_volume > 0 else 0

        # Step 5: 中小场景额外尝试 Beam Search（更深度搜索）
        if total_items <= 500 and container_volume > 0:
            solver = AdvancedBeamSearchSolver(
                container, all_blocks, inventory, container.max_weight, corridor_manager
            )
            best_state = solver.solve(
                beam_width=ADVANCED_BEAM_WIDTH, max_steps=ADVANCED_MAX_BEAM_STEPS
            )
            beam_placements = best_state.placements
            beam_utilization = best_state.placed_volume / container_volume

            # 取放置数量更多 / 利用率更高的方案
            if len(beam_placements) > len(greedy_result):
                return beam_placements
            if (len(beam_placements) == len(greedy_result)
                    and beam_utilization > greedy_utilization + 0.01):
                return beam_placements

        return greedy_result

    def _greedy_pack_with_corridor(
        self,
        container: ContainerConfig,
        items: List[ItemInput],
        blocks: List[Block],
        initial_inventory: Dict[str, int],
        corridor_manager: BatchCorridorManager,
    ) -> List[Dict]:
        """大场景贪心策略：带批次走廊评分。"""
        cl, ch, cw = container.length, container.height, container.width

        detector = CollisionDetector(container)
        stability = StabilityEvaluator(container)
        scoring = AdvancedScoringFunction(container)
        ep_manager = EPManager(container)

        placements: List[Dict] = []
        placed_blocks: List[Dict] = []
        eps = ep_manager.generate_initial()
        inventory = dict(initial_inventory)
        placed_weight = 0.0
        # 物理重心累积量（Block 层面，与 V1 一致）
        cg_x = 0.0
        cg_y = 0.0
        cg_z = 0.0
        total_weight = 0.0

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

                    support_ratio, supported = stability.check_support(
                        block, ex, ey, ez, placements
                    )
                    if not supported:
                        continue

                    if block.is_fragile and OrientationManager.check_no_stack_violation(
                        block, ex, ey, ez, placements
                    ):
                        continue

                    # 计算评分
                    block_center_x = ex + block.length / 2.0
                    same_sku_ratio = self._calc_same_sku_contact(block, ex, ey, ez, placed_blocks)
                    batch_compactness = corridor_manager.evaluate_batch_compactness(
                        block.batch, block, ex, placed_blocks
                    )
                    sequence_penalty = corridor_manager.evaluate_sequence_penalty(
                        block.batch, block_center_x
                    )
                    corridor_penalty = corridor_manager.evaluate_corridor_penalty(
                        block.batch, block_center_x
                    )
                    order_violation = corridor_manager.evaluate_order_violation(
                        block.batch, block_center_x, placed_blocks
                    )
                    fragmentation = min(1.0, len(eps) / MAX_EP_COUNT)

                    # 物理重心偏移预测（Block 层面，与 V1 一致）
                    new_weight = block.count * block.item_weight
                    new_total = total_weight + new_weight
                    if new_total > 0:
                        new_wx = cg_x * total_weight + (ex + block.length / 2.0) * new_weight
                        new_wz = cg_z * total_weight + (ez + block.width / 2.0) * new_weight
                        cg_offset_x = (new_wx / new_total - cl / 2.0) / (cl / 2.0) if cl > 0 else 0.0
                        cg_offset_z = (new_wz / new_total - cw / 2.0) / (cw / 2.0) if cw > 0 else 0.0
                    else:
                        cg_offset_x = cg_offset_z = 0.0

                    score = scoring.score(
                        block, ex, ey, ez,
                        support_ratio, same_sku_ratio,
                        batch_compactness, sequence_penalty,
                        corridor_penalty, order_violation, fragmentation,
                        cg_offset_x, cg_offset_z,
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

                inventory[sku] = inventory.get(sku, 0) - block.count
                placed_weight += block.count * block.item_weight

                # 更新物理重心（Block 层面累积加权坐标，与 V1 一致）
                new_w = block.count * block.item_weight
                if total_weight + new_w > 0:
                    cg_x = (cg_x * total_weight + (x + block.length / 2.0) * new_w) / (total_weight + new_w)
                    cg_y = (cg_y * total_weight + (y + block.height / 2.0) * new_w) / (total_weight + new_w)
                    cg_z = (cg_z * total_weight + (z + block.width / 2.0) * new_w) / (total_weight + new_w)
                total_weight += new_w

                # 更新 EP
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
        """计算同 SKU 接触面积比。"""
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
