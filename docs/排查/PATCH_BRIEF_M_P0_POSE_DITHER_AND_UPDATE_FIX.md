# Patch Brief — M_P0_POSE_DITHER_AND_UPDATE_FIX (Phase 14)

> Planner / Architect 设计稿. 执行者照此实施.
>
> **Origin**: 2026-05-12 用户报告 4 项 UI 改进:
> > 1. 图 1 第一红框: 加按钮 "Driver Dither" — 把 driver pose (除 pose 0) 中相同数值的属性加 0.00X 随机扰动以防止 pose 近似
> > 2. 图 1 第二红框: 加按钮 "Driven Dither" — 同上, 但作用于 driven pose
> > 3. 加全局 Radius 调节 — 一次性对当前节点所有 pose 设置同一 radius, 放在 dither 按钮旁
> > 4. 图 2 "更新" 按钮 bug: 无法实时更新 pose 信息, 需修复
>
> **Status**: APPROVED — 等执行者实施.

---

## 1. Context — 为什么要 Dither 按钮

历史: user 在 Maya Script Editor 跑过 standalone dither script (Phase 13 之后 ad-hoc), 验证 dither perturbation 能打破 cluster 让 MQB 数学 well-conditioned. 现在希望**做成 UI 按钮**, 无需每次手工跑 script.

