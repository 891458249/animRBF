# -*- coding: utf-8 -*-
"""2026-04-28 (M_LIVE_DEBUG): permanent audit of the three live-Maya
defenses requested after the live-environment regression report.

  Defense 1 — every cmds.listConnections call site in core.py is
              defended with `or []` (or `or list()`).
  Defense 2 — _on_connect / _on_disconnect carry top-of-slot trace
              prints; _gather_routed_targets prints the gathered
              scope. The traces tell a live operator whether the
              new code path is actually loaded (vs Maya's stale
              module cache).
  Defense 3 — UI signal chain reaches the new slots (no leftover
              wiring to a legacy connect_poses / disconnect_outputs).
"""

from __future__ import absolute_import

import os
import re
import unittest


_REPO_ROOT = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..")
)
_CORE_PY = os.path.join(
    _REPO_ROOT, "modules", "RBFtools", "scripts", "RBFtools",
    "core.py")
_CTRL_PY = os.path.join(
    _REPO_ROOT, "modules", "RBFtools", "scripts", "RBFtools",
    "controller.py")
_MW_PY = os.path.join(
    _REPO_ROOT, "modules", "RBFtools", "scripts", "RBFtools",
    "ui", "main_window.py")


def _read(p):
    with open(p, "r", encoding="utf-8") as fh:
        return fh.read()


# ----------------------------------------------------------------------
# Defense 1 — listConnections returns None on empty; every call site
# MUST coerce to [] so `for x in conns` never trips a TypeError that
# would silently abort a Qt slot.
# ----------------------------------------------------------------------


class TestM_LIVE_DEBUG_ListConnectionsDefense(unittest.TestCase):

    def _audit_file(self, path):
        text = _read(path)
        lines = text.splitlines()
        undefended = []
        for m in re.finditer(r"cmds\.listConnections\(", text):
            ln = text.count("\n", 0, m.start()) + 1
            # Look ahead 10 lines — the assignment + closing paren
            # of a wrapped listConnections call cannot reasonably
            # span more than that. Ten is generous.
            block = "\n".join(lines[ln - 1:ln + 9])
            if "or []" not in block and "or list()" not in block:
                undefended.append((ln, lines[ln - 1].strip()[:90]))
        return undefended

    def test_core_py_all_defended(self):
        undefended = self._audit_file(_CORE_PY)
        self.assertEqual(undefended, [],
            "core.py contains undefended listConnections calls — "
            "Maya returns None on empty, every site MUST end with "
            "`or []` to avoid a TypeError that aborts the Qt "
            "slot silently. Sites: {}".format(undefended))

    def test_controller_py_all_defended(self):
        undefended = self._audit_file(_CTRL_PY)
        self.assertEqual(undefended, [])

    def test_main_window_py_all_defended(self):
        undefended = self._audit_file(_MW_PY)
        self.assertEqual(undefended, [])


# ----------------------------------------------------------------------
# Defense 2 — top-of-slot trace prints
# ----------------------------------------------------------------------


class TestM_LIVE_DEBUG_TraceLogs(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._mw = _read(_MW_PY)

    def test_on_connect_prints_marker(self):
        body = self._mw.split(
            "def _on_connect(self):")[1].split("\n    def ")[0]
        self.assertIn(">>> ON_CONNECT TRIGGERED <<<", body,
            "_on_connect must print a top-of-slot marker so a live "
            "operator can verify the new code path is loaded.")

    def test_on_disconnect_prints_marker(self):
        body = self._mw.split(
            "def _on_disconnect(self):")[1].split("\n    def ")[0]
        self.assertIn(">>> ON_DISCONNECT TRIGGERED <<<", body)

    def test_gather_routed_targets_prints_scope(self):
        body = self._mw.split(
            "def _gather_routed_targets(self):")[1].split(
            "\n    def ")[0]
        self.assertIn("GATHERED DRIVERS", body)
        self.assertIn("GATHERED DRIVENS", body)


# ----------------------------------------------------------------------
# Defense 3 — UI signal chain reaches the new slots
# ----------------------------------------------------------------------


class TestM_LIVE_DEBUG_SignalChain(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._mw = _read(_MW_PY)

    def test_btn_connect_button_to_panel_signal(self):
        self.assertIn(
            "self._btn_connect.clicked.connect(self.connectRequested)",
            self._mw)

    def test_btn_disconnect_button_to_panel_signal(self):
        self.assertIn(
            "self._btn_disconnect.clicked.connect"
            "(self.disconnectRequested)",
            self._mw)

    def test_panel_signal_to_new_slots(self):
        self.assertIn(
            "pe.connectRequested.connect(self._on_connect)", self._mw)
        self.assertIn(
            "pe.disconnectRequested.connect(self._on_disconnect)",
            self._mw)

    def test_no_legacy_slot_wiring_left(self):
        # The panel signals must NOT route to legacy
        # connect_poses / disconnect_outputs slots — the pose-editor
        # panel emits connectRequested / disconnectRequested and
        # they go to the routed _on_connect / _on_disconnect ONLY.
        self.assertNotIn(
            "pe.connectRequested.connect(self.connect_poses)",
            self._mw)
        self.assertNotIn(
            "pe.disconnectRequested.connect"
            "(self.disconnect_outputs)",
            self._mw)


if __name__ == "__main__":
    unittest.main()
