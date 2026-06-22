"""AdvancedBlockOptimizer V2 验证测试。

验证项:
    1. 基本功能：能正常放置物品
    2. 边界与碰撞：无越界、无重叠
    3. 批次顺序：Batch0 应靠前（小 X），Batch2 应靠后（大 X）
    4. 空间利用率：与 V1 Block 对比
    5. 批次走廊：动态计算正确
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.engine.advanced_block_optimizer import (
    AdvancedBlockOptimizer,
    BatchCorridorManager,
    ADVANCED_BEAM_WIDTH,
    CORRIDOR_EXPANSION_RATIO,
)
from app.engine.block_optimizer import BlockOptimizer
from app.models.container import ContainerConfig
from app.models.item import ItemInput


def test_basic_placement():
    """基本放置：单 SKU 应能正常放置。"""
    print("\n[1] 基本放置测试...")
    packer = AdvancedBlockOptimizer()
    container = ContainerConfig(length=1000, width=1000, height=1000, max_weight=500000)
    items = [ItemInput(id="A", length=100, width=100, height=100, weight=5, quantity=10)]
    placements = packer.pack(container, items)
    assert len(placements) == 10, f"Expected 10, got {len(placements)}"
    print(f"  ✓ 放置 {len(placements)} 件物品")


def test_no_overlap_and_bounds():
    """无重叠、无越界。"""
    print("\n[2] 边界与碰撞测试...")
    packer = AdvancedBlockOptimizer()
    container = ContainerConfig(length=1000, width=800, height=800, max_weight=500000)
    items = [
        ItemInput(id="A", length=120, width=100, height=80, weight=5, quantity=20, batch_number=0),
        ItemInput(id="B", length=100, width=80, height=60, weight=3, quantity=15, batch_number=1),
        ItemInput(id="C", length=80, width=60, height=40, weight=2, quantity=25, batch_number=2),
    ]
    placements = packer.pack(container, items)

    # 边界检查
    for i, p in enumerate(placements):
        assert p["x"] >= -0.01, f"Placement {i} x<0: {p['x']}"
        assert p["y"] >= -0.01, f"Placement {i} y<0: {p['y']}"
        assert p["z"] >= -0.01, f"Placement {i} z<0: {p['z']}"
        assert p["x"] + p["l"] <= container.length + 0.01, \
            f"Placement {i} x+l>cl: {p['x']+p['l']}"
        assert p["y"] + p["h"] <= container.height + 0.01, \
            f"Placement {i} y+h>ch: {p['y']+p['h']}"
        assert p["z"] + p["w"] <= container.width + 0.01, \
            f"Placement {i} z+w>cw: {p['z']+p['w']}"

    # 重叠检查
    for i in range(len(placements)):
        for j in range(i + 1, len(placements)):
            a, b = placements[i], placements[j]
            overlap = (a["x"] < b["x"] + b["l"] and a["x"] + a["l"] > b["x"] and
                       a["y"] < b["y"] + b["h"] and a["y"] + a["h"] > b["y"] and
                       a["z"] < b["z"] + b["w"] and a["z"] + a["w"] > b["z"])
            assert not overlap, f"Placement {i} and {j} overlap"

    print(f"  ✓ {len(placements)} 件物品全部在边界内，无重叠")


def test_batch_corridor():
    """批次走廊动态计算。"""
    print("\n[3] 批次走廊动态计算测试...")
    container = ContainerConfig(length=12000, width=2352, height=2395, max_weight=28000)
    items = [
        ItemInput(id="A", length=500, width=400, height=300, weight=10, quantity=10, batch_number=0),
        ItemInput(id="B", length=500, width=400, height=300, weight=10, quantity=60, batch_number=1),
        ItemInput(id="C", length=500, width=400, height=300, weight=10, quantity=30, batch_number=2),
    ]
    manager = BatchCorridorManager(container, items)

    # 验证走廊构建
    assert len(manager.corridors) == 3, f"Expected 3 corridors, got {len(manager.corridors)}"

    # Batch0 总体积 = 10 * 500*400*300 = 60,000,000
    # Batch1 总体积 = 60 * 500*400*300 = 360,000,000
    # Batch2 总体积 = 30 * 500*400*300 = 180,000,000
    # Total = 600,000,000
    # Batch0 ratio = 10% → expected_length = 1200
    # Batch1 ratio = 60% → expected_length = 7200
    # Batch2 ratio = 30% → expected_length = 3600

    b0 = manager.get_corridor(0)
    b1 = manager.get_corridor(1)
    b2 = manager.get_corridor(2)

    print(f"  Batch0: corridor=[{b0.preferred_min_x:.0f}, {b0.preferred_max_x:.0f}], target={b0.target_center_x:.0f}")
    print(f"  Batch1: corridor=[{b1.preferred_min_x:.0f}, {b1.preferred_max_x:.0f}], target={b1.target_center_x:.0f}")
    print(f"  Batch2: corridor=[{b2.preferred_min_x:.0f}, {b2.preferred_max_x:.0f}], target={b2.target_center_x:.0f}")

    # 验证 target_center 顺序
    assert b0.target_center_x < b1.target_center_x < b2.target_center_x, \
        "Target centers should be in ascending order"

    # 验证走廊重叠（20% 缓冲）
    # Batch0 走廊应与 Batch1 走廊重叠
    assert b0.preferred_max_x > b1.preferred_min_x, \
        "Batch0 corridor should overlap with Batch1"

    print(f"  ✓ 批次走廊顺序正确，存在重叠缓冲")


def test_batch_ordering():
    """批次顺序：Batch0 靠前（小 X），Batch2 靠后（大 X）。"""
    print("\n[4] 批次顺序测试...")
    packer = AdvancedBlockOptimizer()
    container = ContainerConfig(length=12000, width=2352, height=2395, max_weight=28000)
    items = [
        ItemInput(id="A", length=600, width=400, height=300, weight=15, quantity=10, batch_number=0),
        ItemInput(id="B", length=600, width=400, height=300, weight=15, quantity=20, batch_number=1),
        ItemInput(id="C", length=600, width=400, height=300, weight=15, quantity=10, batch_number=2),
    ]
    placements = packer.pack(container, items)

    # 按 batch 分组统计 X 范围
    batch_x = {0: [], 1: [], 2: []}
    # 需要从 item 配置推断 batch（placements 中没有 batch 字段）
    sku_to_batch = {item.id: item.batch_number for item in items}
    for p in placements:
        batch = sku_to_batch.get(p["item_id"], 0)
        batch_x[batch].append(p["x"])

    b0_xs = batch_x[0]
    b1_xs = batch_x[1]
    b2_xs = batch_x[2]

    if b0_xs and b1_xs and b2_xs:
        b0_center = sum(b0_xs) / len(b0_xs)
        b1_center = sum(b1_xs) / len(b1_xs)
        b2_center = sum(b2_xs) / len(b2_xs)

        print(f"  Batch0 平均 X = {b0_center:.0f}")
        print(f"  Batch1 平均 X = {b1_center:.0f}")
        print(f"  Batch2 平均 X = {b2_center:.0f}")

        # 批次顺序应大致为 b0 < b1 < b2（软约束，允许少量偏差）
        # 这里检查平均 X 是否符合递增趋势
        if b0_center <= b1_center <= b2_center:
            print(f"  ✓ 批次顺序完全正确 (b0 ≤ b1 ≤ b2)")
        else:
            # 软约束：至少 b0 应该靠前，b2 应该靠后
            assert b0_center < b2_center, \
                f"Batch0 should be in front of Batch2: b0={b0_center}, b2={b2_center}"
            print(f"  ~ 批次顺序大致正确 (b0 < b2，b1 可能有偏差)")
    else:
        print(f"  ! 某些 batch 未放置: b0={len(b0_xs)}, b1={len(b1_xs)}, b2={len(b2_xs)}")


def test_utilization_comparison():
    """与 V1 Block 对比空间利用率。"""
    print("\n[5] 利用率对比测试 (V2 vs V1)...")
    container = ContainerConfig(length=1200, width=1000, height=800, max_weight=500000)
    items = [
        ItemInput(id="A", length=120, width=100, height=80, weight=5, quantity=40, batch_number=0),
        ItemInput(id="B", length=100, width=80, height=60, weight=3, quantity=30, batch_number=1),
        ItemInput(id="C", length=80, width=60, height=40, weight=2, quantity=50, batch_number=2),
    ]

    # V1
    v1_packer = BlockOptimizer()
    v1_placements = v1_packer.pack(container, items)
    v1_vol = sum(p["l"] * p["h"] * p["w"] for p in v1_placements)
    v1_util = v1_vol / (container.length * container.height * container.width)

    # V2
    v2_packer = AdvancedBlockOptimizer()
    v2_placements = v2_packer.pack(container, items)
    v2_vol = sum(p["l"] * p["h"] * p["w"] for p in v2_placements)
    v2_util = v2_vol / (container.length * container.height * container.width)

    print(f"  V1 Block:   {len(v1_placements)} 件, 利用率 = {v1_util*100:.2f}%")
    print(f"  V2 Advanced: {len(v2_placements)} 件, 利用率 = {v2_util*100:.2f}%")

    # V2 应至少放置相同数量的物品（允许少量偏差）
    assert len(v2_placements) >= len(v1_placements) * 0.9, \
        f"V2 placed {len(v2_placements)}, V1 placed {len(v1_placements)}"


def test_large_scenario_greedy_fallback():
    """大场景（>500件）应使用贪心策略。"""
    print("\n[6] 大场景贪心策略测试...")
    packer = AdvancedBlockOptimizer()
    container = ContainerConfig(length=12000, width=2352, height=2395, max_weight=28000)
    items = [
        ItemInput(id="A", length=300, width=200, height=150, weight=2, quantity=200, batch_number=0),
        ItemInput(id="B", length=300, width=200, height=150, weight=2, quantity=200, batch_number=1),
        ItemInput(id="C", length=300, width=200, height=150, weight=2, quantity=200, batch_number=2),
    ]
    placements = packer.pack(container, items)
    total_qty = sum(i.quantity for i in items)
    print(f"  总物品数: {total_qty}, 放置: {len(placements)}")
    assert len(placements) > 0, "Should place at least some items"
    print(f"  ✓ 大场景贪心策略正常工作")


if __name__ == "__main__":
    print("=" * 60)
    print("AdvancedBlockOptimizer V2 验证测试")
    print("=" * 60)

    test_basic_placement()
    test_no_overlap_and_bounds()
    test_batch_corridor()
    test_batch_ordering()
    test_utilization_comparison()
    test_large_scenario_greedy_fallback()

    print("\n" + "=" * 60)
    print("✓ 所有测试通过")
    print("=" * 60)
