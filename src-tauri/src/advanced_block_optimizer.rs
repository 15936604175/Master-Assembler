/// V2 高级 Block Packing 引擎
/// 基于 Batch Corridor + Target Center + Sequence Penalty + Beam Search

use std::collections::{HashMap, HashSet};
use crate::models::{
    Block, BlockInfo, AdvancedBeamState, BatchCorridor, ContainerConfig, ItemInput, PlacementInfo,
};
use crate::block_optimizer::{
    BlockGenerator, OrientationManager, FragileConstraint,
    EPManager, CollisionDetector, StabilityEvaluator,
    SUPPORT_THRESHOLD, FRAGILE_SAFETY_RATIO, VERTICAL_TOLERANCE,
    MAX_EP_COUNT, calc_same_sku_contact,
};

// ── V2 常量 ───────────────────────────────────────────────────
const ADVANCED_BEAM_WIDTH: usize = 20;           // Beam Search 宽度，每步保留 Top-K 个候选状态
const ADVANCED_MAX_BEAM_STEPS: usize = 150;      // Beam Search 最大搜索步数
const CORRIDOR_EXPANSION_RATIO: f64 = 0.20;      // 批次走廊缓冲扩展比例（相对于批次预期长度）
const SEQUENCE_PENALTY_WEIGHT: f64 = 60.0;       // 顺序偏离惩罚权重（Block 重心偏离目标中心越远罚分越大）
const CORRIDOR_PENALTY_WEIGHT: f64 = 80.0;       // 走廊越界惩罚权重（Block 超出走廊范围时按距离惩罚）
const ORDER_VIOLATION_PENALTY: f64 = 100.0;      // 批次顺序颠倒惩罚（高批次号出现在低批次号之前）
const BATCH_COMPACTNESS_REWARD: f64 = 40.0;       // 同批次紧凑度奖励权重
const FRAGMENTATION_PENALTY: f64 = 50.0;          // 空间碎片化惩罚权重
const CG_PENALTY_WEIGHT: f64 = 20.0;              // 物理重心偏移惩罚权重（轻量引导，不干扰紧贴放置）
const CG_CENTER_REWARD_WEIGHT: f64 = 15.0;        // 物理重心靠近中心奖励权重
const ADVANCED_CG_OFFSET_RATIO: f64 = 0.35;       // 允许的重心偏移比例（容器半长）

// ── BatchCorridorManager ──────────────────────────────────────
pub struct BatchCorridorManager {
    cl: f64, ch: f64, cw: f64,
    container_volume: f64,
    corridors: HashMap<i32, BatchCorridor>,
}

impl BatchCorridorManager {
    pub fn new(container: &ContainerConfig, items: &[ItemInput]) -> Self {
        let cl = container.length; let ch = container.height; let cw = container.width;
        let container_volume = cl * ch * cw;
        let mut mgr = Self { cl, ch, cw, container_volume, corridors: HashMap::new() };
        mgr.build_corridors(items);
        mgr
    }

    fn build_corridors(&mut self, items: &[ItemInput]) {
        let mut batch_volumes: HashMap<i32, f64> = HashMap::new();
        for item in items {
            let batch = item.batch_number;
            let vol = item.length * item.width * item.height * item.quantity as f64;
            *batch_volumes.entry(batch).or_insert(0.0) += vol;
        }
        if batch_volumes.is_empty() { return; }
        let total_volume: f64 = batch_volumes.values().sum();
        if total_volume <= 0.0 { return; }

        let mut sorted_batches: Vec<i32> = batch_volumes.keys().copied().collect();
        sorted_batches.sort();
        let cl = self.cl;
        let mut cumulative_x = 0.0;

        for batch_id in sorted_batches {
            let vol = batch_volumes[&batch_id];
            let ratio = vol / total_volume;
            let expected_length = ratio * cl;
            let expansion = expected_length * CORRIDOR_EXPANSION_RATIO;
            let min_x = (cumulative_x - expansion).max(0.0);
            let max_x = (cumulative_x + expected_length + expansion).min(cl);
            let target_center = (cumulative_x + cumulative_x + expected_length) / 2.0;
            self.corridors.insert(batch_id, BatchCorridor {
                batch_id, preferred_min_x: min_x, preferred_max_x: max_x,
                target_center_x: target_center, total_volume: vol,
            });
            cumulative_x += expected_length;
        }
    }

