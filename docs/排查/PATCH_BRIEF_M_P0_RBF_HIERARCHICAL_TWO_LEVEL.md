# Patch Brief — M_P0_RBF_HIERARCHICAL_TWO_LEVEL (Phase 16)

> Planner / Architect 设计稿 v2.5. 执行者照此实施.
>
> **Origin**: Phase 14 (dither + radius + update fix) 已 LANDED. Phase 15 (Output Clamp + Shepard for Scale) 已 LANDED. 现升级为**显式拓扑分层 RBF 架构** — Base-Delta Two-Level Factored Pose Space. 解决 Phase 15 5 层防御后仍残留的高维多 driver cluster overshoot.
>
> **数学基础**: Functional ANOVA decomposition (Hoeffding 1948) + Combo Corrective BlendShape (工业 30 年实践) + Shepard partition-of-unity gating (Shepard 1968).
>
> **Status**: APPROVED — 等执行者实施 Phase 5 alignment, Planner 批后再写代码.

---

## 阶段 1 — Schema 与数据结构扩展 (Hard Cap 2 层 + Driver Subset)

### 1.1 拓扑层级限制 (Depth Cap)

强制最大 2 层 (Base + Delta), 禁止递归树.

- 在 `poses` 复合属性中新增子属性:
  ```cpp
  static MObject poseParentIndex;  // kInt, default -1
  ```
- 语义:
  - `-1` = **Base Pose** (Layer 1)
  - `≥ 0` = **Delta Pose** (Layer 2), 该值指向一个 Base Pose 的 logical index
- **硬约束**: Delta 指向 Delta 视为非法配置 → training 时 warn + 该 Delta Pose 重新归类为 Base. 杜绝递归.

### 1.2 驱动降维隔离 (Driver Subset)

为消除维度诅咒, 每个 Pose 显式标记关心哪些 driver:

- 在 `poses` 中新增子属性:
  ```cpp
  static MObject poseDriverMask;   // typed kIntArray (or MFnIntArrayData)
  ```
- 语义: `poseDriverMask[k]` 是该 Pose 关心的 driver attr 在 `flat driver vector` 中的索引集合
- **Default 值**: 空数组 = "**关心所有 driver**" (backward compat — 等价旧版单层行为)
- **OOB 防御**: mask index ≥ `sum(driverSource[k].attrs.count)` 时丢弃 + `displayWarning`
- **空显式 mask** (= 数组非空但全 0 / size 0 显式禁用所有 driver): warn + 该 pose 不参与 base/delta 训练, 视为 ignore

### 1.3 C++ 数据结构 (`RBFtools.h`)

废弃单一 `wMat`. 引入:

```cpp
// New struct:
struct RBFSubNet {
    BRMatrix wMat;                       // 权重矩阵 (poseCount × solveCount)
    BRMatrix polyMat;                    // 多项式增强 (polyDim × solveCount)
    std::vector<int> activeDrivers;      // 此 SubNet 关心的 driver 索引集
    std::vector<int> poseIndices;        // 此 SubNet 训练所用的 pose logical 索引集
    std::vector<bool> isActiveLinear;    // C lite — column-rank defence 信息
    // ... 其他 per-net 训练状态 ...
};

class RBFtools : public MPxNode {
private:
    // Base 层 — 单实例 (全局)
    RBFSubNet baseNet;
    
    // Delta 层 — 按 base pose logical index 映射
    std::unordered_map<int, RBFSubNet> deltaNets;
    
    // Cache invalidation flag
    bool subnetCacheDirty;
    // ... 其他成员 ...
};
```

### 1.4 attributeAffects 链 (DG 触发)

```cpp
// 任何 schema 改动触发 evalInput dirty → 下次 compute 重训 baseNet/deltaNets
attributeAffects(poseParentIndex, output);
attributeAffects(poseDriverMask, output);
attributeAffects(poseParentIndex, evalInput);  // 显式重训触发
attributeAffects(poseDriverMask, evalInput);
```

---

## 阶段 2 — 双轨增量训练逻辑 (Training / `evalInput == true` Block)

### 2.1 拓扑解析

