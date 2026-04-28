# -*- coding: utf-8 -*-
"""2026-04-28 (M_SWEEP_EMPTY) — orphan-subscript final sweep at the
end of disconnect_routed.

The per-slot cleanup in _disconnect_or_purge handles the wires we
sever in the current operation, but Maya's internal bookkeeping
(especially after a unitConversion delete) and any prior tool can
leave orphan multi subscripts that no longer carry a connection
yet still occupy a slot in shape.input[] / shape.output[]. This
final sweep walks the multi-array AS A WHOLE, compares
multiIndices vs the connected-subscript set, and force-removes
any leftover.

Coverage:
* Source-scan: helper present, called for both "input" and
  "output" at the end of disconnect_routed.
* Mock E2E: orphans cleaned, fully-occupied arrays no-op,
  getAttr-None defended.
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


class TestM_SWEEP_EMPTY_SourceScan(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._core = _read(_CORE_PY)

    def test_helper_present(self):
        self.assertIn("def _sweep_empty_subscripts", self._core)

    def test_helper_uses_multiIndices(self):
        body = self._core.split(
            "def _sweep_empty_subscripts(")[1].split(
            "\ndef ")[0]
        # Must enumerate the multi via multiIndices=True so it
        # finds subscripts WITHOUT connections too (an
        # listConnections-only walk would miss orphans).
        self.assertIn("multiIndices=True", body)
        # Must compare against the occupied set so genuinely-wired
        # subscripts are NOT collateral damage.
        self.assertTrue(
            "_occupied_input_subscripts" in body and
            "_occupied_output_subscripts" in body,
            "_sweep_empty_subscripts must consult both occupied "
            "helpers to avoid removing wired subscripts.")
        self.assertIn("removeMultiInstance", body)
        self.assertIn("b=True", body)

    def test_disconnect_routed_invokes_sweep_both_sides(self):
        body = self._core.split(
            "def disconnect_routed(")[1].split("\ndef ")[0]
        self.assertIn(
            "_sweep_empty_subscripts(shape, \"input\")", body)
        self.assertIn(
            "_sweep_empty_subscripts(shape, \"output\")", body)


# ----------------------------------------------------------------------
# Mock E2E — runtime behaviour
# ----------------------------------------------------------------------


@unittest.skipIf(conftest._REAL_MAYA,
    "mock-dependent (cmds stubs)")
class TestM_SWEEP_EMPTY_RuntimeBehavior(unittest.TestCase):

    def test_removes_orphan_subscripts(self):
        # multiIndices reports {0, 1, 2, 5, 7}; only 0 and 5 are
        # actually wired. The sweep must remove 1, 2 and 7 — and
        # leave 0 + 5 alone.
        from RBFtools import core
        with mock.patch.object(core, "cmds") as mc:
            mc.getAttr.return_value = [0, 1, 2, 5, 7]
            # _occupied_input_subscripts internally calls
            # listConnections; mock pairs reflect only the live
            # wires.
            mc.listConnections.return_value = [
                "rbfShape.input[0]", "boneA.tx",
                "rbfShape.input[5]", "boneB.ry",
            ]
            n = core._sweep_empty_subscripts("rbfShape", "input")
        self.assertEqual(n, 3)
        removed = [c.args[0] for c
                   in mc.removeMultiInstance.call_args_list]
        self.assertEqual(sorted(removed),
                         ["rbfShape.input[1]",
                          "rbfShape.input[2]",
                          "rbfShape.input[7]"])
        for c in mc.removeMultiInstance.call_args_list:
            self.assertIs(c.kwargs.get("b"), True)

    def test_noop_when_fully_occupied(self):
        from RBFtools import core
        with mock.patch.object(core, "cmds") as mc:
            mc.getAttr.return_value = [0, 1]
            mc.listConnections.return_value = [
                "rbfShape.input[0]", "boneA.tx",
                "rbfShape.input[1]", "boneA.ty",
            ]
            n = core._sweep_empty_subscripts("rbfShape", "input")
        self.assertEqual(n, 0)
        mc.removeMultiInstance.assert_not_called()

    def test_handles_getAttr_returning_none(self):
        # Empty multi-array -> getAttr returns None. Helper must
        # coerce to [] and return 0 cleanly.
        from RBFtools import core
        with mock.patch.object(core, "cmds") as mc:
            mc.getAttr.return_value = None
            n = core._sweep_empty_subscripts("rbfShape", "input")
        self.assertEqual(n, 0)
        mc.removeMultiInstance.assert_not_called()

    def test_output_side_uses_output_plug(self):
        from RBFtools import core
        with mock.patch.object(core, "cmds") as mc:
            mc.getAttr.return_value = [3]
            mc.listConnections.return_value = []   # nothing wired
            core._sweep_empty_subscripts("rbfShape", "output")
        # The remove call must target ".output[3]", not ".input[3]".
        removed = [c.args[0] for c
                   in mc.removeMultiInstance.call_args_list]
        self.assertEqual(removed, ["rbfShape.output[3]"])


if __name__ == "__main__":
    unittest.main()
