# 箱智 (X-Intelligence) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) for syntax tracking.

**Goal:** Build a container loading optimization system with FastAPI backend and React + Three.js frontend

**Architecture:** FastAPI monolith with algorithm engine module, React SPA with @react-three/fiber 3D visualization. Extreme Point algorithm + 6-rotation + volume sort + space cutting.

**Tech Stack:** Python 3.11+, FastAPI, pytest, React 18, TypeScript, Three.js/@react-three/fiber, Ant Design, framer-motion, vitest

---

## File Structure

```
F:\Master-Assembler\
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py
│   │   ├── containers.json
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   └── optimize.py
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── container.py
│   │   │   ├── item.py
│   │   │   └── solution.py
│   │   └── engine/
│   │       ├── __init__.py
│   │       ├── packer.py
│   │       ├── extreme_point.py
│   │       ├── rotation.py
│   │       └── space_cutter.py
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── test_rotation.py
│   │   ├── test_extreme_point.py
│   │   ├── test_space_cutter.py
│   │   └── test_packer.py
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.tsx
│   │   ├── App.css
│   │   ├── components/
│   │   │   ├── ControlPanel.tsx
│   │   │   ├── ContainerConfig.tsx
│   │   │   ├── ItemListEditor.tsx
│   │   │   ├── Layout3D.tsx
│   │   │   ├── PlacedItem.tsx
│   │   │   ├── ResultPanel.tsx
│   │   │   └── UtilizationBar.tsx
│   │   ├── services/
│   │   │   └── api.ts
│   │   └── types/
│   │       └── index.ts
│   ├── index.html
│   ├── package.json
│   ├── tsconfig.json
│   ├── vite.config.ts
│   └── vitest.config.ts
└── docs/
    └── superpowers/
        └── specs/
            └── 2026-06-16-master-assembler-design.md
```

---

### Task 1: Backend scaffolding

**Files:**
- Create: `backend/requirements.txt`
- Create: `backend/app/__init__.py`
- Create: `backend/app/api/__init__.py`
- Create: `backend/app/models/__init__.py`
- Create: `backend/app/engine/__init__.py`
- Create: `backend/tests/__init__.py`
- Create: `backend/app/containers.json`

- [ ] **Step 1: Create requirements.txt**

```
fastapi==0.111.0
uvicorn==0.29.0
pydantic==2.7.0
pytest==8.1.0
httpx==0.27.0
```

File: `backend/requirements.txt`

- [ ] **Step 2: Create init files and containers.json**

```
# backend/app/__init__.py  (empty)
# backend/app/api/__init__.py  (empty)
# backend/app/models/__init__.py  (empty)
# backend/app/engine/__init__.py  (empty)
# backend/tests/__init__.py  (empty)
```

File: `backend/app/containers.json`
```json
{
  "presets": [
    { "id": "20GP", "name": "20尺普柜", "length": 5898, "width": 2352, "height": 2395, "max_weight": 28000 },
    { "id": "40GP", "name": "40尺普柜", "length": 12032, "width": 2352, "height": 2395, "max_weight": 28000 },
    { "id": "40HQ", "name": "40尺高柜", "length": 12032, "width": 2352, "height": 2695, "max_weight": 28000 }
  ]
}
```

---

### Task 2: Data models

**Files:**
- Create: `backend/app/models/container.py`
- Create: `backend/app/models/item.py`
- Create: `backend/app/models/solution.py`

- [ ] **Step 1: Write tests for models**

File: `backend/tests/` (models will be tested implicitly via packer tests, but create basic validation tests)

- [ ] **Step 2: Implement container model**

```python
from pydantic import BaseModel, Field

class ContainerConfig(BaseModel):
    length: float = Field(gt=0, description="Container inner length (mm)")
    width: float = Field(gt=0, description="Container inner width (mm)")
    height: float = Field(gt=0, description="Container inner height (mm)")
    max_weight: float = Field(gt=0, description="Maximum load weight (kg)")
```

File: `backend/app/models/container.py`

- [ ] **Step 3: Implement item model**

```python
from pydantic import BaseModel, Field

class ItemInput(BaseModel):
    id: str = Field(min_length=1, description="Item SKU ID")
    length: float = Field(gt=0, description="Item length (mm)")
    width: float = Field(gt=0, description="Item width (mm)")
    height: float = Field(gt=0, description="Item height (mm)")
    weight: float = Field(gt=0, description="Item weight (kg)")
    quantity: int = Field(gt=0, le=10000, description="Item quantity")

class ItemInstance(BaseModel):
    item_id: str
    length: float
    width: float
    height: float
    weight: float
```

File: `backend/app/models/item.py`

- [ ] **Step 4: Implement solution model**

```python
from pydantic import BaseModel
from typing import List, Optional

class Placement(BaseModel):
    item_id: str
    x: float
    y: float
    z: float
    length: float
    width: float
    height: float
    rotation: str

class UnplacedItem(BaseModel):
    item_id: str
    quantity: int
    reason: str

class CGPoint(BaseModel):
    x: float
    y: float
    z: float

class Stats(BaseModel):
    total_items_placed: int
    total_items_unplaced: int
    algorithm_time_ms: float

class OptimizeRequest(BaseModel):
    container: ContainerConfig
    items: List[ItemInput]

class OptimizeResponse(BaseModel):
    success: bool
    container_utilization: float
    weight_utilization: float
    total_weight: float
    placements: List[Placement]
    unplaced_items: List[UnplacedItem]
    center_of_gravity: CGPoint
    stats: Stats
```

File: `backend/app/models/solution.py` (import ContainerConfig from container, ItemInput from item)

---

### Task 3: Rotation module

**Files:**
- Create: `backend/app/engine/rotation.py`
- Create: `backend/tests/test_rotation.py`

- [ ] **Step 1: Write the failing test**

