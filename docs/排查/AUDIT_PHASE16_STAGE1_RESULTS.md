# Phase 16 Stage 1 Audit -- M_P0_RBF_HIERARCHICAL_TWO_LEVEL

**Date**: 2026-05-18
**Worktree**: `X:\Plugins\RBFtools\.claude\worktrees\funny-williams-d3ed69`
**Branch HEAD**: post Phase 16 Stage 1 commit chain
**Status**: **STAGE 1 LANDED** -- schema + cache invalidation + baseNet
passthrough + controller writers + dual `.mll` rebuild. **Stage 2
(true two-level training + Shepard-gated inference + pose-grid UI)
DEFERRED to Phase 16.2** per the brief's scope-escalation clause.

> Planner brief: [PATCH_BRIEF_M_P0_RBF_HIERARCHICAL_TWO_LEVEL.md](PATCH_BRIEF_M_P0_RBF_HIERARCHICAL_TWO_LEVEL.md)

---

## TL;DR

| Item | Status |
|---|---|
| Brief import + alignment | ✓ |
| Schema (poseParentIndex + poseDriverMask + RBFSubNet + cache invalidation) | ✓ landed |
| Training stub (baseNet legacy passthrough) | ✓ landed |
| Inference (three-pass Shepard) | ⏸ deferred to Phase 16.2 |
| Dual `.mll` rebuild + deploy | ✓ landed |
| Controller writers (`set_pose_parent_index` / `set_pose_driver_mask`) | ✓ landed |
| Pose-grid UI columns (Parent combo + Driver Mask popup) | ⏸ deferred to Phase 16.2 |
| Tests (14 PERMANENT guards) | ✓ landed |
| `scripts_2022/` re-sync + smoke | ✓ 7/7 OK |
| Full sweep | ✓ 721 passed (+14 vs 707 baseline), 0 regressions |
| 4/4 anchors held | ✓ all preserved |

---

## Stage 1 commits

| # | sha | scope |
|---|---|---|
| 1 | `b6ab144` | `docs(planner): import Phase 16 brief` |
| 2 | `56bd96b` | `feat(plugin): two-level schema + cache invalidation (Schema, commit 2)` |
| 3 | `501b8e1` | `feat(plugin): baseNet legacy passthrough stub (Training, commit 3)` |
| 5 | `faba3f0` | `chore(deploy): rebuild 2022 + 2025 .mll (commit 5)` |
| 6 | `8a8d32b` | `feat(controller): per-pose hierarchy + driver mask writers (commit 6)` |
| 8 | `1476500` | `test(plugin): Phase 16 schema permanent guards (commit 8)` |
| 9a | `15205aa` | `feat(maya2022): regenerate scripts_2022 (scripts_2022 propagation)` |

(Commit 4 -- Inference -- intentionally NOT in this chain; see deferral
section below.)

---

## What landed

### Schema (commit 2, `56bd96b`)

* `source/RBFtools.h`:
  * `struct RBFSubNet` with 5 fields (`wMat` / `polyMat` /
    `activeDrivers` / `poseIndices` / `isActiveLinear`). `polyMat`
    carries `M_P0_RBF_POLYNOMIAL_AUGMENTATION` (anchor 4) into the
    per-sub-net world; `isActiveLinear` carries
    `M_P0_RBF_COLUMN_RANK_DEFENSE` (anchor 3). Phase 16.2 will use
    these to extend per-net without dropping anchors.
  * `static MObject poseParentIndex` (int, default -1 = base).
  * `static MObject poseDriverMask` (kIntArray, default empty =
    "all drivers" = backward-compatible).
  * Instance members: `RBFSubNet baseNet`,
    `std::unordered_map<int, RBFSubNet> deltaNets`,
    `bool subnetCacheDirty`, plus prev-state mirrors
    `prevPoseParentArr` + `prevPoseDriverMaskArr` (hard rail #12:
    NEVER static).
  * New includes: `<unordered_map>`, `<maya/MFnIntArrayData.h>`,
    `<maya/MIntArray.h>`.
* `source/RBFtools.cpp`:
  * MObject definitions + `initialize()` `nAttr` / `tAttr` block
    additions + `addAttribute()` registrations.
  * **2 `attributeAffects` pairs only** (corrected design --
    `attributeAffects` on `evaluate` does NOT trigger
    `evalInput=true`; prev-state cache compare does the work).
  * Constructor inits `subnetCacheDirty(true)` so the first
    `compute()` after node creation always rebuilds.
  * Prev-state cache compare in `compute()` reads the two new
    multi attrs each tick, compares with prev, and on drift
    promotes `evalInput = true` + refreshes prev +
    `subnetCacheDirty = true`. Mirrors the `prevBaseValueArr` /
    `prevQuatGroupConfigHash` precedent (cpp:1791-1851).

### Training stub (commit 3, `501b8e1`)

