from typing import List, Tuple, Dict

ExtremePoint = Tuple[float, float, float]

SUPPORT_THRESHOLD = 0.1
VERTICAL_TOLERANCE = 1.0


def generate_new_eps(x: float, y: float, z: float,
                     item_l: float, item_h: float, item_w: float) -> List[ExtremePoint]:
    return [
        (x + item_l, y, z),
        (x, y + item_h, z),
        (x, y, z + item_w),
        (x + item_l, y, z + item_w),
        (x + item_l, y + item_h, z),
        (x, y + item_h, z + item_w),
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
    """评估放置位置得分（空间利用率最优版本）。

    优化点：
    - 移除 O(N) 的 cg_score / gravity_score / fragile_safe / adj_score 计算
    - 仅保留 O(1) 的 BLF（Bottom-Left-Fill）评分
    - 不考虑重量平衡和稳定性约束
    """
    ex, ey, ez = ep
    il, ih, iw = item_size
    cl, ch, cw = container

    # BLF 评分：优先填底部、左部、后部，O(1) 复杂度
    if cl > 0 and ch > 0 and cw > 0:
        blf_score = 1.0 - (ey / ch * 0.5 + ex / cl * 0.3 + ez / cw * 0.2)
        blf_score = max(0.0, min(1.0, blf_score))
    else:
        blf_score = 1.0

    # 紧贴容器壁奖励：物品贴边时给予小幅加分，鼓励规则堆叠
    wall_bonus = 0.0
    if ex <= 0.01 or ex + il >= cl - 0.01:
        wall_bonus += 0.05
    if ez <= 0.01 or ez + iw >= cw - 0.01:
        wall_bonus += 0.05
    if ey <= 0.01:
        wall_bonus += 0.05

    total_score = blf_score + wall_bonus

    metrics = {
        "blf_score": round(blf_score, 4),
        "wall_bonus": round(wall_bonus, 4),
    }

    return round(total_score, 4), metrics


def evaluate_placement_fast(ep: ExtremePoint, item_size: Tuple[float, float, float],
                             container: Tuple[float, float, float],
                             existing_placements: List[Dict],
                             weight: float = 1.0,
                             is_fragile: bool = False) -> float:
    """快速评估放置位置得分（与 evaluate_placement 一致，O(1) 复杂度）。"""
    ex, ey, ez = ep
    il, ih, iw = item_size
    cl, ch, cw = container

    if cl > 0 and ch > 0 and cw > 0:
        blf_score = 1.0 - (ey / ch * 0.5 + ex / cl * 0.3 + ez / cw * 0.2)
        blf_score = max(0.0, min(1.0, blf_score))
    else:
        blf_score = 1.0

    wall_bonus = 0.0
    if ex <= 0.01 or ex + il >= cl - 0.01:
        wall_bonus += 0.05
    if ez <= 0.01 or ez + iw >= cw - 0.01:
        wall_bonus += 0.05
    if ey <= 0.01:
        wall_bonus += 0.05

    return round(blf_score + wall_bonus, 4)
