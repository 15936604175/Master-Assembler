"""验证用户报告的场景：所有 batch_number=0，V2 应能全部放置。"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.engine.advanced_block_optimizer import AdvancedBlockOptimizer
from app.engine.block_optimizer import BlockOptimizer
from app.models.container import ContainerConfig
from app.models.item import ItemInput


def test_user_scenario():
    """用户场景：4 SKU，全 batch 0，140 件。"""
    print("=" * 60)
    print("用户场景验证：4 SKU × 全 batch 0 × 140 件")
    print("=" * 60)

    container = ContainerConfig(length=12032, width=2352, height=2695, max_weight=28000)
    items = [
        ItemInput(id="A", length=1000, width=800, height=600, weight=10, quantity=50, batch_number=0),
        ItemInput(id="B", length=600, width=600, height=300, weight=10, quantity=50, batch_number=0),
        ItemInput(id="C", length=1200, width=1000, height=1000, weight=10, quantity=10, batch_number=0),
        ItemInput(id="D", length=800, width=800, height=600, weight=10, quantity=30, batch_number=0),
    ]
    total_qty = sum(i.quantity for i in items)
    print(f"总物品数: {total_qty}")

    # V1
    print("\n[V1 BlockOptimizer]")
    v1 = BlockOptimizer()
    v1_placements = v1.pack(container, items)
    v1_vol = sum(p["l"] * p["h"] * p["w"] for p in v1_placements)
    v1_util = v1_vol / (container.length * container.height * container.width)
    print(f"  放置: {len(v1_placements)}/{total_qty}, 利用率: {v1_util*100:.2f}%")

    # V2
    print("\n[V2 AdvancedBlockOptimizer]")
    v2 = AdvancedBlockOptimizer()
    v2_placements = v2.pack(container, items)
    v2_vol = sum(p["l"] * p["h"] * p["w"] for p in v2_placements)
    v2_util = v2_vol / (container.length * container.height * container.width)
    print(f"  放置: {len(v2_placements)}/{total_qty}, 利用率: {v2_util*100:.2f}%")

    # 验证
    print("\n[验证]")
    if len(v2_placements) >= len(v1_placements):
        print(f"  ✓ V2 放置数量 ({len(v2_placements)}) >= V1 ({len(v1_placements)})")
    else:
        print(f"  ✗ V2 放置数量 ({len(v2_placements)}) < V1 ({len(v1_placements)})")

    if len(v2_placements) == total_qty:
        print(f"  ✓ V2 全部放置")
    else:
        # 统计未放置
        from collections import Counter
        placed = Counter(p["item_id"] for p in v2_placements)
        for item in items:
            unplaced = item.quantity - placed.get(item.id, 0)
            if unplaced > 0:
                print(f"  ✗ {item.id} 未放置 {unplaced} 件")


if __name__ == "__main__":
    test_user_scenario()
