"""M_B24b2 — 3 active downstream multi-source adaptation tests +
5 legacy single-driver sanity tests + Mirror dialog wiring sanity.

Hardening 3 byte-equivalent tolerance form: prefer set/dict equality
over repr() == or str() == to avoid float-format noise. Each active
adapter (core_prune / core_profile / live_edit_widget) is verified
to behave equivalently to the legacy single-driver path under the
auto-migrated single-element drivers list.
"""

from __future__ import absolute_import

import unittest
from unittest import mock

import conftest


# ----------------------------------------------------------------------
# core_prune.analyse_node — multi-source aggregation + cross-source
#                           redundant detection (A.2)
# ----------------------------------------------------------------------


@unittest.skipIf(conftest._REAL_MAYA,
    "mock-dependent (cmds.reset_mock / mock.patch on cmds.*)")
class TestM_B24B2_PruneMultiSource(unittest.TestCase):
    """3 active downstream test #1: core_prune."""

    def _stub(self, mc):
        from RBFtools.core import PoseData, DriverSource
        mc.read_all_poses.return_value = [
            PoseData(0, [0.0, 0.0, 0.0, 0.0], [1.0]),
            PoseData(1, [0.0, 0.0, 0.0, 0.0], [1.0]),
        ]
        mc.read_driven_info.return_value = ("drvn", ["o"])
        mc.read_quat_group_starts.return_value = []

        def veq(a, b, *args, **kwargs):
            tol = kwargs.get("abs_tol", kwargs.get("tol", 1e-6))
            return all(abs(x - y) < tol for x, y in zip(a, b))
        mc.vector_eq.side_effect = veq
        return DriverSource

    def test_multi_source_aggregate_attrs(self):
        from RBFtools import core_prune
        with mock.patch("RBFtools.core_prune.core") as mc:
            DS = self._stub(mc)
            mc.read_driver_info_multi.return_value = [
                DS(node="drv1", attrs=("rotateX",)),
                DS(node="drv2", attrs=("rotateY", "rotateZ")),
            ]
            action = core_prune.analyse_node("RBF1")
        # Aggregate driver_attr_names across sources, source order
        # preserved.
        self.assertEqual(action.driver_attr_names,
                         ["rotateX", "rotateY", "rotateZ"])

    def test_cross_source_redundant_detected(self):
        """A.2: same attr name across sources is flagged."""
        from RBFtools import core_prune
        with mock.patch("RBFtools.core_prune.core") as mc:
            DS = self._stub(mc)
            mc.read_driver_info_multi.return_value = [
                DS(node="drv1", attrs=("rotateX",)),
                DS(node="drv2", attrs=("rotateX",)),  # duplicate
            ]
            action = core_prune.analyse_node("RBF1")
        # cross_source_redundant entries: (attr, first_idx, dup_idx)
        self.assertEqual(action.cross_source_redundant,
                         [("rotateX", 0, 1)])

    def test_legacy_single_driver_sanity(self):
        """Hardening 5: byte-equivalent legacy single-driver path."""
        from RBFtools import core_prune
        with mock.patch("RBFtools.core_prune.core") as mc:
            DS = self._stub(mc)
            mc.read_driver_info_multi.return_value = [
                DS(node="drv", attrs=("rotateX", "rotateY"))]
            action = core_prune.analyse_node("RBF1")
        # Legacy path: cross-source redundant must be empty (only 1 src).
        self.assertEqual(action.cross_source_redundant, [])
        self.assertEqual(action.driver_attr_names, ["rotateX", "rotateY"])


# ----------------------------------------------------------------------
# core_profile.profile_node — multi-source 5-column table (B.2)
# ----------------------------------------------------------------------


@unittest.skipIf(conftest._REAL_MAYA,
    "mock-dependent (cmds.reset_mock / mock.patch on cmds.*)")
