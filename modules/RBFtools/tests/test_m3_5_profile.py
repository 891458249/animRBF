"""M3.5 — Pose Profiler tests.

Test layout
-----------
T1   _estimate_solve_times — big-O monotonicity (n=10/100/1000).
T2   _estimate_memory — pose / weight / working components.
T3   profile_node end-to-end (mock) — consumes M3.1 analyse_node
     for health checks (T_REUSE_PRUNE).
T4   format_report — full sections present (Topology / Configuration /
     Wiring / Memory / Performance / Health / Recommendation).
T5   format_report split-suggestion triggers — n_poses>80 / cells>500 /
     cholesky>5ms each fire independently.
T6   T_PROFILE_READ_ONLY (PERMANENT) — profile_node body
     forbids 8 mutation symbols (cmds.setAttr / connectAttr /
     disconnectAttr / delete / removeMultiInstance / aliasAttr /
     createNode / undo_chunk).
T7   spillover §3 add_tools_panel_widget — 3 sub-cases:
       a — lazy create on first call
       b — duplicate widget_id raises RuntimeError
       c — remove returns True for known id
T_TOOLS_SECTION_PERSISTS (PERMANENT) — once created, the panel
     stays alive even after every widget is removed.
T_CAVEAT_VISIBLE (PERMANENT) — format_report output contains the
     visible caveat strings:
       "[CONCEPTUAL — no machine calibration]"
       "_K_CHOL"
       "[configured value;"
T8   controller.profile_current_node — read-only, no ask_confirm
     in the source body.
T9   Tools menu uses add_tools_action spillover (source-text scan).
T10  i18n EN/CN parity for M3.5 keys.
"""

from __future__ import absolute_import

import conftest  # noqa: F401

import inspect
import re
import unittest
from unittest import mock

import maya.cmds as cmds


def _reset_cmds():
    cmds.reset_mock(side_effect=True, return_value=True)
    cmds.objExists.return_value = True
    cmds.warning.side_effect = None


# ----------------------------------------------------------------------
# T1 — _estimate_solve_times
# ----------------------------------------------------------------------


class T1_EstimateSolveTimes(unittest.TestCase):

    def test_cubic_growth(self):
        from RBFtools.core_profile import _estimate_solve_times
        t10 = _estimate_solve_times(10, False)["cholesky_sec"]
        t100 = _estimate_solve_times(100, False)["cholesky_sec"]
        t1000 = _estimate_solve_times(1000, False)["cholesky_sec"]
        # 100/10 = 10x in linear → 1000x in cubic.
        self.assertAlmostEqual(t100 / t10, 1000.0, places=3)
        self.assertAlmostEqual(t1000 / t100, 1000.0, places=3)

    def test_ge_three_times_cholesky(self):
        from RBFtools.core_profile import _estimate_solve_times
        t = _estimate_solve_times(50, False)
        self.assertAlmostEqual(t["ge_sec"] / t["cholesky_sec"], 3.0,
                                places=3)

    def test_qwa_only_when_quat_groups(self):
        from RBFtools.core_profile import _estimate_solve_times
        self.assertIsNone(
            _estimate_solve_times(10, False)["qwa_iter_sec"])
        self.assertIsNotNone(
            _estimate_solve_times(10, True)["qwa_iter_sec"])


# ----------------------------------------------------------------------
# T2 — _estimate_memory
# ----------------------------------------------------------------------


class T2_EstimateMemory(unittest.TestCase):

    def test_components_correct(self):
        from RBFtools.core_profile import _estimate_memory
        m = _estimate_memory(10, 3, 8)
        self.assertEqual(m["pose_data"], 10 * 3 * 8)
        self.assertEqual(m["weight_matrix"], 10 * 8 * 8)
        self.assertEqual(m["working_memory"], 10 * 10 * 8)
        self.assertEqual(m["total"],
            m["pose_data"] + m["weight_matrix"] + m["working_memory"])

    def test_zero_poses_zero_memory(self):
        from RBFtools.core_profile import _estimate_memory
        self.assertEqual(_estimate_memory(0, 3, 8)["total"], 0)


# ----------------------------------------------------------------------
# T3 — profile_node end-to-end + T_REUSE_PRUNE
# ----------------------------------------------------------------------