遍历所有 pose, 根据 `poseParentIndex` 分发到 2 组:

```cpp
std::vector<int> basePoseIndices;
std::unordered_map<int, std::vector<int>> childGroupsByParent;

for (int i = 0; i < poseCount; ++i) {
    int parent = readPoseParentIndex(i);
    if (parent < 0) {
        basePoseIndices.push_back(i);
    } else {
        // Cycle / depth guard: parent 必须也是 base
        if (readPoseParentIndex(parent) != -1) {
            displayWarning("Delta cannot point to Delta — pose " + i
                           + " demoted to Base.");
            basePoseIndices.push_back(i);
        } else {
            childGroupsByParent[parent].push_back(i);
        }
    }
}
```

### 2.2 训练 Base 层 (`baseNet`)

- 提取 `basePoseIndices` 集合
- `baseNet.activeDrivers` = `union(poseDriverMask[i] for i in basePoseIndices)` (空 mask 视为关心全 driver)
- 用 base pose 在 activeDrivers 子集上的 driver vector + 目标值, 调现有 `cholesky` / `solve` 训练 `baseNet.wMat`, `baseNet.polyMat`
- 同样跑现有 column-rank defence (C lite) + polynomial augmentation (Path B) — 这些 Phase 16 完全保留

### 2.3 训练 Delta 层 (`deltaNets[parent_id]`)

对每个 parent_id 含 children:

1. **Sibling mask 一致性约束**: 同 parent_id 下所有 children 的 `poseDriverMask` 应该一致, 否则 Planner 推荐策略:
   - 取 mask 的**并集** (`deltaNets[parent_id].activeDrivers = union(children.masks)`)
   - 若并集与某 child 自己的 mask 不等 → `displayWarning("delta mask inconsistent at parent " + parent_id)`

2. **核心数学转换 (RHS Delta)** — 关键公式:

   $$\text{Delta\_Target}_i = \text{Actual\_Pose\_Value}_i - \text{Predicted\_Base\_Value}_i$$

   其中 `Predicted_Base_Value_i` 计算方式 (**Polish 1 — 精确**):

   ```
   driver_full = read child pose's full driver vector (length = sum of all driverSource attrs)
   driver_for_base = project(driver_full, baseNet.activeDrivers)   ← 投影到 base 子集
   Predicted_Base_Value_i = inferenceWithNet(baseNet, driver_for_base)
   ```

   **不是**用 child pose 的 "全量 driver" 喂 baseNet (baseNet 不接受 driver 维度不匹配的输入). 而是 child pose driver vector 经 `baseNet.activeDrivers` 索引集投影后输入.

3. 用局部的 Delta Driver 子集 (= `deltaNets[parent_id].activeDrivers` 集) + Delta_Target, 训练 `deltaNets[parent_id].wMat`, `deltaNets[parent_id].polyMat`

### 2.4 缓存与线程安全

- `evalInput == true` 时: **允许且必须**写入 instance member `baseNet`, `deltaNets`, `subnetCacheDirty = false`
- `compute()` 推理时: **只读** instance member, 不写
- 严禁 static 共享变量 (每节点 instance 独立 cache, 不跨节点 share)
- Cache invalidation: `attributeAffects(poses, evalInput)` + `attributeAffects(poseParentIndex/poseDriverMask, evalInput)` 让 schema 改动自动触发下次 compute 重训

---

## 阶段 3 — 双轨混合推理 (Inference / `getPoseWeights`)

### 3.1 Pass 1 — Base 推理 + 收集 $\phi_i$

```
1. driver_full = current input driver vector (实时)
2. driver_for_base = project(driver_full, baseNet.activeDrivers)
3. Base_Output = inferenceWithNet(baseNet, driver_for_base)
4. 同时记录 per base pose 的 kernel value (Polish 5 — 精确):
       phi_i = phi( ||driver_for_base - baseNet.poseInputs[i]||, sigma_i, kernelType )
   注: phi_i 是 **核函数值标量**, 不是 weight w_i, 不是 w_i * phi 乘积.
```

### 3.2 Pass 2 — Delta 局部推理 + Shepard Gating

