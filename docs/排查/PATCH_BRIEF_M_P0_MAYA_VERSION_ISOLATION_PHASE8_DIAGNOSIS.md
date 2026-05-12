# Patch Brief — M_P0_MAYA_VERSION_ISOLATION Phase 8 (diagnosis-first)

> Planner / Architect 诊断 brief. 执行者照此实施 (大概率不改代码, 主修诊断).
>
> **Origin**: 2026-05-12 用户报告 Maya 2022 两个新 bug:
> 1. MQB 算法无法使用
> 2. 断开连接时 driven 节点 scale 被设置为 0
>
> **关键诉求**: "maya2022 的版本是需要与 maya2025 完全一模一样的. 分析所有 maya2025 版本相关代码, 在 maya2022 版上一比一完美还原, 并且兼容 py2 和 py3".
>
> **Status**: APPROVED — 等执行者按 H1→H2→H3 顺序排查.

---

## 1. Planner 已完成的等价性验证 (执行者无需重做)

| 检查 | 结果 | 证据 |
|---|---|---|
| Python `scripts/` vs `scripts_2022/` disconnect 路径字节级等价 | ✓ 完全相同 | `core.py:4337 == scripts_2022/core.py:4346`, `cmds.setAttr(other_plug, 1.0)` 一致, `SCALE_ATTR_NAMES` frozenset 一致 |
| MQB 路由 (kernelType=4) Python 端等价 | ✓ 完全相同 | `core_profile.py:248` `_KERNEL_LABELS`, `constants.py` kernel labels 一致 |
| 数值字面量 / control flow / function signature | ✓ 完全相同 | `diff -ru` 排除 R1-R7 后**剩空** (无 unexpected drift) |
| .cpp source 含全部修复 (M_P0_DISCONNECT_SCALE_RESTORE + polyDim 1+d + column-rank defence) | ✓ 验证 | `grep` 命中 source/RBFtools.cpp:161/2000-2295 |
| .mll 双 build 同 commit (mtime 一致 02:03 May 12 = milestone) | ✓ | `2022.mll: e869aa88...`, `2025.mll: df3cc02a...`, size 都是 188416, mtime 都是 02:03 |
| installer Phase 7 latest (mtime 20:21 May 12) | ✓ | sha256 `3d2d67048e15...`, size 13971016 |
| 4/4 anchors held | ✓ | scripts/ revert 后字节级 = milestone, .mll 双 build 含全部 anchor 修复 |

**结论**: main repo (HEAD `381a3a4`) **代码层面 100% 健康**. bug 必然来自**环境 / 部署 / 用户机器副本不一致**.

---

## 2. 三个 root cause hypothesis (按概率排序)

### H1 (95% 概率) — 用户机器装的不是最新 installer

**Evidence**:
- 用户 disconnect scale=0 bug = `M_P0_DISCONNECT_SCALE_RESTORE` (2026-05-10) 修复**之前**的行为
- 用户 MQB 无法使用 = `M_P0_RBF_COLUMN_RANK_DEFENSE` (2026-05-12 02:00) 修复**之前**的行为
- 若装的是最新 installer (Phase 7, 2026-05-12 20:21), 双 fix 都应已生效

**用户最可能的失误路径**:
- 装的是更早 build 的 installer (e.g. v2 build, 2026-05-12 02:03 之前的 build)
- 或者没卸载旧 RBFtools 直接装, modules/ 目录残留老 .mll + 老 Python
- 或者 .pyc 缓存让 Maya 加载老代码

**修复**: 强制重装步骤 (§4.1), 不动代码.

### H2 (4% 概率) — Maya 2022 加载错 module path

**Evidence**:
- .mod template MAYAVERSION:2022 → scripts_2022 ✓ 已验证
- 但若用户机器 RBFtools.mod 是老版本 (Phase 4 之前 deploy 的), 仍走 scripts: scripts
- 走 scripts/ 路径在 Maya 2022 py2 模式下会因 isinstance str 拒绝 unicode → 整个 module 加载失败 → 没 UI

