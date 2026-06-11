# -*- coding: utf-8 -*-
"""M_P0_LOAD_EDITOR_MULTI (2026-04-30) — _load_editor used legacy
single-source readers and produced dim-mismatched pose models.

User report 2026-04-30 (followup to 41f3e47): switching to a
multi-source RBF node still leaves the pose grid blank, AND any
attempt to add a pose on the new node raises:

  // Warning: Driver attribute count (8) differs from existing
  //   poses (4). //

even though the new node has its own 8-attr driver setup.

Root cause (legacy single-source vs new multi-source schema):

  ``controller._load_editor`` discovered the active node's
  wiring via the deprecated ``core.read_driver_info`` /
  ``core.read_driven_info`` helpers — both return only the
  FIRST driverSource[0] / drivenSource[0] entry. With M_B24-era
  multi-source nodes carrying e.g. 2 driverSource entries of 4
  attrs each, those readers report 4 attrs.

  ``core.read_all_poses`` already walks the multi-source schema
  and produces PoseData with ``inputs`` / ``values`` flattened
  across every source — 8 attrs in this example.

  Cascade:
    1. setup_columns configures pose_model with 4 columns.
    2. read_all_poses returns rows with 8-input dimension.
    3. First pose_model.add_pose(p) raises ValueError "Input
       dimension mismatch: expected 4, got 8".
    4. _load_editor aborts before editorLoaded.emit().
    5. main_window's editorLoaded subscribers never fire — the
       driver / driven tab editors AND the pose grid all stay
       stale (the user-reported "切换 RBF 节点后 pose 信息全部
       消失" symptom).
    6. After the partial abort, pose_model.n_inputs retains
       whatever the previous node had configured. The next UI
       add_pose (which already walks the multi readers via
       _gather_role_info) compares its 8-attr count against
       the OLD node's stale n_inputs (4) and rejects with the
       verbatim warning the user saw.

Path A fix: ``_load_editor`` now reads via the multi-source
helpers (``read_driver_info_multi`` /
``read_driven_info_multi``) and flat-concats their attrs.
Dimensions exactly match what ``read_all_poses`` produces and
what main_window ``_gather_role_info`` hands the controller's
``add_pose`` path; both cascades close.

Complementary to M_P0_NODE_SWITCH_POSE_GRID (41f3e47): that
commit closed the editorLoaded -> _refresh_pose_grid leg in the
view layer; this commit closes the data-shape leg in the
controller. Both are necessary — Lesson #8 (project-methodology
candidate): "症状的多个候选层 (view 时机 / controller 数据
shape / core 读取) 逐层修复时，每层 fix 必须配套 user 全链路
实测验收，不可'修了 view 层就假定全愈'".

Out-of-scope: alias-path callsites at controller.py:1218 /
1292 (and a handful of others — 826 / 838 / 931 / 932 / 1805)
still use the legacy single-source readers. They are recorded
technical debt; deferred to an independent
M_ALIAS_MULTI_AWARE sub-task.

PERMANENT GUARD T_M_P0_LOAD_EDITOR_MULTI.
"""

from __future__ import absolute_import

import ast
import os
import unittest
from unittest import mock

import conftest


_REPO_ROOT = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..")
)
_CTRL_PY = os.path.join(
    _REPO_ROOT, "modules", "RBFtools", "scripts", "RBFtools",
    "controller.py")


def _read(p):
    with open(p, "r", encoding="utf-8") as fh:
        return fh.read()


def _slice_method(src, signature):
    idx = src.find(signature)
    assert idx >= 0, "{} not found".format(signature)
    end = src.find("\n    def ", idx + 1)
    return src[idx:end if end > 0 else len(src)]


# ----------------------------------------------------------------------
# PERMANENT GUARD T_M_P0_LOAD_EDITOR_MULTI
# ----------------------------------------------------------------------


