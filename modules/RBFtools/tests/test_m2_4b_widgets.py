"""M2.4b — Ordered list editor widgets + visibility wiring.

T1  _OrderedListEditorBase public API surface
T2  OrderedIntListEditor structural API
T3  OrderedEnumListEditor structural API
T4  Signal contract: listChanged signal exists
T5  Visibility helper: _update_encoding_visibility behaviour
T6  load() syncs visibility for v5 rig opening with non-Raw encoding
T7  i18n: M2.4b keys present in EN + CN tables
T8  DRIVER_INPUT_ROTATE_ORDER_LABELS order matches Maya enum
T9  set_values does NOT emit listChanged (controller round-trip guard)
"""

from __future__ import absolute_import

# Install Maya / PySide mocks BEFORE importing widget modules.
import conftest  # noqa: F401

import unittest
from unittest import mock


# ----------------------------------------------------------------------
# T1 — Base class API surface
# ----------------------------------------------------------------------


class T1_BaseClassAPI(unittest.TestCase):
    """The base class declares the contract every concrete editor must
    fulfil. Asserting class-level callables here catches a refactor that
    accidentally drops a public method."""

    def test_set_values_callable(self):
        from RBFtools.ui.widgets._ordered_list_editor_base import (
            _OrderedListEditorBase,
        )
        self.assertTrue(callable(getattr(_OrderedListEditorBase,
                                         "set_values", None)))

    def test_get_values_callable(self):
        from RBFtools.ui.widgets._ordered_list_editor_base import (
            _OrderedListEditorBase,
        )
        self.assertTrue(callable(getattr(_OrderedListEditorBase,
                                         "get_values", None)))

    def test_clear_callable(self):
        from RBFtools.ui.widgets._ordered_list_editor_base import (
            _OrderedListEditorBase,
        )
        self.assertTrue(callable(getattr(_OrderedListEditorBase,
                                         "clear", None)))

    def test_set_label_callable(self):
        from RBFtools.ui.widgets._ordered_list_editor_base import (
            _OrderedListEditorBase,
        )
        self.assertTrue(callable(getattr(_OrderedListEditorBase,
                                         "set_label", None)))

    def test_set_empty_hint_callable(self):
        from RBFtools.ui.widgets._ordered_list_editor_base import (
            _OrderedListEditorBase,
        )
        self.assertTrue(callable(getattr(_OrderedListEditorBase,
                                         "set_empty_hint", None)))

    def test_retranslate_callable(self):
        from RBFtools.ui.widgets._ordered_list_editor_base import (
            _OrderedListEditorBase,
        )
        self.assertTrue(callable(getattr(_OrderedListEditorBase,
                                         "retranslate", None)))


# ----------------------------------------------------------------------
# T2 — OrderedIntListEditor
# ----------------------------------------------------------------------


class T2_IntEditorAPI(unittest.TestCase):

    def test_class_exists(self):
        from RBFtools.ui.widgets.ordered_int_list_editor import (
            OrderedIntListEditor,
        )
        self.assertTrue(callable(OrderedIntListEditor))

    def test_create_row_widget_overridden(self):
        from RBFtools.ui.widgets.ordered_int_list_editor import (
            OrderedIntListEditor,
        )
        from RBFtools.ui.widgets._ordered_list_editor_base import (
            _OrderedListEditorBase,
        )
        # The subclass must define its own _create_row_widget;
        # comparing the function objects ensures it's not the
        # base class's NotImplementedError stub.
        self.assertNotEqual(
            OrderedIntListEditor._create_row_widget,
            _OrderedListEditorBase._create_row_widget,
        )

    def test_read_row_value_overridden(self):
        from RBFtools.ui.widgets.ordered_int_list_editor import (
            OrderedIntListEditor,
        )
        from RBFtools.ui.widgets._ordered_list_editor_base import (
            _OrderedListEditorBase,
        )
        self.assertNotEqual(
            OrderedIntListEditor._read_row_value,
            _OrderedListEditorBase._read_row_value,
        )


# ----------------------------------------------------------------------
# T3 — OrderedEnumListEditor
# ----------------------------------------------------------------------


