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
  ├─ Phase 1.5: Block 块状优化          ← 企业级引擎：Block Packing + Beam Search + 物理稳定性 + 批次分层
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

## 2. Block 块状优化 (BlockOptimizer) — Phase 1.5 企业级引擎

**文件：** `backend/app/engine/block_optimizer.py`

**核心架构（模块化设计）：**
```
BlockOptimizer ─┬─ BlockGenerator       (Block生成器)
                 ├─ OrientationManager   (方向约束管理)
                 ├─ FragileConstraint     (易碎约束检测)
                 ├─ BatchManager          (批次分层装载)
                 ├─ EPManager             (Extreme Point管理器)
                 ├─ CollisionDetector     (碰撞检测器)
                 ├─ StabilityEvaluator    (重力与稳定性评估)
                 ├─ ScoringFunction       (综合评分函数)
                 └─ BeamSearchSolver      (束搜索求解器)
```

### 2.1 核心思想：从贪心到企业级 Block Packing

**问题：** 普通贪心逐物品放置产生 `ABABAB` 交错，导致空间碎片严重，无物理稳定性保证，无批次顺序约束。

**解决方案：**
1. **Block Packing** — 同 SKU 组合成规则长方体，减少碎片
2. **物理稳定性评估** — 支撑率 + 重心偏移双重检查
3. **易碎品安全约束** — 禁止上方压载、提升支撑率阈值
4. **批次感知分层装载** — batch0 靠出口，batch1 中间，batch≥2 内层
5. **Beam Search 增强** — 小场景用束搜索探索更多可能性

### 2.2 数据结构

| 结构 | 描述 |
|------|------|
| `Block` (dataclass) | `sku, batch, nx, ny, nz, length, height, width, volume, count, item_*, is_fragile, rotation_label, orientation_name, quality_score` |
| `placed_blocks: List[Dict]` | 已放置 Block 列表（用于同 SKU 聚集 + 批次分层计算） |
| `placements: List[Dict]` | 展开后的单品 placement 列表（与 EPacker 格式一致） |
| `extreme_points: List[(x,y,z)]` | 候选放置点，EPManager 统一管理剪枝与更新 |
| `CollisionDetector._grid` | 空间网格索引，O(1) 平均复杂度重叠检查 |
| `BeamState` | Beam Search 状态 = `placements + placed_blocks + eps + inventory + score` |

### 2.3 Block 生成算法（BlockGenerator）

对每个 SKU，枚举所有合法的 `nx × ny × nz` 组合：

```python
for (rot_l, rot_w, rot_h), rot_label, orient_name in allowed_orientations:
    max_nx = min(6, int(cl / rot_l))
    max_ny = min(4, int(ch / rot_h))
    max_nz = min(6, int(cw / rot_w))
    for nx in range(1, max_nx+1):
        for ny in range(1, max_ny+1):
            for nz in range(1, max_nz+1):
                if nx*ny*nz <= count:               # 不超过库存
                    if block_vol <= container_vol * 0.5:  # ≤ 50% 容器体积
                        生成 Block（继承 SKU 的 fragile + batch 属性）
```

**质量评分（体积 × 紧凑度）：**
```python
quality_score = volume × (0.4 + 0.6 × compactness)
compactness = min(l, h, w) / max(l, h, w)      # 越接近立方体越好
```

**排序策略（双键降序）：**
- **主排序**：单品体积降序 — 大物品优先，避免小 Block 抢占空间
- **次排序**：Block 质量降序 — 大体积且紧凑优先

### 2.4 物理稳定性评估（StabilityEvaluator）

**支撑率检查（硬约束）：**
```python
support_ratio = 底部支撑面积 / Block 底面积
普通 Block: support_ratio >= 50%   (SUPPORT_THRESHOLD)
易碎品 Block: support_ratio >= 70% (FRAGILE_SAFETY_RATIO)
地面层 (y <= 1mm): support_ratio = 100%（自动满足）
```

**重心偏移评估（评分约束）：**
```python
cg_x = Σ(weight_i × center_x_i) / Σ(weight_i)   # 累积加权计算
cg_z = Σ(weight_i × center_z_i) / Σ(weight_i)
offset_x = |cg_x - container_l/2| / (container_l/2)  # 归一化到 [0, 1]
score_penalty = (offset_x + offset_z) × 20         # 评分中的惩罚项
```

### 2.5 易碎品安全约束（FragileConstraint）

```
规则1: 易碎品 Block 的支撑率 ≥ 70%（比普通 50% 更严格）
规则2: 易碎品上方禁止任何物品压载（check_no_stack_violation）
规则3: 非易碎品压在易碎品上方时，在评分中增加 fragile_penalty × 150 惩罚
```

