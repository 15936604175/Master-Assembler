/// 可行性验证器模块

use crate::extreme_point::{check_overlap, check_support, VERTICAL_TOLERANCE, SUPPORT_THRESHOLD_EP};
use crate::models::{ContainerConfig, ItemInput, PlacementInfo, VerificationReport};
use crate::rotation::orientation_vertical_dim;
use std::collections::HashMap;

pub struct FeasibilityVerifier {
    container: ContainerConfig,
    container_dims: (f64, f64, f64),
    max_weight: f64,
    item_specs: HashMap<String, ItemSpec>,
}

struct ItemSpec {
    is_fragile: bool,
    forbidden_horizontal_dims: Vec<String>,
}

impl FeasibilityVerifier {
    pub fn new(container: &ContainerConfig, items: &[ItemInput]) -> Self {
        let mut item_specs = HashMap::new();
        for item in items {
            item_specs.insert(
                item.id.clone(),
                ItemSpec {
                    is_fragile: item.is_fragile,
                    forbidden_horizontal_dims: item.forbidden_horizontal_dims.clone(),
                },
            );
        }
        FeasibilityVerifier {
            container: container.clone(),
            container_dims: (container.length, container.height, container.width),
            max_weight: container.max_weight,
            item_specs,
        }
    }

    pub fn verify(&self, placements: &[PlacementInfo]) -> VerificationReport {
        let mut report = VerificationReport {
            is_feasible: true,
            geometry_ok: true,
            physics_ok: true,
            orientation_ok: true,
            stability_score: 0.0,
            support_score: 0.0,
            cg_deviation_ratio: 0.0,
            fragile_violations: 0,
            orientation_violations: 0,
            messages: Vec::new(),
        };

        if placements.is_empty() {
            report.messages.push("空方案，视为可行".to_string());
            return report;
        }

        let (geometry_ok, geom_msgs) = self.verify_geometry(placements);
        report.geometry_ok = geometry_ok;
        report.messages.extend(geom_msgs);

        let (physics_ok, physics_msgs, _total_weight) = self.verify_physics(placements);
        report.physics_ok = physics_ok;
        report.messages.extend(physics_msgs);

        let (orientation_ok, orient_msgs) = self.verify_orientation(placements);
        report.orientation_ok = orientation_ok;
        report.orientation_violations = self.count_orientation_violations(placements);
        report.messages.extend(orient_msgs);

        report.stability_score = self.calc_stability_score(placements);
        let (support_score, _) = self.calc_support_score(placements);
        report.support_score = support_score;
        report.cg_deviation_ratio = self.calc_cg_deviation(placements);
        report.fragile_violations = self.calc_fragile_violations(placements);
        report.is_feasible = geometry_ok && physics_ok && orientation_ok;

        report
    }

    fn verify_geometry(&self, placements: &[PlacementInfo]) -> (bool, Vec<String>) {
        let mut messages = Vec::new();
        let mut ok = true;
        let (cl, ch, cw) = self.container_dims;

        for (i, p) in placements.iter().enumerate() {
            if p.x < -0.001 || p.y < -0.001 || p.z < -0.001 {
                messages.push(format!("[几何] 商品 {} 坐标为负", p.item_id));
                ok = false;
            }
            if p.x + p.l > cl + 0.001 || p.y + p.h > ch + 0.001 || p.z + p.w > cw + 0.001 {
                messages.push(format!("[几何] 商品 {} 超出容器边界", p.item_id));
                ok = false;
            }
            let others: Vec<PlacementInfo> = placements[..i].to_vec();
            if check_overlap(p.x, p.y, p.z, p.l, p.h, p.w, &others) {
                messages.push(format!("[几何] 商品 {} 与已放置物品重叠", p.item_id));
                ok = false;
            }
            if p.y > VERTICAL_TOLERANCE {
                let (_, is_supported) = check_support(p.x, p.y, p.z, p.l, p.h, p.w, &others);
                if !is_supported {
                    messages.push(format!(
                        "[几何] 商品 {} 底部支撑不足 (支持率 {}% 需要)",
                        p.item_id,
                        SUPPORT_THRESHOLD_EP * 100.0
                    ));
                }
            }
        }
        (ok, messages)
    }