class T3_EnumEditorAPI(unittest.TestCase):

    def test_class_exists(self):
        from RBFtools.ui.widgets.ordered_enum_list_editor import (
            OrderedEnumListEditor,
        )
        self.assertTrue(callable(OrderedEnumListEditor))

    def test_subclass_relationship(self):
        from RBFtools.ui.widgets.ordered_enum_list_editor import (
            OrderedEnumListEditor,
        )
        from RBFtools.ui.widgets._ordered_list_editor_base import (
            _OrderedListEditorBase,
        )
        self.assertTrue(issubclass(OrderedEnumListEditor,
                                   _OrderedListEditorBase))

    def test_create_row_widget_overridden(self):
        from RBFtools.ui.widgets.ordered_enum_list_editor import (
            OrderedEnumListEditor,
        )
        from RBFtools.ui.widgets._ordered_list_editor_base import (
            _OrderedListEditorBase,
        )
        self.assertNotEqual(
            OrderedEnumListEditor._create_row_widget,
            _OrderedListEditorBase._create_row_widget,
        )


# ----------------------------------------------------------------------
# T4 — listChanged signal exists on each class
# ----------------------------------------------------------------------


class T4_SignalContract(unittest.TestCase):

    def test_base_has_listchanged(self):
        from RBFtools.ui.widgets._ordered_list_editor_base import (
            _OrderedListEditorBase,
        )
        self.assertTrue(hasattr(_OrderedListEditorBase, "listChanged"))

    def test_int_editor_inherits_listchanged(self):
        from RBFtools.ui.widgets.ordered_int_list_editor import (
            OrderedIntListEditor,
        )
        self.assertTrue(hasattr(OrderedIntListEditor, "listChanged"))

    def test_enum_editor_inherits_listchanged(self):
        from RBFtools.ui.widgets.ordered_enum_list_editor import (
            OrderedEnumListEditor,
        )
        self.assertTrue(hasattr(OrderedEnumListEditor, "listChanged"))


# ----------------------------------------------------------------------
# T5 — Visibility helper
# ----------------------------------------------------------------------


class T5_VisibilityHelper(unittest.TestCase):
    """`_update_encoding_visibility(idx)` is the single source of truth
    for the rotateOrder-editor show/hide. Callable from both
    `_on_input_encoding` (user-driven) and `load()` (controller-driven)."""

    def test_update_encoding_visibility_callable(self):
        from RBFtools.ui.widgets.rbf_section import RBFSection
        self.assertTrue(callable(getattr(
            RBFSection, "_update_encoding_visibility", None)))

    def test_on_input_encoding_callable(self):
        from RBFtools.ui.widgets.rbf_section import RBFSection
        self.assertTrue(callable(getattr(
            RBFSection, "_on_input_encoding", None)))


# ----------------------------------------------------------------------
# T6 — load() integration
# ----------------------------------------------------------------------


class T6_LoadSyncsVisibility(unittest.TestCase):
    """The class-level inspection: load() must contain the
    `_update_encoding_visibility` call. We check via source-text
    inspection (instantiation needs a real QApplication)."""

    def test_load_calls_update_encoding_visibility(self):
        import pathlib
        path = pathlib.Path(__file__).resolve().parent.parent
        rbf_section = (path / "scripts" / "RBFtools" / "ui" / "widgets"
                       / "rbf_section.py")
        text = rbf_section.read_text(encoding="utf-8")
        # The load() method must invoke the visibility helper after
        # set_values() so v5 rigs with non-Raw encoding open with the
        # editor visible.
        self.assertIn("_update_encoding_visibility(ienc)", text,
            "load() does not call _update_encoding_visibility(ienc) — "
            "addendum §M2.4b Q2 contract violation")


# ----------------------------------------------------------------------
# T7 — i18n key coverage
# ----------------------------------------------------------------------


class T7_i18nKeysM2_4b(unittest.TestCase):

    M24B_KEYS = [
        "driver_rotate_order_label",
        "rotate_order_empty_hint",
        "quat_group_start_label",
        "quat_group_empty_hint",
        "quat_group_start_value_tip",
        "list_editor_add",
        "list_editor_remove",
        "list_editor_move_up",
        "list_editor_move_down",
        "list_editor_add_tip",
        "list_editor_remove_tip",
        "list_editor_move_up_tip",
        "list_editor_move_down_tip",
    ]

    def test_keys_present_in_both_tables(self):
        import pathlib
        path = pathlib.Path(__file__).resolve().parent.parent
        i18n_path = (path / "scripts" / "RBFtools" / "ui" / "i18n.py")
        text = i18n_path.read_text(encoding="utf-8")
        missing = []
        for key in self.M24B_KEYS:
            needle = '"{}":'.format(key)
            count = text.count(needle)
            if count < 2:
                missing.append("{} (count={})".format(key, count))
        self.assertEqual(missing, [],
            "M2.4b i18n keys missing from EN or CN table:\n  "
            + "\n  ".join(missing))


