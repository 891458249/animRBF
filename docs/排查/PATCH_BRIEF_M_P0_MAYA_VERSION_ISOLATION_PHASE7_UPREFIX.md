# Patch Brief — M_P0_MAYA_VERSION_ISOLATION Phase 7 (hotfix)

> Planner / Architect 后续修复. 执行者照此实施.
>
> **Origin**: 2026-05-12 Planner audit ([AUDIT_M_P0_MAYA_VERSION_ISOLATION.md](AUDIT_M_P0_MAYA_VERSION_ISOLATION.md) §2) 发现 sync script Rule 2/3 顺序 bug — Rule 3 (`\xHH→\uXXXX` merge) 后, Rule 2 的 has_non_ascii 检查在已 ASCII-化的 body 上返回 False, **u 前缀未补**.
> **Status**: APPROVED — 等执行者实施.
> **Scope**: 极小. 改 1 个 Python 函数 (`_ascii_escape_string_token`), 跑 sync regen, drift test 自动验证, installer 重打.

---

## 1. 问题定义

### 1.1 现象

Maya 2022 py2 mayapy2 模式下 hover kernel 描述帮助 `?` icon, 气泡显示**字面文本** `φ` 而非 `φ`:

```
Linear kernel: φ(r) = r

The simplest kernel — weight falls off linearly with distance.
...
Cons: Not smooth at pose locations (C⁰ continuity only).
```

期望:
```
Linear kernel: φ(r) = r

The simplest kernel — weight falls off linearly with distance.
...
Cons: Not smooth at pose locations (C⁰ continuity only).
```

### 1.2 Root cause

[tools/sync_2022_from_2025.py:181-232](../../tools/sync_2022_from_2025.py) `_ascii_escape_string_token`:

```python
# Rule 3 first: merge \xHH (HH > 0x7F) sequences. This operates on
# the source-level body (escape sequences still as backslash text).
new_body = _merge_utf8_escapes(body)  # ← \xcf\x86 → φ (合并后 body 全 ASCII)

# Rule 2: any raw non-ASCII char in the (post-Rule-3) body becomes a
# \uXXXX or \UXXXXXXXX escape.
has_non_ascii = any(ord(c) > 127 for c in new_body)  # ← False, body 已全 ASCII
if has_non_ascii:                                     # ← 不进 branch
    ...
    if not (_is_bytes_prefix(prefix) or "u" in prefix.lower()):
        prefix = "u" + prefix                          # ← u 前缀不被加
```

py2 docs:
> `\uXXXX` escape sequence is **unique to Unicode literals**. 