```python
import pytest
from app.engine.rotation import get_all_rotations

def test_get_all_rotations_returns_six():
    result = get_all_rotations(100, 80, 50)
    assert len(result) == 6

def test_get_all_rotations_contents():
    result = get_all_rotations(100, 80, 50)
    expected = [
        (100, 80, 50), (100, 50, 80),
        (80, 100, 50), (80, 50, 100),
        (50, 100, 80), (50, 80, 100),
    ]
    for r in expected:
        assert r in result

def test_get_all_rotations_cube():
    result = get_all_rotations(50, 50, 50)
    # All 6 should be the same for a cube, but still return 6
    assert len(result) == 6
    for r in result:
        assert r == (50, 50, 50)
```

File: `backend/tests/test_rotation.py`

- [ ] **Step 2: Implement rotation module**

```python
from typing import List, Tuple

def get_all_rotations(length: float, width: float, height: float) -> List[Tuple[float, float, float]]:
    dims = [(length, width, height),
            (length, height, width),
            (width, length, height),
            (width, height, length),
            (height, length, width),
            (height, width, length)]
    return dims
```

File: `backend/app/engine/rotation.py`

- [ ] **Step 3: Run tests to verify**

Run: `pytest backend/tests/test_rotation.py -v`

---

### Task 4: Extreme Point algorithm

**Files:**
- Create: `backend/app/engine/extreme_point.py`
- Create: `backend/tests/test_extreme_point.py`

- [ ] **Step 1: Write the failing test**

```python
import pytest
from app.engine.extreme_point import (
    ExtremePoint3D, generate_new_eps, is_valid_ep,
    evaluate_placement
)

def test_generate_new_eps():
    eps = generate_new_eps(10, 10, 10, 100, 50, 60)
    assert len(eps) == 3
    # EP along X
    assert (110, 10, 10) in eps
    # EP along Y
    assert (10, 60, 10) in eps
    # EP along Z
    assert (10, 10, 60) in eps

def test_is_valid_ep_within_container():
    ep = (50, 50, 50)
    item_size = (30, 20, 40)  # l, h, w (x, y, z)
    container = (200, 200, 200)
    assert is_valid_ep(ep, item_size, container) == True

def test_is_valid_ep_outside_container():
    ep = (190, 190, 190)
    item_size = (30, 20, 40)
    container = (200, 200, 200)
    assert is_valid_ep(ep, item_size, container) == False

def test_evaluate_placement():
    # Lower placement should score higher
    placements = [
        ((0, 0, 0), (10, 10, 10)),
        ((0, 50, 0), (10, 10, 10)),
    ]
    # With no existing placements, proximity = 1 for first EP
    scores = [evaluate_placement(p[0], p[1], (100, 100, 100), []) for p in placements]
    assert scores[0] >= scores[1]
```

File: `backend/tests/test_extreme_point.py`

- [ ] **Step 2: Implement extreme point module**

```python
from typing import List, Tuple, Optional

ExtremePoint = Tuple[float, float, float]

def generate_new_eps(x: float, y: float, z: float,
                      item_l: float, item_h: float, item_w: float) -> List[ExtremePoint]:
    return [
        (x + item_l, y, z),
        (x, y + item_h, z),
        (x, y, z + item_w),
    ]

def is_valid_ep(ep: ExtremePoint, item_size: Tuple[float, float, float],
                container: Tuple[float, float, float]) -> bool:
    ex, ey, ez = ep
    il, ih, iw = item_size
    cl, ch, cw = container
    return (ex + il <= cl and ey + ih <= ch and ez + iw <= cw)

def evaluate_placement(ep: ExtremePoint, item_size: Tuple[float, float, float],
                       container: Tuple[float, float, float],
                       existing_placements: List[dict]) -> float:
    ex, ey, ez = ep
    il, ih, iw = item_size
    cl, ch, cw = container

    w1, w2, w3, w4 = 0.4, 0.3, 0.2, 0.1

    # Proximity: distance from origin — closer to (0,0,0) is better
    max_dist = (cl**2 + ch**2 + cw**2) ** 0.5
    dist = (ex**2 + ey**2 + ez**2) ** 0.5
    proximity = 1.0 - (dist / max_dist) if max_dist > 0 else 1.0

    # Support area: how much of bottom is supported
    support_area = il * iw
    max_support = container[0] * container[2]
    support_score = support_area / max_support if max_support > 0 else 1.0

    # Gravity score: lower Y is better
    gravity_score = 1.0 - (ey / ch) if ch > 0 else 1.0

    # Waste volume: distance to nearest placed item
    waste_score = 0.0
    if existing_placements:
        min_gap = min(
            ((ex - p["x"])**2 + (ey - p["y"])**2 + (ez - p["z"])**2) ** 0.5
            for p in existing_placements
        )
        waste_score = min_gap / max_dist
    else:
        waste_score = 0.0

    return w1 * proximity + w2 * support_score + w3 * gravity_score - w4 * waste_score
```

File: `backend/app/engine/extreme_point.py`

- [ ] **Step 3: Run tests**

Run: `pytest backend/tests/test_extreme_point.py -v`

---

### Task 5: Space cutting module

**Files:**
- Create: `backend/app/engine/space_cutter.py`
- Create: `backend/tests/test_space_cutter.py`

- [ ] **Step 1: Write the failing test**

```python
import pytest
from app.engine.space_cutter import (
    Space, cut_space, merge_spaces, remove_degenerate_spaces
)

def test_cut_space_along_x():
    # Container space (100, 100, 100), item placed at (0,0,0) size (40, 30, 20)
    original = Space(0, 0, 0, 100, 100, 100)
    item_box = (0, 0, 0, 40, 30, 20)  # x,y,z,l,h,w
    result = cut_space(original, item_box)
    # Should produce 3 spaces: along X, Y, Z
    assert len(result) == 3
    # X space
    assert any(s.x == 40 and s.y == 0 and s.z == 0 and s.l == 60 for s in result)
    # Y space
    assert any(s.x == 0 and s.y == 30 and s.z == 0 and s.h == 70 for s in result)
    # Z space
    assert any(s.x == 0 and s.y == 0 and s.z == 20 and s.w == 80 for s in result)

def test_cut_space_no_intersection():
    original = Space(0, 0, 0, 100, 100, 100)
    item_box = (200, 200, 200, 10, 10, 10)
    result = cut_space(original, item_box)
    assert result == [original]

def test_remove_degenerate_spaces():
    spaces = [
        Space(0, 0, 0, 100, 1, 100),  # degenerate (height=1)
        Space(0, 0, 0, 100, 100, 100),  # valid
    ]
    result = remove_degenerate_spaces(spaces, min_size=5)
    assert len(result) == 1
    assert result[0].h == 100
```

