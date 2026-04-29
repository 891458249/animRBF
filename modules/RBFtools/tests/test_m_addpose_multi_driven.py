# -*- coding: utf-8 -*-
"""M_ADDPOSE_MULTI_DRIVEN (2026-04-29) — Pose snapshot walks the
multi-source list instead of the legacy single-source tuple.

User report (2026-04-29 P0): a pose row added with 3 driven sources
(joint1 / joint2 / joint3) of 9 attrs each showed THREE IDENTICAL
groups of 9 numbers across the 27-column row. The driven values
were physically different in the scene (each joint at a different
position) but PoseData.values came out as ``[*joint1_vals,
*joint1_vals, *joint1_vals]``.

Root cause: ``controller.add_pose`` line 1308-1309 read
``core.read_current_values(driven_node, driven_attrs)`` where
``driven_node`` was the FIRST source's name (from
``main_window._gather_role_info`` flat-concat tuple) and
``driven_attrs`` was the 27-attr concat. ``cmds.getAttr`` happily
returned joint1's 9 values 3 times — the joint name was joint1,
the attrs all existed on joint1, and joint2/joint3 were never
queried. Same shape on the driver side.

Fix:
  * ``_capture_multi_inputs(fallback_node, fallback_attrs)`` walks
    ``read_driver_sources()`` and stitches per-source values into
    a contiguous ``inputs`` vector.
  * ``_capture_multi_outputs(fallback_node, fallback_attrs)``
    driven mirror.
  * ``add_pose`` / ``update_pose`` use the helpers; legacy single-
    source path falls back when no multi list is wired.
  * ``recall_pose`` splays PoseData back to (source.node, attr)
    pairs in the same order — same triple-write bug solved.
  * ``recall_base_pose`` mirrors.

PERMANENT GUARDS — T_ADDPOSE_MULTI_DRIVEN_AWARE.
"""

from __future__ import absolute_import

import os
import unittest
from unittest import mock

import conftest


_REPO_ROOT = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..")
)
_CTRL_PY = os.path.join(
    _REPO_ROOT, "modules", "RBFtools", "scripts", "RBFtools",
    "controller.py")


def _read(p):
    with open(p, "r", encoding="utf-8") as fh:
        return fh.read()


# ----------------------------------------------------------------------
# PERMANENT GUARD T_ADDPOSE_MULTI_DRIVEN_AWARE
# ----------------------------------------------------------------------


class T_ADDPOSE_MULTI_DRIVEN_AWARE(unittest.TestCase):
    """PERMANENT GUARD — Bug fix locks. DO NOT REMOVE.

    add_pose / update_pose MUST capture per-source values across
    every driver/driven source. The legacy single-source
    ``read_current_values(driven_node, driven_attrs)`` flow on a
    multi-source node returned the FIRST source's values
    duplicated — the user's exact triple-9-column repro."""

    @classmethod
    def setUpClass(cls):
        cls._ctrl = _read(_CTRL_PY)

    def test_PERMANENT_a_helpers_present(self):
        for sym in ("def _capture_multi_inputs",
                    "def _capture_multi_outputs"):
            self.assertIn(sym, self._ctrl,
                "controller missing {}".format(sym))

    def test_PERMANENT_b_add_pose_uses_multi_helpers(self):
        body = self._ctrl.split(
            "def add_pose(self, driver_node, driven_node,"
        )[1].split("\n    def ")[0]
        self.assertIn("self._capture_multi_inputs(", body)
        self.assertIn("self._capture_multi_outputs(", body)

    def test_PERMANENT_c_update_pose_uses_multi_helpers(self):
        body = self._ctrl.split(
            "def update_pose(self, row, driver_node, driven_node,"
        )[1].split("\n    def ")[0]
        self.assertIn("self._capture_multi_inputs(", body)
        self.assertIn("self._capture_multi_outputs(", body)

    def test_PERMANENT_d_helpers_walk_source_lists(self):
        body = self._ctrl.split(
            "def _capture_multi_outputs(self,"
        )[1].split("\n    def ")[0]
        self.assertIn("self.read_driven_sources()", body,
            "_capture_multi_outputs MUST walk "
            "read_driven_sources() to retrieve per-source attrs.")
        body_in = self._ctrl.split(
            "def _capture_multi_inputs(self,"
        )[1].split("\n    def ")[0]
        self.assertIn("self.read_driver_sources()", body_in)


# ----------------------------------------------------------------------
# Mock E2E — multi-source snapshot correctness
# ----------------------------------------------------------------------


@unittest.skipIf(conftest._REAL_MAYA,
    "mock-dependent (cmds + core stubs)")
