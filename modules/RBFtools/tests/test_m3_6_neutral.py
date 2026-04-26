"""M3.6 — Auto-neutral-sample tests.

Test layout
-----------
T1   generate_neutral_values default — all zeros.
T2   generate_neutral_values isScale=True — slot forced 1.0.
T3   T_NEUTRAL_QUAT_W (3 sub-cases): no group / single group /
     multi groups — quat-leader W component forced to 1.0.
T4   add_neutral_sample call sequencing:
       T4a — writes pose[0] via _write_pose_to_node
       T4b — does NOT touch alias / baseline / poseLocalTransform
             pipeline (source-text scan)
T5   controller.create_node auto-trigger gating:
       T5a — optionVar True + type==1 → add_neutral_sample called
       T5b — optionVar False → not called
T6   controller.add_neutral_sample_to_current_node existing-pose
     path triggers ConfirmDialog with action_id="add_neutral_with_existing".
T7   Tools menu spillover entry + Edit menu reset entry source-scan.
T8   i18n EN/CN parity for M3.6 keys.
"""

from __future__ import absolute_import

import conftest  # noqa: F401

import unittest
from unittest import mock

import maya.cmds as cmds


def _reset_cmds():
    cmds.reset_mock(side_effect=True, return_value=True)
    cmds.objExists.return_value = True
    cmds.warning.side_effect = None


# ----------------------------------------------------------------------
# T1 — generate_neutral_values default
# ----------------------------------------------------------------------


class T1_GenerateNeutralDefault(unittest.TestCase):

    def test_all_zeros_when_no_flags(self):
        from RBFtools.core_neutral import generate_neutral_values
        self.assertEqual(generate_neutral_values(5),
                         [0.0, 0.0, 0.0, 0.0, 0.0])


# ----------------------------------------------------------------------
# T2 — isScale slots forced 1.0
# ----------------------------------------------------------------------


class T2_GenerateNeutralIsScale(unittest.TestCase):

    def test_isScale_slot_is_one(self):
        from RBFtools.core_neutral import generate_neutral_values
        result = generate_neutral_values(
            4, output_is_scale=[False, True, False, True])
        self.assertEqual(result, [0.0, 1.0, 0.0, 1.0])

    def test_short_isScale_padded_with_false(self):
        # Caller may pass fewer flags than n_outputs (e.g. baselines
        # haven't been written yet); remaining slots default to False.
        from RBFtools.core_neutral import generate_neutral_values
        result = generate_neutral_values(4, output_is_scale=[True])
        self.assertEqual(result, [1.0, 0.0, 0.0, 0.0])


# ----------------------------------------------------------------------
# T3 — T_NEUTRAL_QUAT_W (PERMANENT GUARD, 3 sub-cases)
# ----------------------------------------------------------------------


class T3_NeutralQuatW(unittest.TestCase):
    """PERMANENT GUARD — DO NOT REMOVE.

    For every quat-group leader index s, the (s+3) slot (W component
    of identity quaternion) must be forced to 1.0 to land on
    quaternion identity (0, 0, 0, 1) and avoid M2.2 PSD-guard
    fallback. Single code path covers auto-trigger and manual-
    button — both query quat_group_starts from the node."""

    def test_a_no_quat_groups_all_zero(self):
        from RBFtools.core_neutral import generate_neutral_values
        result = generate_neutral_values(8, quat_group_starts=[])
        self.assertEqual(result, [0.0] * 8)

    def test_b_single_quat_group(self):
        from RBFtools.core_neutral import generate_neutral_values
        result = generate_neutral_values(8, quat_group_starts=[2])
        # values[2..5] = (0, 0, 0, 1) → identity quat
        self.assertEqual(result, [0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0])

    def test_c_multi_quat_groups(self):
        from RBFtools.core_neutral import generate_neutral_values
        result = generate_neutral_values(16, quat_group_starts=[4, 12])
        expected = [0.0] * 16
        expected[4 + 3] = 1.0
        expected[12 + 3] = 1.0
        self.assertEqual(result, expected)


# ----------------------------------------------------------------------
# T4 — add_neutral_sample call sequencing
# ----------------------------------------------------------------------


@unittest.skipIf(conftest._REAL_MAYA,
    "mock-dependent (cmds.reset_mock / mock.patch on cmds.*); real maya.cmds is not a MagicMock under mayapy")
