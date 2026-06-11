# -*- coding: utf-8 -*-
"""M_P0_TAB_REMOVE_SPARSE_FIX (2026-04-30) — multi-tab remove only
worked on the first source.

User report 2026-04-30: with multiple drivers / drivens, clicking
the X on tabs 2, 3, ... is silently ignored. Repro path:

  view (Qt tabCloseRequested + list enumerate) emits a DENSE
    list-position index 0..n-1
  -> main_window._on_driver_source_remove_requested(idx)
  -> ctrl.remove_driver_source(idx)
  -> core.remove_driver_source(node, idx)   [treats idx as sparse]

  But core.add_*_source picks new sparse multi indices via
  ``max(indices) + 1`` — append-only with NO hole reuse. So once
  any non-tail entry is removed, the driverSource[] sparse multi
  becomes discontinuous (e.g. [0, 1, 2] -> remove 0 -> [1, 2]).

  First click: list_pos == sparse_idx == 0 (coincidence) -> works.
  Subsequent clicks: list_pos != sparse_idx -> core hits an empty
  multi slot, removeMultiInstance is a silent no-op, the X looks
  dead.

The same drift hits FIVE more view-facing controller methods (every
caller that takes a "list_idx" from the view layer):

    remove_driver_source              user-visible repro
    remove_driven_source              driven mirror
    set_driver_source_attrs           silently edits wrong source
    set_driven_source_attrs           silently edits wrong source
    disconnect_driver_source_attrs    silently disconnects wrong
    disconnect_driven_source_attrs    silently disconnects wrong

Lesson #7 (project-methodology candidate): "view ↔ core index-
space drift goes silent until the sparse multi goes
discontinuous". The boundary translator at the controller layer is
the canonical fix; view keeps emitting dense Qt indices, core
keeps consuming sparse multi indices, the controller bridges.

Lesson #6 reinforced: AST guard walks ast.parse(controller.py) and
asserts every one of the six view-facing methods invokes
``self._list_idx_to_sparse(...)`` at least once — drift detection
that static grep alone cannot enforce.

PERMANENT GUARD T_P0_TAB_REMOVE_SPARSE.
"""

from __future__ import absolute_import

import ast
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


# The six view-facing methods that take a list-position index from
# the view and historically passed it straight to core as a sparse
# multi index. Each MUST translate via _list_idx_to_sparse first.
_GUARDED_METHODS = (
    "remove_driver_source",
    "remove_driven_source",
    "set_driver_source_attrs",
    "set_driven_source_attrs",
    "disconnect_driver_source_attrs",
    "disconnect_driven_source_attrs",
)


def _read(p):
    with open(p, "r", encoding="utf-8") as fh:
        return fh.read()


# ----------------------------------------------------------------------
# PERMANENT GUARD T_P0_TAB_REMOVE_SPARSE
# ----------------------------------------------------------------------


class T_P0_TAB_REMOVE_SPARSE(unittest.TestCase):
    """PERMANENT GUARD — DO NOT REMOVE.

    Locks the controller-layer boundary translator that bridges
    Qt dense list-position to driverSource[]/drivenSource[] sparse
    multi index."""

    @classmethod
    def setUpClass(cls):
        cls._src = _read(_CTRL_PY)
        cls._tree = ast.parse(cls._src)

    def test_PERMANENT_a_helper_present(self):
        self.assertIn(
            "def _list_idx_to_sparse(self, role, list_idx):",
            self._src,
            "controller MUST define _list_idx_to_sparse(role, "
            "list_idx) — the canonical view↔core index translator.")

    def test_PERMANENT_b_helper_returns_none_on_oob(self):
        # Static read of the helper body — must explicitly handle
        # out-of-range with None (NOT an exception, NOT a silent 0).
        body = self._src.split(
            "def _list_idx_to_sparse(self, role, list_idx):"
        )[1].split("\n    def ")[0]
        self.assertIn(
            "return None", body,
            "_list_idx_to_sparse MUST return None on no-current-"
            "node / shape-missing / multiIndices-unavailable / "
            "list_idx-out-of-range branches.")
        # Sort the multiIndices result so view↔sparse mapping is
        # deterministic regardless of cmds ordering.
        self.assertIn(
            "sorted(", body,
            "Helper MUST sort multiIndices before indexing — "
            "Maya's order is documented ascending but the explicit "
            "sort is a defence-in-depth contract.")

    def test_PERMANENT_c_ast_guard_six_methods_translate(self):
        # AST walk: each guarded method MUST invoke
        # self._list_idx_to_sparse at least once in its body. This
        # is the lesson-#6 drift guard reapplied — static grep
        # could miss a future regression that types `int(index)`
        # back in by accident.
        violations = []
        for node in ast.walk(self._tree):
            if not isinstance(node, ast.FunctionDef):
                continue
            if node.name not in _GUARDED_METHODS:
                continue
            calls_helper = False
            for sub in ast.walk(node):
                if not isinstance(sub, ast.Call):
                    continue
                func = sub.func
                if isinstance(func, ast.Attribute) and \
                        func.attr == "_list_idx_to_sparse":
                    calls_helper = True
                    break
            if not calls_helper:
                violations.append(node.name)
        self.assertEqual(
            violations, [],
            "AST guard: the following view-facing methods do NOT "
            "call self._list_idx_to_sparse — list-pos drift will "
            "re-introduce the user's P0 multi-tab remove bug:\n"
            "{}".format(violations))

    def test_PERMANENT_d_ast_guard_no_int_index_on_core_calls(self):
        # Defence-in-depth: each guarded method's body MUST NOT
        # pass `int(index)` to core.* — that pattern was the
        # original bug shape. Translation is now via multi_idx.
        for method_name in _GUARDED_METHODS:
            body = self._src.split(
                "def {}(self,".format(method_name)
            )[1].split("\n    def ")[0]
            # Locate the core.* call line(s) inside the body.
            for line in body.splitlines():
                stripped = line.strip()
                if not stripped.startswith(
                        ("core.remove_", "core.set_",
                         "core.disconnect_")):
                    continue
                self.assertNotIn(
                    "int(index)", stripped,
                    "Method {!r} still passes int(index) to "
                    "{!r} — drift regression. Use multi_idx "
                    "instead.".format(method_name, stripped))


