"""M_B24d - T_M_B24D_DATA_PATH_WIRED (#31 PERMANENT GUARD).

Locks add_driver_source's data-path wiring contract and atomic
fail-soft rollback. M_B24a/b shipped the metadata write path but
left the actual driver_node -> shape.input[] data flow unwired,
so RBF compute() never saw multi-source driver data. M_B24d is
the corrective sub-task.

Hardening 6 - 4 sub-checks (source-scan core.py):
  (a) add_driver_source body wires data path to input[ (Generic
      mode) OR driverList[ (Matrix mode, M_B24d_matrix_followup) -
      either is valid; both routes flow real data into
      RBFtools.cpp compute()
  (b) _count_existing_input_attrs (or equivalent base helper)
      defined
  (c) removeMultiInstance rollback path present
  (d) _is_matrix_mode (or equivalent mode probe) defined

Plus mock-pattern tests for atomic fail-soft + Generic mode append
+ remove disconnect. The original Matrix mode NotImplementedError
test was removed when M_B24d_matrix_followup wired the Matrix
data path; see tests/test_m_b24d_matrix_followup.py for the
replacement coverage.
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
# T_M_B24D_DATA_PATH_WIRED (#31, PERMANENT GUARD)
# ----------------------------------------------------------------------


class TestM_B24D_DataPathWired(unittest.TestCase):
    """#31 - 4 source-scan sub-checks."""

    @classmethod
    def setUpClass(cls):
        with open(_CORE_PY, "r", encoding="utf-8") as f:
            cls._src = f.read()
        # Extract add_driver_source function body (def line through
        # next top-level def). The def signature wraps across lines
        # (`def add_driver_source(node, driver_node, driver_attrs,\n
        #   weight=1.0, encoding=0):`), so the regex matches the
        # def keyword and then captures everything up to the next
        # top-level `def` / `class` / EOF.
        m = re.search(
            r"^def\s+add_driver_source\b(?P<body>.*?)(?=^def\s|^class\s|\Z)",
            cls._src, re.M | re.S)
        cls._add_body = m.group("body") if m else ""

    def test_a_connectattr_to_data_path_present(self):
        """M_B24d_matrix_followup: data path can flow through
        input[] (Generic mode) OR driverList[] (Matrix mode). Either
        route satisfies the #32 contract."""
        has_generic = ".input[" in self._add_body
        has_matrix = ".driverList[" in self._add_body
        self.assertTrue(
            has_generic or has_matrix,
            "add_driver_source must wire data path to input[] "
            "(Generic) or driverList[] (Matrix) - M_B24d Generic + "
            "M_B24d_matrix_followup Matrix")

    def test_b_base_helper_present(self):
        self.assertIn("_count_existing_input_attrs", self._src,
            "core.py must define _count_existing_input_attrs (or "
            "equivalent base offset helper) for input[] append")

    def test_c_atomic_rollback_path_present(self):
        self.assertIn("removeMultiInstance", self._add_body,
            "add_driver_source body must contain removeMultiInstance "
            "rollback for atomic fail-soft (Hardening 1)")

    def test_d_matrix_mode_probe_present(self):
        self.assertIn("_is_matrix_mode", self._src,
            "core.py must define _is_matrix_mode (or equivalent "
            "mode probe) so add_driver_source can defer Matrix mode")


# ----------------------------------------------------------------------
# (Removed) Matrix mode NotImplementedError test
# ----------------------------------------------------------------------
# Original `TestM_B24D_MatrixModeDeferred.test_matrix_mode_raises_not_
# implemented` was obsoleted by M_B24d_matrix_followup, which wires the
# Matrix mode data path (driver.worldMatrix[0] -> driverList[idx].
# driverInput). Replacement coverage lives in
# tests/test_m_b24d_matrix_followup.py.


# ----------------------------------------------------------------------
# Mock-pattern: Atomic fail-soft rollback (Hardening 1)
# ----------------------------------------------------------------------


@unittest.skipIf(conftest._REAL_MAYA,
    "mock-dependent (cmds.reset_mock / mock.patch on cmds.*)")
class TestM_B24D_AtomicFailSoft(unittest.TestCase):

    def test_input_connect_failure_rolls_back_metadata(self):
        """When the input[] connectAttr raises, the metadata
        driverSource[idx] entry must be removed via
        removeMultiInstance so the node never holds half-state."""
        from RBFtools import core
        import maya.cmds as cmds
        cmds.reset_mock()
        cmds.objExists.return_value = True
        cmds.listRelatives.return_value = ["RBF1Shape"]
        cmds.getAttr.return_value = []
        # Mode: Generic (type=1, rbfMode=0).
        def safe_get_generic(path, default=0):
            if path.endswith(".type"):    return 1
            if path.endswith(".rbfMode"): return 0
            return default
        # connectAttr first call (driver.message -> driverSource_node)
        # succeeds; second call (driver.translateX -> input[0]) fails.
        call_count = {"n": 0}
        def fake_connect(*args, **kwargs):
            call_count["n"] += 1
            if ".input[" in args[1]:
                raise RuntimeError("simulated input[] failure")
            return None
        cmds.connectAttr.side_effect = fake_connect
        with mock.patch("RBFtools.core.safe_get",
                        side_effect=safe_get_generic):
            with self.assertRaises(RuntimeError):
                core.add_driver_source(
                    "RBF1", "drv1", ["translateX"])
        # Rollback: removeMultiInstance must have been called on
        # the driverSource[idx] plug.
        rmi_calls = [c for c in cmds.removeMultiInstance.call_args_list]
        self.assertGreaterEqual(len(rmi_calls), 1,
            "add_driver_source must call removeMultiInstance on the "
            "driverSource[idx] plug when data-path wiring fails")
        rmi_arg0 = rmi_calls[0][0][0]
        self.assertIn("driverSource[", rmi_arg0,
            "rollback target must be the driverSource[idx] plug")


# ----------------------------------------------------------------------
# Mock-pattern: Generic mode append base offset
# ----------------------------------------------------------------------


@unittest.skipIf(conftest._REAL_MAYA,
    "mock-dependent (cmds.reset_mock / mock.patch on cmds.*)")
class TestM_B24D_GenericModeAppend(unittest.TestCase):

    def test_input_base_offset_starts_at_zero_for_empty_node(self):
        """First add_driver_source on an empty node connects to
        input[0..n-1] (base = 0)."""
        from RBFtools import core
        import maya.cmds as cmds
        cmds.reset_mock()
        cmds.objExists.return_value = True
        cmds.listRelatives.return_value = ["RBF1Shape"]
        # getAttr default returns []; multiIndices behavior
        # implicit -> base = 0.
        cmds.getAttr.return_value = []
        def safe_get_generic(path, default=0):
            if path.endswith(".type"):    return 1
            if path.endswith(".rbfMode"): return 0
            return default
        cmds.connectAttr.side_effect = None  # all succeed
        with mock.patch("RBFtools.core.safe_get",
                        side_effect=safe_get_generic):
            core.add_driver_source(
                "RBF1", "drv1", ["translateX", "translateY"])
        # Verify connectAttr was called with input[0] and input[1].
        connect_targets = [
            c[0][1] for c in cmds.connectAttr.call_args_list
        ]
        self.assertTrue(
            any(".input[0]" in t for t in connect_targets),
            "expected connectAttr to .input[0] for first driver attr")
        self.assertTrue(
            any(".input[1]" in t for t in connect_targets),
            "expected connectAttr to .input[1] for second driver attr")


if __name__ == "__main__":
    unittest.main()