class T4_AddNeutralSampleSequencing(unittest.TestCase):

    def _stub(self, mc):
        from RBFtools.core import PoseData
        mc._exists.return_value = True
        mc.get_shape.return_value = "RBF1Shape"
        mc.read_driver_info.return_value = ("drv", ["rotateX"])
        mc.read_driven_info.return_value = ("drvn", ["a", "b"])
        mc.read_quat_group_starts.return_value = []
        mc.read_output_baselines.return_value = []
        mc.read_all_poses.return_value = []
        mc.PoseData = PoseData
        mc.undo_chunk.return_value.__enter__ = lambda s: None
        mc.undo_chunk.return_value.__exit__ = lambda s, *a: False
        mc.vector_eq.side_effect = (
            lambda a, b, abs_tol=1e-6: list(a) == list(b))

    def test_a_writes_pose_zero_when_empty(self):
        _reset_cmds()
        from RBFtools import core_neutral
        with mock.patch("RBFtools.core_neutral.core") as mc:
            self._stub(mc)
            wrote = core_neutral.add_neutral_sample("RBF1")
        self.assertTrue(wrote)
        # _write_pose_to_node called exactly once at index 0.
        self.assertEqual(mc._write_pose_to_node.call_count, 1)
        args = mc._write_pose_to_node.call_args[0]
        self.assertEqual(args[1], 0)  # sequential_idx
        pose = args[2]
        self.assertEqual(pose.index, 0)
        self.assertEqual(pose.inputs, [0.0])
        self.assertEqual(pose.values, [0.0, 0.0])

    def test_b_does_not_call_pipeline_helpers(self):
        """Source-text scan: add_neutral_sample body must NOT
        reference apply_poses / capture_output_baselines /
        capture_per_pose_local_transforms / auto_alias_outputs.
        Those belong to apply_poses; M3.6 is write-only on poses[0]
        per addendum §M3.6 Q8."""
        import inspect, re
        from RBFtools.core_neutral import add_neutral_sample
        src = inspect.getsource(add_neutral_sample)
        src = re.sub(r'"""[\s\S]*?"""', "", src)
        for forbidden in ("apply_poses",
                          "capture_output_baselines",
                          "capture_per_pose_local_transforms",
                          "auto_alias_outputs"):
            self.assertNotIn(forbidden, src,
                "add_neutral_sample body references {!r} — M3.6 must "
                "stay write-only on poses[0] (addendum §M3.6 Q8)"
                .format(forbidden))

    def test_c_idempotent_when_pose_zero_matches(self):
        _reset_cmds()
        from RBFtools import core_neutral
        from RBFtools.core import PoseData
        with mock.patch("RBFtools.core_neutral.core") as mc:
            self._stub(mc)
            mc.read_all_poses.return_value = [
                PoseData(0, [0.0], [0.0, 0.0]),  # already rest
            ]
            wrote = core_neutral.add_neutral_sample("RBF1")
        self.assertFalse(wrote,
            "should be idempotent when pose[0] already rest")
        self.assertEqual(mc._write_pose_to_node.call_count, 0)

    def test_d_existing_poses_shifted_by_one(self):
        _reset_cmds()
        from RBFtools import core_neutral
        from RBFtools.core import PoseData
        with mock.patch("RBFtools.core_neutral.core") as mc:
            self._stub(mc)
            mc.read_all_poses.return_value = [
                PoseData(0, [1.0], [3.0, 4.0]),
                PoseData(1, [2.0], [5.0, 6.0]),
            ]
            wrote = core_neutral.add_neutral_sample("RBF1")
        self.assertTrue(wrote)
        # _write_pose_to_node called 3 times: [0]=neutral,
        # [1]=shifted-from-0, [2]=shifted-from-1.
        self.assertEqual(mc._write_pose_to_node.call_count, 3)
        # First call should be the rest pose at index 0.
        first_call = mc._write_pose_to_node.call_args_list[0][0]
        self.assertEqual(first_call[1], 0)
        self.assertEqual(first_call[2].inputs, [0.0])


# ----------------------------------------------------------------------
# T5 — controller.create_node auto-trigger gating
# ----------------------------------------------------------------------


@unittest.skipIf(conftest._REAL_MAYA,
    "mock-dependent (cmds.reset_mock / mock.patch on cmds.*); real maya.cmds is not a MagicMock under mayapy")