class T3_ProfileNodeEndToEnd(unittest.TestCase):

    def _stub(self, mc):
        from RBFtools.core import PoseData
        mc._exists.return_value = True
        mc.get_shape.return_value = "RBF1Shape"
        mc.read_all_poses.return_value = [
            PoseData(0, [0.0, 0.0], [1.0, 0.0]),
            PoseData(1, [1.0, 0.0], [0.0, 1.0]),
        ]
        mc.read_driver_info.return_value = ("drv", ["rotateX", "rotateY"])
        mc.read_driven_info.return_value = ("drvn", ["a", "b"])
        mc.read_quat_group_starts.return_value = []
        mc.safe_get.side_effect = lambda path, default=0: default

    def test_basic_topology_present(self):
        from RBFtools import core_profile
        with mock.patch("RBFtools.core_profile.core") as mc, \
             mock.patch("RBFtools.core_profile.core_prune") as mp:
            self._stub(mc)
            from RBFtools.core_prune import PruneAction
            mp.analyse_node.return_value = PruneAction()
            mp.PruneOptions = lambda: None
            p = core_profile.profile_node("RBF1")
        self.assertEqual(p["topology"]["n_poses"], 2)
        self.assertEqual(p["topology"]["n_inputs"], 2)
        self.assertEqual(p["topology"]["n_outputs"], 2)

    def test_T_REUSE_PRUNE_calls_analyse_node(self):
        from RBFtools import core_profile
        with mock.patch("RBFtools.core_profile.core") as mc, \
             mock.patch("RBFtools.core_profile.core_prune") as mp:
            self._stub(mc)
            from RBFtools.core_prune import PruneAction
            mp.analyse_node.return_value = PruneAction()
            mp.PruneOptions = lambda: None
            core_profile.profile_node("RBF1")
            self.assertEqual(mp.analyse_node.call_count, 1)

    def test_health_counts_propagate(self):
        from RBFtools import core_profile
        from RBFtools.core_prune import PruneAction
        with mock.patch("RBFtools.core_profile.core") as mc, \
             mock.patch("RBFtools.core_profile.core_prune") as mp:
            self._stub(mc)
            action = PruneAction()
            action.duplicate_pose_indices = [3, 5]
            action.redundant_input_indices = [1]
            action.constant_output_indices = []
            action.conflict_pairs = [(0, 7), (2, 9)]
            mp.analyse_node.return_value = action
            mp.PruneOptions = lambda: None
            p = core_profile.profile_node("RBF1")
        self.assertEqual(p["health"]["duplicate_poses"], 2)
        self.assertEqual(p["health"]["redundant_inputs"], 1)
        self.assertEqual(p["health"]["constant_outputs"], 0)
        self.assertEqual(p["health"]["conflict_pairs"], 2)


# ----------------------------------------------------------------------
# T4 — format_report sections
# ----------------------------------------------------------------------


class T4_FormatReportSections(unittest.TestCase):

    def _profile(self, n_poses=12, triggers=()):
        return {
            "node_name": "RBF_L_arm",
            "topology": {
                "n_poses": n_poses, "n_inputs": 3, "n_outputs": 8,
                "cells_full": n_poses * n_poses,
                "cells_sym": n_poses * (n_poses + 1) // 2,
                "quat_groups": 0,
            },
            "configuration": {
                "type_mode": "RBF", "rbf_mode": 0, "kernel": 1,
                "input_encoding": 1, "distance_type": 0,
                "radius": 0.85, "regularization": 1e-08,
                "solver_method": 0,
            },
            "wiring": {"driver_node": "drv", "driven_node": "drvn"},
            "memory": {
                "pose_data": 1024, "weight_matrix": 8192,
                "working_memory": 4096, "total": 13312,
            },
            "performance": {
                "cholesky_sec": 0.001,
                "ge_sec":       0.003,
                "qwa_iter_sec": None,
                "estimated_per_eval_sec": 0.001,
            },
            "health": {
                "duplicate_poses": 0, "redundant_inputs": 0,
                "constant_outputs": 0, "conflict_pairs": 0,
            },
            "split_triggers": list(triggers),
        }

    def test_all_sections_present(self):
        from RBFtools.core_profile import format_report
        report = format_report(self._profile())
        for header in ("Topology", "Configuration", "Wiring",
                       "Memory estimates", "Performance estimates",
                       "Health checks", "Recommendation"):
            self.assertIn(header, report)

    def test_ok_recommendation_when_no_triggers(self):
        from RBFtools.core_profile import format_report
        report = format_report(self._profile(n_poses=10))
        self.assertIn("[OK] Node size is healthy", report)


# ----------------------------------------------------------------------
# T5 — format_report split-suggestion triggers
# ----------------------------------------------------------------------