File: `backend/tests/test_space_cutter.py`

- [ ] **Step 2: Implement space cutter**

```python
from typing import List, Optional
from dataclasses import dataclass

@dataclass
class Space:
    x: float
    y: float
    z: float
    l: float  # length (X)
    h: float  # height (Y)
    w: float  # width (Z)

def cut_space(space: Space, item_box: tuple) -> List[Space]:
    ix, iy, iz, il, ih, iw = item_box

    # Check intersection
    if (space.x >= ix + il or space.x + space.l <= ix or
        space.y >= iy + ih or space.y + space.h <= iy or
        space.z >= iz + iw or space.z + space.w <= iz):
        return [space]

    result = []

    # Space along X axis (right of item)
    if space.x + space.l > ix + il:
        result.append(Space(ix + il, space.y, space.z,
                           space.x + space.l - (ix + il), space.h, space.w))

    # Space along Y axis (above item)
    if space.y + space.h > iy + ih:
        result.append(Space(space.x, iy + ih, space.z,
                           space.l, space.y + space.h - (iy + ih), space.w))

    # Space along Z axis (in front of item)
    if space.z + space.w > iz + iw:
        result.append(Space(space.x, space.y, iz + iw,
                           space.l, space.h, space.z + space.w - (iz + iw)))

    return result

def remove_degenerate_spaces(spaces: List[Space], min_size: float = 5.0) -> List[Space]:
    return [s for s in spaces if s.l >= min_size and s.h >= min_size and s.w >= min_size]
```

File: `backend/app/engine/space_cutter.py`

- [ ] **Step 3: Run tests**

Run: `pytest backend/tests/test_space_cutter.py -v`

---

### Task 6: Packer engine

**Files:**
- Create: `backend/app/engine/packer.py`
- Create: `backend/tests/test_packer.py`

- [ ] **Step 1: Write the failing test**

```python
import pytest
from app.engine.packer import EPacker
from app.models.container import ContainerConfig
from app.models.item import ItemInput

def test_packer_single_item():
    packer = EPacker()
    container = ContainerConfig(length=100, width=100, height=100, max_weight=1000)
    items = [ItemInput(id="A", length=50, width=40, height=30, weight=5, quantity=1)]
    result = packer.pack(container, items)
    assert result.success == True
    assert len(result.placements) == 1
    assert result.unplaced_items == []

def test_packer_multiple_items():
    packer = EPacker()
    container = ContainerConfig(length=200, width=200, height=200, max_weight=5000)
    items = [
        ItemInput(id="A", length=100, width=100, height=100, weight=10, quantity=4),
    ]
    result = packer.pack(container, items)
    assert result.success == True
    # Should fit at least some
    assert len(result.placements) > 0

def test_packer_exceeds_weight():
    packer = EPacker()
    container = ContainerConfig(length=1000, width=1000, height=1000, max_weight=10)
    items = [ItemInput(id="A", length=50, width=50, height=50, weight=100, quantity=1)]
    result = packer.pack(container, items)
    assert result.success == True
    # Heavy item should be flagged as unplaced
    assert len(result.unplaced_items) > 0 or result.weight_utilization <= 1.0

def test_packer_utilization_benchmark():
    packer = EPacker()
    container = ContainerConfig(length=5898, width=2352, height=2395, max_weight=28000)
    items = [
        ItemInput(id="A", length=400, width=300, height=200, weight=15, quantity=50),
        ItemInput(id="B", length=500, width=400, height=250, weight=20, quantity=30),
        ItemInput(id="C", length=300, width=200, height=150, weight=10, quantity=40),
    ]
    result = packer.pack(container, items)
    # Should achieve at least 65% utilization (reasonable for mixed sizes)
    assert result.container_utilization >= 0.65
```

File: `backend/tests/test_packer.py`

- [ ] **Step 2: Implement packer engine**