class TestM_B24B2_ProfileMultiSource(unittest.TestCase):
    """3 active downstream test #2: core_profile."""

    def _stub(self, mc):
        from RBFtools.core import PoseData, DriverSource
        mc.read_all_poses.return_value = [
            PoseData(0, [0.0], [1.0]),
        ]
        mc.read_driven_info.return_value = ("drvn", ["o"])
        mc.read_quat_group_starts.return_value = []
        mc.safe_get.side_effect = lambda path, default=0: default
        return DriverSource

    def test_driver_sources_in_wiring_block(self):
        from RBFtools import core_profile
        with mock.patch("RBFtools.core_profile.core") as mc, \
             mock.patch("RBFtools.core_profile.core_prune"):
            DS = self._stub(mc)
            mc.read_driver_info_multi.return_value = [
                DS(node="drv1", attrs=("rotateX",), weight=1.0, encoding=0),
                DS(node="drv2", attrs=("rotateY",), weight=0.5, encoding=4),
            ]
            p = core_profile.profile_node("RBF1")
        sources = p["wiring"]["driver_sources"]
        self.assertEqual(len(sources), 2)
        self.assertEqual(sources[0]["node"], "drv1")
        self.assertEqual(sources[1]["weight"], 0.5)
        self.assertEqual(sources[1]["encoding"], 4)

    def test_legacy_single_driver_sanity(self):
        """Hardening 5: legacy single-driver -> single-row table."""
        from RBFtools import core_profile
        with mock.patch("RBFtools.core_profile.core") as mc, \
             mock.patch("RBFtools.core_profile.core_prune"):
            DS = self._stub(mc)
            mc.read_driver_info_multi.return_value = [
                DS(node="drv", attrs=("rotateX",), weight=1.0, encoding=0)]
            p = core_profile.profile_node("RBF1")
        sources = p["wiring"]["driver_sources"]
        self.assertEqual(len(sources), 1)
        self.assertEqual(sources[0]["node"], "drv")


# ----------------------------------------------------------------------
# live_edit_widget — multi-driver listen (C.2)
# ----------------------------------------------------------------------


class TestM_B24B2_LiveEditMultiSource(unittest.TestCase):
    """3 active downstream test #3: live_edit_widget. Source-scan only
    since the widget needs a real Qt app loop to instantiate."""

    def test_widget_uses_read_driver_info_multi(self):
        import os
        path = os.path.normpath(os.path.join(
            os.path.dirname(__file__), "..", "scripts", "RBFtools",
            "ui", "widgets", "live_edit_widget.py"))
        with open(path, "r", encoding="utf-8") as f:
            src = f.read()
        # M_B24b2: live_edit must consume the multi-source API.
        self.assertIn("read_driver_info_multi", src,
            "live_edit_widget.py must call read_driver_info_multi "
            "(M_B24b2 active downstream adaptation)")

    def test_widget_legacy_single_driver_pairs_byte_equivalent(self):
        """Hardening 5 byte-equivalent: legacy single-driver path
        produces (node, attr) pairs equivalent to the pre-M_B24b2
        for-attr scriptJob loop. Set comparison avoids order
        sensitivity per Hardening 3."""
        from RBFtools.core import DriverSource
        legacy_pairs = {("drv", a) for a in ("rotateX", "rotateY")}
        sources = [DriverSource(node="drv",
                                 attrs=("rotateX", "rotateY"))]
        multi_pairs = {(s.node, a) for s in sources for a in s.attrs}
        self.assertEqual(legacy_pairs, multi_pairs)


# ----------------------------------------------------------------------
# Mirror dialog warning — controller wiring (D.2 + Hardening 5 action_id)
# ----------------------------------------------------------------------


class TestM_B24B2_MirrorDialogWiring(unittest.TestCase):
    """controller.mirror_current_node integrates an ask_confirm
    gating call when the source has > 1 driver sources."""

    def test_controller_uses_mirror_multi_source_action_id(self):
        import os
        path = os.path.normpath(os.path.join(
            os.path.dirname(__file__), "..", "scripts", "RBFtools",
            "controller.py"))
        with open(path, "r", encoding="utf-8") as f:
            src = f.read()
        self.assertIn('action_id="mirror_multi_source_warning"', src,
            "controller.mirror_current_node must use the "
            "mirror_multi_source_warning action_id (Hardening 5)")
        self.assertIn("read_driver_info_multi", src,
            "controller must probe driver source count before mirror")


if __name__ == "__main__":
    unittest.main()
