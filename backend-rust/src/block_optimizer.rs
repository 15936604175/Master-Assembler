/// V1 Block Packing 引擎
/// 基于 Block Packing + Extreme Point + Beam Search + 物理稳定性评估

use std::collections::{HashMap, HashSet};
use crate::models::{
    Block, BlockInfo, BeamState, ContainerConfig, ItemInput, PlacementInfo,
};
use crate::rotation::get_allowed_orientations;

// ── 常量配置 ──────────────────────────────────────────────────
const MAX_NX: usize = 6;
const MAX_NY: usize = 4;
const MAX_NZ: usize = 6;
const MAX_BLOCK_VOLUME_RATIO: f64 = 0.5;
const MAX_BLOCKS_PER_SKU: usize = 200;
pub const MAX_EP_COUNT: usize = 600;
pub const SUPPORT_THRESHOLD: f64 = 0.5;
pub const VERTICAL_TOLERANCE: f64 = 1.0;
const CG_OFFSET_RATIO: f64 = 0.35;
pub const FRAGILE_SAFETY_RATIO: f64 = 0.7;
const BEAM_WIDTH: usize = 10;
const MAX_BEAM_STEPS: usize = 200;
const GRID_CELL_DIV: f64 = 10.0;

// ── BlockGenerator ────────────────────────────────────────────
pub struct BlockGenerator<'a> {
    container: &'a ContainerConfig,
    container_volume: f64,
    items: &'a [ItemInput],
}

impl<'a> BlockGenerator<'a> {
    pub fn new(container: &'a ContainerConfig, items: &'a [ItemInput]) -> Self {
        let container_volume = container.length * container.height * container.width;
        Self { container, container_volume, items }
    }

    pub fn generate(&self) -> Vec<Block> {
        let mut all_blocks: Vec<Block> = Vec::new();
        for item in self.items {
            let mut sku_blocks = self.generate_for_sku(item);
            sku_blocks.sort_by(|a, b| b.quality_score.partial_cmp(&a.quality_score).unwrap());
            let top_k: Vec<Block> = sku_blocks.iter().take(MAX_BLOCKS_PER_SKU).cloned().collect();
            let small_blocks: Vec<Block> = sku_blocks
                .iter()
                .skip(MAX_BLOCKS_PER_SKU)
                .filter(|b| b.count <= 4)
                .cloned()
                .collect();
            all_blocks.extend(top_k);
            all_blocks.extend(small_blocks);
        }
        all_blocks.sort_by(|a, b| {
            let va = a.item_length * a.item_height * a.item_width;
            let vb = b.item_length * b.item_height * b.item_width;
            vb.partial_cmp(&va).unwrap().then(b.quality_score.partial_cmp(&a.quality_score).unwrap())
        });
        all_blocks
    }

    fn generate_for_sku(&self, item: &ItemInput) -> Vec<Block> {
        let count = item.quantity as usize;
        if count == 0 { return Vec::new(); }

        let orientations = get_allowed_orientations(
            item.length, item.width, item.height,
            &item.forbidden_horizontal_dims,
        );
        let orientations = if orientations.is_empty() {
            vec![((item.length, item.width, item.height), "lwh".to_string(), "height_vertical".to_string())]
        } else {
            orientations
        };

        let mut sku_blocks: Vec<Block> = Vec::new();
        let mut seen: HashSet<(i64, i64, i64, usize)> = HashSet::new();
        let batch = item.batch_number;

        for ((rot_l, rot_w, rot_h), rot_label, orient_name) in &orientations {
            let max_nx = if *rot_l > 0.0 {
                MAX_NX.min((self.container.length / rot_l) as usize)
            } else { 1 };
            let max_ny = if *rot_h > 0.0 {
                MAX_NY.min((self.container.height / rot_h) as usize)
            } else { 1 };
            let max_nz = if *rot_w > 0.0 {
                MAX_NZ.min((self.container.width / rot_w) as usize)
            } else { 1 };

            for nx in 1..=max_nx {
                for ny in 1..=max_ny {
                    for nz in 1..=max_nz {
                        let block_count = nx * ny * nz;
                        if block_count > count { continue; }
                        let bl = nx as f64 * rot_l;
                        let bh = ny as f64 * rot_h;
                        let bw = nz as f64 * rot_w;
                        let bvol = bl * bh * bw;
                        if bvol > self.container_volume * MAX_BLOCK_VOLUME_RATIO { continue; }
                        let key = (
                            (bl * 10.0).round() as i64,
                            (bh * 10.0).round() as i64,
                            (bw * 10.0).round() as i64,
                            block_count,
                        );
                        if !seen.insert(key) { continue; }
                        let quality = Self::score_block(bl, bh, bw, bvol);
                        sku_blocks.push(Block {
                            sku: item.id.clone(),
                            batch,
                            nx, ny, nz,
                            length: bl, height: bh, width: bw,
                            volume: bvol, count: block_count,
                            item_length: *rot_l, item_height: *rot_h, item_width: *rot_w,
                            item_weight: item.weight,
                            is_fragile: item.is_fragile,
                            rotation_label: rot_label.clone(),
                            orientation_name: orient_name.clone(),
                            quality_score: quality,
                        });
                    }
                }
            }
        }
        sku_blocks
    }