实现机制：放置后遍历所有已放置 fragile Block，检查是否有物品 top > fragile_top 且水平重叠。

### 2.6 批次感知分层装载（BatchManager）

**业务背景：** 不同 batch 对应不同卸货点，货物需按卸货顺序分层排列。

```
策略：
   batch=0 ─ 优先靠近出口（x+block.length ≈ container_length），贴外侧墙
   batch=1 ─ 中间层（x 居中区域）
   batch≥2 ─ 内层区域（x 较小，靠近装货原点）
```

**批次评分函数：**
```python
if batch == 0:
    # 靠出口：距离越近得分越高 + 贴外侧墙奖励 + 贴地板奖励
    dist = cl - (x + block.length)
    score = 0.6 × (1 - dist/cl) + 0.2 × (贴墙? 1 : 0) + 0.2 × (贴底? 1 : 0)
elif batch == 1:
    # 居中：block 中心越接近容器中心越好
    bc = x + block.length/2
    score = 1 - |bc - cl/2| / (cl/2)
else:
    # 内层：x 越小越好
    score = 1 - x / cl
```

### 2.7 综合评分函数（ScoringFunction）—— 9 维度加权

遍历所有 `(Extreme Point × Block)` 组合，选评分最高者：

```python
score = support_ratio × 100          # 支撑率评分（核心安全指标）
      + wall_contact / 3 × 50         # 贴容器壁奖励（鼓励规则堆叠）
      + same_sku_ratio × 80           # 同 SKU 聚集奖励（核心特征）
      + (block_volume / container_vol) × 200   # 大 Block 优先（减少碎片）
      + floor_bonus × 30              # 地面接触奖励（鼓励从底部往上）
      - (|cg_offset_x| + |cg_offset_z|) × 20   # 重心偏移惩罚
      - fragile_penalty × 150         # 易碎品风险惩罚
      + batch_score × 60              # 批次正确性奖励
```

**同 SKU 聚集计算：**
```python
for pb in placed_blocks:
    if pb.sku != block.sku: continue
    # 检查 X/Y/Z 三对面是否相邻（间距 < 1mm）
    # 累加接触面重叠面积
same_sku_ratio = contact_area / block_surface_area   # [0, 1]
```

### 2.8 Beam Search 增强（小场景启用）

**策略：** 中小场景（≤300件）额外执行 Beam Search 探索更优解，大场景（>300件）使用贪心路径保证性能。

```
Beam Search 流程：
   State = (placements, placed_blocks, extreme_points, inventory, score)
   Beam = [initial_state]   # beam_width = 5
   
   for step in range(max_steps=100):
       new_beam = []
       for state in Beam:
           for block in available_blocks:
               # 每个 Block 选最佳 EP（支撑/碰撞/易碎过滤后评分最高）
               (best_ep, best_score) = find_best_placement(state, block)
               if found:
                   new_state = apply_placement(state, block, best_ep)
                   new_beam.append((new_state_score, new_state))
       
       # 保留 top-K 状态
       Beam = [s for _, s in sorted(new_beam, reverse=True)[:beam_width]]
       best = max(Best, Beam[0], key=placed_volume)
   
   return greedy_solution if beam_util <= greedy_util + 1% else beam_solution
```

### 2.9 主流程

```
输入: container, items
Step1: BlockGenerator 生成 Block 库（每个 SKU → nx×ny×nz 枚举）
Step2: 按 (单品体积降序, Block质量降序) 排序
Step3: 贪心路径（默认，所有场景）：
       初始化 EP = [(0,0,0)] + 地面网格点
       while progress:
           for block in sorted_blocks:
               if 库存 >= block.count and 重量允许:
                   best_ep, best_score = find_best_ep(block)
                   if best_ep:
                       放置 Block → 展开为单品 placement
                       更新 EP（剪枝 + 新角点）
                       库存 -= block.count
Step4: Beam Search 路径（仅 ≤300 件场景）：
       如果 Beam Search 利用率 > 贪心 + 1%：采用 Beam 解
Step5: 输出 placement 列表（与 EPacker 格式一致）
```

### 2.10 与贪心算法的对比

| 维度 | 贪心 (EPacker) | Block 优化 (BlockOptimizer) |
|------|---------------|---------------------------|
| **装箱对象** | 单个 Box | Block（同 SKU 长方体） |
| **放置决策** | 逐物品选最佳 EP | 贪心 + Beam Search 双路径 |
| **稳定性** | 无显式支撑率检查 | 支撑率 ≥50% + 重心偏移评分 |
| **易碎品处理** | 无特殊约束 | 易碎品支撑率 ≥70%，禁止上方压载 |
| **批次处理** | 按 batch_number 排序放置 | 批次分层 + 位置偏好评分 |
| **同 SKU 聚集** | 隐式依赖排序 | 接触面积比显式奖励 |
| **空间碎片** | 较多 | 较少 |
| **典型耗时（900件）** | ~350ms | ~5ms |
| **典型耗时（1600件）** | ~15s | ~56ms |
| **利用率（多SKU 900件）** | 97.80% | **99.60% (+1.80%)** |
| **利用率（混合尺寸750件）** | 99.20% | **99.80% (+0.60%)** |

