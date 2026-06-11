# -*- coding: utf-8 -*-
"""M_P0_DRIVER_CONNECT_UX_REVAMP (2026-05-12) -- Phase 13 driver
connect UX revamp test surface.

Covers all four user directives (brief sec.0):
  1. Per-tab connection status indicator (red/yellow/green dot)
  2. Single-tab "Connect" only affects current tab; switching
     tabs does not overwrite previous wires (atomic Step 2+4 +
     rollback in set_driver_source_attrs)
  3. Multi-tab cumulative "Connect" is idempotent -- per-tab
     indicator-guided dispatch skips already-green tabs
  4. "Apply" button preserves multi-driver wiring -- Apply must
     not collapse green dots to just the last active tab
     (apply_poses_routed + _clear_poses_only)

Fourteen + extras test cases (brief sec.2 Part D.1):
  PERMANENT GUARDS (source introspection):
    1.  Part A: metadata write moved after Step 2 + Step 4
    2.  Part A: pre_wires snapshot for rollback restore
    3.  Part A: rollback connectAttr + restore loop present
    4.  Part A: driver_source_connection_state helper present
    5.  Part A: controller.driver_source_connection_state method
    6.  Part B: status icon factory + refresh_tab_indicators
    7.  Part C: count-change dialog in apply slot
    8.  Part E.1: _on_driver_source_attrs_apply idempotent skip
    9.  Part E.2: _on_connect batch filter
    10. Part E.3: _on_connect_clicked attr dedupe
    11. Part F.1: core.apply_poses_routed signature + _clear_
        poses_only Step 1 call
    12. Part F.2: _clear_poses_only skips "input" and "output"
    13. Part F.3: controller.apply_poses_routed method present
    14. Part F.4: main_window._on_apply dispatch by topology
  RUNTIME BEHAVIOUR (mocked cmds):
    R1-R4. driver_source_connection_state -> "connected"/"partial"/
           "disconnected" returns + index OOR
  ATTR DEDUPE PURE LOGIC:
    D1-D3. order preserved for [X,Y,X,Z], no-dupes no-op,
           all-dupes collapse
"""

from __future__ import absolute_import

import io
import os
import sys
import unittest
from unittest import mock

# Allow `import conftest` regardless of cwd at pytest invocation
# (root-level sweep cwd is the repo root, not modules/RBFtools/tests).
_TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
if _TESTS_DIR not in sys.path:
    sys.path.insert(0, _TESTS_DIR)

import conftest  # noqa: E402


_REPO_ROOT = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..")
)
_CORE_PY = os.path.join(
    _REPO_ROOT, "modules", "RBFtools", "scripts", "RBFtools",
    "core.py")
_CTRL_PY = os.path.join(
    _REPO_ROOT, "modules", "RBFtools", "scripts", "RBFtools",
    "controller.py")
_MAIN_PY = os.path.join(
    _REPO_ROOT, "modules", "RBFtools", "scripts", "RBFtools",
    "ui", "main_window.py")
_TSE_PY = os.path.join(
    _REPO_ROOT, "modules", "RBFtools", "scripts", "RBFtools",
    "ui", "widgets", "tabbed_source_editor.py")


def _read(path):
    with io.open(path, "r", encoding="utf-8") as fh:
        return fh.read()


def _slice_def(src, header):
    """Return source text from *header* to next top-level ``def`` or
    ``class``. Used to scope assertions to one function body."""
    idx = src.find(header)
    assert idx >= 0, "header {!r} not found".format(header)
    rest = src[idx + len(header):]
    next_def = rest.find("\ndef ")
    next_cls = rest.find("\nclass ")
    end = min(p for p in (next_def, next_cls, len(rest)) if p >= 0)
    return src[idx:idx + len(header) + end]


# ----------------------------------------------------------------------
# PERMANENT GUARDS -- source introspection
# ----------------------------------------------------------------------