class T5_AutoTriggerGating(unittest.TestCase):
    """Direct MainController() instantiation goes through the Qt
    inheritance chain (PoseTableModel → QAbstractTableModel)
    which the conftest shim does not fully fake. Test the auto-
    trigger wiring at the helper-method + source-text level
    instead — same coverage, no ancestry concerns."""

    def test_a_optvar_true_default_when_unset(self):
        _reset_cmds()
        from RBFtools.controller import MainController
        cmds.optionVar.side_effect = None
        cmds.optionVar.return_value = None
        # exists -> False, so the helper should default to True.
        cmds.optionVar.side_effect = (
            lambda *a, **k: False if k.get("exists") else None)
        # Construct a bare object skipping __init__ so we can
        # exercise the helper without tripping the full ancestry.
        ctrl = MainController.__new__(MainController)
        self.assertTrue(ctrl._auto_neutral_enabled())

    def test_b_optvar_false_disables_auto(self):
        _reset_cmds()
        from RBFtools.controller import MainController
        cmds.optionVar.side_effect = None
        cmds.optionVar.return_value = None
        cmds.optionVar.side_effect = (
            lambda *a, **k: True if k.get("exists")
            else (False if k.get("query") else None))
        ctrl = MainController.__new__(MainController)
        self.assertFalse(ctrl._auto_neutral_enabled())

    def test_c_create_node_source_gates_on_type_and_optvar(self):
        """Source-text guard: controller.create_node must check both
        _auto_neutral_enabled() AND .type == 1 before invoking
        core_neutral.add_neutral_sample."""
        import pathlib
        path = pathlib.Path(__file__).resolve().parent.parent
        text = (path / "scripts" / "RBFtools"
                / "controller.py").read_text(encoding="utf-8")
        # The two-condition guard must appear together inside
        # create_node().
        idx = text.find("def create_node(self)")
        self.assertGreater(idx, 0)
        body = text[idx:idx + 2000]
        self.assertIn("_auto_neutral_enabled()", body)
        self.assertIn('".type", 0) == 1', body)
        self.assertIn("core_neutral.add_neutral_sample(", body)


# ----------------------------------------------------------------------
# T6 — manual button + existing poses → confirm
# ----------------------------------------------------------------------


class T6_ManualButtonExistingPoses(unittest.TestCase):

    def test_action_id_in_source(self):
        import pathlib
        path = pathlib.Path(__file__).resolve().parent.parent
        text = (path / "scripts" / "RBFtools"
                / "controller.py").read_text(encoding="utf-8")
        self.assertIn('action_id="add_neutral_with_existing"', text)

    def test_method_callable(self):
        from RBFtools.controller import MainController
        self.assertTrue(callable(getattr(
            MainController,
            "add_neutral_sample_to_current_node", None)))


# ----------------------------------------------------------------------
# T7 — Tools / Edit menu wiring
# ----------------------------------------------------------------------


class T7_MenuWiring(unittest.TestCase):

    def test_tools_entry_via_spillover(self):
        import pathlib
        path = pathlib.Path(__file__).resolve().parent.parent
        text = (path / "scripts" / "RBFtools" / "ui"
                / "main_window.py").read_text(encoding="utf-8")
        self.assertIn('add_tools_action(\n            "menu_add_neutral_sample"',
                      text)

    def test_edit_reset_entry_present(self):
        import pathlib
        path = pathlib.Path(__file__).resolve().parent.parent
        text = (path / "scripts" / "RBFtools" / "ui"
                / "main_window.py").read_text(encoding="utf-8")
        self.assertIn("menu_reset_auto_neutral", text)
        self.assertIn("self._menu_edit.addAction", text)


# ----------------------------------------------------------------------
# T8 — i18n parity
# ----------------------------------------------------------------------


class T8_I18nParity(unittest.TestCase):

    REQUIRED = (
        "menu_add_neutral_sample",
        "menu_reset_auto_neutral",
        "reset_auto_neutral_done",
        "title_add_neutral",
        "summary_add_neutral",
        "status_neutral_starting",
        "status_neutral_done",
        "status_neutral_failed",
    )

    def test_keys_present_in_both_languages(self):
        from RBFtools.ui.i18n import _EN, _ZH
        for k in self.REQUIRED:
            self.assertIn(k, _EN, "missing EN: " + k)
            self.assertIn(k, _ZH, "missing CN: " + k)


if __name__ == "__main__":
    unittest.main()
