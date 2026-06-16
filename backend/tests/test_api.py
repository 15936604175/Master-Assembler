import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.mark.asyncio
async def test_optimize_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/optimize", json={
            "container": {"length": 100, "width": 100, "height": 100, "max_weight": 1000},
            "items": [{"id": "A", "length": 50, "width": 40, "height": 30, "weight": 5, "quantity": 1}],
        })
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert len(data["placements"]) == 1
    assert data["placements"][0]["item_id"] == "A"


@pytest.mark.asyncio
async def test_optimize_invalid_input():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/optimize", json={
            "container": {"length": -1, "width": 100, "height": 100, "max_weight": 1000},
            "items": [],
        })
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_optimize_health_check():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
