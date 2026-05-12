"""M3.1 — Pose Pruner tests.

Test layout
-----------
T1   _scan_duplicates — vector_eq + (input AND value) policy +
     conflict separation.
T2   _scan_redundant_inputs — driver dim with all-equal column.
T3   _scan_constant_outputs — output dim with all-equal column.
T4   shift_quat_starts — 7 boundary cases (T_QUAT_GROUP_SHIFT
     PERMANENT GUARD): a unaffected, b in-range invalid, c shifted,
     d multi-removed multi-group, e empty removed, f empty starts,
     g multi-removed-same-group.
T5   analyse_node end-to-end (mock core read helpers).
T6   execute_prune call sequencing — apply_poses called once with
     packed (drv_attrs, drvn_attrs, poses); write_quat_group_starts
     called once.
T7   controller path A wiring (action_id="prune_poses").
T8   Tools menu spillover entry.
T9   pose-row spillover entry (danger=True).
T10  i18n EN/CN parity for M3.1 keys.
T11  Pruner does NOT call cmds.aliasAttr directly (source-scan).
T12  Pruner preserves invalid quat group's original start value
     (E.2 contract — verified through execute_prune behaviour).
T13  T_ANALYSE_READ_ONLY (PERMANENT) — analyse_node body MUST NOT
     contain any mutation call (setAttr/connectAttr/delete/
     removeMultiInstance/aliasAttr/createNode/undo_chunk).
"""

from __future__ import absolute_import

import conftest  # noqa: F401

import inspect
import unittest
from unittest import mock

import maya.cmds as cmds


def _reset_cmds():
    cmds.reset_mock()
    cmds.objExists.return_value = True
    cmds.warning.side_effect = None


def _pose(idx, ins, vals):
    from RBFtools.core import PoseData
    return PoseData(idx, ins, vals)


# ----------------------------------------------------------------------
# T1 — _scan_duplicates
# ----------------------------------------------------------------------


class T1_ScanDuplicates(unittest.TestCase):

    def test_input_and_value_both_same_marks_duplicate(self):
        from RBFtools.core_prune import _scan_duplicates
        poses = [
            _pose(0, [0.0, 0.0], [1.0]),
            _pose(1, [0.0, 0.0], [1.0]),  # full duplicate of 0
            _pose(2, [0.5, 0.5], [2.0]),
        ]
        dup, conf = _scan_duplicates(poses)
        self.assertEqual(dup, [1])
        self.assertEqual(conf, [])

    def test_input_only_same_yields_conflict_not_duplicate(self):
        from RBFtools.core_prune import _scan_duplicates
        poses = [
            _pose(0, [0.0, 0.0], [1.0]),
            _pose(1, [0.0, 0.0], [9.0]),  # same input, diff value
        ]
        dup, conf = _scan_duplicates(poses)
        self.assertEqual(dup, [])
        self.assertEqual(conf, [(0, 1)])

    def test_no_duplicates_no_conflicts(self):
        from RBFtools.core_prune import _scan_duplicates
        poses = [
            _pose(0, [0.0, 0.0], [1.0]),
            _pose(1, [1.0, 0.0], [2.0]),
            _pose(2, [0.0, 1.0], [3.0]),
        ]
        dup, conf = _scan_duplicates(poses)
        self.assertEqual(dup, [])
        self.assertEqual(conf, [])


# ----------------------------------------------------------------------
# T2 — _scan_redundant_inputs
# ----------------------------------------------------------------------


class T2_ScanRedundantInputs(unittest.TestCase):

    def test_all_zero_column_flagged(self):
        from RBFtools.core_prune import _scan_redundant_inputs
        poses = [
            _pose(0, [0.0, 1.0, 0.0], [0.0]),
            _pose(1, [0.0, 2.0, 0.0], [0.0]),
            _pose(2, [0.0, 3.0, 0.0], [0.0]),
        ]
        # input dims 0 and 2 have zero range; dim 1 varies.
        self.assertEqual(_scan_redundant_inputs(poses, 3), [0, 2])

    def test_empty_poses_returns_empty(self):
        from RBFtools.core_prune import _scan_redundant_inputs
        self.assertEqual(_scan_redundant_inputs([], 3), [])


