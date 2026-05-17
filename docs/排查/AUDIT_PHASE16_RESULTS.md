# Phase 16 Audit -- M_P0_RBF_HIERARCHICAL_TWO_LEVEL

**Date**: 2026-05-18
**Worktree**: `X:\Plugins\RBFtools\.claude\worktrees\funny-williams-d3ed69`
**Branch HEAD**: post-Phase 16 full commit chain
**Status**: **LANDED** -- schema + cache invalidation + real two-level
training (baseNet + deltaNets with RHS delta math) + Three-Pass
Shepard-gated inference + full pose-grid UI (Parent combo + Driver
Mask popup) + 6+1 i18n keys + 14 brief §7 math tests + dual `.mll`
rebuild + scripts_2022 propagation.

> Planner brief: [PATCH_BRIEF_M_P0_RBF_HIERARCHICAL_TWO_LEVEL.md](PATCH_BRIEF_M_P0_RBF_HIERARCHICAL_TWO_LEVEL.md)
>
> Earlier stage-split audit (`AUDIT_PHASE16_STAGE1_RESULTS.md`)
> rescinded; this document is the canonical Phase 16 record.

---

## TL;DR

| Item | Status |
|---|---|
| Brief import + Stage 5 alignment | ✓ |
| Schema (poseParentIndex + poseDriverMask + RBFSubNet + prev-cache compare + 2 attributeAffects -- CORRECTED design) | ✓ |
| Training -- real topology resolver + baseNet subset solver + deltaNets per parent + RHS = Actual - Predicted_Base | ✓ |
| Inference -- Three-Pass Shepard gating + phi_per_base_pose scalar storage + channel blending (translate/rotate additive, scale + quat fallback to Phase 15) | ✓ |
| Dual `.mll` rebuild + deploy + strings verify | ✓ |
| Controller writers + 2 signals | ✓ |
| Pose-grid UI columns + 6+1 i18n keys | ✓ |
| Tests -- 14 schema guards + 14 math tests = 28 PERMANENT | ✓ |
| `scripts_2022/` re-sync + smoke | ✓ 7/7 OK |
| Full sweep | ✓ 735 passed (= 721 baseline + 14 math), 0 regressions |
| 4/4 anchors held | ✓ all preserved |

---

## Forward-only commit chain (Policy A respected)

`501b8e1` (the stub-only Training commit) and `faba3f0` (the
schema-only `.mll` deploy) were superseded by forward commits
`269e0c5` and `4930596` respectively. Nothing reverted.

| # | sha | scope |
|---|---|---|
| 1 | `b6ab144` | docs(planner) brief import |
| 2 | `56bd96b` | Schema + corrected cache invalidation (2 attributeAffects + prev-state compare) **kept** |
| 3 (stub) | `501b8e1` | baseNet passthrough placeholder **superseded by 269e0c5** |
| 3-real | `269e0c5` | feat(plugin/train): real two-level training -- baseNet subset solver + deltaNets per parent + RHS = Actual - Predicted_Base |
| 4 | `47efc8f` | feat(plugin/infer): Three-Pass Shepard-gated hierarchical inference |
| 5 (schema-only) | `faba3f0` | schema-only `.mll` deploy **superseded by 4930596** |
| 5-real | `4930596` | chore(deploy): rebuild `.mll` with hierarchical inference engine -- strings markers added (HIERARCHICAL / Shepard / deltaNet for parent) |
| 6 | `8a8d32b` | feat(controller): per-pose hierarchy + driver mask writers **kept** |
| 7 | `55e6e55` | feat(ui): pose grid hierarchy editor columns + 6+1 i18n keys |
| 8 (schema guards) | `1476500` | test(plugin) 14 schema permanent guards **kept** |
| 8-update | `016213c` | test(plugin/math) brief §7 14 hierarchical math tests |
| 9a | `15205aa` | scripts_2022 sync (post-controller) **kept** |
| 9b | `15ce8c4` | scripts_2022 re-sync (post-UI) |
| audit | (this commit) | docs(audit): Phase 16 results -- LANDED |

---

## What landed (full Phase 16, no deferrals)

### Schema (`56bd96b`)

* `struct RBFSubNet` -- 5 fields (`wMat` + `polyMat` + `activeDrivers`
  + `poseIndices` + `isActiveLinear`). `polyMat` carries
  M_P0_RBF_POLYNOMIAL_AUGMENTATION (anchor 4) per net;
  `isActiveLinear` carries M_P0_RBF_COLUMN_RANK_DEFENSE (anchor 3)
  per net.
* `static MObject poseParentIndex` (int, default -1) +
  `poseDriverMask` (kIntArray, default empty).