对每个 parent_id $\in$ `deltaNets.keys()`:

```
1. driver_for_delta = project(driver_full, deltaNets[parent_id].activeDrivers)
2. Delta_y_i(x) = inferenceWithNet(deltaNets[parent_id], driver_for_delta)
3. 不立刻加, 先 gating
```

**Localized Delta Aggregation (Shepard Gating)** — 防止 Delta 全局泄露:

$$\alpha_i(x) = \frac{\phi_i}{\sum_{k \in \text{base pose indices}} \phi_k}$$

**分母**: **所有 Base Pose 的 $\phi_k$ 之和** (不是所有 Pose, 也不是仅有 children 的 base pose). 这保证:
- 当 driver state 远离 parent_i 时 $\phi_i \to 0$, 因此 $\alpha_i \to 0$, 该 parent 的 delta 不泄露
- $\sum_i \alpha_i = 1$ (partition of unity) — Delta 总贡献被 normalize

### 3.3 Pass 3 — Final Blending (按 channel 类型合成)

对每个 output channel `c`:

#### Translate / Rotate (Euler) 通道 (加性):
$$y_c^{\text{final}} = y_c^{\text{base}} + \sum_{i \in \text{parents}} \alpha_i \cdot \Delta y_{i,c}$$

#### Scale 通道 (`outputIsScale[c] == true`) (乘性):
$$y_c^{\text{final}} = y_c^{\text{base}} \cdot \prod_{i \in \text{parents}} \left(1 + \alpha_i \cdot \Delta y_{i,c}^{\text{rel}}\right)$$

其中 $\Delta y_{i,c}^{\text{rel}}$ 是 Delta 训练时对应转换的**相对比例** (而非绝对差). 若实现复杂可降级:
- **Scale fallback to single-layer**: `outputIsScale[c] == true` 的 channel 暂禁用分层 (回退 Phase 15 Shepard for Scale 单层路径). 标记 `// TODO Phase 17 Scale Multiplicative Delta`

#### QWA (Quaternion) 通道 (`isQuatMember[c] == true`):
**严格禁用分层** — 李代数 $\mathfrak{so}(3)$ 对数映射与连乘复杂, 留 Phase 17:
```cpp
if (c < isQuatMember.size() && isQuatMember[c]) {
    outputs[c] = Base_Output[c];
    // TODO: Phase 17 Quaternion Delta Blending via so(3) log-exp
    continue;
}
```

---

## 阶段 4 — 钳制时机分离 (Clamp & Fallback)

### 4.1 Clamp 时机

| Clamp 类型 | 何时作用 | Phase 16 是否新增 |
|---|---|---|
| **Input Clamp** (driver-side AABB) | 进入 `baseNet` / `deltaNets[i]` 推理**之前**, 作用于输入空间 | Phase 15 已有, 本 patch 保留 |
| **Output Clamp** (driven-side, Phase 15 新增) | `Final_Output` 合成**之后**, 作用于输出空间 | Phase 15 已有, 本 patch 保留 |

**两者不冲突, 在分层架构下各自作用域不变**. brief 内任何"clamp 在 Pass 之前"的表述若指 input clamp 是对的, 指 output clamp 是错的 — 必须严格区分.

### 4.2 向后兼容性 (Numerical Equivalence)

**Polish 6 — 严格表述**: 当场景中所有 pose 的 `poseParentIndex == -1` (全 base, 无 delta):
- `deltaNets` 为空, Pass 2 / Pass 3 的 $\sum$ 项为 0
- `Final_Output == Base_Output`
- baseNet 训练数据 = 所有 pose (因为全 base), `activeDrivers` 默认全 driver
- **数学行为**: 与 Phase 15 单层求解 **Numerically Equivalent within machine epsilon** (即 `|y_new - y_old| < 1e-12 per output channel`)

注: **不声称 "100% Bit-identical"** — 新增 DG attribute + compute() 内多了 dispatch 分支必然导致 instruction sequence 不同, 但**数值精度等价**.

---

## 阶段 5 — Alignment First (执行者第一步, **Planner 批准后才写代码**)

执行者**第一回复**只输出 2 个 alignment 项, **不修任何 .cpp**:

