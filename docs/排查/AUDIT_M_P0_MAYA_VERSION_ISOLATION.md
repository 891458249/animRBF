# Planner Audit — M_P0_MAYA_VERSION_ISOLATION

> **审阅日期**: 2026-05-12
> **审阅 SHA**: `8cc90e3` (origin/main HEAD)
> **审阅范围**: 12 个 commit (`2a41617..8cc90e3`), Phase 1-6
> **结论**: **❌ NOT READY TO TAG MILESTONE** — 1 个 critical bug 在 scripts_2022/help_texts.py 需要 Phase 7 hotfix.

---

## 1. 摘要

| 项 | 结果 |
|---|---|
| 12 个 commit 全部 land | ✅ |
| Phase 1 revert 完整 (scripts/ = milestone 字节级) | ✅ — `git diff milestone..HEAD -- modules/RBFtools/scripts/` 为空 |
| Phase 2 scripts_2022/ 51 .py 全部 100% ASCII | ✅ |
| Phase 3 sync script idempotent + --check OK | ✅ |
| Phase 4 .mod template 3 处 MAYAVERSION:2022 → scripts_2022 | ✅ |
| Phase 5 installer 重打 + per-version routing | ✅ |
| Phase 6 drift detector 2 cases passed | ✅ |
| sweep 0 回归 (614 passed, 与 milestone 一致) | ✅ |
| 4/4 anchors 保留 | ✅ (Phase 1 revert 后必然) |
| **scripts_2022 vs scripts 严格功能等价** | **❌ 1 个 critical bug + 1 个 functional divergence** |

---

## 2. ❌ Critical Bug — Rule 2 u-prefix 在 Rule 3 path 未触发

### 2.1 现象

`scripts_2022/RBFtools/ui/help_texts.py` 内 **8 处** kernel 描述字符串字面量含 `\uXXXX` escape **但缺 `u` 前缀**:

| 行号 | 当前内容 (scripts_2022) | 问题 |
|---|---|---|
| 241 | `"Linear kernel: φ(r) = r\n\n"` | 缺 u 前缀 |
| 246 | `"Cons: Not smooth at pose locations (C⁰ continuity only).",` | 缺 u 前缀 |
| 249 | `"Gaussian 1 kernel: φ(r) = exp(-r²)\n\n"` | 缺 u 前缀 |
| 253 | `"Pros: Smooth (C∞), well-behaved, most commonly used.\n"` | 缺 u 前缀 |
| 257 | `"Gaussian 2 kernel: φ(r) = exp(-r²/2)\n\n"` | 缺 u 前缀 |
| 264 | `"Thin Plate Spline kernel: φ(r) = r² · ln(r)\n\n"` | 缺 u 前缀 |
| 271 | `"Multi-Quadratic Biharmonic kernel: φ(r) = √(1 + r²)\n\n"` | 缺 u 前缀 |
| 278 | `"Inverse Multi-Quadratic Biharmonic kernel: φ(r) = 1/√(1 + r²)\n\n"` | 缺 u 前缀 |

### 2.2 Python 2 行为陷阱 (用户底线违反)

py2 docs (Library Reference §2.4.1):
> The `\u` escape sequence is unique to Unicode literals.

py2 `"φ"` (无 u 前缀) 评估为 **6 个 ASCII 字面字符** `\`, `u`, `0`, `3`, `c`, `6`, **不是** φ. py3 `"φ"` == `"φ"` (无 u/不 u 不影响, py3 所有 string literal 都是 unicode).

**Maya 2022 py2 mayapy2 模式实际表现**:
- hover "Linear" kernel `?` icon → 期望气泡显示 `Linear kernel: φ(r) = r ...`
- **实际**显示 `Linear kernel: φ(r) = r ...` (字面 `φ` 文本)

类似 7 处 kernel 描述均受影响.

### 2.3 Root cause — sync script Rule 2/3 order bug

`tools/sync_2022_from_2025.py:181-232` `_ascii_escape_string_token` 函数:

```python
# Line 210-212: Rule 3 first — merge \xHH multi-byte to \uXXXX
new_body = _merge_utf8_escapes(body)

# Line 216: Rule 2 check — has_non_ascii looks at POST-Rule-3 body
has_non_ascii = any(ord(c) > 127 for c in new_body)
if has_non_ascii:
    # ... auto-promote u prefix
    if not (_is_bytes_prefix(prefix) or "u" in prefix.lower()):
        prefix = "u" + prefix
