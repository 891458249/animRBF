"""M_B24d_matrix_followup - Matrix mode driverList wiring tests.

Lock-in coverage for the M_B24d_matrix_followup sub-task:

  * `add_driver_source` Matrix branch wires
    `driver.worldMatrix[0]` -> `shape.driverList[idx].driverInput`
    (NOT `.matrix`; see addendum
    §M_B24d_matrix_followup.matrix-vs-worldmatrix).
  * `_resolve_driver_rotate_order` connects the driver's
    `rotateOrder` -> `shape.driverInputRotateOrder[idx]` when the
    driver carries the attribute, and skips silently otherwise
    (defaulting to xyz=0).
  * `_wire_matrix_mode_data_path` post-connect verification raises
    when `listConnections` returns empty (cpp:2087-2093 early-
    return guard).
  * Atomic fail-soft rollback: a failure inside the Matrix branch
    must remove the partial `driverSource[idx]` metadata via
    `removeMultiInstance` and disconnect any matrix wiring it had
    completed (mirrors M_B24d Hardening 1 for the Generic branch).
  * Mode-exclusion semantic: existing Generic wiring + Matrix-mode
    shape => RuntimeError; existing Matrix wiring + Generic-mode
    shape => RuntimeError. Both messages reference the addendum
    anchor.

All tests are mock-only (`@skipIf(_REAL_MAYA)`); the project's
real-Maya parity comes from the existing M_B24b2 + M_B24d empirical
runs plus the source-scan permanent guards.
"""

from __future__ import absolute_import

import os
import re
import unittest
from unittest import mock

import conftest


_REPO_ROOT = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..")
)
_CORE_PY = os.path.join(
    _REPO_ROOT, "modules", "RBFtools", "scripts", "RBFtools", "core.py"
)


# ----------------------------------------------------------------------
# Shared test scaffolding
# ----------------------------------------------------------------------


def _safe_get_matrix(path, default=0):
    """safe_get patch returning Matrix mode (type=1, rbfMode=1)."""
    if path.endswith(".type"):
        return 1
    if path.endswith(".rbfMode"):
        return 1
    return default


def _safe_get_generic(path, default=0):
    """safe_get patch returning Generic mode (type=1, rbfMode=0)."""
    if path.endswith(".type"):
        return 1
    if path.endswith(".rbfMode"):
        return 0
    return default


# ----------------------------------------------------------------------
# Source-scan: Matrix wiring helpers exist + use worldMatrix[0]
# ----------------------------------------------------------------------


class TestM_B24D_MatrixFollowup_Source(unittest.TestCase):
    """Permanent-guard-shaped source scans on core.py."""

    @classmethod
    def setUpClass(cls):
        with open(_CORE_PY, "r", encoding="utf-8") as f:
            cls._src = f.read()

    def test_wire_helper_defined(self):
        self.assertIn("def _wire_matrix_mode_data_path", self._src,
            "_wire_matrix_mode_data_path helper missing")

    def test_unwire_helper_defined(self):
        self.assertIn("def _unwire_matrix_mode_data_path", self._src,
            "_unwire_matrix_mode_data_path helper missing")

    def test_rotate_order_helper_defined(self):
        self.assertIn("def _resolve_driver_rotate_order", self._src,
            "_resolve_driver_rotate_order helper missing")

    def test_uses_worldmatrix_not_local_matrix(self):
        """Red-line 5 source-scan: the Matrix wiring helper must
        connect worldMatrix[0], never the local .matrix plug."""
        wire_block = re.search(
            r"def _wire_matrix_mode_data_path.*?(?=^def\s|\Z)",
            self._src, re.M | re.S)
        self.assertIsNotNone(wire_block,
            "_wire_matrix_mode_data_path body not found")
        body = wire_block.group(0)
        self.assertIn("worldMatrix[0]", body,
            "Matrix wiring helper must use driver.worldMatrix[0] "
            "(see addendum §M_B24d_matrix_followup.matrix-vs-"
            "worldmatrix)")

    def test_post_connect_verification_present(self):
        """Hardening 2: the Matrix wiring helper must verify the
        connection landed via listConnections + raise on empty."""
        wire_block = re.search(
            r"def _wire_matrix_mode_data_path.*?(?=^def\s|\Z)",
            self._src, re.M | re.S)
        body = wire_block.group(0)
        self.assertIn("listConnections", body,
            "Matrix wiring helper must call listConnections after "
            "connectAttr (cpp:2087-2093 early-return guard)")
        self.assertIn("raise", body,
            "Matrix wiring helper must raise on empty incoming")


