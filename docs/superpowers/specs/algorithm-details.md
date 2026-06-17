# 装配大师算法详解

## 算法流水线总览

```
用户输入 (商品 + 集装箱参数)
        │
        ▼
  数据验证 (item_validator.py)
        │
        ▼
  ┌─ Phase 1: 贪心算法 (EPacker)      ← 快速基线解
  │
  ├─ Phase 2: 遗传算法 (GA)            ← 以贪心解为种子进化
  │
  ├─ Phase 2: 局部搜索 (LS)            ← 以GA最优解为种子模拟退火
  │
  └─ Phase 2: 帕累托优化 (NSGA-II)     ← 多目标非支配排序
        │
        ▼
  可行性验证 (FeasibilityVerifier)
        │
        ▼
  多方案结果输出 (Top 5-10)
```

---

## 1. 贪心算法 (EPacker) — Phase 1 基础引擎

**文件：** `backend/app/engine/packer.py` + `backend/app/engine/extreme_point.py`

### 1.1 核心思想

逐物品决策，每次选择一个"最佳"位置放置当前商品。这是**确定性算法**——同一输入永远产生同一输出。

### 1.2 数据结构

| 结构 | 描述 |
|------|------|
| `extreme_points: List[(x,y,z)]` | 候选放置点列表，初始为 `[(0,0,0)]` |
| `placements: List[Dict]` | 已放置商品列表 |
| `remaining_spaces: List[Space]` | 未使用的自由空间 |

**极值点管理：** 每次放置后从物品的三个远角生成新极值点：

```
放置物品 (x, y, z, l, h, w) 后:
  ─ 沿 X 方向: (x + l, y, z)
  ─ 沿 Y 方向: (x, y + h, z)
  ─ 沿 Z 方向: (x, y, z + w)
```

### 1.3 排序策略

```python
instances.sort(key=lambda x: (
    x.batch_number,                    # 主排序：批次号升序（小的先装）
    -(x.length * x.width * x.height),  # 次排序：体积降序
    -x.weight,                          # 第三排序：同体积重量降序
))
```

### 1.4 硬约束检查（放置可行性）

每次尝试放置前，**全部以硬约束拒绝不可行候选**：

| 约束 | 函数 | 逻辑 |
|------|------|------|
| 边界检查 | `is_valid_ep()` | `x+l ≤ container_l && y+h ≤ container_h && z+w ≤ container_w` |
| 重叠检测 | `check_overlap()` | 与所有已放置物品的 AABB 包围盒无重叠 |
| 支撑检查 | `check_support()` | 底部 ≥ 60% 面积被支撑（地面层自动满足） |
| 重心检查 | `check_cg_stability()` | X/Z 轴偏移 ≤ 容器半长 × 35%（早期少量物品放松） |
| 朝向约束 | `get_allowed_orientations()` | 只尝试 `forbidden_horizontal_dims` 允许的朝向 |

**支撑率计算细节：**

```python
def check_support(x, y, z, l, h, w, placements):
    if y <= VERTICAL_TOLERANCE:  # 地面层
        return 1.0, True

    item_footprint = l * w       # 物品底面积
    supported_area = 0.0

    for p in placements:
        if p.top != y:           # 只有正下方的物品才贡献支撑
            continue
        overlap_x = max(0, min(x+l, p.x+p.l) - max(x, p.x))
        overlap_z = max(0, min(z+w, p.z+p.w) - max(z, p.z))
        supported_area += overlap_x * overlap_z

    support_ratio = supported_area / item_footprint
    return support_ratio, support_ratio >= 0.6
```

**重心检查细节：**

```python
def check_cg_stability(x, y, z, l, h, w, weight, placements, container):
    # 预计算放置后的新重心
    new_cx = (Σ(p.weight × p.center_x) + weight × (x + l/2)) / total_weight
    new_cz = (Σ(p.weight × p.center_z) + weight × (z + w/2)) / total_weight

    # 安全边界：X偏移 ≤ 容器长×35%，Z偏移 ≤ 容器宽×35%
    is_stable = (abs(new_cx - cx_center) ≤ cl × 0.35
             and abs(new_cz - cz_center) ≤ cw × 0.35)

    # CG评分：离中心越近越高，有高度惩罚
    cg_score = max(0, 1 - (offset_x/allowed + offset_z/allowed)/2)
    height_penalty = min(1, new_cy / (ch × 0.5))  # 超过半高罚分
    cg_score = cg_score × (1 - height_penalty × 0.3)
```

