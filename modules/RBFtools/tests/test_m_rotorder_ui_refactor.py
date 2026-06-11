# -*- coding: utf-8 -*-
"""M_ROTORDER_UI_REFACTOR (2026-04-29) — driver-tab-synced
rotate-order editor.

Pre-refactor: ``OrderedEnumListEditor`` (4-button add/remove/up/down)
let the user edit the ``driverInputRotateOrder[]`` row count and
ordering independently of the actual driverSource[] count, producing
mismatched scenes that mis-encoded the C++ applyEncodingToBlock
reads (RBFtools.cpp:2624).

Path B refactor: a new dedicated widget
``DriverRotateOrderEditor`` projects the driver-source tab list
into rows. The user can ONLY edit the per-row enum combo
(xyz / yzx / zxy / xzy / yxz / zyx); add / remove / reorder
controls are NOT exposed.

5-file atomic change:
  * ``widgets/driver_rotate_order_editor.py`` — new widget.
  * ``rbf_section.py`` — import + instantiation swap;
    ``set_driver_sources_for_rotate_order`` public entry-point.
  * ``controller.py`` — ``_resync_rotate_order_length`` self-heal
    helper (truncate / pad multi to driver count).
  * ``main_window.py`` — ``_reload_driver_sources`` tail appends a
    self-heal call + the ``set_driver_sources_for_rotate_order``
    push (1-shot per driver-list change, ≤3 LoC per planner
    ratification).
  * ``i18n.py`` — ``driver_rotate_order_row_label`` template
    (EN + ZH parity).

PERMANENT GUARD T_DRIVER_ROTATE_ORDER_SYNC.
"""

from __future__ import absolute_import

import os
import unittest
from unittest import mock

import conftest


_REPO_ROOT = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..")
)
_NEW_WIDGET_PY = os.path.join(
    _REPO_ROOT, "modules", "RBFtools", "scripts", "RBFtools",
    "ui", "widgets", "driver_rotate_order_editor.py")
_RBF_SECTION_PY = os.path.join(
    _REPO_ROOT, "modules", "RBFtools", "scripts", "RBFtools",
    "ui", "widgets", "rbf_section.py")
_CTRL_PY = os.path.join(
    _REPO_ROOT, "modules", "RBFtools", "scripts", "RBFtools",
    "controller.py")
_MAIN_WINDOW_PY = os.path.join(
    _REPO_ROOT, "modules", "RBFtools", "scripts", "RBFtools",
    "ui", "main_window.py")
_I18N_PY = os.path.join(
    _REPO_ROOT, "modules", "RBFtools", "scripts", "RBFtools",
    "ui", "i18n.py")
_BASE_PY = os.path.join(
    _REPO_ROOT, "modules", "RBFtools", "scripts", "RBFtools",
    "ui", "widgets", "_ordered_list_editor_base.py")
_INT_LIST_PY = os.path.join(
    _REPO_ROOT, "modules", "RBFtools", "scripts", "RBFtools",
    "ui", "widgets", "ordered_int_list_editor.py")


def _read(p):
    with open(p, "r", encoding="utf-8") as fh:
        return fh.read()


# ----------------------------------------------------------------------
# PERMANENT GUARD T_DRIVER_ROTATE_ORDER_SYNC
# ----------------------------------------------------------------------