# ----------------------------------------------------------------------
# T3 — _scan_constant_outputs
# ----------------------------------------------------------------------


class T3_ScanConstantOutputs(unittest.TestCase):

    def test_constant_column_flagged(self):
        from RBFtools.core_prune import _scan_constant_outputs
        poses = [
            _pose(0, [0.0], [1.0, 5.0]),
            _pose(1, [1.0], [1.0, 6.0]),
            _pose(2, [2.0], [1.0, 7.0]),
        ]
        self.assertEqual(_scan_constant_outputs(poses, 2), [0])

    def test_empty_poses_returns_empty(self):
        from RBFtools.core_prune import _scan_constant_outputs
        self.assertEqual(_scan_constant_outputs([], 2), [])


# ----------------------------------------------------------------------
# T4 — shift_quat_starts (T_QUAT_GROUP_SHIFT PERMANENT GUARD)
# ----------------------------------------------------------------------


class T4_QuatGroupShift(unittest.TestCase):
    """PERMANENT GUARD — DO NOT REMOVE.

    Locks the precise behaviour of shift_quat_starts across all
    boundary cases. Any optimisation that breaks one case will
    silently break user-facing pruner correctness."""

    def test_a_unaffected_no_shift(self):
        from RBFtools.core_prune import shift_quat_starts
        # Group spans [4..7]; nothing removed before 4 → no shift.
        self.assertEqual(shift_quat_starts([4], []), [4])
        # Removed indices all >= 8 → no overlap, no shift.
        self.assertEqual(shift_quat_starts([4], [8, 9]), [4])

    def test_b_in_range_invalid(self):
        from RBFtools.core_prune import shift_quat_starts
        # Group [4..7]; remove 5 → group invalidated → None.
        self.assertEqual(shift_quat_starts([4], [5]), [None])
        # Remove the leader itself.
        self.assertEqual(shift_quat_starts([4], [4]), [None])
        # Remove the trailing sibling.
        self.assertEqual(shift_quat_starts([4], [7]), [None])

    def test_c_unaffected_but_shifted(self):
        from RBFtools.core_prune import shift_quat_starts
        # Group [8..11]; remove output 2 (before group, no overlap).
        # New start = 8 - 1 = 7.
        self.assertEqual(shift_quat_starts([8], [2]), [7])

    def test_d_multi_removed_multi_group_independent(self):
        from RBFtools.core_prune import shift_quat_starts
        # Two groups: [4..7] (will be invalidated by removing 5),
        # [10..13] (unaffected, must shift by count of removed-before-10).
        result = shift_quat_starts([4, 10], [5, 12])
        # Group 0: removed=5 in range → invalid → None.
        # Group 1: removed=12 in [10..13] → invalid → None.
        # Both invalid in this construction. Use a cleaner case:
        result = shift_quat_starts([4, 10], [2, 5])
        # Group 0: removed=5 in [4..7] → invalid → None.
        # Group 1: [10..13]; removed=2 (before) and 5 (before),
        # neither in range → shift = -2 → 8.
        self.assertEqual(result, [None, 8])

    def test_e_empty_removed_is_identity(self):
        from RBFtools.core_prune import shift_quat_starts
        self.assertEqual(shift_quat_starts([0, 4, 8], []), [0, 4, 8])

    def test_f_empty_starts_returns_empty(self):
        from RBFtools.core_prune import shift_quat_starts
        self.assertEqual(shift_quat_starts([], [3, 4, 5]), [])

    def test_g_multi_removed_same_group_still_invalid(self):
        from RBFtools.core_prune import shift_quat_starts
        # Group [4..7]; remove BOTH 5 and 6 (both in range).
        # Result: still invalid (None) — no special handling for
        # "multi-overlap" beyond what single-overlap does.
        self.assertEqual(shift_quat_starts([4], [5, 6]), [None])