```

**bug**: Rule 3 把 `\xcf\x86` (2 个 byte escape, source contains raw bytes 0xcf 0x86) 合并为 `φ` (6 个 ASCII 字符). 此时 `new_body` 已经全是 ASCII bytes (`\` `u` `0` `3` `c` `6` 都 < 128), `has_non_ascii == False`, u 前缀**不会**被加.

### 2.4 与 milestone scripts/ 对比 — pre-existing display 问题

milestone state `modules/RBFtools/scripts/RBFtools/ui/help_texts.py:241`:

```python
"Linear kernel: \xcf\x86(r) = r\n\n"
```

py3 解析:
- `\xcf` → U+00CF (`Ï` Latin Capital I with Diaeresis)
- `\x86` → U+0086 (control char, non-printable)
- 显示: `Linear kernel: Ï<ctrl>(r) = r`

这是 milestone 原本就有的 **pre-existing display bug** — 作者意图是 `φ` (希腊小写 phi, U+03C6), 但写成了 utf-8 byte sequence `\xcf\x86` 形式 (这是 utf-8 编码 phi 时的 byte 序列), Python parser 把 `\xHH` 解析为 codepoint 而非 utf-8 byte, 所以显示乱码.

**Maya 2025 用户从未报告过这个问题** — 可能因为 (a) kernel_linear 帮助气泡很少被打开, (b) `Ï` 不影响功能仅影响美观.

### 2.5 修复建议 (Phase 7 hotfix)

修改 `tools/sync_2022_from_2025.py:181-232` `_ascii_escape_string_token`, 在 **Rule 3 后** 增加额外检查: 若 `new_body` 含 `\uXXXX` 或 `\UXXXXXXXX` escape sequence **且** 前缀无 u, 则自动加 u 前缀.

伪代码:

```python
new_body = _merge_utf8_escapes(body)

# Rule 2 check — has_non_ascii (raw chars in body)
has_non_ascii = any(ord(c) > 127 for c in new_body)

# 新增 — Rule 3 path 也要 u-prefix promote
has_unicode_escape = bool(re.search(r'\\[uU][0-9a-fA-F]{4,8}', new_body))

if has_non_ascii or has_unicode_escape:
    # ... escape non-ASCII raw chars (only if has_non_ascii)
    if has_non_ascii:
        # escape logic for raw chars
        ...
    # Auto-promote u prefix in EITHER case
    if not (_is_bytes_prefix(prefix) or "u" in prefix.lower()):
        prefix = "u" + prefix