### 5.1 架构定义 (C++ 伪代码)

`RBFtools.h` 中如何定义 `RBFSubNet` 结构 + Base / Delta 存储变量的声明. 例:

```cpp
struct RBFSubNet { ... };
class RBFtools : public MPxNode {
private:
    RBFSubNet baseNet;
    std::unordered_map<int, RBFSubNet> deltaNets;
    bool subnetCacheDirty;
    // ...
};
```

### 5.2 数学推理 (用一两句话确认理解)

回答以下 2 问:

**问 a**: Phase 3.2 中 Shepard Gating $\alpha_i = \phi_i / \sum_k \phi_k$ 的**分母 $\sum_k \phi_k$ 代表什么** — 所有 Pose 还是所有 Base Pose? (正确答案: **所有 Base Pose** — 即 baseNet 训练所用的 pose 集合)

**问 b**: 为什么 Shepard Gating 能**解决 Delta 全局泄露导致的 overshoot**? (期望答案: 当 current driver 远离 parent_i 时 $\phi_i \to 0$ → $\alpha_i \to 0$ → 该 parent 的 delta 贡献被自动归零, delta 不会在远 driver state 处"leak" 产生 spurious overshoot. partition of unity 保证总贡献 normalized.)

### 5.3 Planner 批准信号

执行者 5.1 + 5.2 输出后, **暂停**, 等待 user (或 Planner) 输入 `[Approve]` 才进入阶段 6+. 不许擅自开始写 .cpp.

---

## 阶段 6 (新增) — UI 暴露 `poseParentIndex` + `poseDriverMask`

⚠️ **Phase 8 缺陷修复 — Schema 加了但 UI 不暴露 = schema 死的**

### 6.1 Pose Grid 新增 2 列

[ui/widgets/pose_grid_editor.py](modules/RBFtools/scripts/RBFtools/ui/widgets/pose_grid_editor.py) 每个 pose row 新增:

| 列名 | 控件 | Default | 行为 |
|---|---|---|---|
| **Parent** | QComboBox | "None (-1)" | items: "None (-1)" + 所有 base pose 的 logical index. 选某 base → 此 row 变 delta pose, 自动写入 `poses[row].poseParentIndex` plug |
| **Driver Mask** | QPushButton "..." 开 popup, popup 含 multi-checkbox QListWidget | 全勾选 (= 关心所有 driver) | items: 所有 `driverSource[k].attrs` 的 flat 列表. 用户取消某 checkbox → 写入 `poses[row].poseDriverMask` int array |

### 6.2 Controller

[controller.py](modules/RBFtools/scripts/RBFtools/controller.py) 加 method:

```python
def set_pose_parent_index(self, row, parent_row):
    """Write poses[row].poseParentIndex plug.
    parent_row == -1 sets pose as base. parent_row >= 0 sets pose as
    delta with parent = parent_row's logical index."""
    if not self._current_node:
        return False
    shape = core.get_shape(self._current_node)
    plug = "{}.poses[{}].poseParentIndex".format(shape, row)
    try:
        cmds.setAttr(plug, int(parent_row))
        self.poseParentChanged.emit(row, parent_row)
        return True
    except Exception as exc:
        cmds.warning("set_pose_parent_index failed: {}".format(exc))
        return False

def set_pose_driver_mask(self, row, mask_indices):
    """Write poses[row].poseDriverMask plug (int array).
    Empty mask_indices = all drivers (default backward compat)."""
    if not self._current_node:
        return False
    shape = core.get_shape(self._current_node)
    plug = "{}.poses[{}].poseDriverMask".format(shape, row)
    try:
        cmds.setAttr(plug, len(mask_indices),
                     *mask_indices, type="Int32Array")
        self.poseDriverMaskChanged.emit(row, list(mask_indices))
        return True
    except Exception as exc:
        cmds.warning("set_pose_driver_mask failed: {}".format(exc))
        return False
```

### 6.3 Signal 连接 (main_window.py)

```python
ctrl.poseParentChanged.connect(self._refresh_pose_grid)
ctrl.poseDriverMaskChanged.connect(self._refresh_pose_grid)
```