class T_M_P0_DRIVER_CONNECT_UX_REVAMP_Source(unittest.TestCase):
    """PERMANENT GUARDS -- DO NOT REMOVE.

    Each test pins one of the Phase 13 invariants by reading the
    relevant source file and asserting the canonical patch markers
    are present. Regression mode: if anyone removes / inadvertently
    re-orders the atomic step layout (Part A) or drops the
    idempotent skip (Part E), these tests fail loudly with a
    pointer to the brief.
    """

    @classmethod
    def setUpClass(cls):
        cls._core = _read(_CORE_PY)
        cls._ctrl = _read(_CTRL_PY)
        cls._main = _read(_MAIN_PY)
        cls._tse = _read(_TSE_PY)

    # --- Part A ---------------------------------------------------------

    def test_PERMANENT_1_metadata_write_after_step_2_and_4(self):
        """Part A: driverSource_attrs metadata write MUST sit after
        Step 2 (re-wire source[index]) AND Step 4 (re-wire source
        [i>index]) so silent connectAttr failures cannot poison
        the metadata."""
        body = _slice_def(self._core, "def set_driver_source_attrs(")
        # Step 2 marker.
        step2_idx = body.find("# 2) Re-wire source[index]")
        # Step 4 marker.
        step4_idx = body.find(
            "# 4) Re-wire source[i>index]")
        # Step 3 marker (after rename).
        step3_idx = body.find(
            "# 3) Metadata write -- ONLY now that every wire landed.")
        self.assertGreater(step2_idx, 0,
            "Step 2 re-wire comment missing in set_driver_source_attrs")
        self.assertGreater(step4_idx, 0,
            "Step 4 re-wire comment missing in set_driver_source_attrs")
        self.assertGreater(step3_idx, 0,
            "Step 3 metadata comment missing (Part A moves it AFTER 2+4)")
        # Order constraint: 2 < 4 < 3.
        self.assertLess(step2_idx, step4_idx,
            "Step 2 must precede Step 4")
        self.assertLess(step4_idx, step3_idx,
            "Step 3 metadata MUST come AFTER Step 4 -- Part A invariant")

    def test_PERMANENT_2_pre_wires_snapshot_present(self):
        """Part A: pre_wires snapshot recorded BEFORE Step 1
        disconnect so rollback can put every wire back at its
        original input[] subscript."""
        body = _slice_def(self._core, "def set_driver_source_attrs(")
        self.assertIn("pre_wires = []", body,
            "pre_wires snapshot MUST be initialised before Step 1")
        self.assertIn("pre_wires.append((s.node, attr, sub_idx))", body,
            "pre_wires MUST capture (source_node, attr, subscript) "
            "tuples")

    def test_PERMANENT_3_rollback_phase_present(self):
        """Part A: rollback block MUST disconnect everything we
        connected then restore originals via the pre_wires
        snapshot."""
        body = _slice_def(self._core, "def set_driver_source_attrs(")
        # Phase R1 -- disconnect newly-created wires.
        self.assertIn("connected_step2 + connected_step4", body,
            "Rollback MUST iterate connected_step2 + connected_step4 "
            "and disconnect each")
        # Phase R2 -- restore originals.
        self.assertIn("for orig_node, orig_attr, orig_sub in pre_wires",
            body,
            "Rollback MUST walk pre_wires and re-issue connectAttr "
            "for each original wire")
        self.assertIn("aborted + rolled back", body,
            "Rollback MUST emit a `cmds.warning` describing the "
            "abort + rollback so the TD sees the honest failure")

    def test_PERMANENT_4_connection_state_helper_present(self):
        """Part A.2: driver_source_connection_state helper MUST
        be a public top-level function returning one of three
        canonical strings."""
        self.assertIn("def driver_source_connection_state(node, index):",
            self._core,
            "core MUST expose driver_source_connection_state(node, "
            "index)")
        body = _slice_def(
            self._core, "def driver_source_connection_state(")
        for s in ('"connected"', '"partial"', '"disconnected"'):
            self.assertIn(s, body,
                "driver_source_connection_state MUST be able to "
                "return {}".format(s))

    def test_PERMANENT_5_controller_method_present(self):
        """Part A.3: controller.driver_source_connection_state
        method MUST forward to core, translating list_idx -> sparse
        multi_idx."""
        self.assertIn(
            "def driver_source_connection_state(self, index):",
            self._ctrl,
            "controller MUST expose driver_source_connection_state")
        body = _slice_def(self._ctrl,
            "def driver_source_connection_state(self, index):")
        self.assertIn("_list_idx_to_sparse(\"driver\"", body,
            "controller method MUST translate dense list_idx -> "
            "sparse multi_idx via _list_idx_to_sparse")
        self.assertIn("core.driver_source_connection_state(", body,
            "controller method MUST forward to the core helper")

    # --- Part B ---------------------------------------------------------

    def test_PERMANENT_6_status_icon_factory_and_refresh_present(self):
        """Part B: _make_status_icon + refresh_tab_indicators
        MUST live in tabbed_source_editor.py, and the driver
        subclass MUST override _query_state."""
        self.assertIn("def _make_status_icon(state):", self._tse,
            "tabbed_source_editor MUST expose _make_status_icon")
        self.assertIn("def refresh_tab_indicators(self, controller):",
            self._tse,
            "panel MUST expose refresh_tab_indicators")
        # Driver subclass override.
        body = _slice_def(self._tse,
            "class TabbedDriverSourceEditor(_TabbedSourceEditorBase):")
        self.assertIn("def _query_state(self, controller, index):",
            body,
            "TabbedDriverSourceEditor MUST override _query_state to "
            "call controller.driver_source_connection_state")
        self.assertIn(
            "controller.driver_source_connection_state(index)", body,
            "_query_state override MUST forward to controller")

    # --- Part C ---------------------------------------------------------

    def test_PERMANENT_7_count_change_dialog_in_apply(self):
        """Part C: _on_driver_source_attrs_apply MUST surface a
        confirmation dialog when the attr count changes and there
        are subsequent sources."""
        body = _slice_def(self._main,
            "def _on_driver_source_attrs_apply(self, index, attrs):")
        self.assertIn("title_attr_count_change", body,
            "Part C: apply slot MUST reference the count-change "
            "dialog title key")
        self.assertIn("msg_attr_count_change_will_rewire", body,
            "Part C: apply slot MUST reference the count-change "
            "dialog message key")
        self.assertIn("QMessageBox.question", body,
            "Part C: apply slot MUST surface a QMessageBox "
            "confirmation dialog")

    # --- Part E ---------------------------------------------------------

    def test_PERMANENT_8_idempotent_skip_in_apply(self):
        """Part E.1: _on_driver_source_attrs_apply MUST short-
        circuit when state==connected AND attrs unchanged."""
        body = _slice_def(self._main,
            "def _on_driver_source_attrs_apply(self, index, attrs):")
        self.assertIn(
            "driver_source_connection_state(int(index))", body,
            "Part E.1: apply slot MUST query connection_state to "
            "detect green tabs")
        self.assertIn('state == "connected" and existing_attrs == '
                       'new_attrs', body,
            "Part E.1: apply slot MUST short-circuit on "
            'state=="connected" AND attrs unchanged')
        self.assertIn("driver_idempotent_skip", body,
            "Part E.1: apply slot MUST emit the idempotent-skip "
            "i18n key")

    def test_PERMANENT_9_batch_filter_in_on_connect(self):
        """Part E.2: _on_connect MUST filter driver_targets by
        per-tab indicator state and surface an all-already-
        connected dialog when every tab was filtered out."""
        body = _slice_def(self._main, "def _on_connect(self):")
        self.assertIn("filtered_drivers = []", body,
            "Part E.2: _on_connect MUST initialise filtered_drivers")
        self.assertIn("driver_source_connection_state(i)", body,
            "Part E.2: _on_connect MUST query per-tab "
            "connection_state during filtering")
        self.assertIn("connect_all_already_connected", body,
            "Part E.2: _on_connect MUST surface the "
            "all-already-connected dialog when filtered_drivers "
            "is empty")
        self.assertIn("connect_routed(\n                filtered_drivers",
            body.replace("\r\n", "\n"),
            "Part E.2: _on_connect MUST pass filtered_drivers (not "
            "raw driver_targets) to connect_routed")

    def test_PERMANENT_10_attr_dedupe_in_clicked(self):
        """Part E.3: _on_connect_clicked MUST dedupe selected
        attrs preserving order before emitting."""
        body = _slice_def(self._tse, "def _on_connect_clicked(self):")
        self.assertIn("seen = set()", body,
            "Part E.3: _on_connect_clicked MUST initialise a seen "
            "set for dedupe")
        # The dedupe loop MUST iterate the raw selection.
        self.assertIn("for a in attrs_raw:", body,
            "Part E.3: _on_connect_clicked MUST iterate the raw "
            "selection")
        self.assertIn("if a not in seen:", body,
            "Part E.3: _on_connect_clicked MUST skip duplicates")

    # --- Part F ---------------------------------------------------------

    def test_PERMANENT_11_apply_poses_routed_signature(self):
        """Part F.1: core.apply_poses_routed MUST exist with the
        (node, driver_targets, driven_targets, poses) signature AND
        call _clear_poses_only (NOT clear_node_data) for Step 1.
        This is the user-reported invariant for directive #4 --
        Apply MUST preserve multi-driver input[]/output[] wiring."""
        self.assertIn(
            "def apply_poses_routed(node, driver_targets, "
            "driven_targets, poses):",
            self._core,
            "core MUST expose apply_poses_routed with the documented "
            "multi-driver signature (Part F.1)")
        body = _slice_def(
            self._core,
            "def apply_poses_routed(node, driver_targets, "
            "driven_targets, poses):")
        # Step 1 MUST be _clear_poses_only -- NOT clear_node_data.
        self.assertIn("_clear_poses_only(node)", body,
            "Part F.1: Step 1 MUST call _clear_poses_only so "
            "input[]/output[] connections survive Apply. Calling "
            "clear_node_data here would re-introduce the user's "
            "directive-4 regression.")
        # The legacy clear_node_data MUST NOT appear in this routed
        # path -- that's the entire point of the fix.
        self.assertNotIn("clear_node_data(node)", body,
            "Part F.1: apply_poses_routed MUST NOT call "
            "clear_node_data (that wipes input[]/output[]).")
        # Post-apply metadata audit MUST emit warnings on drift.
        self.assertIn("apply_poses_routed: driverSource[]", body,
            "Part F.1: post-apply audit MUST surface driverSource[] "
            "drift via cmds.warning")

    def test_PERMANENT_12_clear_poses_only_skips_input_output(self):
        """Part F.2: _clear_poses_only MUST iterate only the
        pose-related multi attrs (poses, baseValue, outputIsScale)
        and MUST NOT touch input[] or output[]. The whole point of
        the helper is to leave the multi-driver wiring alive across
        Apply."""
        self.assertIn("def _clear_poses_only(node):", self._core,
            "core MUST expose _clear_poses_only (Part F.2)")
        body = _slice_def(self._core, "def _clear_poses_only(node):")
        # The attr tuple MUST list exactly poses/baseValue/
        # outputIsScale. Verifying the literal string keeps the test
        # tied to the canonical helper layout.
        self.assertIn(
            '("poses", "baseValue", "outputIsScale")', body,
            "Part F.2: _clear_poses_only MUST iterate exactly "
            'the tuple ("poses", "baseValue", "outputIsScale")')
        # And it MUST NOT mention "input" or "output" as attrs to
        # clear -- those are precisely the connections to preserve.
        # Defensive: check the iteration tuple doesn't contain
        # "input" / "output" (i.e. no clear_node_data-style 5-tuple).
        self.assertNotIn('"input"', body,
            "Part F.2: _clear_poses_only MUST NOT include "
            '"input" in the clear loop')
        self.assertNotIn('"output"', body,
            "Part F.2: _clear_poses_only MUST NOT include "
            '"output" in the clear loop')

    def test_PERMANENT_13_controller_apply_poses_routed(self):
        """Part F.3: controller.apply_poses_routed MUST exist and
        forward to core.apply_poses_routed after the duplicate-pose
        pre-check (parity with the legacy apply_poses)."""
        self.assertIn(
            "def apply_poses_routed(self, driver_targets, "
            "driven_targets):",
            self._ctrl,
            "controller MUST expose apply_poses_routed (Part F.3)")
        body = _slice_def(self._ctrl,
            "def apply_poses_routed(self, driver_targets, "
            "driven_targets):")
        self.assertIn(
            "core.apply_poses_routed(", body,
            "controller.apply_poses_routed MUST forward to "
            "core.apply_poses_routed")
        # Duplicate-pose pre-check parity with apply_poses.
        self.assertIn("_detect_duplicate_pose_inputs", body,
            "Part F.3: controller.apply_poses_routed MUST run the "
            "duplicate-pose pre-check before invoking core")

    def test_PERMANENT_14_on_apply_dispatch_by_topology(self):
        """Part F.4: main_window._on_apply MUST dispatch by
        driverSource topology -- multi-driver routes through
        apply_poses_routed, single-driver keeps the legacy
        apply_poses. Also MUST refresh tab indicators post-Apply
        so the user sees the green dots survive (the whole point
        of Part F)."""
        body = _slice_def(self._main, "def _on_apply(self):")
        self.assertIn("is_multi", body,
            "Part F.4: _on_apply MUST compute an is_multi flag for "
            "topology-aware dispatch")
        self.assertIn("apply_poses_routed(", body,
            "Part F.4: _on_apply MUST call apply_poses_routed in "
            "the multi-driver branch")
        self.assertIn("self._ctrl.apply_poses(", body,
            "Part F.4: _on_apply MUST still call legacy apply_poses "
            "in the single-driver branch (0 regression)")
        self.assertIn("refresh_tab_indicators(self._ctrl)", body,
            "Part F.4: _on_apply MUST refresh tab indicators "
            "post-Apply so the user sees whether multi-driver "
            "wiring survived (Part B / directive #4)")


