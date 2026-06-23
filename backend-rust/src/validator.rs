/// 输入验证模块

use crate::models::{ContainerConfig, ItemInput};
use crate::rotation::get_allowed_orientations;
use std::collections::HashMap;

pub fn validate_items(
    items: &[ItemInput],
    container: &ContainerConfig,
) -> (bool, Vec<String>) {
    let mut errors: Vec<String> = Vec::new();
    let mut total_volume = 0.0;
    let mut total_weight = 0.0;
    let container_volume = container.length * container.width * container.height;
    let mut item_ids: HashMap<String, i32> = HashMap::new();

    for item in items {
        if let Some(cnt) = item_ids.get_mut(&item.id) {
            *cnt += 1;
            errors.push(format!("商品ID重复: '{}' 出现 {} 次", item.id, *cnt));
        } else {
            item_ids.insert(item.id.clone(), 1);
        }

        let allowed = get_allowed_orientations(
            item.length,
            item.width,
            item.height,
            &item.forbidden_horizontal_dims,
        );

        if allowed.is_empty() {
            errors.push(format!(
                "商品 '{}' 的朝向约束矛盾: forbidden_horizontal_dims={:?} 导致所有 3 种朝向均被排除（最多禁止 2 个维度垂直，至少保留 1 个合法朝向）",
                item.id, item.forbidden_horizontal_dims
            ));
            continue;
        }

        let mut can_fit = false;
        for (rot_dims, _, _) in &allowed {
            let (rot_l, rot_w, rot_h) = *rot_dims;
            if rot_l <= container.length + 0.001
                && rot_h <= container.height + 0.001
                && rot_w <= container.width + 0.001
            {
                can_fit = true;
                break;
            }
        }
        if !can_fit {
            errors.push(format!(
                "商品 '{}' ({}×{}×{}mm) 在朝向约束 {:?} 下，所有允许朝向的尺寸均超出容器 ({}×{}×{}mm)",
                item.id, item.length, item.width, item.height,
                item.forbidden_horizontal_dims,
                container.length, container.width, container.height
            ));
        }

        let item_vol = item.length * item.width * item.height * item.quantity as f64;
        total_volume += item_vol;
        total_weight += item.weight * item.quantity as f64;
    }

    if total_volume > container_volume * 1.5 {
        errors.push(format!(
            "商品总体积 ({:.0} mm³) 远超容器容量 ({:.0} mm³)，可能无法装入",
            total_volume, container_volume
        ));
    }

    if total_weight > container.max_weight {
        errors.push(format!(
            "商品总重量 ({:.2} kg) 超过容器最大载重 ({:.2} kg)",
            total_weight, container.max_weight
        ));
    }

    (errors.is_empty(), errors)
}

pub fn validate_request(
    container: &ContainerConfig,
    items: &[ItemInput],
) -> (bool, Vec<String>) {
    let mut errors: Vec<String> = Vec::new();

    if container.length <= 0.0 || container.width <= 0.0 || container.height <= 0.0 {
        errors.push("容器尺寸必须大于0".to_string());
    }
    if container.max_weight <= 0.0 {
        errors.push("容器最大载重必须大于0".to_string());
    }
    if items.is_empty() {
        errors.push("商品列表不能为空".to_string());
    }

    let (items_valid, item_errors) = validate_items(items, container);
    errors.extend(item_errors);

    (errors.is_empty(), errors)
}