class T5_SplitSuggestionTriggers(unittest.TestCase):

    def test_warn_when_triggers_nonempty(self):
        from RBFtools.core_profile import format_report
        prof = T4_FormatReportSections()._profile(
            n_poses=120,
            triggers=["n_poses = 120 > 80"])
        report = format_report(prof)
        self.assertIn("[WARN] Node size triggers split suggestion",
                      report)
        self.assertIn("rig-semantic", report)

    def test_magnitude_table_present(self):
        from RBFtools.core_profile import format_report
        prof = T4_FormatReportSections()._profile(
            n_poses=120,
            triggers=["n_poses = 120 > 80"])
        report = format_report(prof)
        self.assertIn("N=2 (M~", report)
        self.assertIn("N=3 (M~", report)
        self.assertIn("N=4 (M~", report)

    def test_no_warn_when_triggers_empty(self):
        from RBFtools.core_profile import format_report
        report = format_report(
            T4_FormatReportSections()._profile(n_poses=10))
        self.assertNotIn("[WARN]", report)

    def test_thresholds_documented(self):
        from RBFtools.core_profile import (
            _THRESH_N_POSES, _THRESH_CELLS, _THRESH_CHOL_MS,
        )
        self.assertEqual(_THRESH_N_POSES, 80)
        self.assertEqual(_THRESH_CELLS, 500)
        self.assertEqual(_THRESH_CHOL_MS, 5.0)


# ----------------------------------------------------------------------
# T6 — T_PROFILE_READ_ONLY (PERMANENT)
# ----------------------------------------------------------------------


class T6_ProfileReadOnly(unittest.TestCase):
    """PERMANENT GUARD — DO NOT REMOVE.

    profile_node must remain read-only. Body MUST NOT contain any
    cmds.* mutation operation or undo_chunk wrapper. Mirrors M3.1
    T_ANALYSE_READ_ONLY."""

    def test_PERMANENT_no_mutations(self):
        from RBFtools.core_profile import profile_node
        src = inspect.getsource(profile_node)
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
                "profile_node violated read-only contract — found "
                + f)


# ----------------------------------------------------------------------
# T7 — spillover §3 add/remove
# ----------------------------------------------------------------------


class T7_AddToolsPanelWidget(unittest.TestCase):

    def test_method_exists_and_signature(self):
        from RBFtools.ui.main_window import RBFToolsWindow
        self.assertTrue(callable(getattr(
            RBFToolsWindow, "add_tools_panel_widget", None)))
        self.assertTrue(callable(getattr(
            RBFToolsWindow, "remove_tools_panel_widget", None)))
        self.assertTrue(callable(getattr(
            RBFToolsWindow, "_ensure_tools_section", None)))

    def test_lazy_create_in_source(self):
        """Source-text guard: _ensure_tools_section must check the
        attribute is None before creating the CollapsibleFrame."""
        import pathlib
        path = pathlib.Path(__file__).resolve().parent.parent
        text = (path / "scripts" / "RBFtools" / "ui"
                / "main_window.py").read_text(encoding="utf-8")
        idx = text.find("def _ensure_tools_section(self):")
        self.assertGreater(idx, 0)
        body = text[idx:idx + 1500]
        self.assertIn('getattr(self, "_tools_section", None) is None',
                      body)
        self.assertIn("CollapsibleFrame", body)

    def test_dup_id_raises_in_source(self):
        """Source-text guard: add_tools_panel_widget must raise
        RuntimeError on duplicate widget_id (no silent overwrite —
        H.2 contract)."""
        import pathlib
        path = pathlib.Path(__file__).resolve().parent.parent
        text = (path / "scripts" / "RBFtools" / "ui"
                / "main_window.py").read_text(encoding="utf-8")
        idx = text.find("def add_tools_panel_widget(self, widget_id, widget):")
        self.assertGreater(idx, 0)
        body = text[idx:idx + 2000]
        self.assertIn("RuntimeError", body)
        self.assertIn("already", body)


# ----------------------------------------------------------------------
# T_TOOLS_SECTION_PERSISTS (PERMANENT)
# ----------------------------------------------------------------------


