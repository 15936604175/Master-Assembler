# 箱智 (X-Intelligence) 设计文档

## 概述

箱智是一款集装箱装载优化软件，使用 Extreme Point 算法结合 3 种朝向枚举、批次优先排序、重心平衡约束和剩余空间切割策略，为给定商品集合计算最优的集装箱装载方案。

## 技术栈

| 层级 | 技术 |
|------|------|
| 后端 | Python 3.11+ / FastAPI |
| 数据验证 | Pydantic V2 (field_validator) |
| 算法引擎 | NumPy (向量化几何计算) / scipy.spatial (空间查询) |
| 遗传算法 | DEAP (分布式进化算法框架) |
| 前端 | React 18 + TypeScript |
| 3D 渲染 | Three.js + @react-three/fiber |
| 动画 | framer-motion |
| UI | Ant Design |
| 测试 | pytest (后端) / vitest (前端) |

## 项目结构

```
F:\Master-Assembler\
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                       # FastAPI 应用入口
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   └── optimize.py               # POST /api/optimize 路由
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── container.py              # 集装箱数据模型
│   │   │   ├── item.py                   # 商品数据模型
│   │   │   └── solution.py               # 优化结果模型
│   │   ├── engine/
│   │   │   ├── __init__.py
│   │   │   ├── packer.py                 # 主装配引擎 (编排流程)
│   │   │   ├── extreme_point.py          # Extreme Point 算法实现 (Phase 1)
│   │   │   ├── rotation.py               # 3 种朝向枚举
│   │   │   ├── space_cutter.py           # 剩余空间切割
│   │   │   ├── genetic_algorithm.py      # 遗传算法模块 (Phase 2)
│   │   │   ├── local_search.py           # 局部搜索模块 (Phase 2)
│   │   │   ├── pareto_optimizer.py       # 帕累托优化器 NSGA-II (Phase 2)
│   │   │   └── feasibility.py            # 可行性验证模块
│   │   ├── validators/
│   │   │   ├── __init__.py
│   │   │   └── item_validator.py         # Pydantic V2 数据验证
│   │   └── containers.json               # 预设标准集装箱数据
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── test_rotation.py
│   │   ├── test_extreme_point.py
│   │   ├── test_space_cutter.py
│   │   ├── test_packer.py
│   │   ├── test_genetic_algorithm.py
│   │   ├── test_local_search.py
│   │   ├── test_pareto_optimizer.py
│   │   └── test_feasibility.py
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.tsx
│   │   ├── components/
│   │   │   ├── ControlPanel/
│   │   │   │   ├── ControlPanel.tsx
│   │   │   │   ├── ContainerConfig.tsx
│   │   │   │   └── ItemListEditor.tsx
│   │   │   ├── Layout3D/
│   │   │   │   ├── Layout3D.tsx           # Three.js 场景
│   │   │   │   ├── ContainerMesh.tsx
│   │   │   │   ├── PlacedItem.tsx
│   │   │   │   └── SceneControls.tsx
│   │   │   ├── ResultPanel/
│   │   │   │   ├── ResultPanel.tsx
│   │   │   │   └── UtilizationBar.tsx
│   │   │   └── Package3DModal/
│   │   │       ├── Package3DModal.tsx      # (参考 README 风格)
│   │   │       └── PackageViewer3D.tsx
│   │   ├── services/
│   │   │   └── api.ts                     # API 客户端
│   │   └── types/
│   │       └── index.ts                   # TypeScript 类型定义
│   ├── package.json
│   └── vite.config.ts
└── docs/
    └── superpowers/
        └── specs/
            └── 2026-06-16-master-assembler-design.md
```

## 数据流

