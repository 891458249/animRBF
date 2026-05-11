# RBFtools — 执行者会话交接文档

**日期**: 2026-05-12  
**Worktree**: `X:\Plugins\RBFtools\.claude\worktrees\nifty-neumann-4ae975`  
**当前 origin/main HEAD**: `3f10fea` (M_P0_RBF_COLUMN_RANK_DEFENSE chore deploy)  
**Main worktree**: `X:\Plugins\RBFtools` FF'd to `3f10fea`

---

## §0 — 会话目的: 解决 user 切换 kernel (MQB 等) 时 driven 关节飞 / kFailure

整条修复链跨 ~5 个 M_P0_*  patch, 从初步 retry-loop 防御到最终数学正确的 polynomial augmentation + column-rank defence.

---

## §1 — 已 land 完整 commit chain (since `ee6d63f` baseline)

```
3f10fea  chore(deploy)  M_P0_RBF_COLUMN_RANK_DEFENSE .mll v5 (188,416 B, polyDim 1+d + C lite)
d6f5c9b  fix(plugin)    M_P0_RBF_COLUMN_RANK_DEFENSE source (Path B + C lite)
fde4be7  chore(deploy)  M_P0_RBF_POLYNOMIAL_AUGMENTATION .mll v4 (186,368 B, audit-trail intermediate)
489fb34  fix(plugin)    M_P0_RBF_POLYNOMIAL_AUGMENTATION source (audit-trail intermediate, polyDim=1 for MQ)
fd5607b  chore(deploy)  M_P0_LAMBDA_RETRY_TIERED_CEIL .mll v3 (audit-trail)
4a3cae4  fix(plugin)    M_P0_LAMBDA_RETRY_TIERED_CEIL source (audit-trail, retry loop)
b16d117  chore(deploy)  M_P0_BOUNDED_LAMBDA_RETRY_FLOOR_1E5 .mll v1 (audit-trail)
8e7a6d3  fix(plugin)    M_P0_BOUNDED_LAMBDA_RETRY_FLOOR_1E5 source (audit-trail)
b7441d4  fix(ui)        M_P0_BATCH_DEFAULT_TRUE
f49628b  ROLLBACK_6     (audit doc + parity test + diag)
7e6c25f  ROLLBACK_5     (.mll dual deploy after ROLLBACK_1/2)
91adfc9  ROLLBACK_2     (remove auto-adaptive λ retry loop)
c924b1c  ROLLBACK_1     (TPS r≤0 → value)
ee6d63f  baseline       (M_P0_LAMBDA_CEIL_TIGHTEN, 折回点)
```

**所有 12 个 commits 都已 push 到 origin/main**. policy A 严守 (无 amend / rebase / reset / force).

---

## §2 — 数学修复路径演化 (供新执行者快速建立 mental model)

### 早期错误判断 (ROLLBACK chain 之后到 polynomial augmentation 之前)
- 假设根因是 K 矩阵病态 → 加 λ retry loop (8e7a6d3 / b16d117)
- λ ceil 不够 → 提高 ceil (4a3cae4 / fd5607b: 1e-5 strictly-PD / 1e-3 conditionally-PD)
- **仍 fail**: 用户 λ=1e-3 + MQB 仍飞 → 证明 λ ceil 不是真根因

### 数学正确诊断 (489fb34 起)
研究报告 (`docs/源文档/RBF 算法多驱动控制研究.docx`) + Gemini 架构师评审锁定真根因:
- **MQB / IMQB / TPS / Linear 是条件正定 (CPD) 核**
- CPD 核必须**多项式增强 (polynomial augmentation)** 才唯一可解:
  ```
  [ K + λI   P  ] [ w ]   [ y ]
  [ P^T      0  ] [ a ] = [ 0 ]
  ```
  其中 P 是多项式基底矩阵 (1, x_0, x_1, ..., x_{d-1}) 每个 pose 求值