### 1.5 软评分函数（7维加权）

遍历所有`(极值点 × 允许朝向)`组合，选评分最高者：

```python
score = 0.25 × proximity       # 距离原点(0,0,0)近 → 紧凑
      + 0.30 × support_ratio   # 底部支撑面积大 → 稳定（权重最高）
      + 0.20 × cg_score        # 重心居中且低 → 安全
      + 0.15 × gravity_score   # 物品高度低 → 重心低
      + 0.10 × fragile_safe    # 不压迫下方易碎品 → 安全
      + 0.10 × adj_score       # 贴近已有物品 → 减少碎片
                          ——
      = 1.10 (adj是额外奖励)
```

**易碎品保护逻辑** (`check_fragile_safety`)：

```python
# 新物品放在已有易碎品正上方时，计算覆盖比例
for fragile in placements:
    if fragile.is_fragile and 新物品底部 ≈ 易碎品顶部:
        coverage = 重叠面积 / 易碎品顶面积
        if coverage > 0.1:  # 覆盖超过10% → 计为压迫
            penalty += coverage × 新物品重量
fragile_safe = max(0, 1 - penalty)
```

### 1.6 剩余空间切割

放置后从 `remaining_spaces` 中移除被占用的部分，沿三个方向切出子空间：

```
                    ┌──────┬──────────┐
                    │ 所占  │  X方向   │
                    │ 区域  │  子空间   │
                    ├──────┤          │
                    │ Z方向 │          │
                    │ 子空间 │          │
                    └──────┴──────────┘
```

移除小于 `min_size=10mm` 的碎片空间。

### 1.7 输出指标

每次放置后汇总统计算：

| 指标 | 计算方式 |
|------|---------|
| `container_utilization` | 已用体积 / 容器总体积 |
| `weight_utilization` | 已用重量 / 最大载重 |
| `center_of_gravity` | 各物品形心按重量加权平均 |
| `cg_deviation_ratio` | CG偏离容器中心的归一化比值（0~1） |
| `avg_support_ratio` | 所有已放置商品的平均支撑率 |
| `fragile_violations` | 易碎品上方有物品的次数 |

---

## 2. 共享基类 (OptimizerBase)

**文件：** `backend/app/engine/optimizer_base.py`

GA、LS、NSGA-II 均继承自此基类，共享以下核心方法：

### 2.1 染色体解码 `_decode(chromosome)`

染色体是一个整数列表，每个基因 = 该商品的朝向索引：

```
染色体: [0, 2, 1, 3, ...]
          ↑  ↑  ↑  ↑
       商品1 商品2 商品3 商品4 ...
```

解码过程：遍历染色体 → 根据朝向索引查 `allowed_rotations` → 调用 `EPacker._try_place()` 逐个放置。**如果某个商品放不下了就提前终止**，后续基因被视为未放置。

### 2.2 三个独立目标 `evaluate_objectives()`

```python
目标1: 体积利用率 (utilization)  = 已用体积 / 容器体积    [0, 1]  ↑越大越好
目标2: 稳定性评分 (stability)    = FeasibilityVerifier 计算 [0, 1]  ↑越大越好
目标3: CG平衡 (cg_balance)       = max(0, 1 - cg_deviation × 3) [0, 1]  ↑越大越好
```

### 2.3 加权综合分 `score_placements()`

```python
score = 0.5 × utilization + 0.3 × stability + 0.2 × cg_balance
```

GA 和 LS 使用此加权得分作为适应度/评价指标。NSGA-II **不使用**此加权分，而是保持三个目标独立进行非支配排序。

### 2.4 朝向约束预计算

`_build_rotation_constraints()` 在初始化时预计算每个商品的允许朝向索引列表，避免每次解码重复计算。