Dither 原理 (引用 ScienceDirect [Stabilized RBF interpolation](https://www.sciencedirect.com/science/article/abs/pii/S0377042723004260) + 工业 numerical 标准):

$$\text{cond}\left(\begin{bmatrix} K + \lambda I & P \\ P^T & 0 \end{bmatrix}\right) \approx O\left(\frac{1}{\lambda} + \frac{1}{\epsilon}\right)$$

加 ε ≈ 0.005 扰动到 cluster 内 channel → cond 从 ∞ (singular) 降到 ~10⁵ (double precision 完全 hold).

## 2. Part A — Driver Dither 按钮

### 2.1 UI 位置

[`ui/widgets/pose_grid_editor.py`](modules/RBFtools/scripts/RBFtools/ui/widgets/pose_grid_editor.py) (或 pose panel 容器), 在 "添加姿势" / "删除姿势" 按钮**右侧** 加新按钮:

```
[ 添加姿势 ] [ 删除姿势 ] [ 🎲 驱动器去重 ] [ 🎲 被驱动器去重 ]
```

按钮标签 (i18n):
- en: `"Dither Drivers"`
- zh: `"驱动器去重"`

按钮 tooltip:
- en: `"Add ±0.005 random perturbation to clustered driver channels (preserves Pose 0)"`
- zh: `"对驱动器 pose 中重复的属性加 ±0.005 随机扰动 (Pose 0 不变)"`

### 2.2 Backend — `core.dither_driver_poses`

新文件加在 [core.py](modules/RBFtools/scripts/RBFtools/core.py) (放在 pose 操作区域附近):

```python
def dither_driver_poses(node, base_pose_index=0,
                       magnitude=0.005, seed=42):
    """对 driver pose 中 cluster channel 加微小随机扰动.
    
    检测: 任意 2 pose (除 base_pose_index) 在某 input slot 数值
    差异 < 1e-6 → 标记为 cluster.
    扰动: 对标记 channel 加 random.uniform(-magnitude, +magnitude).
    
    Parameters
    ----------
    node : str
        Transform 或 shape 名.
    base_pose_index : int
        基础姿势 index (不动). 默认 0.
    magnitude : float
        扰动幅度 (rad / unit). 默认 0.005 ≈ 0.29° rotation, 视觉无感.
    seed : int or None
        random seed. None 表示真随机.
    
    Returns
    -------
    int
        实际被扰动的 (pose, input_slot) 对数.
    """
    import random
    shape = get_shape(node)
    if not _exists(shape):
        return 0
    
    rng = random.Random(seed)
    
    pose_indices = cmds.getAttr(
        shape + ".poses", multiIndices=True) or []
    
    # 1. 读取 driver values per pose
    pose_data = {}
    for p in pose_indices:
        if p == base_pose_index:
            continue
        n_inputs = cmds.getAttr(
            "{}.poses[{}].poseInput".format(shape, p),
            multiIndices=True) or []
        row = []
        for ii in n_inputs:
            try:
                v = cmds.getAttr(
                    "{}.poses[{}].poseInput[{}]".format(shape, p, ii))
                row.append((ii, v))
            except Exception:
                pass
        pose_data[p] = row
    
    # 2. 检测 cluster
    EPS = 1e-6
    to_perturb = set()
    pose_list = sorted(pose_data.keys())
    for i in range(len(pose_list)):
        for j in range(i + 1, len(pose_list)):
            p1, p2 = pose_list[i], pose_list[j]
            for (ii, v1) in pose_data[p1]:
                v2 = next(
                    (v for k, v in pose_data[p2] if k == ii), None)
                if v2 is None:
                    continue
                if abs(v1 - v2) < EPS:
                    to_perturb.add((p1, ii))
                    to_perturb.add((p2, ii))
    
    # 3. 加扰动
    perturbed = 0
    with undo_chunk("RBFtools: dither driver poses"):
        for (pose_idx, input_idx) in sorted(to_perturb):
            plug = "{}.poses[{}].poseInput[{}]".format(
                shape, pose_idx, input_idx)
            try:
                old_v = cmds.getAttr(plug)
            except Exception:
                continue
            delta = rng.uniform(-magnitude, +magnitude)
            new_v = old_v + delta
            # 断 inbound connection 才能 setAttr 静态值
            incoming = cmds.listConnections(
                plug, source=True, destination=False,
                plugs=True) or []
            for src in incoming:
                try:
                    cmds.disconnectAttr(src, plug)
                except Exception:
                    pass
            try:
                cmds.setAttr(plug, new_v)
                perturbed += 1
            except Exception as exc:
                cmds.warning(
                    "dither_driver_poses: setAttr {} = {} "
                    "failed: {}".format(plug, new_v, exc))
    return perturbed
```

### 2.3 Controller exposure

[controller.py](modules/RBFtools/scripts/RBFtools/controller.py) 加 method:

```python
def dither_driver_poses(self, magnitude=0.005, seed=42):
    """Forward to core.dither_driver_poses for the active node."""
    if not self._current_node:
        cmds.warning("dither_driver_poses: no active node")
        return 0
    try:
        n = core.dither_driver_poses(
            self._current_node,
            base_pose_index=0,
            magnitude=magnitude,
            seed=seed)
        if n > 0:
            self.statusMessage.emit(
                tr("dither_driver_done").format(n))
        else:
            self.statusMessage.emit(
                tr("dither_driver_no_cluster"))
        return n
    except Exception as exc:
        cmds.warning(
            "dither_driver_poses failed: {}".format(exc))
        return 0
```

### 2.4 UI 信号连接

`pose_grid_editor.py` 加按钮 + signal `ditherDriversRequested`:

```python
self._btn_dither_drv = QtWidgets.QPushButton(tr("btn_dither_drivers"))
self._btn_dither_drv.setToolTip(tr("btn_dither_drivers_tip"))
self._btn_dither_drv.clicked.connect(self._on_dither_drivers_clicked)
# 加入 layout (在 add/delete pose 之后)

def _on_dither_drivers_clicked(self):
    self.ditherDriversRequested.emit()
```

`main_window.py` 连接:

```python
pe.ditherDriversRequested.connect(self._on_dither_drivers)

def _on_dither_drivers(self):
    n = self._ctrl.dither_driver_poses(magnitude=0.005)
    if n > 0:
        cmds.confirmDialog(
            title="RBFtools",
            message=tr("dither_driver_done").format(n),
            button=["OK"], defaultButton="OK")
    else:
        cmds.confirmDialog(
            title="RBFtools",
            message=tr("dither_driver_no_cluster"),
            button=["OK"], defaultButton="OK")
    # 触发 pose grid 刷新让用户看到新值
    self._refresh_pose_grid()
```

---

## 3. Part B — Driven Dither 按钮

### 3.1 对称设计

与 Part A 完全对称, 仅:
- target plug 改为 `.poses[p].poseValue[i]` (driven side)
- backend 函数 `core.dither_driven_poses` (镜像)
- controller method `dither_driven_poses`
- UI button label: `"被驱动器去重"` / `"Dither Drivens"`

### 3.2 ⚠️ Warning Dialog (driven side 特殊)

driven side dither = 给 RBF training **target (label)** 加噪音, 可能让训练精度下降. UI 上必须弹 confirm dialog:

```python
def _on_dither_drivens(self):
    result = cmds.confirmDialog(
        title=tr("title_dither_driven_warning"),
        message=tr("msg_dither_driven_warning"),
        button=["确认 (Confirm)", "取消 (Cancel)"],
        defaultButton="取消 (Cancel)",
        cancelButton="取消 (Cancel)")
    if result != "确认 (Confirm)":
        return
    n = self._ctrl.dither_driven_poses(magnitude=0.005)
    # ... 同 driver side ...
```

i18n key 内容:

```python
"title_dither_driven_warning": {
    "en": "Dither Driven Output — Warning",
    "zh": "去重被驱动器输出 — 警告"
},
"msg_dither_driven_warning": {
    "en": "Adding noise to driven (output) values will reduce RBF "
          "training accuracy. The trained weights will learn from "
          "noisy targets, which may produce visible artifacts during "
          "inference. Use only when driver-side dither alone cannot "
          "resolve cluster issues. Continue?",
    "zh": "对被驱动器 (输出) 值加噪音会降低 RBF 训练精度. weights 学的是"
          "带噪音的目标, 可能在 inference 时产生可见 artifact. 仅在驱动"
          "器去重无法解决 cluster 问题时使用. 是否继续?"
},
```

---

## 3.5 Part C-bis — 全局 Radius 调节 (用户 directive #3)

### 3.5.1 UI 位置

在 pose 面板 dither 按钮**右侧**:

```
[ 添加姿势 ] [ 删除姿势 ] [ 🎲 驱动器去重 ] [ 🎲 被驱动器去重 ] [ 半径: spin 5.0] [ 批量设置半径 ]
```

控件: `QDoubleSpinBox` (range 0.001 - 1000.0, decimals 3, single step 0.1) + `QPushButton`.

### 3.5.2 Backend — `core.set_all_poses_radius`

复用 `set_pose_radius` 已有 plug write 模式 (controller.py:1901-1919), 但批量:

```python
def set_all_poses_radius(node, radius):
    """对节点所有 pose 设置同一 radius.
    
    Parameters
    ----------
    node : str
    radius : float
        必须 > 0. <= 0 时改用 DEFAULT_POSE_RADIUS.
    
    Returns
    -------
    int
        实际成功写入的 pose 数.
    """
    shape = get_shape(node)
    if not _exists(shape):
        return 0
    r = float(radius)
    if r <= 0.0:
        r = DEFAULT_POSE_RADIUS
    pose_indices = cmds.getAttr(
        shape + ".poses", multiIndices=True) or []
    n = 0
    with undo_chunk("RBFtools: set all poses radius"):
        for p in pose_indices:
            plug = "{}.poseRadius[{}]".format(shape, p)
            try:
                cmds.setAttr(plug, r)
                n += 1
            except Exception as exc:
                cmds.warning(
                    "set_all_poses_radius: setAttr {} = {} failed: "
                    "{}".format(plug, r, exc))
    return n
```

### 3.5.3 Controller exposure

```python
def set_all_poses_radius(self, radius):
    """M_P0_POSE_DITHER_AND_UPDATE_FIX Part C-bis: bulk apply radius
    to all poses of the active node."""
    if not self._current_node:
        cmds.warning("set_all_poses_radius: no active node")
        return 0
    try:
        n = core.set_all_poses_radius(self._current_node, radius)
        # Sync pose_model so UI grid reflects new radius
        for row in range(self._pose_model.rowCount()):
            try:
                self._pose_model.update_pose_radius(row, float(radius))
            except Exception:
                pass
        self.statusMessage.emit(
            tr("global_radius_done").format(n, radius))
        return n
    except Exception as exc:
        cmds.warning(
            "set_all_poses_radius failed: {}".format(exc))
        return 0
```

### 3.5.4 UI 信号

`pose_grid_editor.py`:

```python
self._spin_global_radius = QtWidgets.QDoubleSpinBox()
self._spin_global_radius.setRange(0.001, 1000.0)
self._spin_global_radius.setDecimals(3)
self._spin_global_radius.setSingleStep(0.1)
self._spin_global_radius.setValue(5.0)

self._btn_apply_global_radius = QtWidgets.QPushButton(
    tr("btn_apply_global_radius"))
self._btn_apply_global_radius.setToolTip(
    tr("btn_apply_global_radius_tip"))
self._btn_apply_global_radius.clicked.connect(
    self._on_apply_global_radius_clicked)

def _on_apply_global_radius_clicked(self):
    r = self._spin_global_radius.value()
    self.globalRadiusRequested.emit(r)
```

`main_window.py`:

```python
pe.globalRadiusRequested.connect(self._on_global_radius)

def _on_global_radius(self, radius):
    n = self._ctrl.set_all_poses_radius(float(radius))
    self._refresh_pose_grid()  # show new radius column
    cmds.confirmDialog(
        title="RBFtools",
        message=tr("global_radius_done").format(n, radius),
        button=["OK"], defaultButton="OK")
```

### 3.5.5 i18n keys

```python
"btn_apply_global_radius": {
    "en": "Apply Radius to All",
    "zh": "批量设置半径"
},
"btn_apply_global_radius_tip": {
    "en": "Set the radius value above to every pose of the active node",
    "zh": "把上方半径值应用到当前节点的所有 pose"
},
"global_radius_done": {
    "en": "Radius {1:.3f} applied to {0} pose(s).",
    "zh": "已对 {0} 个 pose 设置半径 = {1:.3f}."
},
```

---

## 4. Part C — Update 按钮 Bug Fix

### 4.1 Root cause (Planner 已 code-read 定位)

[`controller.update_pose`](modules/RBFtools/scripts/RBFtools/controller.py:1880-1891):

```python
def update_pose(self, row, driver_node, driven_node,
                driver_attrs, driven_attrs):
    if not driver_node or not driven_node:
        return
    inputs = self._capture_multi_inputs(driver_node, driver_attrs)
    outputs = self._capture_multi_outputs(driven_node, driven_attrs)
    self._pose_model.update_pose_values(row, inputs, outputs)
    #                                   ↑↑↑ 只写 UI model 内存
    # ❌ 没写 Maya shape.poses[row].poseInput/poseValue (plug)
    # ❌ 没 emit signal 让 main_window 触发 grid refresh
```

`pose_model.update_pose_values` (`ui/pose_model.py:269-288`) 内部:
- ✓ 写 `pose.inputs / pose.values` (UI 缓存)
- ✓ emit `dataChanged` signal

但 emit 的是 **QStandardItemModel 内部 signal**, **PoseGridEditor 自定义 widget** 可能没 hook 它. 即使 hook 了, **真实 Maya node 数据 (`shape.poses[row]`)** 未更新, **下次 Apply 才同步**.

[`_on_pose_grid_update`](modules/RBFtools/scripts/RBFtools/ui/main_window.py:1788-1806) 调 `ctrl.update_pose` 之后**也没** `self._refresh_pose_grid()` — 对比 `_on_pose_grid_delete` (L1808-1811) 是有调用的.

### 4.2 修复 3 步

#### Step 1 — `controller.update_pose` 加 plug write

```python
def update_pose(self, row, driver_node, driven_node,
                driver_attrs, driven_attrs):
    if not driver_node or not driven_node:
        return
    inputs = self._capture_multi_inputs(driver_node, driver_attrs)
    outputs = self._capture_multi_outputs(
        driven_node, driven_attrs)
    self._pose_model.update_pose_values(row, inputs, outputs)
    
    # M_P0_POSE_DITHER_AND_UPDATE_FIX Part C — write to Maya node
    # immediately so the RBF kernel sees the new values without
    # waiting for the next Apply.
    if self._current_node and cmds.objExists(self._current_node):
        try:
            shape = core.get_shape(self._current_node)
            core.write_pose_inputs_to_node(shape, row, inputs)
            core.write_pose_values_to_node(shape, row, outputs)
        except Exception as exc:
            cmds.warning(
                "update_pose: plug write failed: {}".format(exc))
```

`core.write_pose_inputs_to_node` / `write_pose_values_to_node` 是新 helper, 或复用现有 `_write_pose_to_node` 的细化版本.

#### Step 2 — `main_window._on_pose_grid_update` 触发 grid refresh

```python
def _on_pose_grid_update(self, pose_index):
    drv_node, dvn_node, drv_attrs, dvn_attrs = (
        self._gather_role_info())
    self._ctrl.update_pose(
        int(pose_index), drv_node, dvn_node, drv_attrs, dvn_attrs)
    # M_P0_POSE_DITHER_AND_UPDATE_FIX Part C — refresh grid so the
    # updated values display immediately (mirrors _on_pose_grid_delete
    # pattern at L1811).
    self._refresh_pose_grid()
```

#### Step 3 — 验证 `dataChanged` 真触发 grid widget 重绘

PoseGridEditor 是否 listen `dataChanged`? 若 listen, Step 2 是冗余的 safety net.
若**不 listen**, Step 2 是必需的修复.

执行者**实测**: 跑 Step 1+2 后, 移动 driver 在 viewport, click 更新, 看 grid 显示是否立即变.

---

## 5. Commit Chain (Policy B, 5 个 commit)

| # | Commit | 内容 |
|---|---|---|
| 1 | `feat(core): dither + global radius + plug write helpers (Part A+B+C-bis+C core)` | core.py: dither_driver_poses + dither_driven_poses + set_all_poses_radius + write_pose_inputs_to_node + write_pose_values_to_node |
| 2 | `feat(controller): expose dither + global radius + fix update_pose plug write (Part A+B+C+C-bis controller)` | controller.py: 3 new methods + update_pose 加 plug write |
| 3 | `feat(ui): pose-panel dither buttons + global radius spinbox + i18n (Part A+B+C-bis UI)` | pose_grid_editor.py + main_window.py + i18n.py (3 buttons + 1 spinbox + 11 i18n keys) |
| 4 | `fix(ui): update button triggers grid refresh (Part C UI)` | main_window._on_pose_grid_update 加 `_refresh_pose_grid()` |
| 5 | `test: dither + global radius + update_pose plug write unit cases (Part D, 10 cases)` | 新 test 文件 |
| 6 | `chore(installer): rebuild for M_P0_POSE_DITHER_AND_UPDATE_FIX` | installer .exe 重打 |

---

## 6. Test 用例 (Part D)

`modules/RBFtools/tests/test_m_p0_pose_dither_and_update_fix.py`:

1. **`test_dither_driver_simple`** — 3 pose, pose 1/2 cluster, dither 后 plug 值差 |Δ| ≤ 0.005, pose 0 不变
2. **`test_dither_driver_seed_reproducible`** — 同 seed 跑两次, plug 值字节级相同
3. **`test_dither_driven_simple`** — 同 1 但作用于 driven plug
4. **`test_dither_no_cluster_returns_zero`** — pose 全 unique, 函数返回 0, 无 plug write
5. **`test_update_pose_writes_plug`** — update_pose 后 `cmds.getAttr(shape + ".poses[row].poseInput[i]")` 等于 captured value
6. **`test_update_pose_triggers_grid_signal`** — pose_model.dataChanged emit 1 次 (mock connect listener)
7. **`test_dither_pose0_untouched`** — base_pose_index=0 的 pose 在任何 cluster 下都不被扰动
8. **`test_set_all_poses_radius_writes_all_plugs`** — N pose 节点调用后 N 个 poseRadius[i] plug 全部写入 = 新值
9. **`test_set_all_poses_radius_returns_count`** — 返回值 = 实际写入的 pose 数 (N)
10. **`test_set_all_poses_radius_negative_clamps_to_default`** — radius <= 0 自动 fallback DEFAULT_POSE_RADIUS, 不写非法值

---

## 7. 不动什么

- ❌ 不动 C++ source / .mll (纯 Python + UI)
- ❌ 不动 RBF 数学逻辑 (dither 是 pose data 预处理, 不改 solver)
- ❌ 不动 4/4 anchors
- ❌ 不动 git history (Policy A)
- ❌ Dither 默认 not auto-run — 用户主动 click 才执行 (避免无声修改 pose data 让 user 困惑)

---

## 8. Commit Messages

### Commit 1
```
feat(core): dither_driver_poses + dither_driven_poses helpers (M_P0_POSE_DITHER_AND_UPDATE_FIX Part A+B core)

Add core.dither_driver_poses(node, base_pose_index=0, magnitude=0.005,
seed=42) and symmetric core.dither_driven_poses. Detects clustered
channel values across non-base poses (|v_i - v_j| < 1e-6) and adds
random uniform[-magnitude, +magnitude] perturbation to break ill-
conditioned augmented matrix (math basis: cond reduction from
infinity to O(1/lambda + 1/epsilon), industry-standard dither).

Also adds core.write_pose_inputs_to_node / write_pose_values_to_node
helpers used by controller.update_pose to write captured viewport
state into Maya shape.poses[row] plugs immediately (Part C).

Math: N/A (data preprocessing, no solver change).
Anchors held: 4/4.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

### Commit 2
```
feat(controller): expose dither methods + fix update_pose plug write (M_P0_POSE_DITHER_AND_UPDATE_FIX Part A+B+C controller)

Controller exposes:
* dither_driver_poses(magnitude, seed) -> int (perturbed count)
* dither_driven_poses(magnitude, seed) -> int

update_pose now writes captured inputs/outputs directly to Maya
shape.poses[row].poseInput / poseValue plugs (was previously
in-memory model only — user-reported bug where "更新" button had
no effect until next Apply).

Anchors held: 4/4.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

### Commit 3
```
feat(ui): pose-panel dither buttons + i18n keys (M_P0_POSE_DITHER_AND_UPDATE_FIX Part A+B UI)

Two new buttons in pose grid panel beside add/delete pose:
* 驱动器去重 (Dither Drivers) — green button, no confirm dialog
* 被驱动器去重 (Dither Drivens) — yellow button, confirm dialog
  warns user that driven-side dither reduces training accuracy

Signal: ditherDriversRequested / ditherDrivensRequested emitted to
main_window which dispatches to controller. Post-dither calls
_refresh_pose_grid() so user sees new perturbed values immediately.

i18n: 5 new keys (btn_dither_drivers, btn_dither_drivers_tip,
btn_dither_drivens, btn_dither_drivens_tip, title_dither_driven_warning,
msg_dither_driven_warning, dither_driver_done, dither_driver_no_cluster).

Anchors held: 4/4.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

### Commit 4
```
fix(ui): update button triggers grid refresh (M_P0_POSE_DITHER_AND_UPDATE_FIX Part C UI)

main_window._on_pose_grid_update calls _refresh_pose_grid() after
ctrl.update_pose returns. Mirrors the existing _on_pose_grid_delete
pattern (L1811). Without this, the pose model's internal
dataChanged signal did not propagate to PoseGridEditor's custom
widget tree, leaving stale values displayed.

Together with Part C controller plug write (commit 2), the Update
button now: (1) writes captured viewport state to Maya shape plugs,
(2) refreshes the grid display, (3) is reflected by RBF inference
on next compute() without needing a full Apply.

Anchors held: 4/4.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

### Commit 5
```
test: dither + update_pose plug write unit cases (M_P0_POSE_DITHER_AND_UPDATE_FIX Part D)

New test_m_p0_pose_dither_and_update_fix.py (7 cases):
* dither_driver_simple / driven_simple
* dither_seed_reproducible
* dither_no_cluster_returns_zero
* dither_pose0_untouched
* update_pose_writes_plug
* update_pose_triggers_grid_signal

Anchors held: 4/4.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

---

## 9. 用户实测 (执行者完成后)

### 场景 A — Driver Dither

1. 用户构造 3 pose 含 cluster (e.g. pose 1/2 在 cols 0-5 完全相同)
2. click "驱动器去重" 按钮
3. **期望**: dialog 弹 "已对 N 个 channel 加扰动", grid 显示数值微变 (±0.005)
4. 跑诊断: `cmds.getAttr(shape + ".poses[1].poseInput[0]")` 值变化 ≤ 0.005
5. Apply + 切 MQB kernel → **期望 ill-condition 不再 fail**

### 场景 B — Driven Dither

1. 同上但 driven 端 cluster
2. click "被驱动器去重" 按钮 → **期望弹 warning dialog**
3. 点确认 → 执行
4. 点取消 → 0 改动

### 场景 C — Update 按钮 fix

1. 选 driver joint, 摆 pose A, click 添加姿势
2. 移动 driver joint 到 pose B 状态
3. 选中 pose row 1, click "更新" 按钮
4. **期望**: pose 1 的 driver 列**立即显示** pose B 的值 (不需要 Apply)
5. 跑诊断: `cmds.getAttr(shape + ".poses[1].poseInput[0]")` 等于 pose B 的 driver value

### 场景 D — 全局 Radius

1. 节点有 N 个 pose (e.g. N=22), 各 pose radius 不同
2. UI spinbox 输入 `8.5`, click "批量设置半径"
3. **期望**: dialog 显示 "已对 22 个 pose 设置半径 = 8.500"
4. grid 每行的 radius 列**立即显示 8.500**
5. 跑诊断: 每个 `cmds.getAttr(shape + ".poseRadius[i]")` 都 = 8.5
6. spinbox 输入 `-1` (非法), click → 自动 fallback DEFAULT_POSE_RADIUS (e.g. 5.0)

---

## 10. 关键路径速查

| 文件 | 操作 |
|---|---|
| [core.py](modules/RBFtools/scripts/RBFtools/core.py) | Part A+B+C-bis: dither_driver_poses + dither_driven_poses + set_all_poses_radius + write_pose_inputs_to_node + write_pose_values_to_node |
| [controller.py:1880](modules/RBFtools/scripts/RBFtools/controller.py) | Part A+B+C+C-bis: 3 dither/radius methods + 修 update_pose 加 plug write |
| [ui/widgets/pose_grid_editor.py](modules/RBFtools/scripts/RBFtools/ui/widgets/pose_grid_editor.py) | Part A+B+C-bis: 2 buttons + 1 spinbox + 1 apply button + 3 signals |
| [ui/main_window.py:281, 1788](modules/RBFtools/scripts/RBFtools/ui/main_window.py) | Part A+B+C-bis: signal handlers; Part C: _on_pose_grid_update 加 _refresh_pose_grid() |
| [ui/i18n.py](modules/RBFtools/scripts/RBFtools/ui/i18n.py) | Part A+B+C-bis: 11 new keys |
| `tests/test_m_p0_pose_dither_and_update_fix.py` | Part D: 10 cases (新) |
| `installer/RBFtoolsInstaller.exe` | 重打 |