    fn score_block(length: f64, height: f64, width: f64, volume: f64) -> f64 {
        let dims = [length, height, width];
        let max_dim = dims.iter().cloned().fold(f64::NEG_INFINITY, f64::max);
        let min_dim = dims.iter().cloned().fold(f64::INFINITY, f64::min);
        let compactness = if max_dim > 0.0 { min_dim / max_dim } else { 0.0 };
        volume * (0.4 + 0.6 * compactness)
    }
}

// ── OrientationManager ────────────────────────────────────────
pub struct OrientationManager;

impl OrientationManager {
    pub fn is_no_stack(block: &Block) -> bool { block.is_fragile }

    pub fn check_no_stack_violation(
        block: &Block, x: f64, y: f64, z: f64,
        existing: &[PlacementInfo],
    ) -> bool {
        if !block.is_fragile { return false; }
        let x2 = x + block.length;
        let y2 = y + block.height;
        let z2 = z + block.width;
        for p in existing {
            if p.y < y2 - VERTICAL_TOLERANCE { continue; }
            if p.y < y2 { continue; }
            if x < p.x + p.l && x2 > p.x && z < p.z + p.w && z2 > p.z {
                return true;
            }
        }
        false
    }
}

// ── FragileConstraint ─────────────────────────────────────────
pub struct FragileConstraint;

impl FragileConstraint {
    pub fn check(
        block: &Block, x: f64, y: f64, z: f64,
        support_ratio: f64, existing: &[PlacementInfo],
    ) -> (f64, bool, String) {
        if !block.is_fragile {
            return Self::check_pressing_fragile(
                x, y, z, block.length, block.height, block.width,
                block.item_weight * block.count as f64, existing,
            );
        }
        let mut reasons = Vec::new();
        let mut score = 1.0;
        if support_ratio < FRAGILE_SAFETY_RATIO {
            score -= 0.5;
            reasons.push(format!("易碎品支撑率不足: {:.2}%", support_ratio * 100.0));
        }
        let (_, safe, r) = Self::check_pressing_fragile(
            x, y, z, block.length, block.height, block.width,
            block.item_weight * block.count as f64, existing,
        );
        if !safe {
            score -= 0.3;
            reasons.push(r);
        }
        (score, score > 0.5, reasons.join("; "))
    }

    pub fn check_pressing_fragile(
        x: f64, y: f64, z: f64,
        l: f64, h: f64, w: f64, weight: f64,
        existing: &[PlacementInfo],
    ) -> (f64, bool, String) {
        let x2 = x + l;
        let z2 = z + w;
        let mut penalty = 0.0;
        let mut reason = String::new();
        for p in existing {
            if !p.is_fragile { continue; }
            if (y - (p.y + p.h)).abs() > VERTICAL_TOLERANCE { continue; }
            let overlap_x = (x2.min(p.x + p.l) - x.max(p.x)).max(0.0);
            let overlap_z = (z2.min(p.z + p.w) - z.max(p.z)).max(0.0);
            let overlap_area = overlap_x * overlap_z;
            let fragile_area = p.l * p.w;
            if overlap_area > 0.0 && fragile_area > 0.0 {
                let coverage = overlap_area / fragile_area;
                if coverage > 0.1 {
                    penalty += coverage * (weight / 100.0);
                    reason = format!("压在易碎品上方 (覆盖率 {:.1}%)", coverage * 100.0);
                }
            }
        }
        let safety = (1.0 - penalty).max(0.0);
        (safety, safety > 0.7, reason)
    }
}

// ── BatchManager ──────────────────────────────────────────────
pub struct BatchManager {
    cl: f64,
    ch: f64,
    cw: f64,
}