- 数学依据: **Wendland 2004 §10 (Thm 10.3 唯一性)**, Schaback 1995, Wahba 1990
- 工业标准: SciPy `RBFInterpolator`, PyGeM "Multi-Quadric Biharmonic" 都默认 polyDim = 1 + d

### 489fb34 半修复 (polynomial augmentation, polyDim 不够)
- 加 `getPolynomialDim` / `polyBasis` helpers
- 加 `BRMatrix polyMat` 私有成员
- 改 solver: polyDim=0 (Gaussian) Cholesky/GE; polyDim>0 (CPD) augmented GE
- **半修复**: MQB polyDim=1 (strict-CPD-minimum, 仅 constant), 用户实测**仍 kFailure** (cols 0-2 共线问题)

### 3f10fea / d6f5c9b 完整修复 (Path B + C lite 双管齐下)
- **Path B**: 升级 MQB / IMQB / Linear polyDim 从 1 → 1 + d (匹配 SciPy/PyGeM)
- **C lite**: 解算前扫描 matPoses 列方差, var < 1e-8 的列从 P 剔除 + polyMat 零填回扩展
- **数学正当**: CPD 唯一性只要求 P 含 π_{m-1} 基底, 加更多 polynomial 不破坏唯一性 (只需 P 全列秩, C lite 保证)
- **零 Runge 风险**: degree-1 linear polynomial 不产生 oscillation
- **Inference 0 改动**: dropped polyMat 行 = 0, 自然在 polyBasis · polyMat 中贡献 0

---

## §3 — 当前 build artifact 状态 (用户即将测试)

| Path | mtime | size | 含 |
|---|---|---|---|
| `installer\RBFtoolsInstaller.exe` | **2026-05-12 02:03** | **14,868,566 B** | 完整修复链 (含 d6f5c9b polyDim 1+d + C lite) |
| `modules\plug-ins\win64\2022\RBFtools.mll` | 2026-05-12 02:00:14 | 188,416 B | sha256 `E869AA88...20C0E4A` |
| `modules\plug-ins\win64\2025\RBFtools.mll` | 2026-05-12 02:01:10 | 188,416 B | sha256 `DF3CC02A...82F3996` |

**用户下一步操作**:
1. 关 Maya (释放 .mll 文件锁)
2. 跑 `installer\RBFtoolsInstaller.exe` → Install
3. 重启 Maya
4. 实测切 MQB / IMQB / TPS + Apply → **期望**: 不再 kFailure, driven 不飞, 训练点 max\|Δ\| < 1e-3
5. 若仍 fail: 提供 cmds.warning 输出 (其中包含 "M_P0_RBF_COLUMN_RANK_DEFENSE — dropping N degenerate driver column(s) [variance < 1e-08] from polynomial augmentation P matrix..." 信息), 用于诊断

---

## §4 — 用户 reproducer 数据 (核心 case)

```
RBFnode_shoulder_LShape  (22 poses, 9-dim Raw encoding, multi-driver)
Kernel: MQB (kernelType = 4)
User lambda: 1e-7 (manual, low)

Pose data (22 × 9):
- Cols 0-2 (Driver 1):
  - 18/22 poses: bit-identical (2.57e-7, -1.49e-6, -9.92e-8) — rest pose
  - 4 outliers (Index 15/16/20/21): real signal (0.01-0.81 magnitude)
- Cols 3-5 (Driver 2): mixed pattern
- Cols 6-8 (Driver 3): mixed pattern

Pre-fix failure: "RBF system singular at user lambda = 1e-07,
                  kernel index = 4, polyDim = 1. Last singular pose
                  index: 7"

Expected post-fix:
- C lite detects cols 0-2 of matPoses are degenerate (var < 1e-8 after normalize)
- Drops them from P (P shrinks from 22×10 to 22×7)
- Augmented system (22+7)×(22+7) solves
- Once-per-rig warning: "M_P0_RBF_COLUMN_RANK_DEFENSE — dropping 3
                         degenerate driver column(s) [variance < 1e-08]
                         from polynomial augmentation P matrix.
                         Driver index (0-based, post-encoding) dropped:
                         0, 1, 2. ..."
- driven 关节正常驱动
```