### 6.4 i18n keys (新 6 个)

```python
"pose_col_parent": {"en": "Parent", "zh": "父姿势"},
"pose_col_parent_tip": {
    "en": "Optional parent base pose. -1 (None) = this is a base pose. "
          ">=0 = this is a delta pose layered on top of the selected "
          "base pose.",
    "zh": "可选父基础姿势. -1 (无) = 本姿势是 base. >=0 = 本姿势是 delta, "
          "叠加在所选 base 之上."
},
"pose_col_driver_mask": {"en": "Driver Mask", "zh": "驱动器掩码"},
"pose_col_driver_mask_tip": {
    "en": "Subset of driverSource[] indices this pose responds to. "
          "Empty = all drivers (default).",
    "zh": "本姿势响应的 driverSource 索引子集. 空 = 全部驱动器 (默认)."
},
"pose_driver_mask_popup_title": {
    "en": "Select Active Drivers for Pose",
    "zh": "选择本姿势的活跃驱动器"
},
"pose_layering_warning_inconsistent_mask": {
    "en": "Sibling delta poses under parent {0} have inconsistent "
          "driver masks. Using union: {1}",
    "zh": "父 {0} 下的 delta 姿势驱动器掩码不一致, 取并集: {1}"
},
```

---

## 阶段 7 — Test (Part D, 新建测试文件)

`modules/RBFtools/tests/test_m_p0_rbf_hierarchical_two_level.py`:

| # | Case | 验证 |
|---|---|---|
| 1 | `test_all_pose_parent_minus_1_numerically_equivalent` | 全部 pose parent=-1 时, output ‖y_new - y_old‖ < 1e-12 (Phase 15 baseline) |
| 2 | `test_delta_pointing_to_delta_demoted_to_base` | child→child 链, parent_index 嵌套 → 自动 demote + warn |
| 3 | `test_pose_driver_mask_oob_index_filtered` | mask 含 out-of-range index → 丢弃 + warn, 不崩溃 |
| 4 | `test_pose_driver_mask_empty_default_all` | mask = 空数组 → 视为全 driver (backward compat) |
| 5 | `test_predicted_base_value_uses_projected_driver` | child pose driver vector 投影到 baseNet.activeDrivers 后才喂 baseNet (维度匹配) |
| 6 | `test_shepard_gating_partition_of_unity` | 任意 driver state 下 $\sum_i \alpha_i = 1.0$ (within 1e-9) |
| 7 | `test_delta_doesnt_leak_at_far_driver` | 当 current driver 离 parent_i 极远 ($\phi_i < 1e-6$), output ≈ Base_Output (delta 贡献 ≈ 0) |
| 8 | `test_translate_rotate_additive_blending` | translate/rotate 通道: y = base + Σα·Δ 数值正确 |
| 9 | `test_scale_channel_uses_phase15_shepard_single_layer` | outputIsScale=true 时回退 Phase 15 单层 Shepard (本 patch 不走分层) |
| 10 | `test_quaternion_channel_returns_base_only` | isQuatMember=true 通道: outputs[c] = Base_Output[c] (Phase 17 TODO) |
| 11 | `test_sibling_delta_mask_union_when_inconsistent` | parent=3 下 2 个 children mask 不同 → 用并集 + warn |
| 12 | `test_input_clamp_applied_before_pass1` | input clamp 触发, 在 baseNet 推理之前 |
| 13 | `test_output_clamp_applied_after_final` | output clamp 触发, 在 Final blending 之后 |
| 14 | `test_user_22_pose_case_overshoot_resolved` | 复现 user multi-driver 22-pose case, 切分层后 frame 805 scaleZ 在 trained range 内 |

---

## 阶段 8 — Commit Chain (Policy B, 10 个 commit)

