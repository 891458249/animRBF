# -*- coding: utf-8 -*-
"""2026-04-28 (M_BATCH_ROUTING) — tab-aware Connect / Disconnect with
per-side Batch checkboxes.

Coverage:
* Source-scan: checkbox + routed_targets API on tabbed editors;
  connect_routed / disconnect_routed in core + controller; main_window
  _gather_routed_targets + slot wiring.
* Disconnect hardening: the legacy ``try / except: pass`` swallow is
  GONE inside disconnect_routed; every failure path emits cmds.warning.
* Mock E2E: routed_targets() honours the batch flag — single active tab
  vs full sweep.
"""

from __future__ import absolute_import

import os
import unittest
from unittest import mock

import conftest


_REPO_ROOT = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..")
)
_TABBED_PY = os.path.join(
    _REPO_ROOT, "modules", "RBFtools", "scripts", "RBFtools",
    "ui", "widgets", "tabbed_source_editor.py")
_CORE_PY = os.path.join(
    _REPO_ROOT, "modules", "RBFtools", "scripts", "RBFtools",
    "core.py")
_CTRL_PY = os.path.join(
    _REPO_ROOT, "modules", "RBFtools", "scripts", "RBFtools",
    "controller.py")
_MW_PY = os.path.join(
    _REPO_ROOT, "modules", "RBFtools", "scripts", "RBFtools",
    "ui", "main_window.py")
_I18N_PY = os.path.join(
    _REPO_ROOT, "modules", "RBFtools", "scripts", "RBFtools",
    "ui", "i18n.py")


def _read(p):
    with open(p, "r", encoding="utf-8") as fh:
        return fh.read()


# ----------------------------------------------------------------------
# Source-scan
# ----------------------------------------------------------------------