    pub fn get_corridor(&self, batch_id: i32) -> Option<&BatchCorridor> {
        self.corridors.get(&batch_id)
    }

    pub fn evaluate_sequence_penalty(&self, batch_id: i32, block_center_x: f64) -> f64 {
        let corridor = match self.get_corridor(batch_id) { Some(c) => c, None => return 0.0 };
        let distance = (block_center_x - corridor.target_center_x).abs();
        let normalized = if self.cl > 0.0 { distance / (self.cl / 2.0) } else { 0.0 };
        normalized.min(1.0)
    }

    pub fn evaluate_corridor_penalty(&self, batch_id: i32, block_center_x: f64) -> f64 {
        let corridor = match self.get_corridor(batch_id) { Some(c) => c, None => return 0.0 };
        if corridor.preferred_min_x <= block_center_x && block_center_x <= corridor.preferred_max_x {
            return 0.0;
        }
        let distance = if block_center_x < corridor.preferred_min_x {
            corridor.preferred_min_x - block_center_x
        } else {
            block_center_x - corridor.preferred_max_x
        };
        let normalized = if self.cl > 0.0 { distance / self.cl } else { 0.0 };
        normalized.min(1.0)
    }

    pub fn evaluate_order_violation(&self, batch_id: i32, block_center_x: f64, placed_blocks: &[BlockInfo]) -> f64 {
        let _corridor = match self.get_corridor(batch_id) { Some(c) => c, None => return 0.0 };
        let mut max_penalty: f64 = 0.0;
        for pb in placed_blocks {
            if pb.batch <= batch_id { continue; }
            let pb_center_x = pb.x + pb.l / 2.0;
            if pb_center_x < block_center_x {
                let distance = block_center_x - pb_center_x;
                let normalized = if self.cl > 0.0 { distance / self.cl } else { 0.0 };
                max_penalty = max_penalty.max(normalized.min(1.0));
            }
        }
        max_penalty
    }

    pub fn evaluate_batch_compactness(&self, batch_id: i32, block: &Block, x: f64, placed_blocks: &[BlockInfo]) -> f64 {
        let same_batch: Vec<&BlockInfo> = placed_blocks.iter().filter(|pb| pb.batch == batch_id).collect();
        if same_batch.is_empty() { return 0.0; }
        let bl = block.length;
        let mut contact_score = 0.0;
        for pb in &same_batch {
            let block_center_x = x + bl / 2.0;
            let pb_center_x = pb.x + pb.l / 2.0;
            let x_distance = (block_center_x - pb_center_x).abs();
            if x_distance < self.cl * 0.1 {
                contact_score += 1.0 - (x_distance / (self.cl * 0.1));
            }
        }
        (contact_score / same_batch.len() as f64).min(1.0)
    }
}

// ── AdvancedScoringFunction ───────────────────────────────────
pub struct AdvancedScoringFunction {
    cl: f64, ch: f64, cw: f64,
    container_volume: f64,
}

impl AdvancedScoringFunction {
    pub fn new(container: &ContainerConfig) -> Self {
        Self {
            cl: container.length, ch: container.height, cw: container.width,
            container_volume: container.length * container.height * container.width,
        }
    }