# ----------------------------------------------------------------------
# Mock-pattern: Matrix mode end-to-end add wiring
# ----------------------------------------------------------------------


@unittest.skipIf(conftest._REAL_MAYA,
    "mock-dependent (cmds.reset_mock / mock.patch on cmds.*)")
class TestM_B24D_MatrixFollowup_AddWires(unittest.TestCase):

    def _setup_cmds(self, has_rotate_order=True):
        from RBFtools import core  # noqa
        import maya.cmds as cmds
        cmds.reset_mock()
        cmds.objExists.return_value = True
        cmds.listRelatives.return_value = ["RBF1Shape"]
        cmds.getAttr.return_value = []
        # Post-connect verify must see a non-empty incoming list.
        cmds.listConnections.return_value = ["drv1.worldMatrix[0]"]
        cmds.attributeQuery.return_value = bool(has_rotate_order)
        cmds.connectAttr.side_effect = None
        return cmds

    def test_matrix_mode_connects_worldmatrix(self):
        cmds = self._setup_cmds()
        from RBFtools import core
        with mock.patch("RBFtools.core.safe_get",
                        side_effect=_safe_get_matrix):
            core.add_driver_source("RBF1", "drv1", ["translateX"])
        sources = [c[0][0] for c in cmds.connectAttr.call_args_list]
        targets = [c[0][1] for c in cmds.connectAttr.call_args_list]
        self.assertTrue(any(".worldMatrix[0]" in s for s in sources),
            "Matrix mode add must connect driver.worldMatrix[0] "
            "(not .matrix)")
        self.assertFalse(
            any(s.endswith(".matrix") for s in sources),
            "Red line 5: Matrix mode must NOT connect local .matrix")
        self.assertTrue(
            any(".driverList[" in t and ".driverInput" in t
                for t in targets),
            "Matrix mode must target driverList[idx].driverInput")

    def test_matrix_mode_connects_rotate_order_when_present(self):
        cmds = self._setup_cmds(has_rotate_order=True)
        from RBFtools import core
        with mock.patch("RBFtools.core.safe_get",
                        side_effect=_safe_get_matrix):
            core.add_driver_source("RBF1", "drv1", ["translateX"])
        sources = [c[0][0] for c in cmds.connectAttr.call_args_list]
        targets = [c[0][1] for c in cmds.connectAttr.call_args_list]
        self.assertTrue(
            any(s.endswith(".rotateOrder") for s in sources),
            "rotateOrder sync should fire when driver has the attr")
        self.assertTrue(
            any(".driverInputRotateOrder[" in t for t in targets),
            "rotateOrder must wire to driverInputRotateOrder[idx]")

    def test_matrix_mode_skips_rotate_order_when_absent(self):
        cmds = self._setup_cmds(has_rotate_order=False)
        from RBFtools import core
        with mock.patch("RBFtools.core.safe_get",
                        side_effect=_safe_get_matrix):
            core.add_driver_source("RBF1", "drv1", ["translateX"])
        sources = [c[0][0] for c in cmds.connectAttr.call_args_list]
        self.assertFalse(
            any(s.endswith(".rotateOrder") for s in sources),
            "rotateOrder must NOT be wired when driver lacks the "
            "attribute (fallback to Maya default xyz=0)")

    def test_matrix_mode_no_input_array_writes(self):
        """Matrix branch must NOT touch shape.input[] (that is the
        Generic-mode data path)."""
        cmds = self._setup_cmds()
        from RBFtools import core
        with mock.patch("RBFtools.core.safe_get",
                        side_effect=_safe_get_matrix):
            core.add_driver_source(
                "RBF1", "drv1", ["translateX", "translateY"])
        targets = [c[0][1] for c in cmds.connectAttr.call_args_list]
        self.assertFalse(
            any(".input[" in t for t in targets),
            "Matrix branch must not write into shape.input[]")