```python
import time
import math
from typing import List, Dict
from app.models.container import ContainerConfig
from app.models.item import ItemInput, ItemInstance
from app.models.solution import (
    OptimizeResponse, Placement, UnplacedItem, CGPoint, Stats
)
from app.engine.rotation import get_all_rotations
from app.engine.extreme_point import (
    generate_new_eps, is_valid_ep, evaluate_placement
)
from app.engine.space_cutter import Space, cut_space, remove_degenerate_spaces

class EPacker:
    def __init__(self):
        self.placements: List[dict] = []
        self.extreme_points: List[tuple] = [(0.0, 0.0, 0.0)]
        self.remaining_spaces: List[Space] = []
        self.placed_weight: float = 0.0
        self.container_volume: float = 0.0
        self.placed_volume: float = 0.0
        self.container: tuple = (0, 0, 0)

    def pack(self, container: ContainerConfig, items: List[ItemInput]) -> OptimizeResponse:
        start_time = time.time()
        self.container = (container.length, container.height, container.width)
        self.container_volume = container.length * container.height * container.width
        self.placed_weight = 0.0
        self.placed_volume = 0.0
        self.placements = []
        self.extreme_points = [(0.0, 0.0, 0.0)]
        self.remaining_spaces = [
            Space(0, 0, 0, container.length, container.height, container.width)
        ]

        max_weight = container.max_weight

        # Expand items by quantity
        instances: List[ItemInstance] = []
        for item in items:
            for _ in range(item.quantity):
                instances.append(ItemInstance(
                    item_id=item.id,
                    length=item.length,
                    width=item.width,
                    height=item.height,
                    weight=item.weight,
                ))

        # Sort by volume descending
        instances.sort(key=lambda x: x.length * x.width * x.height, reverse=True)

        unplaced_map: Dict[str, int] = {}
        for inst in instances:
            if self.placed_weight + inst.weight > max_weight:
                unplaced_map[inst.item_id] = unplaced_map.get(inst.item_id, 0) + 1
                continue

            placed = self._try_place(inst)
            if not placed:
                unplaced_map[inst.item_id] = unplaced_map.get(inst.item_id, 0) + 1

        elapsed = (time.time() - start_time) * 1000

        placements_out = []
        for p in self.placements:
            placements_out.append(Placement(
                item_id=p["item_id"],
                x=p["x"], y=p["y"], z=p["z"],
                length=p["l"], width=p["w"], height=p["h"],
                rotation=p["rotation"],
            ))

        unplaced_out = []
        for uid, qty in unplaced_map.items():
            unplaced_out.append(UnplacedItem(item_id=uid, quantity=qty, reason="空间或重量不足"))

        cg = self._calc_center_of_gravity()

        total_placed = sum(1 for p in self.placements)
        total_unplaced = sum(unplaced_map.values())

        return OptimizeResponse(
            success=True,
            container_utilization=self.placed_volume / self.container_volume if self.container_volume > 0 else 0,
            weight_utilization=self.placed_weight / max_weight if max_weight > 0 else 0,
            total_weight=self.placed_weight,
            placements=placements_out,
            unplaced_items=unplaced_out,
            center_of_gravity=CGPoint(x=cg[0], y=cg[1], z=cg[2]),
            stats=Stats(
                total_items_placed=total_placed,
                total_items_unplaced=total_unplaced,
                algorithm_time_ms=round(elapsed, 2),
            ),
        )

    def _try_place(self, item: ItemInstance) -> bool:
        cl, ch, cw = self.container
        best_score = -float("inf")
        best_placement = None
        best_rot = None

        rotations = get_all_rotations(item.length, item.width, item.height)

        for rot_l, rot_w, rot_h in rotations:
            item_size = (rot_l, rot_h, rot_w)  # (x_size, y_size, z_size)
            for ep in self.extreme_points:
                if not is_valid_ep(ep, item_size, self.container):
                    continue
                existing = [{
                    "x": p["x"], "y": p["y"], "z": p["z"],
                    "l": p["l"], "h": p["h"], "w": p["w"]
                } for p in self.placements]
                score = evaluate_placement(ep, item_size, self.container, existing)
                if score > best_score:
                    ex, ey, ez = ep
                    best_score = score
                    best_placement = (ex, ey, ez, rot_l, rot_h, rot_w)
                    best_rot = f"{rot_l}x{rot_w}x{rot_h}"

        if best_placement is None:
            return False

        x, y, z, l, h, w = best_placement

        # Place item
        self.placements.append({
            "item_id": item.item_id,
            "x": x, "y": y, "z": z,
            "l": l, "h": h, "w": w,
            "weight": item.weight,
            "rotation": best_rot,
        })
        self.placed_weight += item.weight
        self.placed_volume += l * h * w

        # Generate new Extreme Points
        new_eps = generate_new_eps(x, y, z, l, h, w)
        for nep in new_eps:
            if is_valid_ep(nep, (l, h, w), self.container):
                self.extreme_points.append(nep)
        self.extreme_points = list(set(self.extreme_points))

        # Cut remaining spaces
        item_box = (x, y, z, l, h, w)
        new_spaces = []
        for space in self.remaining_spaces:
            new_spaces.extend(cut_space(space, item_box))
        self.remaining_spaces = remove_degenerate_spaces(new_spaces, min_size=10.0)

        return True

    def _calc_center_of_gravity(self) -> tuple:
        if not self.placements:
            return (0.0, 0.0, 0.0)
        total_w = sum(p["weight"] for p in self.placements)
        if total_w == 0:
            return (0.0, 0.0, 0.0)
        cx = sum(p["weight"] * (p["x"] + p["l"] / 2) for p in self.placements) / total_w
        cy = sum(p["weight"] * (p["y"] + p["h"] / 2) for p in self.placements) / total_w
        cz = sum(p["weight"] * (p["z"] + p["w"] / 2) for p in self.placements) / total_w
        return (cx, cy, cz)
```

File: `backend/app/engine/packer.py`

- [ ] **Step 3: Run tests**

Run: `pytest backend/tests/test_packer.py -v`

---

### Task 7: API endpoint + FastAPI main

**Files:**
- Create: `backend/app/api/optimize.py`
- Create: `backend/app/main.py`

- [ ] **Step 1: Write the failing test for API**

```python
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
    assert data["success"] == True
    assert len(data["placements"]) == 1

@pytest.mark.asyncio
async def test_optimize_invalid_input():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/optimize", json={
            "container": {"length": -1, "width": 100, "height": 100, "max_weight": 1000},
            "items": [],
        })
    assert response.status_code == 422
```

File: `backend/tests/test_api.py`

- [ ] **Step 2: Implement API route and main**

```python
from fastapi import APIRouter, HTTPException
from app.models.solution import OptimizeRequest, OptimizeResponse
from app.engine.packer import EPacker

router = APIRouter()
packer = EPacker()

@router.post("/optimize", response_model=OptimizeResponse)
async def optimize(request: OptimizeRequest):
    try:
        result = packer.pack(request.container, request.items)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

File: `backend/app/api/optimize.py`

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.optimize import router as optimize_router

app = FastAPI(title="箱智 API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(optimize_router, prefix="/api")
```

File: `backend/app/main.py`

- [ ] **Step 3: Run tests**

Run: `pytest backend/tests/test_api.py -v`

---

