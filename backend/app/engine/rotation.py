from typing import List, Tuple

"""
Orientation definitions (沿X, 沿Y, 沿Z):
  Orientation 1 (height_vertical):  (L, H, W) - height is vertical, base is L×W
  Orientation 2 (width_vertical):   (L, W, H) - width is vertical, base is L×H
  Orientation 3 (length_vertical):  (W, H, L) - length is vertical, base is W×H

  forbidden_horizontal_dims 指定哪些维度禁止与地面垂直（即禁止该维度朝上）。
  最多 2 个参数（至少要有一个维度可以垂直）。

  Example: forbidden_horizontal_dims = ["height"]
    - height_vertical: height 朝上 → 禁止 → 排除
    - width_vertical:  width 朝上 → 允许
    - length_vertical: length 朝上 → 允许

  Example: forbidden_horizontal_dims = ["height", "width"]
    - height_vertical: height 朝上 → 禁止 → 排除
    - width_vertical:  width 朝上 → 禁止 → 排除
    - length_vertical: length 朝上 → 允许（唯一合法朝向）
"""

# 每种朝向对应的垂直维度（与地面垂直的维度）
ORIENTATION_VERTICAL_DIM = {
    "height_vertical": "height",   # height 与地面垂直
    "width_vertical": "width",     # width 与地面垂直
    "length_vertical": "length",   # length 与地面垂直
}

# 每种朝向对应的水平维度集合（保留用于兼容性）
ORIENTATION_HORIZONTAL = {
    "height_vertical": {"length", "width"},
    "width_vertical": {"length", "height"},
    "length_vertical": {"width", "height"},
}


def get_all_rotations(length: float, width: float, height: float) -> List[Tuple[float, float, float]]:
    return [
        (length, width, height),
        (length, height, width),
        (width, length, height),
        (width, height, length),
        (height, length, width),
        (height, width, length),
    ]


def get_allowed_orientations(
    length: float, width: float, height: float,
    forbidden_horizontal_dims: List[str],
) -> List[Tuple[Tuple[float, float, float], str, str]]:
    """
    Returns allowed orientations based on forbidden_horizontal_dims constraint.

    forbidden_horizontal_dims 语义：禁止该维度与地面垂直（朝上）。
      - []: all 3 orientations allowed
      - ['height']: height 不能朝上 → 排除 height_vertical，允许 width_vertical 和 length_vertical
      - ['width']: width 不能朝上 → 排除 width_vertical，允许 height_vertical 和 length_vertical
      - ['length']: length 不能朝上 → 排除 length_vertical，允许 height_vertical 和 width_vertical
      - ['height', 'width']: 只允许 length_vertical
      - ['height', 'width', 'length']: 全部排除（非法，最多 2 个参数）

    Returns list of (dimensions_tuple, rotation_label, orientation_name).
    """
    all_orientations = [
        ((length, width, height), "lwh", "height_vertical"),    # H vertical, base L×W
        ((length, height, width), "lhw", "width_vertical"),     # W vertical, base L×H
        ((width, height, length), "whl", "length_vertical"),    # L vertical, base W×H
    ]

    if not forbidden_horizontal_dims:
        return all_orientations

    forbidden = set(forbidden_horizontal_dims)

    def is_allowed(orient_name: str) -> bool:
        # 该朝向的垂直维度
        vertical_dim = ORIENTATION_VERTICAL_DIM[orient_name]
        # 如果垂直维度在禁止列表中，则排除该朝向
        return vertical_dim not in forbidden

    return [o for o in all_orientations if is_allowed(o[2])]


def get_orientation_for_rotation(
    length: float, width: float, height: float,
    rot_l: float, rot_w: float, rot_h: float,
) -> str:
    if abs(rot_h - height) < 0.01:
        return "height_vertical"
    elif abs(rot_h - width) < 0.01:
        return "width_vertical"
    elif abs(rot_h - length) < 0.01:
        return "length_vertical"
    closest = min(
        ("height", height), ("width", width), ("length", length),
        key=lambda t: abs(rot_h - t[1])
    )
    return closest[0] + "_vertical"