非 u-literal 中 `φ` 是 6 个字面字符 `\` `u` `0` `3` `c` `6`, **不是** φ.

### 1.3 影响范围

[scripts_2022/RBFtools/ui/help_texts.py](../../modules/RBFtools/scripts_2022/RBFtools/ui/help_texts.py) **8 处 hit** (kernel 描述):

- line 241, 246 (Linear kernel)
- line 249, 253 (Gaussian 1)
- line 257 (Gaussian 2)
- line 264 (Thin Plate Spline)
- line 271 (Multi-Quadratic Biharmonic)
- line 278 (Inverse Multi-Quadratic Biharmonic)

非 help_texts.py 的 hits 全部是 `u"""..."""` 已加 u 前缀的 docstring (grep false positive on closing `"""`).

---

## 2. 修改清单 (执行者照搬)

### 2.1 修 sync 脚本

文件: `tools/sync_2022_from_2025.py`
函数: `_ascii_escape_string_token` (line ~181-232)

**当前** (line 216-230):

```python
# Rule 2: any raw non-ASCII char in the (post-Rule-3) body becomes a
# \uXXXX or \UXXXXXXXX escape.
has_non_ascii = any(ord(c) > 127 for c in new_body)
if has_non_ascii:
    escaped = []
    for c in new_body:
        cp = ord(c)
        if cp < 128:
            escaped.append(c)
        elif cp <= 0xFFFF:
            escaped.append("\\u{0:04x}".format(cp))
        else:
            escaped.append("\\U{0:08x}".format(cp))
    new_body = "".join(escaped)
    # Auto-prefix u if not already u/b
    if not (_is_bytes_prefix(prefix) or "u" in prefix.lower()):
        prefix = "u" + prefix

return prefix + quote + new_body + quote
```

**修改后**:

```python
import re  # 顶部已 import, 复用即可

# ... 上面 Rule 3 merge 不变 ...
new_body = _merge_utf8_escapes(body)

# Rule 2: any raw non-ASCII char in the (post-Rule-3) body becomes a
# \uXXXX or \UXXXXXXXX escape.
has_non_ascii = any(ord(c) > 127 for c in new_body)

# Phase 7 hotfix: Rule 3 may have produced \uXXXX / \UXXXXXXXX escapes
# from \xHH multi-byte sequences. py2 requires u-prefix for \u escapes
# to be recognised as unicode; without u-prefix, `φ` evaluates to
# 6 literal ASCII chars instead of phi. Auto-promote u-prefix whenever
# the post-Rule-3 body contains a unicode-escape sequence.
has_unicode_escape = bool(
    re.search(r'(?<!\\)(?:\\\\)*\\[uU][0-9a-fA-F]{4}', new_body)
)

if has_non_ascii:
    escaped = []
    for c in new_body:
        cp = ord(c)
        if cp < 128:
            escaped.append(c)
        elif cp <= 0xFFFF:
            escaped.append("\\u{0:04x}".format(cp))
        else:
            escaped.append("\\U{0:08x}".format(cp))
    new_body = "".join(escaped)

# Auto-prefix u if literal contains raw non-ASCII (Rule 2)
# OR post-Rule-3 unicode escapes (Phase 7 hotfix).
if (has_non_ascii or has_unicode_escape) and not (
        _is_bytes_prefix(prefix) or "u" in prefix.lower()):
    prefix = "u" + prefix

return prefix + quote + new_body + quote
```

**关键变化** (4 行 + 1 个 regex):
1. `has_unicode_escape` 检查 — 用 negative-lookbehind regex 避免误判 `\\u` (转义反斜杠后的 `u`, 不是 unicode escape)
2. u-prefix promote 触发条件: **either** `has_non_ascii` **or** `has_unicode_escape`

### 2.2 跑 sync regen scripts_2022/

```bash
cd X:/Plugins/RBFtools
python tools/sync_2022_from_2025.py
# 期望: OK: scripts_2022/ regenerated (51 py + 5 other files).
```

`git diff` 验证: 应看到 scripts_2022/RBFtools/ui/help_texts.py 8 处行加 `u` 前缀, 无其他改动.

### 2.3 验证

```bash
# 1. 验证 8 处 bug 消除
grep -cE '^\s+"[^"]*\\u[0-9a-fA-F]{4}' modules/RBFtools/scripts_2022/RBFtools/ui/help_texts.py
# 期望: 0

# 2. 验证全 scripts_2022 无该模式
grep -rEn '(^|[^uUbBrR_a-zA-Z])"[^"]*\\u[0-9a-fA-F]{4}' modules/RBFtools/scripts_2022/ \
    | grep -v 'u"""' | grep -v "u'''"
# 期望: 0 (排除 u""" 多行 docstring 的闭合 """ 误判)

# 3. drift test
python tools/sync_2022_from_2025.py --check
# 期望: OK

# 4. unit
python -m pytest modules/RBFtools/tests/unit/test_m_p0_maya_version_isolation_drift.py -v
# 期望: 2 passed

# 5. 全 sweep
python -m pytest modules/RBFtools/tests --continue-on-collection-errors -q
# 期望: 614 + new = passed, 0 回归
```

### 2.4 installer 重打

```bash
tools\build_installer.bat
# 期望: installer/RBFtoolsInstaller.exe mtime 更新
```

---

## 3. 不动什么 (negative space)

- ❌ 不动 `scripts/` (Maya 2025 神圣)
- ❌ 不动其他 sync 规则 (Rule 1/4/5/6/7)
- ❌ 不动 .mod template (Phase 4 已对)
- ❌ 不动 .mll / cmake / installer 内部逻辑
- ❌ 不动 git history (Policy A)
- ❌ 不引入新依赖

---

## 4. 验证

### 4.1 静态 (执行者本地, brief §2.3)

期望 8 处 hit → 0, drift OK, sweep 0 回归.

### 4.2 Maya 2022 实测 (用户)

1. 关 Maya 2022
2. 完全卸载旧 RBFtools (删 `~/Documents/maya/modules/RBFtools` + RBFtools.mod)
3. 重启电脑 (清 .pyc 缓存)
4. 跑新 installer
5. 启动 Maya 2022, 加载 RBFtools
6. **核心测试**: hover Linear / Gaussian / TPS / MQB / IMQB / ExpMap / SwingTwist 的 `?` icon
   - 期望气泡正确显示 `φ(r)`, `r²`, `√`, `∞`, `★`, `—`, `·` 等数学/装饰字符
   - **无字面 `φ` 等 escape 文本**

### 4.3 Maya 2025 防回归

scripts/ 完全未动, .mod MAYAVERSION:2025 仍路由 `scripts:` → scripts/. 0 回归. 仍不需重装 (共用 modules 目录).

---

## 5. 风险评估

| 风险 | 概率 | 影响 | 缓解 |
|---|---|---|---|
| `has_unicode_escape` regex 误判 `\\u` 转义双反斜杠 | 低 | u 前缀加得过多 (无害) | regex `(?<!\\)(?:\\\\)*\\[uU][0-9a-fA-F]{4}` 已考虑奇数反斜杠 |
| 修改顺序敏感, 改 sync 后未跑 regen | 中 | scripts_2022/ 未更新, drift test fail (CI gate) | drift test 强制 catch |
| 8 处 hit 之外仍有遗漏 | 低 | 用户报新 hit | brief §2.3 step 2 grep 全扫描 |

### 5.1 回退路径

```bash
git revert <fix_sha>  # revert sync script 改动
git revert <regen_sha>  # revert scripts_2022 regen
git revert <installer_sha>  # revert installer rebuild
```

3 commit 回退, 干净.

---

## 6. Commit 模板

### Commit 1 — fix(tooling)

```
fix(tooling): sync_2022_from_2025.py auto-promote u-prefix on \uXXXX escapes from Rule 3 merge (M_P0_MAYA_VERSION_ISOLATION Phase 7)