### 2.11 输出指标

Block 优化输出与贪心算法完全一致的 placement 格式，复用 `_build_response_from_dicts` 构建 `OptimizeResponse`，包含：
- `container_utilization`：已用体积 / 容器总体积
- `placements`：展开后的单品列表（每个 Block 展开为 `nx×ny×nz` 个 placement）
- `weight_utilization`：已用载重 / 最大载重
- `center_of_gravity`：(x, y, z) 重心坐标
- `feasibility_report`：FeasibilityVerifier 独立验证（重叠/边界/支撑率）

---

## 3. 共享基类 (OptimizerBase)

**文件：** `backend/app/engine/optimizer_base.py`

GA、LS、NSGA-II 均继承自此基类，共享以下核心方法：

### 3.1 染色体解码 `_decode(chromosome)`

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

### 3.4 朝向约束预计算

`_build_rotation_constraints()` 在初始化时预计算每个商品的允许朝向索引列表，避免每次解码重复计算。

### 3.5 贪心种子

`_greedy_chromosome()` 运行一次 EPacker，将贪心结果编码为染色体，作为种群中的一个优质种子。

---

## 4. 遗传算法 (Genetic Algorithm)

**文件：** `backend/app/engine/genetic_algorithm.py`

### 4.1 配置参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `population_size` | 80 | 种群个体数（每代） |
| `generations` | 150 | 最大代数 |
| `crossover_rate` | 0.8 | 交叉概率 |
| `mutation_rate` | 0.15 | 变异概率 |
| `elite_count` | 5 | 每代精英保留数 |
| `tournament_size` | 3 | 锦标赛选择规模 |
| `seed_ratio` | 0.3 | 种子个体比例 |

### 4.2 初始化种群

```python
population[0] = _greedy_chromosome()  # 1个贪心种子
population[1:] = _random_chromosome() # 其余随机生成
```

随机染色体 = 每个基因从该商品的 `allowed_rotations` 列表中随机选一个。

### 4.3 适应度函数

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

### 4.4 进化算子

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

### 4.5 精英保留 + 终止条件

```python
# 每代保留前5个最优个体直接进入下一代
elites = 最优的5个染色体[:]

# 终止条件：连续30代无改进 → 提前终止
if 连续30代best_fitness无提升:
    break
```

### 4.6 完整流程

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

## 5. 局部搜索 + 模拟退火 (Local Search)

**文件：** `backend/app/engine/local_search.py`

### 5.1 种子策略

```python
# 优先使用GA的最优解作为种子
seed = GA.best_chromosome
# 若GA未运行，使用贪心染色体
seed = seed or _greedy_chromosome()
```

### 5.2 四种邻域算子

| 算子 | 说明 | 适用范围 |
|------|------|---------|
| `swap` | 随机交换两个商品的位置 | ≥2个商品 |
| `rotate` | 随机改变一个商品的朝向 | 该商品有≥2种允许朝向 |
| `insert` | 将一个商品移到另一个位置 | ≥2个商品 |
| `block_move` | 移动连续 2~5 个商品到另一位置 | ≥4个商品 |

`block_move` 是 LS 独有的算子，GA 中没有。

### 5.3 模拟退火机制

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

### 5.4 终止条件

```python
max_iterations = 1000       # 最大迭代上限
no_improve_limit = 50       # 连续50次无改进 → 终止
```

---

## 6. 帕累托多目标优化 (NSGA-II)

**文件：** `backend/app/engine/pareto_optimizer.py`

### 6.1 核心思想

GA 和 LS 将三个目标**加权求和**为单一分数，NSGA-II 则**保持三个目标独立**，通过非支配排序寻找 Pareto 前沿——即一组在不同目标之间最优权衡的解。

### 6.2 非支配排序

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

### 6.3 拥挤距离

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

### 6.4 选择策略

锦标赛选择，比较规则：

```python
def better(a, b):
    if a.rank != b.rank:
        return a if a.rank < b.rank else b   # rank越小越好
    return a if a.crowding_distance >= b.crowding_distance else b  # 拥挤距离越大越好
```

### 6.5 父代+子代合并筛选

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

### 6.6 输出结果

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

## 7. 三种约束处理方式的对比

### 7.1 硬约束（贪心引擎直接拒绝）