---

## §5 — 严守 policy (新执行者必读)

### Policy A — Git history immutable
- ❌ `git commit --amend` / `git rebase` / `git reset` / `git push --force`
- 所有修复 chain 都保留 (即使中间 commit 已被后续 commit superseded)
- Audit history > clean history

### Policy B — Scope discipline
- 单 commit 单点, fix commit 与 chore(deploy) commit 分离
- 清洁项 (Unicode 替换 / format 调整 / 等) 单独 `chore` commit
- 禁止 在 fix commit 内夹带 unrelated 改动

### Policy C — SSH push only
- Remote: `git@github.com:891458249/animRBF.git`
- HTTPS 被 CN middlebox 阻断
- 用户 `~/.ssh/config` 已配置 `Host github.com / Hostname ssh.github.com / Port 443`
- `git push --no-tags` (注意 `--no-tags` 不是 `--tags=false`, 后者是错误语法)

### 必须保留的功能 (任何后续 patch 0 触动)
- ✅ ROLLBACK_1 TPS r≤0 → value (c924b1c, in interpolateRbf)
- ✅ 5 prev-tracker (M_P0_TRAINING_AFFECTING_ATTRS) — UX auto-retrain
- ✅ Python `_TRAINING_AFFECTING_ATTRS` frozenset (M_P0_TRAINING_ATTRS_FORCE_RETRAIN)
- ✅ M_P0_BATCH_DEFAULT_TRUE (b7441d4, tabbed_source_editor)
- ✅ cpp schema regularization setDefault(1.0e-5) (8e7a6d3)
- ✅ Multi-driver quat RBF / B1 QWA / B2 nlerp / poses I/O / etc.

---

## §6 — 测试体系 (新执行者参考)

**Unit tests** (`modules/RBFtools/tests/unit/`):
```
test_batch_default_true.py         (4 tests)  — M_P0_BATCH_DEFAULT_TRUE
test_kernel_rollback_parity.py     (8 tests)  — M_P0_KERNEL_SWITCH_ROLLBACK
test_lambda_retry_tiered_ceil.py   (6 SKIPPED) — audit-trail (intermediate, superseded)
test_polynomial_augmentation.py    (8 tests)  — M_P0_RBF_POLYNOMIAL_AUGMENTATION
test_column_rank_defense.py        (8 tests)  — M_P0_RBF_COLUMN_RANK_DEFENSE
```
**全 unit**: 28 passed + 6 skipped = 34 collectable

**Full sweep**: `python -m pytest modules/RBFtools/tests --continue-on-collection-errors -q`
- 612 passed, 32 skipped, 50 errors (pre-existing mayapy collection issues, **与本会话改动无关**), 14 subtests passed

**Phase 5 行为验证** (mayapy / Maya GUI):
- `modules/RBFtools/tests/scratch/diag_kernel_rollback.py` — 6 kernel × 20 pose × 10 joint × 9 attr CSV diff vs oracle (`X:\RBFtools`), max\|Δ\| < 1e-3
- Phase 5 是用户驱动测试 (执行者本地无 mayapy 环境)

---

## §7 — Oracle 锚点 (回退基线参考)

- **Oracle path**: `X:\RBFtools` (用户备份, 切 kernel 不飞)
- **Oracle 行为 sha 锚点**: `≈ e249ec0` (= 156af4c~1, M_P0_AUTO_ADAPTIVE_LAMBDA λ retry loop 引入前)
- **Oracle Python sha 锚点**: `< f2a3d0b` (M_P0_CREATE_NODE_REGULARIZATION 引入前)
- **Oracle 文件 SHA256**:
  - RBFtools.cpp: `D6DCCB57...01DC7`
  - RBFtools.h: `AF8E1597...98B0`
  - controller.py: `091441C1...5FE8`