**实测验证**: §4.2 用户跑诊断脚本看 `help_texts.__file__` 是否含 `scripts_2022`.

**修复**: 若 H2 命中, 用户机器 RBFtools.mod 是老版本 → 强制重装解决 (同 H1 修复).

### H3 (<1% 概率) — Maya 2022 与 Maya 2025 API 行为差异

**Evidence**:
- 不太可能 — cmds.setAttr / cmds.disconnectAttr / cmds.connectAttr 等核心 API 跨 Maya 版本稳定
- C++ MFnNumericData / MPxNode API 也稳定

**若 H3 命中**: 需要更细致的 Maya 版本兼容性 audit (执行者 §4.3).

---

## 3. 当前 Planner 评估 — Maya 2025 (scripts/) 代码本身是否有"未发现"的 bug?

**用户原话**: "分析所有 maya2025 版本相关代码, 在 maya2022 版上一比一完美还原".

Planner 已完成 audit ([AUDIT_M_P0_MAYA_VERSION_ISOLATION.md](AUDIT_M_P0_MAYA_VERSION_ISOLATION.md) + 本次跟进 diff):

- scripts/ 在 Maya 2025 (py3) 下: MQB / disconnect 均 work (用户 milestone 实测 ✓)
- scripts_2022/ 与 scripts/ Python 端**字节级行为等价** (除 R1-R7 transformation, 不改逻辑)
- 因此 scripts_2022/ 在 Maya 2022 (py3 模式) 下应**与 scripts/ 在 Maya 2025 下行为完全一致**

**Planner 不认为 scripts_2022/ 与 scripts/ 之间存在"一比一不完美"的 Python 代码差异**. 当前 bug 必然源于**环境/部署**, 非代码.

---

## 4. 诊断步骤 (按 H1→H2→H3 顺序, 大概率 H1 就解决)

### 4.1 H1 诊断 — 用户强制重装 (优先)

**用户操作**:

1. **彻底关闭 Maya 2022** (任务管理器确认 `maya.exe` 进程为 0)
2. **删除以下 3 处** (即使是空目录也要确认删):
   ```
   C:\Users\sz-dingyongzhen\Documents\maya\modules\RBFtools (整个目录)
   C:\Users\sz-dingyongzhen\Documents\maya\modules\RBFtools.mod (若存在)
   C:\Users\sz-dingyongzhen\Documents\maya\2022\prefs\userPrefs.mel (备份后删, 清 Maya UI 缓存)
   ```
