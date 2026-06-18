"""验证贪心算法优化后的放满率和性能。"""
import sys
import time
import threading
sys.path.insert(0, ".")

from app.engine.packer import EPacker
from app.models.container import ContainerConfig
from app.models.item import ItemInput


def run_test(name, container, items, expected_max_util=None, timeout_sec=30):
    print(f"\n=== {name} ===")
    print(f"容器: {container.length} x {container.height} x {container.width} = "
          f"{container.length*container.height*container.width/1e9:.3f} m³")

    items_vol = sum(i.length * i.width * i.height * i.quantity for i in items)
    total_count = sum(i.quantity for i in items)
    print(f"物品总体积: {items_vol/1e9:.3f} m³, 总数量: {total_count}")
    theoretical_max = items_vol / (container.length * container.height * container.width) \
        if container.length * container.height * container.width > 0 else 0
    print(f"理论最大利用率: {theoretical_max:.2%}")

    result_box = {}

    def worker():
        try:
            packer = EPacker()
            t0 = time.time()
            result = packer.pack(container, items)
            result_box["time"] = time.time() - t0
            result_box["packer"] = packer
            result_box["result"] = result
        except Exception as e:
            result_box["error"] = e

    t = threading.Thread(target=worker, daemon=True)
    t.start()
    t.join(timeout_sec)

    if t.is_alive():
        print(f"  [超时] 超过 {timeout_sec}s 未完成")
        return None, theoretical_max, None

    if "error" in result_box:
        print(f"  [错误] {result_box['error']}")
        return None, theoretical_max, None

    packer = result_box["packer"]
    result = result_box["result"]
    elapsed = result_box["time"]

    actual_util = result.container_utilization
    placed_count = result.stats.total_items_placed
    unplaced_count = result.stats.total_items_unplaced
    placed_vol = sum(p["l"] * p["h"] * p["w"] for p in packer.placements)

    if packer.placements:
        max_x = max(p["x"] + p["l"] for p in packer.placements)
        max_y = max(p["y"] + p["h"] for p in packer.placements)
        max_z = max(p["z"] + p["w"] for p in packer.placements)
        bbox_vol = max_x * max_y * max_z
        bbox_util = placed_vol / bbox_vol if bbox_vol > 0 else 0
    else:
        max_x = max_y = max_z = 0
        bbox_util = 0

    print(f"耗时: {elapsed:.2f}s")
    print(f"实际利用率(容器): {actual_util:.2%}")
    print(f"放置: {placed_count}/{total_count}, 未放置: {unplaced_count}")
    print(f"边界框: x={max_x}, y={max_y}, z={max_z}")
    print(f"边界框内利用率: {bbox_util:.2%}")
    if theoretical_max > 0:
        ratio = actual_util / theoretical_max
        print(f"利用率/理论最大: {ratio:.2%}")

    if expected_max_util is not None and actual_util < expected_max_util:
        print(f"  [警告] 期望至少 {expected_max_util:.2%}，实际 {actual_util:.2%}")

    for u in result.unplaced_items:
        print(f"  未放置: {u.item_id} x{u.quantity} - {u.reason}")

    return actual_util, theoretical_max, elapsed


# === 测试 1: 完美匹配立方体 ===
container1 = ContainerConfig(length=500, width=500, height=500, max_weight=1e9)
items1 = [ItemInput(id="A", length=100, width=100, height=100, weight=1, quantity=125,
                    is_fragile=False, batch_number=0, forbidden_horizontal_dims=[])]
run_test("测试1: 完美匹配 100³ × 125个 in 500³", container1, items1, 0.95)

# === 测试 2: 中等数量小立方体 ===
container2 = ContainerConfig(length=600, width=600, height=600, max_weight=1e9)
items2 = [ItemInput(id="A", length=100, width=100, height=100, weight=1, quantity=200,
                    is_fragile=False, batch_number=0, forbidden_horizontal_dims=[])]
run_test("测试2: 100³ × 200个 in 600³", container2, items2, 0.85)

