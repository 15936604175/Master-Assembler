/// 朝向管理模块
///
/// 朝向定义（沿X, 沿Y, 沿Z）:
///   height_vertical:  (L, H, W) - height is vertical, base is L×W
///   width_vertical:   (L, W, H) - width is vertical, base is L×H
///   length_vertical:  (W, H, L) - length is vertical, base is W×H

pub type OrientRotation = ((f64, f64, f64), String, String);

pub fn orientation_vertical_dim(orient_name: &str) -> &str {
    match orient_name {
        "height_vertical" => "height",
        "width_vertical" => "width",
        "length_vertical" => "length",
        _ => "",
    }
}

pub fn get_all_rotations(length: f64, width: f64, height: f64) -> Vec<(f64, f64, f64)> {
    vec![
        (length, width, height),
        (length, height, width),
        (width, length, height),
        (width, height, length),
        (height, length, width),
        (height, width, length),
    ]
}

pub fn get_allowed_orientations(
    length: f64,
    width: f64,
    height: f64,
    forbidden_horizontal_dims: &[String],
) -> Vec<OrientRotation> {
    let all_orientations: Vec<OrientRotation> = vec![
        ((length, width, height), "lwh".to_string(), "height_vertical".to_string()),
        ((length, height, width), "lhw".to_string(), "width_vertical".to_string()),
        ((width, height, length), "whl".to_string(), "length_vertical".to_string()),
    ];

    if forbidden_horizontal_dims.is_empty() {
        return all_orientations;
    }

    let forbidden: std::collections::HashSet<&str> =
        forbidden_horizontal_dims.iter().map(|s| s.as_str()).collect();

    all_orientations
        .into_iter()
        .filter(|(_, _, orient_name)| {
            let vertical_dim = orientation_vertical_dim(orient_name);
            !forbidden.contains(vertical_dim)
        })
        .collect()
}

pub fn get_orientation_for_rotation(
    length: f64,
    width: f64,
    height: f64,
    _rot_l: f64,
    _rot_w: f64,
    rot_h: f64,
) -> String {
    if (rot_h - height).abs() < 0.01 {
        "height_vertical".to_string()
    } else if (rot_h - width).abs() < 0.01 {
        "width_vertical".to_string()
    } else if (rot_h - length).abs() < 0.01 {
        "length_vertical".to_string()
    } else {
        let candidates = [
            ("height", height),
            ("width", width),
            ("length", length),
        ];
        let closest = candidates
            .iter()
            .min_by(|a, b| (rot_h - a.1).abs().partial_cmp(&(rot_h - b.1).abs()).unwrap())
            .unwrap();
        format!("{}_vertical", closest.0)
    }
}