### Task 8: Frontend scaffolding

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/tsconfig.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/vitest.config.ts`
- Create: `frontend/index.html`

- [ ] **Step 1: Create project files**

File: `frontend/package.json`
```json
{
  "name": "x-intelligence-frontend",
  "private": true,
  "version": "1.0.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc && vite build",
    "preview": "vite preview",
    "test": "vitest run",
    "test:watch": "vitest"
  },
  "dependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "three": "^0.165.0",
    "@react-three/fiber": "^8.16.0",
    "@react-three/drei": "^9.105.0",
    "antd": "^5.17.0",
    "framer-motion": "^11.2.0",
    "lucide-react": "^0.378.0"
  },
  "devDependencies": {
    "@types/react": "^18.3.3",
    "@types/react-dom": "^18.3.0",
    "@types/three": "^0.165.0",
    "typescript": "^5.4.0",
    "vite": "^5.2.0",
    "@vitejs/plugin-react": "^4.3.0",
    "vitest": "^1.6.0",
    "@testing-library/react": "^15.0.0",
    "@testing-library/jest-dom": "^6.4.0",
    "jsdom": "^24.0.0"
  }
}
```

File: `frontend/tsconfig.json`
```json
{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": false,
    "noUnusedParameters": false,
    "noFallthroughCasesInSwitch": true
  },
  "include": ["src"]
}
```

File: `frontend/vite.config.ts`
```ts
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://localhost:8000',
    },
  },
})
```

File: `frontend/vitest.config.ts`
```ts
import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: [],
  },
})
```

File: `frontend/index.html`
```html
<!DOCTYPE html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>箱智</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/App.tsx"></script>
  </body>
</html>
```

- [ ] **Step 2: Install frontend dependencies**

Run: `cd frontend && npm install`

---

### Task 9: Frontend types and API service

**Files:**
- Create: `frontend/src/types/index.ts`
- Create: `frontend/src/services/api.ts`

- [ ] **Step 1: Write tests**

```typescript
import { describe, it, expect } from 'vitest';
import type { ContainerConfig, ItemInput, OptimizeResponse } from '../types';

describe('Types', () => {
  it('OptimizeResponse structure', () => {
    const response: OptimizeResponse = {
      success: true,
      container_utilization: 0.85,
      weight_utilization: 0.5,
      total_weight: 100,
      placements: [{ item_id: 'A', x: 0, y: 0, z: 0, length: 50, width: 40, height: 30, rotation: 'lwh' }],
      unplaced_items: [],
      center_of_gravity: { x: 200, y: 100, z: 150 },
      stats: { total_items_placed: 1, total_items_unplaced: 0, algorithm_time_ms: 10 },
    };
    expect(response.success).toBe(true);
    expect(response.placements.length).toBe(1);
  });
});
```

File: `frontend/src/types/__tests__/types.test.ts`

- [ ] **Step 2: Implement types**

```typescript
export interface ContainerConfig {
  length: number;
  width: number;
  height: number;
  max_weight: number;
}

export interface ItemInput {
  id: string;
  length: number;
  width: number;
  height: number;
  weight: number;
  quantity: number;
}

export interface OptimizeRequest {
  container: ContainerConfig;
  items: ItemInput[];
}

export interface Placement {
  item_id: string;
  x: number;
  y: number;
  z: number;
  length: number;
  width: number;
  height: number;
  rotation: string;
}

export interface UnplacedItem {
  item_id: string;
  quantity: number;
  reason: string;
}

export interface CGPoint {
  x: number;
  y: number;
  z: number;
}

export interface Stats {
  total_items_placed: number;
  total_items_unplaced: number;
  algorithm_time_ms: number;
}

export interface OptimizeResponse {
  success: boolean;
  container_utilization: number;
  weight_utilization: number;
  total_weight: number;
  placements: Placement[];
  unplaced_items: UnplacedItem[];
  center_of_gravity: CGPoint;
  stats: Stats;
}
```

File: `frontend/src/types/index.ts`

- [ ] **Step 3: Implement API service**

```typescript
import type { OptimizeRequest, OptimizeResponse } from '../types';

const API_BASE = '/api';

export async function optimize(request: OptimizeRequest): Promise<OptimizeResponse> {
  const response = await fetch(`${API_BASE}/optimize`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  });
  if (!response.ok) {
    throw new Error(`API error: ${response.status}`);
  }
  return response.json();
}
```

File: `frontend/src/services/api.ts`

---

### Task 10: Control panel components

**Files:**
- Create: `frontend/src/components/ContainerConfig.tsx`
- Create: `frontend/src/components/ItemListEditor.tsx`
- Create: `frontend/src/components/ControlPanel.tsx`

- [ ] **Step 1: Implement ContainerConfig**

```tsx
import { Select, InputNumber, Card, Space } from 'antd';

const PRESETS = [
  { value: '20GP', label: '20尺普柜 (5898×2352×2395)', length: 5898, width: 2352, height: 2395, maxWeight: 28000 },
  { value: '40GP', label: '40尺普柜 (12032×2352×2395)', length: 12032, width: 2352, height: 2395, maxWeight: 28000 },
  { value: '40HQ', label: '40尺高柜 (12032×2352×2695)', length: 12032, width: 2352, height: 2695, maxWeight: 28000 },
];

interface ContainerConfigProps {
  value: { length: number; width: number; height: number; max_weight: number };
  onChange: (value: any) => void;
}

