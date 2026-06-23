/// Extreme Point 工具函数模块

use crate::models::PlacementInfo;

pub const SUPPORT_THRESHOLD_EP: f64 = 0.1;
pub const VERTICAL_TOLERANCE: f64 = 1.0;

pub fn generate_new_eps(
    x: f64, y: f64, z: f64,
    item_l: f64, item_h: f64, item_w: f64,
) -> Vec<(f64, f64, f64)> {
    vec![
        (x + item_l, y, z),
        (x, y + item_h, z),
        (x, y, z + item_w),
        (x + item_l, y, z + item_w),
        (x + item_l, y + item_h, z),
        (x, y + item_h, z + item_w),
    ]
}

pub fn is_valid_ep(
    ep: (f64, f64, f64),
    item_size: (f64, f64, f64),
    container: (f64, f64, f64),
) -> bool {
    let (ex, ey, ez) = ep;
    let (il, ih, iw) = item_size;
    let (cl, ch, cw) = container;
    ex + il <= cl + 0.001 && ey + ih <= ch + 0.001 && ez + iw <= cw + 0.001
}

pub fn check_overlap(
    x: f64, y: f64, z: f64,
    l: f64, h: f64, w: f64,
    placements: &[PlacementInfo],
) -> bool {
    for p in placements {
        if x < p.x + p.l
            && x + l > p.x
            && y < p.y + p.h
            && y + h > p.y
            && z < p.z + p.w
            && z + w > p.z
        {
            return true;
        }
    }
    false
}

pub fn check_support(
    x: f64, y: f64, z: f64,
    l: f64, h: f64, w: f64,
    placements: &[PlacementInfo],
) -> (f64, bool) {
    if y <= VERTICAL_TOLERANCE {
        return (1.0, true);
    }
    let item_footprint = l * w;
    if item_footprint <= 0.0 {
        return (0.0, false);
    }
    let mut supported_area = 0.0;
    let x2 = x + l;
    let z2 = z + w;

    for p in placements {
        let p_top = p.y + p.h;
        if (p_top - y).abs() > VERTICAL_TOLERANCE {
            continue;
        }
        let overlap_x = (x2.min(p.x + p.l) - x.max(p.x)).max(0.0);
        let overlap_z = (z2.min(p.z + p.w) - z.max(p.z)).max(0.0);
        supported_area += overlap_x * overlap_z;
    }

    let support_ratio = supported_area / item_footprint;
    let is_supported = support_ratio >= SUPPORT_THRESHOLD_EP;
    ((support_ratio * 10000.0).round() / 10000.0, is_supported)
}

pub fn check_cg_stability(
    x: f64, y: f64, z: f64,
    l: f64, h: f64, w: f64,
    weight: f64,
    placements: &[PlacementInfo],
    container: (f64, f64, f64),
) -> (f64, bool) {
    let total_weight: f64 = placements.iter().map(|p| p.weight).sum::<f64>() + weight;
    if total_weight <= 0.0 {
        return (1.0, true);
    }
    let new_cx = (placements.iter().map(|p| p.weight * (p.x + p.l / 2.0)).sum::<f64>()
        + weight * (x + l / 2.0))
        / total_weight;
    let new_cy = (placements.iter().map(|p| p.weight * (p.y + p.h / 2.0)).sum::<f64>()
        + weight * (y + h / 2.0))
        / total_weight;
    let new_cz = (placements.iter().map(|p| p.weight * (p.z + p.w / 2.0)).sum::<f64>()
        + weight * (z + w / 2.0))
        / total_weight;

    let (cl, ch, cw) = container;
    let cx_center = cl / 2.0;
    let cz_center = cw / 2.0;
    let allowed_offset_x = cl * 0.35;
    let allowed_offset_z = cw * 0.35;
    let offset_x = (new_cx - cx_center).abs();
    let offset_z = (new_cz - cz_center).abs();

    let mut cg_score = (1.0 - (offset_x / allowed_offset_x + offset_z / allowed_offset_z) / 2.0).max(0.0);
    let height_penalty = if ch > 0.0 {
        (new_cy / (ch * 0.5)).min(1.0)
    } else {
        0.0
    };
    cg_score *= 1.0 - height_penalty * 0.3;

    let is_stable = offset_x <= allowed_offset_x && offset_z <= allowed_offset_z;
    ((cg_score * 10000.0).round() / 10000.0, is_stable)
}

