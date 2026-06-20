"""BlockOptimizer 单元测试。"""
import pytest
from app.engine.block_optimizer import BlockOptimizer, Block
from app.models.container import ContainerConfig
from app.models.item import ItemInput


def test_block_optimizer_single_item():
    """单个商品应能正常放置。"""
    packer = BlockOptimizer()
    container = ContainerConfig(length=100, width=100, height=100, max_weight=1000)
    items = [ItemInput(id="A", length=50, width=40, height=30, weight=5, quantity=1)]
    placements = packer.pack(container, items)
    assert len(placements) == 1
    assert placements[0]["item_id"] == "A"


def test_block_optimizer_multiple_same_items():
    """同 SKU 多件商品应形成 Block 聚集放置。"""
    packer = BlockOptimizer()
    container = ContainerConfig(length=400, width=400, height=400, max_weight=50000)
    items = [ItemInput(id="A", length=100, width=100, height=100, weight=10, quantity=20)]
    placements = packer.pack(container, items)
    assert len(placements) > 0
    # 所有 placement 应为 SKU A
    assert all(p["item_id"] == "A" for p in placements)


def test_block_optimizer_no_overlap():
    """放置结果不应有重叠。"""
    packer = BlockOptimizer()
    container = ContainerConfig(length=500, width=500, height=500, max_weight=50000)
    items = [
        ItemInput(id="A", length=100, width=80, height=60, weight=5, quantity=30),
        ItemInput(id="B", length=120, width=100, height=80, weight=8, quantity=20),
    ]
    placements = packer.pack(container, items)

    # 检查所有 placement 两两不重叠
    for i in range(len(placements)):
        for j in range(i + 1, len(placements)):
            a, b = placements[i], placements[j]
            overlap = (a["x"] < b["x"] + b["l"] and a["x"] + a["l"] > b["x"] and
                       a["y"] < b["y"] + b["h"] and a["y"] + a["h"] > b["y"] and
                       a["z"] < b["z"] + b["w"] and a["z"] + a["w"] > b["z"])
            assert not overlap, f"Placement {i} and {j} overlap"


def test_block_optimizer_within_bounds():
    """所有放置应在容器边界内。"""
    packer = BlockOptimizer()
    container = ContainerConfig(length=500, width=500, height=500, max_weight=50000)
    items = [
        ItemInput(id="A", length=100, width=80, height=60, weight=5, quantity=30),
        ItemInput(id="B", length=120, width=100, height=80, weight=8, quantity=20),
    ]
    placements = packer.pack(container, items)
    for p in placements:
        assert p["x"] >= 0
        assert p["y"] >= 0
        assert p["z"] >= 0
        assert p["x"] + p["l"] <= container.length + 0.001
        assert p["y"] + p["h"] <= container.height + 0.001
        assert p["z"] + p["w"] <= container.width + 0.001


def test_block_optimizer_weight_limit():
    """超过载重的商品应被跳过。"""
    packer = BlockOptimizer()
    container = ContainerConfig(length=1000, width=1000, height=1000, max_weight=10)
    items = [ItemInput(id="A", length=50, width=50, height=50, weight=100, quantity=5)]
    placements = packer.pack(container, items)
    assert len(placements) == 0


def test_block_optimizer_utilization_benchmark():
    """Block 优化应达到合理的空间利用率。"""
    packer = BlockOptimizer()
    container = ContainerConfig(length=1000, width=1000, height=1000, max_weight=500000)
    items = [
        ItemInput(id="A", length=200, width=200, height=200, weight=10, quantity=80),
    ]
    placements = packer.pack(container, items)
    placed_vol = sum(p["l"] * p["h"] * p["w"] for p in placements)
    container_vol = 1000 * 1000 * 1000
    utilization = placed_vol / container_vol
    # 200mm cubes in 1000mm container: 5*5*5=125 max. 80 items = 64% theoretical
    assert utilization >= 0.5, f"Utilization {utilization} too low"


def test_block_optimizer_same_sku_clustering():
    """同 SKU 商品应聚集放置（接触面积大）。"""
    packer = BlockOptimizer()
    container = ContainerConfig(length=600, width=600, height=600, max_weight=500000)
    items = [
        ItemInput(id="A", length=100, width=100, height=100, weight=5, quantity=50),
        ItemInput(id="B", length=100, width=100, height=100, weight=5, quantity=50),
    ]
    placements = packer.pack(container, items)

    # 统计同 SKU 邻接对数
    same_sku_adjacent = 0
    cross_sku_adjacent = 0
    for i in range(len(placements)):
        for j in range(i + 1, len(placements)):
            a, b = placements[i], placements[j]
            # 检查是否相邻（共享一个面）
            x_touch = (abs(a["x"] + a["l"] - b["x"]) < 1 or abs(b["x"] + b["l"] - a["x"]) < 1)
            y_touch = (abs(a["y"] + a["h"] - b["y"]) < 1 or abs(b["y"] + b["h"] - a["y"]) < 1)
            z_touch = (abs(a["z"] + a["w"] - b["z"]) < 1 or abs(b["z"] + b["w"] - a["z"]) < 1)
            adjacent = (x_touch and y_touch) or (x_touch and z_touch) or (y_touch and z_touch)
            if adjacent:
                if a["item_id"] == b["item_id"]:
                    same_sku_adjacent += 1
                else:
                    cross_sku_adjacent += 1

    # 同 SKU 邻接应多于跨 SKU 邻接（聚集效应）
    assert same_sku_adjacent > cross_sku_adjacent, \
        f"Same-SKU adjacent {same_sku_adjacent} should > cross-SKU {cross_sku_adjacent}"


def test_block_optimizer_multiple_skus():
    """多 SKU 场景应全部放置或合理利用空间。"""
    packer = BlockOptimizer()
    container = ContainerConfig(length=1200, width=1000, height=800, max_weight=500000)
    items = [
        ItemInput(id="A", length=120, width=100, height=80, weight=5, quantity=40),
        ItemInput(id="B", length=100, width=80, height=60, weight=3, quantity=30),
        ItemInput(id="C", length=80, width=60, height=40, weight=2, quantity=50),
    ]
    placements = packer.pack(container, items)
    total_qty = sum(i.quantity for i in items)
    # 物品总体积仅占容器 6.5%，应能全部放置
    assert len(placements) >= total_qty * 0.9, \
        f"Placed {len(placements)}/{total_qty}, expected >= 90%"


def test_block_optimizer_empty_items():
    """空物品列表应返回空结果。"""
    packer = BlockOptimizer()
    container = ContainerConfig(length=100, width=100, height=100, max_weight=1000)
    placements = packer.pack(container, [])
    assert len(placements) == 0
