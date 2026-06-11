# Phase 11 Implementation Results -- M_P0_MAYA_2022_FROM_SCRATCH

**Date**: 2026-05-12
**Executor**: claude/funny-williams-d3ed69
**Repo HEAD at land**: `8969bb1` (Phase 11C+F smoke + drift detector extension)
**Status**: **LANDED** -- 5 commits FF'd to origin/main, installer rebuilt.

> Planner brief: [PATCH_BRIEF_M_P0_MAYA_2022_FROM_SCRATCH.md](PATCH_BRIEF_M_P0_MAYA_2022_FROM_SCRATCH.md)
> Phase 9 precursor: [AUDIT_PHASE9_RESULTS.md](AUDIT_PHASE9_RESULTS.md)

---

## TL;DR

| Phase | Action | Result |
|---|---|---|
| 11A | `git mv scripts_2022 -> scripts_2022_DEPRECATED_phase11` | commit `4bc9f86` |
| 11B | Rewrite sync script (R1-R10) | commit `e7c5b52` |
| 11B | Regenerate scripts_2022 from scratch | commit `dc67d6f`, 51 py + 5 other files |
| 11C | Add smoke audit + run | commit `8969bb1` (combined w/ 11F) |
| 11D | Verify dual .mll parity | **PASS**, no rebuild needed (diff = 0) |
| 11E | Rebuild installer + verify .mod | New installer 15,494,216 B sha256 `68dc55b6...` |
| 11F | Extend drift detector test | commit `8969bb1`, 3rd test runs smoke from pytest |
| Sweep | Full pytest | **615 passed** (+1 vs 614 baseline), 0 regressions |
| Anchors | 4/4 Python + 2/2 C++ markers | held |

Brief's strategy pivot achieved: scripts_2022 is now derived **purely** from scripts/ (Maya 2025 source), with zero bytes consulted from the prior scripts_2022 tree.

---

## Phase 11A -- Archive

Renamed `modules/RBFtools/scripts_2022/` to `modules/RBFtools/scripts_2022_DEPRECATED_phase11/` via `git mv` (Policy A -- history preserved). 56 files renamed, no contents changed. Maya does NOT load the `_DEPRECATED_phase11` tree because `.mod` template routes `MAYAVERSION:2022` to `scripts_2022`, which is recreated in Phase 11B.

Commit: `4bc9f86 chore(maya2022): archive obsolete scripts_2022 to _DEPRECATED_phase11`.

---

## Phase 11B -- Sync Script Rewrite + scripts_2022 Regen

### B.1 -- Sync rewrite

`tools/sync_2022_from_2025.py` is a from-scratch rewrite (commit `e7c5b52`, 596 lines, 318 ins / 278 del vs Phase 7). New rule set per brief sec.2 R1-R10:

  * **R1** PEP 263 coding decl injection (unchanged from Phase 7).
  * **R2** STRING token non-ASCII -> `\uXXXX` escape + auto `u`-prefix (unchanged).
  * **R3** COMMENT token non-ASCII transliteration (unchanged).
  * **R4** `isinstance(x, str) -> isinstance(x, _STR_TYPES)` + helper injection (header tag updated to `M_P0_MAYA_2022_FROM_SCRATCH R4`).
  * **R5** **NEW** -- wholesale `ui/compat.py` replacement. Maya 2022 has no PySide6 / shiboken6, so the try-PySide6 / fall-back-PySide2 dispatch in scripts/ produces a spurious `ImportError` at every module load. The R5 replacement statically pins PySide2 + shiboken2.
  * **R5b** **NEW** -- targeted flattener for `main_window.py:_is_alive()`. The scripts/ source has a `try: from shiboken2 ... except ImportError: from shiboken6 ...` fallback; R5b strips the dead-code `shiboken6` branch so the smoke test's "0 PySide6/shiboken6 imports in scripts_2022" requirement holds.
  * **R6** R2 applied to triple-quoted docstrings -- handled implicitly because the tokenize-based pass sees a docstring as a `STRING` token. Listed separately in the brief for clarity.
  * **R7** Defensive try/except in `help_button.py` (renumbered from Phase 7 R5).
  * **R8** Audit-only py3-only-syntax scan (renumbered from Phase 7 R7).
  * **R9/R10** Out of scope for the sync script -- handled by Phase 11C smoke test + Phase 11D `.mll` strings diff.

### B.2 -- scripts_2022 regenerated

`python tools/sync_2022_from_2025.py` writes 51 .py + 5 other files (3 top-level shims + 48 `.py` in `RBFtools/` + 5 `.mel`). Commit `dc67d6f`, 56 files added, 25,698 insertions.

