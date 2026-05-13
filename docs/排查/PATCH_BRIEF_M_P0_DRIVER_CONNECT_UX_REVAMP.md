# Patch Brief — M_P0_DRIVER_CONNECT_UX_REVAMP (Phase 13)

> Planner / Architect 设计稿. 执行者照此实施.
>
> **Origin**: 2026-05-12 用户排查 `RBFnode_shoulder_LShape` 时发现 driver source metadata 与 input[] wiring 不一致 — driverSource[1/2] metadata 显示 3 attr 但 input[] 只 wire 1 个 attr per driver. 用户多次重试"连接"按钮后体验到"切换 tab 连接覆盖了前面 driver". Planner 代码阅读定位到 [core.py:1845-1852](modules/RBFtools/scripts/RBFtools/core.py) silent connectAttr failure 是 root cause.
>
> **User directive (原话)**:
> > 1. 每个 driver 标签页都需要有连接状态指示灯 (红灯为未连接, 绿灯为已连接)
> > 2. 当不是批量进行连接时, 在每一个 driver 标签页下点击连接时需要将当前标签页的 driver 根据所选属性与 rbf 节点进行连接, 切换标签页连接后面的 driver 时不许覆盖连接信息
> > 3. 多 driver tab 累计连接时, 需要根据各个 driver 的所选属性以及连接指示灯的状态来拾取, 不要出现重复累计的情况
>
> **Status**: APPROVED — 等执行者实施.

---

## 1. 问题定义

### 1.1 当前 Bug 链 (Planner 已 code-read 验证)

[`set_driver_source_attrs`](modules/RBFtools/scripts/RBFtools/core.py) (core.py:1747-1902) 5 step 流程:

| Step | 操作 | Bug |
|---|---|---|
| 1 | `_disconnect_or_purge` source[index..end] 所有 input wire | OK |
| 2 | `cmds.connectAttr` re-wire source[index] new_attrs | ⚠️ **silent failure** — 失败仅 `cmds.warning`, 不 raise / 不 rollback |
| 3 | `cmds.setAttr(driverSource_attrs, ...)` 写 metadata | 即使 Step 2 部分失败仍执行 — **metadata 与 wire 漂移** |
| 4 | re-wire source[i > index] with **existing attrs** | OK 但同样 silent failure |
| 5 | `_sweep_empty_subscripts` 清理 | OK |

**结果**: Step 2 中 connectAttr 失败 (e.g. `_node_state_frozen` 期间 DG transition 异常 / unitConversion 残留竞争) → metadata 写 3 attr, input[] 只 wire 1 attr.

后续 set_driver_source_attrs 再调用时, **`base = sum(len(s.attrs) for s in sources[:index])` 用错误 metadata 算 base offset**, 越改越偏.

### 1.2 用户体验症状

```
切 Driver 1 tab → highlight 3 attr → click "连接"
   → set_driver_source_attrs(1, [X,Y,Z])
   → Step 2 connectAttr 失败 (silent)
   → metadata: [X,Y,Z], wire: [X 只 1 个]

切 Driver 2 tab → highlight 3 attr → click "连接"
   → set_driver_source_attrs(2, [X,Y,Z])
   → base 错算 = source[0] + source[1] = 1 + 3 = 4 (用 metadata 算)
   → Step 1 disconnect source[2..end] from input[4]... 但 input[4] 不存在 (实际 source[1] 只 wire 到 input[1])
   → Step 2 wire source[2] to input[4..6] (input[4/5/6])
   → 但实际 Driver 1 的 wire 是 input[1], 现在被 Driver 2 wire 覆盖
```

用户感知: "切换 tab 连接覆盖前面 driver".

### 1.3 缺乏 visual feedback

当前 UI 没有任何指示**每个 tab 的 wire state**. 用户无法直观看到:
- driver 0 的 1 attr 是否真 wire 完整?
- driver 1 的 3 attr 是否真 wire 完整?
- 哪个 tab 处于不一致状态?

---

## 2. 设计 — 两部件 + 三 commit

### Part A — Silent failure 修 (commit 1, **必须先 land**)

Bug fix 优先, 因 Part B (指示灯) 显示的状态依赖 Part A 后的 atomic guarantee.

#### A.1 修改 [core.py:1813-1902](modules/RBFtools/scripts/RBFtools/core.py) `set_driver_source_attrs`

**关键改动**:

1. **Step 2 atomic**: connectAttr 失败立即 raise + rollback 已连 wire
2. **Step 2 后才写 metadata** (Step 3 移到 Step 2 之后):
   - 全部 connectAttr 成功 → 写新 metadata
   - 任一 failure → 不写 metadata + rollback 已连 wire + 恢复 source[index] 原 attrs wire