# ----------------------------------------------------------------------
# Mock-pattern: Post-connect verification (Hardening 2)
# ----------------------------------------------------------------------


@unittest.skipIf(conftest._REAL_MAYA,
    "mock-dependent (cmds.reset_mock / mock.patch on cmds.*)")
class TestM_B24D_MatrixFollowup_VerifyGuard(unittest.TestCase):

    def test_silent_connect_failure_raises(self):
        """When listConnections returns [] after the connectAttr
        call, the helper must raise so we never silently feed
        cpp:2087-2093's early-return guard."""
        from RBFtools import core
        import maya.cmds as cmds
        cmds.reset_mock()
        cmds.objExists.return_value = True
        cmds.listRelatives.return_value = ["RBF1Shape"]
        cmds.getAttr.return_value = []
        cmds.attributeQuery.return_value = True
        cmds.listConnections.return_value = []   # silent fail
        cmds.connectAttr.side_effect = None
        with mock.patch("RBFtools.core.safe_get",
                        side_effect=_safe_get_matrix):
            with self.assertRaises(RuntimeError) as ctx:
                core.add_driver_source(
                    "RBF1", "drv1", ["translateX"])
        msg = str(ctx.exception)
        self.assertIn("driverInput", msg)
        self.assertIn("2087", msg)


# ----------------------------------------------------------------------
# Mock-pattern: Atomic fail-soft rollback in Matrix branch
# ----------------------------------------------------------------------


@unittest.skipIf(conftest._REAL_MAYA,
    "mock-dependent (cmds.reset_mock / mock.patch on cmds.*)")
class TestM_B24D_MatrixFollowup_AtomicRollback(unittest.TestCase):

    def test_matrix_wire_failure_removes_metadata(self):
        from RBFtools import core
        import maya.cmds as cmds
        cmds.reset_mock()
        cmds.objExists.return_value = True
        cmds.listRelatives.return_value = ["RBF1Shape"]
        cmds.getAttr.return_value = []
        cmds.attributeQuery.return_value = True
        cmds.listConnections.return_value = ["drv1.worldMatrix[0]"]

        def fake_connect(*args, **kwargs):
            # Metadata message connect succeeds; the matrix data
            # path connectAttr blows up.
            if ".driverInput" in args[1]:
                raise RuntimeError("simulated driverInput failure")
            return None
        cmds.connectAttr.side_effect = fake_connect

        with mock.patch("RBFtools.core.safe_get",
                        side_effect=_safe_get_matrix):
            with self.assertRaises(RuntimeError):
                core.add_driver_source(
                    "RBF1", "drv1", ["translateX"])
        rmi_calls = list(cmds.removeMultiInstance.call_args_list)
        self.assertGreaterEqual(len(rmi_calls), 1,
            "Matrix branch failure must roll back driverSource[idx]")
        rmi_target = rmi_calls[0][0][0]
        self.assertIn("driverSource[", rmi_target,
            "Rollback target must be the driverSource[idx] plug")


# ----------------------------------------------------------------------
# Mock-pattern: Mode-exclusion semantic (Hardening 1)
# ----------------------------------------------------------------------


@unittest.skipIf(conftest._REAL_MAYA,
    "mock-dependent (cmds.reset_mock / mock.patch on cmds.*)")