```
用户输入 (商品 + 集装箱参数)
        │
        ▼
React ControlPanel ──POST /api/optimize──▶ FastAPI
                                              │
                                              ▼
                                     ┌─ 数据验证 (2.2.1)
                                     │   ├─ 参数合法性检查
                                     │   ├─ 容器限制预检
                                     │   └─ 不可行方案过滤
                                     ▼
                               ┌─ Phase 1: 基础引擎
                               │    ├─ 批次优先 + 体积降序排序
                               │    ├─ 3种朝向枚举 + 朝向约束过滤
                               │    ├─ Extreme Point 插入
                               │    └─ 剩余空间切割 + 实时重心跟踪
                               │         │
                               │         ▼
                               │  初始可行解 (种子)
                               │
                               ├─ Phase 2: 智能优化 ──┐
                               │    ├─ 遗传算法(GA)    │
                               │    ├─ 局部搜索(LS)    │
                               │    └─ 帕累托优化(NSGA-II) │
                               │         │              │
                               │         ▼              │
                               │  Pareto 最优解集 ◄──────┘
                               │
                               └─ 可行性验证 (2.2.6)
                                    ├─ 几何验证
                                    ├─ 物理验证
                                    └─ 稳定性评分
                                      │
                                      ▼
                                 多方案结果 (Top 5-10)
                                      │
                                      ▼
React Layout3D ◀── result ── Three.js 渲染
React ResultPanel ◀── stats ── 利用率/清单展示
```

## API 规格

### POST /api/optimize

**请求体：**

```json
{
  "container": {
    "length": 1200,
    "width": 800,
    "height": 900,
    "max_weight": 28000
  },
  "items": [
    {
      "id": "A",
      "length": 100,
      "width": 80,
      "height": 50,
      "weight": 5,
      "quantity": 20,
      "batch_number": 1,
      "forbidden_horizontal_dim": null
    },
    {
      "id": "B",
      "length": 60,
      "width": 60,
      "height": 40,
      "weight": 3,
      "quantity": 15,
      "batch_number": 2,
      "forbidden_horizontal_dim": "height"
    }
  ]
}
```

**响应体：**

```json
{
  "success": true,
  "container_utilization": 0.87,
  "weight_utilization": 0.52,
  "total_weight": 145,
  "cg_deviation_ratio": 0.08,
  "placements": [
    {
      "item_id": "A",
      "x": 0, "y": 0, "z": 0,
      "length": 100, "width": 80, "height": 50,
      "rotation": "lwh",
      "orientation": "height_vertical"
    }
  ],
  "unplaced_items": [
    { "item_id": "B", "quantity": 2, "reason": "空间不足" }
  ],
  "center_of_gravity": { "x": 450, "y": 300, "z": 200 },
  "stats": {
    "total_items_placed": 33,
    "total_items_unplaced": 2,
    "algorithm_time_ms": 45
  }
}
```

## 模块设计

### 2.2.1 数据验证模块

**职责：**
- 输入参数合法性检查（尺寸>0、重量>0、数量>0）
- 商品总体积/总重量是否超过容器限制（预检）
- 单个商品尺寸是否超过容器（提前过滤不可行方案）

**技术实现：**
- 使用 Pydantic V2 的 `field_validator` 进行声明式验证
- 自定义验证器处理业务规则

```python
from pydantic import BaseModel, Field, field_validator
from typing import Optional

class ItemInput(BaseModel):
    id: str = Field(min_length=1)
    length: float = Field(gt=0)
    width: float = Field(gt=0)
    height: float = Field(gt=0)
    weight: float = Field(gt=0)
    quantity: int = Field(gt=0, le=10000)
    batch_number: int = Field(default=0, ge=0, description="批次号，小的先装")
    forbidden_horizontal_dim: Optional[str] = Field(default=None, description="禁止水平的维度：'length'/'width'/'height'/null")

    @field_validator('forbidden_horizontal_dim')
    @classmethod
    def validate_forbidden_dim(cls, v):
        if v is not None and v not in ('length', 'width', 'height'):
            raise ValueError("forbidden_horizontal_dim 必须是 'length', 'width', 'height' 或 null")
        return v

    @field_validator('length', 'width', 'height')
    @classmethod
    def check_single_dimension(cls, v, info):
        """单个商品尺寸验证由引擎层根据容器判断"""
        return v

class OptimizeRequest(BaseModel):
    container: ContainerConfig
    items: List[ItemInput]

    @field_validator('items')
    @classmethod
    def check_total_volume(cls, v, info):
        container = info.data.get('container')
        if container:
            total_vol = sum(i.length * i.width * i.height * i.quantity for i in v)
            container_vol = container.length * container.width * container.height
            if total_vol > container_vol:
                raise ValueError(f'商品总体积 ({total_vol}) 超过容器容量 ({container_vol})')
        return v
```