Static verification:

  * **byte-level ASCII**: 51/51 files decode as ASCII.
  * **`ast.parse`**: 51/51 files parse cleanly (py3 host).
  * **0 PySide6/shiboken6 imports** (tokenize-based scan, ignoring comments).
  * **`_STR_TYPES` helper** present in `core.py` + `core_json.py`.
  * **R7 defensive try/except** present in `help_button.py`.
  * **R5 PySide2 hard-pin** in `compat.py` (`BINDING = "PySide2"`, no PySide6 import).
  * **`--check` idempotent**: running sync a second time produces zero drift.

---

## Phase 11C -- Smoke Audit

`tools/audit_phase11_maya2022_smoke.py` (new file, commit `8969bb1`) covers the seven brief sec.3 invariants:

```
  [OK  ]  1. ast.parse                    51/51 py files parse cleanly
  [OK  ]  2. byte ASCII                   51/51 py files are byte-ASCII
  [OK  ]  3. _STR_TYPES helper            present in 2/2 expected files
  [OK  ]  4. compat.py PySide2-only       no PySide6 imports
  [OK  ]  5. 0 PySide6 imports            0 imports in scripts_2022
  [OK  ]  6. help_button R7 defensive     try/except + fallback present
  [OK  ]  7. 4/4 anchors held             scripts/ (Maya 2025 path) holds:
                                            - M_P0_DISCONNECT_SCALE_RESTORE
                                            - _TRAINING_AFFECTING_ATTRS
                                            - M_P0_BATCH_DEFAULT_TRUE
                                            - DriverSource.node TypeError
```

The compat.py PySide2-only check uses a tokenwise import scan so the R5 docstring (which mentions PySide6 to document the prior dispatch pattern) doesn't false-positive.

---

## Phase 11D -- Dual `.mll` Verify

Confirmed both `.mll` artifacts unchanged from Phase 9 audit (sha256 still `e869aa88...` for 2022 / `df3cc02a...` for 2025). `M_P0_` strings parity:

```
=== modules/RBFtools/plug-ins/win64/2022/RBFtools.mll ===
  : M_P0_RBF_COLUMN_RANK_DEFENSE
  ; remove duplicate poses or move poses off a common hyperplane (M_P0_RBF_POLYNOMIAL_AUGMENTATION).

=== modules/RBFtools/plug-ins/win64/2025/RBFtools.mll ===
  : M_P0_RBF_COLUMN_RANK_DEFENSE
  ; remove duplicate poses or move poses off a common hyperplane (M_P0_RBF_POLYNOMIAL_AUGMENTATION).

diff: ZERO
```

Plus dual-SDK isolation re-confirmed:

  * `2022/RBFtools.mll` links `OpenMaya20220000` symbols (no `OpenMaya20250000`).
  * `2025/RBFtools.mll` links `OpenMaya20250000` symbols (no `OpenMaya20220000`).

**No `.mll` rebuild required.**

**Note on `M_P0_DISCONNECT_SCALE_RESTORE`**: the brief sec.2 R10 lists this with "(in C++ source)" but it lives in Python (`scripts/RBFtools/core.py`, also `scripts_2022/RBFtools/core.py`). Validated as a Python-side anchor in Phase 11C check 7 instead of a `.mll` string in 11D.

---

## Phase 11E -- Installer Rebuild

`.mod` template re-verified: `MAYAVERSION:2022 -> scripts_2022` on win64, mac, linux. No template change needed (Phase 4 was already correct).

`tools\build_installer.bat` rebuild output:

| Path | mtime | size | sha256 |
|---|---|---|---|
| `installer/RBFtoolsInstaller.exe` | 2026-05-12 22:47 | 15,494,216 B | `68dc55b6a0c281f621ba10fb982a10e72f46d8ebf62e899c29cd637f177741a5` |

Bundled content (per `tools/build_installer.spec`): the entire `modules/` tree (including the from-scratch scripts_2022/) + `resources/module_template.mod`.

The `scripts_2022_DEPRECATED_phase11/` tree is also bundled because the spec packages all of `modules/`, but Maya does NOT load it -- the `.mod` template routes `MAYAVERSION:2022` to `scripts_2022`, not the `_DEPRECATED` tree. Future cleanup may strip the deprecated tree from the bundle; for Phase 11 it is left in for audit trail.

---

## Phase 11F -- Drift Detector Extension

`modules/RBFtools/tests/unit/test_m_p0_maya_version_isolation_drift.py` extended with a third test `test_PERMANENT_c_phase11_smoke_audit_passes` that invokes the smoke audit from pytest. Catches sync regressions that the byte-drift check would miss (byte-equal output, broken smoke invariants).

```
modules/RBFtools/tests/unit/test_m_p0_maya_version_isolation_drift.py::test_PERMANENT_a_scripts_2022_matches_sync_output PASSED
modules/RBFtools/tests/unit/test_m_p0_maya_version_isolation_drift.py::test_PERMANENT_b_scripts_2022_is_pure_ascii PASSED
modules/RBFtools/tests/unit/test_m_p0_maya_version_isolation_drift.py::test_PERMANENT_c_phase11_smoke_audit_passes PASSED
```

---