class TestM_B24D_MatrixFollowup_ModeExclusion(unittest.TestCase):

    def test_matrix_mode_with_existing_generic_wiring_raises(self):
        """Existing input[] populated indices + Matrix-mode shape =>
        RuntimeError pointing at the addendum anchor."""
        from RBFtools import core
        import maya.cmds as cmds
        cmds.reset_mock()
        cmds.objExists.return_value = True
        cmds.listRelatives.return_value = ["RBF1Shape"]

        def fake_get_attr(plug, *args, **kwargs):
            if plug.endswith(".input"):
                return [0]   # populated -> Generic wiring present
            if plug.endswith(".driverList"):
                return []
            if plug.endswith(".driverSource"):
                return []
            return []
        cmds.getAttr.side_effect = fake_get_attr
        cmds.listConnections.return_value = []
        cmds.attributeQuery.return_value = True

        with mock.patch("RBFtools.core.safe_get",
                        side_effect=_safe_get_matrix):
            with self.assertRaises(RuntimeError) as ctx:
                core.add_driver_source(
                    "RBF1", "drv1", ["translateX"])
        msg = str(ctx.exception)
        self.assertIn("Matrix mode", msg)
        self.assertIn("Generic mode", msg)
        self.assertIn("mode-exclusion-semantic", msg)

    def test_generic_mode_with_existing_matrix_wiring_raises(self):
        """Existing driverList[d].driverInput connection + Generic-
        mode shape => RuntimeError pointing at the addendum anchor."""
        from RBFtools import core
        import maya.cmds as cmds
        cmds.reset_mock()
        cmds.objExists.return_value = True
        cmds.listRelatives.return_value = ["RBF1Shape"]

        def fake_get_attr(plug, *args, **kwargs):
            if plug.endswith(".input"):
                return []
            if plug.endswith(".driverList"):
                return [0]
            if plug.endswith(".driverSource"):
                return []
            return []
        cmds.getAttr.side_effect = fake_get_attr

        def fake_list_connections(plug, *args, **kwargs):
            if ".driverList[" in plug and ".driverInput" in plug:
                return ["other.worldMatrix[0]"]
            return []
        cmds.listConnections.side_effect = fake_list_connections
        cmds.attributeQuery.return_value = True

        with mock.patch("RBFtools.core.safe_get",
                        side_effect=_safe_get_generic):
            with self.assertRaises(RuntimeError) as ctx:
                core.add_driver_source(
                    "RBF1", "drv1", ["translateX"])
        msg = str(ctx.exception)
        self.assertIn("Matrix mode", msg)
        self.assertIn("Generic mode", msg)
        self.assertIn("mode-exclusion-semantic", msg)


# ----------------------------------------------------------------------
# Mock-pattern: remove_driver_source Matrix branch unwire
# ----------------------------------------------------------------------


@unittest.skipIf(conftest._REAL_MAYA,
    "mock-dependent (cmds.reset_mock / mock.patch on cmds.*)")
class TestM_B24D_MatrixFollowup_RemoveUnwires(unittest.TestCase):

    def test_remove_disconnects_matrix_data_path(self):
        from RBFtools import core
        import maya.cmds as cmds
        cmds.reset_mock()
        cmds.objExists.return_value = True
        cmds.listRelatives.return_value = ["RBF1Shape"]

        def fake_get_attr(plug, *args, **kwargs):
            if plug.endswith(".driverSource"):
                return [0]
            return []
        cmds.getAttr.side_effect = fake_get_attr

        def fake_list_connections(plug, *args, **kwargs):
            if plug.endswith(".driverSource_node"):
                return ["drv1"]
            return []
        cmds.listConnections.side_effect = fake_list_connections
        cmds.attributeQuery.return_value = True

        with mock.patch("RBFtools.core.safe_get",
                        side_effect=_safe_get_matrix):
            core.remove_driver_source("RBF1", 0)
        disc_sources = [
            c[0][0] for c in cmds.disconnectAttr.call_args_list]
        disc_targets = [
            c[0][1] for c in cmds.disconnectAttr.call_args_list]
        self.assertTrue(
            any(s.endswith(".worldMatrix[0]") for s in disc_sources),
            "remove must disconnect driver.worldMatrix[0]")
        self.assertTrue(
            any(".driverList[" in t and ".driverInput" in t
                for t in disc_targets),
            "remove must target driverList[idx].driverInput")


if __name__ == "__main__":
    unittest.main()