| # | Commit | Scope |
|---|---|---|
| 1 | `docs(planner): Phase 16 Two-Level Factored Pose Space brief` | git add brief 入 git audit-trail |
| 2 | `feat(plugin/schema): poseParentIndex + poseDriverMask sub-attributes (阶段 1)` | RBFtools.cpp/h: 2 new compound sub-attrs + attributeAffects + RBFSubNet struct |
| 3 | `feat(plugin/train): two-level training — baseNet + deltaNets with RHS delta math (阶段 2)` | training path 拓扑解析 + Base/Delta 双轨训练 + sibling mask union 一致性 |
| 4 | `feat(plugin/infer): Shepard-gated localized delta aggregation + channel blending (阶段 3)` | getPoseWeights: Pass 1/2/3 + α_i partition of unity + translate/rotate 加性 + scale 单层回退 + quaternion 禁用 |
| 5 | `chore(deploy): rebuild 2022 + 2025 .mll with hierarchical engine (Phase 16)` | cmake clean rebuild 双 SDK + 部署 + strings grep "deltaNets" / "Shepard" 验证 |
| 6 | `feat(controller): set_pose_parent_index + set_pose_driver_mask (阶段 6)` | controller.py 2 new methods + 2 signals |
| 7 | `feat(ui): pose grid 2 new columns (Parent + Driver Mask) + i18n (阶段 6)` | pose_grid_editor.py + main_window.py + i18n.py (6 keys) |
| 8 | `test: hierarchical two-level + UI + backward compat 14 cases (阶段 7)` | 新 test 文件 14 cases |
| 9 | `chore(installer): rebuild for M_P0_RBF_HIERARCHICAL_TWO_LEVEL` | installer .exe 重打 |

**Phase 5 alignment 步骤不产生 commit** — 仅是执行者回复, Planner 批准后才开始 commit 1+.

---

## 阶段 9 — 4/4 Anchors 影响

| Anchor | 影响 |
|---|---|
| TPS r≤0 oracle return-value | 0 — `interpolateRbf` 不动 |
| Honest-failure | **强化** — 4 处 warn (recursive parent / OOB mask / sibling inconsistency / quaternion fallback) |
| Column-rank defence (C lite) | 0 — 每个 SubNet 各自跑 C lite, 完全保留 |
| polyDim = 1+d for all CPD | 0 — 每个 SubNet 各自 polynomial augmentation, 完全保留 |

---

## 阶段 10 — Polish Summary (我前一轮 Review 7 处补强已整合)

| # | 补强点 | 在本 brief 哪节 |
|---|---|---|
| 1 | UI 暴露 (阶段 6 新增) | §6 完整 — pose grid 2 列 + controller + signal + 6 i18n |
| 2 | Polish 1: Predicted_Base_Value 投影到 baseNet.activeDrivers | §2.3 第 2 步显式说"投影" |
| 3 | Polish 2: poseDriverMask 默认 / OOB / 空 mask | §1.2 三类 case 明确 |
| 4 | Polish 3: Cache invalidation 触发 (attributeAffects 链) | §1.4 完整 |
| 5 | Polish 4: Sibling delta mask 一致性 (取并集 + warn) | §2.3 第 1 步 |
| 6 | Polish 5: φ_i 精确定义 (核函数值, 非 weight) | §3.1 第 4 步显式注 |
| 7 | Polish 6: "Numerically Equivalent within machine epsilon" 替代 "Bit-identical" | §4.2 完整 |

---

## 阶段 11 — Commit message 模板 (执行者照搬)

### Commit 2
```
feat(plugin/schema): poseParentIndex + poseDriverMask sub-attributes (M_P0_RBF_HIERARCHICAL_TWO_LEVEL 阶段 1)

Schema extension to enable two-level factored pose space (Base +
Delta) RBF hierarchy. Both sub-attributes added to existing `poses`
compound:

* poseParentIndex (kInt, default -1)
  -1 = base pose, >=0 = delta pose pointing to base pose's logical
  index. Depth hard-capped at 2 (recursive delta-to-delta demoted
  to base at training time with displayWarning).

* poseDriverMask (kIntArray, default empty=all drivers)
  Subset of driverSource[] indices this pose responds to. OOB
  indices filtered with displayWarning. Empty array = all drivers
  (backward compat — equivalent to legacy single-layer behavior
  numerically within machine epsilon).

New struct RBFSubNet { wMat, polyMat, activeDrivers, poseIndices,
isActiveLinear } replaces global wMat/polyMat. Class members
baseNet + deltaNets unordered_map<int, RBFSubNet>. instance-scoped,
no static (per-node cache, thread-safe across multiple RBFtools
instances).

attributeAffects chain: poseParentIndex/poseDriverMask trigger
evalInput dirty so DG auto-retraing on schema changes.

Backward compat: all poses with parent=-1 + empty mask → behavior
numerically equivalent to Phase 15 (|y_new - y_old| < 1e-12).
NOT claimed bit-identical (new DG attributes + compute dispatch
branches change instruction sequence).

Math: Functional ANOVA decomposition basis (Hoeffding 1948).
Anchors held: 4/4. Honest-failure strengthened (4 warn paths).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

### Commit 3
```
feat(plugin/train): two-level training — baseNet + deltaNets with RHS delta math (M_P0_RBF_HIERARCHICAL_TWO_LEVEL 阶段 2)

