# -*- coding: utf-8 -*-
"""M_P0_RBF_HIERARCHICAL_SUBATTR_REFACTOR (2026-05-28).

poseParentIndex / poseDriverMask were originally shipped as top-level
multis parallel to poses[]. That design broke the round-trip the user
reported: the writer set ``poseParentIndex[row]`` but ``read_all_poses``
never read it back, so the pose-grid Parent column always reverted to
-1 after Apply + reload. The refactor moves both into *children of the
poses[] compound* (``poses[p].poseParentIndex`` / ``poses[p].
poseDriverMask``) so they travel with the pose element through
add / remove / .ma round-trip.

This file guards the refactor end-to-end:

PoseData transport object (pure Python):
  1.  parent_index / driver_mask slots exist + default to base / all
  2.  keyword-only with backward-compatible defaults (legacy
      PoseData(idx, in, val[, radius]) callsites unbroken)
  3.  __repr__ / __eq__ include the new fields

Write + read round-trip (in-memory fake scene -> real core helpers):
  4.  _write_pose_to_node writes poses[i].poseParentIndex +
      poses[i].poseDriverMask (correct plug + value)
  5.  parent_index round-trips through safe_get on the child plug
  6.  driver_mask round-trips through _read_pose_driver_mask
  7.  empty mask + base parent round-trip (backward compat)

_read_pose_driver_mask shape tolerance:
  8.  flat / singly-nested / None / empty all normalize to list[int]

Source-introspection (cpp + core):
  9.  cpp reads the children via poseElem.child(poseParentIndex) and
      no longer does the top-level inputArrayValue(poseParentIndex)
  10. core.py write/read paths target the poses[].* child plug

Live mayapy round-trip (skipped unless real Maya is present):
  11. real RBFtools node: setAttr child -> read_all_poses fidelity
"""

from __future__ import absolute_import

import io
import os
import sys
import unittest

try:
    from unittest import mock
except ImportError:  # pragma: no cover - py2 fallback
    import mock

_TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
if _TESTS_DIR not in sys.path:
    sys.path.insert(0, _TESTS_DIR)

import conftest  # noqa: E402

from RBFtools import core  # noqa: E402


_REPO_ROOT = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..")
)
_RBF_CPP = os.path.join(_REPO_ROOT, "source", "RBFtools.cpp")
_CORE_PY = os.path.join(
    _REPO_ROOT, "modules", "RBFtools", "scripts", "RBFtools", "core.py")


def _read(path):
    with io.open(path, "r", encoding="utf-8") as fh:
        return fh.read()


class _FakeScene(object):
    """Minimal in-memory cmds stand-in: setAttr stores by plug string,
    getAttr returns the stored value (raising for unknown plugs so the
    real safe_get fallback path is exercised)."""

    def __init__(self):
        self.store = {}

    def setAttr(self, plug, *args, **kwargs):
        if kwargs.get("type") == "Int32Array":
            n = int(args[0]) if args else 0
            self.store[plug] = [int(x) for x in args[1:1 + n]]
        elif args:
            self.store[plug] = args[0]

    def getAttr(self, plug, *args, **kwargs):
        if plug not in self.store:
            raise ValueError("no such plug: {}".format(plug))
        return self.store[plug]

    def warning(self, *a, **k):
        pass


# ----------------------------------------------------------------------
# 1-3. PoseData transport object
# ----------------------------------------------------------------------