class T_M_P0_LOAD_EDITOR_MULTI(unittest.TestCase):
    """PERMANENT GUARD — DO NOT REMOVE.

    Locks _load_editor's switch from the legacy single-source
    readers to read_driver_info_multi / read_driven_info_multi —
    the dimension contract that makes pose_model setup_columns
    + read_all_poses + add_pose internally consistent."""

    @classmethod
    def setUpClass(cls):
        cls._ctrl_src = _read(_CTRL_PY)
        cls._body = _slice_method(
            cls._ctrl_src, "def _load_editor(self):")

    def test_PERMANENT_a_uses_multi_source_readers(self):
        self.assertIn(
            "core.read_driver_info_multi(", self._body,
            "_load_editor MUST use core.read_driver_info_multi "
            "so the column count matches read_all_poses + the "
            "UI _gather_role_info contract.")
        self.assertIn(
            "core.read_driven_info_multi(", self._body,
            "_load_editor MUST use core.read_driven_info_multi "
            "for the same reason on the driven side.")

    def test_PERMANENT_b_does_not_use_legacy_readers(self):
        # Defence-in-depth: the deprecated single-source readers
        # MUST NOT appear in the helper body — that path is the
        # bug shape.
        self.assertNotIn(
            "core.read_driver_info(", self._body,
            "_load_editor MUST NOT call core.read_driver_info — "
            "the deprecated single-source reader returns only "
            "driverSource[0]'s attrs, mismatching the multi-"
            "source schema produced by read_all_poses.")
        self.assertNotIn(
            "core.read_driven_info(", self._body,
            "_load_editor MUST NOT call core.read_driven_info — "
            "same reason on the driven side.")

    def test_PERMANENT_c_flat_concat_pattern_present(self):
        # The flat-concat pattern MUST be present so the column
        # count = sum(len(src.attrs) for src in sources). This
        # is the same contract as main_window._gather_role_info.
        self.assertIn(
            "for src in drv_sources for a in src.attrs", self._body,
            "_load_editor MUST flat-concat driver source attrs "
            "across every source — without this the controller-"
            "side column count drifts from the UI-side multi-"
            "source attr count.")
        self.assertIn(
            "for src in dvn_sources for a in src.attrs",
            self._body)

    def test_PERMANENT_d_setup_columns_called_after_multi_read(self):
        # The order matters: read multi-source FIRST, THEN
        # setup_columns with the resolved attrs. A future
        # refactor that inverted the order would re-introduce a
        # different symptom.
        idx_read = self._body.find("read_driver_info_multi(")
        idx_setup = self._body.find("setup_columns(")
        self.assertGreater(idx_read, 0)
        self.assertGreater(idx_setup, 0)
        self.assertLess(idx_read, idx_setup,
            "_load_editor MUST call multi-source readers BEFORE "
            "setup_columns so the column count reflects the "
            "live multi-source attrs.")

    def test_PERMANENT_e_emits_editor_loaded(self):
        # The whole point of the bug fix is that
        # editorLoaded.emit() is reachable after a successful
        # load. Lock the emit call's presence so a future
        # refactor cannot accidentally drop it again.
        self.assertIn(
            "self.editorLoaded.emit()", self._body,
            "_load_editor MUST emit editorLoaded after the load "
            "completes — without this main_window's grid / "
            "driver / driven rebuilds never fire and the "
            "node-switch is silent.")

    def test_PERMANENT_f_alias_paths_unchanged(self):
        # Defence-in-depth: the alias-path callsites at
        # line ~1218 / ~1292 (and the other legacy hits) must
        # stay unchanged — out-of-scope for this fix, recorded
        # technical debt for M_ALIAS_MULTI_AWARE. Counting the
        # legacy-reader hits across the whole controller MUST
        # remain >= 5 so the technical debt is visible.
        legacy_hits = (
            self._ctrl_src.count("core.read_driver_info(") +
            self._ctrl_src.count("core.read_driven_info("))
        self.assertGreaterEqual(
            legacy_hits, 5,
            "Expected >= 5 legacy single-source reader callsites "
            "still present (alias paths + a few others recorded "
            "as M_ALIAS_MULTI_AWARE technical debt). Got "
            "{}.".format(legacy_hits))

    def test_PERMANENT_g_ast_guard_multi_calls_present(self):
        # AST walk: _load_editor FunctionDef MUST contain
        # core.read_driver_info_multi + core.read_driven_info_multi
        # Calls. Lesson #6 reapplied — static grep can drift if
        # the helper is extracted into a sibling.
        tree = ast.parse(self._ctrl_src)
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef):
                continue
            if node.name != "_load_editor":
                continue
            seen_drv = False
            seen_dvn = False
            for sub in ast.walk(node):
                if not isinstance(sub, ast.Call):
                    continue
                func = sub.func
                if not isinstance(func, ast.Attribute):
                    continue
                if func.attr == "read_driver_info_multi":
                    seen_drv = True
                if func.attr == "read_driven_info_multi":
                    seen_dvn = True
            self.assertTrue(
                seen_drv,
                "AST guard: _load_editor MUST call "
                "read_driver_info_multi (lesson #6).")
            self.assertTrue(
                seen_dvn,
                "AST guard: _load_editor MUST call "
                "read_driven_info_multi (lesson #6).")
            return
        self.fail("_load_editor FunctionDef not found.")


