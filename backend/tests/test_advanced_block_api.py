"""端到端 API 测试：验证 /optimize-advanced-block 端点。"""
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.mark.asyncio
async def test_advanced_block_endpoint():
    """测试高级 Block 优化端点基本功能。"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/optimize-advanced-block", json={
            "container": {"length": 12000, "width": 2352, "height": 2395, "max_weight": 28000},
            "items": [
                {"id": "A", "length": 600, "width": 400, "height": 300, "weight": 15, "quantity": 10, "batch_number": 0},
                {"id": "B", "length": 600, "width": 400, "height": 300, "weight": 15, "quantity": 20, "batch_number": 1},
                {"id": "C", "length": 600, "width": 400, "height": 300, "weight": 15, "quantity": 10, "batch_number": 2},
            ],
        })

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["solution_type"] == "advanced_block"
    assert data["stats"]["total_items_placed"] > 0
    assert data["feasibility_report"]["is_feasible"] is True


@pytest.mark.asyncio
async def test_advanced_block_batch_ordering():
    """测试高级 Block 优化的批次顺序正确性。"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/optimize-advanced-block", json={
            "container": {"length": 12000, "width": 2352, "height": 2395, "max_weight": 28000},
            "items": [
                {"id": "A", "length": 600, "width": 400, "height": 300, "weight": 15, "quantity": 10, "batch_number": 0},
                {"id": "B", "length": 600, "width": 400, "height": 300, "weight": 15, "quantity": 20, "batch_number": 1},
                {"id": "C", "length": 600, "width": 400, "height": 300, "weight": 15, "quantity": 10, "batch_number": 2},
            ],
        })

    data = response.json()
    sku_to_batch = {"A": 0, "B": 1, "C": 2}
    batch_x = {0: [], 1: [], 2: []}
    for p in data["placements"]:
        batch = sku_to_batch.get(p["item_id"], 0)
        batch_x[batch].append(p["x"])

    b0 = sum(batch_x[0]) / len(batch_x[0]) if batch_x[0] else 0
    b2 = sum(batch_x[2]) / len(batch_x[2]) if batch_x[2] else 0

    # Batch0 应在 Batch2 前面（X 更小）
    assert b0 < b2, f"Batch0 (x={b0}) should be in front of Batch2 (x={b2})"


@pytest.mark.asyncio
async def test_advanced_block_invalid_input():
    """测试无效输入返回 422。"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/optimize-advanced-block", json={
            "container": {"length": -1, "width": 100, "height": 100, "max_weight": 1000},
            "items": [],
        })

    assert response.status_code == 422
