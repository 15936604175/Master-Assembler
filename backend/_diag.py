import sys
sys.path.insert(0, ".")

from app.engine.packer import EPacker
from app.engine.rotation import get_allowed_orientations
from app.engine.extreme_point import (
    is_valid_ep, check_overlap, check_support, check_cg_stability
)
from app.models.container import ContainerConfig
from app.models.item import ItemInput, ItemInstance


def diagnose(container, items):
    packer = EPacker()
    result = packer.pack(container, items)

    print(f"Placed: {len(packer.placements)}, Unplaced: {result.stats.total_items_unplaced}")
    print(f"Util: {result.container_utilization}")
    print(f"CG: ({result.center_of_gravity.x}, {result.center_of_gravity.y}, {result.center_of_gravity.z})")
    print(f"CG deviation: {result.cg_deviation_ratio}")
    print(f"EP count after pack: {len(packer.extreme_points)}")

    if packer.placements:
        max_x = max(p["x"] + p["l"] for p in packer.placements)
        max_z = max(p["z"] + p["w"] for p in packer.placements)
        max_y = max(p["y"] + p["h"] for p in packer.placements)
        print(f"Bounding box: x={max_x}, y={max_y}, z={max_z}")
        print(f"Container: {container.length} x {container.height} x {container.width}")

    for u in result.unplaced_items:
        print(f"  Unplaced: {u.item_id} x{u.quantity} - {u.reason}")

    print(f"\n--- Diagnosing unplaced items ---")
    for u in result.unplaced_items:
        inst = ItemInstance(
            item_id=u.item_id, length=100, width=100, height=100,
            weight=10, is_fragile=False, batch_number=0,
            forbidden_horizontal_dims=[],
        )
        if u.item_id == "B":
            inst = ItemInstance(
                item_id="B", length=200, width=200, height=200,
                weight=10, is_fragile=False, batch_number=0,
                forbidden_horizontal_dims=[],
            )

        allowed = get_allowed_orientations(
            inst.length, inst.width, inst.height, inst.forbidden_horizontal_dims
        )
        reasons = {"invalid_ep": 0, "overlap": 0, "no_support": 0, "cg_fail": 0, "valid": 0}
        for (rot_l, rot_w, rot_h), rot_label, orient in allowed:
            item_size = (rot_l, rot_h, rot_w)
            for ep in packer.extreme_points:
                if not is_valid_ep(ep, item_size, packer.container):
                    reasons["invalid_ep"] += 1
                    continue
                ex, ey, ez = ep
                if check_overlap(ex, ey, ez, rot_l, rot_h, rot_w, packer.placements):
                    reasons["overlap"] += 1
                    continue
                _, is_supported = check_support(ex, ey, ez, rot_l, rot_h, rot_w, packer.placements)
                if not is_supported:
                    reasons["no_support"] += 1
                    continue
                _, is_cg_ok = check_cg_stability(
                    ex, ey, ez, rot_l, rot_h, rot_w, inst.weight,
                    packer.placements, packer.container
                )
                max_cg_weight = (packer.max_weight or 0.0) * 0.1
                if not is_cg_ok and len(packer.placements) > 5 and packer.placed_weight > max_cg_weight:
                    reasons["cg_fail"] += 1
                    continue
                reasons["valid"] += 1

        print(f"  {u.item_id}: {reasons}")
        print(f"    EPs near center (>2000 x): {sum(1 for ep in packer.extreme_points if ep[0] > 2000)}")
        print(f"    EPs near origin (<2000 x): {sum(1 for ep in packer.extreme_points if ep[0] <= 2000)}")


if __name__ == "__main__":
    container = ContainerConfig(length=5898, width=2352, height=2395, max_weight=28000)
    items = [
        ItemInput(id="A", length=100, width=100, height=100, weight=10, quantity=50,
                  is_fragile=False, batch_number=0, forbidden_horizontal_dims=[]),
        ItemInput(id="B", length=200, width=200, height=200, weight=10, quantity=20,
                  is_fragile=False, batch_number=0, forbidden_horizontal_dims=[]),
    ]
    diagnose(container, items)
