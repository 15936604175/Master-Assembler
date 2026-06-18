"""详细性能分析：找出剩余瓶颈。"""
import sys
import time
sys.path.insert(0, ".")

from app.engine.packer import EPacker, MAX_EP_COUNT, FAST_EP_COUNT, _generate_floor_eps, _prune_eps
from app.engine.extreme_point import generate_new_eps, check_overlap
from app.engine.rotation import get_allowed_orientations
from app.models.container import ContainerConfig
from app.models.item import ItemInput, ItemInstance

# 测试 50³ × 1000 in 500³
container = ContainerConfig(length=500, width=500, height=500, max_weight=1e9)
items = [ItemInput(id="A", length=50, width=50, height=50, weight=1, quantity=1000,
                  is_fragile=False, batch_number=0, forbidden_horizontal_dims=[])]

packer = EPacker()
packer.container = (container.length, container.height, container.width)
packer.container_volume = container.length * container.height * container.width
packer.max_weight = container.max_weight
packer.placed_weight = 0.0
packer.placed_volume = 0.0
packer.placements = []
cl, ch, cw = packer.container
packer._grid_cell_size = max(max(cl, ch, cw) / 10.0, 50.0)
packer._grid = {}
packer.extreme_points = _generate_floor_eps(container.length, container.height, container.width)

instances = []
for item in items:
    for _ in range(item.quantity):
        instances.append(ItemInstance(
            item_id=item.id, length=item.length, width=item.width, height=item.height,
            weight=item.weight, is_fragile=False, batch_number=0,
            forbidden_horizontal_dims=[],
        ))

# 分段计时
time_total = 0
time_overlap = 0
time_eval = 0
time_ep_update = 0
time_grid_add = 0
ep_count_sum = 0
placement_count = 0

t_start = time.time()
for i, inst in enumerate(instances[:1000]):  # 跑完整1000个
    t0 = time.time()
    allowed_orientations = get_allowed_orientations(
        inst.length, inst.width, inst.height, inst.forbidden_horizontal_dims
    )
    best_score = -float("inf")
    best_placement = None
    best_rot = ""
    best_orientation = ""

    for (rot_l, rot_w, rot_h), rot_label, orientation_name in allowed_orientations:
        for ep in packer.extreme_points:
            ex, ey, ez = ep
            if ex + rot_l > cl + 0.001 or ey + rot_h > ch + 0.001 or ez + rot_w > cw + 0.001:
                continue
            t1 = time.time()
            overlap = packer._grid_check_overlap(ex, ey, ez, rot_l, rot_h, rot_w)
            time_overlap += time.time() - t1
            if overlap:
                continue
            t1 = time.time()
            from app.engine.extreme_point import evaluate_placement_fast
            score = evaluate_placement_fast(
                ep, (rot_l, rot_h, rot_w), packer.container, packer.placements,
                weight=inst.weight, is_fragile=inst.is_fragile
            )
            time_eval += time.time() - t1
            if score > best_score:
                best_score = score
                best_placement = (ex, ey, ez, rot_l, rot_h, rot_w)
                best_rot = rot_label
                best_orientation = orientation_name

    if best_placement is None:
        continue

    x, y, z, l, h, w = best_placement
    packer.placements.append({
        "item_id": inst.item_id, "x": x, "y": y, "z": z,
        "l": l, "h": h, "w": w, "weight": inst.weight,
        "is_fragile": inst.is_fragile, "rotation": best_rot,
        "orientation": best_orientation,
    })
    t1 = time.time()
    packer._grid_add(len(packer.placements) - 1, packer.placements[-1])
    time_grid_add += time.time() - t1
    packer.placed_weight += inst.weight
    packer.placed_volume += l * h * w
    placement_count += 1

    t1 = time.time()
    new_eps = generate_new_eps(x, y, z, l, h, w)
    seen = set()
    unique_eps = []
    for ep in packer.extreme_points:
        key = (round(ep[0], 2), round(ep[1], 2), round(ep[2], 2))
        if key not in seen:
            seen.add(key)
            unique_eps.append(ep)
    for nep in new_eps:
        key = (round(nep[0], 2), round(nep[1], 2), round(nep[2], 2))
        if key not in seen:
            seen.add(key)
            unique_eps.append(nep)
    unique_eps = packer._remove_consumed_eps(unique_eps)
    packer.extreme_points = _prune_eps(unique_eps, packer.container, MAX_EP_COUNT)
    time_ep_update += time.time() - t1

    ep_count_sum += len(packer.extreme_points)

total_time = time.time() - t_start
print(f"=== 性能分析 (前200个物品) ===")
print(f"总时间: {total_time:.2f}s")
print(f"check_overlap (网格): {time_overlap:.2f}s ({time_overlap/total_time*100:.1f}%)")
print(f"evaluate_placement: {time_eval:.2f}s ({time_eval/total_time*100:.1f}%)")
print(f"EP更新: {time_ep_update:.2f}s ({time_ep_update/total_time*100:.1f}%)")
print(f"grid_add: {time_grid_add:.2f}s ({time_grid_add/total_time*100:.1f}%)")
print(f"放置数量: {placement_count}")
print(f"平均EP数: {ep_count_sum/placement_count if placement_count else 0:.1f}")
print(f"最终EP数: {len(packer.extreme_points)}")

# 检查网格效率
print(f"\n网格单元大小: {packer._grid_cell_size}")
print(f"网格单元数: {len(packer._grid)}")
avg_per_cell = sum(len(v) for v in packer._grid.values()) / len(packer._grid) if packer._grid else 0
print(f"平均每单元物品数: {avg_per_cell:.2f}")
