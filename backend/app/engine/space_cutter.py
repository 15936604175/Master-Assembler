from typing import List
from dataclasses import dataclass


@dataclass
class Space:
    x: float
    y: float
    z: float
    l: float  # length (X)
    h: float  # height (Y)
    w: float  # width (Z)


def cut_space(space: Space, item_box: tuple) -> List[Space]:
    ix, iy, iz, il, ih, iw = item_box

    if (space.x >= ix + il or space.x + space.l <= ix or
        space.y >= iy + ih or space.y + space.h <= iy or
        space.z >= iz + iw or space.z + space.w <= iz):
        return [space]

    result = []

    if ix > space.x:
        result.append(Space(
            space.x, space.y, space.z,
            ix - space.x, space.h, space.w
        ))

    if space.x + space.l > ix + il:
        result.append(Space(
            ix + il, space.y, space.z,
            space.x + space.l - (ix + il), space.h, space.w
        ))

    if iy > space.y:
        result.append(Space(
            space.x, space.y, space.z,
            space.l, iy - space.y, space.w
        ))

    if space.y + space.h > iy + ih:
        result.append(Space(
            space.x, iy + ih, space.z,
            space.l, space.y + space.h - (iy + ih), space.w
        ))

    if iz > space.z:
        result.append(Space(
            space.x, space.y, space.z,
            space.l, space.h, iz - space.z
        ))

    if space.z + space.w > iz + iw:
        result.append(Space(
            space.x, space.y, iz + iw,
            space.l, space.h, space.z + space.w - (iz + iw)
        ))

    return result


def remove_degenerate_spaces(spaces: List[Space], min_size: float = 5.0) -> List[Space]:
    return [s for s in spaces if s.l >= min_size and s.h >= min_size and s.w >= min_size]