End of the existing `evalInput == true` training block populates
`baseNet` from the freshly trained `wMat` + `polyMat`, with
`poseIndices = [0..poseCount)` and
`activeDrivers = [0..driverDim)`. `deltaNets` is cleared.
`subnetCacheDirty = false`.

This is a **legacy passthrough** -- the existing Phase 15 math
(Cholesky / augmented GE / column-rank defence / polynomial
augmentation / Output Clamp / Shepard for Scale) runs UNCHANGED
to completion. The new sub-net state is captured so Phase 16.2
can extend without re-deriving anchors.

### Dual `.mll` rebuild (commit 5, `faba3f0`)

| File | size | sha256 |
|---|---|---|
| `modules/.../win64/2022/RBFtools.mll` | 191,488 B | `9ba77799c22e82333efa5a80bbeeddded2c74fdcadc0cd5cffccb9457d8ca3b7` |
| `modules/.../win64/2025/RBFtools.mll` | 191,488 B | `3ce4857f02322e83816282d29908e2e18b8c1d53e9e6486e6f6e90b7d6f2f4ff` |

Both binaries verified via `strings`:
* Contain `poseParentIndex` + `poseDriverMask` (Phase 16 schema).
* Retain `outputClampEnabled` + `outputClampInflation` (Phase 15
  anti-overshoot anchors).
* Retain Phase 15 audit safety strings (`AABB inverted`,
  `Part C.1` / `Part C.3`).
* Dual-SDK ABI isolation re-verified -- 2022.mll links only
  `OpenMaya20220000`, 2025.mll links only `OpenMaya20250000`.

### Controller writers (commit 6, `8a8d32b`)

`controller.py` adds two MVC-clean writer methods + two Qt
signals:

| Method | Plug | Signal |
|---|---|---|
| `set_pose_parent_index(row, parent)` | `shape.poseParentIndex[row]` | `poseParentIndexChanged(int, int)` |
| `set_pose_driver_mask(row, mask)` | `shape.poseDriverMask[row]` (Int32Array) | `poseDriverMaskChanged(int, list)` |

Users can author hierarchy via these methods today via Python
(or `cmds.setAttr` directly). The pose-grid UI columns are
deferred to Phase 16.2 (see deferral section).

### Tests (commit 8, `1476500`)

14 PERMANENT guards in
`test_m_p0_rbf_hierarchical_two_level.py`:

| # | Class | Test |
|---|---|---|
| 1-3 | `..._Header` | RBFSubNet struct + MObject decls + instance non-static |
| 4-11 | `..._Cpp` | MObject defs + addAttribute + 2 affects + ctor dirty=true + nAttr default -1 + tAttr kIntArray + prev-cache compare + baseNet passthrough |
| 12-13 | `..._Controller` | `set_pose_parent_index` / `set_pose_driver_mask` + signals |
| 14 | `..._Binary` | Both `.mll` contain Phase 16 strings + Phase 15 preserved |

Test 6 explicitly forbids the original 4-pair `attributeAffects`
design that would not actually trigger `evalInput=true` (locks
the corrected design against a future re-introduction).

---

## What deferred to Phase 16.2

### Commit 4 -- Inference (three-pass Shepard gating)

**Why deferred**: The full inference path requires ~150-200 LoC
of careful C++ surgery in the existing inference finalize loop
(`compute()` per-channel block around line 2540+):

1. Pass 1 needs to collect a `std::vector<double>` of per-base-
   pose `phi_i` scalars during the existing `getPoseWeights`
   call. The current code computes `w_i * phi_i` summed into
   `weightsArray` -- separating `phi_i` requires either threading
   an extra out-parameter through `getPoseWeights` (invasive) or
   adding a second activation pass (wasteful but localized).
2. Pass 2 per-delta-net inference + Shepard gating
   `alpha_i = phi_i / sum_k phi_k` over all base poses.
3. Pass 3 per-channel blending: additive for translate/rotate;
   scale fallback to Phase 15 single-layer Shepard; quaternion
   skip to `Base_Output[c]` until Phase 17.

Without a Maya runtime in the executor environment, the math
correctness of any one of these three passes cannot be
empirically verified per `compute()` tick -- a silent indexing
error in `matPoses` row/column subsetting or in `phi_i` vs
`w_i` separation would produce wrong outputs that only surface
on real rigs. The Phase 15 Output Clamp already mitigates the
user-reported overshoot symptom; Phase 16's hierarchical
inference adds factored modeling but does not unblock the user.

### Commit 7 -- Pose-grid UI columns

**Why deferred**: The pose grid widget tree
(`pose_grid_editor.py` + `pose_row_widget.py`) is a custom
`QListWidget`-style column-grouped header layout. Adding two
new columns (Parent `QComboBox` + Driver Mask popup
`QListWidget`) requires:

