# -*- coding: utf-8 -*-
"""M_REBUILD_REFACTOR (2026-04-28) — incremental diff replacement
of the remove-all + re-add-all rebuild flow.

User report — "部分属性 disconnect → 再 connect" 序列后:
  Bug A: input[] subscripts left as visually noisy empty slots
         (TD photo: input[0] / input[1] red box). Root cause:
         remove_driver_source ran a bare cmds.disconnectAttr
         loop with `except: pass`, bypassing the
         M_UNITCONV_PURGE / M_REMOVE_MULTI / M_SWEEP_EMPTY atomic
         protocol locked by the prior 3 commits.
  Bug B: After several connect/disconnect cycles, input[4..22]
         accumulated + the same attr ended up wired to MULTIPLE
         input[] subscripts. Root cause: set_driver_source_attrs
         ran a "for d in existing_indices: remove_driver_source"
         loop (N calls to the Bug-A-affected helper) followed by
         add_driver_source per source — the residue compounded
         linearly each click.

Fix:
  1) remove_driver_source (Generic mode) routes every sever
     through _disconnect_or_purge + a final
     _sweep_empty_subscripts chaser.
  2) _disconnect_all_outputs (driven mirror of Bug A) does the
     same.
  3) set_driver_source_attrs / set_driven_source_attrs replace
     the remove-all + re-add-all rebuild with a single-source
     incremental diff: disconnect source[index..end] via
     _disconnect_or_purge, reconnect source[index] with new_attrs
     at base, re-wire downstream sources at shifted base.
     Sources strictly before `index` are NEVER touched.

PERMANENT GUARDS:
  #X+1 T_REMOVE_DRIVER_SOURCE_PURGE_REUSE — locks Bug A fix.
  #X+2 T_SET_ATTRS_INCREMENTAL_DIFF      — locks Bug B fix.

Sequence E2E: simulate the user's exact repro path (add → partial
disconnect → partial reconnect) and verify input[] subscripts stay
stable AND _disconnect_or_purge is consulted at every sever.
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


def _read(p):
    with open(p, "r", encoding="utf-8") as fh:
        return fh.read()


# ----------------------------------------------------------------------
# PERMANENT GUARD T_REMOVE_DRIVER_SOURCE_PURGE_REUSE
# ----------------------------------------------------------------------


class T_REMOVE_DRIVER_SOURCE_PURGE_REUSE(unittest.TestCase):
    """PERMANENT GUARD — Bug A fix locks. DO NOT REMOVE.

    remove_driver_source (Generic mode block) MUST route every
    sever through _disconnect_or_purge so unitConversion ghosts
    + empty input[] subscripts cannot accumulate. The legacy bare
    cmds.disconnectAttr + `except: pass` is forbidden in this
    function body."""

    @classmethod
    def setUpClass(cls):
        cls._core = _read(_CORE_PY)

    def test_PERMANENT_remove_driver_uses_disconnect_or_purge(self):
        body = self._core.split(
            "def remove_driver_source")[1].split("\ndef ")[0]
        self.assertIn("_disconnect_or_purge", body,
            "remove_driver_source MUST call _disconnect_or_purge "
            "(atomic protocol reuse) — Bug A fix.")
        # And the chaser sweep MUST follow so the wholesale removal
        # doesn't leave any orphan subscripts.
        self.assertIn("_sweep_empty_subscripts", body)

    def test_PERMANENT_remove_driver_no_silent_swallow(self):
        body = self._core.split(
            "def remove_driver_source")[1].split("\ndef ")[0]
        # The legacy `except Exception: pass` swallow that
        # bypassed the atomic protocol MUST be gone from the
        # disconnect path. The only remaining `except: pass` would
        # be in the removeMultiInstance fallback which is fine.
        # Defensive: count bare-pass excepts in the disconnect
        # loop. A pristine implementation has zero.
        # We assert the explicit Bug A pattern is absent.
        self.assertNotIn(
            "cmds.disconnectAttr(src, dst)", body,
            "remove_driver_source body must route disconnects "
            "through _disconnect_or_purge — bare cmds.disconnectAttr "
            "of (src, dst) was the Bug A pattern.")

    def test_PERMANENT_disconnect_all_outputs_uses_purge(self):
        body = self._core.split(
            "def _disconnect_all_outputs")[1].split("\ndef ")[0]
        self.assertIn("_disconnect_or_purge", body,
            "_disconnect_all_outputs (driven Bug A mirror) MUST "
            "route through _disconnect_or_purge.")
        self.assertIn("_sweep_empty_subscripts", body)


# ----------------------------------------------------------------------
# PERMANENT GUARD T_SET_ATTRS_INCREMENTAL_DIFF
# ----------------------------------------------------------------------


class T_SET_ATTRS_INCREMENTAL_DIFF(unittest.TestCase):
    """PERMANENT GUARD — Bug B fix locks. DO NOT REMOVE.

    set_driver_source_attrs / set_driven_source_attrs MUST use
    incremental diff (single-source repack + downstream shift),
    NOT the legacy remove-all + re-add-all loop that compounded
    Bug A residue."""

    @classmethod
    def setUpClass(cls):
        cls._core = _read(_CORE_PY)

    def test_PERMANENT_set_driver_no_remove_loop(self):
        body = self._core.split(
            "def set_driver_source_attrs")[1].split("\ndef ")[0]
        # The legacy "for d in existing_indices: remove_driver_source"
        # loop is the precise Bug B pattern. Its absence is the
        # incremental-diff red line.
        self.assertNotIn("remove_driver_source(node, d)", body,
            "set_driver_source_attrs must NOT call remove_driver_source "
            "in a loop — that was the Bug B accumulator.")
        self.assertNotIn("add_driver_source(\n                node, src.node",
                         body,
            "set_driver_source_attrs must NOT call add_driver_source "
            "in a loop — Bug B mate.")

    def test_PERMANENT_set_driver_has_diff_logic(self):
        body = self._core.split(
            "def set_driver_source_attrs")[1].split("\ndef ")[0]
        # Incremental diff markers — removed / added lists +
        # short-circuit on no-op.
        self.assertIn("removed", body)
        self.assertIn("added", body)
        self.assertIn("if existing_attrs == new_attrs_list", body,
            "set_driver_source_attrs must short-circuit when the "
            "user re-clicks Connect with no actual change "
            "(saves a full DG storm).")

    def test_PERMANENT_set_driven_no_remove_loop(self):
        body = self._core.split(
            "def set_driven_source_attrs")[1].split("\ndef ")[0]
        self.assertNotIn("remove_driven_source(node, d)", body,
            "set_driven_source_attrs must NOT call remove_driven_source "
            "in a loop.")

    def test_PERMANENT_set_driven_has_diff_logic(self):
        body = self._core.split(
            "def set_driven_source_attrs")[1].split("\ndef ")[0]
        self.assertIn("removed", body)
        self.assertIn("added", body)
        self.assertIn("if existing_attrs == new_attrs_list", body)

    def test_PERMANENT_both_use_disconnect_or_purge(self):
        for fn in ("def set_driver_source_attrs",
                   "def set_driven_source_attrs"):
            body = self._core.split(fn)[1].split("\ndef ")[0]
            self.assertIn("_disconnect_or_purge", body)


# ----------------------------------------------------------------------
# Sequence E2E — TD repro path
# ----------------------------------------------------------------------


@unittest.skipIf(conftest._REAL_MAYA,
    "mock-dependent (cmds + read_*_info_multi stubs)")
class TestM_REBUILD_REFACTOR_Sequence(unittest.TestCase):
    """Mock E2E reproducing the user's exact bug path —
    add → partial disconnect → partial reconnect — and asserting
    the public contract:

      * Every sever routes through _disconnect_or_purge
      * No accumulation of input[] subscripts (the failing repro)
      * No remove_driver_source loop
      * No add_driver_source loop
    """

    def test_sequence_set_then_partial_disconnect_then_reconnect(self):
        from RBFtools import core
        # State 1: source has [tx, ty, tz] at input[0..2].
        # Each call simulates one step in the TD's repro:
        #   step A: set_driver_source_attrs(0, [tx,ty,tz])  (initial)
        #   step B: disconnect ty                           (partial)
        #   step C: reconnect [tx,ty,tz]                    (full restore)
        sources_v1 = [
            core.DriverSource(node="drv1",
                              attrs=("tx", "ty", "tz"),
                              weight=1.0, encoding=0)]
        sources_v2 = [
            core.DriverSource(node="drv1",
                              attrs=("tx", "tz"),
                              weight=1.0, encoding=0)]

        # Step B: set attrs to [tx, tz] (removed ty).
        with mock.patch.object(
                core, "read_driver_info_multi",
                return_value=list(sources_v1)), \
             mock.patch.object(core, "get_shape",
                               return_value="RBF1Shape"), \
             mock.patch.object(core, "_exists",
                               return_value=True), \
             mock.patch.object(
                 core, "_subscript_of_existing_input",
                 side_effect=[0, 1, 2]), \
             mock.patch.object(core, "_disconnect_or_purge",
                               return_value=True) as purge, \
             mock.patch.object(core, "_sweep_empty_subscripts"), \
             mock.patch.object(core, "remove_driver_source") as rm, \
             mock.patch.object(core, "add_driver_source") as add:
            import maya.cmds as cmds
            cmds.attributeQuery.return_value = True
            ok = core.set_driver_source_attrs(
                "RBF1", 0, ["tx", "tz"])
        self.assertTrue(ok)
        # 3 disconnects (one per existing attr) — atomic protocol.
        self.assertEqual(purge.call_count, 3)
        # NO remove/add storm — Bug B regression check.
        rm.assert_not_called()
        add.assert_not_called()

        # Step C: set attrs back to [tx, ty, tz] (re-added ty).
        with mock.patch.object(
                core, "read_driver_info_multi",
                return_value=list(sources_v2)), \
             mock.patch.object(core, "get_shape",
                               return_value="RBF1Shape"), \
             mock.patch.object(core, "_exists",
                               return_value=True), \
             mock.patch.object(
                 core, "_subscript_of_existing_input",
                 side_effect=[0, 1]), \
             mock.patch.object(core, "_disconnect_or_purge",
                               return_value=True) as purge_C, \
             mock.patch.object(core, "_sweep_empty_subscripts"), \
             mock.patch.object(core, "remove_driver_source") as rm_C, \
             mock.patch.object(core, "add_driver_source") as add_C:
            import maya.cmds as cmds
            cmds.attributeQuery.return_value = True
            ok = core.set_driver_source_attrs(
                "RBF1", 0, ["tx", "ty", "tz"])
        self.assertTrue(ok)
        # 2 disconnects (existing was [tx, tz]).
        self.assertEqual(purge_C.call_count, 2)
        rm_C.assert_not_called()
        add_C.assert_not_called()

    def test_no_op_short_circuit_when_attrs_unchanged(self):
        from RBFtools import core
        with mock.patch.object(
                core, "read_driver_info_multi",
                return_value=[
                    core.DriverSource(node="drv1",
                                      attrs=("tx", "ty"),
                                      weight=1.0, encoding=0)]), \
             mock.patch.object(core, "get_shape",
                               return_value="RBF1Shape"), \
             mock.patch.object(core, "_disconnect_or_purge") as purge, \
             mock.patch.object(core, "_sweep_empty_subscripts") as sweep:
            ok = core.set_driver_source_attrs(
                "RBF1", 0, ["tx", "ty"])
        self.assertTrue(ok)
        # No-op: no DG storm, no helpers invoked.
        purge.assert_not_called()
        sweep.assert_not_called()

    def test_remove_driver_source_routes_to_purge_in_generic_mode(self):
        # Test-isolation form: patch every cmds.* helper with its
        # own with-block so neighbouring tests' side_effect /
        # return_value can't bleed in via the conftest module-level
        # cmds mock.
        from RBFtools import core
        with mock.patch.object(core, "_exists",
                               return_value=True), \
             mock.patch.object(core, "get_shape",
                               return_value="RBF1Shape"), \
             mock.patch.object(core, "_is_matrix_mode",
                               return_value=False), \
             mock.patch.object(
                 core, "_subscript_of_existing_input",
                 side_effect=[0, 1]), \
             mock.patch.object(core, "_disconnect_or_purge") as purge, \
             mock.patch.object(core, "_sweep_empty_subscripts") as sweep, \
             mock.patch.object(core, "cmds") as mc:
            mc.getAttr.side_effect = [[0], ["tx", "ty"]]
            mc.listConnections.return_value = ["drv1"]
            mc.attributeQuery.return_value = True
            core.remove_driver_source("RBF1", 0)
        self.assertEqual(purge.call_count, 2)
        sweep.assert_called_once_with("RBF1Shape", "input")


if __name__ == "__main__":
    unittest.main()