Phase 2 audit found 8 hits in scripts_2022/RBFtools/ui/help_texts.py
where Rule 3 merged \xHH multi-byte sequences (e.g. \xcf\x86) to \uXXXX
codepoint escapes but did not add u-prefix to the containing literal.
Without u-prefix, py2 evaluates φ as 6 literal ASCII chars
instead of phi -- breaking display of kernel formula in Maya 2022 py2
help bubbles.

Fix: extend Rule 2 has_non_ascii check to also trigger u-prefix when
post-Rule-3 body contains \uXXXX or \UXXXXXXXX escape (negative-
lookbehind to avoid \\u false positives).

Bug-fix scope: 1 function (_ascii_escape_string_token, ~10 lines).
Cascading regen of scripts_2022 in separate commit (Phase 7b).
Anchors held: 4/4.
Maya 2025 impact: 0 (sync only touches scripts_2022).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

### Commit 2 — chore(maya2022): regen scripts_2022

```
chore(maya2022): regen scripts_2022 with Phase 7 u-prefix fix (M_P0_MAYA_VERSION_ISOLATION Phase 7b)

Re-ran python tools/sync_2022_from_2025.py after Phase 7 sync fix.
Expected diff: 8 lines in scripts_2022/RBFtools/ui/help_texts.py
gain `u` prefix (kernel descriptions at lines 241/246/249/253/257/
264/271/278).

drift detector --check: OK.
```

### Commit 3 — chore(installer)

```
chore(installer): rebuild for M_P0_MAYA_VERSION_ISOLATION Phase 7

Installer rebuilt to pick up Phase 7 scripts_2022 regen.
mtime: <new>, size: <new>.
```

---

## 7. 完成后 Planner 评审 checklist

- [ ] commit 3 个, Phase ID 标注一致
- [ ] sync script 改动仅在 `_ascii_escape_string_token` (无 scope creep)
- [ ] grep `^\s+"[^"]*\\u[0-9a-fA-F]{4}'` scripts_2022/ → 0 hit
- [ ] drift test --check OK
- [ ] sweep 0 回归
- [ ] installer mtime/size 更新
- [ ] 用户 Maya 2022 实测帮助气泡 8 处 kernel 显示正确数学符号 (`φ` `²` `∞` `√` etc.)
- [ ] 4/4 anchors 保留 (Phase 7 不动 .mll, 不动 scripts/, 不动 isinstance/help_button defensive 路径)
- [ ] **若全 pass** → 升级 milestone tag `milestone/RBF-MQB-correct-2026-05-12-isolation-LANDED`

---

## 8. 关键文件路径

| 文件 | 操作 |
|---|---|
| [tools/sync_2022_from_2025.py](../../tools/sync_2022_from_2025.py) | **改** `_ascii_escape_string_token` (~10 行) |
| [modules/RBFtools/scripts_2022/RBFtools/ui/help_texts.py](../../modules/RBFtools/scripts_2022/RBFtools/ui/help_texts.py) | **regen** (sync auto-update 8 行) |
| `installer/RBFtoolsInstaller.exe` | **重打** |