class TestPoseDataHierarchyFields(unittest.TestCase):

    def test_01_slots_and_defaults(self):
        p = core.PoseData(0, [0.1, 0.2], [0.3])
        self.assertEqual(p.parent_index, -1,
            "default parent_index MUST be -1 (base pose)")
        self.assertEqual(p.driver_mask, [],
            "default driver_mask MUST be [] (all drivers)")
        # __slots__ enforced — no stray attribute creation.
        self.assertIn("parent_index", core.PoseData.__slots__)
        self.assertIn("driver_mask", core.PoseData.__slots__)

    def test_02_legacy_callsites_unbroken(self):
        """Every historical signature still builds a plain base pose."""
        a = core.PoseData(0, [0.0], [1.0])
        b = core.PoseData(1, [0.0], [1.0], radius=7.0)
        c = core.PoseData(index=2, inputs=[0.0], values=[1.0],
                          radius=5.0)
        for p in (a, b, c):
            self.assertEqual(p.parent_index, -1)
            self.assertEqual(p.driver_mask, [])

    def test_03_explicit_fields_preserved(self):
        p = core.PoseData(3, [0.0, 1.0], [2.0], radius=5.0,
                         parent_index=1, driver_mask=[0, 2])
        self.assertEqual(p.parent_index, 1)
        self.assertEqual(p.driver_mask, [0, 2])
        # repr surfaces them
        r = repr(p)
        self.assertIn("parent_index=1", r)
        self.assertIn("driver_mask=[0, 2]", r)
        # eq distinguishes on the hierarchy fields
        same = core.PoseData(3, [0.0, 1.0], [2.0], radius=5.0,
                            parent_index=1, driver_mask=[0, 2])
        diff_parent = core.PoseData(3, [0.0, 1.0], [2.0], radius=5.0,
                                   parent_index=0, driver_mask=[0, 2])
        diff_mask = core.PoseData(3, [0.0, 1.0], [2.0], radius=5.0,
                                 parent_index=1, driver_mask=[0])
        self.assertEqual(p, same)
        self.assertNotEqual(p, diff_parent)
        self.assertNotEqual(p, diff_mask)

    def test_03b_two_legacy_poses_still_equal(self):
        """Backward-compat: two poses built the old way both default
        to (-1, []) so equality is unaffected."""
        self.assertEqual(
            core.PoseData(0, [0.0], [1.0]),
            core.PoseData(0, [0.0], [1.0]))


# ----------------------------------------------------------------------
# 4-7. Write + read round-trip through the real core helpers
# ----------------------------------------------------------------------


class TestWriteReadRoundTrip(unittest.TestCase):

    def test_04_write_targets_child_plugs(self):
        fake = mock.MagicMock()
        with mock.patch.object(core, "cmds", fake):
            pose = core.PoseData(0, [0.1, 0.2], [0.3, 0.4],
                                parent_index=1, driver_mask=[0, 2])
            core._write_pose_to_node("RBFShape", 0, pose)
        calls = [c.args for c in fake.setAttr.call_args_list]
        plugs = [c[0] for c in calls if c]
        self.assertIn("RBFShape.poses[0].poseParentIndex", plugs,
            "write MUST target the poses[] child plug, not a "
            "top-level poseParentIndex[row] multi")
        # parent value written
        parent_call = [c for c in calls
                       if c and c[0] == "RBFShape.poses[0].poseParentIndex"]
        self.assertEqual(parent_call[0][1], 1)
        # mask written as Int32Array to the child plug
        mask_calls = [c for c in fake.setAttr.call_args_list
                      if c.args and
                      c.args[0] == "RBFShape.poses[0].poseDriverMask"]
        self.assertTrue(mask_calls, "mask MUST target poses[] child plug")
        self.assertEqual(mask_calls[0].kwargs.get("type"), "Int32Array")

    def test_05_06_round_trip_fidelity(self):
        """The brief's headline guard: PoseData(parent_index=1,
        driver_mask=[0,2]) -> write -> read -> fields preserved."""
        fake = _FakeScene()
        with mock.patch.object(core, "cmds", fake):
            pose = core.PoseData(0, [0.1, 0.2], [0.3, 0.4],
                                parent_index=1, driver_mask=[0, 2])
            core._write_pose_to_node("RBFShape", 0, pose)
            parent = int(core.safe_get(
                "RBFShape.poses[0].poseParentIndex", -1))
            mask = core._read_pose_driver_mask("RBFShape", 0)
        self.assertEqual(parent, 1,
            "parent_index MUST survive write -> read (the round-trip "
            "the user reported broken)")
        self.assertEqual(mask, [0, 2],
            "driver_mask MUST survive write -> read")

    def test_07_empty_mask_base_parent_round_trip(self):
        fake = _FakeScene()
        with mock.patch.object(core, "cmds", fake):
            pose = core.PoseData(0, [0.0], [1.0])  # base / all drivers
            core._write_pose_to_node("RBFShape", 0, pose)
            parent = int(core.safe_get(
                "RBFShape.poses[0].poseParentIndex", -1))
            mask = core._read_pose_driver_mask("RBFShape", 0)
        self.assertEqual(parent, -1)
        self.assertEqual(mask, [])


