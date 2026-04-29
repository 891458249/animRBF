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
        self.assertIn(
            "def _resync_rotate_order_length(self):",
            self._ctrl,
            "controller MUST expose _resync_rotate_order_length "
            "self-heal helper.")
        body = self._ctrl.split(
            "def _resync_rotate_order_length(self):"
        )[1].split("\n    def ")[0]
        # Must reuse the existing read / write helpers — never
        # touch shape attrs directly from the controller layer.
        self.assertIn(
            "core.read_driver_info_multi(", body,
            "Helper MUST resolve target driver count via "
            "read_driver_info_multi (not ad-hoc cmds.getAttr).")
        self.assertIn(
            "core.read_driver_rotate_orders(", body,
            "Helper MUST read existing array via the canonical "
            "core reader.")
        self.assertIn(
            "core.write_driver_rotate_orders(", body,
            "Helper MUST write back via the canonical core writer "
            "(M_REBUILD_REFACTOR clear-then-write semantics).")
        # Idempotence guard: must short-circuit when already aligned.
        self.assertIn(
            "return False", body,
            "Helper MUST return False (idempotent no-op) when "
            "the persisted array already matches the driver count.")

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

    def _make_ctrl(self, drv_count, existing_orders):
        from RBFtools.controller import MainController
        ctrl = MainController.__new__(MainController)
        ctrl._current_node = "RBF1"
        # Stub readers / writer.
        from RBFtools import core
        from RBFtools.core import DriverSource
        sources = [
            DriverSource(node="d{}".format(i), attrs=("rx",))
            for i in range(drv_count)
        ]
        ctrl._sources = sources
        ctrl._existing = list(existing_orders)
        ctrl._writes = []
        return ctrl

    def test_resync_idempotent_when_already_aligned(self):
        # Scenario (f): aligned -> no write-back.
        from RBFtools import core
        from RBFtools.controller import MainController
        ctrl = self._make_ctrl(drv_count=3,
                                existing_orders=[0, 1, 2])
        with mock.patch.object(
                core, "read_driver_info_multi",
                return_value=ctrl._sources):
            with mock.patch.object(
                    core, "read_driver_rotate_orders",
                    return_value=list(ctrl._existing)):
                with mock.patch.object(
                        core, "write_driver_rotate_orders") as w:
                    result = MainController._resync_rotate_order_length(
                        ctrl)
        self.assertFalse(result, "Aligned state must short-circuit.")
        w.assert_not_called()

    def test_resync_truncates_when_array_too_long(self):
        # Scenario: 2 drivers but persisted [0, 1, 2, 3] -> truncate.
        from RBFtools import core
        from RBFtools.controller import MainController
        ctrl = self._make_ctrl(drv_count=2,
                                existing_orders=[0, 1, 2, 3])
        with mock.patch.object(
                core, "read_driver_info_multi",
                return_value=ctrl._sources):
            with mock.patch.object(
                    core, "read_driver_rotate_orders",
                    return_value=list(ctrl._existing)):
                with mock.patch.object(
                        core, "write_driver_rotate_orders") as w:
                    result = MainController._resync_rotate_order_length(
                        ctrl)
        self.assertTrue(result)
        w.assert_called_once_with("RBF1", [0, 1])

    def test_resync_pads_when_array_too_short(self):
        # Scenario: 4 drivers but persisted [5, 3] -> pad with xyz=0.
        from RBFtools import core
        from RBFtools.controller import MainController
        ctrl = self._make_ctrl(drv_count=4,
                                existing_orders=[5, 3])
        with mock.patch.object(
                core, "read_driver_info_multi",
                return_value=ctrl._sources):
            with mock.patch.object(
                    core, "read_driver_rotate_orders",
                    return_value=list(ctrl._existing)):
                with mock.patch.object(
                        core, "write_driver_rotate_orders") as w:
                    result = MainController._resync_rotate_order_length(
                        ctrl)
        self.assertTrue(result)
        w.assert_called_once_with("RBF1", [5, 3, 0, 0])

    def test_resync_clears_when_no_drivers(self):
        # 0 drivers + persisted entries -> write back empty list.
        from RBFtools import core
        from RBFtools.controller import MainController
        ctrl = self._make_ctrl(drv_count=0,
                                existing_orders=[2, 5])
        with mock.patch.object(
                core, "read_driver_info_multi",
                return_value=[]):
            with mock.patch.object(
                    core, "read_driver_rotate_orders",
                    return_value=list(ctrl._existing)):
                with mock.patch.object(
                        core, "write_driver_rotate_orders") as w:
                    result = MainController._resync_rotate_order_length(
                        ctrl)
        self.assertTrue(result)
        w.assert_called_once_with("RBF1", [])

    def test_resync_double_call_idempotent(self):
        # Scenario (f) reinforced: first call writes, second call
        # is a no-op.
        from RBFtools import core
        from RBFtools.controller import MainController
        ctrl = self._make_ctrl(drv_count=2,
                                existing_orders=[0, 1, 2])
        # First call truncates.
        first_state = list(ctrl._existing)

        def _read_orders(*_args, **_kw):
            return list(first_state)

        write_log = []

        def _write(_node, values):
            # After write, "persisted" state matches what was written.
            first_state[:] = list(values)
            write_log.append(list(values))

        with mock.patch.object(
                core, "read_driver_info_multi",
                return_value=ctrl._sources):
            with mock.patch.object(
                    core, "read_driver_rotate_orders",
                    side_effect=_read_orders):
                with mock.patch.object(
                        core, "write_driver_rotate_orders",
                        side_effect=_write):
                    r1 = MainController._resync_rotate_order_length(
                        ctrl)
                    r2 = MainController._resync_rotate_order_length(
                        ctrl)
        self.assertTrue(r1, "First call should truncate + write.")
        self.assertFalse(r2, "Second call MUST be idempotent.")
        self.assertEqual(write_log, [[0, 1]],
            "Only the first call writes; second is no-op.")

    def test_resync_no_op_without_node(self):
        from RBFtools import core
        from RBFtools.controller import MainController
        ctrl = MainController.__new__(MainController)
        ctrl._current_node = None
        with mock.patch.object(
                core, "write_driver_rotate_orders") as w:
            result = MainController._resync_rotate_order_length(ctrl)
        self.assertFalse(result)
        w.assert_not_called()

    # ------------------------------------------------------------------
    # rbf_section visibility gating (Raw/Quat hide; BendRoll/ExpMap/
    # SwingTwist show) is owned by _update_encoding_visibility and
    # already locked by T_INPUT_ENCODING_AUTOPIPE
    # (test_PERMANENT_f_visibility_quat_hidden) — no need to
    # re-assert here.
    # ------------------------------------------------------------------


if __name__ == "__main__":
    unittest.main()