| 约束 | 贪心 | GA | LS | NSGA-II |
|------|------|----|----|---------|
| 边界检查 | 放置前检查 → 跳过 | 解码时由贪心拒绝 | 同GA | 同GA |
| 重叠检测 | 放置前检查 → 跳过 | 解码时由贪心拒绝 | 同GA | 同GA |
| 支撑率≥60% | 放置前检查 → 跳过 | 解码时由贪心拒绝 | 同GA | 同GA |
| 重心偏移≤35% | 放置前检查 → 跳过 | 解码时由贪心拒绝 | 同GA | 同GA |
| 朝向约束 | 只枚举允许朝向 | 预计算allowed_rotations | 同GA | 同GA |
| 重量限制 | 提前跳过超重商品 | 解码时由贪心拒绝 | 同GA | 同GA |

### 7.2 软约束（评分函数权衡）

| 评分维度 | 贪心权重 | GA/LS/NSGA-II |
|---------|---------|--------------|
| 利用率 | 间接（proximity+support） | 直接 0.5 权重 |
| 支撑率 | 0.30（直接加权） | 通过 stability_score 间接（0.3） |
| CG稳定性 | 0.20 | 通过 cg_balance 间接（0.2） |
| 重心高度 | 0.15 | 合并到 stability_score |
| 易碎品安全 | 0.10 | 不直接评分，但可行性检查会罚分 |
| 紧凑度 | 0.25+0.10 | 不直接评分，解码结果已隐含 |

### 7.3 事后验证（FeasibilityVerifier）

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

## 8. 算法对比总结

| 维度 | 贪心 (Greedy) | Block 优化 | 遗传算法 (GA) | 局部搜索 (LS) | 帕累托 (NSGA-II) |
|------|--------------|-----------|--------------|--------------|-----------------|
| **核心策略** | 逐物品最优选择 | Block Packing + Beam Search + 稳定性评估 | 种群进化 | 单点邻域搜索 | 多目标非支配排序 |
| **装箱对象** | 单个 Box | Block（同SKU长方体） | 单个 Box | 单个 Box | 单个 Box |
| **物理稳定性** | 无显式支撑率检查 | 支撑率≥50% + 重心偏移评分 | 依赖贪心解码 | 依赖贪心解码 | 依赖贪心解码 |
| **易碎品约束** | 无特殊处理 | 易碎品支撑率≥70% + 禁止上方压载 | 无特殊处理 | 无特殊处理 | 无特殊处理 |
| **批次处理** | 按batch排序 | 批次分层 + 位置偏好评分 | 按batch排序 | 按batch排序 | 按batch排序 |
| **评分方式** | BLF + 墙接触 | **9维加权**（支撑+贴壁+聚集+体积+重心+易碎+批次） | 3维加权 (0.5+0.3+0.2) | 同GA | **3个独立目标，无加权** |
| **探索机制** | 无（确定性） | Block库自然回退 + 小场景Beam Search | 交叉(80%) + 变异(15%) | 模拟退火 + 4种邻域 | 交叉(85%) + 变异(20%) + 非支配排序 |
| **输出方案数** | 1个 | 1个 | 1个最优 | 1个最优 | 多个Pareto解 |
| **商品数量上限** | 无限制 | 无限制 | 200个 | 200个 | 200个 |
| **多SKU 900件耗时** | ~350ms | ~5ms | 10-20s | 2-5s | 15-30s |
| **大批量1600件耗时** | ~15s | ~56ms | 30-60s | 10-20s | 50-120s |
| **多SKU利用率** | 97.80% | **99.60% (+1.80%)** | 约98-99% | 约98.5-99.5% | 97-99.5% |
| **优点** | 极快，总是可行 | 同SKU聚集，速度优势大，稳定性保证 | 全局搜索能力强 | 微调能力强 | 提供多样化解 |
| **缺点** | 空间碎片多，无稳定性保证 | 超小场景Block生成有开销 | 可能不稳定 | 依赖种子质量 | 计算量最大 |

### API 调用方式

```python
# Phase 1: 仅贪心
POST /api/optimize

# Phase 1.5: 仅 Block 优化（企业级，推荐）
POST /api/optimize-block

# Phase 2: 五种算法并行
POST /api/optimize-phase2?enable_ga=true&enable_ls=true&enable_pareto=true&enable_block=true&timeout_seconds=60
# 返回:
#   primary:          贪心结果
#   block_solution:   Block 优化结果（企业级）
#   ga_solution:      遗传算法最优
#   ls_solution:      局部搜索最优
#   pareto_solutions: 帕累托方案列表（0~8个）
```

**推荐使用策略：** 多SKU/大批量场景优先使用 Block 优化；需要多方案对比时启用 Phase 2 全开。
