# -*- coding: utf-8 -*-
"""M_BLOCKING_DEFAULT (2026-04-29) — RBFtools shape ships with
nodeState=2 (Blocking); first Apply flips it to 0 (Normal).

User report (2026-04-29 P0): brand-new RBF node + connecting
driver/driven attrs caused the driven joints to be IMMEDIATELY
mis-driven by garbage RBF compute() output (no poses registered
yet ⇒ untrained kernel ⇒ undefined output values written to the
driven channels).

Reference behaviour — AnimaRbfSolver: out-of-the-box nodeState=2
(Blocking) so compute() output is gated; user's first
"Apply" press flips it to nodeState=0 (Normal) so the rig goes
live only after pose data exists.

Fix:
  1. core.create_node sets shape.nodeState=2 immediately after
     createNode (paired with the existing type=1 default for RBF
     mode). cmds.warning surfaces the informational notice.
  2. core.apply_poses checks current nodeState and flips to 0
     when != 0. Idempotent on subsequent Applies.

PERMANENT GUARD T_BLOCKING_DEFAULT.
Mock E2E — 4 scenarios:
  * create_node sets nodeState=2.
  * apply_poses on a Blocking node flips to 0.
  * apply_poses on an already-Normal node is a no-op.
  * create_node setAttr-failure path warns but does not block
    node creation.
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
# PERMANENT GUARD T_BLOCKING_DEFAULT
# ----------------------------------------------------------------------


class T_BLOCKING_DEFAULT(unittest.TestCase):
    """PERMANENT GUARD — DO NOT REMOVE.

    create_node MUST set nodeState=2 (Blocking) on creation so an
    untrained RBF cannot mis-drive the rig. apply_poses MUST flip
    nodeState=0 (Normal) so the first Apply makes the node live."""

    @classmethod
    def setUpClass(cls):
        cls._core = _read(_CORE_PY)

    def test_PERMANENT_a_create_node_sets_blocking(self):
        body = self._core.split(
            "def create_node():")[1].split("\ndef ")[0]
        # Must explicitly set nodeState to 2 on the freshly-
        # created shape.
        self.assertIn(".nodeState\", 2", body,
            "create_node MUST setAttr shape.nodeState=2 "
            "(Blocking) so an untrained RBF cannot mis-drive "
            "the rig — M_BLOCKING_DEFAULT root cause.")

    def test_PERMANENT_b_apply_poses_flips_to_normal(self):
        body = self._core.split(
            "def apply_poses(node, driver_node")[1].split(
            "\ndef ")[0]
        self.assertIn(".nodeState\", 0", body,
            "apply_poses MUST setAttr shape.nodeState=0 (Normal) "
            "so the first Apply unblocks the node.")
        # And the read-before-write idempotency check.
        self.assertIn("getAttr(shape + \".nodeState\")", body,
            "apply_poses MUST read current nodeState before "
            "writing, so a second Apply on an already-Normal "
            "node is a no-op (no spurious warnings + no DG "
            "churn).")


# ----------------------------------------------------------------------
# Mock E2E — runtime behaviour
# ----------------------------------------------------------------------


@unittest.skipIf(conftest._REAL_MAYA,
    "mock-dependent (cmds stubs)")
class TestM_BLOCKING_DEFAULT_RuntimeBehavior(unittest.TestCase):

    def test_create_node_sets_nodeState_2(self):
        # Verify the create_node entry path issues setAttr with
        # nodeState=2 (Blocking) right after createNode.
        from RBFtools import core
        with mock.patch.object(core, "ensure_plugin"), \
             mock.patch.object(core, "get_transform",
                               return_value="RBFnode1"), \
             mock.patch.object(core, "get_shape",
                               return_value="RBFnode1Shape"), \
             mock.patch.object(core, "cmds") as mc:
            mc.ls.return_value = []
            mc.createNode.return_value = "RBFnode1Shape"
            mc.rename.return_value = "RBFnode1"
            core.create_node()
        # Collect every (plug, value) pair the function tried to
        # setAttr with a positional value.
        setattr_calls = [
            c.args for c in mc.setAttr.call_args_list
            if len(c.args) >= 2
        ]
        self.assertIn(("RBFnode1Shape.nodeState", 2),
                      setattr_calls,
            "Expected setAttr(shape.nodeState, 2) in the "
            "create_node call sequence — Blocking default lock.")

    def test_create_node_warns_but_does_not_block_on_setAttr_fail(
            self):
        from RBFtools import core
        with mock.patch.object(core, "ensure_plugin"), \
             mock.patch.object(core, "get_transform",
                               return_value="RBFnode1"), \
             mock.patch.object(core, "get_shape",
                               return_value="RBFnode1Shape"), \
             mock.patch.object(core, "cmds") as mc:
            mc.ls.return_value = []
            mc.createNode.return_value = "RBFnode1Shape"
            mc.rename.return_value = "RBFnode1"
            # Make setAttr on nodeState raise; the type=1 setAttr
            # earlier should still run, and the function MUST NOT
            # propagate the exception.
            def _setattr(plug, *args, **kwargs):
                if plug.endswith(".nodeState"):
                    raise RuntimeError("simulated lock")
                return None
            mc.setAttr.side_effect = _setattr
            transform = core.create_node()
        # Node creation still returns successfully.
        self.assertEqual(transform, "RBFnode1")
        # cmds.warning surfaced the failure (defensive UX).
        self.assertTrue(mc.warning.called)

    def test_apply_poses_flips_blocking_to_normal(self):
        from RBFtools import core
        # Stub every helper apply_poses calls so we can probe the
        # nodeState transition cleanly.
        with mock.patch.object(core, "_exists",
                               return_value=True), \
             mock.patch.object(core, "get_shape",
                               return_value="RBFnode1Shape"), \
             mock.patch.object(core, "_node_has_baseline_schema",
                               return_value=True), \
             mock.patch.object(core, "clear_node_data"), \
             mock.patch.object(core, "_write_pose_to_node"), \
             mock.patch.object(core, "write_pose_swing_twist_cache"), \
             mock.patch.object(core, "capture_output_baselines",
                               return_value=[]), \
             mock.patch.object(core, "write_output_baselines"), \
             mock.patch.object(
                 core, "capture_per_pose_local_transforms",
                 return_value=[]), \
             mock.patch.object(core, "write_pose_local_transforms"), \
             mock.patch.object(core, "auto_alias_outputs"), \
             mock.patch.object(core, "cmds") as mc:
            # Sim: shape currently in Blocking state.
            mc.getAttr.return_value = 2
            core.apply_poses(
                "RBFnode1", "drv", "dvn", ["tx"], ["tx"], [])
        # Assert exactly one setAttr targeted nodeState with 0.
        nodestate_writes = [
            c for c in mc.setAttr.call_args_list
            if c.args and c.args[0].endswith(".nodeState")
        ]
        self.assertEqual(len(nodestate_writes), 1)
        self.assertEqual(nodestate_writes[0].args[1], 0,
            "apply_poses must write nodeState=0 to unblock.")

    def test_apply_poses_idempotent_when_already_normal(self):
        # Subsequent Applies (nodeState already 0) must NOT write
        # nodeState again. Saves a redundant DG dirty + a noisy
        # warning.
        from RBFtools import core
        with mock.patch.object(core, "_exists",
                               return_value=True), \
             mock.patch.object(core, "get_shape",
                               return_value="RBFnode1Shape"), \
             mock.patch.object(core, "_node_has_baseline_schema",
                               return_value=True), \
             mock.patch.object(core, "clear_node_data"), \
             mock.patch.object(core, "_write_pose_to_node"), \
             mock.patch.object(core, "write_pose_swing_twist_cache"), \
             mock.patch.object(core, "capture_output_baselines",
                               return_value=[]), \
             mock.patch.object(core, "write_output_baselines"), \
             mock.patch.object(
                 core, "capture_per_pose_local_transforms",
                 return_value=[]), \
             mock.patch.object(core, "write_pose_local_transforms"), \
             mock.patch.object(core, "auto_alias_outputs"), \
             mock.patch.object(core, "cmds") as mc:
            mc.getAttr.return_value = 0   # already Normal
            core.apply_poses(
                "RBFnode1", "drv", "dvn", ["tx"], ["tx"], [])
        nodestate_writes = [
            c for c in mc.setAttr.call_args_list
            if c.args and c.args[0].endswith(".nodeState")
        ]
        self.assertEqual(len(nodestate_writes), 0,
            "apply_poses must NOT write nodeState when it is "
            "already 0 (idempotent regression check).")


if __name__ == "__main__":
    unittest.main()