# ----------------------------------------------------------------------
# Mock E2E — runtime: multi-source node switch loads dim-consistent.
# ----------------------------------------------------------------------


class _PoseModelStub(object):
    """Plain-Python pose-model emulating the bits _load_editor
    touches. The real PoseTableModel inherits from
    QAbstractTableModel which under conftest's minimal Qt shim
    returns MagicMock for every attr lookup, breaking the int
    comparisons inside add_pose."""

    def __init__(self):
        self.n_inputs = 0
        self.n_outputs = 0
        self._rows = []

    def clear(self):
        self.n_inputs = 0
        self.n_outputs = 0
        self._rows = []

    def setup_columns(self, drv_attrs, dvn_attrs):
        self.n_inputs = len(drv_attrs)
        self.n_outputs = len(dvn_attrs)

    def add_pose(self, pose):
        if self.n_inputs and \
                len(pose.inputs) != self.n_inputs:
            raise ValueError(
                "Input dimension mismatch: expected {}, got "
                "{}".format(
                    self.n_inputs, len(pose.inputs)))
        if self.n_outputs and \
                len(pose.values) != self.n_outputs:
            raise ValueError(
                "Output dimension mismatch: expected {}, got "
                "{}".format(
                    self.n_outputs, len(pose.values)))
        self._rows.append(pose)

    def rowCount(self):
        return len(self._rows)


@unittest.skipIf(conftest._REAL_MAYA,
    "mock-dependent (cmds + core stubs)")