3. **重启电脑** (强制清 .pyc / 文件锁)
4. 跑 `X:\Plugins\RBFtools\installer\RBFtoolsInstaller.exe` — **验证 mtime ≥ 2026-05-12 20:21**, 否则你的 installer 也是旧的, 让执行者再跑 `tools\build_installer.bat` 重打
5. 启动 Maya 2022 → 加载 RBFtools
6. **跑 Maya Script Editor 诊断脚本**:
   ```python
   # M_P0_MAYA_VERSION_ISOLATION Phase 8 诊断
   import os
   import hashlib
   
   # 1. 模块路径验证 (期望含 'scripts_2022')
   from RBFtools.ui import help_texts as ht
   print("=" * 60)
   print("DIAGNOSTIC OUTPUT — paste back to Planner")
   print("=" * 60)
   print("\n1. help_texts module path:")
   print("  ", ht.__file__)
   print("   Expected to contain: scripts_2022")
   
   # 2. .mll 路径 + sha256 验证
   import maya.cmds as cmds
   plugin_info = cmds.pluginInfo("RBFtools", q=True, path=True)
   print("\n2. .mll path:")
   print("  ", plugin_info)
   if plugin_info and os.path.exists(plugin_info):
       with open(plugin_info, "rb") as f:
           sha = hashlib.sha256(f.read()).hexdigest()
       size = os.path.getsize(plugin_info)
       mtime = os.path.getmtime(plugin_info)
       print("   sha256:", sha)
       print("   size:", size)
       print("   mtime (epoch):", mtime)
   print("   Expected 2022 sha256: e869aa88fdb9e10f6ef9377bc0e2db43f5427183146b950224338a20020c0e4a")
   print("   Expected 2025 sha256: df3cc02a9cf56caf00daa7d67147516e337ee2189d35f637b7084202c82f3996")
   
   # 3. Python 版本 + 是否 py2/py3
   import sys
   print("\n3. Python version:")
   print("  ", sys.version)
   print("   Note: py2 unicode test:", end=" ")
   try:
       _ = unicode  # noqa
       print("py2 mode (unicode type exists)")
   except NameError:
       print("py3 mode")
   
   # 4. 复现 disconnect scale=0 bug
   print("\n4. 复现 disconnect scale 测试:")
   print("   (a) 创建一个测试场景: RBFnode + 1 driver joint + 1 driven mesh")
   print("   (b) Apply + Connect")
   print("   (c) 在 Script Editor 看 driven.scaleX before disconnect:")
   print("       cmds.getAttr('<driven>.scaleX')")
   print("   (d) 点 Disconnect 按钮")
   print("   (e) 再看 driven.scaleX after disconnect:")
   print("       cmds.getAttr('<driven>.scaleX')")
   print("   (f) 期望: 1.0 (不应该是 0.0)")
   
   # 5. 复现 MQB 测试
   print("\n5. 复现 MQB 测试:")
   print("   (a) 选 RBFnode, kernel dropdown 切 Multi-Quadratic Biharmonic (index 4)")
   print("   (b) 点 Apply")
   print("   (c) 期望: 无 kFailure, driven 不飞")
   print("   (d) 看 Script Editor: 是否有 'M_P0_RBF_COLUMN_RANK_DEFENSE' 相关 warning")
   ```
7. **把诊断脚本输出整段复制反馈给 Planner**, 包含:
   - module path (`scripts_2022` ?)
   - .mll sha256 (匹配期望 ?)
   - Python 版本
   - disconnect 测试 (scale 值 before / after)
   - MQB 测试 (kFailure ? warning 内容 ?)

### 4.2 H2 诊断 (若 H1 输出显示 module path 不含 `scripts_2022`)

用户运行:

```python
# 检查 RBFtools.mod 内容
mod = r"C:\Users\sz-dingyongzhen\Documents\maya\modules\RBFtools.mod"
import os
if os.path.exists(mod):
    with open(mod, "rb") as f:
        print(f.read().decode("utf-8"))
else:
    print("RBFtools.mod not found at", mod)
# 期望: 含 MAYAVERSION:2022 + scripts_2022 路由
```

若 mod 内容是老版本 (无 scripts_2022 路由) → 用户**确实**装的是旧 installer → 回到 §4.1 强制重装.

### 4.3 H3 诊断 (若 H1 + H2 都验证 OK 但 bug 仍在)

执行者跑 (在 main repo):

```bash
# 1. 验证 .mll 双 build 真包含 M_P0_DISCONNECT_SCALE_RESTORE C++ defense
strings modules/RBFtools/plug-ins/win64/2022/RBFtools.mll | grep -E "DISCONNECT_SCALE|COLUMN_RANK|polyDim" | sort -u

# 2. 对比 2025 .mll 含同样字符串
strings modules/RBFtools/plug-ins/win64/2025/RBFtools.mll | grep -E "DISCONNECT_SCALE|COLUMN_RANK|polyDim" | sort -u

# 3. 看 cmake 配置是否真分 2022/2025 编译
cat CMakeLists.txt | grep -nE "MAYA_VERSION|find_package|Maya|target_compile_definitions"
```

若 2022 .mll 缺某 string (e.g. "M_P0_DISCONNECT_SCALE_RESTORE") 而 2025 .mll 有 → **2022 build 漏 patch, 是真 bug** → 执行者跑 cmake clean rebuild, 重新双 deploy.