### 2.2.2 Extreme Point 算法引擎（Phase 1 基础）

坐标系统：容器原点 (0,0,0) 位于左下后角，X=长度方向，Y=高度方向，Z=宽度方向。

**极值点管理：**
- **初始化**：容器原点 (0,0,0) 作为第一个极值点
- **更新策略**：每次放置物品后，从物品的三个远角生成新极值点
  - 沿 X 方向：(x + l, y, z)
  - 沿 Y 方向：(x, y + h, z)
  - 沿 Z 方向：(x, y, z + w)
- **去重**：合并坐标相近的极值点（容差处理，如 < 1mm 视为相同）
- **排序**：按 Z 优先、Y 次之、X 最后的启发式规则排序（优先填充底部深处）

**3 种朝向枚举（原 6 方向旋转）：**
| 编号 | 朝向 (沿X, 沿Y, 沿Z) | 说明 |
|------|----------------------|------|
| 1 | (L, H, W) | 原始高度 H 为垂直方向，底面 L×W |
| 2 | (L, W, H) | 原始宽度 W 为垂直方向，底面 L×H |
| 3 | (W, L, H) | 原始长度 L 为垂直方向，底面 W×H |

- 当有维度相等时自动去重（如立方体仅 1 种有效朝向）
- 根据商品属性（如易碎品标记、朝向约束）过滤不允许的朝向

**朝向约束（forbidden_horizontal_dim）：**
每个商品可通过 `forbidden_horizontal_dim` 指定某个维度禁止水平放置：

| forbidden_horizontal_dim | 允许的朝向 | 含义 |
|--------------------------|-----------|------|
| `null` | 1, 2, 3 | 无限制 |
| `"height"` | 1 | 高度必须垂直 → 仅朝向1 |
| `"width"` | 2 | 宽度必须垂直 → 仅朝向2 |
| `"length"` | 3 | 长度必须垂直 → 仅朝向3 |

实现方式：`get_allowed_orientations(length, width, height, forbidden_horizontal_dim)`
返回过滤后的朝向列表（1-3 个），引擎在放置时只尝试允许的朝向。

**排序策略（批次优先 + 体积降序）：**
- 预处理：按 `(batch_number ASC, 体积 DESC)` 排序
  - 批次号小的先装（批次号 0 视为无批次约束，排在最后）
  - 同批次内按体积从大到小排序
  - 同体积按重量降序（重的先放，利于稳定性）
- 易碎品特殊处理标记（降低放置优先级或限制不可被压迫）

**放置可行性检查：**
- **边界检查**：物品不超出容器范围 `x + l <= container_l`
- **碰撞检测**：使用 AABB 包围盒快速检测与已放置物品无重叠
- **支撑检查**：底部必须有 ≥60% 面积被支撑（z=0 层除外）
- **重量累计检查**：实时跟踪已放置总重量，不超过 `max_weight`
- **重心约束检查**：放置前预计算新重心，若任一轴偏移超过容器尺寸的 15% 则跳过该候选