evalInput == true block now performs topology parsing + two-tier
training:

1. Collect base pose indices (parent_index == -1) → train baseNet
   using union(poseDriverMask) as activeDrivers. Existing cholesky/
   solve + column-rank defence + polynomial augmentation retained
   per SubNet.

2. For each parent_id with children, train deltaNets[parent_id]:
   * Sibling driver mask consistency check — non-matching masks
     resolved by union + displayWarning.
   * RHS delta math: Delta_Target_i = Actual_i - Predicted_Base_i
     where Predicted_Base_i = inferenceWithNet(baseNet,
     project(child_driver_vector, baseNet.activeDrivers)).
   * Child driver projected onto baseNet's active subset before
     base inference — avoids dim mismatch when delta uses different
     driver subset than base.

Cache: instance member write only during evalInput==true;
compute() inference path read-only.

Math: f(x_1,x_2) = f_base(x_1) + Σ α_i Δf_i(x_2|parent_i)
following Functional ANOVA + Combo BlendShape practice.

Anchors held: 4/4 (each SubNet runs its own C lite + Path B).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

### Commit 4
```
feat(plugin/infer): Shepard-gated localized delta aggregation + channel blending (M_P0_RBF_HIERARCHICAL_TWO_LEVEL 阶段 3)

getPoseWeights now implements three-pass inference:

Pass 1 — Base inference:
   driver_for_base = project(driver_full, baseNet.activeDrivers)
   Base_Output = inferenceWithNet(baseNet, driver_for_base)
   For each base pose i record phi_i = phi(||x - x_i||) scalar
   (NOT weight w_i, NOT w_i*phi product).

Pass 2 — Delta inference + Shepard gating:
   For each parent_id with children:
     driver_for_delta = project(driver_full,
                                deltaNets[parent_id].activeDrivers)
     Delta_y_i = inferenceWithNet(deltaNets[parent_id],
                                  driver_for_delta)
   Compute alpha_i = phi_i / sum_k(phi_k for k in all base poses)
   — partition of unity. Far driver states have phi_i->0 hence
   alpha_i->0, delta does not leak (anti-overshoot guarantee).

Pass 3 — Channel-specific blending:
   * Translate/Rotate (Euler): additive y = base + Σ alpha_i Δy_i
   * Scale (outputIsScale[c]==true): single-layer fallback to
     Phase 15 Shepard. TODO Phase 17 multiplicative delta.
   * Quaternion (isQuatMember[c]==true): outputs[c] = Base_Output[c]
     only. TODO Phase 17 so(3) log-exp delta blending.

Input clamp applied per-net BEFORE Pass 1/2. Output clamp
(Phase 15) applied AFTER Pass 3 Final_Output. Both clamp routes
preserved.

Math: Shepard 1968 (partition of unity normalization) +
ANOVA additive decomposition.

Anchors held: 4/4 (TPS r<=0, honest-failure strengthened with
4 displayWarning paths, column-rank in each SubNet, polyDim 1+d
per SubNet).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

(Commit 5/6/7/8/9 message 见 brief §8 commit chain, 执行者依模板写)

---

## 阶段 12 — 验证

### 12.1 静态 (执行者本地)

```bash
cd X:/Plugins/RBFtools