    pub fn score(
        &self, block: &Block, x: f64, y: f64, _z: f64,
        support_ratio: f64, same_sku_ratio: f64,
        batch_compactness: f64, sequence_penalty: f64,
        corridor_penalty: f64, order_violation: f64, fragmentation: f64,
        cg_offset_x: f64, cg_offset_z: f64,
    ) -> f64 {
        let s_support = support_ratio * 100.0;
        let s_volume = if self.container_volume > 0.0 { block.volume / self.container_volume * 80.0 } else { 0.0 };
        let mut wall_contact = 0.0;
        if x <= 0.01 || x + block.length >= self.cl - 0.01 { wall_contact += 1.0; }
        if _z <= 0.01 || _z + block.width >= self.cw - 0.01 { wall_contact += 1.0; }
        if y <= 0.01 { wall_contact += 1.0; }
        let s_wall = (wall_contact / 3.0) * 60.0;
        let s_cluster = same_sku_ratio * 50.0;
        let s_batch_compact = batch_compactness * BATCH_COMPACTNESS_REWARD;
        let p_sequence = sequence_penalty * SEQUENCE_PENALTY_WEIGHT;
        let p_corridor = corridor_penalty * CORRIDOR_PENALTY_WEIGHT;
        let p_order = order_violation * ORDER_VIOLATION_PENALTY;
        let p_frag = fragmentation * FRAGMENTATION_PENALTY;
        // 物理重心偏移惩罚（水平方向 X/Z）
        let p_cg = (cg_offset_x.abs() + cg_offset_z.abs()) * CG_PENALTY_WEIGHT;
        // 物理重心靠近中心奖励（放置后重心越靠近中心，奖励越高）
        let cg_closeness = (1.0 - cg_offset_x.abs() - cg_offset_z.abs()).max(0.0);
        let s_cg_center = cg_closeness * CG_CENTER_REWARD_WEIGHT;
        s_support + s_volume + s_wall + s_cluster + s_batch_compact + s_cg_center - p_sequence - p_corridor - p_order - p_frag - p_cg
    }
}

// -- AdvancedBeamSearchSolver --
pub struct AdvancedBeamSearchSolver<'a> {
    container: &'a ContainerConfig,
    cl: f64, ch: f64, cw: f64,
    container_volume: f64,
    blocks: &'a [Block],
    initial_inventory: HashMap<String, i32>,
    max_weight: f64,
    corridor_manager: &'a BatchCorridorManager,
}

impl<'a> AdvancedBeamSearchSolver<'a> {
    pub fn new(
        container: &'a ContainerConfig, blocks: &'a [Block],
        inventory: &HashMap<String, i32>, max_weight: f64,
        corridor_manager: &'a BatchCorridorManager,
    ) -> Self {
        Self {
            container, cl: container.length, ch: container.height, cw: container.width,
            container_volume: container.length * container.height * container.width,
            blocks, initial_inventory: inventory.clone(), max_weight, corridor_manager,
        }
    }

    pub fn solve(&self, beam_width: usize, max_steps: usize) -> AdvancedBeamState {
        let ep_mgr = EPManager::new(self.container);
        let initial_state = AdvancedBeamState {
            placements: Vec::new(), placed_blocks: Vec::new(),
            extreme_points: ep_mgr.generate_initial(),
            inventory: self.initial_inventory.clone(),
            score: 0.0, placed_volume: 0.0, placed_weight: 0.0,
            batch_min_x: HashMap::new(), batch_max_x: HashMap::new(), batch_volume: HashMap::new(),
            cg_x: 0.0, cg_y: 0.0, cg_z: 0.0, total_weight: 0.0,
        };
        let mut beam = vec![initial_state.clone()];
        let mut best_state = initial_state;

        for _step in 0..max_steps {
            let mut new_beam: Vec<(f64, AdvancedBeamState)> = Vec::new();
            for state in &beam {
                let candidates = self.expand_state(state);
                for (score, new_state) in candidates { new_beam.push((score, new_state)); }
            }
            if new_beam.is_empty() { break; }
            new_beam.sort_by(|a, b| b.0.partial_cmp(&a.0).unwrap());
            beam = new_beam.into_iter().take(beam_width).map(|(_, s)| s).collect();
            if beam[0].placed_volume > best_state.placed_volume { best_state = beam[0].clone(); }
            if beam.iter().all(|s| s.extreme_points.is_empty() || s.inventory.values().all(|&v| v == 0)) { break; }
        }
        best_state
    }