class TestM_P0_LOAD_EDITOR_MULTI_RuntimeBehavior(unittest.TestCase):

    def _make_ctrl(self, current_node="RBFnode2"):
        from RBFtools.controller import MainController
        ctrl = MainController.__new__(MainController)
        ctrl._current_node = current_node
        ctrl._pose_model = _PoseModelStub()
        ctrl.editorLoaded = mock.MagicMock()
        return ctrl

    def _make_multi_sources(self, role, count, attrs_per_source):
        from RBFtools.core import DriverSource, DrivenSource
        cls = DriverSource if role == "driver" else DrivenSource
        return [
            cls(node="{}_{}".format(role, i),
                attrs=tuple(
                    "attr{}_{}".format(i, j)
                    for j in range(attrs_per_source)))
            for i in range(count)
        ]

    def _run_load(self, ctrl, drv_sources, dvn_sources, poses,
                  shape_type=1):
        from RBFtools import core
        from RBFtools import controller as ctrl_mod
        from RBFtools.controller import MainController
        cmds_stub = mock.MagicMock()
        cmds_stub.objExists.return_value = True
        with mock.patch.object(
                core, "get_shape", return_value="ShapeStub"):
            with mock.patch.object(
                    core, "safe_get",
                    return_value=shape_type):
                with mock.patch.object(
                        core, "read_driver_info_multi",
                        return_value=drv_sources):
                    with mock.patch.object(
                            core, "read_driven_info_multi",
                            return_value=dvn_sources):
                        with mock.patch.object(
                                core, "read_all_poses",
                                return_value=poses):
                            with mock.patch.object(
                                    ctrl_mod, "cmds",
                                    cmds_stub):
                                MainController._load_editor(ctrl)

    # ------------------------------------------------------------------
    # Scenario (a): single source — regression guard.
    # ------------------------------------------------------------------

    def test_single_source_node_loads_correctly(self):
        from RBFtools.core import PoseData
        ctrl = self._make_ctrl()
        drv = self._make_multi_sources("driver", 1, 3)
        dvn = self._make_multi_sources("driven", 1, 2)
        poses = [PoseData(
            index=0, inputs=[0.1] * 3, values=[0.2] * 2, radius=5.0)
            for _ in range(2)]
        self._run_load(ctrl, drv, dvn, poses)
        self.assertEqual(ctrl._pose_model.n_inputs, 3)
        self.assertEqual(ctrl._pose_model.n_outputs, 2)
        self.assertEqual(ctrl._pose_model.rowCount(), 2)
        ctrl.editorLoaded.emit.assert_called_once()

    # ------------------------------------------------------------------
    # Scenario (b): multi-driver — KEY regression repro.
    # ------------------------------------------------------------------

    def test_multi_driver_2x4_loads_with_8_inputs(self):
        # User-reported repro: 2 driverSource × 4 attrs each.
        # Pre-fix this raised dim mismatch and aborted.
        from RBFtools.core import PoseData
        ctrl = self._make_ctrl()
        drv = self._make_multi_sources("driver", 2, 4)
        dvn = self._make_multi_sources("driven", 1, 3)
        poses = [PoseData(
            index=0, inputs=[0.0] * 8, values=[0.0] * 3, radius=5.0)
            for _ in range(2)]
        self._run_load(ctrl, drv, dvn, poses)
        self.assertEqual(
            ctrl._pose_model.n_inputs, 8,
            "2x4 multi-driver MUST configure 8 input columns; "
            "got {}.".format(ctrl._pose_model.n_inputs))
        self.assertEqual(ctrl._pose_model.n_outputs, 3)
        self.assertEqual(
            ctrl._pose_model.rowCount(), 2,
            "Both 8-input poses MUST load (no dim mismatch).")
        ctrl.editorLoaded.emit.assert_called_once()

    # ------------------------------------------------------------------
    # Scenario (c): multi-driver + multi-driven.
    # ------------------------------------------------------------------

    def test_multi_driver_and_driven_loads_correctly(self):
        from RBFtools.core import PoseData
        ctrl = self._make_ctrl()
        drv = self._make_multi_sources("driver", 3, 2)
        dvn = self._make_multi_sources("driven", 2, 4)
        # 3*2=6 inputs, 2*4=8 outputs.
        poses = [PoseData(
            index=0, inputs=[0.5] * 6, values=[0.5] * 8, radius=5.0)
            for _ in range(4)]
        self._run_load(ctrl, drv, dvn, poses)
        self.assertEqual(ctrl._pose_model.n_inputs, 6)
        self.assertEqual(ctrl._pose_model.n_outputs, 8)
        self.assertEqual(ctrl._pose_model.rowCount(), 4)

    # ------------------------------------------------------------------
    # Scenario (d): post-switch add_pose dimension check passes.
    # ------------------------------------------------------------------

    def test_post_switch_add_pose_passes_dim_check(self):
        # 3 driver source × 3 attrs = 9 attrs; user UI hands
        # add_pose 9 attrs; controller MUST NOT reject.
        from RBFtools.controller import MainController
        from RBFtools.core import PoseData
        ctrl = self._make_ctrl()
        drv = self._make_multi_sources("driver", 3, 3)
        dvn = self._make_multi_sources("driven", 1, 4)
        # Empty poses on the new node — typical "freshly-switched
        # to a not-yet-populated node" case.
        self._run_load(ctrl, drv, dvn, [])
        self.assertEqual(ctrl._pose_model.n_inputs, 9)
        self.assertEqual(ctrl._pose_model.n_outputs, 4)
        # Now simulate UI calling add_pose with 9-attr flat list.
        # The dim-check at controller.py:1602-1611 compares
        # n_inputs against len(driver_attrs); they must match.
        # Build the flat attr list the same way
        # _gather_role_info would.
        flat_drv_attrs = [a for src in drv for a in src.attrs]
        flat_dvn_attrs = [a for src in dvn for a in src.attrs]
        self.assertEqual(len(flat_drv_attrs), 9)
        self.assertEqual(
            ctrl._pose_model.n_inputs, len(flat_drv_attrs),
            "Pre-fix mismatch (4 vs 9) was the user-reported "
            "'Driver attribute count differs from existing "
            "poses' warning; post-fix the lengths must match.")

    # ------------------------------------------------------------------
    # Scenario (e): post-switch column-count consistency.
    # ------------------------------------------------------------------

    def test_post_switch_pose_model_column_consistency(self):
        # The pose grid renders n_inputs + n_outputs columns
        # (plus radius). Here we just assert the n_inputs +
        # n_outputs sum matches what the UI computes.
        from RBFtools.core import PoseData
        ctrl = self._make_ctrl()
        drv = self._make_multi_sources("driver", 2, 5)
        dvn = self._make_multi_sources("driven", 1, 3)
        self._run_load(ctrl, drv, dvn, [])
        self.assertEqual(ctrl._pose_model.n_inputs, 10)
        self.assertEqual(ctrl._pose_model.n_outputs, 3)

    # ------------------------------------------------------------------
    # Scenario (g): A↔B switch idempotent.
    # ------------------------------------------------------------------

    def test_A_to_B_to_A_switch_idempotent(self):
        # nodeA: 8 attrs / 4 attrs; nodeB: 4 attrs / 2 attrs.
        # Switch A -> B -> A -> B -> A (5 events). Each
        # configuration MUST be loaded cleanly with no residue.
        from RBFtools.core import PoseData
        ctrl = self._make_ctrl()
        a_drv = self._make_multi_sources("driver", 2, 4)
        a_dvn = self._make_multi_sources("driven", 1, 4)
        b_drv = self._make_multi_sources("driver", 1, 4)
        b_dvn = self._make_multi_sources("driven", 1, 2)
        a_poses = [PoseData(
            index=0, inputs=[0.0] * 8, values=[0.0] * 4, radius=5.0)
            for _ in range(3)]
        b_poses = [PoseData(
            index=0, inputs=[0.0] * 4, values=[0.0] * 2, radius=5.0)
            for _ in range(1)]
        for src_drv, src_dvn, poses, expected_in, expected_out, \
                expected_rows in [
                    (a_drv, a_dvn, a_poses, 8, 4, 3),
                    (b_drv, b_dvn, b_poses, 4, 2, 1),
                    (a_drv, a_dvn, a_poses, 8, 4, 3),
                    (b_drv, b_dvn, b_poses, 4, 2, 1),
                    (a_drv, a_dvn, a_poses, 8, 4, 3),
                ]:
            self._run_load(ctrl, src_drv, src_dvn, poses)
            self.assertEqual(
                ctrl._pose_model.n_inputs, expected_in)
            self.assertEqual(
                ctrl._pose_model.n_outputs, expected_out)
            self.assertEqual(
                ctrl._pose_model.rowCount(), expected_rows)

    # ------------------------------------------------------------------
    # Edge: empty node path.
    # ------------------------------------------------------------------

    def test_empty_current_node_emits_clean(self):
        from RBFtools.controller import MainController
        ctrl = self._make_ctrl(current_node="")
        MainController._load_editor(ctrl)
        ctrl.editorLoaded.emit.assert_called_once()
        self.assertEqual(ctrl._pose_model.n_inputs, 0)
        self.assertEqual(ctrl._pose_model.n_outputs, 0)

    def test_no_sources_node_emits_clean(self):
        # Node exists but has 0 driverSource entries (e.g. user
        # created it but never wired anything). Multi readers
        # return [] -> driver_attrs / driven_attrs = []. No
        # poses to load. editorLoaded fires.
        ctrl = self._make_ctrl()
        self._run_load(ctrl, [], [], [])
        self.assertEqual(ctrl._pose_model.n_inputs, 0)
        self.assertEqual(ctrl._pose_model.n_outputs, 0)
        ctrl.editorLoaded.emit.assert_called_once()


if __name__ == "__main__":
    unittest.main()