# === 测试 3: 不能完美整除（之前超时） ===
container3 = ContainerConfig(length=500, width=500, height=500, max_weight=1e9)
items3 = [ItemInput(id="A", length=30, width=30, height=30, weight=1, quantity=4000,
                    is_fragile=False, batch_number=0, forbidden_horizontal_dims=[])]
run_test("测试3: 30³ × 4000个 in 500³ (之前超时)", container3, items3, 0.7, timeout_sec=60)

# === 测试 4: 混合尺寸物品 ===
container4 = ContainerConfig(length=600, width=600, height=600, max_weight=1e9)
items4 = [
    ItemInput(id="大", length=300, width=300, height=300, weight=1, quantity=5,
              is_fragile=False, batch_number=0, forbidden_horizontal_dims=[]),
    ItemInput(id="中", length=150, width=150, height=150, weight=1, quantity=30,
              is_fragile=False, batch_number=0, forbidden_horizontal_dims=[]),
    ItemInput(id="小", length=50, width=50, height=50, weight=1, quantity=200,
              is_fragile=False, batch_number=0, forbidden_horizontal_dims=[]),
]
run_test("测试4: 混合尺寸 in 600³", container4, items4, 0.6)

# === 测试 5: 长方体物品 ===
container5 = ContainerConfig(length=600, width=600, height=600, max_weight=1e9)
items5 = [ItemInput(id="A", length=200, width=100, height=50, weight=1, quantity=200,
                    is_fragile=False, batch_number=0, forbidden_horizontal_dims=[])]
run_test("测试5: 200x100x50 × 200个 in 600³", container5, items5, 0.85)

# === 测试 6: 大尺寸物品 ===
container6 = ContainerConfig(length=1000, width=1000, height=1000, max_weight=1e9)
items6 = [ItemInput(id="A", length=500, width=500, height=500, weight=1, quantity=8,
                    is_fragile=False, batch_number=0, forbidden_horizontal_dims=[])]
run_test("测试6: 500³ × 8个 in 1000³", container6, items6, 0.95)

# === 测试 7: 真实场景（货车装载，之前超时） ===
container7 = ContainerConfig(length=5898, width=2352, height=2395, max_weight=1e9)
items7 = [
    ItemInput(id="箱A", length=600, width=400, height=300, weight=10, quantity=100,
              is_fragile=False, batch_number=0, forbidden_horizontal_dims=[]),
    ItemInput(id="箱B", length=500, width=400, height=350, weight=10, quantity=50,
              is_fragile=False, batch_number=0, forbidden_horizontal_dims=[]),
    ItemInput(id="箱C", length=400, width=300, height=250, weight=5, quantity=150,
              is_fragile=False, batch_number=0, forbidden_horizontal_dims=[]),
]
run_test("测试7: 货车装载混合箱 (之前超时)", container7, items7, 0.5, timeout_sec=60)

# === 测试 8: 完美填充 ===
container8 = ContainerConfig(length=1200, width=800, height=600, max_weight=1e9)
items8 = [ItemInput(id="A", length=400, width=400, height=200, weight=1, quantity=18,
                    is_fragile=False, batch_number=0, forbidden_horizontal_dims=[])]
run_test("测试8: 完美填充 400x400x200 × 18个", container8, items8, 0.95)

# === 测试 9: 非常小的物品（之前超时） ===
container9 = ContainerConfig(length=500, width=500, height=500, max_weight=1e9)
items9 = [ItemInput(id="A", length=50, width=50, height=50, weight=1, quantity=1000,
                    is_fragile=False, batch_number=0, forbidden_horizontal_dims=[])]
run_test("测试9: 50³ × 1000个 in 500³ (之前超时)", container9, items9, 0.9, timeout_sec=60)

# === 测试 10: 大规模压力测试 ===
container10 = ContainerConfig(length=1000, width=1000, height=1000, max_weight=1e9)
items10 = [ItemInput(id="A", length=50, width=50, height=50, weight=1, quantity=8000,
                     is_fragile=False, batch_number=0, forbidden_horizontal_dims=[])]
run_test("测试10: 50³ × 8000个 in 1000³ (大规模)", container10, items10, 0.9, timeout_sec=60)

print("\n" + "=" * 60)
print("测试完成")