impl BatchManager {
    pub fn new(container: &ContainerConfig) -> Self {
        Self { cl: container.length, ch: container.height, cw: container.width }
    }

    pub fn evaluate_batch_placement(&self, block: &Block, x: f64, y: f64, _z: f64) -> f64 {
        let batch = block.batch;
        let x2 = x + block.length;
        if batch == 0 {
            let dist_from_back = self.cl - x2;
            let normalized = 1.0 - (dist_from_back / self.cl.max(1.0)).min(1.0);
            0.6 * normalized
                + 0.2 * if _z <= 0.01 || _z + block.width >= self.cw - 0.01 { 1.0 } else { 0.0 }
                + 0.2 * if y <= 0.01 { 1.0 } else { 0.0 }
        } else if batch == 1 {
            let center = self.cl / 2.0;
            let block_center = x + block.length / 2.0;
            let dist = (block_center - center).abs();
            1.0 - (dist / (self.cl / 2.0)).min(1.0)
        } else {
            1.0 - (x / self.cl.max(1.0)).min(1.0)
        }
    }
}

// ── EPManager ─────────────────────────────────────────────────
pub struct EPManager {
    cl: f64,
    ch: f64,
    cw: f64,
}

impl EPManager {
    pub fn new(container: &ContainerConfig) -> Self {
        Self { cl: container.length, ch: container.height, cw: container.width }
    }

    pub fn generate_initial(&self) -> Vec<(f64, f64, f64)> {
        let mut eps = vec![(0.0, 0.0, 0.0)];
        let step_x = (self.cl / 10.0).max(300.0);
        let step_z = (self.cw / 10.0).max(300.0);
        let mut x = step_x;
        while x < self.cl {
            let mut z = step_z;
            while z < self.cw {
                eps.push((x, 0.0, z));
                z += step_z;
            }
            x += step_x;
        }
        eps
    }

    pub fn generate_new_points(&self, x: f64, y: f64, z: f64, l: f64, h: f64, w: f64) -> Vec<(f64, f64, f64)> {
        vec![
            (x + l, y, z), (x, y + h, z), (x, y, z + w),
            (x + l, y, z + w), (x + l, y + h, z), (x, y + h, z + w),
        ]
    }

    pub fn prune(&self, eps: Vec<(f64, f64, f64)>) -> Vec<(f64, f64, f64)> {
        let valid: Vec<(f64, f64, f64)> = eps.into_iter()
            .filter(|(x, y, z)| *x < self.cl - 0.01 && *y < self.ch - 0.01 && *z < self.cw - 0.01)
            .collect();
        if valid.len() <= MAX_EP_COUNT { return valid; }

        let mut floor_eps: Vec<_> = valid.iter().filter(|e| e.1 <= 1.0).cloned().collect();
        let mut non_floor_eps: Vec<_> = valid.iter().filter(|e| e.1 > 1.0).cloned().collect();

        let floor_quota = MAX_EP_COUNT / 2;
        let mut non_floor_quota = MAX_EP_COUNT - floor_quota;
        let mut actual_floor_quota = floor_quota;

        if floor_eps.len() <= floor_quota {
            non_floor_quota = MAX_EP_COUNT - floor_eps.len();
        } else if non_floor_eps.len() <= non_floor_quota {
            actual_floor_quota = MAX_EP_COUNT - non_floor_eps.len();
        }

        if floor_eps.len() > actual_floor_quota {
            floor_eps.sort_by(|a, b| a.0.partial_cmp(&b.0).unwrap().then(a.2.partial_cmp(&b.2).unwrap()));
            let step = (floor_eps.len() / actual_floor_quota).max(1);
            floor_eps = floor_eps.into_iter().step_by(step).take(actual_floor_quota).collect();
        }
        if non_floor_eps.len() > non_floor_quota {
            non_floor_eps.sort_by(|a, b| {
                a.1.partial_cmp(&b.1).unwrap()
                    .then(a.0.partial_cmp(&b.0).unwrap())
                    .then(a.2.partial_cmp(&b.2).unwrap())
            });
            let step = (non_floor_eps.len() / non_floor_quota).max(1);
            non_floor_eps = non_floor_eps.into_iter().step_by(step).take(non_floor_quota).collect();
        }
        floor_eps.into_iter().chain(non_floor_eps).collect()
    }
}

