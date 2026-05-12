"""M_B24c - Mirror multi-source migration tests + #33 source-scan.

Locks the M_B24c contract:

  * `core.mirror_node` reads via :func:`read_driver_info_multi` (not
    the deprecated `read_driver_info`), iterates every driver source
    per pose, applies the naming rule per source with F.1 fallback
    (no match -> keep original + cmds.warning).
  * Write side delegates to :func:`add_driver_source` per source -
    reusing the M_B24d / M_B24d_matrix_followup atomic + mode-
    exclusion + worldMatrix wiring rather than the legacy
    `connect_node` single-driver path.
  * Matrix-mode multi-source mirror is hard-blocked at the engine
    entry with a `NotImplementedError` (M_B24c (Hardening 2)).
  * `read_driver_info_multi` docstring carries the M_B24c RESOLVED
    stamp while preserving the M_B24b2 anchor that
    T_V5_PARITY_B2_LIVE (#29) sub-check (d) asserts on.

#33 T_MIRROR_MULTI_SOURCE_WIRED is the new permanent guard: 4 source-
scan sub-checks on the mirror_node function body.
"""

from __future__ import absolute_import

import inspect
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
# #33 T_MIRROR_MULTI_SOURCE_WIRED — 4 source-scan sub-checks
# ----------------------------------------------------------------------


class TestM_B24C_MirrorMultiSourceWired(unittest.TestCase):
    """#33 - source-scan core.py:mirror_node body."""

    @classmethod
    def setUpClass(cls):
        from RBFtools.core import mirror_node
        cls._body = inspect.getsource(mirror_node)

    def test_a_uses_read_driver_info_multi(self):
        """Sub-check (a): mirror_node must read sources via the
        multi API. Bare `read_driver_info(` (deprecated) is NOT
        permitted on the driver side - call should match `_multi(`."""
        self.assertIn("read_driver_info_multi", self._body,
            "mirror_node must use read_driver_info_multi (M_B24c)")
        # Driver-side `read_driver_info(` (without `_multi`) is the
        # forbidden literal. Allow `read_driver_info_multi(` and
        # docstring mentions; check via regex with negative lookahead.
        forbidden = re.findall(r"read_driver_info\((?!_multi)", self._body)
        self.assertFalse(forbidden,
            "mirror_node body must not call deprecated "
            "read_driver_info() on driver side (M_B24c (C.1))")

    def test_b_uses_add_driver_source(self):
        """Sub-check (b): write-side driver wiring delegates to
        add_driver_source (M_B24d/M_B24d_matrix_followup reuse,
        decision E.3)."""
        self.assertIn("add_driver_source", self._body,
            "mirror_node write side must reuse add_driver_source "
            "(M_B24c (E.3))")

    def test_c_no_connect_node_driver_side(self):
        """Sub-check (c): mirror_node must NOT call connect_node.
        connect_node bundles wire_driver_inputs (legacy single-
        driver) with wire_driven_outputs - using it would overwrite
        the multi-source add_driver_source wiring. Driven side calls
        wire_driven_outputs directly instead."""
        # `connect_node` appears nowhere in the mirror_node body
        # (we replaced it with wire_driven_outputs + per-source
        # add_driver_source loop).
        self.assertNotIn("connect_node(", self._body,
            "mirror_node must not call connect_node (legacy single-"
            "driver path); driven side wires via wire_driven_outputs "
            "and driver side via add_driver_source (M_B24c (E.3))")
        # Driven side wire is allowed and required.
        self.assertIn("wire_driven_outputs", self._body,
            "mirror_node must wire driven side via wire_driven_outputs")

    def test_d_matrix_mode_entry_guard_present(self):
        """Sub-check (d): mirror_node entry contains _is_matrix_mode
        probe + NotImplementedError raise pointing at M_B24c2
        (Hardening 2)."""
        self.assertIn("_is_matrix_mode", self._body,
            "mirror_node entry must probe _is_matrix_mode (M_B24c "
            "Hardening 2)")
        self.assertIn("NotImplementedError", self._body,
            "mirror_node must raise NotImplementedError for Matrix-"
            "mode multi-source (M_B24c2 deferred)")
        self.assertIn("M_B24c2", self._body,
            "mirror_node Matrix-mode raise must reference M_B24c2 "
            "deferred sub-task")


# ----------------------------------------------------------------------
# Source-scan: per-source naming fallback wired (F.1)
# ----------------------------------------------------------------------


