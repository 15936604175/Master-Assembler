from typing import List, Dict, Tuple
from pydantic import ValidationError
from app.models.container import ContainerConfig
from app.models.item import ItemInput


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

        max_dim = max(item.length, item.width, item.height)
        container_min = min(container.length, container.width, container.height)
        if max_dim > container_min + 0.001:
            errors.append(
                f"商品 '{item.id}' 尺寸 ({max_dim:.0f}mm) "
                f"超过容器最小维度 ({container_min:.0f}mm)"
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