// ── CollisionDetector ─────────────────────────────────────────
pub struct CollisionDetector {
    cell_size: f64,
    grid: HashMap<(i32, i32, i32), Vec<usize>>,
    visit_version: u64,
    visits: Vec<u64>,
    placements: Vec<PlacementInfo>,
}

impl CollisionDetector {
    pub fn new(container: &ContainerConfig) -> Self {
        let cell_size = (container.length.max(container.height).max(container.width) / GRID_CELL_DIV).max(50.0);
        Self { cell_size, grid: HashMap::new(), visit_version: 0, visits: Vec::new(), placements: Vec::new() }
    }

    pub fn empty(cell_size: f64) -> Self {
        Self { cell_size, grid: HashMap::new(), visit_version: 0, visits: Vec::new(), placements: Vec::new() }
    }

    pub fn add(&mut self, p: PlacementInfo) {
        let idx = self.placements.len();
        let x = p.x; let y = p.y; let z = p.z;
        let x2 = x + p.l; let y2 = y + p.h; let z2 = z + p.w;
        self.placements.push(p);
        self.visits.push(0);
        let cs = self.cell_size;
        for gx in (x / cs).floor() as i32..=((x2 / cs).floor() as i32) {
            for gy in (y / cs).floor() as i32..=((y2 / cs).floor() as i32) {
                for gz in (z / cs).floor() as i32..=((z2 / cs).floor() as i32) {
                    self.grid.entry((gx, gy, gz)).or_default().push(idx);
                }
            }
        }
    }

    pub fn check(&mut self, x: f64, y: f64, z: f64, l: f64, h: f64, w: f64) -> bool {
        let x2 = x + l; let y2 = y + h; let z2 = z + w;
        let cs = self.cell_size;
        self.visit_version += 1;
        let ver = self.visit_version;
        for gx in (x / cs).floor() as i32..=((x2 / cs).floor() as i32) {
            for gy in (y / cs).floor() as i32..=((y2 / cs).floor() as i32) {
                for gz in (z / cs).floor() as i32..=((z2 / cs).floor() as i32) {
                    let indices: Vec<usize> = self.grid.get(&(gx, gy, gz)).cloned().unwrap_or_default();
                    for idx in indices {
                        if self.visits[idx] == ver { continue; }
                        self.visits[idx] = ver;
                        let p = &self.placements[idx];
                        if x < p.x + p.l && x2 > p.x && y < p.y + p.h && y2 > p.y && z < p.z + p.w && z2 > p.z {
                            return true;
                        }
                    }
                }
            }
        }
        false
    }

    pub fn check_point(&mut self, x: f64, y: f64, z: f64) -> bool {
        let cs = self.cell_size;
        self.visit_version += 1;
        let ver = self.visit_version;
        let gx = (x / cs).floor() as i32;
        let gy = (y / cs).floor() as i32;
        let gz = (z / cs).floor() as i32;
        let indices: Vec<usize> = self.grid.get(&(gx, gy, gz)).cloned().unwrap_or_default();
        for idx in indices {
            if self.visits[idx] == ver { continue; }
            self.visits[idx] = ver;
            let p = &self.placements[idx];
            if p.x <= x && x < p.x + p.l && p.y <= y && y < p.y + p.h && p.z <= z && z < p.z + p.w {
                return true;
            }
        }
        false
    }
}

// ── StabilityEvaluator ────────────────────────────────────────
pub struct StabilityEvaluator {
    cl: f64,
    ch: f64,
    cw: f64,
}

impl StabilityEvaluator {
    pub fn new(container: &ContainerConfig) -> Self {
        Self { cl: container.length, ch: container.height, cw: container.width }
    }

    pub fn calc_support_ratio(&self, x: f64, y: f64, z: f64, l: f64, h: f64, w: f64, placements: &[PlacementInfo]) -> f64 {
        if y <= VERTICAL_TOLERANCE { return 1.0; }
        let item_footprint = l * w;
        if item_footprint <= 0.0 { return 0.0; }
        let mut supported_area = 0.0;
        let x2 = x + l; let z2 = z + w;
        for p in placements {
            let p_top = p.y + p.h;
            if (p_top - y).abs() > VERTICAL_TOLERANCE { continue; }
            let ox = (x2.min(p.x + p.l) - x.max(p.x)).max(0.0);
            let oz = (z2.min(p.z + p.w) - z.max(p.z)).max(0.0);
            supported_area += ox * oz;
        }
        supported_area / item_footprint
    }