class TestM_BATCH_ROUTING_SourceScan(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._tab  = _read(_TABBED_PY)
        cls._core = _read(_CORE_PY)
        cls._ctrl = _read(_CTRL_PY)
        cls._mw   = _read(_MW_PY)
        cls._i18n = _read(_I18N_PY)

    def test_tabbed_editor_has_batch_checkbox(self):
        self.assertIn("self._chk_batch", self._tab)
        self.assertIn("QtWidgets.QCheckBox", self._tab)

    def test_tabbed_editor_routed_targets_api(self):
        for fn in ("def is_batch_mode",
                   "def active_tab_target",
                   "def tab_targets",
                   "def routed_targets"):
            self.assertIn(fn, self._tab,
                "tabbed editor missing {}".format(fn))

    def test_tabbed_editor_subclass_keys(self):
        self.assertIn(
            "_batch_checkbox_key   = \"batch_all_driver_tabs\"",
            self._tab)
        self.assertIn(
            "_batch_checkbox_key = \"batch_all_driven_tabs\"",
            self._tab)

    def test_i18n_keys_present(self):
        for k in ("batch_all_driver_tabs",
                  "batch_all_driven_tabs",
                  "source_tab_batch_tip"):
            # Both EN and ZH copies — assert at least 2 occurrences
            # so a one-side regression is caught.
            self.assertGreaterEqual(
                self._i18n.count('"{}":'.format(k)), 2,
                "i18n key {} missing EN/ZH parity".format(k))

    def test_core_routed_apis_present(self):
        for fn in ("def connect_routed",
                   "def disconnect_routed",
                   "def _flatten_targets"):
            self.assertIn(fn, self._core,
                "core missing {}".format(fn))

    def test_core_disconnect_routed_no_silent_swallow(self):
        # Hard red line: the legacy `try: ... except: pass` swallow is
        # gone in disconnect_routed. Every failure path must reach
        # cmds.warning so the user never sees "nothing happened".
        # Source-scan extracts the function body and checks for the
        # forbidden bare pass.
        body = self._core.split(
            "def disconnect_routed(")[1].split("\ndef ")[0]
        self.assertNotIn("except Exception:\n            pass", body,
            "disconnect_routed must NOT swallow exceptions silently")
        self.assertIn("cmds.warning", body)
        self.assertIn("listConnections", body)
        self.assertIn("plugs=True", body)

    def test_core_attribute_query_defense(self):
        # Connect path verifies attr existence before connectAttr.
        body = self._core.split(
            "def _flatten_targets(")[1].split("\ndef ")[0]
        self.assertIn("cmds.attributeQuery", body)
        self.assertIn("exists=True", body)

    def test_controller_routed_apis_present(self):
        self.assertIn("def connect_routed", self._ctrl)
        self.assertIn("def disconnect_routed", self._ctrl)
        self.assertIn(
            "core.connect_routed(node, driver_targets, driven_targets)",
            self._ctrl)
        self.assertIn(
            "core.disconnect_routed(node, driver_targets, driven_targets)",
            self._ctrl)

    def test_main_window_uses_routed_path(self):
        # _on_connect / _on_disconnect drive the new ctrl.connect_routed
        # / disconnect_routed APIs. Legacy connect_poses /
        # disconnect_outputs callsites in those two slots are gone.
        self.assertIn("def _gather_routed_targets", self._mw)
        on_connect = self._mw.split(
            "def _on_connect(self):")[1].split("\n    def ")[0]
        self.assertIn("connect_routed", on_connect)
        self.assertNotIn(
            "self._ctrl.connect_poses(", on_connect,
            "_on_connect must use the routed path, not the legacy "
            "flat-aggregate connect_poses.")
        on_disc = self._mw.split(
            "def _on_disconnect(self):")[1].split("\n    def ")[0]
        self.assertIn("disconnect_routed", on_disc)
        self.assertNotIn(
            "self._ctrl.disconnect_outputs(", on_disc,
            "_on_disconnect must use the routed path, not the "
            "legacy flat disconnect_outputs.")


# ----------------------------------------------------------------------
# Mock E2E — routed_targets honours the batch flag
# ----------------------------------------------------------------------


@unittest.skipIf(conftest._REAL_MAYA,
    "mock-dependent (PySide / cmds stubs)")
class TestM_BATCH_ROUTING_RoutedTargets(unittest.TestCase):

    def _make_editor(self, tabs, active_idx=0, batch=False):
        from RBFtools.ui.widgets.tabbed_source_editor import (
            _TabbedSourceEditorBase)
        ed = _TabbedSourceEditorBase.__new__(_TabbedSourceEditorBase)
        ed._tabs = mock.MagicMock()
        ed._tabs.count.return_value = len(tabs)
        ed._tabs.currentIndex.return_value = active_idx

        def widget_at(i):
            if 0 <= i < len(tabs):
                node, attrs = tabs[i]
                w = mock.MagicMock()
                w.node_name.return_value = node
                w.selected_attrs.return_value = list(attrs)
                return w
            return None
        ed._tabs.widget.side_effect = widget_at
        ed._chk_batch = mock.MagicMock()
        ed._chk_batch.isChecked.return_value = bool(batch)
        return ed

    def test_active_tab_only_when_batch_off(self):
        ed = self._make_editor(
            tabs=[("boneA", ["tx", "ty"]),
                  ("boneB", ["rx"])],
            active_idx=1, batch=False)
        targets = ed.routed_targets()
        self.assertEqual(targets, [("boneB", ["rx"])])

    def test_all_tabs_when_batch_on(self):
        ed = self._make_editor(
            tabs=[("boneA", ["tx", "ty"]),
                  ("boneB", ["rx"])],
            active_idx=0, batch=True)
        targets = ed.routed_targets()
        self.assertEqual(targets, [
            ("boneA", ["tx", "ty"]),
            ("boneB", ["rx"]),
        ])

    def test_empty_when_no_tabs(self):
        ed = self._make_editor(tabs=[], active_idx=-1, batch=True)
        self.assertEqual(ed.routed_targets(), [])

    def test_main_window_gather_routes_via_editors(self):
        from RBFtools.ui.main_window import RBFToolsWindow
        win = RBFToolsWindow.__new__(RBFToolsWindow)
        win._pose_editor = mock.MagicMock()
        win._pose_editor.driver_editor.routed_targets.return_value = [
            ("driverA", ["tx"])]
        win._pose_editor.driven_editor.routed_targets.return_value = [
            ("drivenX", ["rx", "ry"])]
        drv, dvn = RBFToolsWindow._gather_routed_targets(win)
        self.assertEqual(drv, [("driverA", ["tx"])])
        self.assertEqual(dvn, [("drivenX", ["rx", "ry"])])


if __name__ == "__main__":
    unittest.main()