class TestM_B24C_PerSourceNamingFallback(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from RBFtools.core import mirror_node
        cls._body = inspect.getsource(mirror_node)

    def test_remap_loop_present(self):
        """F.1 fallback: per-source loop computes new_name +
        appends warnings.append on no_match, preserving the
        original name (mirror does NOT abort)."""
        self.assertIn("for s in sources", self._body,
            "mirror_node must loop over sources for per-source "
            "naming remap (M_B24c (A.3))")
        self.assertIn("apply_naming_rule", self._body)
        # F.1 fallback: warnings.append + 'using original name'
        self.assertTrue(
            "Driver name remap failed for source" in self._body,
            "mirror_node must record per-source name-remap failure "
            "via warnings.append (M_B24c (F.1))")


# ----------------------------------------------------------------------
# Source-scan: docstring RESOLVED stamp on read_driver_info_multi
# ----------------------------------------------------------------------


class TestM_B24C_DocstringResolvedStamp(unittest.TestCase):
    """Confirms the M_B24b2 anchor is preserved (so
    T_V5_PARITY_B2_LIVE (#29) sub-check (d) keeps passing) AND the
    M_B24c RESOLVED stamp is present."""

    def test_docstring_preserves_legacy_anchor(self):
        from RBFtools.core import read_driver_info_multi
        doc = read_driver_info_multi.__doc__ or ""
        self.assertIn("§M_B24b2.mirror-deferred-rationale", doc,
            "Legacy M_B24b2 anchor must be preserved (T_V5_PARITY_"
            "B2_LIVE #29 sub-check (d) depends on this literal)")

    def test_docstring_has_m_b24c_resolved_stamp(self):
        from RBFtools.core import read_driver_info_multi
        doc = read_driver_info_multi.__doc__ or ""
        self.assertIn("RESOLVED", doc,
            "Docstring must carry the M_B24c RESOLVED stamp")
        self.assertIn("M_B24c", doc)
        self.assertIn("M_B24c2", doc,
            "Docstring must point at M_B24c2 for the still-deferred "
            "Matrix-mode multi-source mirror sub-task")
        self.assertIn("planner-error-correction", doc,
            "Docstring must reference the planner-error-correction "
            "anchor (callsite count corrected from 5 to 2)")


# ----------------------------------------------------------------------
# Mock-pattern: Matrix mode multi-source -> NotImplementedError
# ----------------------------------------------------------------------


@unittest.skipIf(conftest._REAL_MAYA,
    "mock-dependent (cmds.reset_mock / mock.patch on cmds.*)")
class TestM_B24C_MatrixEntryGuard(unittest.TestCase):

    def _patch_matrix(self, n_sources):
        """Force _is_matrix_mode -> True and read_driver_info_multi
        -> n_sources synthetic DriverSource entries."""
        from RBFtools import core
        sources = [
            core.DriverSource(
                node="drv{}".format(i),
                attrs=("translateX",),
                weight=1.0, encoding=0)
            for i in range(n_sources)
        ]
        return mock.patch.multiple(
            "RBFtools.core",
            _is_matrix_mode=mock.MagicMock(return_value=True),
            read_driver_info_multi=mock.MagicMock(return_value=sources),
            _exists=mock.MagicMock(return_value=True),
            get_shape=mock.MagicMock(return_value="srcShape"),
        )

    def test_matrix_multi_source_raises(self):
        from RBFtools import core
        with self._patch_matrix(2):
            with self.assertRaises(NotImplementedError) as ctx:
                core.mirror_node(
                    source_node="src",
                    target_name="tgt",
                    mirror_axis=0,
                    naming_rule_index=0)
        msg = str(ctx.exception)
        self.assertIn("Matrix-mode multi-source mirror is DEFERRED", msg)
        self.assertIn("M_B24c2", msg)
        self.assertIn("§M_B24c2-stub", msg)

    def test_matrix_single_source_does_not_raise_at_guard(self):
        """Single-source Matrix node must NOT trip the multi-source
        guard. (It may fail later for unrelated mock-shape reasons,
        but the NotImplementedError specific to the guard is the
        contract under test.)"""
        from RBFtools import core
        import maya.cmds as cmds
        cmds.reset_mock()
        cmds.objExists.return_value = True
        cmds.listRelatives.return_value = ["srcShape"]
        cmds.getAttr.return_value = []
        cmds.listConnections.return_value = []
        with self._patch_matrix(1):
            try:
                core.mirror_node(
                    source_node="src",
                    target_name="tgt",
                    mirror_axis=0,
                    naming_rule_index=0)
            except NotImplementedError as exc:
                self.fail(
                    "mirror_node raised NotImplementedError for a "
                    "single-source Matrix node: {}".format(exc))
            except Exception:
                # Other failures (mock incompleteness) are allowed -
                # we are only guarding against the M_B24c2 raise.
                pass


# ----------------------------------------------------------------------
# Mock-pattern: controller.mirror_current_node uses _info action_id
# ----------------------------------------------------------------------


class TestM_B24C_ControllerActionId(unittest.TestCase):
    """Source-scan controller.py for the renamed action_id (G.1)."""

    @classmethod
    def setUpClass(cls):
        path = os.path.normpath(os.path.join(
            os.path.dirname(__file__), "..", "scripts", "RBFtools",
            "controller.py"))
        with open(path, "r", encoding="utf-8") as f:
            cls._src = f.read()

    def test_renamed_action_id_present(self):
        self.assertIn('action_id="mirror_multi_source_info"', self._src,
            "controller must use mirror_multi_source_info action_id "
            "(M_B24c (G.1) rename)")

    def test_legacy_action_id_removed(self):
        self.assertNotIn(
            'action_id="mirror_multi_source_warning"', self._src,
            "Legacy mirror_multi_source_warning action_id must be "
            "removed after the M_B24c (G.1) rename")

    def test_per_source_preview_loop_present(self):
        self.assertIn("driver_preview_lines", self._src,
            "controller mirror preview must iterate per-source "
            "driver remap (M_B24c (A.3))")


if __name__ == "__main__":
    unittest.main()