    pub fn check_support(&self, block: &Block, x: f64, y: f64, z: f64, placements: &[PlacementInfo]) -> (f64, bool) {
        let ratio = self.calc_support_ratio(x, y, z, block.length, block.height, block.width, placements);
        let threshold = if block.is_fragile { FRAGILE_SAFETY_RATIO } else { SUPPORT_THRESHOLD };
        if ratio < threshold { return (ratio, false); }
        if y > VERTICAL_TOLERANCE && block.count > 1 {
            if !self.check_no_floating_items(block, x, y, z, placements) {
                return (ratio, false);
            }
        }
        (ratio, true)
    }

    fn check_no_floating_items(&self, block: &Block, x: f64, y: f64, z: f64, placements: &[PlacementInfo]) -> bool {
        let il = block.item_length;
        let iw = block.item_width;
        for ix in 0..block.nx {
            for iz in 0..block.nz {
                let sx = x + ix as f64 * il;
                let sz = z + iz as f64 * iw;
                let sx2 = sx + il;
                let sz2 = sz + iw;
                let mut supported_area = 0.0;
                for p in placements {
                    let p_top = p.y + p.h;
                    if (p_top - y).abs() > VERTICAL_TOLERANCE { continue; }
                    let ox = (sx2.min(p.x + p.l) - sx.max(p.x)).max(0.0);
                    let oz = (sz2.min(p.z + p.w) - sz.max(p.z)).max(0.0);
                    supported_area += ox * oz;
                }
                let item_area = il * iw;
                let item_ratio = if item_area > 0.0 { supported_area / item_area } else { 0.0 };
                if item_ratio < SUPPORT_THRESHOLD { return false; }
            }
        }
        true
    }

    pub fn calc_cg_offset(&self, total_weight: f64, weighted_x: f64, weighted_y: f64, weighted_z: f64) -> (f64, f64, f64) {
        if total_weight <= 0.0 { return (0.0, 0.0, 0.0); }
        let cg_x = weighted_x / total_weight;
        let cg_y = weighted_y / total_weight;
        let cg_z = weighted_z / total_weight;
        let offset_x = if self.cl > 0.0 { (cg_x - self.cl / 2.0) / (self.cl / 2.0) } else { 0.0 };
        let offset_y = if self.ch > 0.0 { (cg_y - self.ch / 2.0) / (self.ch / 2.0) } else { 0.0 };
        let offset_z = if self.cw > 0.0 { (cg_z - self.cw / 2.0) / (self.cw / 2.0) } else { 0.0 };
        (offset_x, offset_y, offset_z)
    }

    pub fn cg_score(&self, offset_x: f64, offset_y: f64, offset_z: f64) -> f64 {
        let euclidean = (offset_x.powi(2) + offset_y.powi(2) + offset_z.powi(2)).sqrt();
        let normalized = euclidean / 3.0_f64.sqrt();
        (1.0 - normalized * 1.5).max(0.0)
    }

    pub fn is_cg_stable(&self, offset_x: f64, offset_z: f64) -> bool {
        offset_x.abs() <= CG_OFFSET_RATIO && offset_z.abs() <= CG_OFFSET_RATIO
    }
}

// ── ScoringFunction ───────────────────────────────────────────
pub struct ScoringFunction {
    cl: f64,
    ch: f64,
    cw: f64,
    container_volume: f64,
}

impl ScoringFunction {
    pub fn new(container: &ContainerConfig) -> Self {
        Self {
            cl: container.length,
            ch: container.height,
            cw: container.width,
            container_volume: container.length * container.height * container.width,
        }
    }

    pub fn score(
        &self, block: &Block, x: f64, y: f64, _z: f64,
        support_ratio: f64, same_sku_ratio: f64,
        cg_offset_x: f64, cg_offset_z: f64,
        fragile_penalty: f64, batch_score: f64, _is_fragile: bool,
    ) -> f64 {
        let s_support = support_ratio * 100.0;
        let mut wall_contact = 0.0;
        if x <= 0.01 || x + block.length >= self.cl - 0.01 { wall_contact += 1.0; }
        if _z <= 0.01 || _z + block.width >= self.cw - 0.01 { wall_contact += 1.0; }
        if y <= 0.01 { wall_contact += 1.0; }
        let s_wall = wall_contact / 3.0 * 50.0;
        let s_cluster = same_sku_ratio * 80.0;
        let s_volume = if self.container_volume > 0.0 { block.volume / self.container_volume * 200.0 } else { 0.0 };
        let s_floor = if y <= VERTICAL_TOLERANCE { 30.0 } else { 0.0 };
        let cg_penalty = (cg_offset_x.abs() + cg_offset_z.abs()) * 20.0;
        let s_fragile = -fragile_penalty * 150.0;
        let s_batch = batch_score * 60.0;
        s_support + s_wall + s_cluster + s_volume + s_floor - cg_penalty + s_fragile + s_batch
    }
}