# ----------------------------------------------------------------------
# Runtime behaviour -- mocked cmds (only under pure-Python conftest)
# ----------------------------------------------------------------------


@unittest.skipIf(conftest._REAL_MAYA,
    "mock-dependent (cmds + core stubs)")
class TestM_P0_DRIVER_CONNECT_UX_REVAMP_Runtime(unittest.TestCase):
    """Runtime tests for driver_source_connection_state with the
    core helpers stubbed at module level. These verify that the
    helper returns the documented string for the three canonical
    state machines (connected / partial / disconnected)."""

    def _setup_core_stubs(self, sources, wired_attrs_per_source,
                          shape="rbfShape", node="rbfNode"):
        """Patch core helpers so driver_source_connection_state
        sees a well-defined wire state without touching Maya.

        *sources* is list of (driver_node, attrs_tuple). The helper
        considers each tab fully wired iff *wired_attrs_per_source*
        sets the same length; partial iff shorter; disconnected
        iff empty.
        """
        from RBFtools import core

        # Build DriverSource tuples mirroring read_driver_info_multi's
        # contract.
        ds_list = []
        for drv_node, attrs in sources:
            ds_list.append(core.DriverSource(
                node=drv_node, attrs=tuple(attrs),
                weight=1.0, encoding=0))

        # _subscript_of_existing_input lookup table: a plug exists
        # iff (source_node, attr) is in the wired set.
        wired_set = set()
        for i, (drv_node, attrs) in enumerate(sources):
            attrs_wired = wired_attrs_per_source[i] if (
                i < len(wired_attrs_per_source)) else []
            for a in attrs_wired:
                wired_set.add((drv_node, a))

        def _sub_lookup(plug, shape_arg):
            for (n, a) in wired_set:
                if plug == "{}.{}".format(n, a):
                    return 0
            return None

        patches = [
            mock.patch.object(core, "_exists", return_value=True),
            mock.patch.object(core, "get_shape", return_value=shape),
            mock.patch.object(core, "read_driver_info_multi",
                              return_value=ds_list),
            mock.patch.object(core, "_subscript_of_existing_input",
                              side_effect=_sub_lookup),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def test_connection_state_connected(self):
        from RBFtools import core
        self._setup_core_stubs(
            sources=[("driverA", ["rx"])],
            wired_attrs_per_source=[["rx"]])
        self.assertEqual(
            core.driver_source_connection_state("rbfNode", 0),
            "connected")

    def test_connection_state_partial(self):
        from RBFtools import core
        self._setup_core_stubs(
            sources=[("driverA", ["rx", "ry", "rz"])],
            wired_attrs_per_source=[["rx"]])
        self.assertEqual(
            core.driver_source_connection_state("rbfNode", 0),
            "partial")

    def test_connection_state_disconnected_no_wires(self):
        from RBFtools import core
        self._setup_core_stubs(
            sources=[("driverA", ["rx", "ry", "rz"])],
            wired_attrs_per_source=[[]])
        self.assertEqual(
            core.driver_source_connection_state("rbfNode", 0),
            "disconnected")

    def test_connection_state_disconnected_out_of_range(self):
        from RBFtools import core
        self._setup_core_stubs(
            sources=[("driverA", ["rx"])],
            wired_attrs_per_source=[["rx"]])
        # Index 5 has no source -- helper returns disconnected
        # rather than raising.
        self.assertEqual(
            core.driver_source_connection_state("rbfNode", 5),
            "disconnected")


# ----------------------------------------------------------------------
# Attr dedupe -- pure logic test (no cmds required)
# ----------------------------------------------------------------------


class TestAttrDedupePreservesOrder(unittest.TestCase):
    """Part E.3 invariant: the dedupe loop MUST preserve order
    when the same attr appears more than once in the raw
    selection."""

    def _dedupe(self, attrs_raw):
        # Mirror the inline dedupe in
        # tabbed_source_editor._on_connect_clicked. Kept here as a
        # one-line helper so the test exercises the exact same
        # algorithm without instantiating a QWidget.
        seen = set()
        out = []
        for a in attrs_raw:
            if a not in seen:
                seen.add(a)
                out.append(a)
        return out

    def test_attr_dedupe_preserves_order_typical(self):
        self.assertEqual(
            self._dedupe(["X", "Y", "X", "Z"]),
            ["X", "Y", "Z"])

    def test_attr_dedupe_preserves_order_no_dupes(self):
        self.assertEqual(
            self._dedupe(["rx", "ry", "rz"]),
            ["rx", "ry", "rz"])

    def test_attr_dedupe_preserves_order_all_dupes(self):
        self.assertEqual(
            self._dedupe(["a", "a", "a", "a"]),
            ["a"])


if __name__ == "__main__":
    unittest.main()
