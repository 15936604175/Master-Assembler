from typing import List, Tuple, Optional

"""
Orientation definitions (沿X, 沿Y, 沿Z):
  Orientation 1 (height_vertical):  (L, H, W) - height is vertical, base is L×W
  Orientation 2 (width_vertical):   (L, W, H) - width is vertical, base is L×H
  Orientation 3 (length_vertical):  (W, L, H) - length is vertical, base is W×H
"""


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
    forbidden_horizontal_dim: Optional[str],
) -> List[Tuple[Tuple[float, float, float], str, str]]:
    """
    Returns allowed orientations based on forbidden_horizontal_dim constraint.

    forbidden_horizontal_dim:
      - None: all 3 orientations allowed
      - 'height': height cannot be horizontal → only orientation 1 (height_vertical)
      - 'width': width cannot be horizontal → only orientation 2 (width_vertical)
      - 'length': length cannot be horizontal → only orientation 3 (length_vertical)

    Returns list of (dimensions_tuple, rotation_label, orientation_name).
    """
    all_orientations = [
        ((length, width, height), "lwh", "height_vertical"),
        ((length, height, width), "lhw", "width_vertical"),
        ((width, length, height), "wlh", "length_vertical"),
    ]

    if forbidden_horizontal_dim is None:
        return all_orientations

    if forbidden_horizontal_dim == "height":
        return [all_orientations[0]]
    elif forbidden_horizontal_dim == "width":
        return [all_orientations[1]]
    elif forbidden_horizontal_dim == "length":
        return [all_orientations[2]]

    return all_orientations


def get_orientation_for_rotation(
    length: float, width: float, height: float,
    rot_l: float, rot_w: float, rot_h: float,
) -> str:
    """
    Given original dimensions and rotation dimensions, determine which dimension is vertical.
    The vertical dimension is the one that equals 'height' (the axis going up in the container).
    Orientation is determined by which original dimension's length appears in the rot_h position:
      - rot_h == height: height_vertical (height stays as vertical axis)
      - rot_h == width: width_vertical (width becomes vertical axis)
      - rot_h == length: length_vertical (length becomes vertical axis)
    """
    if abs(rot_h - height) < 0.01:
        return "height_vertical"
    elif abs(rot_h - width) < 0.01:
        return "width_vertical"
    elif abs(rot_h - length) < 0.01:
        return "length_vertical"
    # Fallback for floating-point edge cases
    closest = min(
        ("height", height), ("width", width), ("length", length),
        key=lambda t: abs(rot_h - t[1])
    )
    return closest[0] + "_vertical"