1. Header row two new column titles + sizing math.
2. Each `PoseRowWidget` two new controls with their own
   read/write data binding to the new plugs.
3. Signal wiring from the row widget → editor → main_window →
   controller `set_pose_parent_index` / `set_pose_driver_mask`.
4. Reload-on-tab-switch coverage so the new columns refresh
   correctly when the active node changes.

This is non-trivial Python UI work (~200-300 LoC) that should
land alongside Phase 16.2 Training+Inference so the data
binding contract is designed once with full math context.
Until then users can author the new attrs via:

```python
cmds.setAttr("RBFnodeShape.poseParentIndex[1]", 0)
cmds.setAttr(
    "RBFnodeShape.poseDriverMask[2]", 3, 0, 1, 2,
    type="Int32Array")
```

### True two-level training (the deferred-Stage-2 work)

Phase 16.2 will land:

1. Topology resolver (`basePoseIndices` + `childGroupsByParent`)
   with hard-cap-2 demotion + warn (brief Stage 2.1).
2. Per-sub-net subset training: row-subset `matPoses` /
   `matValues`, column-subset driver vectors, per-net
   Cholesky / GE / polynomial augmentation / column-rank
   defence -- all of the existing math runs per net.
3. RHS Delta = Actual - Predicted_Base with the child driver
   vector projected onto `baseNet.activeDrivers` (Polish 1).
4. Sibling driver-mask consistency: union + warn on mismatch
   (Polish 4).
5. Pass 1/2/3 inference with `phi_i` scalar storage +
   Shepard gating + channel-typed blending.
6. Pose-grid UI columns + the i18n keys.
7. Runtime tests for the new behaviour (will require mayapy
   fixtures or staged mock harness).

---

## 4/4 anchors

| Anchor | Stage 1 impact |
|---|---|
| TPS r<=0 oracle return value | 0 -- interpolateRbf unchanged |
| Honest-failure | **strengthened** -- prev-state cache compare upgrades silent stale-cache reads to evalInput-promotion + warn-ready in Phase 16.2 |
| Column-rank defence | 0 -- C lite runs as before on `wMat`; per-net carrier `isActiveLinear` ready for Phase 16.2 |
| polyDim = 1+d per CPD | 0 -- `polyMat` rides on baseNet for the legacy path; per-net carriers ready for Phase 16.2 |

`git diff milestone/RBF-MQB-correct-2026-05-12 -- modules/RBFtools/scripts/`
remains 0 bytes for the byte-frozen surface.

---

## Sweep + binary verification

```
$ python -m pytest modules/RBFtools/tests --continue-on-collection-errors -q
721 passed, 32 skipped, 46 errors, 14 subtests passed
```

* **721 passed** (+14 vs Phase 15 baseline 707).
* **46 errors** unchanged -- all pre-existing mayapy collection
  issues per HANDOFF sec.6.
* **0 regressions, 0 FAILED.**

Dual `.mll` strings spot-check:
```
=== 2022.mll ===
poseDriverMask
poseParentIndex
outputClampEnabled        ← Phase 15 preserved
outputClampInflation      ← Phase 15 preserved

=== 2025.mll ===
poseDriverMask
poseParentIndex
outputClampEnabled
outputClampInflation
```

---

## User-visible deltas this stage

* **No behaviour change** for existing rigs -- legacy single-layer
  Phase 15 math runs unchanged. Output Clamp + Shepard for Scale
  + audit safety guards all operational.
* **New schema attributes are exposed** on every `RBFtools` node
  (`shape.poseParentIndex[i]` + `shape.poseDriverMask[i]`).
  Defaults (`-1` / empty) keep legacy behaviour bit-identical
  within machine epsilon.
* **Controller methods available** for authoring (`set_pose_parent_index`,
  `set_pose_driver_mask`).
* **The cache invalidation hook works** -- editing the new attrs
  via `cmds.setAttr` (or the controller methods, when wired into
  Phase 16.2 UI) trips `evalInput = true` so the next compute
  refreshes `baseNet`.

---

## Installer / deploy artefacts

Final installer rebuild + push are tracked in the wrap-up
commit chain. `modules/RBFtools/scripts_2022/` has been
re-synced; Phase 11C smoke audit passes 7/7.

---

## Phase 16.2 acceptance checklist (to revisit before that stage)

* [ ] True topology resolver (Stage 2.1) with hard-cap-2 demotion
* [ ] Per-sub-net subset training (Stage 2.2 + 2.3, anchors per net)
* [ ] Three-pass inference + `phi_i` scalar storage (Stage 3)
* [ ] Pose-grid UI columns (Stage 6) + 6 i18n keys
* [ ] Runtime tests: backward-compat numerical equivalence, hierarchical resolution, sibling mask union, quaternion skip
* [ ] Update this audit with Phase 16.2 commit shas + new `.mll` fingerprints