## Full Sweep

```
615 passed, 32 skipped, 50 errors, 14 subtests passed in 3.10s
```

  * **+1 vs Phase 9 baseline** (614 -> 615) -- the new `test_PERMANENT_c_phase11_smoke_audit_passes`.
  * **50 errors** unchanged -- all pre-existing mayapy collection issues per HANDOFF sec.6.
  * **0 regressions**.

---

## 4/4 Anchors Held

| Anchor | Path | Status |
|---|---|---|
| TPS r<=0 oracle return-value | `source/RBFtools.cpp` (`interpolateRbf`) | held (Phase 9 verified, .mll unchanged) |
| Honest-failure (TypeError on non-str) | `scripts/RBFtools/core.py:65` + `scripts_2022/.../core.py` (R4 `_STR_TYPES`) | held |
| Column-rank defence | `source/RBFtools.cpp` (string `M_P0_RBF_COLUMN_RANK_DEFENSE` visible in both .mll) | held |
| polyDim = 1 + d (all CPD kernels) | `source/RBFtools.cpp` (`getPolynomialDim`) | held (Phase 9 verified, .mll unchanged) |

`git diff milestone/RBF-MQB-correct-2026-05-12 -- modules/RBFtools/scripts/` is still 0 bytes -- Maya 2025 path byte-frozen.

---

## Commit Series

| sha | subject |
|---|---|
| `b9d1233` | `docs(planner): import Phase 11 from-scratch brief + Phase 10 deep-dive (Phase 11 prelude)` |
| `4bc9f86` | `chore(maya2022): archive obsolete scripts_2022 to _DEPRECATED_phase11 (Phase 11A)` |
| `e7c5b52` | `fix(tooling): rewrite sync_2022_from_2025.py from-scratch with R1-R10 (Phase 11B)` |
| `dc67d6f` | `feat(maya2022): regenerate scripts_2022 from scratch (Phase 11B)` |
| `8969bb1` | `test(maya2022): Phase 11 smoke audit + drift detector extension (Phase 11C+F)` |

5 commits total, all FF'd to `origin/main` via `git push --no-tags origin claude/funny-williams-d3ed69:main` (Policy C SSH preserved). Policy A held -- no amend / rebase / reset / force.

---

## User Test Instructions (双 Maya 必跑)

Per brief sec.6.2:

### Maya 2022.5.1

1. Close Maya 2022 (confirm `maya.exe` is gone in Task Manager).
2. Delete:
   * `C:\Users\sz-dingyongzhen\Documents\maya\modules\RBFtools` (entire directory)
   * `C:\Users\sz-dingyongzhen\Documents\maya\modules\RBFtools.mod` (if present)
3. Restart the machine (clears `.pyc` cache + file locks).
4. Run the new installer: `X:\Plugins\RBFtools\installer\RBFtoolsInstaller.exe` (mtime must be **>= 2026-05-12 22:47**, sha256 `68dc55b6...`).
5. Start Maya 2022, test:
   * **MQB kernel switch -> Apply**: expect no `kFailure`, driven joints behave (M_P0_RBF_COLUMN_RANK_DEFENSE warning may appear in Script Editor once per rig with degenerate driver columns -- that's the variance-floor drop working as designed).
   * **Disconnect button**: expect `driven.scaleX == 1.0` (not 0.0).
   * **Help bubbles**: expect tooltips to show (R7 defensive try/except keeps them working even if `help_texts.py` ever regressed; pure ASCII source means no py2 encoding crash).
   * **No spurious `ImportError` at module load** (R5 PySide2 hard-pin).

### Maya 2025.3

6. Reuse the same install (modules tree is shared). Restart Maya 2025.
7. Repeat MQB / disconnect / help tests. Expected behaviour: same as `milestone/RBF-MQB-correct-2026-05-12` (scripts/ is byte-frozen since that milestone).

### Diagnostic snippet (if any test still fails)

```python
import RBFtools
print("RBFtools loaded from:", RBFtools.__file__)   # must contain scripts_2022 on Maya 2022
from RBFtools.ui import compat
print("Qt binding:", compat.BINDING)                 # must be "PySide2" on Maya 2022
from RBFtools import core
print("DISCONNECT_SCALE comment present:",
      "M_P0_DISCONNECT_SCALE_RESTORE" in open(core.__file__, encoding="utf-8").read())
import maya.cmds as cmds
print("plugin path:", cmds.pluginInfo("RBFtools", q=True, path=True))
```

If any of those four print lines is wrong, escalate to the Planner with the actual values + Maya version.

---

## Milestone Tag (post user-confirmation)

Per brief completion criterion, once the user confirms MQB + disconnect both work on both Maya 2022 and Maya 2025 after the clean reinstall, tag:

```
git tag -a milestone/RBF-MQB-correct-2026-05-12-from-scratch-LANDED <HEAD>
```

(Tag push is optional and is **not** part of `git push --no-tags`.)
