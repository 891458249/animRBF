# -*- coding: utf-8 -*-
"""M_P0_POSE_GRID_DEEP_FIX (2026-04-30) — Round 3 of the same
"node switch leaves pose grid empty" symptom.

Round history (same user-visible symptom, three different layers):

  Round 1 — M_P0_NODE_SWITCH_POSE_GRID (41f3e47): added the
    self._refresh_pose_grid() call inside _on_editor_loaded so the
    view rebuilds when controller fires editorLoaded.
  Round 2 — M_P0_LOAD_EDITOR_MULTI (5799958): switched _load_editor
    from the deprecated single-source readers to the multi-source
    flat-concat readers so pose_model.setup_columns receives the
    right dimensions.
  Round 3 — THIS COMMIT: closes two more failure points that survive
    Rounds 1+2:

    Candidate A: ``core.read_all_poses`` early-returned [] when
    ``shape.output[]`` size was 0. The output multi is only
    populated by the Connect button; a node that has been Applied
    but not yet Connected has shape.poses[] populated AND
    structurally sound, but ``cmds.getAttr(shape+".output",
    size=True)`` returns 0. The pre-fix early-return rejected
    such nodes as "no poses", leaving pose_model empty even
    though Rounds 1+2 had wired the view + controller paths
    correctly.

    Candidate B: ``controller._load_editor`` looped raw over the
    poses list calling ``self._pose_model.add_pose(p)``. add_pose
    raises ``ValueError`` on dim mismatch — a single malformed
    pose (e.g. v5-pre-multi node with 4-dim poseInput vs current
    8-dim setup_columns) aborted the whole loop and left
    ``editorLoaded.emit`` unfired. View-side _refresh_pose_grid
    never received the signal; pose grid AND driver / driven
    tabs all stayed blank.

Path A double-belt fix:

  * ``core.read_all_poses`` falls back to multi-source metadata
    (driverSource[] / drivenSource[] flat-concat) when the
    input / output multi sizes are zero. Empty-but-metadata
    nodes (Apply-only / Connect-only) load correctly; truly
    empty nodes still return [] cleanly.

  * ``controller._load_editor`` wraps each ``add_pose`` call in
    try/except so a single malformed pose surfaces as a
    cmds.warning instead of aborting the loop. editorLoaded.emit
    is now reachable in every branch.

Lesson #4 (4th recurrence): "reload-path data contract drift
silent through MVC layers". Lesson #8 (2nd application): "multi-
layer cascades demand multi-layer verification — the same user-
visible symptom can have failure points in view / controller /
core, and fixing one does not validate the others until the
full path runs end-to-end".

PERMANENT GUARD T_M_P0_POSE_GRID_DEEP_FIX.
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
_CORE_PY = os.path.join(
    _REPO_ROOT, "modules", "RBFtools", "scripts", "RBFtools",
    "core.py")
_CTRL_PY = os.path.join(
    _REPO_ROOT, "modules", "RBFtools", "scripts", "RBFtools",
    "controller.py")


def _read(p):
    with open(p, "r", encoding="utf-8") as fh:
        return fh.read()


def _slice_method(src, signature):
    idx = src.find(signature)
    assert idx >= 0, "{} not found".format(signature)
    end = src.find("\ndef ", idx + 1)
    if end < 0:
        end = src.find("\n    def ", idx + 1)
    return src[idx:end if end > 0 else len(src)]


# ----------------------------------------------------------------------
# PERMANENT GUARD T_M_P0_POSE_GRID_DEEP_FIX
# ----------------------------------------------------------------------


class T_M_P0_POSE_GRID_DEEP_FIX(unittest.TestCase):
    """PERMANENT GUARD — DO NOT REMOVE.

    Locks both belts of the Round 3 fix: the read_all_poses
    multi-source-metadata fallback (Candidate A) and the
    _load_editor per-pose try/except (Candidate B)."""

    @classmethod
    def setUpClass(cls):
        cls._core = _read(_CORE_PY)
        cls._ctrl = _read(_CTRL_PY)

    # ----- Candidate A: read_all_poses fallback ------------------------

    def test_PERMANENT_a_read_all_poses_fallback_present(self):
        body = _slice_method(
            self._core, "def read_all_poses(node):")
        self.assertIn(
            "read_driver_info_multi(node)", body,
            "read_all_poses MUST fall back to "
            "read_driver_info_multi when input size=0 — "
            "Apply-only nodes have populated driverSource[] "
            "metadata even when shape.input[] is unwired.")
        self.assertIn(
            "read_driven_info_multi(node)", body,
            "read_all_poses MUST fall back to "
            "read_driven_info_multi when output size=0 — "
            "Apply-only nodes have populated drivenSource[] "
            "metadata even when shape.output[] is unwired.")
        self.assertIn(
            "sum(len(s.attrs) for s in", body,
            "Fallback MUST flat-concat across every source so "
            "the dim count matches what setup_columns + "
            "_gather_role_info produce.")

    def test_PERMANENT_b_read_all_poses_keeps_true_empty_path(self):
        # When BOTH wiring AND metadata report zero, the node is
        # truly unconfigured — the pre-fix early-return is still
        # correct here. Lock that the function returns [] in this
        # branch instead of trying to read poses with zero
        # dimensions.
        body = _slice_method(
            self._core, "def read_all_poses(node):")
        # Two return [] sites total: one before fallback (non-RBF
        # / no shape) + one after fallback (still zero).
        self.assertGreaterEqual(
            body.count("return []"), 2,
            "read_all_poses MUST keep the post-fallback "
            "'truly empty' early-return — without it a node "
            "with no driver/driven configuration would attempt "
            "to read poses with zero dimensions.")

    def test_PERMANENT_c_ast_fallback_calls_present(self):
        # AST guard (lesson #6 reapplied): the fallback Calls
        # MUST appear inside read_all_poses' FunctionDef.
        tree = ast.parse(self._core)
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef):
                continue
            if node.name != "read_all_poses":
                continue
            seen_drv = seen_dvn = False
            for sub in ast.walk(node):
                if not isinstance(sub, ast.Call):
                    continue
                func = sub.func
                if isinstance(func, ast.Name):
                    if func.id == "read_driver_info_multi":
                        seen_drv = True
                    if func.id == "read_driven_info_multi":
                        seen_dvn = True
                elif isinstance(func, ast.Attribute):
                    if func.attr == "read_driver_info_multi":
                        seen_drv = True
                    if func.attr == "read_driven_info_multi":
                        seen_dvn = True
            self.assertTrue(seen_drv,
                "AST guard: read_all_poses MUST call "
                "read_driver_info_multi (lesson #6).")
            self.assertTrue(seen_dvn,
                "AST guard: read_all_poses MUST call "
                "read_driven_info_multi (lesson #6).")
            return
        self.fail("read_all_poses FunctionDef not found.")

    # ----- Candidate B: _load_editor per-pose try/except ---------------

    def test_PERMANENT_d_load_editor_wraps_add_pose(self):
        body = _slice_method(
            self._ctrl, "def _load_editor(self):")
        # The add_pose call MUST be inside a try block. We assert
        # that a try: line exists between the for-poses statement
        # and the add_pose call.
        idx_for = body.find("for p in poses:")
        self.assertGreater(idx_for, 0,
            "_load_editor MUST keep the for-poses loop.")
        # Slice the loop body and look for try/except.
        loop_section = body[idx_for:body.find(
            "self.editorLoaded.emit()", idx_for)]
        self.assertIn(
            "try:", loop_section,
            "_load_editor MUST wrap the add_pose call in "
            "try/except — without it a single malformed pose "
            "aborts the loop and editorLoaded.emit never fires.")
        self.assertIn(
            "except ValueError", loop_section,
            "The try/except MUST catch ValueError specifically "
            "(the dim-mismatch exception type pose_model.add_pose "
            "raises) so unrelated bugs still surface.")

    def test_PERMANENT_e_load_editor_warns_on_skip(self):
        body = _slice_method(
            self._ctrl, "def _load_editor(self):")
        self.assertIn(
            "skipping malformed pose", body,
            "_load_editor MUST emit a cmds.warning for each "
            "skipped pose so the partial-load is visible in "
            "the Script Editor.")

    def test_PERMANENT_f_editor_loaded_unconditional(self):
        # The whole point of the try/except is that
        # editorLoaded.emit() is reachable regardless of how
        # many poses raised. Lock its position AFTER the for
        # loop (not inside any conditional that the loop's
        # exceptions could short-circuit).
        body = _slice_method(
            self._ctrl, "def _load_editor(self):")
        idx_for = body.find("for p in poses:")
        idx_emit = body.find("self.editorLoaded.emit()", idx_for)
        self.assertGreater(idx_emit, idx_for,
            "self.editorLoaded.emit() MUST sit AFTER the "
            "for-poses loop so the emit fires regardless of "
            "per-pose raises.")

    def test_PERMANENT_g_ast_load_editor_try_except_present(self):
        # AST walk: _load_editor's FunctionDef MUST contain a Try
        # node whose body or orelse holds the add_pose call.
        tree = ast.parse(self._ctrl)
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef):
                continue
            if node.name != "_load_editor":
                continue
            sees_try = False
            for sub in ast.walk(node):
                if not isinstance(sub, ast.Try):
                    continue
                # Confirm the try body contains an add_pose call.
                for inner in ast.walk(sub):
                    if not isinstance(inner, ast.Call):
                        continue
                    func = inner.func
                    if isinstance(func, ast.Attribute) and \
                            func.attr == "add_pose":
                        sees_try = True
                        break
                if sees_try:
                    break
            self.assertTrue(
                sees_try,
                "AST guard: _load_editor MUST contain a try "
                "block wrapping add_pose (lesson #6).")
            return
        self.fail("_load_editor FunctionDef not found.")


# ----------------------------------------------------------------------
# Mock E2E — runtime: read_all_poses fallback + add_pose try/except.
# ----------------------------------------------------------------------


class _PoseModelStub(object):
    """Plain-Python pose-model emulating add_pose's dim check."""

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
class TestM_P0_POSE_GRID_DEEP_FIX_RuntimeBehavior(
        unittest.TestCase):

    # ------------------------------------------------------------------
    # Candidate A — read_all_poses fallback paths.
    # ------------------------------------------------------------------

    def _make_cmds_stub(self, input_size, output_size,
                        pose_indices):
        """Build a cmds mock that returns the given multi sizes
        plus a static pose_indices for the poses multi."""
        cmds_stub = mock.MagicMock()
        cmds_stub.objExists.return_value = True
        cmds_stub.ls.return_value = ["RBFnode2Shape"]
        cmds_stub.listRelatives.return_value = ["RBFnode2Shape"]
        cmds_stub.nodeType.return_value = "RBFtools"

        def _get_attr(plug, *args, **kwargs):
            size = kwargs.get("size", False) or (
                args and args[0] is True)
            multi = kwargs.get("multiIndices", False)
            if multi:
                if plug.endswith(".poses"):
                    return list(pose_indices)
                return []
            if size:
                if plug.endswith(".input"):
                    return int(input_size)
                if plug.endswith(".output"):
                    return int(output_size)
                return 0
            # Plug reads (poseInput / poseValue / etc.).
            return 0.0

        cmds_stub.getAttr.side_effect = _get_attr
        return cmds_stub

    def test_apply_only_node_loads_via_metadata_fallback(self):
        # User-reported repro: shape.poses populated but
        # shape.output size=0 (Apply done, Connect not yet).
        # Pre-fix returned []; post-fix returns the real poses
        # via drivenSource flat-concat fallback.
        from RBFtools import core
        from RBFtools.core import DriverSource, DrivenSource
        cmds_stub = self._make_cmds_stub(
            input_size=0, output_size=0,
            pose_indices=[0, 1, 2])
        drv = [DriverSource(
            node="d{}".format(i),
            attrs=("rx", "ry", "rz", "tx"))
            for i in range(2)]   # 8 attrs flat
        dvn = [DrivenSource(
            node="dn0", attrs=("tx", "ty", "tz"))]   # 3 attrs

        with mock.patch.object(core, "cmds", cmds_stub):
            with mock.patch.object(
                    core, "safe_get",
                    side_effect=lambda plug, default=None: (
                        1 if plug.endswith(".type")
                        else (default if default is not None
                              else 0.0))):
                with mock.patch.object(
                        core, "read_driver_info_multi",
                        return_value=drv):
                    with mock.patch.object(
                            core, "read_driven_info_multi",
                            return_value=dvn):
                        poses = core.read_all_poses("RBFnode2")
        self.assertEqual(
            len(poses), 3,
            "Apply-only node with 3 pose indices MUST yield 3 "
            "PoseData entries via fallback. Got {}.".format(
                len(poses)))
        # Each pose carries the metadata-derived dimensions.
        self.assertEqual(len(poses[0].inputs), 8)
        self.assertEqual(len(poses[0].values), 3)

    def test_truly_empty_node_returns_empty(self):
        # No wiring + no metadata -> []; the pre-fix early-
        # return survives this branch.
        from RBFtools import core
        cmds_stub = self._make_cmds_stub(
            input_size=0, output_size=0, pose_indices=[])
        with mock.patch.object(core, "cmds", cmds_stub):
            with mock.patch.object(
                    core, "safe_get", return_value=1):
                with mock.patch.object(
                        core, "read_driver_info_multi",
                        return_value=[]):
                    with mock.patch.object(
                            core, "read_driven_info_multi",
                            return_value=[]):
                        poses = core.read_all_poses("RBFnode2")
        self.assertEqual(
            poses, [],
            "Truly empty node (no wiring, no metadata) MUST "
            "return []; got {}.".format(poses))

    def test_fully_wired_node_skips_fallback(self):
        # input/output sizes both populated -> no fallback;
        # the pre-fix path runs unchanged.
        from RBFtools import core
        cmds_stub = self._make_cmds_stub(
            input_size=4, output_size=2, pose_indices=[0, 1])
        # Watcher: read_driver_info_multi MUST NOT be invoked
        # because both sizes are non-zero.
        drv_watch = mock.MagicMock(return_value=[])
        dvn_watch = mock.MagicMock(return_value=[])
        with mock.patch.object(core, "cmds", cmds_stub):
            with mock.patch.object(
                    core, "safe_get", return_value=1):
                with mock.patch.object(
                        core, "read_driver_info_multi",
                        side_effect=drv_watch):
                    with mock.patch.object(
                            core, "read_driven_info_multi",
                            side_effect=dvn_watch):
                        poses = core.read_all_poses("RBFnode2")
        self.assertEqual(len(poses), 2)
        drv_watch.assert_not_called()
        dvn_watch.assert_not_called()

    def test_input_size_zero_only_falls_back_for_inputs(self):
        # input size=0 + output size=2 -> fallback runs only on
        # the input side. Symmetric verification.
        from RBFtools import core
        from RBFtools.core import DriverSource
        cmds_stub = self._make_cmds_stub(
            input_size=0, output_size=2, pose_indices=[0])
        drv = [DriverSource(node="d", attrs=("a", "b", "c"))]
        dvn_watch = mock.MagicMock(return_value=[])
        with mock.patch.object(core, "cmds", cmds_stub):
            with mock.patch.object(
                    core, "safe_get", return_value=1):
                with mock.patch.object(
                        core, "read_driver_info_multi",
                        return_value=drv):
                    with mock.patch.object(
                            core, "read_driven_info_multi",
                            side_effect=dvn_watch):
                        poses = core.read_all_poses("RBFnode2")
        self.assertEqual(len(poses), 1)
        self.assertEqual(len(poses[0].inputs), 3)
        self.assertEqual(len(poses[0].values), 2)
        # Driven fallback NOT invoked because output_size=2.
        dvn_watch.assert_not_called()

    # ------------------------------------------------------------------
    # Candidate B — _load_editor per-pose try/except.
    # ------------------------------------------------------------------

    def _make_ctrl(self):
        from RBFtools.controller import MainController
        ctrl = MainController.__new__(MainController)
        ctrl._current_node = "RBFnode2"
        ctrl._pose_model = _PoseModelStub()
        ctrl.editorLoaded = mock.MagicMock()
        return ctrl

    def _run_load(self, ctrl, drv_sources, dvn_sources, poses,
                  shape_type=1):
        from RBFtools import core
        from RBFtools import controller as ctrl_mod
        from RBFtools.controller import MainController
        cmds_stub = mock.MagicMock()
        cmds_stub.objExists.return_value = True
        cmds_stub.warning = mock.MagicMock()
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
                                MainController._load_editor(
                                    ctrl)
        return cmds_stub

    def _make_sources(self, role, count, attrs_per_source):
        from RBFtools.core import DriverSource, DrivenSource
        cls = DriverSource if role == "driver" else DrivenSource
        return [
            cls(node="{}_{}".format(role, i),
                attrs=tuple(
                    "a{}_{}".format(i, j)
                    for j in range(attrs_per_source)))
            for i in range(count)
        ]

    def test_one_malformed_pose_skipped_others_loaded(self):
        # 5 poses, the 3rd has wrong input dim -> skipped with
        # cmds.warning; the other 4 load; editorLoaded fires.
        from RBFtools.core import PoseData
        ctrl = self._make_ctrl()
        drv = self._make_sources("driver", 1, 4)
        dvn = self._make_sources("driven", 1, 2)
        poses = []
        for i in range(5):
            if i == 2:
                # Wrong input dim (5 instead of 4).
                poses.append(PoseData(
                    index=i, inputs=[0.0] * 5,
                    values=[0.0] * 2, radius=5.0))
            else:
                poses.append(PoseData(
                    index=i, inputs=[0.0] * 4,
                    values=[0.0] * 2, radius=5.0))
        cmds_stub = self._run_load(ctrl, drv, dvn, poses)
        self.assertEqual(
            ctrl._pose_model.rowCount(), 4,
            "4 valid poses MUST load; the malformed one is "
            "skipped. Got {}.".format(
                ctrl._pose_model.rowCount()))
        ctrl.editorLoaded.emit.assert_called_once()
        # cmds.warning fired at least once for the skip + once
        # for the summary.
        self.assertGreaterEqual(
            cmds_stub.warning.call_count, 2,
            "cmds.warning MUST fire on each skip + once with "
            "the summary count.")

    def test_all_poses_malformed_still_emits(self):
        # Every pose dim-mismatches -> 0 loaded, but
        # editorLoaded MUST still emit so the view layer is not
        # left waiting.
        from RBFtools.core import PoseData
        ctrl = self._make_ctrl()
        drv = self._make_sources("driver", 2, 3)   # 6 attrs
        dvn = self._make_sources("driven", 1, 2)
        poses = [PoseData(
            index=i, inputs=[0.0] * 4,   # wrong: 4 vs 6
            values=[0.0] * 2, radius=5.0)
            for i in range(3)]
        self._run_load(ctrl, drv, dvn, poses)
        self.assertEqual(ctrl._pose_model.rowCount(), 0)
        ctrl.editorLoaded.emit.assert_called_once()

    def test_all_valid_poses_no_warning(self):
        # Sanity: when every pose matches, no warning fires.
        from RBFtools.core import PoseData
        ctrl = self._make_ctrl()
        drv = self._make_sources("driver", 1, 3)
        dvn = self._make_sources("driven", 1, 2)
        poses = [PoseData(
            index=i, inputs=[0.0] * 3,
            values=[0.0] * 2, radius=5.0)
            for i in range(3)]
        cmds_stub = self._run_load(ctrl, drv, dvn, poses)
        self.assertEqual(ctrl._pose_model.rowCount(), 3)
        ctrl.editorLoaded.emit.assert_called_once()
        # No warnings should fire on a clean load.
        cmds_stub.warning.assert_not_called()


if __name__ == "__main__":
    unittest.main()
