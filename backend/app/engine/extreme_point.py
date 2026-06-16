from typing import List, Tuple, Dict

ExtremePoint = Tuple[float, float, float]

SUPPORT_THRESHOLD = 0.6
VERTICAL_TOLERANCE = 1.0


def generate_new_eps(x: float, y: float, z: float,
                     item_l: float, item_h: float, item_w: float) -> List[ExtremePoint]:
    return [
        (x + item_l, y, z),
        (x, y + item_h, z),
        (x, y, z + item_w),
    ]


def is_valid_ep(ep: ExtremePoint, item_size: Tuple[float, float, float],
                container: Tuple[float, float, float]) -> bool:
    ex, ey, ez = ep
    il, ih, iw = item_size
    cl, ch, cw = container
    return (ex + il <= cl + 0.001 and ey + ih <= ch + 0.001 and ez + iw <= cw + 0.001)


def check_overlap(x: float, y: float, z: float,
                  l: float, h: float, w: float,
                  placements: List[Dict]) -> bool:
    for p in placements:
        px, py, pz = p["x"], p["y"], p["z"]
        pl, ph, pw = p["l"], p["h"], p["w"]
        if (x < px + pl and x + l > px and
                y < py + ph and y + h > py and
                z < pz + pw and z + w > pz):
            return True
    return False


def check_support(x: float, y: float, z: float,
                  l: float, h: float, w: float,
                  placements: List[Dict]) -> Tuple[float, bool]:
    if y <= VERTICAL_TOLERANCE:
        return 1.0, True

    item_footprint = l * w
    if item_footprint <= 0:
        return 0.0, False

    supported_area = 0.0
    x2, z2 = x + l, z + w

    for p in placements:
        px, py, pz = p["x"], p["y"], p["z"]
        pl, ph, pw = p["l"], p["h"], p["w"]
        p_top = py + ph

        if abs(p_top - y) > VERTICAL_TOLERANCE:
            continue

        overlap_x = max(0, min(x2, px + pl) - max(x, px))
        overlap_z = max(0, min(z2, pz + pw) - max(z, pz))
        supported_area += overlap_x * overlap_z

    support_ratio = supported_area / item_footprint
    is_supported = support_ratio >= SUPPORT_THRESHOLD
    return round(support_ratio, 4), is_supported


def check_cg_stability(x: float, y: float, z: float,
                       l: float, h: float, w: float,
                       weight: float,
                       placements: List[Dict],
                       container: Tuple[float, float, float]) -> Tuple[float, bool]:
    total_weight = sum(p["weight"] for p in placements) + weight
    if total_weight <= 0:
        return 1.0, True

    new_cx = (sum(p["weight"] * (p["x"] + p["l"] / 2) for p in placements)
              + weight * (x + l / 2)) / total_weight
    new_cy = (sum(p["weight"] * (p["y"] + p["h"] / 2) for p in placements)
              + weight * (y + h / 2)) / total_weight
    new_cz = (sum(p["weight"] * (p["z"] + p["w"] / 2) for p in placements)
              + weight * (z + w / 2)) / total_weight

    cl, ch, cw = container

    cx_center = cl / 2
    cz_center = cw / 2

    allowed_offset_x = cl * 0.35
    allowed_offset_z = cw * 0.35

    offset_x = abs(new_cx - cx_center)
    offset_z = abs(new_cz - cz_center)

    cg_score = max(0.0, 1.0 - (offset_x / allowed_offset_x + offset_z / allowed_offset_z) / 2)
    height_penalty = 0.0
    if ch > 0:
        height_penalty = min(1.0, new_cy / (ch * 0.5))
    cg_score = cg_score * (1.0 - height_penalty * 0.3)

    is_stable = (offset_x <= allowed_offset_x and offset_z <= allowed_offset_z)

    return round(cg_score, 4), is_stable


def check_fragile_safety(x: float, y: float, z: float,
                         l: float, h: float, w: float,
                         weight: float,
                         placements: List[Dict]) -> Tuple[float, bool]:
    x2, y2, z2 = x + l, y + h, z + w
    penalty = 0.0
    has_issue = False

    for p in placements:
        if not p.get("is_fragile"):
            continue
        px, py, pz = p["x"], p["y"], p["z"]
        pl, ph, pw = p["l"], p["h"], p["w"]
        p_top = py + ph

        if abs(y - p_top) > VERTICAL_TOLERANCE:
            continue

        overlap_x = max(0, min(x2, px + pl) - max(x, px))
        overlap_z = max(0, min(z2, pz + pw) - max(z, pz))
        overlap_area = overlap_x * overlap_z
        fragile_area = pl * pw

        if overlap_area > 0 and fragile_area > 0:
            coverage = overlap_area / fragile_area
            if coverage > 0.1:
                penalty += coverage * weight
                has_issue = True

    safety_score = max(0.0, 1.0 - penalty)
    return round(safety_score, 4), not has_issue


def evaluate_placement(ep: ExtremePoint, item_size: Tuple[float, float, float],
                       container: Tuple[float, float, float],
                       existing_placements: List[Dict],
                       weight: float = 1.0,
                       is_fragile: bool = False) -> Tuple[float, Dict]:
    ex, ey, ez = ep
    il, ih, iw = item_size
    cl, ch, cw = container

    support_ratio, is_supported = check_support(
        ex, ey, ez, il, ih, iw, existing_placements
    )

    cg_score, is_cg_ok = check_cg_stability(
        ex, ey, ez, il, ih, iw, weight, existing_placements, container
    )

    fragile_safe = 1.0
    if not is_fragile:
        fragile_safe, _ = check_fragile_safety(
            ex, ey, ez, il, ih, iw, weight, existing_placements
        )

    w1, w2, w3, w4, w5 = 0.25, 0.30, 0.20, 0.15, 0.10

    max_dist = (cl**2 + ch**2 + cw**2) ** 0.5
    dist = (ex**2 + ey**2 + ez**2) ** 0.5
    proximity = 1.0 - (dist / max_dist) if max_dist > 0 else 1.0

    gravity_score = 1.0 - (ey / ch) if ch > 0 else 1.0

    adj_score = 0.0
    if existing_placements:
        min_gap = min(
            ((ex - p["x"])**2 + (ey - p["y"])**2 + (ez - p["z"])**2) ** 0.5
            for p in existing_placements
        )
        adj_score = 1.0 - min(max_dist > 0 and min_gap / max_dist or 0, 1.0)

    total_score = (w1 * proximity
                   + w2 * support_ratio
                   + w3 * cg_score
                   + w4 * gravity_score
                   + w5 * fragile_safe
                   + 0.1 * adj_score)

    metrics = {
        "proximity": round(proximity, 4),
        "support_ratio": support_ratio,
        "cg_score": cg_score,
        "gravity_score": round(gravity_score, 4),
        "fragile_safe": round(fragile_safe, 4),
        "is_supported": is_supported,
        "is_cg_ok": is_cg_ok,
    }

    return round(total_score, 4), metrics