class TestM_ADDPOSE_MULTI_DRIVEN_RuntimeBehavior(unittest.TestCase):

    def _make_ctrl(self, drv_sources=None, dvn_sources=None,
                   read_values_map=None):
        from RBFtools.controller import MainController
        ctrl = MainController.__new__(MainController)
        ctrl._current_node = "RBF1"
        ctrl._auto_fill = False
        # Multi source mocks.
        ctrl.read_driver_sources = mock.MagicMock(
            return_value=drv_sources or [])
        ctrl.read_driven_sources = mock.MagicMock(
            return_value=dvn_sources or [])
        # Pose model stub — accepts add_pose / setup_columns.
        ctrl._pose_model = mock.MagicMock()
        ctrl._pose_model.n_inputs = 0
        ctrl._pose_model.n_outputs = 0
        ctrl._pose_model.rowCount.return_value = 0
        ctrl._pose_model.next_pose_index.return_value = 0
        return ctrl

    def test_capture_multi_outputs_walks_per_source(self):
        # 3 driven sources at different scene positions; the
        # ``read_current_values`` mock returns DIFFERENT values
        # per node so we can verify the helper actually queries
        # each source separately.
        from RBFtools import core
        from RBFtools.controller import MainController
        from RBFtools.core import DrivenSource
        ctrl = self._make_ctrl(dvn_sources=[
            DrivenSource(node="joint1", attrs=("tx", "ty", "tz")),
            DrivenSource(node="joint2", attrs=("tx", "ty", "tz")),
            DrivenSource(node="joint3", attrs=("tx", "ty", "tz")),
        ])
        per_node_values = {
            "joint1": [1.1, 1.2, 1.3],
            "joint2": [2.1, 2.2, 2.3],
            "joint3": [3.1, 3.2, 3.3],
        }
        with mock.patch.object(
                core, "read_current_values",
                side_effect=lambda n, a: list(
                    per_node_values.get(n, []))):
            out = MainController._capture_multi_outputs(
                ctrl, "joint1", ["tx", "ty", "tz"])
        # Bug-fix regression check: 9 distinct values — NOT 3
        # identical groups of [1.1, 1.2, 1.3].
        self.assertEqual(out, [1.1, 1.2, 1.3,
                                2.1, 2.2, 2.3,
                                3.1, 3.2, 3.3])

    def test_capture_multi_inputs_walks_per_source(self):
        from RBFtools import core
        from RBFtools.controller import MainController
        from RBFtools.core import DriverSource
        ctrl = self._make_ctrl(drv_sources=[
            DriverSource(node="ctrlA", attrs=("rx",),
                         weight=1.0, encoding=0),
            DriverSource(node="ctrlB", attrs=("ry", "rz"),
                         weight=1.0, encoding=0),
        ])
        per_node_values = {
            "ctrlA": [10.0],
            "ctrlB": [20.0, 30.0],
        }
        with mock.patch.object(
                core, "read_current_values",
                side_effect=lambda n, a: list(
                    per_node_values.get(n, []))):
            out = MainController._capture_multi_inputs(
                ctrl, "ctrlA", ["rx"])
        self.assertEqual(out, [10.0, 20.0, 30.0])

    def test_capture_falls_back_when_no_sources(self):
        # No multi sources wired -> legacy single-source read.
        from RBFtools import core
        from RBFtools.controller import MainController
        ctrl = self._make_ctrl(drv_sources=[], dvn_sources=[])
        with mock.patch.object(
                core, "read_current_values",
                return_value=[7.7, 8.8]) as rcv:
            out = MainController._capture_multi_outputs(
                ctrl, "fallbackBone", ["tx", "ty"])
        self.assertEqual(out, [7.7, 8.8])
        rcv.assert_called_once_with("fallbackBone", ["tx", "ty"])

    def test_add_pose_E2E_multi_driven_no_duplicates(self):
        # Full add_pose flow: 3 driven sources × 3 attrs each ->
        # PoseData.values is a 9-element vector with the per-
        # source values stitched in source order. Three identical
        # groups would mean the bug regressed.
        from RBFtools import core
        from RBFtools.controller import MainController
        from RBFtools.core import DriverSource, DrivenSource
        ctrl = self._make_ctrl(
            drv_sources=[
                DriverSource(node="ctrl", attrs=("rx",),
                             weight=1.0, encoding=0)],
            dvn_sources=[
                DrivenSource(node="j1", attrs=("tx", "ty", "tz")),
                DrivenSource(node="j2", attrs=("tx", "ty", "tz")),
                DrivenSource(node="j3", attrs=("tx", "ty", "tz")),
            ])
        per_node_values = {
            "ctrl": [45.0],
            "j1":   [1.0, 2.0, 3.0],
            "j2":   [4.0, 5.0, 6.0],
            "j3":   [7.0, 8.0, 9.0],
        }
        with mock.patch.object(
                core, "read_current_values",
                side_effect=lambda n, a: list(
                    per_node_values.get(n, []))), \
             mock.patch.object(core, "is_blendshape",
                               return_value=False):
            pose = MainController.add_pose(
                ctrl, "ctrl", "j1", ["rx"],
                ["tx", "ty", "tz",
                 "tx", "ty", "tz",
                 "tx", "ty", "tz"])
        self.assertIsNotNone(pose)
        self.assertEqual(pose.inputs, [45.0])
        # The user's exact failure mode: 3 identical groups of
        # [1.0, 2.0, 3.0] would mean the bug regressed.
        self.assertEqual(
            pose.values,
            [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0])
        # Sanity: NOT triple-duplicated.
        self.assertNotEqual(pose.values[:3], pose.values[3:6])
        self.assertNotEqual(pose.values[3:6], pose.values[6:9])

    def test_update_pose_E2E_multi_driven_no_duplicates(self):
        from RBFtools import core
        from RBFtools.controller import MainController
        from RBFtools.core import DriverSource, DrivenSource
        ctrl = self._make_ctrl(
            drv_sources=[
                DriverSource(node="ctrl", attrs=("tx",),
                             weight=1.0, encoding=0)],
            dvn_sources=[
                DrivenSource(node="j1", attrs=("tx",)),
                DrivenSource(node="j2", attrs=("tx",)),
            ])
        per_node_values = {
            "ctrl": [99.0],
            "j1":   [11.0],
            "j2":   [22.0],
        }
        with mock.patch.object(
                core, "read_current_values",
                side_effect=lambda n, a: list(
                    per_node_values.get(n, []))):
            MainController.update_pose(
                ctrl, 0, "ctrl", "j1", ["tx"], ["tx", "tx"])
        ctrl._pose_model.update_pose_values.assert_called_once_with(
            0, [99.0], [11.0, 22.0])


if __name__ == "__main__":
    unittest.main()