    fn expand_state(&self, state: &AdvancedBeamState) -> Vec<(f64, AdvancedBeamState)> {
        let mut candidates: Vec<(f64, AdvancedBeamState)> = Vec::new();
        let mut detector = CollisionDetector::new(self.container);
        for p in &state.placements { detector.add(p.clone()); }
        let remaining_skus: HashMap<String, i32> = state.inventory.iter()
            .filter(|(_, &cnt)| cnt > 0).map(|(k, &v)| (k.clone(), v)).collect();
        if remaining_skus.is_empty() { return candidates; }

        let stability = StabilityEvaluator::new(self.container);
        let scoring = AdvancedScoringFunction::new(self.container);
        let ep_mgr = EPManager::new(self.container);

        for block in self.blocks {
            let remaining = remaining_skus.get(&block.sku).copied().unwrap_or(0);
            if remaining < block.count as i32 { continue; }
            if state.placed_weight + block.count as f64 * block.item_weight > self.max_weight { continue; }

            let mut best_score = f64::NEG_INFINITY;
            let mut best_ep: Option<(f64, f64, f64)> = None;

            for &ep in &state.extreme_points {
                let (ex, ey, ez) = ep;
                if ex + block.length > self.cl + 0.01 || ey + block.height > self.ch + 0.01 || ez + block.width > self.cw + 0.01 { continue; }
                if detector.check(ex, ey, ez, block.length, block.height, block.width) { continue; }
                let (support_ratio, supported) = stability.check_support(block, ex, ey, ez, &state.placements);
                if !supported { continue; }
                if block.is_fragile && OrientationManager::check_no_stack_violation(block, ex, ey, ez, &state.placements) { continue; }

                let block_center_x = ex + block.length / 2.0;
                let same_sku_ratio = calc_same_sku_contact(block, ex, ey, ez, &state.placed_blocks);
                let batch_compactness = self.corridor_manager.evaluate_batch_compactness(block.batch, block, ex, &state.placed_blocks);
                let sequence_penalty = self.corridor_manager.evaluate_sequence_penalty(block.batch, block_center_x);
                let corridor_penalty = self.corridor_manager.evaluate_corridor_penalty(block.batch, block_center_x);
                let order_violation = self.corridor_manager.evaluate_order_violation(block.batch, block_center_x, &state.placed_blocks);
                let fragmentation = (state.extreme_points.len() as f64 / MAX_EP_COUNT as f64).min(1.0);

                // 物理重心偏移预测（Block 层面，与 V1 一致）
                let new_weight = block.count as f64 * block.item_weight;
                let new_total_weight = state.total_weight + new_weight;
                let (cg_offset_x, cg_offset_z) = if new_total_weight > 0.0 {
                    let new_wx = state.cg_x * state.total_weight + (ex + block.length / 2.0) * new_weight;
                    let new_wz = state.cg_z * state.total_weight + (ez + block.width / 2.0) * new_weight;
                    let ox = if self.cl > 0.0 { (new_wx / new_total_weight - self.cl / 2.0) / (self.cl / 2.0) } else { 0.0 };
                    let oz = if self.cw > 0.0 { (new_wz / new_total_weight - self.cw / 2.0) / (self.cw / 2.0) } else { 0.0 };
                    (ox, oz)
                } else {
                    (0.0, 0.0)
                };

                let score = scoring.score(block, ex, ey, ez, support_ratio, same_sku_ratio,
                    batch_compactness, sequence_penalty, corridor_penalty, order_violation, fragmentation,
                    cg_offset_x, cg_offset_z);
                if score > best_score { best_score = score; best_ep = Some(ep); }
            }
            if let Some(ep) = best_ep {
                let new_state = self.apply_placement(state, block, ep, &ep_mgr);
                candidates.push((best_score, new_state));
            }
        }
        candidates
    }

