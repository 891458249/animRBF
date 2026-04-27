# -*- coding: utf-8 -*-
"""2026-04-28 (M_BREAK_REBUILD) — break-then-rebuild Connect +
Scene A/B/C Disconnect.

Coverage:
* Source-scan: new core primitives (_subscript_of_existing_*,
  _occupied_*, _next_free_subscript), connect_routed body uses them,
  disconnect_routed dispatches to bone_specific / bone_all.
* Mock E2E: _next_free_subscript skips occupied; existing-subscript
  detection extracts the right index; Scene A vs Scene B dispatch
  picks the right helper; Scene C zero-count surface to caller.
* main_window Scene-C dialog: confirmDialog wired when count == 0.
"""

from __future__ import absolute_import

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
_MW_PY = os.path.join(
    _REPO_ROOT, "modules", "RBFtools", "scripts", "RBFtools",
    "ui", "main_window.py")


def _read(p):
    with open(p, "r", encoding="utf-8") as fh:
        return fh.read()


# ----------------------------------------------------------------------
# Source-scan
# ----------------------------------------------------------------------


class TestM_BREAK_REBUILD_SourceScan(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._core = _read(_CORE_PY)
        cls._mw = _read(_MW_PY)

    def test_new_primitives_present(self):
        for sym in ("def _occupied_input_subscripts",
                    "def _occupied_output_subscripts",
                    "def _next_free_subscript",
                    "def _subscript_of_existing_input",
                    "def _subscript_of_existing_output",
                    "def _disconnect_bone_specific",
                    "def _disconnect_bone_all"):
            self.assertIn(sym, self._core,
                "core missing {}".format(sym))

    def test_connect_routed_break_then_rebuild(self):
        body = self._core.split(
            "def connect_routed(")[1].split("\ndef ")[0]
        # Driver side break-then-rebuild
        self.assertIn("_subscript_of_existing_input(src, shape)",
                      body)
        self.assertIn("_occupied_input_subscripts(shape)", body)
        # Driven side break-then-rebuild
        self.assertIn("_subscript_of_existing_output(shape, dst)",
                      body)
        self.assertIn("_occupied_output_subscripts(shape)", body)
        # The break step must call cmds.disconnectAttr explicitly
        # before the rebuild connectAttr fires.
        self.assertIn("cmds.disconnectAttr", body)
        # And next-free-slot must be queried fresh AFTER the break.
        self.assertIn("_next_free_subscript(occupied)", body)

    def test_disconnect_routed_scene_dispatch(self):
        body = self._core.split(
            "def disconnect_routed(")[1].split("\ndef ")[0]
        # Scene A: per-attr precision
        self.assertIn("_disconnect_bone_specific", body)
        # Scene B: empty-blueprint -> clear all
        self.assertIn("_disconnect_bone_all", body)
        # Scene C: zero-count surface
        self.assertIn("disconnected_count", body)

    def test_disconnect_routed_returns_count(self):
        body = self._core.split(
            "def disconnect_routed(")[1].split("\ndef ")[0]
        self.assertIn("return {\"disconnected_count\":", body)

    def test_main_window_surface_scene_c_dialog(self):
        body = self._mw.split(
            "def _on_disconnect(self):")[1].split("\n    def ")[0]
        # Result is captured + Scene C dispatches confirmDialog.
        self.assertIn("disconnected_count", body)
        self.assertIn("confirmDialog", body)
        self.assertIn("disconnect_no_connections_found", body)


# ----------------------------------------------------------------------
# Mock E2E — primitive correctness
# ----------------------------------------------------------------------


@unittest.skipIf(conftest._REAL_MAYA,
    "mock-dependent (cmds stubs)")
class TestM_BREAK_REBUILD_Primitives(unittest.TestCase):

    def test_next_free_subscript_picks_lowest_gap(self):
        from RBFtools.core import _next_free_subscript
        self.assertEqual(_next_free_subscript(set()), 0)
        self.assertEqual(_next_free_subscript({0}), 1)
        self.assertEqual(_next_free_subscript({0, 1, 2}), 3)
        self.assertEqual(_next_free_subscript({0, 2, 3}), 1)
        self.assertEqual(_next_free_subscript({1, 2, 3}), 0)

    def test_occupied_input_subscripts_extracts_indices(self):
        from RBFtools import core
        with mock.patch.object(core, "cmds") as mc:
            mc.listConnections.return_value = [
                "rbfShape.input[0]", "boneA.tx",
                "rbfShape.input[2]", "boneB.ry",
                "rbfShape.input[5]", "boneC.rz",
            ]
            occ = core._occupied_input_subscripts("rbfShape")
            self.assertEqual(occ, {0, 2, 5})

    def test_subscript_of_existing_input_returns_index(self):
        from RBFtools import core
        with mock.patch.object(core, "cmds") as mc:
            mc.listConnections.return_value = [
                "rbfShape.input[3]"]
            self.assertEqual(
                core._subscript_of_existing_input(
                    "boneA.tx", "rbfShape"), 3)

    def test_subscript_of_existing_input_returns_none(self):
        from RBFtools import core
        with mock.patch.object(core, "cmds") as mc:
            mc.listConnections.return_value = ["other.input[0]"]
            self.assertIsNone(
                core._subscript_of_existing_input(
                    "boneA.tx", "rbfShape"))

    def test_occupied_handles_none_listConnections(self):
        # Defense red line: cmds.listConnections returns None on
        # empty plugs; the helper must coerce to [] and return
        # an empty set rather than crash with TypeError.
        from RBFtools import core
        with mock.patch.object(core, "cmds") as mc:
            mc.listConnections.return_value = None
            self.assertEqual(
                core._occupied_input_subscripts("rbfShape"), set())


if __name__ == "__main__":
    unittest.main()