**重心约束实现细节：**
```
容器中心 = (Cx, Cy, Cz) = (container_l/2, container_h/2, container_w/2)
重心偏移上限 = 容器尺寸 × 0.15（每个轴独立检查）
条件：|CG_x - Cx| ≤ container_l × 0.15
     |CG_y - Cy| ≤ container_h × 0.15
     |CG_z - Cz| ≤ container_w × 0.15
```
引擎实时维护当前重心坐标，每次尝试放置时预计算新重心并做越界判断。

**剩余空间切割策略：**
- 放置物品后，将剩余空间划分为多个子空间
- 采用"最大矩形"思想维护可用空间列表
- 被分割的空间拆分为最多 3 个子空间（沿 X/Y/Z 方向）
- 移除小于最小商品尺寸的空间
- 合并相邻的小空间减少碎片

**评分函数（Phase 1）：**
```
score = 0.35 * proximity       +    // 距离已有物品近 → 紧凑
        0.25 * support_area    +    // 底部支撑面积大 → 稳定
        0.20 * gravity_score   +    // 重心低且居中 → 安全
       -0.10 * waste_volume    +    // 产生的碎片空间 → 避免
        0.10 * cg_balance           // 重心偏离度评分（越接近中心越高）
```

**技术实现：**
- NumPy 数组进行向量化几何计算
- `scipy.spatial` 用于空间查询优化（可选）
- 使用集合（set）存储极值点，自动去重

### 2.2.3 遗传算法模块（Phase 2 增强）

**编码方案设计：**
- 染色体表示：商品排列顺序 + 每个商品的旋转状态
- 示例：`[item_id_1, rot_1, item_id_2, rot_2, ...]`
- 基因由 (商品索引, 旋转索引) 组成

**适应度函数设计：**
- 多目标适应度：利用率、稳定性、重心偏离度
- 惩罚机制：对不可行方案施加严厉惩罚（负适应度）
- 归一化各目标到 [0,1] 区间后加权求和

**选择算子：**
- **锦标赛选择（Tournament Selection）**：随机选取 k 个个体，选最优的进入下一代
- **精英保留策略（Elitism）**：每代保留前 N 个最优个体直接复制到下一代

**交叉算子：**
- **Order Crossover (OX)**：保持商品排列顺序的部分信息，适用于排列编码
- **部分映射交叉（PMX）**：通过映射关系修复重复基因，适用于排列编码

**变异算子：**
- **交换变异**：随机交换两个商品位置
- **旋转变异**：随机改变某个商品的旋转状态（旋转索引突变）
- **插入变异**：随机移动商品到另一个位置

**种群管理：**
- **初始种群生成**：随机生成 + 启发式种子（Extreme Point 结果作为优质种子）
- **种群大小**：50-200（可配置）
- **迭代次数**：100-500 代（可配置）

**技术实现：**
- 使用 DEAP 库提供的基础设施（`creator`, `Toolbox`, `algorithms`）
- 自定义工具箱（Toolbox）注册算子（`mate`, `mutate`, `select`, `evaluate`）
- 并行评估适应度（`multiprocessing.Pool`）

### 2.2.4 局部搜索模块（Phase 2 增强）

**邻域定义：**
- **交换邻域**：交换两个商品的位置
- **插入邻域**：将一个商品移到另一个位置
- **旋转邻域**：改变单个商品的旋转状态
- **块移动邻域**：移动连续的几个商品

**搜索策略：**
- **最佳改进（Best Improvement）**：遍历所有邻域选最优（质量高但计算量大）
- **首次改进（First Improvement）**：找到第一个改进即接受（效率高）
- **模拟退火（Simulated Annealing）**：以一定概率接受劣解，避免局部最优

```
P(accept) = exp(-ΔE / T)     // ΔE: 适应度变化, T: 当前温度
T = T0 * α^k                  // 指数降温
```

**终止条件：**
- 最大迭代次数（可配置，如 1000 次）
- 连续 N 代无改进（如 50 代无改进即停止）
- 达到目标阈值（如利用率 > 95%）

**技术实现：**
- 基于 Extreme Point 解码器评估邻域解
- 缓存机制避免重复计算（邻域解哈希表）

