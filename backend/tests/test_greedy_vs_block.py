"""贪心算法 vs Block 优化 对比测试。

运行方式:
    cd backend && python -m tests.test_greedy_vs_block
或:
    cd backend && python -m pytest tests/test_greedy_vs_block.py -v -s
"""
import time
from app.engine.packer import EPacker
from app.engine.block_optimizer import BlockOptimizer
from app.models.container import ContainerConfig
from app.models.item import ItemInput


def _run_comparison(container, items, label=""):
    """运行贪心和 Block 优化，返回对比结果。"""
    print(f"\n{'='*60}")
    print(f"场景: {label}")
    print(f"容器: {container.length}×{container.width}×{container.height}mm, 载重 {container.max_weight}kg")
    total_qty = sum(i.quantity for i in items)
    print(f"商品: {len(items)} 种 SKU, 共 {total_qty} 件")
    print(f"{'='*60}")

    # 贪心算法
    packer = EPacker()
    t0 = time.time()
    greedy_result = packer.pack(container, items)
    greedy_time = (time.time() - t0) * 1000

    # Block 优化
    block_packer = BlockOptimizer()
    t0 = time.time()
    block_placements = block_packer.pack(container, items)
    block_time = (time.time() - t0) * 1000

    # 计算利用率
    container_vol = container.length * container.height * container.width
    # greedy_result.placements 是 Placement 对象（属性访问）
    greedy_vol = sum(p.length * p.height * p.width for p in greedy_result.placements)
    # block_placements 是 dict 列表（键访问）
    block_vol = sum(p["l"] * p["h"] * p["w"] for p in block_placements)
    greedy_util = greedy_vol / container_vol if container_vol > 0 else 0
    block_util = block_vol / container_vol if container_vol > 0 else 0

    print(f"\n  贪心算法 (EPacker):")
    print(f"    放置数量:   {len(greedy_result.placements)}")
    print(f"    空间利用率: {greedy_util:.2%}")
    print(f"    耗时:       {greedy_time:.1f}ms")

    print(f"\n  Block 优化 (BlockOptimizer):")
    print(f"    放置数量:   {len(block_placements)}")
    print(f"    空间利用率: {block_util:.2%}")
    print(f"    耗时:       {block_time:.1f}ms")

    diff = block_util - greedy_util
    winner = "Block 优化" if block_util > greedy_util else "贪心算法"
    print(f"\n  → 利用率差异: {diff:+.2%} ({winner} 胜出)")

    return greedy_util, block_util, greedy_time, block_time


def test_scenario_single_sku_large_quantity():
    """场景1: 单 SKU 大批量（Block 优势场景）。"""
    container = ContainerConfig(length=1200, width=1000, height=800, max_weight=500000)
    items = [
        ItemInput(id="A", length=200, width=150, height=100, weight=5, quantity=200),
    ]
    g, b, gt, bt = _run_comparison(container, items, "单 SKU 大批量")
    # Block 优化在此场景应不劣于贪心
    assert b >= g - 0.05, f"Block util {b:.2%} should be close to greedy {g:.2%}"


def test_scenario_multiple_skus():
    """场景2: 多 SKU 中等数量。"""
    container = ContainerConfig(length=1200, width=1000, height=800, max_weight=500000)
    items = [
        ItemInput(id="A", length=200, width=150, height=100, weight=5, quantity=50),
        ItemInput(id="B", length=150, width=120, height=80, weight=3, quantity=60),
        ItemInput(id="C", length=100, width=80, height=60, weight=2, quantity=80),
    ]
    g, b, gt, bt = _run_comparison(container, items, "多 SKU 中等数量")
    assert b > 0.2, f"Block util {b:.2%} too low"


def test_scenario_mixed_sizes():
    """场景3: 混合尺寸商品。"""
    container = ContainerConfig(length=1500, width=1200, height=1000, max_weight=500000)
    items = [
        ItemInput(id="LARGE", length=400, width=300, height=200, weight=20, quantity=10),
        ItemInput(id="MEDIUM", length=200, width=150, height=100, weight=8, quantity=40),
        ItemInput(id="SMALL", length=80, width=60, height=50, weight=2, quantity=100),
    ]
    g, b, gt, bt = _run_comparison(container, items, "混合尺寸商品")
    assert b > 0.2, f"Block util {b:.2%} too low"


def test_scenario_cubic_items():
    """场景4: 立方体商品（完美堆叠场景）。"""
    container = ContainerConfig(length=1000, width=1000, height=1000, max_weight=500000)
    items = [
        ItemInput(id="CUBE", length=200, width=200, height=200, weight=10, quantity=100),
    ]
    g, b, gt, bt = _run_comparison(container, items, "立方体商品（完美堆叠）")
    # 立方体场景 Block 优化应表现优秀
    assert b >= 0.5, f"Block util {b:.2%} too low for cubic items"


def test_scenario_high_volume():
    """场景5: 大批量场景（>300 件，验证性能）。"""
    container = ContainerConfig(length=2000, width=1500, height=1200, max_weight=500000)
    items = [
        ItemInput(id="A", length=150, width=100, height=80, weight=3, quantity=150),
        ItemInput(id="B", length=120, width=80, height=60, weight=2, quantity=200),
    ]
    g, b, gt, bt = _run_comparison(container, items, "大批量场景（350件）")
    # 验证 Block 优化在大批量下仍能在合理时间内完成
    assert bt < 30000, f"Block time {bt:.0f}ms too slow for 350 items"