    fn apply_placement(&self, state: &AdvancedBeamState, block: &Block, ep: (f64, f64, f64), ep_mgr: &EPManager) -> AdvancedBeamState {
        let (x, y, z) = ep;
        let mut new_placements = state.placements.clone();
        let mut new_placed_blocks = state.placed_blocks.clone();
        let mut new_inventory = state.inventory.clone();
        let mut new_batch_min_x = state.batch_min_x.clone();
        let mut new_batch_max_x = state.batch_max_x.clone();
        let mut new_batch_volume = state.batch_volume.clone();

        for i in 0..block.nx {
            for j in 0..block.ny {
                for k in 0..block.nz {
                    new_placements.push(PlacementInfo {
                        item_id: block.sku.clone(),
                        x: x + i as f64 * block.item_length, y: y + j as f64 * block.item_height, z: z + k as f64 * block.item_width,
                        l: block.item_length, h: block.item_height, w: block.item_width,
                        weight: block.item_weight, is_fragile: block.is_fragile,
                        rotation: block.rotation_label.clone(), orientation: Some(block.orientation_name.clone()),
                    });
                }
            }
        }
        let block_x2 = x + block.length;
        new_placed_blocks.push(BlockInfo {
            sku: block.sku.clone(), batch: block.batch,
            x, y, z, l: block.length, h: block.height, w: block.width,
        });
        *new_inventory.entry(block.sku.clone()).or_insert(0) -= block.count as i32;

        let batch = block.batch;
        if !new_batch_min_x.contains_key(&batch) {
            new_batch_min_x.insert(batch, x);
            new_batch_max_x.insert(batch, block_x2);
            new_batch_volume.insert(batch, block.volume);
        } else {
            if let Some(v) = new_batch_min_x.get_mut(&batch) { *v = v.min(x); }
            if let Some(v) = new_batch_max_x.get_mut(&batch) { *v = v.max(block_x2); }
            *new_batch_volume.entry(batch).or_insert(0.0) += block.volume;
        }

        let mut new_eps_raw: Vec<(f64, f64, f64)> = Vec::new();
        let mut seen: HashSet<(i64, i64, i64)> = HashSet::new();
        for &(ex, ey, ez) in &state.extreme_points {
            if x <= ex && ex < x + block.length && y <= ey && ey < y + block.height && z <= ez && ez < z + block.width { continue; }
            let key = ((ex * 100.0).round() as i64, (ey * 100.0).round() as i64, (ez * 100.0).round() as i64);
            if !seen.insert(key) { continue; }
            new_eps_raw.push((ex, ey, ez));
        }
        let new_corners = ep_mgr.generate_new_points(x, y, z, block.length, block.height, block.width);
        let mut temp_detector = CollisionDetector::new(self.container);
        for p in &new_placements { temp_detector.add(p.clone()); }
        for nep in new_corners {
            let (ex, ey, ez) = nep;
            if ex >= self.cl - 0.01 || ey >= self.ch - 0.01 || ez >= self.cw - 0.01 { continue; }
            if temp_detector.check_point(ex, ey, ez) { continue; }
            let key = ((ex * 100.0).round() as i64, (ey * 100.0).round() as i64, (ez * 100.0).round() as i64);
            if !seen.insert(key) { continue; }
            new_eps_raw.push(nep);
        }
        let new_eps = ep_mgr.prune(new_eps_raw);
        let new_placed_weight = state.placed_weight + block.count as f64 * block.item_weight;
        let new_placed_volume = state.placed_volume + block.volume;
        let new_total_weight = state.total_weight + block.count as f64 * block.item_weight;

        // 累积加权坐标（Block 层面重心，与 V1 一致）
        let (new_cg_x, new_cg_y, new_cg_z) = if new_total_weight > 0.0 {
            (
                (state.cg_x * state.total_weight + (x + block.length / 2.0) * block.count as f64 * block.item_weight) / new_total_weight,
                (state.cg_y * state.total_weight + (y + block.height / 2.0) * block.count as f64 * block.item_weight) / new_total_weight,
                (state.cg_z * state.total_weight + (z + block.width / 2.0) * block.count as f64 * block.item_weight) / new_total_weight,
            )
        } else {
            (0.0, 0.0, 0.0)
        };

        AdvancedBeamState {
            placements: new_placements, placed_blocks: new_placed_blocks,
            extreme_points: new_eps, inventory: new_inventory,
            score: if self.container_volume > 0.0 { new_placed_volume / self.container_volume } else { 0.0 },
            placed_volume: new_placed_volume, placed_weight: new_placed_weight,
            batch_min_x: new_batch_min_x, batch_max_x: new_batch_max_x, batch_volume: new_batch_volume,
            cg_x: new_cg_x, cg_y: new_cg_y, cg_z: new_cg_z, total_weight: new_total_weight,
        }
    }
}