class T_DRIVER_ROTATE_ORDER_SYNC(unittest.TestCase):
    """PERMANENT GUARD — DO NOT REMOVE.

    Driver tabs are the single source of truth for the rotate-
    order list. The 5-file refactor must stay interlocked: any
    one piece reverting opens the door to mismatched scenes that
    silently mis-encode the C++ read."""

    @classmethod
    def setUpClass(cls):
        cls._widget = _read(_NEW_WIDGET_PY)
        cls._rbf = _read(_RBF_SECTION_PY)
        cls._ctrl = _read(_CTRL_PY)
        cls._mw = _read(_MAIN_WINDOW_PY)
        cls._i18n = _read(_I18N_PY)
        cls._base = _read(_BASE_PY)
        cls._int_list = _read(_INT_LIST_PY)

    def test_PERMANENT_a_widget_has_no_add_remove_buttons(self):
        # The whole point of the refactor — driver tabs own row
        # count, the user MUST NOT have a +/- / up / down button.
        for forbidden in (
                "list_editor_add",
                "list_editor_remove",
                "list_editor_move_up",
                "list_editor_move_down"):
            self.assertNotIn(
                forbidden, self._widget,
                "DriverRotateOrderEditor MUST NOT reference "
                "{!r} — driver tabs are the only authority on "
                "row count + order.".format(forbidden))
        # Defensive double-check on the canonical button glyphs
        # (catches future code that hard-codes them).
        for glyph in (' "+"', ' "-"', " '+'", " '-'"):
            self.assertNotIn(
                glyph, self._widget,
                "DriverRotateOrderEditor MUST NOT add literal "
                "+/- button glyphs — row management is owned "
                "by the driver-source tabs.")

    def test_PERMANENT_b_widget_required_public_api(self):
        for sym in (
                "def set_driver_sources(self, names):",
                "def set_values(self, values):",
                "def get_values(self):",
                "def retranslate(self):",
                "listChanged = QtCore.Signal(list)"):
            self.assertIn(
                sym, self._widget,
                "DriverRotateOrderEditor missing public API "
                "member {!r}".format(sym))

    def test_PERMANENT_c_rbf_section_uses_new_widget(self):
        self.assertIn(
            "from RBFtools.ui.widgets.driver_rotate_order_editor",
            self._rbf,
            "rbf_section MUST import DriverRotateOrderEditor.")
        self.assertIn(
            "self._rotate_order_editor = DriverRotateOrderEditor()",
            self._rbf,
            "rbf_section MUST instantiate DriverRotateOrderEditor "
            "for the rotate-order slot.")
        # The legacy editor MUST no longer be imported here (the
        # class survives in widgets/ but rbf_section is the only
        # source-code consumer).
        self.assertNotIn(
            "from RBFtools.ui.widgets.ordered_enum_list_editor",
            self._rbf,
            "rbf_section MUST NOT import OrderedEnumListEditor "
            "after the refactor — that import would resurrect "
            "the unused dependency.")

    def test_PERMANENT_d_rbf_section_public_entry_point(self):
        self.assertIn(
            "def set_driver_sources_for_rotate_order(self, names):",
            self._rbf,
            "rbf_section MUST expose "
            "set_driver_sources_for_rotate_order — the slot is "
            "the only narrow path main_window uses to push the "
            "live driver-name list into the editor.")

    def test_PERMANENT_e_controller_resync_helper(self):
        # M_P0_ENCODING_OUTPUT_GLITCH (2026-04-30) updated this guard:
        # the original M_ROTORDER_UI_REFACTOR contract called
        # core.write_driver_rotate_orders to truncate / pad the
        # multi, but that path delegates to set_node_multi_attr
        # whose clear-then-write contract calls removeMultiInstance
        # per index — which TEARS DOWN the live driver.rotateOrder
        # connection that M_ENC_AUTOPIPE established. The Path C
        # fix routes self-heal through the canonical
        # auto_resolve_generic_rotate_orders helper instead, which
        # uses connectAttr force=True per source so the live
        # connection survives (or gets re-established cleanly).
        self.assertIn(
            "def _resync_rotate_order_length(self):",
            self._ctrl,
            "controller MUST expose _resync_rotate_order_length "
            "self-heal helper.")
        body = self._ctrl.split(
            "def _resync_rotate_order_length(self):"
        )[1].split("\n    def ")[0]
        self.assertIn(
            "core.auto_resolve_generic_rotate_orders(", body,
            "Helper MUST route through "
            "core.auto_resolve_generic_rotate_orders (Path C fix) — "
            "the canonical M_ENC_AUTOPIPE path that uses "
            "connectAttr force=True per source so the live "
            "driver.rotateOrder connection is preserved.")
        # Read inputEncoding via cmds (controller-layer is allowed
        # narrow getAttr access for routing decisions).
        self.assertIn(
            'cmds.getAttr(shape + ".inputEncoding")', body,
            "Helper MUST read the current inputEncoding so the "
            "auto-resolve walk picks the right branch (clear-on-"
            "bypass for Raw/Quat vs per-source connect for "
            "BendRoll/ExpMap/SwingTwist).")
        # Defence-in-depth: write_driver_rotate_orders MUST NOT
        # appear in the helper body — it is the regression-source
        # path. The canonical core helper still uses it internally
        # for the Raw/Quat clear branch, but the controller layer
        # MUST NOT touch it directly.
        self.assertNotIn(
            "core.write_driver_rotate_orders(", body,
            "Helper MUST NOT call core.write_driver_rotate_orders "
            "directly — that path's clear-then-write semantics is "
            "the M_P0_ENCODING_OUTPUT_GLITCH bug shape.")

    def test_PERMANENT_f_main_window_wires_sync(self):
        # The single ≤3-LoC main_window edit lives inside
        # _reload_driver_sources. The body MUST call BOTH the
        # self-heal AND the per-row sync push.
        body = self._mw.split(
            "def _reload_driver_sources(self):"
        )[1].split("\n    def ")[0]
        self.assertIn(
            "self._ctrl._resync_rotate_order_length()", body,
            "_reload_driver_sources MUST call the controller "
            "self-heal helper so the persisted multi tracks the "
            "live driver-tab count.")
        self.assertIn(
            "self._rbf_section.set_driver_sources_for_rotate_order(",
            body,
            "_reload_driver_sources MUST push the driver-name "
            "list into rbf_section so the editor rebuilds rows "
            "to match.")
        self.assertIn(
            "[s.node for s in sources]", body,
            "Pushed list MUST be the driver.node strings (joint "
            "names) — the row label template uses {name} for "
            "user-facing identification.")

    def test_PERMANENT_g_row_label_template_en_zh_parity(self):
        # Both languages MUST carry the row-label template.
        self.assertGreaterEqual(
            self._i18n.count('"driver_rotate_order_row_label":'),
            2,
            "i18n.py MUST carry driver_rotate_order_row_label "
            "in BOTH _EN and _ZH dicts (count >= 2).")
        # Must use the {idx} + {name} placeholder shape so the
        # widget can .format(idx=i+1, name=driver_name).
        self.assertIn("{idx}", self._i18n)
        self.assertIn("{name}", self._i18n)

    def test_PERMANENT_h_legacy_widgets_untouched(self):
        # _OrderedListEditorBase + OrderedIntListEditor MUST stay
        # bit-for-bit compatible with their pre-refactor surface
        # (OrderedIntListEditor still backs the quat-group-start
        # editor in rbf_section.py:196 with the full +/-/up/down
        # button row). Button instance-attr names are
        # ``_btn_add`` / ``_btn_remove`` / ``_btn_up`` / ``_btn_down``
        # per the existing source.
        for sym in ("class _OrderedListEditorBase",
                    "_btn_add", "_btn_remove",
                    "_btn_up", "_btn_down"):
            self.assertIn(
                sym, self._base,
                "_ordered_list_editor_base MUST still contain "
                "{} — the shared base class is preserved for "
                "OrderedIntListEditor.".format(sym))
        self.assertIn(
            "class OrderedIntListEditor(_OrderedListEditorBase)",
            self._int_list,
            "OrderedIntListEditor MUST still inherit from the "
            "shared base — quat-group-start editor depends on it.")
        # rbf_section MUST still use OrderedIntListEditor for the
        # quat-group editor (the refactor only swapped the rotate-
        # order one).
        self.assertIn(
            "self._quat_group_editor = OrderedIntListEditor(",
            self._rbf,
            "rbf_section MUST keep OrderedIntListEditor for the "
            "quat-group-start editor — the refactor is scoped "
            "to the rotate-order editor only.")

    def test_PERMANENT_i_widget_uses_constants_labels(self):
        # The new widget MUST source the 6 enum labels from the
        # canonical constants module so they stay in lock-step
        # with the C++ eAttr.addField order (xyz / yzx / zxy /
        # xzy / yxz / zyx).
        self.assertIn(
            "DRIVER_INPUT_ROTATE_ORDER_LABELS", self._widget,
            "DriverRotateOrderEditor MUST consume "
            "DRIVER_INPUT_ROTATE_ORDER_LABELS from constants.py "
            "to stay aligned with the C++ enum.")