3. **Step 4 同样 atomic** (re-wire source[i > index]) — failure raise + rollback Step 1+2+3

完整 pseudocode:

```python
def set_driver_source_attrs(node, index, new_attrs):
    # ... (existing setup: read sources, validate index, etc.)
    target = sources[index]
    src_node = target.node
    existing_attrs = list(target.attrs)
    new_attrs_list = list(new_attrs)
    if existing_attrs == new_attrs_list:
        return True
    base = sum(len(s.attrs) for s in sources[:index])
    
    # Save snapshots for rollback
    pre_wires = []  # original wiring state
    for i in range(index, len(sources)):
        s = sources[i]
        for j, attr in enumerate(s.attrs):
            plug = "{}.{}".format(s.node, attr)
            sub_idx = _subscript_of_existing_input(plug, shape)
            if sub_idx is not None:
                pre_wires.append((s.node, attr, sub_idx))
    
    with undo_chunk("RBFtools: set driver source attrs"), \
         _node_state_frozen(shape):
        # Step 1: disconnect source[index..end]
        for i in range(index, len(sources)):
            ...  # same as before
        
        # Step 2: atomic re-wire source[index] new_attrs
        connected_step2 = []
        try:
            for i, attr in enumerate(new_attrs_list):
                if not cmds.attributeQuery(attr, node=src_node, exists=True):
                    raise RuntimeError(
                        "set_driver_source_attrs: {}.{} does not exist".format(
                            src_node, attr))
                src_plug = "{}.{}".format(src_node, attr)
                dst_plug = "{}.input[{}]".format(shape, base + i)
                cmds.connectAttr(src_plug, dst_plug, force=True)
                connected_step2.append((src_plug, dst_plug))
            
            # Step 4: atomic re-wire source[i > index]
            connected_step4 = []
            next_base = base + len(new_attrs_list)
            for i in range(index + 1, len(sources)):
                s = sources[i]
                if not s.node or not _exists(s.node):
                    next_base += len(s.attrs)
                    continue
                for j, attr in enumerate(s.attrs):
                    if not cmds.attributeQuery(attr, node=s.node, exists=True):
                        continue
                    src_plug = "{}.{}".format(s.node, attr)
                    dst_plug = "{}.input[{}]".format(shape, next_base + j)
                    cmds.connectAttr(src_plug, dst_plug, force=True)
                    connected_step4.append((src_plug, dst_plug))
                next_base += len(s.attrs)
            
            # Step 3 (now after Step 2+4): write metadata only on success
            attrs_plug = "{}.driverSource[{}].driverSource_attrs".format(
                shape, index)
            cmds.setAttr(
                attrs_plug, len(new_attrs_list),
                *new_attrs_list, type="stringArray")
        
        except Exception as exc:
            # Rollback: disconnect everything we connected
            for s, d in connected_step2 + connected_step4:
                try: cmds.disconnectAttr(s, d)
                except Exception: pass
            # Restore original wires from pre_wires snapshot
            for orig_node, orig_attr, _orig_sub in pre_wires:
                src_plug = "{}.{}".format(orig_node, orig_attr)
                # Re-allocate at original base (sources[i] base remains stable
                # since we didn't write metadata)
                # Compute target subscript from sources[:i] sum
                # ... (use original sources list, not modified)
            cmds.warning(
                "set_driver_source_attrs aborted + rolled back: {}".format(exc))
            return False
        
        # Step 5: sweep
        _sweep_empty_subscripts(shape, "input")
    
    return True
```

⚠️ Rollback 的 restore-original-wires 是**关键复杂点** — 必须保证 even on failure, plugin state 回到调用前的 consistent state. 执行者细心实现 + test 覆盖.

#### A.2 加 helper `core.driver_source_connection_state(node, index)`

新公共 API, 返回字符串 `"connected"` / `"partial"` / `"disconnected"`:

```python
def driver_source_connection_state(node, index):
    """Returns the wiring state of driverSource[index].
    
    Returns
    -------
    str
        ``"connected"``  — every attr in driverSource_attrs has a
                           matching live shape.input[base+i] connection
                           from the recorded driver_node.
        ``"partial"``    — metadata declares N attrs but only k<N have
                           input[] wires (e.g. silent-failure residue).
                           THIS IS AN INCONSISTENT STATE — user should
                           re-click "连接" or rebuild the node.
        ``"disconnected"``— metadata exists but 0 attrs have wires
                           (e.g. user manually deleted input[] wires).
    """
    shape = get_shape(node)
    sources = read_driver_info_multi(node)
    if index < 0 or index >= len(sources):
        return "disconnected"
    target = sources[index]
    if not target.node or not _exists(target.node):
        return "disconnected"
    n_attrs = len(target.attrs)
    if n_attrs == 0:
        return "disconnected"
    # Count how many attrs of this source have live input[] wires
    wired = 0
    for attr in target.attrs:
        plug = "{}.{}".format(target.node, attr)
        if _subscript_of_existing_input(plug, shape) is not None:
            wired += 1
    if wired == 0:
        return "disconnected"
    if wired == n_attrs:
        return "connected"
    return "partial"
```