// ── Helper: calc_same_sku_contact ─────────────────────────────
pub fn calc_same_sku_contact(
    block: &Block, x: f64, y: f64, z: f64, placed_blocks: &[BlockInfo],
) -> f64 {
    if placed_blocks.is_empty() { return 0.0; }
    let bl = block.length; let bh = block.height; let bw = block.width;
    let mut contact_area = 0.0;
    for pb in placed_blocks {
        if pb.sku != block.sku { continue; }
        let px = pb.x; let py = pb.y; let pz = pb.z;
        let pl = pb.l; let ph = pb.h; let pw = pb.w;
        if (x - (px + pl)).abs() < VERTICAL_TOLERANCE || ((x + bl) - px).abs() < VERTICAL_TOLERANCE {
            let oy = ((y + bh).min(py + ph) - y.max(py)).max(0.0);
            let oz = ((z + bw).min(pz + pw) - z.max(pz)).max(0.0);
            contact_area += oy * oz;
        }
        if (y - (py + ph)).abs() < VERTICAL_TOLERANCE || ((y + bh) - py).abs() < VERTICAL_TOLERANCE {
            let ox = ((x + bl).min(px + pl) - x.max(px)).max(0.0);
            let oz = ((z + bw).min(pz + pw) - z.max(pz)).max(0.0);
            contact_area += ox * oz;
        }
        if (z - (pz + pw)).abs() < VERTICAL_TOLERANCE || ((z + bw) - pz).abs() < VERTICAL_TOLERANCE {
            let ox = ((x + bl).min(px + pl) - x.max(px)).max(0.0);
            let oy = ((y + bh).min(py + ph) - y.max(py)).max(0.0);
            contact_area += ox * oy;
        }
    }
    let surface = 2.0 * (bl * bh + bl * bw + bh * bw);
    if surface > 0.0 { (contact_area / surface).min(1.0) } else { 0.0 }
}

// -- BeamSearchSolver --
pub struct BeamSearchSolver<'a> {
    container: &'a ContainerConfig,
    cl: f64, ch: f64, cw: f64,
    container_volume: f64,
    blocks: &'a [Block],
    initial_inventory: HashMap<String, i32>,
    max_weight: f64,
}

impl<'a> BeamSearchSolver<'a> {
    pub fn new(
        container: &'a ContainerConfig, blocks: &'a [Block],
        inventory: &HashMap<String, i32>, max_weight: f64,
    ) -> Self {
        Self {
            container, cl: container.length, ch: container.height, cw: container.width,
            container_volume: container.length * container.height * container.width,
            blocks, initial_inventory: inventory.clone(), max_weight,
        }
    }

    pub fn solve(&self, beam_width: usize, max_steps: usize) -> BeamState {
        let ep_mgr = EPManager::new(self.container);
        let initial_state = BeamState {
            placements: Vec::new(), placed_blocks: Vec::new(),
            extreme_points: ep_mgr.generate_initial(),
            inventory: self.initial_inventory.clone(),
            score: 0.0, placed_volume: 0.0, placed_weight: 0.0,
            cg_x: 0.0, cg_y: 0.0, cg_z: 0.0, total_weight: 0.0,
        };
        let mut beam = vec![initial_state.clone()];
        let mut best_state = initial_state;

        for _step in 0..max_steps {
            let mut new_beam: Vec<(f64, BeamState)> = Vec::new();
            for state in &beam {
                let candidates = self.expand_state(state);
                for (score, new_state) in candidates {
                    new_beam.push((score, new_state));
                }
            }
            if new_beam.is_empty() { break; }
            new_beam.sort_by(|a, b| b.0.partial_cmp(&a.0).unwrap());
            beam = new_beam.into_iter().take(beam_width).map(|(_, s)| s).collect();
            if beam[0].placed_volume > best_state.placed_volume {
                best_state = beam[0].clone();
            }
            if beam.iter().all(|s| {
                s.extreme_points.is_empty() || s.inventory.values().all(|&v| v == 0)
            }) { break; }
        }
        best_state
    }