def test_no_overlap_block():
    """验证 Block 优化结果无重叠。"""
    container = ContainerConfig(length=1000, width=800, height=600, max_weight=500000)
    items = [
        ItemInput(id="A", length=150, width=100, height=80, weight=5, quantity=50),
        ItemInput(id="B", length=100, width=80, height=60, weight=3, quantity=40),
    ]
    block_packer = BlockOptimizer()
    placements = block_packer.pack(container, items)

    for i in range(len(placements)):
        for j in range(i + 1, len(placements)):
            a, b = placements[i], placements[j]
            overlap = (a["x"] < b["x"] + b["l"] and a["x"] + a["l"] > b["x"] and
                       a["y"] < b["y"] + b["h"] and a["y"] + a["h"] > b["y"] and
                       a["z"] < b["z"] + b["w"] and a["z"] + a["w"] > b["z"])
            assert not overlap, f"Block placement {i} and {j} overlap"


def test_block_within_bounds():
    """验证 Block 优化结果在容器边界内。"""
    container = ContainerConfig(length=1000, width=800, height=600, max_weight=500000)
    items = [
        ItemInput(id="A", length=150, width=100, height=80, weight=5, quantity=50),
        ItemInput(id="B", length=100, width=80, height=60, weight=3, quantity=40),
    ]
    block_packer = BlockOptimizer()
    placements = block_packer.pack(container, items)

    for p in placements:
        assert p["x"] >= 0 and p["x"] + p["l"] <= container.length + 0.001
        assert p["y"] >= 0 and p["y"] + p["h"] <= container.height + 0.001
        assert p["z"] >= 0 and p["z"] + p["w"] <= container.width + 0.001


if __name__ == "__main__":
    print("贪心算法 vs Block 优化 对比测试")
    print("=" * 60)

    results = []

    # 场景1: 单 SKU 超量（物品超过容器容量，测试谁能装更多）
    container = ContainerConfig(length=1000, width=1000, height=1000, max_weight=500000)
    items = [ItemInput(id="A", length=200, width=200, height=200, weight=10, quantity=200)]
    results.append(("单SKU超量(200>125)", *_run_comparison(container, items, "单 SKU 超量 (200件>125max)")))

    # 场景2: 多 SKU 超量
    container = ContainerConfig(length=1200, width=1000, height=800, max_weight=500000)
    items = [
        ItemInput(id="A", length=200, width=150, height=100, weight=5, quantity=300),
        ItemInput(id="B", length=150, width=120, height=80, weight=3, quantity=300),
        ItemInput(id="C", length=100, width=80, height=60, weight=2, quantity=300),
    ]
    results.append(("多SKU超量(900件)", *_run_comparison(container, items, "多 SKU 超量 (900件)")))

    # 场景3: 混合尺寸超量
    container = ContainerConfig(length=1500, width=1200, height=1000, max_weight=500000)
    items = [
        ItemInput(id="LARGE", length=400, width=300, height=200, weight=20, quantity=50),
        ItemInput(id="MEDIUM", length=200, width=150, height=100, weight=8, quantity=200),
        ItemInput(id="SMALL", length=80, width=60, height=50, weight=2, quantity=500),
    ]
    results.append(("混合尺寸超量(750件)", *_run_comparison(container, items, "混合尺寸超量 (750件)")))

    # 场景4: 立方体超量（完美堆叠场景，200>125max）
    container = ContainerConfig(length=1000, width=1000, height=1000, max_weight=500000)
    items = [ItemInput(id="CUBE", length=200, width=200, height=200, weight=10, quantity=200)]
    results.append(("立方体超量(200>125)", *_run_comparison(container, items, "立方体超量 (200件>125max)")))

    # 场景5: 大批量超量（>500 件，验证性能和利用率）
    container = ContainerConfig(length=2000, width=1500, height=1200, max_weight=500000)
    items = [
        ItemInput(id="A", length=150, width=100, height=80, weight=3, quantity=800),
        ItemInput(id="B", length=120, width=80, height=60, weight=2, quantity=800),
    ]
    results.append(("大批量超量(1600件)", *_run_comparison(container, items, "大批量超量 (1600件)")))

    # 场景6: 适中尺寸超量（更贴近实际场景）
    container = ContainerConfig(length=1200, width=1000, height=800, max_weight=500000)
    items = [
        ItemInput(id="BOX-A", length=300, width=200, height=150, weight=8, quantity=100),
        ItemInput(id="BOX-B", length=250, width=180, height=120, weight=6, quantity=100),
    ]
    results.append(("适中尺寸超量(200件)", *_run_comparison(container, items, "适中尺寸超量 (200件)")))

    print(f"\n\n{'='*60}")
    print("汇总对比")
    print(f"{'='*60}")
    print(f"{'场景':<22} {'贪心利用率':>12} {'Block利用率':>12} {'差异':>10} {'贪心耗时':>10} {'Block耗时':>10}")
    print("-" * 82)
    for name, g, b, gt, bt in results:
        diff = b - g
        print(f"{name:<22} {g:>11.2%} {b:>11.2%} {diff:>+9.2%} {gt:>9.0f}ms {bt:>9.0f}ms")
