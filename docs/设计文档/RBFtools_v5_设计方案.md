# RBFtools v5.0 — 整体设计与改造方案

> **版本**：设计草案 v1.0
> **日期**：2026-04-24
> **基线**：v4.1.0（MVC 重构后）
> **目标对齐**：铁拳 8 AnimaRbfSolver 功能对齐 + 数值稳定性 + 性能 + 工作流 + 跨引擎一致性
> **依据**：
> - `docs/源文档/技术分析MD/` 下 13 份技术分析报告
> - `docs/源文档/铁拳技术文档/` 4 份 CEDEC/GDC 公开资料
> - `docs/源文档/chadvernon/jsRadial-master/`（C++ RBF 参考实现）
> - `docs/源文档/chadvernon/cmt-master/scripts/cmt/rig/rbf.py`（Python API 参考）
> - 当前 `modules/RBFtools/scripts/RBFtools/` 源码 + `source/RBFtools.h`

---

## 目录

- [PART A — 现状快照](#part-a--现状快照)
- [PART B — 差距矩阵（当前 vs AnimaDriver）](#part-b--差距矩阵当前-vs-animadriver)
- [PART C — AnimaRbfSolver 全复刻方案](#part-c--animarbfsolver-全复刻方案)
- [PART D — 数值与性能优化方案](#part-d--数值与性能优化方案)
- [PART E — 面向未来的增强功能](#part-e--面向未来的增强功能)
- [PART F — 分阶段实施路线图](#part-f--分阶段实施路线图)
- [PART G — 关键数学细节（LaTeX）](#part-g--关键数学细节latex)

---

## PART A — 现状快照

### A.1 当前架构（v4.1.0）

- **C++ 节点**：单一 `MPxLocatorNode` — `RBFtools`，用 `type` 枚举切换 "Vector Angle" / "RBF" 两种模式
- **Python 层**：MVC 架构清晰，`core.py` ↔ `controller.py` ↔ `main_window.py` 三层解耦良好，`maya.cmds` 零泄漏到 UI
- **辅助模块**：`BRMatrix`（自有矩阵类，`source/BRMatrix.cpp`）做数值计算
- **Undo**：所有场景改动用 `undo_chunk` 上下文管理器封装 ✅
- **i18n**：中英文双语框架已就位

### A.2 已具备的关键功能（从 `RBFtools.h` 枚举的节点属性反推）

| 类别 | 属性 / 能力 |
|---|---|
| **Kernel** | Linear / Gaussian1 / Gaussian2 / Thin Plate / Multi-Quadratic / Inverse Multi-Quadratic |
| **Radius** | Mean Distance / Variance / StdDev / Custom（自动锁） |
| **距离度量** | Euclidean / Angle（Angle 模式隐含四元数距离，需确认） |
| **RBF 模式** | Generic（标量空间）/ Matrix（矩阵空间，用 `poseMatrix`+`poseParentMatrix`+`poseRotateOrder`） |
| **Multi-Driver** | `driverList` + `driverIndex` 多索引驱动（部分 AnimaDriver 分层能力） |
| **Twist 处理** | `twistAxis` + `drawTwist` + `poseDrawTwist`（暗示扭转可视化） |
| **Viewport 2.0** | `RBFtoolsOverride` 自绘（pose 球可视化） |
| **Pose CRUD** | add / recall / update / delete + blendShape auto-fill（rest + one-hot） |
| **Recall 安全** | 临时断开 → setAttr → 重连，避开 DG 覆盖 |

### A.3 Python 层亮点

- `PoseData` 用 `__slots__`，避免误拼字段
- `float_eq` / `vector_eq` 统一用 `math.isclose(abs_tol=1e-6)`，避免 Maya 浮点噪声误判
- `_multi_indices` 支持 Maya 稀疏 multi-instance 数组
- `disconnect_outputs` 会主动清理 Maya 自动插入的 `unitConversion` 中间节点
- OpenMaya 2 API 做世界/局部矩阵计算（`inclusiveMatrix` / `exclusiveMatrix`），精度 & 性能均优于 `cmds.getAttr`

### A.4 紧迫性评估

MVC 架构是**扎实的**。不需要推倒重来——**所有增强都以"追加模块 + 扩展节点属性"方式落地**。
C++ 节点的属性命名（`driverList`, `poseMatrix`, `rbfMode`, `twistAxis`）说明作者对 AnimaDriver 结构有所借鉴，但关键机制（Clamp、Base Value、QWA、Source/Target/Calc 分层）仍缺失。

---

## PART B — 差距矩阵（当前 vs AnimaDriver）

对照 AnimaDriver 落地基准逐条核对：

| # | AnimaDriver 铁律 | 当前实现 | 差距评级 | 动作 |
|---|---|---|---|---|
| B1 | RBFSolver 与 Jiggle / AimConstraint 是六类 Solver 之一 | ❌ 只有 RBF + Vector Angle | **致命** | 新增 Jiggle solver + Aim solver 节点；或用 "Solver 模块化子模式" |
| B2 | 多属性异构输入（多骨 × 多属性） | ⚠️ 有 `driverList` 但 UI 未暴露 | **高** | UI 增加 "多源驱动" 区；core 增加 `add_driver_source` |
| B3 | 输入编码枚举：**BendRoll / Quaternion / ExponentialMap / Euler** 互转 | ❌ 只有 Euclidean / Angle 两个距离选项 | **致命** | 新增 `inputEncoding` 枚举 + 对应投影函数 |
| B4 | 惯例：输入 Quaternion(Roll/BendH/BendV)，输出 Euler | ❌ 当前无输入-输出编码分离概念 | **高** | 输出端增加 `outputEncoding` 枚举 |
| B5 | Driver Clamp（输入钳制到 registered pose 的 min/max） | ❌ 完全缺失 | **致命** | 新增 `poseMin[]` / `poseMax[]` + `clamp` bool；compute 阶段做钳制 |
| B6 | Output Base Value（训练前减基准、推理后加回；Scale 通道默认 1） | ❌ 完全缺失 | **致命** | 新增 `baseValue[]` 向量 + `outputIsScale[]` bitmask |
| B7 | 按补助骨拆分 RBF 节点 | ❌ 无拆分工具 | **中** | 新增 "Split by Aux Bone" 辅助工具 + 性能分析器 |
| B8 | Pose 精简（删同值 / 未连接 attr / 全 pose 同值 attr） | ❌ 无 | **高** | 新增 Pose Pruner 工具 |
| B9 | Maya ↔ 引擎一致性（local Transform 计算） | ⚠️ 有 `get_local_matrix` 工具函数，但未用于 solver compute | **高** | C++ compute 统一用 local Transform |
| B10 | 单独保存 local Transform 规避数值误差 | ❌ 未实现 | **中** | 节点新增 `localTransformCache[]` |
| B11 | GUI：视口实时回写 pose | ⚠️ 仅 `update_pose` 手动触发 | **中** | 增加 "Live Edit Mode" 切换 |
| B12 | GUI：清理未用 driver/attr | ❌ 无 | **中** | Pose Pruner 的子功能 |
| B13 | GUI：镜像 | ❌ 无 | **高** | 新增 Mirror 工具（L/R 或自定义命名规则） |
| B14 | GUI：driver 锁豁免 | ⚠️ `recall_pose` 用断连-重连，对 locked 输入有效 | **低** | 补充提示 UI，让用户知道哪些 driver 被锁了 |
| B15 | GUI：Import/Export（JSON） | ❌ 无 | **高** | 新增 `io.py` 模块 + JSON schema |

**定性结论**：当前是 "一个能用的 RBF 节点"；AnimaRbfSolver 是 "一条完整的补助骨生产流水线"。差距不在数学，在**工作流 + 约束 + 导出**。

---

## PART C — AnimaRbfSolver 全复刻方案

### C.1 节点层重构：单节点多角色 vs 多节点分工

**决策**：在当前 `RBFtools` 单节点基础上扩展，不新增六类 Maya 节点。理由：

1. 避免用户手动创建一堆节点——AnimaDriver 的六类节点是内部抽象，对外可以呈现为"一个 RBF 节点内部的配置段"
2. Maya 节点过多会拖累 DG 评估；合并为复合节点性能更好
3. 现有 C++ 代码架构不会崩

但 **逻辑上**仍分六个"段"，体现在 compute 流程里：

```
[Source 段]   读取 driverList[i] 的属性 → 聚合到统一输入向量
     ↓
[Calc 段]     数学预处理：inputEncoding 变换 / 标准化 / Clamp
     ↓
[Solver 段]   RBF 核心计算（根据 type 切到 Jiggle / Aim / RBF）
     ↓
[Calc 段]     输出后处理：减 Base → 加权 → 加回 Base；outputEncoding
     ↓
[Constraint 段] 可选的 Aim / 朝向约束（作为额外输出通道）
     ↓
[Target 段]   output[] 写到下游（已有）
     ↓
[Other 段]    debug / draw / curveRamp / log
```

### C.2 新增节点属性（按段分组）

#### C.2.1 [Source 段] 多源驱动支持

现有 `driverList` 已经是 compound multi，补充：

```cpp
static MObject driverSource;       // compound, multi
  static MObject driverSource_node;      // MMessage — 目标节点
  static MObject driverSource_attrs;     // MString, multi — 属性名列表
  static MObject driverSource_weight;    // double[]   — 该源在输入向量中的权重
  static MObject driverSource_encoding;  // enum: Raw/Quaternion/BendRoll/ExpMap/Euler
```

#### C.2.2 [Calc 段] 输入编码枚举（核心新增）

```cpp
static MObject inputEncoding;
// enum: 
//   0 = Raw Euler (legacy, 警告)
//   1 = Quaternion XYZW (4-dim per bone)
//   2 = BendRoll (立体投影, 3-dim: roll + bendH + bendV)  
//   3 = ExponentialMap / Log-Quat (3-dim, R^3 连续)
//   4 = Swing-Twist Separated (5-dim: swingXYZW + twist)
```

#### C.2.3 [Calc 段] Driver Clamp

```cpp
static MObject clampEnabled;           // bool, default true
static MObject clampInflation;         // double, default 0.0 (向外膨胀比例, 避免硬切)
// compute time: per-input:
//   min_i = min(pose_i[k].input for all k)
//   max_i = max(pose_i[k].input for all k)
//   input_i = clamp(raw_input_i, min_i - inflation*range, max_i + inflation*range)
```

#### C.2.4 [Calc 段] Output Base Value + Scale 通道

```cpp
static MObject baseValue;              // double, multi (per-output)
static MObject outputIsScale;          // bool,   multi (per-output)
// training time:
//   if outputIsScale[k]: store (poseValue[k] - 1.0) as "delta"
//   else:                store (poseValue[k] - baseValue[k]) as "delta"
// inference time:
//   if outputIsScale[k]: output[k] = 1.0 + weightedDelta
//   else:                output[k] = baseValue[k] + weightedDelta
```

这条是**铁律**——防止旋转/缩放通道训练时基线错误导致 t-pose 抖动。

#### C.2.5 [Solver 段] 解算器类型

```cpp
static MObject solverType;
// enum:
//   0 = RBF (默认, 原有逻辑)
//   1 = Jiggle (弹簧阻尼)
//   2 = Aim Constraint (朝向插值)
//   3 = Curve Driven (ramp 驱动, 已部分存在)
```

#### C.2.6 [Other 段] 导出配置

```cpp
static MObject exportSchema;           // MString — JSON schema 版本号
static MObject exportName;             // MString — 导出时的逻辑名称（引擎侧用）
```

#### C.2.7 [Pose 存储] Swing-Twist 分字段（借鉴 CMT RBF）

```cpp
// 在 poses[i] compound 里新增
static MObject poseSwingQuat;    // double4 — swing 部分
static MObject poseTwistAngle;   // double  — twist 角度
static MObject poseSwingWeight;  // double, default 1.0
static MObject poseTwistWeight;  // double, default 1.0
static MObject poseSigma;        // double, default -1 (-1 表示使用全局 radius)
```

### C.3 Python core.py 新增函数

```python
# --- 输入编码变换（对齐 Report 12） ---
def encode_quaternion_bendroll(qx, qy, qz, qw, twist_axis):
    """将单位四元数分解为 Swing-Twist, 再把 Swing 做立体投影.
    返回 (roll, bend_h, bend_v) ∈ R^3.
    数学：见 PART G 公式 (G.3)"""

def encode_log_quat(qx, qy, qz, qw):
    """指数映射到 R^3 (log-quaternion). 连续无翻转."""
    # q = cos(θ/2) + sin(θ/2)·n → log(q) = (θ/2) · n

def encode_euler_to_quaternion(rx, ry, rz, rotate_order):
    """Maya 欧拉角 → 四元数（用于 input_encoding == Quaternion）"""

# --- 输入钳制 ---
def compute_pose_bounds(poses):
    """扫描所有 pose 的 inputs, 返回 (min_vec, max_vec)"""

def apply_clamp(input_vec, min_vec, max_vec, inflation=0.0):
    """逐维钳制"""

# --- Base Value 管理 ---
def capture_base_values(driven_node, driven_attrs, output_is_scale):
    """在 Apply 前捕获静止姿势基准; Scale 通道强制 1.0"""

# --- Pose 精简（对齐铁律） ---
def prune_duplicate_poses(poses, tol=1e-4):
    """删除 input 向量重复的 pose, 保留第一个"""

def prune_unused_output_attrs(poses, attrs, tol=1e-4):
    """删除所有 pose value 为同一常数的输出维度"""

def prune_unconnected_inputs(poses, attrs, driver_node):
    """删除 driver_node 上没连上下游的输入属性"""

# --- Mirror ---
MIRROR_RULES = [
    (r"(_|^)L(_|$)", r"\1R\2"),
    (r"(_|^)Left(_|$)", r"\1Right\2"),
    # ...
]

def mirror_pose(pose, driver_attrs, driven_attrs, axis="x"):
    """镜像一个 pose:
    1. 翻转 mirror_axis 维度上的平移 (tx → -tx)
    2. 翻转 swing (qx, qw → -qx, qw) 对于绕镜像轴的分量
    3. 按命名规则重映射 driver/driven 节点 (L_shoulder → R_shoulder)
    """

# --- IO ---
def export_solver_to_json(node):
    """导出为 AnimaDriver 兼容 schema"""

def import_solver_from_json(json_path, target_node=None):
    """反向导入; 若 target_node 为 None 则创建新节点"""

# --- Live Edit Mode (视口实时回写) ---
class LivePoseWriter:
    """scriptJob 监听场景变更, 当用户在视口改动被选中的 driver 时,
    自动写回当前 row 的 inputs. 支持节流 (每 100ms 一次)."""
```

### C.4 C++ compute() 流水线改造

伪代码（按 PART C.1 六段展开）：

```cpp
MStatus RBFtools::compute(const MPlug &plug, MDataBlock &data) {
    // === [Source 段] ===
    std::vector<double> rawInput;
    for (driverSource in driverList) {
        auto attrs = getSourceAttrs(driverSource);
        for (attr in attrs) {
            rawInput.push_back(readPlug(attr));
        }
    }
    
    // === [Calc 段 - 输入] ===
    auto encoded = applyInputEncoding(rawInput, inputEncodingVal);
    if (clampEnabled) {
        encoded = clamp(encoded, poseMinVec, poseMaxVec, inflationVal);
    }
    encoded = normalize(encoded, inputNorms);
    
    // === [Solver 段] ===
    std::vector<double> deltaOutput;
    switch (solverType) {
        case 0: deltaOutput = solveRBF(encoded);       break;
        case 1: deltaOutput = solveJiggle(encoded);    break;  // 新
        case 2: deltaOutput = solveAim(encoded);       break;  // 新
        case 3: deltaOutput = solveCurveRamp(encoded); break;
    }
    
    // === [Calc 段 - 输出] ===
    std::vector<double> finalOutput(deltaOutput.size());
    for (size_t k = 0; k < deltaOutput.size(); ++k) {
        if (outputIsScaleArr[k])
            finalOutput[k] = 1.0 + deltaOutput[k];
        else
            finalOutput[k] = baseValueArr[k] + deltaOutput[k];
    }
    
    // === [Constraint 段] (可选) ===
    if (hasAimConstraint) {
        finalOutput = applyAimConstraint(finalOutput);
    }
    
    // === [Target 段] ===
    setOutputValues(finalOutput, data, !active);
    
    // === [Other 段] ===
    if (exposeData) writeDebugAttrs(finalOutput);
    
    return MS::kSuccess;
}
```

---

## PART D — 数值与性能优化方案

### D.1 求解器策略（多层级 Fallback）

基于 Report 09 / 10 / 11 + Chad Vernon 参考：

```
输入矩阵 M = (特征距离矩阵 + λI)   // Report 06 正则化
    ↓
[Tier 1] Cholesky (LLᵀ / LDLᵀ)           — 对称正定时最快 (Report 09)
    失败? (非正定)
    ↓
[Tier 2] ColPivHouseholderQR             — Chad Vernon 默认, 稳定 + 速度均衡
    失败? (严重奇异)
    ↓
[Tier 3] LU with partial pivoting (PA = LU)    // Report 10
    失败? (奇异)
    ↓
[Tier 4] SVD-based pseudo-inverse (M⁺)         // Report 11
    + 小于 1e-6 的奇异值截断
```

在 `BRMatrix.cpp` 增加分层 solve 方法：

```cpp
enum SolveMethod { AUTO, CHOLESKY_ONLY, QR_ONLY, LU_ONLY, SVD_ONLY };
BRMatrix BRMatrix::solve(const BRMatrix& B, SolveMethod hint = AUTO,
                         double regularization = 1e-8,
                         double svdThreshold = 1e-6);
```

推荐默认：`AUTO` + `regularization = 1e-8`。
**对齐 AnimaDriver**：Jiggle solver 使用独立的欧拉积分器，不共享此 solve 路径。

### D.2 Kernel 矩阵优化（Report 05）

当前 `BRMatrix` 是稠密矩阵。对于大补助骨场景（245 根 × 每根 10 pose = 2450 样本），应：

1. **对称性**：距离矩阵天然对称，只存上三角，**内存减半**
2. **分块**：按 Cache Line（64 Byte = 8 double）做 8x8 分块，提升 L1 命中率
3. **SIMD**：SSE2 double 版 `_mm_add_pd` / AVX2 `_mm256_add_pd`，4-8x 加速

优先级：对称性 > SIMD > 分块。预期 1000 样本规模可从 150ms 降到 40ms。

### D.3 四元数输入正确性（Report 12）

核心公式（见 PART G）：

```
d(q₁, q₂) = 1 - |q₁ · q₂|     // 绝对值关键：q 与 -q 等价
```

当前 `distanceType == Angle` 具体实现需要在 `RBFtools.cpp:getAngle()` 里确认是否加了绝对值。**强制要求**：若未加，这是一个隐蔽 bug，补助骨会在 ±180° 附近 flip。

混合维度归一化（标量 + 四元数）：每种距离分开计算 → 除以各自的 `norm_factor` → 再加权合并：

```
d_total = α · (d_scalar / σ_scalar) + β · (d_quat / σ_quat)
```

**Chad Vernon 的教训**：它用单一 `rotationMultiplier` 缩放所有旋转维度——方案过于粗糙。本设计改用 per-dimension `norm_factors[]`。

### D.4 四元数输出（QWA，Report 13）——关键闭环

**当前短板**：输出端如果直接对四元数分量 (qx, qy, qz, qw) 做加权线性组合，结果不再是单位四元数，会导致蒙皮塌陷。

**解决**：Quaternion Weighted Average

```
M = Σᵢ wᵢ · qᵢ · qᵢᵀ    (4x4 矩阵)
q_avg = M 的最大特征值对应的特征向量
```

实现选项：

- **精确**：用 Eigen 的 `SelfAdjointEigenSolver<Matrix4d>`
- **近似**（快 10x）：Power Iteration 10-20 轮，已够美术精度

**触发条件**：输出通道被标记为 "Quaternion Group"（每 4 个连续输出视为一组四元数）。UI 给 `outputQuaternionGroups` 数组属性暴露。

### D.5 局部变换预存（AnimaDriver 铁律 B10）

当前 pose 存的是绝对值 `poseValue[]`。引擎侧在节点边界做 `object-matrix ↔ local-Transform` 转换会引入浮点漂移。

**改造**：新增 `poseLocalTransform[k]`（compound: t, r, s）——在 Apply 时**同时**存绝对值和本地变换分解值。引擎侧直接读取 local Transform，不做二次矩阵运算。

---

## PART E — 面向未来的增强功能

### E.1 性能分析器（Pose Profiler）

基于 Report 05 的性能模型，为每个 RBF 节点报告：

```
N_poses:      42
N_inputs:     12
N_outputs:    24
Matrix size:  42×42 (symmetric, 882 cells in upper tri)
Est. solve:   Cholesky ~ 0.8 ms, SVD ~ 3.2 ms
Memory:       14 KB (data) + 28 KB (working)
Suggestion:   [OK] 规模健康
```

当 N_poses > 80 或 inputs × outputs > 500 时给出**拆分建议**：

> "建议按补助骨拆分为 3 个 RBFtools 节点：shoulder_L (8 poses) / shoulder_R (8 poses) / chest (26 poses)"

### E.2 AnimaDriver JSON Schema（引擎导出）

```json
{
  "schema": "animadriver.rbf.v1",
  "nodeName": "RBF_shoulder_L",
  "solverType": "RBF",
  "inputs": [
    {"source": "joint_L_shoulder", "attrs": ["rotate"], "encoding": "Quaternion"},
    {"source": "joint_L_elbow",    "attrs": ["rx"],      "encoding": "Raw"}
  ],
  "outputs": [
    {"target": "aux_L_deltoid",   "attr": "translateY", "isScale": false, "baseValue": 0.0},
    {"target": "aux_L_deltoid",   "attr": "scaleX",     "isScale": true,  "baseValue": 1.0}
  ],
  "poses": [
    {"id": 0, "inputs": [...], "values": [...], "min": [...], "max": [...]}
  ],
  "kernel": "Gaussian",
  "radius": 0.85,
  "regularization": 1e-8,
  "clamp": {"enabled": true, "inflation": 0.1}
}
```

**双向**：`import_solver_from_json` 允许 TD 把引擎侧测试数据反导进 Maya 对照。
**命名**：借鉴 Chad Vernon 的 `aliasAttr` 用法，export 时生成可读别名（`outputInterpolate[5]` → `shoulderLOut`）。

### E.3 Mirror 工具（对齐 GUI 铁律 B13）

策略：对称命名规则 + 镜像轴

```python
MIRROR_NAME_RULES = [
    (r"(^|_)L($|_)",    r"\1R\2"),
    (r"(^|_)Left($|_)", r"\1Right\2"),
    (r"_[lL]\b",         "_r"),
]

def mirror_rbf_node(src_node, mirror_axis="x", name_rules=MIRROR_NAME_RULES):
    """创建镜像节点:
    1. 复制所有 pose (input/value)
    2. 对每个 pose:
       - 输入: 翻转 mirror_axis 的平移, 翻转 swing-quaternion
       - 输出: 按 outputIsScale 分别翻转(scale 维度不变, translate 翻转)
    3. 按规则重映射 driver/driven 节点名
    4. 使用 undo_chunk 包装
    """
```

### E.4 Live Edit Mode（视口实时回写，铁律 B11）

```python
class LivePoseEditor:
    """监听场景变更, 当用户在视口 transform driver 时自动更新当前行.
    
    机制:
        scriptJob -attributeChange driver.tx -> throttle 100ms -> update_pose(row)
    
    UI:
        [X] Live Edit 复选框 + 当前 active row 高亮
        在 pose table 选中一行即开始监听该行对应的 driver
    """
```

### E.5 Pose Pruner（对齐铁律 B8, B12）

一键清理，UI 给预览 + 确认对话框：

```
Pose Pruner Report
├── ✗ 发现 3 个重复输入 pose (仅保留第一个): pose[4], pose[7], pose[12]
├── ✗ 发现 2 个无变化的输出属性 (全 pose 同值): driven.rx, driven.rz
├── ✗ 发现 1 个未连接的 driver 属性: driver.tz (从未被下游使用)
└── 预估 matrix 缩减: 15×24 → 12×22 (节省 38% 内存, 12% 求解时间)

        [预览变化]  [应用清理]  [取消]
```

### E.6 Jiggle Solver（对齐铁律 B1）

新 `solverType = 1` 时启用，用经典 Verlet 积分：

```
x_{n+1} = x_n + (x_n - x_{n-1}) * (1 - damping) + a * dt²
a = stiffness * (targetPos - x_n)
```

关键 AnimaDriver 细节：**慢动作下的 deltaTime 修正**（Report 02）

- 锁定到固定 `dt = 1/60`，累积余数
- 或按 `dt_effective = min(dt_frame, 1/30)` 截断

新增属性：

```cpp
static MObject jiggleStiffness;   // 0.1
static MObject jiggleDamping;     // 0.9
static MObject jiggleMass;        // 1.0
static MObject jiggleTimeStep;    // 1/60
static MObject jiggleEnabled;     // bool
```

### E.7 Aim Constraint Solver（对齐铁律 B1）

`solverType = 2`：把 RBF 加权后的目标位置转成朝向四元数（`aimVector × upVector`），直接作为输出。与 Maya 原生 `aimConstraint` 等价，但数据流完全在单个 RBFtools 节点内。

### E.8 安全 & 调试

- **`safeMode`** 属性：启用时 compute 失败自动回退到 bind pose，而不是发 error 停 DG
- **`solverStats`** 只读复合属性：`lastSolveTime_ms` / `conditionNumber` / `fallbackUsed`（Cholesky/QR/LU/SVD）
- **调试可视化**：viewport 中把输入点、pose 点、当前插值点画成不同颜色

### E.9 自动中性样本（借鉴 CMT）

创建 RBF 节点时，UI 的"New"按钮默认加 3 个中性样本（全零 swing / 全零 twist / 全零 swing+twist），避免美术忘记加 rest pose 导致插值退化。可通过 optionVar 关闭。

### E.10 每目标独立 sigma（借鉴 Chad Vernon jsRadPose）

当前 RBFtools 是单一 `radius`。Chad Vernon 的 jsRadPose 给每个 target 独立 `targetSigma`。对不对齐目标（稀疏 + 稠密混合场景）很有用。

```cpp
// 在 poses[i] compound 里追加
static MObject poseSigma;              // double, default = -1 (使用全局)
// compute 时: sigma_i = (poseSigma[i] >= 0) ? poseSigma[i] : globalRadius
```

**优先级**：低-中。Milestone 5 之后做即可。

---

## PART F — 分阶段实施路线图

### Milestone 1 — 数值正确性（**最高优先级**，预估 2 周）

- [M1.1] 在 `getAngle()` 里验证并修复 `|q·q|` 绝对值（防 180° flip）
- [M1.2] 实现 Output Base Value + outputIsScale（铁律 B6）
- [M1.3] 实现 Driver Clamp（铁律 B5）
- [M1.4] 求解器四层 Fallback（Cholesky / QR / LU / SVD），正则化 λI
- [M1.5] 单元测试：覆盖 ±180° rotation / 接近奇异 pose / scale 通道

**交付**：已有 rig 可以稳定运行，不再有边缘 flip / scale=0 bug。

### Milestone 2 — 输入输出编码（预估 2 周）

- [M2.1] 输入编码枚举（BendRoll / ExpMap / Swing-Twist）+ encode 函数
- [M2.2] QWA 四元数输出（`outputQuaternionGroups`）
- [M2.3] local Transform 双存储（铁律 B10）
- [M2.4] UI：`rbf_section.py` 增加 Encoding 下拉框
- [M2.5] Pose 存储的 swing-twist 分字段（C.2.7）

**交付**：跨引擎一致性达标，肩关节无糖果纸挤压。

### Milestone 3 — 工作流工具（预估 2 周）

- [M3.1] Pose Pruner（铁律 B8, B12）
- [M3.2] Mirror Tool（铁律 B13）
- [M3.3] JSON Import/Export（铁律 B15）
- [M3.4] Live Edit Mode（铁律 B11）
- [M3.5] Pose Profiler + 拆分建议（铁律 B7）
- [M3.6] 自动中性样本（E.9）
- [M3.7] aliasAttr 自动命名（用于 JSON export）

**交付**：TD 手上的单个 RBFtools 节点能拉出一整条量产流水线。

### Milestone 4 — 附加 Solver（预估 2 周）

- [M4.1] Jiggle Solver（Verlet + dt 修正）
- [M4.2] Aim Constraint Solver
- [M4.3] `solverType` 分支在 compute() 里落地
- [M4.4] UI：solver 类型切换时自动隐藏/显示相关面板

**交付**：六类节点的 Solver 能力归并到单节点内。

### Milestone 5 — 性能与引擎对接（预估 2 周）

- [M5.1] BRMatrix 对称存储 + SIMD solve（Report 05）
- [M5.2] 性能统计 `solverStats`
- [M5.3] 每目标 sigma（E.10）
- [M5.4] UE5 端 runtime 组件（解析 JSON schema, 重建计算图）—— 如果在 scope
- [M5.5] Benchmark 场景：245 补助骨 @ 60FPS 验证

**交付**：生产级可用，性能对齐 Tekken 8 的 245 根补助骨指标。

---

## PART G — 关键数学细节（LaTeX）

### G.1 带正则化的 RBF 权重求解（Report 06 + 08）

设 $N$ 个 pose，每个 pose 输入 $\mathbf{x}_i \in \mathbb{R}^d$，输出 $\mathbf{y}_i \in \mathbb{R}^m$：

**Step 1** — 构建核矩阵 $\mathbf{K} \in \mathbb{R}^{N \times N}$：

$$K_{ij} = \phi\!\left(\frac{\|\mathbf{x}_i - \mathbf{x}_j\|}{\sigma}\right)$$

**Step 2** — 加正则化（Tikhonov）：

$$\tilde{\mathbf{K}} = \mathbf{K} + \lambda \mathbf{I}, \quad \lambda \approx 10^{-8}$$

**Step 3** — 减基准（对齐铁律 B6）：

$$\tilde{\mathbf{Y}}_{i,k} = \begin{cases} y_{i,k} - 1 & \text{if outputIsScale}[k] \\ y_{i,k} - b_k & \text{otherwise} \end{cases}$$

**Step 4** — 解权重矩阵 $\mathbf{W} \in \mathbb{R}^{N \times m}$：

$$\tilde{\mathbf{K}} \mathbf{W} = \tilde{\mathbf{Y}}$$

用 Cholesky / QR / LU / SVD 四层 fallback（PART D.1）。

**Step 5** — 推理时，对输入 $\mathbf{x}$（已 Clamp + Encoding + Normalize）：

$$\mathbf{k}(\mathbf{x})_i = \phi\!\left(\frac{\|\mathbf{x} - \mathbf{x}_i\|}{\sigma}\right)$$

$$\boldsymbol{\delta}(\mathbf{x}) = \mathbf{W}^\top \mathbf{k}(\mathbf{x})$$

$$\text{output}_k = \begin{cases} 1 + \delta_k & \text{if outputIsScale}[k] \\ b_k + \delta_k & \text{otherwise} \end{cases}$$

### G.2 四元数距离（Report 12）

$$d(q_1, q_2) = 1 - \left|q_1 \cdot q_2\right| = 1 - \left|q_{1x}q_{2x} + q_{1y}q_{2y} + q_{1z}q_{2z} + q_{1w}q_{2w}\right|$$

绝对值消除 $q \equiv -q$ 的路径歧义。角距离形式：

$$\theta(q_1, q_2) = 2 \arccos\!\left(\left|q_1 \cdot q_2\right|\right)$$

CMT 的归一化变体（`rbf.py:340`）：

$$d_{\text{norm}}(q_1, q_2) = \frac{\arccos(2(q_1 \cdot q_2)^2 - 1)}{\pi}$$

平方消除符号歧义，映射到 $[0, 1]$。

### G.3 Swing-Twist 分解（铁律 B4）

给定单位四元数 $q = (x, y, z, w)$ 和扭转轴 $\hat{\mathbf{a}} = (a_x, a_y, a_z)$：

**提取 twist**：

$$q_{\text{twist}} = \operatorname{normalize}(w, \; (x,y,z) \cdot \hat{\mathbf{a}} \cdot \hat{\mathbf{a}})$$

具体做法：

$$\mathbf{p} = (x, y, z) \cdot \hat{\mathbf{a}}^\top \hat{\mathbf{a}}, \quad q_{\text{twist}} = \frac{(w, p_x, p_y, p_z)}{\|(w, p_x, p_y, p_z)\|}$$

**提取 swing**：

$$q_{\text{swing}} = q \cdot q_{\text{twist}}^{-1}$$

### G.4 BendRoll 立体投影（铁律 B4）

从 $q_{\text{swing}}$ 取出非扭转分量 $(s_x, s_y, s_z)$（垂直于 $\hat{\mathbf{a}}$ 的平面内的投影）：

$$\text{bend}_H = \frac{2 s_h}{1 + s_w}, \quad \text{bend}_V = \frac{2 s_v}{1 + s_w}$$

其中 $s_h, s_v$ 是 $(s_x, s_y, s_z)$ 在与 $\hat{\mathbf{a}}$ 正交的两轴上的投影。$\text{roll}$ 则是 $q_{\text{twist}}$ 对应的扭转角：

$$\text{roll} = 2 \operatorname{atan2}(q_{\text{twist}}.\text{axis}\cdot\hat{\mathbf{a}}, q_{\text{twist}}.w)$$

### G.5 Log-Quaternion / Exponential Map（铁律 B3）

$$q = \cos(\theta/2) + \sin(\theta/2) \hat{\mathbf{n}} \Longrightarrow \log(q) = \frac{\theta}{2} \hat{\mathbf{n}} \in \mathbb{R}^3$$

距离直接用 $\|\log(q_1 \cdot q_2^{-1})\|$ 的欧几里得距离。适合 ROM < 180° 的补助骨。

### G.6 QWA 加权四元数平均（Report 13）

给定样本 $\{q_i\}$ 和权重 $\{w_i\}$：

$$\mathbf{M} = \sum_{i=1}^{N} w_i \, q_i q_i^\top \in \mathbb{R}^{4 \times 4}$$

$$q_{\text{avg}} = \arg\max_{\|q\|=1} q^\top \mathbf{M} q$$

即 $\mathbf{M}$ 最大特征值对应的特征向量。该方法在全局意义下最优，解决 LERP 退化问题。

### G.7 Driver Clamp 逐维

设训练集中第 $j$ 维输入的边界为：

$$m_j = \min_{i} x_{i,j}, \quad M_j = \max_{i} x_{i,j}, \quad r_j = M_j - m_j$$

推理时：

$$\tilde{x}_j = \operatorname{clamp}(x_j, \; m_j - \alpha r_j, \; M_j + \alpha r_j)$$

其中 $\alpha \in [0, 0.2]$ 是膨胀系数，默认 $\alpha = 0$（硬钳制）。

### G.8 Jiggle Verlet 积分（E.6）

基本形式：

$$\mathbf{x}_{n+1} = \mathbf{x}_n + (\mathbf{x}_n - \mathbf{x}_{n-1})(1 - c) + \mathbf{a}_n \Delta t^2$$

其中：

$$\mathbf{a}_n = \frac{k}{m}(\mathbf{x}_{\text{target},n} - \mathbf{x}_n)$$

$k$ 为弹性系数，$c$ 为阻尼系数 $\in [0,1]$，$m$ 为质量，$\Delta t$ 为时间步长。

慢动作保护：

$$\Delta t_{\text{eff}} = \min(\Delta t_{\text{frame}}, 1/30)$$

---

## 附录 — 文件对应索引

| PART | 主要依据来源 |
|------|-------------|
| A | 当前代码 `modules/RBFtools/scripts/RBFtools/*.py` + `source/RBFtools.h` |
| B | 用户提供的 AnimaDriver 落地基准（15 条铁律） |
| C | Report 01-04（铁拳四份公开资料）+ 当前 C++ 节点属性结构 |
| D | Report 05 (Large Datasets), 06 (Regression), 09 (Cholesky), 10 (LU), 11 (Moore-Penrose), 12 (Quat Input), 13 (Quat Output) + Chad Vernon jsRadial.cpp |
| E | Report 02, 04 (Tekken) + CMT rbf.py (CEDEC 扩展场景) |
| F | 综合 |
| G | Report 06, 08, 11-13 + Verlet 物理教科书 |

---

**文档结束**

_作为方案定稿，本文档为后续 Milestone 执行的唯一事实来源。执行中如发现方案错误或补充需求，请另起 `RBFtools_v5_addendum_YYYYMMDD.md`，不要直接覆写本文件。_