- **Oracle 行为锚点 4/4**:
  - TPS r≤0 = `value` (本会话已 ROLLBACK_1 恢复)
  - λ retry loop 不存在
  - C++ prev-tracker 仅 oracle 既有 (4c379ad 新增的 5 个 prev-tracker 保留为 UX, 未回退)
  - Python `_TRAINING_AFFECTING_ATTRS` 不存在 (保留为 UX, 未回退)

详 `docs/排查/M_P0_KERNEL_SWITCH_ROLLBACK_index.md` §0.5.

---

## §8 — 研究报告 + Gemini 建议 (信息源)

### 研究报告
`docs/源文档/RBF 算法多驱动控制研究.docx` (157 段, ~3 MB)

关键引用:
- § 1: "对驱动源集合 V 进行**去重检查和共线性校验**, 引入微小的随机噪声 (Jittering) 打破近邻数值危机"
- § 3: "正则化与多项式项的**双保险**" (Tikhonov + polynomial augmentation)
- § 4 应用案例: 心脏 FSI / 航空航天 / 人体碰撞模拟

### Gemini 架构师评审 (3 轮)
1. **初评**: 推 C lite + SVD Tier 3
2. **回应作 scope 建议**: 推迟 SVD (Eigen 依赖 + 复杂度), 仅 C lite
3. **拍板 Option II**: ACK C lite + Path B 联合; 推翻"Runge 担忧"; 引用 PyGeM `n+1+3` 工业标准

---

## §9 — 未完成 / 后续候选 patch (按优先级)

### P1 (high, 待用户实测反馈)
1. **用户重装 installer 后 MQB / IMQB / TPS 测试**:
   - 期望: 不再 kFailure, driven 不飞
   - 若 still fail: 看 Maya Script Editor 中 `M_P0_RBF_COLUMN_RANK_DEFENSE — dropping ... driver column(s)` warning 内容, 用于诊断
   - Phase 5 数据等价性 CSV diff (max\|Δ\| < 1e-3) — 用户跑 `diag_kernel_rollback.py`

### P2 (medium, 设计已论证, 等触发条件)
2. **M_P0_RBF_SVD_TIER_3** — 商业级 robustness fallback
   - Eigen 依赖引入 (cmake + dual SDK build verify)
   - Tier 3: 检测 cond(K) → JacobiSVD with threshold
   - 触发条件: 用户 case 在 Path B + C lite 后仍 fail, 或 driver count > 2000 场景
   - LoC 估 ~120 + 50 test + Eigen 链接

### P3 (low, 待用户报告)
3. **Maya 2025 file dialog hang** (M_P0_FILE_DIALOG_HANG)
   - User 之前报 export_poses_to_path 通过文件对话框时挂起
   - 还未诊断: 是 cmds.fileDialog2 慢路径 (X: 盘扫描) 还是 export 函数本身
   - 等用户实测直接调 export_poses_to_path 结果

### P4 (low, UI/UX)
4. **per-kernel polyDim 配置** — 让用户在 UI 上覆盖 polyDim default
   - 当前 hard-code 1+d for CPD, 0 for Gaussian
   - 加 controller attr "Polynomial Degree" combo (Constant / Linear / Auto)

---

## §10 — 新执行者第一动作 checklist

进入 worktree `X:\Plugins\RBFtools\.claude\worktrees\nifty-neumann-4ae975` 后立刻执行:

```bash
# Step 0 同步
git fetch origin
git rev-parse HEAD                    # 期望: 3f10fea
git rev-parse origin/main              # 期望: 3f10fea
git status --short                     # 期望: 仅 ?? source/build_check{,_2022}/

# Step 0.5 验证 .mll + installer 实测就位
ls -la modules/RBFtools/plug-ins/win64/2022/RBFtools.mll  # 期望 188,416 B / 2026-05-12 02:00
ls -la modules/RBFtools/plug-ins/win64/2025/RBFtools.mll  # 期望 188,416 B / 2026-05-12 02:01
ls -la /x/Plugins/RBFtools/installer/RBFtoolsInstaller.exe  # 期望 14,868,566 B / 2026-05-12 02:03

# Step 0.6 跑 unit sweep 验证 0 回归
python -m pytest modules/RBFtools/tests/unit/ -v   # 期望 28 passed + 6 skipped
python -m pytest modules/RBFtools/tests --continue-on-collection-errors -q   # 期望 612 passed
```