#### A.3 controller exposure

[controller.py](modules/RBFtools/scripts/RBFtools/controller.py) 加 method:

```python
def driver_source_connection_state(self, index):
    """Forward to core.driver_source_connection_state for the
    active node's driverSource[index]."""
    if not self._current_node:
        return "disconnected"
    multi_idx = self._list_idx_to_sparse("driver", index)
    if multi_idx is None:
        return "disconnected"
    try:
        return core.driver_source_connection_state(
            self._current_node, multi_idx)
    except Exception as exc:
        cmds.warning(
            "driver_source_connection_state failed: {}".format(exc))
        return "disconnected"
```

---

### Part B — UI 指示灯 (commit 2)

#### B.1 修改 [tabbed_source_editor.py](modules/RBFtools/scripts/RBFtools/ui/widgets/tabbed_source_editor.py)

每个 tab title 前加状态 dot:
- ● 绿 (Unicode `●` + green color) — connected
- ◐ 黄 (`◐`) — partial
- ○ 红 (`○` + red color) — disconnected

**实现**: 用 QTabBar custom paint 或 setTabIcon 加彩色 QPixmap.

最简单方式: 用 `setTabText(index, "<dot> <name>")` + QTextDocument-style rich text. 但 QTabBar 不直接支持 rich text — 需要 `setTabIcon(index, QIcon(pixmap))`.

推荐: 用 `setTabIcon` + 程序生成 12x12 QPixmap (3 个静态 pixmap cache).

代码骨架:

```python
def _make_status_icon(state):
    """state: 'connected' | 'partial' | 'disconnected'"""
    color = {
        "connected": QtGui.QColor("#4CAF50"),    # green
        "partial":   QtGui.QColor("#FFC107"),    # amber
        "disconnected": QtGui.QColor("#F44336"), # red
    }.get(state, QtGui.QColor("#888888"))
    pm = QtGui.QPixmap(12, 12)
    pm.fill(QtCore.Qt.transparent)
    painter = QtGui.QPainter(pm)
    painter.setRenderHint(QtGui.QPainter.Antialiasing)
    painter.setBrush(color)
    painter.setPen(QtCore.Qt.NoPen)
    painter.drawEllipse(1, 1, 10, 10)
    painter.end()
    return QtGui.QIcon(pm)


def refresh_tab_indicators(self, controller):
    """Walk each tab, query connection_state, update tab icon."""
    for i in range(self._tabs.count()):
        state = controller.driver_source_connection_state(i)
        self._tabs.setTabIcon(i, _make_status_icon(state))
```

#### B.2 Refresh hooks

`refresh_tab_indicators` 在以下 events 被调:

1. tab 添加 / 删除 (`driverSourcesChanged` controller signal)
2. attrs apply 完成 (单 tab / batch 都需要)
3. attrs clear 完成
4. node selection changed (`currentNodeChanged`)
5. 手动 reload button

主要 hook 在 [main_window.py](modules/RBFtools/scripts/RBFtools/ui/main_window.py):

```python
# 在 _connect_signals 类似函数:
ctrl.driverSourcesChanged.connect(
    lambda: self._driver_source_list.refresh_tab_indicators(ctrl))
ctrl.currentNodeChanged.connect(
    lambda: self._driver_source_list.refresh_tab_indicators(ctrl))
```

---

### Part C — Single-tab "连接" 语义清晰化 (commit 2 同一 commit)

#### C.1 不动其他 tab subscript 的 subset case

当 `new_attrs == existing_attrs`: 已 short-circuit, no-op ✓

当 `len(new_attrs) == len(existing_attrs)` 且 attr 仅顺序/内容变: Step 1 disconnect + Step 2 re-wire 都在 base..base+n 内, **不 shift base offset, 不影响 source[i > index]**.

当 `len(new_attrs) != len(existing_attrs)`: base offset shift, **必须 re-wire source[i > index]**. 这是数学必然 (input[] 是 dense subscript). 但 Part A.1 让 Step 4 atomic — 失败 rollback, 不会留半成品.

#### C.2 UX 提示 (optional)

`_on_driver_source_attrs_apply` 检测 attr 数变化时弹 dialog:

```python
def _on_driver_source_attrs_apply(self, index, attrs):
    plan = self._guard_attrs_apply("driver", int(index), list(attrs))
    if plan is None:
        return
    
    # M_P0_DRIVER_CONNECT_UX_REVAMP: warn user if attr count change
    # will force re-wiring of all subsequent driver sources
    sources = self._ctrl.read_driver_sources()
    existing_count = len(sources[index].attrs) if index < len(sources) else 0
    new_count = len(attrs)
    if existing_count != new_count and index < len(sources) - 1:
        result = QtWidgets.QMessageBox.question(
            self,
            tr("title_attr_count_change"),
            tr("msg_attr_count_change_will_rewire").format(
                index, existing_count, new_count,
                len(sources) - index - 1),
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
        if result != QtWidgets.QMessageBox.Yes:
            return
    
    if plan["overlapping"]:
        cmds.warning(...)
    self._ctrl.set_driver_source_attrs(int(index), list(attrs))
```

新 i18n key (en + zh 各加):

```python
# i18n.py:
"title_attr_count_change": {"en": "Driver attr count change",
                             "zh": "驱动属性数变化"},
"msg_attr_count_change_will_rewire": {
    "en": "Driver {} attr count will change from {} to {}. This will "
          "trigger re-wiring of all {} subsequent driver source(s). "
          "Continue?",
    "zh": "Driver {} 的 attr 数将从 {} 变为 {}, 这会触发后续 {} 个 "
          "driver source 的重连. 是否继续?"},
```

#### C.3 状态恢复 fallback

如果 Part A.1 rollback 触发 (Step 2/4 failure), UI 立即:
- 刷新 indicator (变红/黄)
- 弹 dialog 告知用户

---

### Part E — 幂等性 + Indicator-Guided Dispatch (commit 2 同一 commit, 用户 directive #3)

**核心承诺**: "连接" 按钮**任何路径**任何模式下都是**幂等的** — 用户重复 click / 跨 tab 累计 click 不会产生重复 wire / 重复 metadata.

#### E.1 单 tab "连接" idempotent short-circuit

修改 [main_window.py `_on_driver_source_attrs_apply`](modules/RBFtools/scripts/RBFtools/ui/main_window.py:1989):

```python
def _on_driver_source_attrs_apply(self, index, attrs):
    plan = self._guard_attrs_apply("driver", int(index), list(attrs))
    if plan is None:
        return
    
    # M_P0_DRIVER_CONNECT_UX_REVAMP Part E.1 — indicator-guided
    # idempotent short-circuit. If tab is already green AND user's
    # selection equals existing metadata attrs, no-op (skip).
    state = self._ctrl.driver_source_connection_state(int(index))
    sources = self._ctrl.read_driver_sources()
    existing_attrs = (
        list(sources[index].attrs) if index < len(sources) else [])
    new_attrs = list(attrs)
    if state == "connected" and existing_attrs == new_attrs:
        cmds.warning(tr("driver_idempotent_skip").format(index))
        return
    
    # state == partial: force atomic rewire to recover from broken state
    # state == disconnected OR attrs changed: proceed via set_driver_source_attrs
    
    # ... existing count-change dialog (Part C) ...
    if plan["overlapping"]:
        cmds.warning(...)
    self._ctrl.set_driver_source_attrs(int(index), list(attrs))
```

**幂等行为表**:

| Tab 状态 | 用户 attr selection | 行为 |
|---|---|---|
| ● connected | == existing metadata | **no-op skip** (idempotent) |
| ● connected | ≠ existing (attr 数 / 顺序 / 内容变) | atomic re-wire via set_driver_source_attrs (走 Part C dialog if count 变) |
| ◐ partial | 任意 | atomic re-wire (恢复 from broken state) |
| ○ disconnected | 任意 | wire (走 set_driver_source_attrs) |

#### E.2 Pose 面板 "连接" 按钮 (batch / routed) 按 tab 过滤

修改 [main_window.py `_on_connect`](modules/RBFtools/scripts/RBFtools/ui/main_window.py:2389) — 已 connected 且 attr 一致的 driver tab 自动 skip:

```python
def _on_connect(self):
    cmds.warning(">>> ON_CONNECT TRIGGERED <<<")
    driver_targets, driven_targets = self._gather_routed_targets()
    
    # M_P0_DRIVER_CONNECT_UX_REVAMP Part E.2 — per-tab indicator filter.
    # Walk each driver_target, query state; drop tabs already fully
    # connected with identical attrs. Defends against repeat-click /
    # batch-click producing duplicate wires.
    sources = self._ctrl.read_driver_sources()
    filtered_drivers = []
    skipped = []
    for i, (node, attrs) in enumerate(driver_targets):
        if i >= len(sources):
            filtered_drivers.append((node, attrs))
            continue
        state = self._ctrl.driver_source_connection_state(i)
        existing_attrs = list(sources[i].attrs)
        if state == "connected" and existing_attrs == list(attrs):
            skipped.append(i)
            continue
        filtered_drivers.append((node, attrs))
    
    if skipped:
        cmds.warning(
            "Connect: {} already-connected driver tab(s) skipped "
            "(idempotent): indices {}".format(len(skipped), skipped))
    
    if not filtered_drivers and not driven_targets:
        try:
            cmds.confirmDialog(
                title="RBFtools",
                message=tr("connect_all_already_connected"),
                button=["OK"], defaultButton="OK")
        except Exception:
            cmds.warning(tr("connect_all_already_connected"))
        return
    
    self._set_interaction_enabled(False)
    self._is_updating = True
    try:
        self._ctrl.connect_routed(
            filtered_drivers, driven_targets)
    finally:
        self._is_updating = False
        self._set_interaction_enabled(True)
    self._refresh_pose_grid()
    # Trigger indicator refresh after connect storm
    self._driver_source_list.refresh_tab_indicators(self._ctrl)
```

#### E.3 attr 选择去重 (defensive)

修改 [tabbed_source_editor.py `_on_connect_clicked`](modules/RBFtools/scripts/RBFtools/ui/widgets/tabbed_source_editor.py:310):

```python
def _on_connect_clicked(self):
    idx = self._tabs.currentIndex()
    if idx < 0:
        return
    content = self._tabs.widget(idx)
    if content is None:
        return
    attrs_raw = list(content.selected_attrs())
    # M_P0_DRIVER_CONNECT_UX_REVAMP Part E.3 — dedupe preserving order.
    # selected_attrs() comes from QListWidget.selectedItems() and is
    # typically already unique, but defensive dedupe shields against
    # any future re-implementation that might emit duplicates.
    seen = set()
    attrs = []
    for a in attrs_raw:
        if a not in seen:
            seen.add(a)
            attrs.append(a)
    if self.is_batch_mode():
        self.attrsApplyBatchRequested.emit(attrs)
    else:
        self.attrsApplyRequested.emit(idx, attrs)
```

#### E.4 新 i18n keys

```python
# i18n.py 新增:
"driver_idempotent_skip": {
    "en": "Driver {} already fully connected with same attrs; "
          "skipping (idempotent).",
    "zh": "Driver {} 已用相同属性完整连接, 跳过 (幂等)."
},
"connect_all_already_connected": {
    "en": "All driver tabs are already fully connected with the "
          "selected attrs (idempotent skip).",
    "zh": "所有 driver tab 都已用当前所选属性完整连接, 无需重连 (幂等)."
},
```

#### E.5 Part E 与 Part A/B/C 协同流

```
用户 click "连接" (单 tab 或 batch)
   │
   ├── Part E.3: attr 选择去重
   │
   ├── Part E.1/E.2: query indicator state
   │     │
   │     ├── connected + same attrs → idempotent skip (warning + return)
   │     ├── connected + diff attrs → 走 Part C dialog (count 变?) → Part A set_driver_source_attrs
   │     ├── partial                → 强制 Part A atomic re-wire (恢复)
   │     └── disconnected           → 走 Part A set_driver_source_attrs
   │
   ├── Part A: atomic execute (raise + rollback on failure)
   │
   └── Part B: refresh_tab_indicators(controller) 更新 dot 颜色
```

---

### Part D — Test (commit 3)

新 unit test `modules/RBFtools/tests/test_m_p0_driver_connect_ux_revamp.py`:

#### D.1 Cases (跑在 mayapy / cmds stub)

1. **`test_connection_state_connected`** — 创建 RBFnode + 1 driver 1 attr, 验证 state = "connected"
2. **`test_connection_state_partial`** — 模拟 metadata 3 attr 但只 wire 1 个 input, 验证 state = "partial"
3. **`test_connection_state_disconnected`** — 删 input[] wire, 验证 state = "disconnected"
4. **`test_set_driver_source_attrs_atomic_rollback`** — mock connectAttr 抛 exception, 验证 rollback 后 state 恢复, metadata 未污染
5. **`test_set_driver_source_attrs_atomic_metadata_written_only_on_success`** — 验证 Step 3 仅在 Step 2+4 全成功后写
6. **`test_single_tab_connect_no_attr_count_change_preserves_others`** — 单 tab connect attrs 顺序变但数不变, 验证其他 tab 的 input subscript 字节级不动
7. **`test_single_tab_connect_attr_count_change_atomic_rewire`** — 单 tab connect 改 attr 数, 验证 source[i > index] re-wire atomic
8. **`test_idempotent_skip_connected_same_attrs`** — Part E.1: tab state=connected, attrs 不变, 第二次 click 后 input[] 字节级不变 (no duplicate wire, no re-write metadata)
9. **`test_idempotent_skip_batch_filters_connected_tabs`** — Part E.2: 3 tab 全绿, batch connect 走 _gather → 全 skip, connect_routed 收到 empty driver_targets, 0 wire churn
10. **`test_attr_dedupe_preserves_order`** — Part E.3: 模拟 selected_attrs 返回 [X, Y, X, Z], 验证 _on_connect_clicked emit 去重后 [X, Y, Z]
11. **`test_partial_state_forces_atomic_rewire`** — Part E.1: tab state=partial (人造 broken metadata vs wire), click 连接 → 触发 atomic re-wire (即使 attrs 与 metadata 同), 修复到 connected

