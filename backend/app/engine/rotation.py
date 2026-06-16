from typing import List, Tuple

"""
Orientation definitions (沿X, 沿Y, 沿Z):
  Orientation 1 (height_vertical):  (L, H, W) - height is vertical, base is L×W
  Orientation 2 (width_vertical):   (L, W, H) - width is vertical, base is L×H
  Orientation 3 (length_vertical):  (W, H, L) - length is vertical, base is W×H

  Each orientation has one vertical dimension and two horizontal dimensions.
  forbidden_horizontal_dims specifies which dimensions CANNOT be horizontal.
  An orientation is excluded if ANY of its horizontal dimensions is in the forbidden list.

  Example: forbidden_horizontal_dims = ["height"]
    - height_vertical: horizontal={length, width} → height not in horizontal → ALLOWED
    - width_vertical:  horizontal={length, height} → height IS horizontal → EXCLUDED
    - length_vertical: horizontal={width, height} → height IS horizontal → EXCLUDED
"""

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

    forbidden_horizontal_dims:
      - []: all 3 orientations allowed
      - ['height']: height cannot be horizontal → only orientation 1 (height_vertical)
      - ['width']: width cannot be horizontal → only orientation 2 (width_vertical)
      - ['length']: length cannot be horizontal → only orientation 3 (length_vertical)
      - ['height', 'length']: height AND length cannot be horizontal → impossible (excluded all)

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
        horizontal = ORIENTATION_HORIZONTAL[orient_name]
        return not bool(forbidden & horizontal)

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