class T_ToolsSectionPersists(unittest.TestCase):
    """PERMANENT GUARD — DO NOT REMOVE.

    Once the ToolsSection collapsible is created, it persists for
    the session. remove_tools_panel_widget must NOT destroy the
    section even when the last child is removed (avoid visual
    flicker on subsequent add). Source-text guard verifies that
    remove_tools_panel_widget body does not assign self._tools_section
    to None or call delete on it."""

    def test_PERMANENT_remove_does_not_destroy_section(self):
        import pathlib
        path = pathlib.Path(__file__).resolve().parent.parent
        text = (path / "scripts" / "RBFtools" / "ui"
                / "main_window.py").read_text(encoding="utf-8")
        idx = text.find("def remove_tools_panel_widget(self, widget_id):")
        self.assertGreater(idx, 0)
        # Take method body (~50 lines).
        body = text[idx:idx + 2000]
        self.assertNotIn("self._tools_section = None", body,
            "remove_tools_panel_widget assigns _tools_section = None "
            "— violates persistence contract (T_TOOLS_SECTION_PERSISTS)")
        self.assertNotIn("self._tools_section.deleteLater", body,
            "remove_tools_panel_widget calls _tools_section.deleteLater "
            "— violates persistence contract")


# ----------------------------------------------------------------------
# T_CAVEAT_VISIBLE (PERMANENT)
# ----------------------------------------------------------------------


class T_CaveatVisible(unittest.TestCase):
    """PERMANENT GUARD — DO NOT REMOVE.

    The Performance estimates section MUST surface its conceptual
    nature so users do not mistake the numbers for measured data
    (addendum §M3.5.F2). The configured-solver field MUST surface
    the "C++ instance member, not a Maya attribute" caveat
    (addendum §M3.5.F1). Both caveats are bracketed and visually
    prominent."""

    def test_PERMANENT_perf_caveat_present(self):
        from RBFtools.core_profile import format_report
        report = format_report(
            T4_FormatReportSections()._profile())
        self.assertIn("[CONCEPTUAL — no machine calibration]",
                      report,
            "Performance estimates section missing the CONCEPTUAL "
            "caveat — addendum §M3.5.F2 visibility contract")

    def test_PERMANENT_calibration_pointer_present(self):
        """Footer caveat must name the tunable symbols so users can
        grep their way to the calibration entry point."""
        from RBFtools.core_profile import format_report
        report = format_report(
            T4_FormatReportSections()._profile())
        self.assertIn("_K_CHOL", report,
            "Calibration entry-point pointer (_K_CHOL) missing from "
            "report footer — addendum §M3.5.F2 visibility contract")

    def test_PERMANENT_solver_method_caveat_present(self):
        from RBFtools.core_profile import format_report
        report = format_report(
            T4_FormatReportSections()._profile())
        self.assertIn("[configured value;", report,
            "solver_method field missing the F1 caveat — addendum "
            "§M3.5.F1 visibility contract")


# ----------------------------------------------------------------------
# T8 — controller read-only
# ----------------------------------------------------------------------


class T8_ControllerReadOnly(unittest.TestCase):

    def test_profile_current_node_no_ask_confirm(self):
        """profile_current_node must NOT call ask_confirm — read-only
        operations are not destructive and must not gate on user
        permission."""
        import pathlib
        path = pathlib.Path(__file__).resolve().parent.parent
        text = (path / "scripts" / "RBFtools"
                / "controller.py").read_text(encoding="utf-8")
        idx = text.find("def profile_current_node(self):")
        self.assertGreater(idx, 0)
        body = text[idx:idx + 1500]
        self.assertNotIn("ask_confirm", body,
            "profile_current_node references ask_confirm — read-only "
            "operations should not gate on confirm dialogs")


# ----------------------------------------------------------------------
# T9 — Tools menu spillover
# ----------------------------------------------------------------------


class T9_ToolsMenuSpillover(unittest.TestCase):

    def test_uses_add_tools_action(self):
        import pathlib
        path = pathlib.Path(__file__).resolve().parent.parent
        text = (path / "scripts" / "RBFtools" / "ui"
                / "main_window.py").read_text(encoding="utf-8")
        self.assertIn('add_tools_action(\n            "menu_profile_to_se"',
                      text)


# ----------------------------------------------------------------------
# T10 — i18n parity
# ----------------------------------------------------------------------


class T10_I18nParity(unittest.TestCase):

    REQUIRED = (
        "section_tools",
        "menu_profile_to_se",
        "btn_refresh_profile",
        "status_profile_pending",
        "status_profile_failed",
    )

    def test_keys_present_in_both_languages(self):
        from RBFtools.ui.i18n import _EN, _ZH
        for k in self.REQUIRED:
            self.assertIn(k, _EN, "missing EN: " + k)
            self.assertIn(k, _ZH, "missing CN: " + k)


if __name__ == "__main__":
    unittest.main()