#### D.2 UI test (optional, mayapy GUI)

`tests/scratch/smoke_tab_indicator.py` — 用户手动跑, 验证 3 tab 各显示对应颜色 dot.

---

## 3. Commit chain (Policy B, 严格 single-purpose)

| # | Commit | Scope |
|---|---|---|
| 1 | `fix(plugin): set_driver_source_attrs atomic + rollback (M_P0_DRIVER_CONNECT_UX_REVAMP Part A)` | core.py: atomic set + driver_source_connection_state helper + controller.driver_source_connection_state |
| 2 | `feat(ui): driver tab connection indicator + idempotent dispatch + attr count change UX (M_P0_DRIVER_CONNECT_UX_REVAMP Part B+C+E)` | tabbed_source_editor.py: tab icon + refresh hooks + attr dedupe; main_window.py: signal wire + count-change dialog + indicator-guided idempotent filter (both single-tab and batch paths); i18n.py: 4 new keys |
| 3 | `test(plugin+ui): atomic rollback + connection state + UX dialog (M_P0_DRIVER_CONNECT_UX_REVAMP Part D)` | new test_m_p0_driver_connect_ux_revamp.py (7 cases) + scratch/smoke_tab_indicator.py |
| 4 | (若 .mll rebuild 不需) `chore(installer): rebuild for Phase 13` | installer 重打 |

---

## 4. 不动什么

- ❌ 不动 `modules/RBFtools/scripts/` 的 milestone 字节级状态以外的 file (本 patch 直接改 scripts/, 因为是 Maya 2025 path 的真实 feature)
- ❌ 不动 C++ source / .mll (本 patch 纯 Python + UI)
- ❌ 不引入新依赖 (用现有 PySide2/6 + Maya cmds)
- ❌ 不改 input[] dense subscript 设计 (plugin 内部数据结构不动)
- ❌ 不删 / 改 add_driver_source (本 patch 仅 fix set_driver_source_attrs path; add_driver_source 路径已 OK)

## 5. 4/4 anchors

| Anchor | 影响 |
|---|---|
| TPS r≤0 (C++) | 0 — Python only |
| Honest-failure | **强化** — Part A.1 把 silent warn 升级为 atomic raise + rollback, 用户能立即看到失败 |
| Column-rank defence (C++) | 0 |
| polyDim 1+d (C++) | 0 |

---

## 6. 验证

### 6.1 静态 (执行者)

```bash
cd X:/Plugins/RBFtools
python -m pytest modules/RBFtools/tests/test_m_p0_driver_connect_ux_revamp.py -v
# 期望: 7 passed

python -m pytest modules/RBFtools/tests --continue-on-collection-errors -q
# 期望: 614 + 7 new = 621, 0 回归
```

### 6.2 用户实测 (Maya 2025 + Maya 2022)

#### 场景 A — 多 driver tab 连接累积

1. 新建 RBFnode
2. **Driver 0**: 选 Elbow, highlight `[rotateX]`, click "添加驱动" → 期望 Driver 0 tab 显示 **● 绿** (connected, 1/1)
3. 切 Driver 1 tab: 选 Shoulder, highlight `[rotateX, rotateY, rotateZ]`, click "添加驱动" → 期望 **Driver 0 仍 ● 绿**, Driver 1 ● 绿 (3/3)
4. 切 Driver 2 tab: 选 L_Shoulder, highlight `[rotateX, rotateY, rotateZ]`, click "添加驱动" → 期望 **Driver 0 + 1 仍 ● 绿**, Driver 2 ● 绿 (3/3)
5. 跑诊断: `cmds.getAttr(shape + ".input", multiIndices=True)` 期望 `[0, 1, 2, 3, 4, 5, 6]` (7 个 input, 累积)