    fn expand_state(&self, state: &BeamState) -> Vec<(f64, BeamState)> {
        let mut candidates: Vec<(f64, BeamState)> = Vec::new();
        let mut detector = CollisionDetector::new(self.container);
        for p in &state.placements { detector.add(p.clone()); }

        let remaining_skus: HashMap<String, i32> = state.inventory.iter()
            .filter(|(_, &cnt)| cnt > 0).map(|(k, &v)| (k.clone(), v)).collect();
        if remaining_skus.is_empty() { return candidates; }

        let stability = StabilityEvaluator::new(self.container);
        let scoring = ScoringFunction::new(self.container);
        let batch_mgr = BatchManager::new(self.container);
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

                let same_sku_ratio = calc_same_sku_contact(block, ex, ey, ez, &state.placed_blocks);
                let new_weight = block.count as f64 * block.item_weight;
                let new_total = state.total_weight + new_weight;
                let (offset_x, offset_z) = if new_total > 0.0 {
                    let wx = state.cg_x * state.total_weight + (ex + block.length / 2.0) * new_weight;
                    let wz = state.cg_z * state.total_weight + (ez + block.width / 2.0) * new_weight;
                    let ox = if self.cl > 0.0 { (wx / new_total - self.cl / 2.0) / (self.cl / 2.0) } else { 0.0 };
                    let oz = if self.cw > 0.0 { (wz / new_total - self.cw / 2.0) / (self.cw / 2.0) } else { 0.0 };
                    (ox, oz)
                } else { (0.0, 0.0) };

                let frag_penalty = if block.is_fragile { 0.0 } else {
                    let (fs, _, _) = FragileConstraint::check_pressing_fragile(
                        ex, ey, ez, block.length, block.height, block.width, new_weight, &state.placements);
                    1.0 - fs
                };
                let batch_score = batch_mgr.evaluate_batch_placement(block, ex, ey, ez);
                let score = scoring.score(block, ex, ey, ez, support_ratio, same_sku_ratio, offset_x, offset_z, frag_penalty, batch_score, block.is_fragile);
                if score > best_score { best_score = score; best_ep = Some(ep); }
            }

            if let Some(ep) = best_ep {
                let new_state = self.apply_placement(state, block, ep, &ep_mgr);
                candidates.push((best_score, new_state));
            }
        }
        candidates
    }

    fn apply_placement(&self, state: &BeamState, block: &Block, ep: (f64, f64, f64), ep_mgr: &EPManager) -> BeamState {
        let (x, y, z) = ep;
        let mut new_placements = state.placements.clone();
        let mut new_placed_blocks = state.placed_blocks.clone();
        let mut new_inventory = state.inventory.clone();

        for i in 0..block.nx {
            for j in 0..block.ny {
                for k in 0..block.nz {
                    new_placements.push(PlacementInfo {
                        item_id: block.sku.clone(),
                        x: x + i as f64 * block.item_length,
                        y: y + j as f64 * block.item_height,
                        z: z + k as f64 * block.item_width,
                        l: block.item_length, h: block.item_height, w: block.item_width,
                        weight: block.item_weight, is_fragile: block.is_fragile,
                        rotation: block.rotation_label.clone(),
                        orientation: Some(block.orientation_name.clone()),
                    });
                }
            }
        }
        new_placed_blocks.push(BlockInfo {
            sku: block.sku.clone(), batch: block.batch,
            x, y, z, l: block.length, h: block.height, w: block.width,
        });
        *new_inventory.entry(block.sku.clone()).or_insert(0) -= block.count as i32;

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
        let (new_cg_x, new_cg_y, new_cg_z) = if new_total_weight > 0.0 {
            (
                (state.cg_x * state.total_weight + (x + block.length / 2.0) * block.count as f64 * block.item_weight) / new_total_weight,
                (state.cg_y * state.total_weight + (y + block.height / 2.0) * block.count as f64 * block.item_weight) / new_total_weight,
                (state.cg_z * state.total_weight + (z + block.width / 2.0) * block.count as f64 * block.item_weight) / new_total_weight,
            )
        } else { (0.0, 0.0, 0.0) };
        let new_score = if self.container_volume > 0.0 { new_placed_volume / self.container_volume } else { 0.0 };

        BeamState {
            placements: new_placements, placed_blocks: new_placed_blocks,
            extreme_points: new_eps, inventory: new_inventory,
            score: new_score, placed_volume: new_placed_volume, placed_weight: new_placed_weight,
            cg_x: new_cg_x, cg_y: new_cg_y, cg_z: new_cg_z, total_weight: new_total_weight,
        }
    }
}