# ----------------------------------------------------------------------
# T5 — analyse_node end-to-end
# ----------------------------------------------------------------------


class T5_AnalyseNodeEndToEnd(unittest.TestCase):

    def _stub(self, mc):
        # 4 poses, 2 driver attrs, 3 driven attrs; pose 1 is a full
        # duplicate of 0; input dim 1 is redundant; output dim 2 is
        # constant.
        from RBFtools.core import PoseData
        mc.read_all_poses.return_value = [
            PoseData(0, [0.0, 5.0], [1.0, 2.0, 7.0]),
            PoseData(1, [0.0, 5.0], [1.0, 2.0, 7.0]),
            PoseData(2, [1.0, 5.0], [3.0, 4.0, 7.0]),
            PoseData(3, [2.0, 5.0], [5.0, 6.0, 7.0]),
        ]
        mc.read_driver_info.return_value = ("drv", ["rotateX", "rotateY"])
        # M_B24b2: core_prune now consumes read_driver_info_multi; mock
        # the new entry-point too so existing tests keep their fixture.
        from RBFtools.core import DriverSource
        mc.read_driver_info_multi.return_value = [
            DriverSource(node="drv", attrs=("rotateX", "rotateY"))]
        mc.read_driven_info.return_value = ("drvn", ["a", "b", "c"])
        mc.read_quat_group_starts.return_value = []
        # vector_eq: simple element-wise tolerance.
        def veq(a, b, abs_tol=1e-6):
            return len(a) == len(b) and all(
                abs(x - y) < abs_tol for x, y in zip(a, b))
        mc.vector_eq.side_effect = veq

    def test_duplicate_redundant_constant_all_detected(self):
        from RBFtools import core_prune
        with mock.patch("RBFtools.core_prune.core") as mc:
            self._stub(mc)
            action = core_prune.analyse_node("RBF1")
        self.assertEqual(action.duplicate_pose_indices, [1])
        self.assertEqual(action.redundant_input_indices, [1])
        self.assertEqual(action.constant_output_indices, [2])

    def test_conflict_pairs_separate_from_duplicates(self):
        from RBFtools import core_prune
        from RBFtools.core import PoseData
        with mock.patch("RBFtools.core_prune.core") as mc:
            self._stub(mc)
            mc.read_all_poses.return_value = [
                PoseData(0, [0.0, 0.0], [1.0]),
                PoseData(1, [0.0, 0.0], [9.0]),  # input same, value diff
            ]
            mc.read_driver_info.return_value = ("drv", ["x", "y"])
            from RBFtools.core import DriverSource
            mc.read_driver_info_multi.return_value = [
                DriverSource(node="drv", attrs=("x", "y"))]
            mc.read_driven_info.return_value = ("drvn", ["o"])
            action = core_prune.analyse_node("RBF1")
        self.assertEqual(action.duplicate_pose_indices, [])
        self.assertEqual(action.conflict_pairs, [(0, 1)])

    def test_has_changes_false_when_only_conflicts(self):
        from RBFtools import core_prune
        action = core_prune.PruneAction()
        action.conflict_pairs = [(0, 1)]
        self.assertFalse(action.has_changes())


# ----------------------------------------------------------------------
# T6 — execute_prune call sequencing
# ----------------------------------------------------------------------


@unittest.skipIf(conftest._REAL_MAYA,
    "mock-dependent (cmds.reset_mock / mock.patch on cmds.*); real maya.cmds is not a MagicMock under mayapy")