export default function ContainerConfig({ value, onChange }: ContainerConfigProps) {
  const handlePreset = (presetId: string) => {
    const preset = PRESETS.find(p => p.value === presetId);
    if (preset) {
      onChange({ length: preset.length, width: preset.width, height: preset.height, max_weight: preset.maxWeight });
    }
  };

  return (
    <Card title="集装箱配置" size="small" style={{ marginBottom: 16 }}>
      <Space direction="vertical" style={{ width: '100%' }}>
        <Select
          placeholder="选择预设箱型"
          onChange={handlePreset}
          allowClear
          options={PRESETS}
          style={{ width: '100%' }}
        />
        <Space>
          <div>
            <div>长 (mm)</div>
            <InputNumber value={value.length} onChange={v => onChange({ ...value, length: v })} min={1} />
          </div>
          <div>
            <div>宽 (mm)</div>
            <InputNumber value={value.width} onChange={v => onChange({ ...value, width: v })} min={1} />
          </div>
          <div>
            <div>高 (mm)</div>
            <InputNumber value={value.height} onChange={v => onChange({ ...value, height: v })} min={1} />
          </div>
          <div>
            <div>最大载重 (kg)</div>
            <InputNumber value={value.max_weight} onChange={v => onChange({ ...value, max_weight: v })} min={1} />
          </div>
        </Space>
      </Space>
    </Card>
  );
}
```

File: `frontend/src/components/ContainerConfig.tsx`

- [ ] **Step 2: Implement ItemListEditor**

```tsx
import { Button, InputNumber, Input, Table, Card, Space } from 'antd';
import { PlusOutlined, DeleteOutlined } from '@ant-design/icons';

interface ItemRow {
  key: string;
  id: string;
  length: number;
  width: number;
  height: number;
  weight: number;
  quantity: number;
}

interface ItemListEditorProps {
  value: ItemRow[];
  onChange: (items: ItemRow[]) => void;
}

export default function ItemListEditor({ value, onChange }: ItemListEditorProps) {
  const addItem = () => {
    const newItem: ItemRow = {
      key: Date.now().toString(),
      id: '',
      length: 100,
      width: 100,
      height: 100,
      weight: 10,
      quantity: 1,
    };
    onChange([...value, newItem]);
  };

  const removeItem = (key: string) => {
    onChange(value.filter(item => item.key !== key));
  };

  const updateItem = (key: string, field: keyof ItemRow, val: any) => {
    onChange(value.map(item => item.key === key ? { ...item, [field]: val } : item));
  };

  const columns = [
    { title: 'ID', dataIndex: 'id', width: 80,
      render: (_: any, record: ItemRow) => (
        <Input size="small" value={record.id} onChange={e => updateItem(record.key, 'id', e.target.value)} />
      )},
    { title: '长', dataIndex: 'length', width: 80,
      render: (_: any, record: ItemRow) => (
        <InputNumber size="small" value={record.length} min={1} onChange={v => updateItem(record.key, 'length', v)} />
      )},
    { title: '宽', dataIndex: 'width', width: 80,
      render: (_: any, record: ItemRow) => (
        <InputNumber size="small" value={record.width} min={1} onChange={v => updateItem(record.key, 'width', v)} />
      )},
    { title: '高', dataIndex: 'height', width: 80,
      render: (_: any, record: ItemRow) => (
        <InputNumber size="small" value={record.height} min={1} onChange={v => updateItem(record.key, 'height', v)} />
      )},
    { title: '重量', dataIndex: 'weight', width: 80,
      render: (_: any, record: ItemRow) => (
        <InputNumber size="small" value={record.weight} min={0.1} step={0.1} onChange={v => updateItem(record.key, 'weight', v)} />
      )},
    { title: '数量', dataIndex: 'quantity', width: 80,
      render: (_: any, record: ItemRow) => (
        <InputNumber size="small" value={record.quantity} min={1} onChange={v => updateItem(record.key, 'quantity', v)} />
      )},
    { title: '', width: 50,
      render: (_: any, record: ItemRow) => (
        <Button size="small" danger icon={<DeleteOutlined />} onClick={() => removeItem(record.key)} />
      )},
  ];

  return (
    <Card title="商品列表" size="small" style={{ marginBottom: 16 }}>
      <Table dataSource={value} columns={columns} pagination={false} size="small" scroll={{ x: 600 }} />
      <Button type="dashed" onClick={addItem} icon={<PlusOutlined />} style={{ width: '100%', marginTop: 8 }}>
        添加商品
      </Button>
    </Card>
  );
}

export type { ItemRow };
```

File: `frontend/src/components/ItemListEditor.tsx`

- [ ] **Step 3: Implement ControlPanel**

```tsx
import { useState } from 'react';
import { Button, Card, Spin, message } from 'antd';
import { PlayCircleOutlined } from '@ant-design/icons';
import ContainerConfig from './ContainerConfig';
import ItemListEditor from './ItemListEditor';
import type { ItemRow } from './ItemListEditor';
import { optimize } from '../services/api';
import type { OptimizeResponse, ContainerConfig as ContainerConfigType, ItemInput } from '../types';

interface ControlPanelProps {
  onResult: (result: OptimizeResponse) => void;
  onLoading: (loading: boolean) => void;
}

export default function ControlPanel({ onResult, onLoading }: ControlPanelProps) {
  const [container, setContainer] = useState<ContainerConfigType>({
    length: 5898, width: 2352, height: 2395, max_weight: 28000,
  });
  const [items, setItems] = useState<ItemRow[]>([]);
  const [loading, setLoading] = useState(false);

  const handleOptimize = async () => {
    if (items.length === 0) {
      message.warning('请至少添加一个商品');
      return;
    }
    setLoading(true);
    onLoading(true);
    try {
      const inputItems: ItemInput[] = items.map(item => ({
        id: item.id || 'UNKNOWN',
        length: item.length,
        width: item.width,
        height: item.height,
        weight: item.weight,
        quantity: item.quantity,
      }));
      const result = await optimize({ container, items: inputItems });
      onResult(result);
    } catch (err) {
      message.error('优化请求失败');
    } finally {
      setLoading(false);
      onLoading(false);
    }
  };

  return (
    <Card title="箱智" style={{ minWidth: 320, height: '100%', overflow: 'auto' }}>
      <ContainerConfig value={container} onChange={setContainer} />
      <ItemListEditor value={items} onChange={setItems} />
      <Button
        type="primary"
        size="large"
        icon={loading ? <Spin /> : <PlayCircleOutlined />}
        onClick={handleOptimize}
        disabled={loading}
        block
      >
        {loading ? '优化中...' : '开始优化'}
      </Button>
    </Card>
  );
}
```

File: `frontend/src/components/ControlPanel.tsx`

---

### Task 11: Layout3D component (Three.js)

**Files:**
- Create: `frontend/src/components/PlacedItem.tsx`
- Create: `frontend/src/components/Layout3D.tsx`

- [ ] **Step 1: Implement PlacedItem**

```tsx
import { useRef, useState } from 'react';
import { BoxGeometry, MeshStandardMaterial } from 'three';
import { Box } from '@react-three/drei';
import type { Placement } from '../types';