### 2.5 贪心种子

`_greedy_chromosome()` 运行一次 EPacker，将贪心结果编码为染色体，作为种群中的一个优质种子。

---

## 3. 遗传算法 (Genetic Algorithm)

**文件：** `backend/app/engine/genetic_algorithm.py`

### 3.1 配置参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `population_size` | 80 | 种群个体数（每代） |
| `generations` | 150 | 最大代数 |
| `crossover_rate` | 0.8 | 交叉概率 |
| `mutation_rate` | 0.15 | 变异概率 |
| `elite_count` | 5 | 每代精英保留数 |
| `tournament_size` | 3 | 锦标赛选择规模 |
| `seed_ratio` | 0.3 | 种子个体比例 |

### 3.2 初始化种群

```python
population[0] = _greedy_chromosome()  # 1个贪心种子
population[1:] = _random_chromosome() # 其余随机生成
```

随机染色体 = 每个基因从该商品的 `allowed_rotations` 列表中随机选一个。

### 3.3 适应度函数

```python
def _evaluate(chromosome) -> FitnessResult:
    placements = _decode(chromosome)          # 解码→放置方案
    if not placements:
        return raw_score = -999               # 空方案→极低分

    utilization, stability, cg_balance = evaluate_objectives(placements)
    raw_score = score_placements(placements)   # 0.5u + 0.3s + 0.2cg
    report = verifier.verify(placements)

    return FitnessResult(utilization, stability, cg_balance, raw_score, report)
```

### 3.4 进化算子

**选择：** 锦标赛选择（tournament_size=3），对 `raw_score` 排序选最优。

**交叉 — 均匀交叉（Uniform Crossover）：**

```python
c1, c2 = p1[:], p2[:]
for i in range(size):
    if random() < 0.5:  # 每个基因位以50%概率交换
        c1[i], c2[i] = c2[i], c1[i]
return c1, c2
```

**三种变异算子（等概率随机选择）：**

| 算子 | 概率 | 操作 |
|------|------|------|
| `swap` | ~33% | 随机交换两个基因位置（改变商品顺序） |
| `rotate` | ~33% | 随机改变一个基因的朝向值（改变摆放姿态） |
| `insert` | ~33% | 随机移动一个基因到另一个位置（改变商品顺序） |

### 3.5 精英保留 + 终止条件

```python
# 每代保留前5个最优个体直接进入下一代
elites = 最优的5个染色体[:]

# 终止条件：连续30代无改进 → 提前终止
if 连续30代best_fitness无提升:
    break
```

### 3.6 完整流程

```
1. 初始化种群（1个贪心种子 + 79个随机）
2. 对每代:
   a. 评估每个个体的适应度
   b. 更新全局最优
   c. 检查终止条件（30代停滞 → 终止）
   d. 进化：选择 → 交叉(80%) → 变异(15%) → 生成新一代
3. 返回最优个体的解码结果
```

---

## 4. 局部搜索 + 模拟退火 (Local Search)

**文件：** `backend/app/engine/local_search.py`

### 4.1 种子策略

```python
# 优先使用GA的最优解作为种子
seed = GA.best_chromosome
# 若GA未运行，使用贪心染色体
seed = seed or _greedy_chromosome()
```

### 4.2 四种邻域算子

| 算子 | 说明 | 适用范围 |
|------|------|---------|
| `swap` | 随机交换两个商品的位置 | ≥2个商品 |
| `rotate` | 随机改变一个商品的朝向 | 该商品有≥2种允许朝向 |
| `insert` | 将一个商品移到另一个位置 | ≥2个商品 |
| `block_move` | 移动连续 2~5 个商品到另一位置 | ≥4个商品 |

`block_move` 是 LS 独有的算子，GA 中没有。

### 4.3 模拟退火机制

```python
delta = neighbor_score - current_score
if delta > 0:                       # 更好的解 → 直接接受
    current = neighbor
elif random() < exp(delta / temp):  # 更差的解 → 概率接受
    current = neighbor

temp *= 0.995  # 指数降温
```