# ----------------------------------------------------------------------
# Mock E2E — boundary translator + every guarded method.
# ----------------------------------------------------------------------


@unittest.skipIf(conftest._REAL_MAYA,
    "mock-dependent (cmds + core stubs)")
class TestM_P0_TAB_REMOVE_SPARSE_RuntimeBehavior(unittest.TestCase):

    # ------------------------------------------------------------------
    # Helper boundary cases.
    # ------------------------------------------------------------------

    def _make_ctrl(self, sparse_indices):
        """Build a controller stub whose _list_idx_to_sparse hits a
        cmds.getAttr(multiIndices=True) returning *sparse_indices*."""
        from RBFtools.controller import MainController
        ctrl = MainController.__new__(MainController)
        ctrl._current_node = "RBF1"
        ctrl._sparse = list(sparse_indices)
        return ctrl

    def _patch_helper_env(self, ctrl):
        """Yield a context where core.get_shape returns "RBF1Shape"
        and cmds.getAttr(driver/drivenSource, multiIndices=True)
        returns ctrl._sparse."""
        from RBFtools import core
        from RBFtools import controller as ctrl_mod
        cmds_stub = mock.MagicMock()
        cmds_stub.getAttr = mock.MagicMock(
            return_value=list(ctrl._sparse))
        cmds_stub.warning = mock.MagicMock()
        return mock.patch.multiple(
            ctrl_mod,
            cmds=cmds_stub,
            core=mock.MagicMock(
                get_shape=mock.MagicMock(return_value="RBF1Shape"),
                # remove/set/disconnect are exercised by the
                # individual tests via deeper patches; here the
                # helper only needs get_shape.
            ),
        )

    def test_helper_translates_dense_to_sparse(self):
        # sparse=[2, 5, 7] -> list_idx 0->2, 1->5, 2->7
        from RBFtools.controller import MainController
        ctrl = self._make_ctrl([2, 5, 7])
        with self._patch_helper_env(ctrl):
            self.assertEqual(
                MainController._list_idx_to_sparse(
                    ctrl, "driver", 0), 2)
            self.assertEqual(
                MainController._list_idx_to_sparse(
                    ctrl, "driver", 1), 5)
            self.assertEqual(
                MainController._list_idx_to_sparse(
                    ctrl, "driver", 2), 7)

    def test_helper_returns_none_oob(self):
        from RBFtools.controller import MainController
        ctrl = self._make_ctrl([0, 1, 2])
        with self._patch_helper_env(ctrl):
            for bad in (-1, 3, 99):
                self.assertIsNone(
                    MainController._list_idx_to_sparse(
                        ctrl, "driver", bad),
                    "list_idx {} MUST map to None".format(bad))

    def test_helper_returns_none_no_current_node(self):
        from RBFtools.controller import MainController
        ctrl = self._make_ctrl([0, 1, 2])
        ctrl._current_node = ""
        # No env patch needed — early return.
        self.assertIsNone(
            MainController._list_idx_to_sparse(ctrl, "driver", 0))

    def test_helper_role_string_drives_attr_name(self):
        # "driven" must read drivenSource, not driverSource.
        from RBFtools.controller import MainController
        from RBFtools import controller as ctrl_mod
        ctrl = self._make_ctrl([4, 9])
        cmds_stub = mock.MagicMock()
        seen = []

        def _get(plug, multiIndices=False):
            seen.append(plug)
            return [4, 9]

        cmds_stub.getAttr.side_effect = _get
        with mock.patch.multiple(
                ctrl_mod, cmds=cmds_stub,
                core=mock.MagicMock(
                    get_shape=mock.MagicMock(
                        return_value="RBF1Shape"))):
            MainController._list_idx_to_sparse(ctrl, "driven", 0)
        self.assertTrue(seen)
        self.assertIn("drivenSource", seen[0],
            "role='driven' MUST query drivenSource multi attr "
            "(got {!r}).".format(seen[0]))

    def test_helper_sorts_unsorted_multi_indices(self):
        # Defence-in-depth: even if cmds returns an unsorted
        # list, the helper MUST treat indices in ascending order
        # (matches view rebuild order from read_*_info_multi).
        from RBFtools.controller import MainController
        from RBFtools import controller as ctrl_mod
        cmds_stub = mock.MagicMock()
        cmds_stub.getAttr = mock.MagicMock(return_value=[7, 2, 5])
        ctrl = self._make_ctrl([])  # value irrelevant — getAttr stubs
        ctrl._current_node = "RBF1"
        with mock.patch.multiple(
                ctrl_mod, cmds=cmds_stub,
                core=mock.MagicMock(
                    get_shape=mock.MagicMock(
                        return_value="RBF1Shape"))):
            self.assertEqual(
                MainController._list_idx_to_sparse(
                    ctrl, "driver", 0), 2)
            self.assertEqual(
                MainController._list_idx_to_sparse(
                    ctrl, "driver", 1), 5)
            self.assertEqual(
                MainController._list_idx_to_sparse(
                    ctrl, "driver", 2), 7)

    # ------------------------------------------------------------------
    # The user-reported repro: 3 drivers, click ❌❌❌ in sequence.
    # ------------------------------------------------------------------

    def test_repro_three_drivers_three_x_clicks_each_hits_correct_sparse(self):
        # Sparse starts [0, 1, 2]. User clicks tab 0 X three times
        # (each click after the reload re-numbers tabs to dense
        # 0..n-1). Pre-fix: only the first click landed.
        # Post-fix: every click translates list_pos 0 to the
        # CURRENT first sparse idx and core.remove receives 0/1/2.
        from RBFtools.controller import MainController
        from RBFtools import core

        sparse_state = [[0, 1, 2]]
        captured_indices = []

        def _fake_remove(_node, idx):
            captured_indices.append(idx)
            sparse_state[0] = [s for s in sparse_state[0] if s != idx]

        ctrl = MainController.__new__(MainController)
        ctrl._current_node = "RBF1"
        ctrl.driverSourcesChanged = mock.MagicMock()
        ctrl.ask_confirm = mock.MagicMock(return_value=True)
        # Stub the helper to read the live sparse_state (mirrors
        # what _list_idx_to_sparse does internally).
        ctrl._list_idx_to_sparse = lambda role, idx: (
            sparse_state[0][idx]
            if 0 <= idx < len(sparse_state[0]) else None)
        with mock.patch.object(
                core, "remove_driver_source",
                side_effect=_fake_remove):
            # Click X on tab 0 three times.
            MainController.remove_driver_source(ctrl, 0)
            MainController.remove_driver_source(ctrl, 0)
            MainController.remove_driver_source(ctrl, 0)
        self.assertEqual(
            captured_indices, [0, 1, 2],
            "Three sequential ❌-clicks on tab 0 MUST translate to "
            "sparse indices [0, 1, 2] — the original bug captured "
            "[0, 0, 0] which silently no-op'd after the first.")
        self.assertEqual(sparse_state[0], [],
            "All three drivers removed.")

    def test_repro_three_drivens_mirror(self):
        # Driven mirror of the repro.
        from RBFtools.controller import MainController
        from RBFtools import core

        sparse_state = [[0, 1, 2]]
        captured = []

        def _fake_remove(_node, idx):
            captured.append(idx)
            sparse_state[0] = [s for s in sparse_state[0] if s != idx]

        ctrl = MainController.__new__(MainController)
        ctrl._current_node = "RBF1"
        ctrl.drivenSourcesChanged = mock.MagicMock()
        ctrl.ask_confirm = mock.MagicMock(return_value=True)
        ctrl._list_idx_to_sparse = lambda role, idx: (
            sparse_state[0][idx]
            if 0 <= idx < len(sparse_state[0]) else None)
        with mock.patch.object(
                core, "remove_driven_source",
                side_effect=_fake_remove):
            MainController.remove_driven_source(ctrl, 0)
            MainController.remove_driven_source(ctrl, 0)
            MainController.remove_driven_source(ctrl, 0)
        self.assertEqual(captured, [0, 1, 2])

    # ------------------------------------------------------------------
    # Set/disconnect attrs paths — sparse-discontinuous edits.
    # ------------------------------------------------------------------

    def test_set_driver_source_attrs_uses_translated_sparse(self):
        # Sparse [1, 2] (after a prior remove of 0). View tab 0
        # MUST translate to sparse 1, not sparse 0 (which is empty).
        from RBFtools.controller import MainController
        from RBFtools import core
        ctrl = MainController.__new__(MainController)
        ctrl._current_node = "RBF1"
        ctrl.driverSourcesChanged = mock.MagicMock()
        ctrl._list_idx_to_sparse = mock.MagicMock(return_value=1)
        with mock.patch.object(
                core, "set_driver_source_attrs",
                return_value=True) as core_set:
            MainController.set_driver_source_attrs(
                ctrl, 0, ["rotateY"])
        ctrl._list_idx_to_sparse.assert_called_with("driver", 0)
        core_set.assert_called_once_with(
            "RBF1", 1, ["rotateY"])

    def test_set_driven_source_attrs_uses_translated_sparse(self):
        from RBFtools.controller import MainController
        from RBFtools import core
        ctrl = MainController.__new__(MainController)
        ctrl._current_node = "RBF1"
        ctrl.drivenSourcesChanged = mock.MagicMock()
        ctrl._list_idx_to_sparse = mock.MagicMock(return_value=3)
        with mock.patch.object(
                core, "set_driven_source_attrs",
                return_value=True) as core_set:
            MainController.set_driven_source_attrs(
                ctrl, 0, ["tx", "ty"])
        core_set.assert_called_once_with(
            "RBF1", 3, ["tx", "ty"])

    def test_disconnect_driver_source_attrs_uses_translated_sparse(self):
        from RBFtools.controller import MainController
        from RBFtools import core
        ctrl = MainController.__new__(MainController)
        ctrl._current_node = "RBF1"
        ctrl.driverSourcesChanged = mock.MagicMock()
        ctrl._list_idx_to_sparse = mock.MagicMock(return_value=2)
        with mock.patch.object(
                core, "disconnect_driver_source_attrs",
                return_value=True) as core_disc:
            MainController.disconnect_driver_source_attrs(
                ctrl, 0, attrs=["rx"])
        core_disc.assert_called_once_with(
            "RBF1", 2, attrs=["rx"])

    def test_disconnect_driven_source_attrs_uses_translated_sparse(self):
        from RBFtools.controller import MainController
        from RBFtools import core
        ctrl = MainController.__new__(MainController)
        ctrl._current_node = "RBF1"
        ctrl.drivenSourcesChanged = mock.MagicMock()
        ctrl._list_idx_to_sparse = mock.MagicMock(return_value=5)
        with mock.patch.object(
                core, "disconnect_driven_source_attrs",
                return_value=True) as core_disc:
            MainController.disconnect_driven_source_attrs(
                ctrl, 0, attrs=["tx"])
        core_disc.assert_called_once_with(
            "RBF1", 5, attrs=["tx"])

    # ------------------------------------------------------------------
    # Cancel paths — translator runs BEFORE confirm dialog so a
    # stale view index never triggers a phantom prompt.
    # ------------------------------------------------------------------

    def test_remove_driver_source_aborts_when_translator_returns_none(self):
        from RBFtools.controller import MainController
        from RBFtools import core
        ctrl = MainController.__new__(MainController)
        ctrl._current_node = "RBF1"
        ctrl.driverSourcesChanged = mock.MagicMock()
        ctrl.ask_confirm = mock.MagicMock(return_value=True)
        ctrl._list_idx_to_sparse = mock.MagicMock(return_value=None)
        with mock.patch.object(
                core, "remove_driver_source") as core_remove:
            ok = MainController.remove_driver_source(ctrl, 99)
        self.assertFalse(ok)
        core_remove.assert_not_called()
        # Confirm dialog MUST NOT have been shown for a phantom idx.
        ctrl.ask_confirm.assert_not_called()
        ctrl.driverSourcesChanged.emit.assert_not_called()

    def test_set_attrs_aborts_when_translator_returns_none(self):
        from RBFtools.controller import MainController
        from RBFtools import core
        ctrl = MainController.__new__(MainController)
        ctrl._current_node = "RBF1"
        ctrl.driverSourcesChanged = mock.MagicMock()
        ctrl._list_idx_to_sparse = mock.MagicMock(return_value=None)
        with mock.patch.object(
                core, "set_driver_source_attrs") as core_set:
            ok = MainController.set_driver_source_attrs(
                ctrl, 99, ["tx"])
        self.assertFalse(ok)
        core_set.assert_not_called()
        ctrl.driverSourcesChanged.emit.assert_not_called()


if __name__ == "__main__":
    unittest.main()
