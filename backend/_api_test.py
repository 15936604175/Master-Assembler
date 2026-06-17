import sys, time, json
sys.path.insert(0, ".")

from httpx import AsyncClient, ASGITransport
import asyncio
from app.main import app


async def main():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "container": {"length": 5898, "width": 2352, "height": 2395, "max_weight": 28000},
            "items": [
                {"id": "A", "length": 100, "width": 100, "height": 100, "weight": 10, "quantity": 50,
                 "is_fragile": False, "batch_number": 0, "forbidden_horizontal_dims": []},
                {"id": "B", "length": 200, "width": 200, "height": 200, "weight": 10, "quantity": 20,
                 "is_fragile": False, "batch_number": 0, "forbidden_horizontal_dims": []},
            ]
        }

        t0 = time.time()
        resp = await client.post("/api/optimize", json=payload)
        t1 = time.time()
        d = resp.json()

        print(f"API /api/optimize ({t1-t0:.2f}s)")
        print(f"  placed: {d['stats']['total_items_placed']}")
        print(f"  unplaced: {d['stats']['total_items_unplaced']}")
        print(f"  util: {d['container_utilization']}")
        print(f"  cg: {d['center_of_gravity']}")
        print(f"  cg_deviation_ratio: {d['cg_deviation_ratio']}")
        for u in d.get('unplaced_items', []):
            print(f"  unplaced: {u}")

        t2 = time.time()
        resp2 = await client.post("/api/optimize-phase2?enable_ga=true&enable_ls=true&enable_pareto=false&timeout_seconds=120", json=payload)
        t3 = time.time()
        d2 = resp2.json()

        print(f"\nAPI /api/optimize-phase2 ({t3-t2:.2f}s)")
        for name, key in [("greedy", "primary"), ("ga", "ga_solution"), ("ls", "ls_solution")]:
            sol = d2.get(key)
            if sol is None:
                print(f"  {name}: None")
                continue
            print(f"  {name}: placed={sol['stats']['total_items_placed']} unplaced={sol['stats']['total_items_unplaced']} util={sol['container_utilization']} cg_dev={sol.get('cg_deviation_ratio')}")


asyncio.run(main())