class T6_ExecutePruneSequencing(unittest.TestCase):

    def test_calls_apply_poses_then_write_quat_starts(self):
        _reset_cmds()
        from RBFtools import core_prune
        from RBFtools.core import PoseData
        with mock.patch("RBFtools.core_prune.core") as mc:
            mc.read_all_poses.return_value = [
                PoseData(0, [0.0, 1.0], [1.0, 2.0]),
                PoseData(1, [0.0, 1.0], [1.0, 2.0]),  # duplicate
            ]
            mc.read_driver_info.return_value = ("drv", ["x", "y"])
            from RBFtools.core import DriverSource
            mc.read_driver_info_multi.return_value = [
                DriverSource(node="drv", attrs=("x", "y"))]
            mc.read_driven_info.return_value = ("drvn", ["a", "b"])
            mc.PoseData = PoseData
            mc.undo_chunk.return_value.__enter__ = lambda s: None
            mc.undo_chunk.return_value.__exit__ = lambda s, *a: False
            action = core_prune.PruneAction()
            action.duplicate_pose_indices = [1]
            action.redundant_input_indices = []
            action.constant_output_indices = []
            action.quat_group_effects = []
            core_prune.execute_prune("RBF1", action)
            # apply_poses called once with packed args (1 pose left).
            self.assertEqual(mc.apply_poses.call_count, 1)
            args = mc.apply_poses.call_args[0]
            packed_poses = args[5]
            self.assertEqual(len(packed_poses), 1)
            self.assertEqual(mc.write_quat_group_starts.call_count, 1)


# ----------------------------------------------------------------------
# T7 — controller path A wiring
# ----------------------------------------------------------------------


class T7_ControllerPathA(unittest.TestCase):

    def test_method_callable(self):
        from RBFtools.controller import MainController
        self.assertTrue(callable(getattr(
            MainController, "prune_current_node", None)))

    def test_action_id_string_present(self):
        import pathlib
        path = pathlib.Path(__file__).resolve().parent.parent
        text = (path / "scripts" / "RBFtools" / "controller.py").read_text(
            encoding="utf-8")
        self.assertIn('action_id="prune_poses"', text)


# ----------------------------------------------------------------------
# T8 — Tools menu spillover
# ----------------------------------------------------------------------


class T8_ToolsMenuSpillover(unittest.TestCase):

    def test_uses_add_tools_action(self):
        import pathlib
        path = pathlib.Path(__file__).resolve().parent.parent
        text = (path / "scripts" / "RBFtools" / "ui"
                / "main_window.py").read_text(encoding="utf-8")
        self.assertIn('add_tools_action("menu_prune_poses"', text)


# ----------------------------------------------------------------------
# T9 — pose-row spillover (danger=True)
# ----------------------------------------------------------------------


class T9_PoseRowSpilloverDanger(unittest.TestCase):

    def test_uses_add_pose_row_action_with_danger(self):
        import pathlib
        path = pathlib.Path(__file__).resolve().parent.parent
        text = (path / "scripts" / "RBFtools" / "ui"
                / "main_window.py").read_text(encoding="utf-8")
        # danger=True for the row_remove_this entry.
        self.assertIn('"row_remove_this", self._on_remove_pose_row, '
                      'danger=True', text)


# ----------------------------------------------------------------------
# T10 — i18n parity
# ----------------------------------------------------------------------


class T10_I18nParity(unittest.TestCase):

    REQUIRED = (
        "menu_prune_poses",
        "row_remove_this",
        "title_prune_poses",
        "summary_prune_poses",
        "prune_cb_duplicates",
        "prune_cb_redundant",
        "prune_cb_constant",
        "label_prune_preview",
        "btn_prune",
        "status_prune_starting",
        "status_prune_done",
        "status_prune_failed",
    )

    def test_keys_present_in_both_languages(self):
        from RBFtools.ui.i18n import _EN, _ZH
        for k in self.REQUIRED:
            self.assertIn(k, _EN, "missing EN: " + k)
            self.assertIn(k, _ZH, "missing CN: " + k)


# ----------------------------------------------------------------------
# T11 — Pruner does NOT call cmds.aliasAttr directly (source-scan)
# ----------------------------------------------------------------------


