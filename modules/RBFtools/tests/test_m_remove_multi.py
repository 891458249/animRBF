# -*- coding: utf-8 -*-
"""2026-04-28 (M_REMOVE_MULTI) — sparse-slot cleanup after disconnect.

A bare cmds.disconnectAttr / cmds.delete leaves the multi-array
subscript ``shape.<side>[idx]`` allocated but empty — the wire is
gone but the index lingers. Subsequent queries see the slot as
"occupied" via cmds.getAttr multiIndices and the array fragments
visually in Node Editor.

The fix is to follow every successful sever with
``cmds.removeMultiInstance(target_plug, b=True)`` so the subscript
is physically destroyed. Centralised in :func:`_disconnect_or_purge`
so every public sever path inherits the cleanup.

Coverage:
* Source-scan: removeMultiInstance present in _disconnect_or_purge,
  fires inside the `if severed:` post-block (never on the failure
  path), b=True kwarg passed.
* Mock E2E: removeMultiInstance called for both unitConversion-
  delete and direct-disconnect paths; NOT called when the sever
  itself failed; b=True kwarg verified.
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
# Source-scan
# ----------------------------------------------------------------------


class TestM_REMOVE_MULTI_SourceScan(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._core = _read(_CORE_PY)

    def test_remove_multi_in_disconnect_or_purge(self):
        body = self._core.split(
            "def _disconnect_or_purge(")[1].split("\ndef ")[0]
        self.assertIn("removeMultiInstance", body,
            "_disconnect_or_purge must call cmds.removeMultiInstance "
            "after a successful sever so the multi-subscript is "
            "physically destroyed (no lingering empty-index holes).")
        # b=True is the force-break flag — required so Maya removes
        # the subscript even if internal bookkeeping still thinks
        # the slot has connections (defends against the
        # unitConversion-delete path leaving partial state).
        self.assertIn("b=True", body)

    def test_remove_multi_only_after_success(self):
        body = self._core.split(
            "def _disconnect_or_purge(")[1].split("\ndef ")[0]
        # Source-scan: the actual cmds.removeMultiInstance CALL
        # MUST be guarded by `if severed:` so a failed disconnect
        # does NOT accidentally drop a still-connected slot.
        # (The docstring mentions removeMultiInstance, so search
        # for the qualified call instead of the bare name.)
        guard_pos = body.find("if severed:")
        # Match the actual call expression (with the local var name)
        # — skips the docstring mention which uses placeholder syntax.
        rmi_pos = body.find("cmds.removeMultiInstance(target_plug")
        self.assertGreater(guard_pos, 0,
            "Expected `if severed:` guard before the "
            "cmds.removeMultiInstance call.")
        self.assertGreater(rmi_pos, guard_pos,
            "cmds.removeMultiInstance(target_plug, ...) must live "
            "inside the `if severed:` block (rmi_pos={}, "
            "guard_pos={}).".format(rmi_pos, guard_pos))


# ----------------------------------------------------------------------
# Mock E2E — runtime behaviour
# ----------------------------------------------------------------------


@unittest.skipIf(conftest._REAL_MAYA,
    "mock-dependent (cmds stubs)")
class TestM_REMOVE_MULTI_RuntimeBehavior(unittest.TestCase):

    def test_unitconv_path_calls_remove_multi(self):
        from RBFtools import core
        with mock.patch.object(core, "cmds") as mc:
            mc.listConnections.return_value = ["unitConv7"]
            mc.nodeType.return_value = "unitConversion"
            ok = core._disconnect_or_purge(
                "rbfShape", "input", 2, "boneA.rx")
        self.assertTrue(ok)
        mc.delete.assert_called_once_with("unitConv7")
        # Slot cleanup AFTER the unitConversion delete path.
        mc.removeMultiInstance.assert_called_once()
        args, kwargs = mc.removeMultiInstance.call_args
        self.assertEqual(args[0], "rbfShape.input[2]")
        self.assertIs(kwargs.get("b"), True)

    def test_direct_path_calls_remove_multi(self):
        from RBFtools import core
        with mock.patch.object(core, "cmds") as mc:
            mc.listConnections.return_value = ["boneA"]
            mc.nodeType.return_value = "joint"
            ok = core._disconnect_or_purge(
                "rbfShape", "input", 5, "boneA.tx")
        self.assertTrue(ok)
        mc.disconnectAttr.assert_called_once()
        mc.removeMultiInstance.assert_called_once()
        args, kwargs = mc.removeMultiInstance.call_args
        self.assertEqual(args[0], "rbfShape.input[5]")
        self.assertIs(kwargs.get("b"), True)

    def test_output_side_uses_correct_plug(self):
        # Driven side: target_plug must use ".output[idx]", not
        # ".input[idx]".
        from RBFtools import core
        with mock.patch.object(core, "cmds") as mc:
            mc.listConnections.return_value = ["boneX"]
            mc.nodeType.return_value = "joint"
            core._disconnect_or_purge(
                "rbfShape", "output", 1, "boneX.tx")
        args, _ = mc.removeMultiInstance.call_args
        self.assertEqual(args[0], "rbfShape.output[1]")

    def test_no_remove_multi_on_disconnect_failure(self):
        # If cmds.disconnectAttr raises, severed stays False and
        # removeMultiInstance MUST NOT fire — dropping the subscript
        # while the wire is still intact would leak a phantom
        # connection.
        from RBFtools import core
        with mock.patch.object(core, "cmds") as mc:
            mc.listConnections.return_value = ["boneA"]
            mc.nodeType.return_value = "joint"
            mc.disconnectAttr.side_effect = RuntimeError(
                "lock locked")
            ok = core._disconnect_or_purge(
                "rbfShape", "input", 0, "boneA.tx")
        self.assertFalse(ok)
        mc.removeMultiInstance.assert_not_called()

    def test_remove_multi_failure_does_not_change_return(self):
        # Best-effort cleanup: if removeMultiInstance itself raises,
        # the function still returns True (the wire is severed).
        from RBFtools import core
        with mock.patch.object(core, "cmds") as mc:
            mc.listConnections.return_value = ["boneA"]
            mc.nodeType.return_value = "joint"
            mc.removeMultiInstance.side_effect = RuntimeError(
                "child has incoming connection")
            ok = core._disconnect_or_purge(
                "rbfShape", "input", 0, "boneA.tx")
        self.assertTrue(ok)


if __name__ == "__main__":
    unittest.main()