    fn verify_physics(&self, placements: &[PlacementInfo]) -> (bool, Vec<String>, f64) {
        let mut messages = Vec::new();
        let total_weight: f64 = placements.iter().map(|p| p.weight).sum();

        if total_weight > self.max_weight + 0.001 {
            messages.push(format!(
                "[物理] 总重量 {:.1}kg 超过限制 {}kg",
                total_weight, self.max_weight
            ));
            return (false, messages, total_weight);
        }

        let cg_deviation = self.calc_cg_deviation(placements);
        if cg_deviation > 0.15 {
            messages.push(format!("[物理] 重心偏离度过大: {:.3} (> 0.15)", cg_deviation));
        }
        (true, messages, total_weight)
    }

    fn verify_orientation(&self, placements: &[PlacementInfo]) -> (bool, Vec<String>) {
        let violations = self.count_orientation_violations(placements);
        let ok = violations == 0;
        let mut messages = Vec::new();

        for p in placements {
            let spec = match self.item_specs.get(&p.item_id) {
                Some(s) => s,
                None => continue,
            };
            if spec.forbidden_horizontal_dims.is_empty() {
                continue;
            }
            let orientation = match &p.orientation {
                Some(o) => o.as_str(),
                None => continue,
            };
            let vertical_dim = orientation_vertical_dim(orientation);
            if vertical_dim.is_empty() {
                continue;
            }
            if spec.forbidden_horizontal_dims.iter().any(|d| d == vertical_dim) {
                messages.push(format!(
                    "[朝向] 商品 {} 禁止 {} 与地面垂直，但实际为 {}",
                    p.item_id, vertical_dim, orientation
                ));
            }
        }
        (ok, messages)
    }

    fn count_orientation_violations(&self, placements: &[PlacementInfo]) -> i32 {
        let mut count = 0;
        for p in placements {
            let spec = match self.item_specs.get(&p.item_id) {
                Some(s) => s,
                None => continue,
            };
            if spec.forbidden_horizontal_dims.is_empty() {
                continue;
            }
            let orientation = match &p.orientation {
                Some(o) => o.as_str(),
                None => continue,
            };
            let vertical_dim = orientation_vertical_dim(orientation);
            if vertical_dim.is_empty() {
                continue;
            }
            if spec.forbidden_horizontal_dims.iter().any(|d| d == vertical_dim) {
                count += 1;
            }
        }
        count
    }

    fn calc_support_score(&self, placements: &[PlacementInfo]) -> (f64, f64) {
        if placements.is_empty() {
            return (1.0, 1.0);
        }
        let mut total = 0.0;
        let count = placements.len();
        for (i, p) in placements.iter().enumerate() {
            if p.y <= VERTICAL_TOLERANCE {
                total += 1.0;
            } else {
                let others: Vec<PlacementInfo> = placements
                    .iter()
                    .enumerate()
                    .filter(|(j, _)| *j != i)
                    .map(|(_, p)| p.clone())
                    .collect();
                let (ratio, _) = check_support(p.x, p.y, p.z, p.l, p.h, p.w, &others);
                total += ratio;
            }
        }
        let avg = total / count as f64;
        (avg, avg)
    }

    fn calc_stability_score(&self, placements: &[PlacementInfo]) -> f64 {
        let (support_score, _) = self.calc_support_score(placements);
        if placements.is_empty() {
            return 1.0;
        }
        let cg = self.calc_center_of_gravity(placements);
        let height_ratio = if self.container.height > 0.0 {
            cg.1 / self.container.height
        } else {
            0.0
        };
        let layers = self.count_layers(placements);
        let min_h = placements.iter().map(|p| p.h).fold(f64::INFINITY, f64::min);
        let max_layers = if !placements.is_empty() && min_h > 0.0 {
            self.container.height / min_h
        } else {
            1.0
        };
        let layer_ratio = if max_layers > 1.0 {
            1.0 - (layers as f64 - 1.0) / max_layers
        } else {
            0.0
        };
        let score = 0.4 * support_score + 0.3 * (1.0 - height_ratio) + 0.3 * layer_ratio;
        (score.max(0.0).min(1.0) * 10000.0).round() / 10000.0
    }