# ----------------------------------------------------------------------
# Mock E2E — runtime widget behaviour (Bug-fix scenarios a-g).
# ----------------------------------------------------------------------


class T_DRIVER_ROTATE_ORDER_WIDGET_API(unittest.TestCase):
    """Structural-API guard for ``DriverRotateOrderEditor``. The
    widget cannot be instantiated under either the pure-Python
    PySide minimal shim (QComboBox returns MagicMock for .count())
    OR a headless mayapy run (no QApplication). We assert the class
    surface here; behavioural correctness is enforced by

      * Source-scan PERMANENT (no add/remove/up/down references) —
        T_DRIVER_ROTATE_ORDER_SYNC.test_PERMANENT_a / _b
      * Controller helper truncate/pad/idempotence —
        TestM_ROTORDER_UI_REFACTOR_ControllerBehavior below.

    Adding a runtime widget instantiation test would require either
    a QApplication fixture (out of scope for the unit lane) or a
    full Maya UI session (live TD verification path)."""

    @classmethod
    def setUpClass(cls):
        from RBFtools.ui.widgets.driver_rotate_order_editor import (
            DriverRotateOrderEditor)
        cls._cls = DriverRotateOrderEditor

    def test_signal_listChanged_present(self):
        self.assertTrue(
            hasattr(self._cls, "listChanged"),
            "DriverRotateOrderEditor MUST declare listChanged.")

    def test_required_methods_callable(self):
        for name in (
                "set_driver_sources",
                "set_values",
                "get_values",
                "set_label",
                "set_empty_hint",
                "retranslate",
                "row_count",
                "driver_names",
                "_format_row_label",
                "_refresh_empty_hint"):
            self.assertTrue(
                callable(getattr(self._cls, name, None)),
                "DriverRotateOrderEditor missing callable {!r}".format(
                    name))