- 初始温度 `T₀ = 1.0`，冷却速率 `α = 0.995`
- 早期温度高 → 容易接受差解（广泛探索）
- 晚期温度接近 0 → 几乎只接受更好解（精细利用）

### 4.4 终止条件

```python
max_iterations = 1000       # 最大迭代上限
no_improve_limit = 50       # 连续50次无改进 → 终止
```

---

## 5. 帕累托多目标优化 (NSGA-II)

**文件：** `backend/app/engine/pareto_optimizer.py`

### 5.1 核心思想

GA 和 LS 将三个目标**加权求和**为单一分数，NSGA-II 则**保持三个目标独立**，通过非支配排序寻找 Pareto 前沿——即一组在不同目标之间最优权衡的解。

### 5.2 非支配排序

```python
def dominates(a, b):
    # A支配B ⇔ A在所有目标上不劣于B，且至少在一个目标上严格优于B
    at_least_one_greater = False
    for i in range(NUM_OBJECTIVES):
        if a[i] < b[i]:
            return False
        if a[i] > b[i]:
            at_least_one_greater = True
    return at_least_one_greater
```

**前沿划分：**

```
Front 0: 不被任何解支配（真正的Pareto前沿）
Front 1: 仅被Front 0支配
Front 2: 仅被Front 0和Front 1支配
...
```

可视化示意（三维目标空间）：

```
                    稳定性↑
                      │  ●   ← Front 0 (Pareto前沿)
                      │ ● ●
                     ╱●  ●
                    │ ●    ●  ← Front 1
                   ╱│
     CG平衡 ●────● ● │
            ●  ●   │╱
           ●  ●   ╱│
          ●  ●  ╱  │
         利用率←────┘
```

### 5.3 拥挤距离

同一前沿内，解离相邻解越远越好（保持多样性）：

```python
for obj_idx in range(NUM_OBJECTIVES):
    solutions.sort(key=lambda s: s.objectives[obj_idx])
    # 边界解设为无穷大（优先保留）
    solutions[0].crowding_distance = inf
    solutions[-1].crowding_distance = inf
    # 内部解的距离 = 相邻两个解在该目标上的归一化距离之和
    for i in range(1, n-1):
        dist = (s[i+1].obj - s[i-1].obj) / (max - min)
        solutions[i].crowding_distance += dist
```

### 5.4 选择策略

锦标赛选择，比较规则：

```python
def better(a, b):
    if a.rank != b.rank:
        return a if a.rank < b.rank else b   # rank越小越好
    return a if a.crowding_distance >= b.crowding_distance else b  # 拥挤距离越大越好
```

### 5.5 父代+子代合并筛选

```python
combined = population + offspring
# 对合并后的种群做非支配排序
fronts = non_dominated_sort(combined)
# 按前沿顺序填充新一代
for front in fronts:
    if len(new_pop) + len(front) <= pop_size:
        new_pop.extend(front)          # 整个前沿进入
    else:
        # 最后一个前沿按拥挤距离降序取剩余名额
        front_sorted = sort(front, by=crowding_distance, desc)
        new_pop.extend(front_sorted[:remaining])
```

### 5.6 输出结果

```python
NSGAResult(
    solutions = 全部60个最终解
    pareto_front = Front 0的解（通常是3-15个不同方案）
)
```

每个 Pareto 解代表一个不同的权衡配置：

| 方案类型 | 利用率 | 稳定性 | CG平衡 | 适用场景 |
|---------|--------|--------|--------|---------|
| 利用率极端解 | **高** | 中 | 低 | 货主想尽可能多装 |
| 稳定性极端解 | 中 | **高** | 中 | 易碎品/长途运输 |
| CG极端解 | 中 | 中 | **高** | 重心敏感的货物 |
| 平衡解 | 较高 | 较高 | 较高 | 通用推荐 |

---

## 6. 三种约束处理方式的对比

### 6.1 硬约束（贪心引擎直接拒绝）