// -- AdvancedBlockOptimizer (main entry) --
pub struct AdvancedBlockOptimizer;

impl AdvancedBlockOptimizer {
    pub fn new() -> Self { Self }

    pub fn pack(&self, container: &ContainerConfig, items: &[ItemInput]) -> Vec<PlacementInfo> {
        let generator = BlockGenerator::new(container, items);
        let all_blocks = generator.generate();
        let inventory: HashMap<String, i32> = items.iter().map(|i| (i.id.clone(), i.quantity)).collect();
        let total_items: i32 = inventory.values().sum();
        let container_volume = container.length * container.height * container.width;
        let corridor_manager = BatchCorridorManager::new(container, items);

        let greedy_result = self.greedy_pack_with_corridor(container, &all_blocks, &inventory, &corridor_manager);
        let greedy_volume: f64 = greedy_result.iter().map(|p| p.l * p.h * p.w).sum();
        let greedy_utilization = if container_volume > 0.0 { greedy_volume / container_volume } else { 0.0 };

        if total_items <= 500 && container_volume > 0.0 {
            let solver = AdvancedBeamSearchSolver::new(container, &all_blocks, &inventory, container.max_weight, &corridor_manager);
            let best_state = solver.solve(ADVANCED_BEAM_WIDTH, ADVANCED_MAX_BEAM_STEPS);
            let beam_placements = &best_state.placements;
            let beam_utilization = best_state.placed_volume / container_volume;
            if beam_placements.len() > greedy_result.len() { return best_state.placements; }
            if beam_placements.len() == greedy_result.len() && beam_utilization > greedy_utilization + 0.01 {
                return best_state.placements;
            }
        }
        greedy_result
    }