```

跑 sync regen scripts_2022/, drift test 自动验证.

---

## 3. ⚠️ Functional Divergence — Rule 3 改变运行时显示

### 3.1 现象

Rule 3 的 `\xcf\x86 → φ` 合并**改变了 Maya 2022 显示行为** vs Maya 2025:

| | Maya 2025 (scripts/) | Maya 2022 py3 (scripts_2022) | Maya 2022 py2 (scripts_2022) |
|---|---|---|---|
| help_texts.py kernel_linear 显示 | `Linear kernel: Ï<ctrl>(r) = r` (milestone pre-existing bug) | `Linear kernel: φ(r) = r` ✅ | `Linear kernel: φ(r) = r` ❌ (Bug §2 修复后会变 ✅) |

scripts_2022 (py3 模式) **比 scripts/ 显示更正确** — Rule 3 实际上**修复了** scripts/ 的 pre-existing 显示 bug, 但仅在 scripts_2022 这个分支. scripts/ 仍保留原 `\xcf\x86` 错误.

### 3.2 判读 — 是 bug 还是 feature?

按用户原话 "底线是所有功能都需要完美落地":

| 选项 | 利弊 |
|---|---|
| A. 接受 divergence (scripts_2022 正确, scripts/ 保留 bug) | + Maya 2022 修复了 pre-existing bug; - scripts_2022 ≠ scripts/ 严格等价 |
| B. 修 scripts/ 让 Maya 2025 也显示正确 (新 patch M_P0_HELP_TEXTS_PHI_FIX) | + 两版都正确; - 违反 "scripts/ 神圣冻结" 原则 |
| C. 在 scripts_2022 故意保留 `\xcf\x86` (撤销 Rule 3 merge) | + 严格等价; - Maya 2022 py2 仍崩溃, Maya 2022 py3 仍显示 `Ï` |

**Planner 建议**: **A — 接受 divergence**. 理由:
1. Rule 3 修复**让 Maya 2022 显示正确** — 符合"完美落地" 底线
2. Maya 2025 已 ship 这个 pre-existing bug 一段时间, 用户未报告, 影响 minor
3. 选项 C 让 py2 直接崩 (UnicodeDecodeError on module load), 违反底线
4. 选项 B 违反用户拍板的"scripts/ 神圣冻结"原则; 可以**单独**起 patch 修 (M_P1_HELP_TEXTS_PHI_FIX), 但**不应**与本 patch 捆绑

**记录此 divergence 在 SESSION_HANDOFF §11 + 加 TODO follow-up patch**, 不阻塞本 patch tag milestone (但前提是先修 §2 critical bug).

---

## 4. ✅ 其他审查 — 全部正确

### 4.1 Rule 4 (isinstance str → _STR_TYPES)

```
scripts/core.py:64       — if not isinstance(node, str):
scripts/core.py:1956     — if not isinstance(node, str):
scripts/core_json.py:610 — if not isinstance(name, str) or not name:
```

```
scripts_2022/core.py:73       — if not isinstance(node, _STR_TYPES):
scripts_2022/core.py:1965     — if not isinstance(node, _STR_TYPES):
scripts_2022/core_json.py:619 — if not isinstance(name, _STR_TYPES) or not name:
```

3 处全转换 + helper inject ✅. py3 下 `_STR_TYPES == (str,)`, 行为完全等同 ✅.

### 4.2 Rule 5 (help_button.py defensive import)

`scripts_2022/RBFtools/ui/widgets/help_button.py` 顶部加 try/except + ASCII fallback ✅. `scripts/RBFtools/ui/widgets/help_button.py` 不动 ✅ — 符合 brief Rule 5 仅作用于 scripts_2022.

(注: 这是 scripts_2022 vs scripts 的**有意 functional difference**, 文档化于 brief §3, 不算 divergence.)

### 4.3 Phase 1 revert 完整性

```bash
git diff milestone/RBF-MQB-correct-2026-05-12..HEAD -- modules/RBFtools/scripts/
# 输出: 空 — scripts/ 字节级 = milestone ✅
```

4 个 revert commits (`2a41617` / `e5b06fe` / `ff40258` / `e345b59`) 干净抵消 v1/v2 改动.

### 4.4 .mod template (Phase 4)

`resources/module_template.mod`:
- linux/mac/win64 共 3 处 `MAYAVERSION:2022` 行均 `[r] scripts: scripts_2022` ✅
- 其他 5 个 MAYAVERSION 行 (2020/2023/2024/2025) 保持 `[r] scripts: scripts` ✅

### 4.5 drift detector + ASCII guard (Phase 6)

```
$ python tools/sync_2022_from_2025.py --check
OK: scripts_2022/ matches sync script output (51 py + 5 other files).
```

`find scripts_2022 -name '*.py' | xargs python decode-ascii-test` → 0 个文件含非 ASCII byte ✅.

### 4.6 EOL stability hotfix (1cd3d95 + 8cc90e3)

执行者主动识别并修复 EOL 漂移问题 (Windows autocrlf 让 main repo checkout CRLF, scripts/ 是 LF). `.gitattributes` 强制 scripts_2022 LF + repo_root_tidy 白名单加入 `.gitattributes` — 解决合理 ✅.

### 4.7 4/4 anchors

| Anchor | 验证 |
|---|---|
| TPS r≤0 oracle (C++) | scripts/ 不动 + .mll 不动 → 保留 ✅ |
| Honest-failure semantics | `isinstance(int, _STR_TYPES) == False` 仍 reject ✅; help_button fallback 主动 warning Not silent fallback ✅ |
| Column-rank defence (C++) | .mll 不动 ✅ |
| polyDim 1+d (C++) | .mll 不动 ✅ |

---

## 5. 评审结论

### 5.1 Land status

**12 commits LANDED** — 但 **scripts_2022/help_texts.py 有 8 处 critical bug 让 Maya 2022 py2 模式下 kernel 描述显示错乱**.

### 5.2 是否升级 milestone tag?

**NO** — 不升级. 现状不能算"完美落地" (用户底线).

### 5.3 必需的 Phase 7 hotfix

写新 brief `PATCH_BRIEF_M_P0_MAYA_VERSION_ISOLATION_PHASE7_UPREFIX.md` 派单给执行者:

1. 修 `tools/sync_2022_from_2025.py:181-232` 让 Rule 3 path 也触发 u-prefix promote
2. 跑 sync regen scripts_2022/
3. drift test 自动验证
4. 用户重打 installer + 重装 Maya 2022 + 实测 kernel 帮助气泡显示 `φ`(r) (不是 `φ(r)`)
5. 单 commit (fix + chore installer 分离)

### 5.4 已知 follow-up (可单独 patch, 不阻塞)

- **M_P1_HELP_TEXTS_PHI_FIX** (低优先级): Maya 2025 scripts/help_texts.py 显示 `Ï<ctrl>(r)` 而非 `φ(r)`. milestone state pre-existing 问题, 用户没报过, 但既然 Maya 2022 已修复, 一致性考虑可以同步修 scripts/. **需用户拍板**是否允许动 scripts/ (违反原"神圣冻结"原则).

---

## 6. 路径速查

| 文件 | 状态 |
|---|---|
| [tools/sync_2022_from_2025.py](../../tools/sync_2022_from_2025.py) (line 181-232 `_ascii_escape_string_token`) | **需修** — Rule 3 后未补 u-prefix |
| [modules/RBFtools/scripts_2022/RBFtools/ui/help_texts.py](../../modules/RBFtools/scripts_2022/RBFtools/ui/help_texts.py) (lines 241/246/249/253/257/264/271/278) | **8 处 bug** (sync regen 后自动修复) |
| [modules/RBFtools/scripts/RBFtools/ui/help_texts.py:241](../../modules/RBFtools/scripts/RBFtools/ui/help_texts.py) | milestone pre-existing display bug (follow-up patch, 不阻塞) |