// -- BlockOptimizer (main entry) --
pub struct BlockOptimizer;

impl BlockOptimizer {
    pub fn new() -> Self { Self }

    pub fn pack(&self, container: &ContainerConfig, items: &[ItemInput]) -> Vec<PlacementInfo> {
        let generator = BlockGenerator::new(container, items);
        let all_blocks = generator.generate();
        let inventory: HashMap<String, i32> = items.iter().map(|i| (i.id.clone(), i.quantity)).collect();
        let total_items: i32 = inventory.values().sum();
        let container_volume = container.length * container.height * container.width;

        let greedy_result = self.greedy_pack(container, &all_blocks, &inventory);
        let greedy_volume: f64 = greedy_result.iter().map(|p| p.l * p.h * p.w).sum();
        let greedy_utilization = if container_volume > 0.0 { greedy_volume / container_volume } else { 0.0 };

        if total_items <= 300 && container_volume > 0.0 {
            let solver = BeamSearchSolver::new(container, &all_blocks, &inventory, container.max_weight);
            let best_state = solver.solve(5, 100);
            let beam_utilization = best_state.placed_volume / container_volume;
            if beam_utilization > greedy_utilization + 0.01 {
                return best_state.placements;
            }
        }
        greedy_result
    }

    fn greedy_pack(
        &self, container: &ContainerConfig,
        blocks: &[Block], initial_inventory: &HashMap<String, i32>,
    ) -> Vec<PlacementInfo> {
        let cl = container.length; let ch = container.height; let cw = container.width;
        let mut detector = CollisionDetector::new(container);
        let stability = StabilityEvaluator::new(container);
        let scoring = ScoringFunction::new(container);
        let batch_mgr = BatchManager::new(container);
        let ep_mgr = EPManager::new(container);

        let mut placements: Vec<PlacementInfo> = Vec::new();
        let mut placed_blocks: Vec<BlockInfo> = Vec::new();
        let mut eps = ep_mgr.generate_initial();
        let mut inventory = initial_inventory.clone();
        let mut placed_weight = 0.0;
        let mut total_weight = 0.0;
        let mut cg_x = 0.0; let mut cg_y = 0.0; let mut cg_z = 0.0;

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

                    let same_sku_ratio = calc_same_sku_contact(block, ex, ey, ez, &placed_blocks);
                    let new_weight = block.count as f64 * block.item_weight;
                    let new_total = total_weight + new_weight;
                    let (offset_x, offset_z) = if new_total > 0.0 {
                        let ox = (cg_x * total_weight + (ex + block.length / 2.0) * new_weight) / new_total;
                        let oz_val = (cg_z * total_weight + (ez + block.width / 2.0) * new_weight) / new_total;
                        (
                            if cl > 0.0 { (ox - cl / 2.0) / (cl / 2.0) } else { 0.0 },
                            if cw > 0.0 { (oz_val - cw / 2.0) / (cw / 2.0) } else { 0.0 },
                        )
                    } else { (0.0, 0.0) };

                    let frag_pen = if block.is_fragile { 0.0 } else {
                        let (fs, _, _) = FragileConstraint::check_pressing_fragile(
                            ex, ey, ez, block.length, block.height, block.width, new_weight, &placements);
                        1.0 - fs
                    };
                    let batch_score = batch_mgr.evaluate_batch_placement(block, ex, ey, ez);
                    let score = scoring.score(block, ex, ey, ez, support_ratio, same_sku_ratio, offset_x, offset_z, frag_pen, batch_score, block.is_fragile);
                    if score > best_score { best_score = score; best_ep = Some(ep); }
                }

                let best_ep = match best_ep { Some(e) => e, None => break };
                let (x, y, z) = best_ep;

                for i in 0..block.nx {
                    for j in 0..block.ny {
                        for k in 0..block.nz {
                            let p = PlacementInfo {
                                item_id: sku.clone(),
                                x: x + i as f64 * block.item_length,
                                y: y + j as f64 * block.item_height,
                                z: z + k as f64 * block.item_width,
                                l: block.item_length, h: block.item_height, w: block.item_width,
                                weight: block.item_weight, is_fragile: block.is_fragile,
                                rotation: block.rotation_label.clone(),
                                orientation: Some(block.orientation_name.clone()),
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
                let new_w = block.count as f64 * block.item_weight;
                placed_weight += new_w;
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