interface PlacedItemProps {
  placement: Placement;
  color: string;
  onHover?: (placement: Placement | null) => void;
}

export default function PlacedItem({ placement, color, onHover }: PlacedItemProps) {
  const [hovered, setHovered] = useState(false);

  return (
    <Box
      position={[
        placement.x + placement.length / 2,
        placement.y + placement.height / 2,
        placement.z + placement.width / 2,
      ]}
      args={[placement.length, placement.height, placement.width]}
      onPointerOver={(e) => { e.stopPropagation(); setHovered(true); onHover?.(placement); }}
      onPointerOut={() => { setHovered(false); onHover?.(null); }}
    >
      <meshStandardMaterial
        color={color}
        opacity={0.85}
        transparent
        wireframe={false}
      />
      <meshStandardMaterial
        color="#000000"
        wireframe
        transparent
        opacity={hovered ? 0.4 : 0.1}
      />
    </Box>
  );
}

const COLORS = [
  '#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7',
  '#DDA0DD', '#98D8C8', '#F7DC6F', '#BB8FCE', '#85C1E9',
  '#F0B27A', '#82E0AA', '#F1948A', '#85929E', '#73C6B6',
];

export { COLORS };
```

File: `frontend/src/components/PlacedItem.tsx`

- [ ] **Step 2: Implement Layout3D**

```tsx
import { Suspense, useMemo, useState } from 'react';
import { Canvas } from '@react-three/fiber';
import { OrbitControls, Grid, Text } from '@react-three/drei';
import { BoxGeometry, EdgesGeometry, LineBasicMaterial, LineSegments } from 'three';
import PlacedItem, { COLORS } from './PlacedItem';
import type { Placement, OptimizeResponse, ContainerConfig } from '../types';

interface Layout3DProps {
  result: OptimizeResponse | null;
  container: ContainerConfig;
}

function ContainerFrame({ length, height, width }: { length: number; height: number; width: number }) {
  const geometry = useMemo(() => new BoxGeometry(length, height, width), [length, height, width]);
  const edges = useMemo(() => new EdgesGeometry(geometry), [geometry]);

  return (
    <mesh>
      <primitive object={edges} />
      <lineBasicMaterial color="#888888" />
      <mesh position={[length / 2, height / 2, width / 2]}>
        <boxGeometry args={[length, height, width]} />
        <meshBasicMaterial color="#cccccc" transparent opacity={0.05} side={2} />
      </mesh>
    </mesh>
  );
}

function Scene({ result, container }: Layout3DProps) {
  const [hovered, setHovered] = useState<Placement | null>(null);

  const itemColors = useMemo(() => {
    const colorMap: Record<string, string> = {};
    if (result) {
      const ids = [...new Set(result.placements.map(p => p.item_id))];
      ids.forEach((id, i) => { colorMap[id] = COLORS[i % COLORS.length]; });
    }
    return colorMap;
  }, [result]);

  return (
    <>
      <ambientLight intensity={0.5} />
      <directionalLight position={[1000, 1500, 1000]} intensity={0.8} />
      <ContainerFrame length={container.length} height={container.height} width={container.width} />
      {result?.placements.map((p, i) => (
        <PlacedItem key={i} placement={p} color={itemColors[p.item_id] || '#888'} onHover={setHovered} />
      ))}
      <Grid position={[container.length / 2, 0, container.width / 2]} args={[container.length, container.width]} />
      <OrbitControls makeDefault />
      {hovered && (
        <Text
          position={[hovered.x + hovered.length / 2, hovered.y + hovered.height + 10, hovered.z + hovered.width / 2]}
          fontSize={20}
          color="black"
        >
          {hovered.item_id}
        </Text>
      )}
    </>
  );
}

export default function Layout3D({ result, container }: Layout3DProps) {
  return (
    <div style={{ width: '100%', height: '100%', minHeight: 400, background: '#fafafa' }}>
      <Canvas camera={{ position: [container.length * 1.2, container.height * 1.2, container.width * 1.2], fov: 50 }}>
        <Suspense fallback={null}>
          <Scene result={result} container={container} />
        </Suspense>
      </Canvas>
    </div>
  );
}
```

File: `frontend/src/components/Layout3D.tsx`

---

### Task 12: Result panel components

**Files:**
- Create: `frontend/src/components/UtilizationBar.tsx`
- Create: `frontend/src/components/ResultPanel.tsx`

- [ ] **Step 1: Implement UtilizationBar**

```tsx
import { Progress, Space } from 'antd';

interface UtilizationBarProps {
  spaceUtil: number;
  weightUtil: number;
  totalWeight: number;
}

export default function UtilizationBar({ spaceUtil, weightUtil, totalWeight }: UtilizationBarProps) {
  const spacePct = Math.round(spaceUtil * 100);
  const weightPct = Math.round(weightUtil * 100);

  return (
    <Space direction="vertical" style={{ width: '100%' }}>
      <div>
        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
          <span>空间利用率</span>
          <span>{spacePct}%</span>
        </div>
        <Progress percent={spacePct} strokeColor={spacePct > 75 ? '#52c41a' : spacePct > 50 ? '#faad14' : '#f5222d'} />
      </div>
      <div>
        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
          <span>载重利用率</span>
          <span>{weightPct}% ({totalWeight.toFixed(1)} kg)</span>
        </div>
        <Progress percent={weightPct} strokeColor={weightPct > 75 ? '#52c41a' : weightPct > 50 ? '#faad14' : '#f5222d'} />
      </div>
    </Space>
  );
}
```

File: `frontend/src/components/UtilizationBar.tsx`

- [ ] **Step 2: Implement ResultPanel**

```tsx
import { Card, Table, Tag, Empty, Button } from 'antd';
import { DownloadOutlined } from '@ant-design/icons';
import UtilizationBar from './UtilizationBar';
import type { OptimizeResponse } from '../types';

