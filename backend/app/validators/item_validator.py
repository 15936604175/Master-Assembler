from typing import List, Dict, Tuple
from pydantic import ValidationError
from app.models.container import ContainerConfig
from app.models.item import ItemInput
from app.engine.rotation import get_allowed_orientations


def validate_items(items: List[ItemInput], container: ContainerConfig
                   ) -> Tuple[bool, List[str]]:
    errors: List[str] = []

    total_volume = 0.0
    total_weight = 0.0
    container_volume = container.length * container.width * container.height

    item_ids: Dict[str, int] = {}

    for item in items:
        if item.id in item_ids:
            item_ids[item.id] += 1
            errors.append(f"商品ID重复: '{item.id}' 出现 {item_ids[item.id]} 次")
        else:
            item_ids[item.id] = 1

        # 检查朝向约束是否矛盾（所有朝向都被排除）
        allowed = get_allowed_orientations(
            item.length, item.width, item.height,
            item.forbidden_horizontal_dims,
        )
        if not allowed:
            errors.append(
                f"商品 '{item.id}' 的朝向约束矛盾: "
                f"forbidden_horizontal_dims={item.forbidden_horizontal_dims} "
                f"导致所有 3 种朝向均被排除（每个维度只能有一个垂直，不能同时禁止两个维度水平）"
            )
            continue

        # 检查是否存在至少一种允许的朝向能放进容器
        can_fit = False
        for (rot_l, rot_w, rot_h), _, _ in allowed:
            if (rot_l <= container.length + 0.001
                    and rot_h <= container.height + 0.001
                    and rot_w <= container.width + 0.001):
                can_fit = True
                break
        if not can_fit:
            errors.append(
                f"商品 '{item.id}' ({item.length}×{item.width}×{item.height}mm) "
                f"在朝向约束 {item.forbidden_horizontal_dims} 下，"
                f"所有允许朝向的尺寸均超出容器 ({container.length}×{container.width}×{container.height}mm)"
            )

        item_vol = item.length * item.width * item.height * item.quantity
        total_volume += item_vol
        total_weight += item.weight * item.quantity

    if total_volume > container_volume * 1.5:
        errors.append(
            f"商品总体积 ({total_volume:.0f} mm³) 远超容器容量 "
            f"({container_volume:.0f} mm³)，可能无法装入"
        )

    if total_weight > container.max_weight:
        errors.append(
            f"商品总重量 ({total_weight:.2f} kg) 超过"
            f"容器最大载重 ({container.max_weight:.2f} kg)"
        )

    return (len(errors) == 0, errors)


def validate_request(container: ContainerConfig, items: List[ItemInput]
                     ) -> Tuple[bool, List[str]]:
    errors: List[str] = []

    if container.length <= 0 or container.width <= 0 or container.height <= 0:
        errors.append("容器尺寸必须大于0")

    if container.max_weight <= 0:
        errors.append("容器最大载重必须大于0")

    if not items:
        errors.append("商品列表不能为空")

    items_valid, item_errors = validate_items(items, container)
    errors.extend(item_errors)

    return (len(errors) == 0, errors)