#### 场景 B — 单 tab "连接" attr 数变化触发 dialog

1. Driver 0 已 connect `[rotateX]` (1 attr)
2. 在 Driver 0 tab highlight `[rotateX, rotateY, rotateZ]` (改成 3 attr)
3. click "连接" (单 tab 模式)
4. **期望弹 dialog**: "Driver 0 的 attr 数将从 1 变为 3, 会触发后续 2 个 driver source 的重连. 是否继续?"
5. 点 "是" → 期望 atomic re-wire, 所有 tab indicator 维持 ● 绿
6. 点 "否" → 期望什么都没改, indicator 不变

#### 场景 C — silent failure → atomic rollback 演示

mock `cmds.connectAttr` 在第 2 个 attr 抛 exception (UI test 不易演示, 留 unit test 覆盖).

#### 场景 D — 幂等性 (Part E)

1. Driver 0/1/2 全部 ● 绿 (3 tab 各完整 connect)
2. 切 Driver 1, **不动 highlight**, 直接 click "连接"
3. **期望**: Script Editor warning "Driver 1 already fully connected with same attrs; skipping (idempotent)"
4. 跑诊断 `cmds.getAttr(shape + ".input", multiIndices=True)` — input[] **数量不变, subscript 不变**
5. 跑诊断 `cmds.getAttr(shape + ".driverSource[1].driverSource_attrs")` — metadata 字符级不变

#### 场景 E — 批量幂等过滤 (Part E.2)

1. 全部 3 tab ● 绿
2. 点 pose 面板的 "连接" 按钮 (batch / routed path)
3. **期望**: Script Editor warning "Connect: 3 already-connected driver tab(s) skipped (idempotent): indices [0, 1, 2]" + dialog "所有 driver tab 都已用当前所选属性完整连接, 无需重连 (幂等)."
4. **无任何 wire churn** — input[] 字节级不变

#### 场景 F — partial state 触发强制 atomic 恢复 (Part E.1)

人造 partial 状态 (用 Maya cmds 手动 `disconnectAttr` 某 input 但 metadata 保留):
1. Driver 1 currently ● 绿 (3 attr, 3 wire)
2. Script Editor 跑: `cmds.disconnectAttr("Shoulder_L_RBFber.rotateY", "RBFnode_shoulder_LShapeShape.input[2]")`
3. 现在 Driver 1 应显示 ◐ 黄 (partial: 2/3 wire)
4. 切 Driver 1 tab, **保留同样 attr selection** [rotateX, rotateY, rotateZ], click "连接"
5. **期望**: 触发 atomic re-wire (跳过 E.1 idempotent skip 因 state != connected), 完成后回到 ● 绿

---

## 7. 风险评估

| 风险 | 概率 | 影响 | 缓解 |
|---|---|---|---|
| Part A.1 rollback restore 逻辑复杂, 边缘 case 漏 | 中 | rollback 不完整, plugin 状态半 broken | D.1 test 4/5/7 三 case 覆盖 + executor 仔细 walk through 边缘 |
| Tab icon 在 PySide2 vs PySide6 渲染差异 | 低 | icon 颜色 / size 微差 | 用低级 QPixmap + QPainter, 两版 API 一致 |
| refresh_tab_indicators 在 mid-storm (compute 进行中) 调用 reentrancy | 低 | UI 卡 / 死锁 | hook 在 `driverSourcesChanged` (post-storm signal), 不在 cmds.* mid-call |
| 用户连击 "连接" 在 dialog 弹窗期间 | 低 | dialog 阻断, 安全 | Qt modal dialog 自动阻断后续 click |

---

## 8. Commit message 模板 (执行者照搬)

### Commit 1

```
fix(plugin): set_driver_source_attrs atomic + rollback (M_P0_DRIVER_CONNECT_UX_REVAMP Part A)

User-reported repro: clicking driver-source-panel "连接" on Driver i
with attr count change leaves metadata-vs-wiring inconsistent on
silent connectAttr failures; subsequent "连接" on Driver j (j>i)
computes wrong base offset from broken metadata and overwrites
i's wires.

Root cause: core.py:1845-1852 caught connectAttr failures with
plain cmds.warning -- metadata stringArray (Step 3) wrote 3 attr
even when only 1 of 3 connectAttr's succeeded.

Fix:
* Step 2 + 4 atomic: connectAttr exception -> raise + rollback
  all already-connected wires + restore source[index] original
  attrs at original base offset
* Step 3 (metadata write) moved AFTER Step 2+4 -- only writes
  on full success
* Pre-snapshot original wires (sources[index..end]) for restore
* All-or-nothing semantics: success returns True with metadata +
  wires consistent; failure returns False + node returns to
  pre-call state

New helper: core.driver_source_connection_state(node, index)
returns "connected" / "partial" / "disconnected" by comparing
driverSource_attrs metadata against live input[] wires. Exposed
via controller.driver_source_connection_state for UI consumption.

Math: N/A (state machine fix).
Anchors held: 4/4 (honest-failure strengthened -- silent warn
upgraded to atomic raise + rollback).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

### Commit 2

```
feat(ui): driver tab connection indicator + idempotent dispatch + attr count change UX (M_P0_DRIVER_CONNECT_UX_REVAMP Part B+C+E)