interface ResultPanelProps {
  result: OptimizeResponse | null;
}

export default function ResultPanel({ result }: ResultPanelProps) {
  if (!result) {
    return (
      <Card title="优化结果" style={{ height: '100%' }}>
        <Empty description="请配置商品并开始优化" />
      </Card>
    );
  }

  const handleExport = () => {
    const blob = new Blob([JSON.stringify(result, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'packing_result.json';
    a.click();
    URL.revokeObjectURL(url);
  };

  const columns = [
    { title: '商品', dataIndex: 'item_id', key: 'item_id', width: 80 },
    { title: '坐标 (X,Y,Z)', key: 'pos',
      render: (_: any, r: any) => `(${Math.round(r.x)}, ${Math.round(r.y)}, ${Math.round(r.z)})`,
      width: 140,
    },
    { title: '尺寸 (L×W×H)', key: 'size',
      render: (_: any, r: any) => `${Math.round(r.length)}×${Math.round(r.width)}×${Math.round(r.height)}`,
      width: 140,
    },
    { title: '旋转', dataIndex: 'rotation', key: 'rotation', width: 100 },
  ];

  const containerVolume = result.container_utilization > 0
    ? (result.placements.reduce((s, p) => s + p.length * p.width * p.height, 0) / result.container_utilization)
    : 0;

  return (
    <Card
      title="优化结果"
      extra={<Button icon={<DownloadOutlined />} onClick={handleExport}>导出</Button>}
      style={{ height: '100%', overflow: 'auto' }}
    >
      <UtilizationBar
        spaceUtil={result.container_utilization}
        weightUtil={result.weight_utilization}
        totalWeight={result.total_weight}
      />

      <div style={{ margin: '16px 0' }}>
        <Tag color="blue">已放置: {result.stats.total_items_placed}</Tag>
        <Tag color={result.unplaced_items.length > 0 ? 'red' : 'green'}>
          未放置: {result.stats.total_items_unplaced}
        </Tag>
        <Tag>耗时: {result.stats.algorithm_time_ms} ms</Tag>
      </div>

      {result.unplaced_items.length > 0 && (
        <div style={{ marginBottom: 12, padding: 8, background: '#fff2f0', borderRadius: 4 }}>
          {result.unplaced_items.map((u, i) => (
            <div key={i}>⚠ {u.item_id} × {u.quantity}: {u.reason}</div>
          ))}
        </div>
      )}

      <Table
        dataSource={result.placements}
        columns={columns}
        rowKey={(_, i) => String(i)}
        pagination={false}
        size="small"
        scroll={{ y: 200 }}
      />
    </Card>
  );
}
```

File: `frontend/src/components/ResultPanel.tsx`

---

### Task 13: App integration

**Files:**
- Create: `frontend/src/App.tsx`
- Create: `frontend/src/App.css`

- [ ] **Step 1: Implement App.tsx**

```tsx
import { useState } from 'react';
import { Layout, ConfigProvider, theme } from 'antd';
import ControlPanel from './components/ControlPanel';
import Layout3D from './components/Layout3D';
import ResultPanel from './components/ResultPanel';
import type { OptimizeResponse, ContainerConfig } from './types';
import './App.css';

const { Sider, Content, Footer } = Layout;

export default function App() {
  const [result, setResult] = useState<OptimizeResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [container, setContainer] = useState<ContainerConfig>({
    length: 5898, width: 2352, height: 2395, max_weight: 28000,
  });

  const handleResult = (res: OptimizeResponse) => {
    setResult(res);
  };

  return (
    <ConfigProvider theme={{ algorithm: theme.defaultAlgorithm }}>
      <Layout style={{ height: '100vh' }}>
        <Sider width={420} style={{ background: '#fff', overflow: 'auto', padding: 16, borderRight: '1px solid #f0f0f0' }}>
          <ControlPanel onResult={handleResult} onLoading={setLoading} />
        </Sider>
        <Layout>
          <Content style={{ position: 'relative' }}>
            {loading && (
              <div style={{ position: 'absolute', top: 16, left: '50%', transform: 'translateX(-50%)', zIndex: 10, padding: '4px 16px', background: '#1890ff', color: '#fff', borderRadius: 4 }}>
                优化计算中...
              </div>
            )}
            <Layout3D result={result} container={container} />
          </Content>
          <Footer style={{ padding: 12, height: 280 }}>
            <ResultPanel result={result} />
          </Footer>
        </Layout>
      </Layout>
    </ConfigProvider>
  );
}
```

File: `frontend/src/App.tsx`

- [ ] **Step 2: Create App.css**

```css
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }
#root { height: 100vh; }
```

File: `frontend/src/App.css`

---

### Task 14: Run tests and verify

- [ ] **Step 1: Run all backend tests**

Run: `cd backend && pip install -r requirements.txt && pytest tests/ -v`

- [ ] **Step 2: Run all frontend tests**

Run: `cd frontend && npm test`

- [ ] **Step 3: Start backend server**

Run: `cd backend && uvicorn app.main:app --reload --port 8000`

- [ ] **Step 4: Start frontend dev server**

Run: `cd frontend && npm run dev`

- [ ] **Step 5: Manual integration test**

Test with browser at http://localhost:5173:
1. Select 20GP container
2. Add item: A, 400x300x200, 15kg, qty 10
3. Click "开始优化"
4. Verify 3D scene shows placements
5. Verify utilization stats display