    fn count_layers(&self, placements: &[PlacementInfo]) -> usize {
        if placements.is_empty() {
            return 0;
        }
        let eps = VERTICAL_TOLERANCE * 2.0;
        let mut layer_ys: Vec<f64> = placements
            .iter()
            .map(|p| (p.y / eps).round() * eps)
            .collect();
        layer_ys.sort_by(|a, b| a.partial_cmp(b).unwrap());
        layer_ys.dedup();
        layer_ys.len()
    }

    fn calc_cg_deviation(&self, placements: &[PlacementInfo]) -> f64 {
        if placements.is_empty() {
            return 0.0;
        }
        let cg = self.calc_center_of_gravity(placements);
        let cx_center = self.container.length / 2.0;
        let cy_center = self.container.height / 2.0;
        let cz_center = self.container.width / 2.0;
        let offset_x = if self.container.length > 0.0 {
            (cg.0 - cx_center).abs() / (self.container.length / 2.0)
        } else { 0.0 };
        let offset_y = if self.container.height > 0.0 {
            (cg.1 - cy_center).abs() / (self.container.height / 2.0)
        } else { 0.0 };
        let offset_z = if self.container.width > 0.0 {
            (cg.2 - cz_center).abs() / (self.container.width / 2.0)
        } else { 0.0 };
        let euclidean_dist = (offset_x.powi(2) + offset_y.powi(2) + offset_z.powi(2)).sqrt();
        (euclidean_dist / 3.0_f64.sqrt()).min(1.0)
    }

    fn calc_fragile_violations(&self, placements: &[PlacementInfo]) -> i32 {
        let mut violations = 0;
        for (fi, fragile) in placements.iter().enumerate() {
            if !fragile.is_fragile {
                continue;
            }
            let f_top = fragile.y + fragile.h;
            for (pi, p) in placements.iter().enumerate() {
                if pi == fi {
                    continue;
                }
                if (p.y - f_top).abs() > VERTICAL_TOLERANCE {
                    continue;
                }
                let overlap_x =
                    (fragile.x + fragile.l).min(p.x + p.l) - fragile.x.max(p.x);
                let overlap_x = overlap_x.max(0.0);
                let overlap_z =
                    (fragile.z + fragile.w).min(p.z + p.w) - fragile.z.max(p.z);
                let overlap_z = overlap_z.max(0.0);
                if overlap_x * overlap_z > 0.0 {
                    violations += 1;
                }
            }
        }
        violations
    }

    fn calc_center_of_gravity(&self, placements: &[PlacementInfo]) -> (f64, f64, f64) {
        if placements.is_empty() {
            return (0.0, 0.0, 0.0);
        }
        let total_w: f64 = placements.iter().map(|p| p.weight).sum();
        if total_w > 0.0 {
            let cx: f64 = placements.iter().map(|p| p.weight * (p.x + p.l / 2.0)).sum::<f64>() / total_w;
            let cy: f64 = placements.iter().map(|p| p.weight * (p.y + p.h / 2.0)).sum::<f64>() / total_w;
            let cz: f64 = placements.iter().map(|p| p.weight * (p.z + p.w / 2.0)).sum::<f64>() / total_w;
            return (cx, cy, cz);
        }
        let total_vol: f64 = placements.iter().map(|p| p.l * p.h * p.w).sum();
        if total_vol > 0.0 {
            let cx: f64 = placements.iter().map(|p| p.l * p.h * p.w * (p.x + p.l / 2.0)).sum::<f64>() / total_vol;
            let cy: f64 = placements.iter().map(|p| p.l * p.h * p.w * (p.y + p.h / 2.0)).sum::<f64>() / total_vol;
            let cz: f64 = placements.iter().map(|p| p.l * p.h * p.w * (p.z + p.w / 2.0)).sum::<f64>() / total_vol;
            return (cx, cy, cz);
        }
        (0.0, 0.0, 0.0)
    }
}