    fn greedy_pack_with_corridor(
        &self, container: &ContainerConfig, blocks: &[Block],
        initial_inventory: &HashMap<String, i32>, corridor_manager: &BatchCorridorManager,
    ) -> Vec<PlacementInfo> {
        let cl = container.length; let ch = container.height; let cw = container.width;
        let mut detector = CollisionDetector::new(container);
        let stability = StabilityEvaluator::new(container);
        let scoring = AdvancedScoringFunction::new(container);
        let ep_mgr = EPManager::new(container);

        let mut placements: Vec<PlacementInfo> = Vec::new();
        let mut placed_blocks: Vec<BlockInfo> = Vec::new();
        let mut eps = ep_mgr.generate_initial();
        let mut inventory = initial_inventory.clone();
        let mut placed_weight = 0.0;
        // 物理重心累积量（Block 层面，与 V1 一致）
        let mut cg_x = 0.0;
        let mut cg_y = 0.0;
        let mut cg_z = 0.0;
        let mut total_weight = 0.0;

        for block in blocks {
            let sku = &block.sku;
            while inventory.get(sku).copied().unwrap_or(0) >= block.count as i32 {
                if placed_weight + block.count as f64 * block.item_weight > container.max_weight { break; }
                let mut best_score = f64::NEG_INFINITY;
                let mut best_ep: Option<(f64, f64, f64)> = None;

                for &ep in &eps {
                    let (ex, ey, ez) = ep;
                    if ex + block.length > cl + 0.01 || ey + block.height > ch + 0.01 || ez + block.width > cw + 0.01 { continue; }
                    if detector.check(ex, ey, ez, block.length, block.height, block.width) { continue; }
                    let (support_ratio, supported) = stability.check_support(block, ex, ey, ez, &placements);
                    if !supported { continue; }
                    if block.is_fragile && OrientationManager::check_no_stack_violation(block, ex, ey, ez, &placements) { continue; }

                    let block_center_x = ex + block.length / 2.0;
                    let same_sku_ratio = calc_same_sku_contact(block, ex, ey, ez, &placed_blocks);
                    let batch_compactness = corridor_manager.evaluate_batch_compactness(block.batch, block, ex, &placed_blocks);
                    let sequence_penalty = corridor_manager.evaluate_sequence_penalty(block.batch, block_center_x);
                    let corridor_penalty = corridor_manager.evaluate_corridor_penalty(block.batch, block_center_x);
                    let order_violation = corridor_manager.evaluate_order_violation(block.batch, block_center_x, &placed_blocks);
                    let fragmentation = (eps.len() as f64 / MAX_EP_COUNT as f64).min(1.0);

                    // 物理重心偏移预测（Block 层面，与 V1 一致）
                    let new_weight = block.count as f64 * block.item_weight;
                    let new_total = total_weight + new_weight;
                    let (cg_offset_x, cg_offset_z) = if new_total > 0.0 {
                        let new_wx = cg_x * total_weight + (ex + block.length / 2.0) * new_weight;
                        let new_wz = cg_z * total_weight + (ez + block.width / 2.0) * new_weight;
                        let ox = if cl > 0.0 { (new_wx / new_total - cl / 2.0) / (cl / 2.0) } else { 0.0 };
                        let oz = if cw > 0.0 { (new_wz / new_total - cw / 2.0) / (cw / 2.0) } else { 0.0 };
                        (ox, oz)
                    } else {
                        (0.0, 0.0)
                    };

                    let score = scoring.score(block, ex, ey, ez, support_ratio, same_sku_ratio,
                        batch_compactness, sequence_penalty, corridor_penalty, order_violation, fragmentation,
                        cg_offset_x, cg_offset_z);
                    if score > best_score { best_score = score; best_ep = Some(ep); }
                }

                let best_ep = match best_ep { Some(e) => e, None => break };
                let (x, y, z) = best_ep;

                for i in 0..block.nx {
                    for j in 0..block.ny {
                        for k in 0..block.nz {
                            let p = PlacementInfo {
                                item_id: sku.clone(),
                                x: x + i as f64 * block.item_length, y: y + j as f64 * block.item_height, z: z + k as f64 * block.item_width,
                                l: block.item_length, h: block.item_height, w: block.item_width,
                                weight: block.item_weight, is_fragile: block.is_fragile,
                                rotation: block.rotation_label.clone(), orientation: Some(block.orientation_name.clone()),
                            };
                            placements.push(p.clone());
                            detector.add(p);
                        }
                    }
                }
                placed_blocks.push(BlockInfo {
                    sku: sku.clone(), batch: block.batch,
                    x, y, z, l: block.length, h: block.height, w: block.width,
                });
                *inventory.entry(sku.clone()).or_insert(0) -= block.count as i32;
                placed_weight += block.count as f64 * block.item_weight;

                // 更新物理重心（Block 层面累积加权坐标，与 V1 一致）
                let new_w = block.count as f64 * block.item_weight;
                if total_weight + new_w > 0.0 {
                    cg_x = (cg_x * total_weight + (x + block.length / 2.0) * new_w) / (total_weight + new_w);
                    cg_y = (cg_y * total_weight + (y + block.height / 2.0) * new_w) / (total_weight + new_w);
                    cg_z = (cg_z * total_weight + (z + block.width / 2.0) * new_w) / (total_weight + new_w);
                }
                total_weight += new_w;

                let new_corners = ep_mgr.generate_new_points(x, y, z, block.length, block.height, block.width);
                let mut seen: HashSet<(i64, i64, i64)> = HashSet::new();
                let mut filtered: Vec<(f64, f64, f64)> = Vec::new();
                for &(ex, ey, ez) in &eps {
                    if x <= ex && ex < x + block.length && y <= ey && ey < y + block.height && z <= ez && ez < z + block.width { continue; }
                    let key = ((ex * 100.0).round() as i64, (ey * 100.0).round() as i64, (ez * 100.0).round() as i64);
                    if !seen.insert(key) { continue; }
                    filtered.push((ex, ey, ez));
                }
                for nep in new_corners {
                    let (ex, ey, ez) = nep;
                    if ex >= cl - 0.01 || ey >= ch - 0.01 || ez >= cw - 0.01 { continue; }
                    if detector.check_point(ex, ey, ez) { continue; }
                    let key = ((ex * 100.0).round() as i64, (ey * 100.0).round() as i64, (ez * 100.0).round() as i64);
                    if !seen.insert(key) { continue; }
                    filtered.push(nep);
                }
                eps = ep_mgr.prune(filtered);
            }
        }
        placements
    }
}