若任一不符 → 上报 Planner, 不主动修复.

---

## §11 — 上下文累积 (本会话覆盖的所有 M_P0_* patch 索引)

| Patch | sha | 状态 | 描述 |
|---|---|---|---|
| M_P0_DUPLICATE_POSE_DETECT | (early) | landed | Python 层 row-level pose dup 检测, 1e-7 tol |
| M_P0_BLEND_SHAPE_TYPO_FIX | (early) | landed | typo `is_blend_shape` → `is_blendshape` |
| M_P0_QUATERNION_HONEST_DISCLOSURE | 78c15a4 | landed | outputEncoding forward-compat UI tooltip |
| M_P0_QUATERNION_BACKEND_LAND | ce136dd / 3d2d095 | landed | outputEncoding Quat/ExpMap inverse transform |
| M_P0_OUTPUT_EXPMAP_FIX | eb27d68 / 95d3a37 / 8004606 | landed | ExpMap dispatch enum bug |
| M_P0_KERNEL_SWITCH_ROLLBACK 1/2/5/6 | c924b1c / 91adfc9 / 7e6c25f / f49628b | landed | TPS r≤0 oracle revert + λ retry remove + .mll deploy + docs |
| M_P0_BATCH_DEFAULT_TRUE | b7441d4 | landed | tabbed source editor 默认 batch=True |
| M_P0_BOUNDED_LAMBDA_RETRY_FLOOR_1E5 | 8e7a6d3 / b16d117 | **superseded** | uniform 1e-5 ceil retry, 半修复 |
| M_P0_LAMBDA_RETRY_TIERED_CEIL | 4a3cae4 / fd5607b | **superseded** | tiered 1e-5/1e-3 retry, 仍半修复 |
| M_P0_RBF_POLYNOMIAL_AUGMENTATION | 489fb34 / fde4be7 | **superseded by polyDim 1+d upgrade** | CPD math 引入, polyDim=1 for MQ |
| **M_P0_RBF_COLUMN_RANK_DEFENSE** | **d6f5c9b / 3f10fea** | **CURRENT** | polyDim 1+d + variance-floor col drop |

---

## §12 — 工作流模板 (新执行者照搬)

每次 patch 标准流程:
1. **实证调研** (Step 1) — grep 现状 + 读相关段
2. **数学/UX 设计 review** — 与 Planner 交流 (gemini), 等 ACK 后动代码
3. **C++ source + test 改动** (commit 1 `fix(plugin):`)
4. **dual .mll build** (cmake build_check_2022 + build_check, 串行避 race)
5. **deploy .mll + parity 验证** (commit 2 `chore(deploy):`)
6. **push 2-commit FF block** `git push --no-tags origin claude/...:main`
7. **main worktree FF pull** `git -C /x/Plugins/RBFtools pull --ff-only origin main`
8. **installer rebuild** (`tools\build_installer.bat`)
9. **状态汇总报告** — 等用户实测反馈

---

## §13 — 用户偏好 (Persona / 习惯)

- 中文回复
- LaTeX-first 数学推导 (用 `$ ... $` / `$$ ... $$`)
- HEREDOC commit messages
- Co-Authored-By trailer: `Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>`
- 严守"老版本 working 是 oracle"哲学
- 重要决策 (e.g. amend / scope creep / non-trivial trade-off) 必须等 Planner ACK 才动手
- 接受适度 audit-trail noise (多个 superseded commit 留在 history) > clean history

---

## 完毕

新执行者: 进 worktree → 跑 Step 10 checklist → 等用户实测 MQB 反馈. 若 fail → 看 warning 输出诊断. 若 pass → 等下一任务.