### 2.2.5 帕累托优化器（Phase 2 核心）

**多目标定义：**

| 目标 | 方向 | 计算公式 |
|------|------|----------|
| 目标1：体积利用率最大化 | 最大化 | `已用体积 / 容器总体积` |
| 目标2：稳定性评分最大化 | 最大化 | 加权综合评分（0-100） |
| 目标3：重心偏离度最小化 | 最小化 | 实际重心与容器几何中心的欧氏距离，归一化为 0-100 分 |

**稳定性评分（目标2）考虑因素：**
- 支撑率：每个物品底部被支撑的面积比例
- 重心高度：重心越低得分越高
- 物品堆叠层数：层数越少越稳定

**NSGA-II 算法集成：**
- **非支配排序**：将种群分为多个 Pareto 前沿（Front 0 为最优）
- **拥挤距离计算**：保持解的多样性，优先保留拥挤距离大的个体
- **精英策略**：子代与父代合并后筛选，保留每代的最优解

```
非支配关系定义：
  方案 A 支配方案 B ⇔
    A 在所有目标上不劣于 B，且至少在一个目标上优于 B

拥挤距离：
  d_i = Σ |f_m(i+1) - f_m(i-1)|    // 同一前沿内相邻个体的目标差值之和
```

**方案筛选与呈现：**
- 从最终 Pareto 前沿提取代表性方案
- **极端解**：利用率最高、稳定性最高、重心最优
- **平衡解**：各目标折中的方案（取拥挤距离最大的中间解）
- 最多返回 5-10 个方案供用户选择

**技术实现：**
- DEAP 内置 NSGA-II 实现（`algorithms.eaMuPlusLambda`）
- 自定义拥挤距离计算
- 结果聚类避免相似方案过多（基于目标空间欧氏距离）

### 2.2.6 可行性验证模块

**职责：**
- 独立验证给定方案是否满足所有约束
- 输入方案，输出布尔值和详细验证报告
- 用于后期验证和调试

**几何可行性：**
- 所有物品在容器内（边界检查）
- 无相互重叠（AABB 碰撞检测）
- 支撑条件满足（每个物品底部 ≥60% 被支撑）

**物理可行性：**
- 总重量不超过限制
- 重心在安全范围内（与几何中心偏移 ≤ 容器尺寸的 15%）
- 易碎品不被重物压迫（易碎品上方无其他物品）

**朝向可行性：**
- 每个放置商品的朝向符合其 `forbidden_horizontal_dim` 约束
- 3种朝向定义：朝向1=(L,H,W)、朝向2=(L,W,H)、朝向3=(W,L,H)
- 若商品标记了禁止水平维度，验证实际朝向未将该维度作为水平方向

**稳定性评分计算：**

| 维度 | 计算方式 | 权重 |
|------|----------|------|
| 支撑率 | 平均每个物品的支撑面积比例 | 0.4 |
| 重心高度 | `1 - 重心高度 / 容器高度` | 0.3 |
| 堆叠层数 | `1 - (层数 - 1) / 最大可能层数` | 0.3 |

**综合公式：**
```
S = 0.4 * 支撑率 + 0.3 * (1 - 重心高度/容器高度) + 0.3 * (1 - (层数-1)/最大层数)
```

**技术实现：**
- 独立的验证器类 `FeasibilityVerifier`
- 方法：`verify(solution) -> (bool, Report)`
- 报告包含：各检查项通过/失败状态、稳定性分项得分、改进建议

## 前端组件设计

### ControlPanel
- 集装箱选择：预设下拉 (20GP/40GP/40HQ) + 自定义输入
- 商品列表：动态表格，每行输入 ID/长/宽/高/重量/数量/批次号/禁止水平维度
- 禁止水平维度：每行下拉选择（无限制/长度/宽度/高度）
- 导入按钮：支持批量导入 (JSON/CSV)
- 执行按钮：调 API 并显示加载状态