# ----------------------------------------------------------------------
# Mock E2E — controller helper (the data-side fix). The widget side
# is verified by source-scan + structural API above (instantiation
# requires real Qt + QApplication).
# ----------------------------------------------------------------------


@unittest.skipIf(conftest._REAL_MAYA,
    "mock-dependent (controller helper + cmds stubs)")
class TestM_ROTORDER_UI_REFACTOR_ControllerBehavior(unittest.TestCase):

    # M_P0_ENCODING_OUTPUT_GLITCH (2026-04-30): the runtime tests
    # below were updated alongside the Path C contract change.
    # The legacy truncate / pad / write_driver_rotate_orders
    # assertions (which the original M_ROTORDER_UI_REFACTOR
    # introduced) are now covered by the dedicated
    # T_M_P0_ENCODING_OUTPUT_GLITCH suite — those assertions
    # locked the behaviour that was the root cause of the user-
    # reported "Raw 正常 + 其他编码乱跳" repro, so they cannot
    # stay green. The replacements here lock the new contract:
    # the helper must route through auto_resolve_generic_rotate_
    # orders with the correct encoding.

    def _make_ctrl(self, encoding=0):
        from RBFtools.controller import MainController
        ctrl = MainController.__new__(MainController)
        ctrl._current_node = "RBF1"
        ctrl._encoding = int(encoding)
        return ctrl

    def _patch_resync_env(self, ctrl):
        """Yield a context where get_shape resolves and
        cmds.getAttr(shape+".inputEncoding") returns
        ctrl._encoding."""
        from RBFtools import core
        from RBFtools import controller as ctrl_mod
        cmds_stub = mock.MagicMock()

        def _get_attr(plug, *args, **kwargs):
            if plug.endswith(".inputEncoding"):
                return ctrl._encoding
            return 0

        cmds_stub.getAttr.side_effect = _get_attr
        cmds_stub.warning = mock.MagicMock()
        return mock.patch.multiple(
            ctrl_mod,
            cmds=cmds_stub,
            core=mock.MagicMock(
                get_shape=mock.MagicMock(return_value="RBF1Shape"),
                auto_resolve_generic_rotate_orders=mock.MagicMock(),
            ),
        )

    def test_resync_routes_through_auto_resolve(self):
        # Path C contract: helper MUST call
        # core.auto_resolve_generic_rotate_orders with the live
        # inputEncoding read from the shape, NOT
        # write_driver_rotate_orders.
        from RBFtools.controller import MainController
        from RBFtools import controller as ctrl_mod
        ctrl = self._make_ctrl(encoding=3)  # ExpMap
        with self._patch_resync_env(ctrl):
            result = MainController._resync_rotate_order_length(ctrl)
            ctrl_mod.core.auto_resolve_generic_rotate_orders \
                .assert_called_once_with("RBF1", 3)
        self.assertTrue(result,
            "Helper MUST return True after a successful auto-"
            "resolve invocation (test hook).")

    def test_resync_passes_raw_encoding_for_clear_branch(self):
        # Raw / Quat -> auto_resolve runs the clear-on-bypass
        # branch internally. Helper just forwards the encoding.
        from RBFtools.controller import MainController
        from RBFtools import controller as ctrl_mod
        ctrl = self._make_ctrl(encoding=0)  # Raw
        with self._patch_resync_env(ctrl):
            MainController._resync_rotate_order_length(ctrl)
            ctrl_mod.core.auto_resolve_generic_rotate_orders \
                .assert_called_once_with("RBF1", 0)

    def test_resync_passes_swingtwist_encoding(self):
        from RBFtools.controller import MainController
        from RBFtools import controller as ctrl_mod
        ctrl = self._make_ctrl(encoding=4)  # SwingTwist
        with self._patch_resync_env(ctrl):
            MainController._resync_rotate_order_length(ctrl)
            ctrl_mod.core.auto_resolve_generic_rotate_orders \
                .assert_called_once_with("RBF1", 4)

    def test_resync_does_not_call_write_driver_rotate_orders(self):
        # Defence-in-depth: the regression-source path MUST NOT be
        # invoked from within the helper. The clear-then-write
        # contract of write_driver_rotate_orders -> set_node_multi
        # _attr is precisely what tore down the live connections.
        from RBFtools.controller import MainController
        from RBFtools import controller as ctrl_mod
        ctrl = self._make_ctrl(encoding=3)
        with self._patch_resync_env(ctrl):
            MainController._resync_rotate_order_length(ctrl)
            ctrl_mod.core.write_driver_rotate_orders \
                .assert_not_called()

    def test_resync_no_op_without_node(self):
        # Early return preserved on no current_node (or shape
        # unresolved).
        from RBFtools import core
        from RBFtools.controller import MainController
        ctrl = MainController.__new__(MainController)
        ctrl._current_node = None
        with mock.patch.object(
                core, "auto_resolve_generic_rotate_orders") as h:
            result = MainController._resync_rotate_order_length(ctrl)
        self.assertFalse(result)
        h.assert_not_called()

    def test_resync_no_op_when_shape_unresolved(self):
        from RBFtools import core
        from RBFtools.controller import MainController
        ctrl = MainController.__new__(MainController)
        ctrl._current_node = "missing_node"
        with mock.patch.object(
                core, "get_shape", return_value=""):
            with mock.patch.object(
                    core, "auto_resolve_generic_rotate_orders") as h:
                result = MainController._resync_rotate_order_length(
                    ctrl)
        self.assertFalse(result)
        h.assert_not_called()

    # ------------------------------------------------------------------
    # rbf_section visibility gating (Raw/Quat hide; BendRoll/ExpMap/
    # SwingTwist show) is owned by _update_encoding_visibility and
    # already locked by T_INPUT_ENCODING_AUTOPIPE
    # (test_PERMANENT_f_visibility_quat_hidden) — no need to
    # re-assert here.
    # ------------------------------------------------------------------


if __name__ == "__main__":
    unittest.main()