# ----------------------------------------------------------------------
# T8 — Maya rotateOrder enum order
# ----------------------------------------------------------------------


class T8_RotateOrderLabels(unittest.TestCase):
    """The label list MUST match Maya's native rotateOrder enum:
        xyz=0, yzx=1, zxy=2, xzy=3, yxz=4, zyx=5
    Mismatch breaks user expectations (driver.rotateOrder plug → node
    .driverInputRotateOrder[k] would have wrong index)."""

    def test_length_6(self):
        from RBFtools.constants import DRIVER_INPUT_ROTATE_ORDER_LABELS
        self.assertEqual(len(DRIVER_INPUT_ROTATE_ORDER_LABELS), 6)

    def test_order(self):
        from RBFtools.constants import DRIVER_INPUT_ROTATE_ORDER_LABELS
        expected = ["xyz", "yzx", "zxy", "xzy", "yxz", "zyx"]
        self.assertEqual(DRIVER_INPUT_ROTATE_ORDER_LABELS, expected)


# ----------------------------------------------------------------------
# T9 — set_values does NOT emit listChanged
# ----------------------------------------------------------------------


class T9_SetValuesNoEmit(unittest.TestCase):
    """Programmatic set_values must NOT emit listChanged. The controller
    is the originator on load → re-emitting would create a feedback
    loop (controller writes node → reload → set_values → emit →
    controller re-writes node → ...). Only user interaction emits."""

    def test_set_values_uses_suspend_emit_guard(self):
        # Source-text contract: set_values must enter and exit the
        # _suspend_emit guard. Instantiation requires a real
        # QApplication; the guard's CONTRACT (not its runtime behaviour)
        # is what we test here. A future refactor that drops the guard
        # would be caught.
        import pathlib
        path = pathlib.Path(__file__).resolve().parent.parent
        base_path = (path / "scripts" / "RBFtools" / "ui" / "widgets"
                     / "_ordered_list_editor_base.py")
        text = base_path.read_text(encoding="utf-8")
        # Find the set_values method body (between def set_values and
        # the next def at top level).
        marker = "def set_values(self, values):"
        idx = text.find(marker)
        self.assertGreater(idx, 0,
                           "set_values method missing on base class")
        # The next 'def ' AFTER set_values marks end of the method.
        end = text.find("\n    def ", idx + len(marker))
        body = text[idx:end]
        self.assertIn("self._suspend_emit = True", body,
            "set_values does not enter the _suspend_emit guard "
            "(addendum §M2.4b refinement: contract violation)")
        self.assertIn("self._suspend_emit = False", body,
            "set_values does not exit the _suspend_emit guard")
        # Crucially, set_values must NOT explicitly call listChanged.emit.
        self.assertNotIn("self.listChanged.emit", body,
            "set_values explicitly emits listChanged — addendum §M2.4b "
            "contract violation (would round-trip into controller)")

    def test_on_any_row_changed_respects_suspend(self):
        # The collector must early-return when _suspend_emit is True.
        import pathlib
        path = pathlib.Path(__file__).resolve().parent.parent
        base_path = (path / "scripts" / "RBFtools" / "ui" / "widgets"
                     / "_ordered_list_editor_base.py")
        text = base_path.read_text(encoding="utf-8")
        marker = "def _on_any_row_changed(self):"
        idx = text.find(marker)
        self.assertGreater(idx, 0,
                           "_on_any_row_changed missing on base class")
        end = text.find("\n    def ", idx + len(marker))
        body = text[idx:end]
        self.assertIn("if self._suspend_emit", body,
            "_on_any_row_changed does not gate on _suspend_emit — "
            "set_values emits would still leak through")


if __name__ == "__main__":
    unittest.main()