Add per-tab connection indicator (red/yellow/green dot) to the
driver source panel. Indicator queries
controller.driver_source_connection_state(i) for each tab:
  green dot   - all metadata attrs have live input[] wires
  yellow dot  - partial wiring (post-rollback recovery state)
  red dot     - metadata exists but 0 wires (or empty source)

Refresh triggers (any of):
  * driverSourcesChanged signal (post add/remove/set)
  * currentNodeChanged signal (node switch)
  * connect_routed post-storm callback
  * Reload button manual click

Indicator-guided idempotent dispatch (Part E):
  * Single-tab "连接": if tab green AND user attrs == metadata,
    no-op skip (idempotent) with warning. If tab yellow, force
    atomic re-wire to recover. If tab red or attrs changed,
    proceed via set_driver_source_attrs.
  * Batch / pose-panel "连接": filter driver_targets per tab
    state — already-green tabs with same attrs skipped before
    connect_routed runs. Prevents duplicate wire accumulation
    on repeat clicks.
  * Attr selection dedupe (defensive): _on_connect_clicked
    dedupes attrs preserving order before emitting signal.

UX dialog: when single-tab "连接" detects attr count change AND
source[index] is not last source, surface confirmation dialog
explaining the re-wiring scope. Prevents accidental cross-tab
disruption.

i18n: 4 new keys (title_attr_count_change,
msg_attr_count_change_will_rewire, driver_idempotent_skip,
connect_all_already_connected — en + zh).

Math: N/A (UI feature).
Anchors held: 4/4.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

### Commit 3

```
test(plugin+ui): atomic rollback + connection state + UX dialog (M_P0_DRIVER_CONNECT_UX_REVAMP Part D)

New unit test test_m_p0_driver_connect_ux_revamp.py:
  1. test_connection_state_connected
  2. test_connection_state_partial
  3. test_connection_state_disconnected
  4. test_set_driver_source_attrs_atomic_rollback
  5. test_set_driver_source_attrs_atomic_metadata_written_only_on_success
  6. test_single_tab_connect_no_attr_count_change_preserves_others
  7. test_single_tab_connect_attr_count_change_atomic_rewire

Scratch (manual mayapy GUI test):
  tests/scratch/smoke_tab_indicator.py -- visual verification of
  red/yellow/green dot colors in driver tab bar.

Math: N/A.
Anchors held: 4/4.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

---

## 9. 关键文件路径速查

| 文件 | 操作 |
|---|---|
| [modules/RBFtools/scripts/RBFtools/core.py:1747-1902](modules/RBFtools/scripts/RBFtools/core.py) | **Part A.1**: set_driver_source_attrs atomic 重写 |
| [modules/RBFtools/scripts/RBFtools/core.py](modules/RBFtools/scripts/RBFtools/core.py) | **Part A.2**: 新 helper driver_source_connection_state |
| [modules/RBFtools/scripts/RBFtools/controller.py](modules/RBFtools/scripts/RBFtools/controller.py) | **Part A.3**: 新 method driver_source_connection_state |
| [modules/RBFtools/scripts/RBFtools/ui/widgets/tabbed_source_editor.py](modules/RBFtools/scripts/RBFtools/ui/widgets/tabbed_source_editor.py) | **Part B.1**: tab icon helper + refresh_tab_indicators |
| [modules/RBFtools/scripts/RBFtools/ui/main_window.py:1989-2013](modules/RBFtools/scripts/RBFtools/ui/main_window.py) | **Part C.2**: _on_driver_source_attrs_apply 加 count-change dialog + signal hook |
| [modules/RBFtools/scripts/RBFtools/ui/i18n.py](modules/RBFtools/scripts/RBFtools/ui/i18n.py) | **Part C.2**: 2 new i18n keys |
| `modules/RBFtools/tests/test_m_p0_driver_connect_ux_revamp.py` | **Part D**: 新 test 文件 (7 cases) |
| `modules/RBFtools/tests/scratch/smoke_tab_indicator.py` | **Part D**: 用户手动跑 GUI smoke |
| `installer/RBFtoolsInstaller.exe` | Phase 13 重打 |