class T11_NoDirectAliasAttr(unittest.TestCase):
    """The Pruner delegates ALL alias maintenance to M3.7
    (auto_alias_outputs runs at the end of apply_poses). Direct
    cmds.aliasAttr calls in core_prune would bypass M3.7's single-
    source contract and risk clobbering user aliases."""

    def test_core_prune_no_aliasAttr(self):
        import pathlib
        path = pathlib.Path(__file__).resolve().parent.parent
        text = (path / "scripts" / "RBFtools"
                / "core_prune.py").read_text(encoding="utf-8")
        # Forbidden literal substring.
        self.assertNotIn("cmds.aliasAttr(", text,
            "core_prune.py must not call cmds.aliasAttr directly — "
            "delegate to M3.7 auto_alias_outputs (J.2 contract)")


# ----------------------------------------------------------------------
# T12 — invalid quat group preserves original start value (E.2)
# ----------------------------------------------------------------------


@unittest.skipIf(conftest._REAL_MAYA,
    "mock-dependent (cmds.reset_mock / mock.patch on cmds.*); real maya.cmds is not a MagicMock under mayapy")
class T12_InvalidGroupPreservesStart(unittest.TestCase):
    """E.2 contract: an invalid quat group's start value is preserved
    in the writeback so the C++ resolver "silently skips" the
    orphan but the user's semantic declaration is not erased."""

    def test_writeback_keeps_invalid_starts(self):
        _reset_cmds()
        from RBFtools import core_prune
        from RBFtools.core import PoseData
        with mock.patch("RBFtools.core_prune.core") as mc:
            mc.read_all_poses.return_value = [
                PoseData(0, [0.0], [1.0, 2.0, 3.0, 4.0, 5.0, 6.0,
                                     7.0, 8.0]),
                PoseData(1, [1.0], [1.0, 2.0, 3.0, 4.0, 5.0, 6.0,
                                     7.0, 9.0]),
            ]
            mc.read_driver_info.return_value = ("drv", ["x"])
            from RBFtools.core import DriverSource
            mc.read_driver_info_multi.return_value = [
                DriverSource(node="drv", attrs=("x",))]
            mc.read_driven_info.return_value = ("drvn",
                ["a", "b", "c", "d", "e", "f", "g", "h"])
            mc.PoseData = PoseData
            mc.undo_chunk.return_value.__enter__ = lambda s: None
            mc.undo_chunk.return_value.__exit__ = lambda s, *a: False

            # Removing output 5 (in range of group at start=4) should
            # invalidate it; the writeback should still contain 4.
            action = core_prune.PruneAction()
            action.duplicate_pose_indices = []
            action.redundant_input_indices = []
            action.constant_output_indices = [5]
            action.quat_group_effects = [
                core_prune.QuatGroupEffect(0, 4, None),  # invalid
            ]
            core_prune.execute_prune("RBF1", action)
            args = mc.write_quat_group_starts.call_args[0]
            writeback = args[1]
            self.assertEqual(writeback, [4],
                "invalid group's original start must be preserved (E.2)")


# ----------------------------------------------------------------------
# T13 — analyse_node read-only PERMANENT GUARD
# ----------------------------------------------------------------------


class T13_AnalyseReadOnly(unittest.TestCase):
    """PERMANENT GUARD — DO NOT REMOVE.

    analyse_node must remain read-only. The body MUST NOT contain
    any cmds.* mutation operation or undo_chunk wrapper. Mirrors
    M3.3 dry_run's read-only contract (T16-style)."""

    def test_PERMANENT_no_mutations(self):
        from RBFtools.core_prune import analyse_node
        src = inspect.getsource(analyse_node)
        # Strip docstring lines so contract documentation can mention
        # the forbidden symbols without false-positive.
        import re
        src = re.sub(r'"""[\s\S]*?"""', "", src)
        forbidden = (
            "cmds.setAttr",
            "cmds.connectAttr",
            "cmds.disconnectAttr",
            "cmds.delete",
            "cmds.removeMultiInstance",
            "cmds.aliasAttr",
            "cmds.createNode",
            "undo_chunk",
        )
        for f in forbidden:
            self.assertNotIn(f, src,
                "analyse_node violated read-only contract — found "
                + f)


if __name__ == "__main__":
    unittest.main()