# ----------------------------------------------------------------------
# 8. _read_pose_driver_mask shape tolerance
# ----------------------------------------------------------------------


class TestReadDriverMaskShapes(unittest.TestCase):

    def _read_with(self, return_value):
        fake = mock.MagicMock()
        fake.getAttr.return_value = return_value
        with mock.patch.object(core, "cmds", fake):
            return core._read_pose_driver_mask("S", 0)

    def test_08_flat(self):
        self.assertEqual(self._read_with([0, 2]), [0, 2])

    def test_08_nested(self):
        self.assertEqual(self._read_with([[0, 2]]), [0, 2])

    def test_08_none(self):
        self.assertEqual(self._read_with(None), [])

    def test_08_empty(self):
        self.assertEqual(self._read_with([]), [])

    def test_08_raises(self):
        fake = mock.MagicMock()
        fake.getAttr.side_effect = RuntimeError("no plug")
        with mock.patch.object(core, "cmds", fake):
            self.assertEqual(core._read_pose_driver_mask("S", 0), [])


# ----------------------------------------------------------------------
# 9-10. Source-introspection
# ----------------------------------------------------------------------


class TestSourceGuards(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._cpp = _read(_RBF_CPP)
        cls._core = _read(_CORE_PY)

    def test_09_cpp_reads_poses_children(self):
        self.assertIn("poseParentIndex).asInt()", self._cpp,
            "compute() MUST read the parent index off the poses[] "
            "element child")
        self.assertIn("child(poseDriverMask).data()", self._cpp,
            "compute() MUST read the driver mask off the poses[] "
            "element child")

    def test_09b_cpp_no_toplevel_multi_read(self):
        self.assertNotIn(
            "data.inputArrayValue(poseParentIndex", self._cpp,
            "Top-level inputArrayValue(poseParentIndex) read MUST be "
            "gone -- the child read replaces it")
        self.assertNotIn(
            "data.inputArrayValue(poseDriverMask", self._cpp,
            "Top-level inputArrayValue(poseDriverMask) read MUST be "
            "gone -- the child read replaces it")

    def test_09c_cpp_addchild(self):
        self.assertIn("cAttr.addChild(poseParentIndex);", self._cpp)
        self.assertIn("cAttr.addChild(poseDriverMask);", self._cpp)

    def test_10_core_write_read_child_plug(self):
        self.assertIn(
            '"{}.poses[{}].poseParentIndex".format(shape, sequential_idx)',
            self._core,
            "_write_pose_to_node MUST write the poses[] child plug")
        self.assertIn(
            '"{}.poses[{}].poseParentIndex".format(shape, pid)',
            self._core,
            "read_all_poses MUST read the poses[] child plug")
        self.assertIn("parent_index", core.PoseData.__slots__)
        self.assertIn("driver_mask", core.PoseData.__slots__)


# ----------------------------------------------------------------------
# 11. Live mayapy round-trip (only under real Maya)
# ----------------------------------------------------------------------


@unittest.skipUnless(getattr(conftest, "_REAL_MAYA", False),
                     "live round-trip requires real mayapy + RBFtools "
                     "plugin")
class TestLiveRoundTrip(unittest.TestCase):

    def test_11_live_child_plug_round_trip(self):  # pragma: no cover
        import maya.cmds as mc
        if not mc.pluginInfo("RBFtools", q=True, loaded=True):
            try:
                mc.loadPlugin("RBFtools")
            except Exception as exc:
                self.skipTest("RBFtools plugin not loadable: "
                              "{}".format(exc))
        node = mc.createNode("RBFtools")
        mc.setAttr(node + ".type", 1)
        # Seed a single pose with a parent + mask via the child plugs.
        mc.setAttr(node + ".poses[0].poseInput[0]", 0.5)
        mc.setAttr(node + ".poses[0].poseValue[0]", 1.0)
        mc.setAttr(node + ".poses[0].poseParentIndex", 1)
        mc.setAttr(node + ".poses[0].poseDriverMask", 2, 0, 2,
                   type="Int32Array")
        self.assertEqual(
            mc.getAttr(node + ".poses[0].poseParentIndex"), 1)
        self.assertEqual(
            list(mc.getAttr(node + ".poses[0].poseDriverMask") or []),
            [0, 2])


if __name__ == "__main__":
    unittest.main()
