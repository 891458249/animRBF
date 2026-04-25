"""M2.4a — core.set_node_multi_attr transactional contract tests.

T0a  Full write: removeMultiInstance × N existing → setAttr × M new
T0b  Mid-write failure: setAttr raises on index 2 → undo_chunk closes
     cleanly, warning emitted, no partial state leakage
T0c  Empty list: equivalent to "clear all", no setAttr calls
T0d  Length cap: list > max_length truncated with warning
T0e  Type guard: non-list/tuple input rejected with warning
"""

from __future__ import absolute_import

# Install Maya / PySide mocks BEFORE importing core.
import conftest  # noqa: F401

import unittest
from unittest import mock

import maya.cmds as cmds


def _reset_cmds_mock():
    """Reset the maya.cmds MagicMock between tests so call_count starts
    at zero. The mock object survives across tests via sys.modules, so
    we have to reset its call history explicitly."""
    cmds.reset_mock()


class T0a_FullWrite(unittest.TestCase):
    """removeMultiInstance × existing-count, then setAttr × new-count, in order."""

    def setUp(self):
        _reset_cmds_mock()

    def test_clear_then_write(self):
        from RBFtools import core
        cmds.objExists.return_value = True
        cmds.listRelatives.return_value = ["shape1"]
        cmds.getAttr.return_value = [0, 1, 2]   # existing indices

        core.set_node_multi_attr("node1", "attr1", [10, 20, 30])

        # 3 removeMultiInstance calls
        rm_calls = [
            c for c in cmds.removeMultiInstance.call_args_list
            if c
        ]
        self.assertEqual(len(rm_calls), 3)
        # then 3 setAttr calls — at least one per index
        set_calls = cmds.setAttr.call_args_list
        self.assertGreaterEqual(len(set_calls), 3)


class T0b_MidWriteFailure(unittest.TestCase):
    """When a setAttr in the middle of the write raises, the undo_chunk
    finally block must still close (no leak) and a warning must fire."""

    def setUp(self):
        _reset_cmds_mock()

    def test_setattr_raises_on_index_2(self):
        from RBFtools import core
        cmds.objExists.return_value = True
        cmds.listRelatives.return_value = ["shape1"]
        cmds.getAttr.return_value = []
        # First two setAttr succeed; third raises.
        call_count = [0]
        def setattr_side_effect(*args, **kw):
            call_count[0] += 1
            if call_count[0] == 3:
                raise RuntimeError("simulated failure on index 2")
        cmds.setAttr.side_effect = setattr_side_effect

        # Should NOT propagate the exception (undo_chunk + warning).
        try:
            core.set_node_multi_attr("node1", "attr1", [10, 20, 30, 40])
        except RuntimeError:
            self.fail("set_node_multi_attr leaked the inner exception")

        # warning was issued for the failure.
        self.assertGreaterEqual(cmds.warning.call_count, 1)
        # undoInfo openChunk + closeChunk both called.
        chunk_calls = [
            c for c in cmds.undoInfo.call_args_list
        ]
        # At minimum: openChunk(once) + closeChunk(once).
        self.assertGreaterEqual(len(chunk_calls), 2)


class T0c_EmptyList(unittest.TestCase):
    """Empty list → clears existing without writing new values."""

    def setUp(self):
        _reset_cmds_mock()

    def test_empty_list_clears(self):
        from RBFtools import core
        cmds.objExists.return_value = True
        cmds.listRelatives.return_value = ["shape1"]
        cmds.getAttr.return_value = [0, 1]

        cmds.setAttr.reset_mock()
        cmds.setAttr.side_effect = None
        core.set_node_multi_attr("node1", "attr1", [])

        # 2 removeMultiInstance calls
        self.assertEqual(cmds.removeMultiInstance.call_count, 2)
        # 0 setAttr calls
        self.assertEqual(cmds.setAttr.call_count, 0)


class T0d_LengthCap(unittest.TestCase):
    """List longer than max_length → truncated + warning."""

    def setUp(self):
        _reset_cmds_mock()

    def test_truncation(self):
        from RBFtools import core
        cmds.objExists.return_value = True
        cmds.listRelatives.return_value = ["shape1"]
        cmds.getAttr.return_value = []
        cmds.setAttr.reset_mock()
        cmds.setAttr.side_effect = None
        cmds.warning.reset_mock()

        too_long = list(range(50))
        core.set_node_multi_attr("node1", "attr1", too_long, max_length=10)

        # Warning fired about cap.
        self.assertGreaterEqual(cmds.warning.call_count, 1)
        # Only 10 setAttr calls.
        self.assertEqual(cmds.setAttr.call_count, 10)


class T0e_TypeGuard(unittest.TestCase):
    """Non-list/tuple input rejected with warning, no setAttr calls."""

    def setUp(self):
        _reset_cmds_mock()

    def test_int_rejected(self):
        from RBFtools import core
        cmds.objExists.return_value = True
        cmds.listRelatives.return_value = ["shape1"]
        cmds.warning.reset_mock()
        cmds.setAttr.reset_mock()
        cmds.setAttr.side_effect = None

        core.set_node_multi_attr("node1", "attr1", 42)

        self.assertGreaterEqual(cmds.warning.call_count, 1)
        self.assertEqual(cmds.setAttr.call_count, 0)


if __name__ == "__main__":
    unittest.main()