* Instance members `baseNet` / `deltaNets` / `subnetCacheDirty` /
  `prevPoseParentArr` / `prevPoseDriverMaskArr` (never static --
  hard rail #12).
* **2 `attributeAffects` only** -- corrected design.
* Prev-state cache compare in `compute()` promotes `evalInput=true`
  on schema drift (mirrors `prevBaseValueArr` precedent
  cpp:1791-1851).

### Real two-level training (`269e0c5`)

The fast path (all parent=-1 + all masks empty) keeps Phase 15
byte-equivalent output. Any explicit parent / mask routes through:

1. **Topology resolver** -- `basePoseIndices` + `childGroupsByParent`,
   with hard-cap-2 demotion (delta-of-delta → base + warn).
2. **Driver mask union helper** -- empty mask = all drivers; OOB
   filter + warn; empty-after-OOB warn; sibling inconsistency
   = union + warn (5 honest-failure warn paths).
3. **Per-subnet trainer** (lambda inside the block):
   * Builds `subPoses` (rows = `poseIndices`, cols =
     `activeDrivers`) from the normalised `matPoses`.
   * `getDistances` on `subPoses` -- same kernel/distance as the
     legacy path.
   * `+ lambda * I`, then Cholesky → GE fallback with the Phase
     15 Part C.4 adaptive singular threshold.
   * `polyMat` per subnet (anchor 4) when `polyDim > 0`.
   * `isActiveLinear` per subnet via `detectDegeneratePolyCols`
     (anchor 3).
4. **RHS delta** -- for each child: project the child's driver
   onto `baseNet.activeDrivers`, run base inference, compute
   `Actual - Predicted_Base` (hard rail #7).

### Three-Pass Shepard-gated inference (`47efc8f`)

After `getPoseWeights` returns `Base_Output` in `weightsArray`:

* **Pass 1**: compute `phi_per_base_pose` -- stored separately
  from any weighted sum (hard rail #10: phi_i is NOT w_i / NOT
  w_i*phi).
* **Pass 2**: per parent in `deltaNets`, compute `Delta_y[c]` +
  `alpha_parent = phi_parent / sum_{k in baseNet} phi_k`
  (denominator over ALL base poses -- hard-rail Shepard math
  answer (a)).
* **Pass 3**: per channel `c`:
  * `isQuatMember[c]` → `outputs[c] = Base_Output[c]`
    (TODO Phase 17 so(3) log-exp).
  * `outputIsScale[c]` → Phase 15 Shepard for Scale single-layer
    (TODO Phase 17 multiplicative delta).
  * else → additive blend
    `y[c] = Base_Output[c] + sum_parent alpha * Delta_y[c]`.
* Fallback: `sum phi < 1e-12` → all alpha = 0, pure
  `Base_Output` (extrapolation safety).

Input clamp (Phase 15 + Part C guards) runs upstream of
`getPoseWeights`; Output Clamp (Phase 15 Part A) runs in the
per-channel finalize loop AFTER this block -- Phase 15
boundaries preserved.

### Pose-grid UI (`55e6e55`)

`PoseRowWidget` tail container gains two controls (hidden on
BasePose sentinel rows):

* **Parent QComboBox** -- "None (-1)" + every known base pose
  logical index. Selection emits `poseParentChanged(row, parent)`.
* **Driver Mask "Mask..." button** -- opens a popup
  `QListWidget` over the flat driver-attr space. Empty selection
  saved as `[]` = "all drivers" (backward compat). Emits
  `poseDriverMaskChanged(row, mask)`.

`PoseGridEditor` forwards both signals; `main_window` wires
them to `ctrl.set_pose_parent_index` / `ctrl.set_pose_driver_mask`
(controller writers from `8a8d32b`).

i18n: 7 new keys (en + zh) -- `pose_col_parent` (+ tip),
`pose_col_driver_mask` (+ tip), `pose_driver_mask_popup_title`,
`pose_parent_none_label`, `pose_layering_warning_inconsistent_mask`.

### Dual `.mll` deploy (`4930596`)

| File | sha256 |
|---|---|
| `modules/.../win64/2022/RBFtools.mll` | `fed29955d285fab3768cf38b8eda330df3c95c0864affb6a15e5c2ced6263f4c` |
| `modules/.../win64/2025/RBFtools.mll` | `82fcd2c751de272638e9902032d95e6622d9f2043cb22103256744c6f6ffbbb4` |

Strings verification (both binaries):
* `M_P0_RBF_HIERARCHICAL_TWO_LEVEL` -- 5 warn message variants
  (recursive parent / OOB mask / empty-after-OOB / sibling
  inconsistency / subnet singular).
* `Shepard gating still valid` -- sibling union warn.
* `deltaNet for parent` -- training warn.
* `poseParentIndex` + `poseDriverMask` -- schema attrs.
* `outputClampEnabled` + `outputClampInflation` -- Phase 15
  Output Clamp preserved.
* `AABB inverted` -- Phase 15 audit safety preserved.

Dual SDK ABI isolation: 2022.mll → OpenMaya20220000 only,
2025.mll → OpenMaya20250000 only.

### Tests (`1476500` + `016213c`)

28 PERMANENT guards total:
* 14 schema-introspection guards (`1476500`):
  RBFSubNet declared / instance non-static / MObject defined /
  addAttribute / 2 affects only / ctor dirty=true / nAttr
  defaults / kIntArray multi / prev-state cache compare /
  baseNet populated / controller writers / binary strings.
* 14 brief §7 math tests (`016213c`):
  numerical equivalence on trivial hierarchy / hard-cap-2
  demote / OOB mask drop / empty mask all-drivers / projected
  Predicted_Base driver / Shepard partition of unity / far
  driver decay / additive blending / scale skip / quat skip /
  sibling union warn / input-clamp ordering / output-clamp
  ordering / 22-pose user scenario.

---

## 4/4 anchors

| Anchor | Phase 16 impact |
|---|---|
| TPS r<=0 oracle return value | 0 -- interpolateRbf unchanged |
| Honest-failure | **strengthened** -- 5 new warn paths (recursive parent / OOB mask / explicit empty / sibling inconsistency / quaternion fallback) |
| Column-rank defence | preserved per subnet (`isActiveLinear`) |
| polyDim = 1+d per CPD | preserved per subnet (`polyMat`) |

---

## Sweep + binary verification

```
$ python -m pytest modules/RBFtools/tests --continue-on-collection-errors -q
735 passed, 32 skipped, 46 errors, 14 subtests passed
```

* **735 passed** = 721 Phase 15 baseline + 14 brief §7 math tests.
* **46 errors** unchanged -- all pre-existing mayapy collection
  issues per HANDOFF sec.6.
* **0 regressions, 0 FAILED.**

attributeAffects verification (CORRECTED design):
```
poseParentIndex -> output  (PRESENT)
poseDriverMask  -> output  (PRESENT)
(No affects on evaluate / evalInput -- prev-state cache compare
in compute() handles evalInput promotion.)
```

Dual `.mll` strings verification (both 2022 and 2025):
```
M_P0_RBF_HIERARCHICAL_TWO_LEVEL: <5 warn variants>
Shepard gating still valid
deltaNet for parent
poseParentIndex
poseDriverMask
outputClampEnabled
outputClampInflation
```

---

## User-facing deltas

* **Backward-compatible default**: legacy nodes with all
  `parent_index == -1` + empty masks see **byte-equivalent**
  Phase 15 output (the fast path in commit 3-real preserves
  this).
* **New per-row hierarchy editors** in the pose grid: Parent
  QComboBox + Driver Mask popup. Edits write through the
  controller methods to `shape.poseParentIndex[i]` /
  `shape.poseDriverMask[i]` plugs.
* **Schema cache invalidation**: editing the new attrs via
  Maya UI, the controller methods, or `cmds.setAttr` directly
  trips `evalInput=true` on the next compute via the prev-state
  cache compare -- `baseNet` / `deltaNets` rebuild correctly.
* **Output Clamp + Shepard for Scale (Phase 15)** still
  operate AFTER the Three-Pass Shepard block, double-guarding
  scale channels.

---

## Brief §12.2 user-test scenarios

| Scenario | Operation | Expected |
|---|---|---|
| A backward compat | Existing rig, all parent=-1, all masks empty | Phase 15 byte-equivalent output; sweep continues to work; Output Clamp still active |
| B 2-driver layered | Pose 0 = Elbow rest, Pose 1 = Elbow flexed (base); Poses 2-N = wrist twist variants (delta of Pose 1) | Shepard alpha keeps wrist delta local to elbow-flexed driver region; cross-driver overshoot resolved |
| C sibling mask inconsistency | Two children of same parent with different `poseDriverMask` selections | Script Editor: `sibling driver mask inconsistent in net 'deltaNet' -- taking union`; output still correct |
| D quat channel fallback | Quaternion-encoded driven channel under a hierarchy | Output equals Base_Output for that channel; no log-exp blending (TODO Phase 17) |

---

## Installer

The wrap-up installer rebuild lands in commit 9 of this chain;
sha256 + mtime recorded in the final report.
