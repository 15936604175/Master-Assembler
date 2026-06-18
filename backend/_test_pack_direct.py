"""直接测试 pack() 方法。"""
import sys
import time
sys.path.insert(0, ".")

from app.engine.packer import EPacker
from app.models.container import ContainerConfig
from app.models.item import ItemInput

# 测试 50³ × 1000 in 500³
container = ContainerConfig(length=500, width=500, height=500, max_weight=1e9)
items = [ItemInput(id="A", length=50, width=50, height=50, weight=1, quantity=1000,
                  is_fragile=False, batch_number=0, forbidden_horizontal_dims=[])]

packer = EPacker()
t0 = time.time()
result = packer.pack(container, items)
t1 = time.time()
print(f"50³ × 1000 in 500³: {t1-t0:.2f}s, 利用率={result.container_utilization:.2%}, 放置={result.stats.total_items_placed}")

# 测试 30³ × 4000 in 500³
container2 = ContainerConfig(length=500, width=500, height=500, max_weight=1e9)
items2 = [ItemInput(id="A", length=30, width=30, height=30, weight=1, quantity=4000,
                   is_fragile=False, batch_number=0, forbidden_horizontal_dims=[])]

packer2 = EPacker()
t0 = time.time()
result2 = packer2.pack(container2, items2)
t1 = time.time()
print(f"30³ × 4000 in 500³: {t1-t0:.2f}s, 利用率={result2.container_utilization:.2%}, 放置={result2.stats.total_items_placed}")

# 测试货车
container3 = ContainerConfig(length=5898, width=2352, height=2395, max_weight=1e9)
items3 = [
    ItemInput(id="箱A", length=600, width=400, height=300, weight=10, quantity=100,
              is_fragile=False, batch_number=0, forbidden_horizontal_dims=[]),
    ItemInput(id="箱B", length=500, width=400, height=350, weight=10, quantity=50,
              is_fragile=False, batch_number=0, forbidden_horizontal_dims=[]),
    ItemInput(id="箱C", length=400, width=300, height=250, weight=5, quantity=150,
              is_fragile=False, batch_number=0, forbidden_horizontal_dims=[]),
]

packer3 = EPacker()
t0 = time.time()
result3 = packer3.pack(container3, items3)
t1 = time.time()
print(f"货车混合箱: {t1-t0:.2f}s, 利用率={result3.container_utilization:.2%}, 放置={result3.stats.total_items_placed}")

# 测试大规模 50³ × 8000 in 1000³
container4 = ContainerConfig(length=1000, width=1000, height=1000, max_weight=1e9)
items4 = [ItemInput(id="A", length=50, width=50, height=50, weight=1, quantity=8000,
                   is_fragile=False, batch_number=0, forbidden_horizontal_dims=[])]

packer4 = EPacker()
t0 = time.time()
result4 = packer4.pack(container4, items4)
t1 = time.time()
print(f"50³ × 8000 in 1000³: {t1-t0:.2f}s, 利用率={result4.container_utilization:.2%}, 放置={result4.stats.total_items_placed}")