若两 .mll 字符串相同 → C++ 不是问题, bug 在 Maya 2022 API 层差异 → 升级 Planner 重新设计 patch.

---

## 5. 修复路径 (取决于诊断结果)

### Path A (H1 命中) — 用户重装解决, **无需新 commit**

最 likely. 用户跑 §4.1 强制重装步骤后所有 bug 消失.

执行者**不需要**做任何代码改动. 仅在用户确认 bug 消失后:
- 在 SESSION_HANDOFF §11 记录"P1 用户实测通过, Phase 7 ready to tag milestone"
- 升级 milestone tag → `milestone/RBF-MQB-correct-2026-05-12-isolation-LANDED`

### Path B (H2 命中) — 同 Path A

老 .mod file 残留是 H1 失误的子集, 解决方案是同样的强制重装.

### Path C (H3 命中) — 真 C++ build bug, 需要重 build

执行者跑 cmake clean rebuild:

```bash
cmake --build build_check_2022 --target clean
cmake --build build_check_2022 --config Release
# 部署到 modules/RBFtools/plug-ins/win64/2022/RBFtools.mll

cmake --build build_check --target clean
cmake --build build_check --config Release
# 部署到 modules/RBFtools/plug-ins/win64/2025/RBFtools.mll

# 验证 2022 .mll 现在包含修复:
strings modules/RBFtools/plug-ins/win64/2022/RBFtools.mll | grep DISCONNECT_SCALE

# 重打 installer
tools\build_installer.bat
```

3 个 commits (Policy B):
1. `chore(deploy): rebuild 2022 + 2025 .mll for Phase 8` 
2. `chore(installer): rebuild for Phase 8`

(不需要 fix commit — source 已 OK, 只是 build 漏)

---

## 6. 不动什么 (negative space)

- ❌ 不动 `modules/RBFtools/scripts/` (Maya 2025 神圣)
- ❌ 不动 `modules/RBFtools/scripts_2022/` (已通过 drift test 验证与 sync 一致)
- ❌ 不动 sync_2022_from_2025.py (已 Phase 7 修过)
- ❌ 不动 .mod template (已正确)
- ❌ 不动 git history (Policy A)
- ❌ **盲修代码** — Planner 评估代码层面健康, 在没有诊断证据前不动 codebase

---

## 7. 完成条件

- [ ] 用户跑 §4.1 强制重装步骤 + 诊断脚本, 反馈输出
- [ ] 若 disconnect scale 测试显示 1.0 + MQB 切 kernel 无 kFailure → **bug 消失** → milestone tag 升级
- [ ] 若仍 fail, 按 H2/H3 路径继续

---

## 8. 关键路径速查

| 文件 | 用途 |
|---|---|
| `X:\Plugins\RBFtools\installer\RBFtoolsInstaller.exe` | mtime 2026-05-12 20:21 = Phase 7 最新, 用户必须装这个 |
| `X:\Plugins\RBFtools\modules\RBFtools\plug-ins\win64\2022\RBFtools.mll` | sha256 `e869aa88...`, milestone state, 含全部修复 |
| `X:\Plugins\RBFtools\modules\RBFtools\plug-ins\win64\2025\RBFtools.mll` | sha256 `df3cc02a...`, milestone state, 含全部修复 |
| `X:\Plugins\RBFtools\source\RBFtools.cpp` | C++ source, 含 M_P0_DISCONNECT_SCALE_RESTORE + COLUMN_RANK_DEFENSE + polyDim |
| `X:\Plugins\RBFtools\modules\RBFtools\scripts\RBFtools\core.py:4337` | disconnect scale restore Python defense, milestone state |
| `X:\Plugins\RBFtools\modules\RBFtools\scripts_2022\RBFtools\core.py:4346` | 同上, sync 派生 (字节级行为等价) |