### Layout3D (Three.js)
- `ContainerMesh`: 半透明线框集装箱
- `PlacedItem`: 每个放置商品用 BoxGeometry + 材质颜色
- `OrbitControls`: 自由旋转/缩放/平移
- 点击拾取：Raycaster 检测，显示商品信息 Tooltip
- 爆炸视图：按 placement 位置偏移
- 视角快捷：前/侧/顶/透视图按钮

### ResultPanel
- 空间利用率进度条 (百分比 + 颜色)
- 载重利用率进度条
- 放置清单表格
- 未放置商品警告
- 导出结果按钮 (JSON)

## 预设集装箱

| 类型 | 长(mm) | 宽(mm) | 高(mm) | 最大载重(kg) |
|------|--------|--------|--------|-------------|
| 20GP | 5898 | 2352 | 2395 | 28000 |
| 40GP | 12032 | 2352 | 2395 | 28000 |
| 40HQ | 12032 | 2352 | 2695 | 28000 |

## 测试策略

### 后端测试 (pytest)

| 测试 | 内容 |
|------|------|
| test_rotation.py | 3 种朝向正确性、去重处理、forbidden_horizontal_dim 过滤 |
| test_extreme_point.py | EP 生成、有效性检查、评分排序、碰撞检测、支撑检查 |
| test_space_cutter.py | 空间分割、合并、废弃逻辑、最大矩形维护 |
| test_packer.py | 完整流程：单商品、多商品、超重、空间不足、批次优先排序、重心约束检查 |
| test_genetic_algorithm.py | 编码/解码、交叉/变异算子、适应度计算、种群收敛 |
| test_local_search.py | 邻域生成、搜索策略、模拟退火接受概率、终止条件 |
| test_pareto_optimizer.py | 非支配排序、拥挤距离、Pareto 前沿提取 |
| test_feasibility.py | 几何验证、物理验证、稳定性评分公式、易碎品检查、朝向约束验证、重心偏离度检查 |
| 利用率基准 | Phase 1 基本算法 ≥ 65%；Phase 2 优化后 ≥ 75% |
| 多方案输出 | Phase 2 输出不少于 3 个非支配方案 |

### 前端测试 (vitest + testing-library)

| 测试 | 内容 |
|------|------|
| ControlPanel | 表单输入、验证、提交 |
| ResultPanel | 数据渲染、空状态、错误状态 |
| API Service | 请求构建、响应解析、错误处理 |

## 验收标准

### Phase 1 (基础引擎)
1. 基础功能：输入商品 → 一键优化 → 展示 3D 布局
2. 空间利用率 ≥ 65% (随机生成的测试数据集，混合尺寸)
3. 单次优化响应时间 < 3 秒 (20 种商品以内)
4. 支持三种预设集装箱 + 自定义
5. 商品颜色区分，点击可查看信息
6. 3D 场景可旋转/缩放/平移
7. 批次优先：小批次商品必须在大批次之前装入（相同极值点优先级下）
8. 朝向约束生效：标记了 `forbidden_horizontal_dim` 的商品不会以该维度水平放置
9. 重心安全：所有方案的重心偏移不超过容器尺寸的 15%

### Phase 2 (智能优化)
10. 空间利用率 ≥ 75% (同数据集，经 GA+LS 优化后)
11. 遗传算法收敛稳定，100 代内适应度不再显著提升
12. 局部搜索每次迭代 ≤ 500ms (50 种商品以内)
13. Pareto 优化器返回 ≥ 3 个非支配方案供用户选择
14. 方案包含完整可行性验证报告（几何/物理/朝向/稳定性评分）
15. 平衡解在利用率、稳定性、重心三项指标上均不低于极端解的 80%
16. 易碎品标记生效：易碎品上方无重物压迫
17. 数据验证模块准确拦截非法输入（尺寸≤0、超容等）
18. 重心偏离度在API响应中返回（`cg_deviation_ratio`）
