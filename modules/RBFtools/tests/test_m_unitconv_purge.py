# -*- coding: utf-8 -*-
"""2026-04-28 (M_UNITCONV_PURGE) — unitConversion ghost-node defense.

Maya silently inserts a ``unitConversion`` node between rotation
plugs (degrees) and dimensionless RBF input/output array entries
(radians). Without skipConversionNodes=True, listConnections-based
queries miss the real subscript; without an explicit delete on
disconnect, orphan unitConversion nodes accumulate and pollute
future queries.

Coverage:
* Source-scan: skipConversionNodes=True on the four query helpers,
  presence of _disconnect_or_purge / _direct_node_at_subscript /
  _resolved_pairs_at, callers route through _disconnect_or_purge
  (no bare cmds.disconnectAttr in the public API surface for the
  rotation-channel-prone paths).
* Mock E2E: _direct_node_at_subscript returns the immediate
  conversion node; _disconnect_or_purge deletes it; otherwise
  falls back to disconnectAttr.
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


class TestM_UNITCONV_PURGE_SourceScan(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._core = _read(_CORE_PY)

    def test_helpers_present(self):
        for sym in ("def _direct_node_at_subscript",
                    "def _disconnect_or_purge",
                    "def _resolved_pairs_at"):
            self.assertIn(sym, self._core,
                "core missing {}".format(sym))

    def test_subscript_lookups_skip_conversion(self):
        # _subscript_of_existing_input/output MUST set
        # skipConversionNodes=True so a rotation channel routed
        # via unitConversion is identified by its real subscript
        # on shape.input[]/output[].
        for fn in ("_subscript_of_existing_input",
                   "_subscript_of_existing_output"):
            body = self._core.split(
                "def {}(".format(fn))[1].split("\ndef ")[0]
            self.assertIn("skipConversionNodes=True", body,
                "{} must use skipConversionNodes=True so "
                "unitConversion-mediated rotation channels are "
                "correctly identified".format(fn))

    def test_resolved_pairs_at_skips_conversion(self):
        body = self._core.split(
            "def _resolved_pairs_at(")[1].split("\ndef ")[0]
        self.assertIn("skipConversionNodes=True", body,
            "_resolved_pairs_at must skipConversion so the "
            "(idx, bone, plug) triple identifies the REAL bone, "
            "not the intermediate conversion node.")

    def test_disconnect_or_purge_deletes_unit_conversion(self):
        body = self._core.split(
            "def _disconnect_or_purge(")[1].split("\ndef ")[0]
        # Must check nodeType against unitConversion AND call delete.
        self.assertIn("nodeType", body)
        self.assertIn("unitConversion", body)
        self.assertIn("cmds.delete", body)
        # Falls back to cmds.disconnectAttr when not a conversion.
        self.assertIn("cmds.disconnectAttr", body)

    def test_disconnect_helpers_route_through_purge(self):
        for fn in ("_disconnect_bone_specific",
                   "_disconnect_bone_all"):
            body = self._core.split(
                "def {}(".format(fn))[1].split("\ndef ")[0]
            self.assertIn("_disconnect_or_purge", body,
                "{} must route severing through _disconnect_or_purge "
                "so any unitConversion ghost is deleted, not "
                "left dangling".format(fn))

    def test_connect_routed_break_step_uses_purge(self):
        body = self._core.split(
            "def connect_routed(")[1].split("\ndef ")[0]
        # Both sides must purge before reconnecting.
        self.assertIn("_disconnect_or_purge(shape, \"input\"", body)
        self.assertIn("_disconnect_or_purge(shape, \"output\"",
                      body)


# ----------------------------------------------------------------------
# Mock E2E — runtime behaviour
# ----------------------------------------------------------------------


@unittest.skipIf(conftest._REAL_MAYA,
    "mock-dependent (cmds stubs)")
class TestM_UNITCONV_PURGE_RuntimeBehavior(unittest.TestCase):

    def test_direct_node_at_subscript_returns_conversion_node(self):
        from RBFtools import core
        with mock.patch.object(core, "cmds") as mc:
            mc.listConnections.return_value = ["unitConv42"]
            self.assertEqual(
                core._direct_node_at_subscript(
                    "rbfShape", "input", 0),
                "unitConv42")

    def test_direct_node_at_subscript_handles_none(self):
        from RBFtools import core
        with mock.patch.object(core, "cmds") as mc:
            mc.listConnections.return_value = None
            self.assertIsNone(
                core._direct_node_at_subscript(
                    "rbfShape", "input", 0))

    def test_disconnect_or_purge_deletes_when_unitconv(self):
        from RBFtools import core
        with mock.patch.object(core, "cmds") as mc:
            mc.listConnections.return_value = ["unitConv99"]
            mc.nodeType.return_value = "unitConversion"
            mc.delete.return_value = None
            ok = core._disconnect_or_purge(
                "rbfShape", "input", 0, "boneA.rx")
        self.assertTrue(ok)
        mc.delete.assert_called_once_with("unitConv99")
        mc.disconnectAttr.assert_not_called()

    def test_disconnect_or_purge_falls_back_to_disconnectAttr(self):
        from RBFtools import core
        with mock.patch.object(core, "cmds") as mc:
            # Direct node is the bone itself, NOT a conversion.
            mc.listConnections.return_value = ["boneA"]
            mc.nodeType.return_value = "joint"
            ok = core._disconnect_or_purge(
                "rbfShape", "input", 0, "boneA.tx")
        self.assertTrue(ok)
        mc.delete.assert_not_called()
        mc.disconnectAttr.assert_called_once()

    def test_subscript_lookup_finds_via_skipConv(self):
        # When unitConversion is in the path, skipConversionNodes=True
        # asks Maya to surface the FINAL destination
        # ("rbfShape.input[3]") rather than the intermediate
        # "unitConv42.input". Our wrapper passes the kwarg, so the
        # mock returns the resolved plug; the helper extracts
        # subscript 3 successfully.
        from RBFtools import core
        with mock.patch.object(core, "cmds") as mc:
            mc.listConnections.return_value = ["rbfShape.input[3]"]
            self.assertEqual(
                core._subscript_of_existing_input(
                    "boneA.rx", "rbfShape"), 3)
            # Verify skipConversionNodes was actually passed.
            kwargs = mc.listConnections.call_args.kwargs
            self.assertIs(kwargs.get("skipConversionNodes"), True)


if __name__ == "__main__":
    unittest.main()
