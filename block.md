# 3D Container Loading Problem（CLP）—— 基于 Block Packing + Extreme Point 的装箱算法设计

你是一名资深算法工程师，需要实现一个企业级集装箱装载系统（Container Loading System）。

目标是在满足装载约束和安全约束的情况下，尽可能提高集装箱空间利用率。

------

# 二、为什么不能直接使用普通贪心

普通方案：

1. 商品按体积排序
2. 遍历候选点
3. 能放则放
4. 放不了换下一件

问题：

会产生大量空间碎片（Fragmentation）

例如：

A B A B A B

最终形成大量不规则剩余空间。

而企业级装箱系统通常希望：

同种商品形成规则块状区域。

例如：

AAAA
AAAA
AAAA

BBBB
BBBB

这样：

- 剩余空间更规则
- 候选点更少
- 空间利用率更高
- 稳定性更好

因此采用：

Block Packing

而不是

Single Box Packing

------

# 三、Block Packing 核心思想

不要直接装箱子。

先生成 Block。

例如：

商品A:

60×40×30

库存：

100件

可以生成：

1×1×1
60×40×30

2×2×1
120×80×30

2×2×2
120×80×60

3×2×2
180×80×60

4×2×2
240×80×60

...

这些 Block 本质上是：

多个相同SKU组成的长方体。

之后：

装箱对象变成：

Block

而不是：

Box

------

# 四、Block生成算法

对于每个SKU：

设：

boxL
boxW
boxH

库存：

count

枚举：

nx
ny
nz

满足：

nx × ny × nz <= count

生成：

blockLength = nx × boxL

blockWidth = ny × boxW

blockHeight = nz × boxH

blockCount = nx × ny × nz

Block:

{
sku,
nx,
ny,
nz,
length,
width,
height,
volume
}

限制：

避免生成过多Block。

例如：

最大：

nx <= 6
ny <= 6
nz <= 4

或者：

blockVolume <= containerVolume × 0.3

------

# 五、Block质量评价

生成Block后进行排序。

优先选择：

1. 体积大
2. 填充率高
3. 长宽比合理

评分：

score =
volumeWeight * volumeRatio
+
cubeWeight * compactness

其中：

compactness =
min(l,w,h)
/
max(l,w,h)

越接近立方体越好。

------

# 六、Extreme Point空间表示

使用 Extreme Point。

初始：

(0,0,0)

放置一个Block后：

产生新的候选点：

(x+l,y,z)

(x,y+w,z)

(x,y,z+h)

所有候选点维护在：

Priority Queue

中。

------

# 七、候选放置搜索

对于每个Block：

遍历所有Extreme Point。

检查：

if Fit(block, point):

生成候选方案

candidate

------

# 八、放置合法性检查

必须满足：

## 1. 不越界

x+l <= containerLength

y+w <= containerWidth

z+h <= containerHeight

------

## 2. 不碰撞

与已有Block无交集

AABB检测：

if overlap:
invalid

------

## 3. 支撑率

必须满足：

supportArea
/
bottomArea

> = threshold

例如：

70%

否则：

不允许悬空

------

## 4. 承重约束

重货不能压轻货

如果：

weightTop > maxLoadBelow

则：

invalid

------

# 九、放置评分函数

不要找到第一个位置就放。

而是：

对所有合法位置打分。

score =

100 * supportRatio

- 

80 * wallContactRatio

- 

60 * sameSkuContactRatio

- 

50 * volumeUtilization

- 

30 * floorContactRatio

- 

40 * fragmentationPenalty

- 

20 * centerOfGravityPenalty

------

# 十、同SKU聚集奖励

核心思想：

相同SKU尽量堆在一起。

计算：

sameSkuContactArea

例如：

新Block接触：

A
A
A

接触面积越大：

得分越高。

奖励：

clusterReward =
contactArea

这样系统会自动形成：

AAAA
AAAA
AAAA

而不是：

ABABAB

------

# 十一、剩余空间规整度

企业软件非常关注：

Residual Space Quality

放置后计算：

剩余空间是否仍接近长方体。

例如：

剩余空间：

300×200×150

得分高。

如果：

产生L型空间

得分低。

定义：

fragmentationPenalty

用于惩罚碎片化。

------

# 十二、搜索策略

不要使用纯贪心。

采用：

Beam Search

beamWidth = 20

每一步：

保留前5个最优状态。

状态：

{
placedBlocks,
remainingInventory,
extremePoints,
score
}

继续扩展。

最终：

取得分最高解。

------

# 十三、Block拆分机制

如果大Block放不进去：

允许拆分。

例如：

4×2×2

拆为：

2×2×2

- 

2×2×2

或者：

3×2×2

- 

1×2×2

递归尝试。

这样能够提高最终填充率。

------

# 十四、装载流程

Step1:

生成Block库

Step2:

Block排序

Step3:

初始化Extreme Point

Step4:

Beam Search

Step5:

尝试放置Block

Step6:

更新候选点

Step7:

更新库存

Step8:

继续搜索

Step9:

输出最佳方案

------

# 十六、优化目标

Primary:

最大化：

loadedVolume
/
containerVolume

Secondary:

最大化：

stability

Tertiary:

最小化：

fragmentation

最终目标：

在企业级集装箱装载场景下实现：

90%+空间利用率

并保持良好的稳定性、可解释性和计算速度。