| 约束 | 贪心 | GA | LS | NSGA-II |
|------|------|----|----|---------|
| 边界检查 | 放置前检查 → 跳过 | 解码时由贪心拒绝 | 同GA | 同GA |
| 重叠检测 | 放置前检查 → 跳过 | 解码时由贪心拒绝 | 同GA | 同GA |
| 支撑率≥60% | 放置前检查 → 跳过 | 解码时由贪心拒绝 | 同GA | 同GA |
| 重心偏移≤35% | 放置前检查 → 跳过 | 解码时由贪心拒绝 | 同GA | 同GA |
| 朝向约束 | 只枚举允许朝向 | 预计算allowed_rotations | 同GA | 同GA |
| 重量限制 | 提前跳过超重商品 | 解码时由贪心拒绝 | 同GA | 同GA |

### 6.2 软约束（评分函数权衡）

| 评分维度 | 贪心权重 | GA/LS/NSGA-II |
|---------|---------|--------------|
| 利用率 | 间接（proximity+support） | 直接 0.5 权重 |
| 支撑率 | 0.30（直接加权） | 通过 stability_score 间接（0.3） |
| CG稳定性 | 0.20 | 通过 cg_balance 间接（0.2） |
| 重心高度 | 0.15 | 合并到 stability_score |
| 易碎品安全 | 0.10 | 不直接评分，但可行性检查会罚分 |
| 紧凑度 | 0.25+0.10 | 不直接评分，解码结果已隐含 |

### 6.3 事后验证（FeasibilityVerifier）

所有算法的最终方案都会经过 `FeasibilityVerifier.verify()` 的独立验证：

```
VerificationReport
  ├── geometry_ok:     边界 + 无重叠 + 支撑≥60%
  ├── physics_ok:      总量量 ≤ max_weight + CG偏离<15%
  ├── orientation_ok:  forbidden_horizontal_dims 合规
  ├── stability_score: 0.4×支撑率 + 0.3×(1-重心高/容器高) + 0.3×(1-(层数-1)/最大层数)
  ├── support_score:   平均支撑率
  ├── cg_deviation_ratio: CG偏离度 (0~1)
  ├── fragile_violations: 压迫计数
  ├── orientation_violations: 朝向违规计数
  └── messages:        详细失败原因列表
```

---

## 7. 算法对比总结

| 维度 | 贪心 (Greedy) | 遗传算法 (GA) | 局部搜索 (LS) | 帕累托 (NSGA-II) |
|------|--------------|--------------|--------------|-----------------|
| **策略** | 逐物品最优选择 | 种群进化 | 单点邻域搜索 | 多目标非支配排序 |
| **评分方式** | 7维加权 (0.25+0.30+0.20+0.15+0.10+0.10) | 3维加权 (0.5+0.3+0.2) | 同GA (0.5+0.3+0.2) | **3个独立目标，无加权** |
| **输出方案数** | 1个 | 1个最优 | 1个最优 | 多个Pareto解 |
| **初始解** | 无（自生成） | 1个贪心种子 + 随机 | GA最优解 → 贪心 | 1个贪心种子 + 随机 |
| **探索机制** | 无 | 交叉(80%) + 变异(15%) | 模拟退火 + 4种邻域 | 交叉(85%) + 变异(20%) + 非支配排序 |
| **商品数量上限** | 无限制 | 200个 | 200个 | 200个 |
| **典型耗时** | <1s | 5-15s | 1-5s | 10-30s |
| **空间利用率** | ≥65% | ≥70-75% | ≥72-78% | 多解范围 65%-80% |
| **优点** | 极快，总是可行 | 全局搜索能力强 | 微调能力强 | 提供多样化解 |
| **缺点** | 容易陷入局部最优 | 可能不稳定 | 依赖种子质量 | 计算量最大 |

### API 调用方式

```python
# Phase 1: 仅贪心
POST /api/optimize

# Phase 2: 四种算法并行
POST /api/optimize-phase2?enable_ga=true&enable_ls=true&enable_pareto=true&timeout_seconds=60
# 返回:
#   primary:      贪心结果
#   ga_solution:  遗传算法最优
#   ls_solution:  局部搜索最优
#   pareto_solutions: 帕累托方案列表（0~8个）
```

**推荐使用策略：** 默认使用 Phase 2 全开，前端展示方案切换栏供用户比较选择。急用或商品极少时回退到 Phase 1。