python -m pytest modules/RBFtools/tests/test_m_p0_rbf_hierarchical_two_level.py -v
# 期望: 14 passed

python -m pytest modules/RBFtools/tests --continue-on-collection-errors -q
# 期望: 634 (Phase 15 baseline) + 14 = 648, 0 回归

# .mll embedded strings 验证
strings modules/RBFtools/plug-ins/win64/2022/RBFtools.mll | grep -E "deltaNets|Shepard|HIERARCHICAL" | sort -u
strings modules/RBFtools/plug-ins/win64/2025/RBFtools.mll | grep -E "deltaNets|Shepard|HIERARCHICAL" | sort -u
# 期望: 两个 .mll 都含 hierarchical patch 字符串
```

### 12.2 用户实测

**场景 A — Backward compat (无任何 Parent 设置)**:
1. 打开任意旧版 .ma 场景
2. **期望**: 所有 pose Parent 列显示 "None (-1)", Driver Mask 列显示"全选"
3. 切 kernel / Apply → 行为与 Phase 15 一致

**场景 B — 2 driver 分层 (user 原报告 case)**:
1. 节点已 add 2 drivers: Elbow + Wrist
2. 创建 3 base poses (仅 elbow 变化): rest / bend30 / bend60
3. 创建 6 delta poses (在 bend30 + bend60 下各 wrist 取 3 值): 设这些 pose 的 Parent = 对应 base pose row + Driver Mask 取消 Elbow
4. Apply → 期望训练成功, 无 ill-condition warning
5. 切 Wrist 旋转, 观察 driven mesh — Wrist delta 仅在 elbow 接近 trained base pose 时生效, 远离 elbow trained range 时 Wrist delta 自动衰减
6. 验证 overshoot: 测过去会 overshoot 的 frame, scale/rotation 在 trained range 内

**场景 C — Sibling mask 不一致 warning**:
1. 在 parent=3 下创建 2 个 delta children
2. child A Driver Mask 选 [Wrist], child B 选 [Wrist, Elbow]
3. Apply → Script Editor warn "sibling delta poses under parent 3 have inconsistent driver masks. Using union: [Wrist, Elbow]"

**场景 D — Quaternion 通道 Phase 17 TODO 验证**:
1. 节点 output 含 quaternion group
2. 加 delta pose 配置
3. Apply → 该 quaternion 通道 inference 输出 = Base_Output (delta 不应用)
4. Script Editor 见 "Phase 17 TODO" trace

---

## 阶段 13 — 关键路径速查

| 文件 | 操作 |
|---|---|
| [source/RBFtools.h](source/RBFtools.h) | RBFSubNet struct + baseNet + deltaNets + 2 new MObject (Phase 1/2) |
| [source/RBFtools.cpp](source/RBFtools.cpp) | attribute init + topology parsing + two-tier training + three-pass inference + clamp 时机分离 (Phase 1/2/3/4) |
| [modules/RBFtools/scripts/RBFtools/controller.py](modules/RBFtools/scripts/RBFtools/controller.py) | set_pose_parent_index + set_pose_driver_mask + 2 signals (Phase 6.2) |
| [modules/RBFtools/scripts/RBFtools/ui/widgets/pose_grid_editor.py](modules/RBFtools/scripts/RBFtools/ui/widgets/pose_grid_editor.py) | 2 new columns (Parent QComboBox + Driver Mask popup) (Phase 6.1) |
| [modules/RBFtools/scripts/RBFtools/ui/main_window.py](modules/RBFtools/scripts/RBFtools/ui/main_window.py) | signal hooks → grid refresh (Phase 6.3) |
| [modules/RBFtools/scripts/RBFtools/ui/i18n.py](modules/RBFtools/scripts/RBFtools/ui/i18n.py) | 6 new keys (Phase 6.4) |
| `modules/RBFtools/tests/test_m_p0_rbf_hierarchical_two_level.py` | 14 unit cases (Phase 7) |
| `modules/RBFtools/plug-ins/win64/{2022,2025}/RBFtools.mll` | 双 SDK rebuild |
| `installer/RBFtoolsInstaller.exe` | 重打 |