pub fn check_fragile_safety(
    x: f64, y: f64, z: f64,
    l: f64, h: f64, w: f64,
    weight: f64,
    placements: &[PlacementInfo],
) -> (f64, bool) {
    let x2 = x + l;
    let z2 = z + w;
    let mut penalty = 0.0;
    let mut has_issue = false;

    for p in placements {
        if !p.is_fragile {
            continue;
        }
        let p_top = p.y + p.h;
        if (y - p_top).abs() > VERTICAL_TOLERANCE {
            continue;
        }
        let overlap_x = (x2.min(p.x + p.l) - x.max(p.x)).max(0.0);
        let overlap_z = (z2.min(p.z + p.w) - z.max(p.z)).max(0.0);
        let overlap_area = overlap_x * overlap_z;
        let fragile_area = p.l * p.w;
        if overlap_area > 0.0 && fragile_area > 0.0 {
            let coverage = overlap_area / fragile_area;
            if coverage > 0.1 {
                penalty += coverage * weight;
                has_issue = true;
            }
        }
    }

    let safety_score = (1.0 - penalty).max(0.0);
    ((safety_score * 10000.0).round() / 10000.0, !has_issue)
}

pub fn evaluate_placement(
    ep: (f64, f64, f64),
    item_size: (f64, f64, f64),
    container: (f64, f64, f64),
    _existing_placements: &[PlacementInfo],
    _weight: f64,
    _is_fragile: bool,
) -> (f64, std::collections::HashMap<String, f64>) {
    let (ex, ey, ez) = ep;
    let (il, ih, iw) = item_size;
    let (cl, ch, cw) = container;

    let blf_score = if cl > 0.0 && ch > 0.0 && cw > 0.0 {
        let s = 1.0 - (ey / ch * 0.5 + ex / cl * 0.3 + ez / cw * 0.2);
        s.max(0.0).min(1.0)
    } else {
        1.0
    };

    let mut wall_bonus = 0.0;
    if ex <= 0.01 || ex + il >= cl - 0.01 { wall_bonus += 0.05; }
    if ez <= 0.01 || ez + iw >= cw - 0.01 { wall_bonus += 0.05; }
    if ey <= 0.01 { wall_bonus += 0.05; }

    let total_score = blf_score + wall_bonus;
    let mut metrics = std::collections::HashMap::new();
    metrics.insert("blf_score".to_string(), (blf_score * 10000.0).round() / 10000.0);
    metrics.insert("wall_bonus".to_string(), (wall_bonus * 10000.0).round() / 10000.0);
    ((total_score * 10000.0).round() / 10000.0, metrics)
}

pub fn evaluate_placement_fast(
    ep: (f64, f64, f64),
    item_size: (f64, f64, f64),
    container: (f64, f64, f64),
    _existing_placements: &[PlacementInfo],
    _weight: f64,
    _is_fragile: bool,
) -> f64 {
    let (ex, ey, ez) = ep;
    let (il, ih, iw) = item_size;
    let (cl, ch, cw) = container;

    let blf_score = if cl > 0.0 && ch > 0.0 && cw > 0.0 {
        let s = 1.0 - (ey / ch * 0.5 + ex / cl * 0.3 + ez / cw * 0.2);
        s.max(0.0).min(1.0)
    } else {
        1.0
    };

    let mut wall_bonus = 0.0;
    if ex <= 0.01 || ex + il >= cl - 0.01 { wall_bonus += 0.05; }
    if ez <= 0.01 || ez + iw >= cw - 0.01 { wall_bonus += 0.05; }
    if ey <= 0.01 { wall_bonus += 0.05; }

    ((blf_score + wall_bonus) * 10000.0).round() / 10000.0
}
