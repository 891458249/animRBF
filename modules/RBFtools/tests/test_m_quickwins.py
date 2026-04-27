"""M_QUICKWINS - Item 2 (i18n retranslate coverage) + Item 3
(default RBF type on create_node) + Item 4a (Limit label).

Three small UX correctnesses landing together to clear the
2026-04-27 user reports without delaying the v5.0 final path.

* **Item 2** - language switch must repaint every persistent
  widget in the inspector. Pre-M_QUICKWINS the
  `_retranslate_all` path called retranslate on 5 widgets;
  the M_B24b1 `DriverSourceListEditor`, M_B24b1
  `OutputEncodingCombo`, M3.4 `LiveEditWidget`, and M3.5
  `ProfileWidget` were never repainted, leaving stale
  English / Chinese surfaces after a language toggle.

* **Item 3** - `core.create_node` now sets `.type = 1` (RBF)
  immediately after `cmds.createNode`, so the GeneralSection
  combo defaults to RBF without the TD having to switch
  every time. The C++ schema default of 0 (Vector-Angle) is
  unchanged - only the Python orchestrator's behaviour
  shifted.

* **Item 4a** - `clamp_enabled` / `clamp_inflation` i18n
  labels rephrased to the TD-facing "Limit" terminology that
  matches the user's reference UX (the underlying
  clampEnabled / clampInflation schema is untouched).
"""

from __future__ import absolute_import

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


def _read(path):
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read()


# ----------------------------------------------------------------------
# Item 3 - create_node defaults to RBF (type=1)
# ----------------------------------------------------------------------


class TestM_QUICKWINS_Item3_DefaultRBFType(unittest.TestCase):
    """create_node() must `setAttr "shape.type" 1` after the
    cmds.createNode call so newly-created nodes land in RBF mode
    (not the C++ default Vector-Angle / type=0)."""

    def test_create_node_body_sets_type_to_rbf(self):
        body = _read(_CORE_PY)
        # Locate the create_node function body.
        m = re.search(
            r"^def\s+create_node\b.*?(?=^def\s|^class\s|\Z)",
            body, re.M | re.S)
        self.assertIsNotNone(m,
            "core.create_node body not found")
        fn = m.group(0)
        self.assertIn("setAttr", fn,
            "create_node must call setAttr on the new shape "
            "(M_QUICKWINS Item 3 default RBF)")
        self.assertIn(".type", fn,
            "create_node must target the .type attribute "
            "(M_QUICKWINS Item 3 default RBF)")
        # Look for the explicit "type, 1" pair.
        self.assertTrue(
            re.search(r"\.type[\"']?\s*,\s*1", fn),
            "create_node must set type=1 (RBF mode) - "
            "M_QUICKWINS Item 3")

    @unittest.skipIf(conftest._REAL_MAYA,
        "mock-dependent (mock.patch on cmds.*)")
    def test_create_node_setattr_called_with_type_1(self):
        """End-to-end: invoking core.create_node under a fully
        mocked cmds yields a setAttr(<shape>.type, 1) call."""
        from RBFtools import core
        import maya.cmds as cmds
        cmds.reset_mock()
        cmds.ls.return_value = []
        cmds.createNode.return_value = "RBFtoolsShape1"
        cmds.rename.return_value = "RBFnode1"
        with mock.patch("RBFtools.core.ensure_plugin"), \
             mock.patch("RBFtools.core.get_transform",
                        return_value="RBFtools1"), \
             mock.patch("RBFtools.core.get_shape",
                        return_value="RBFnode1Shape"), \
             mock.patch("RBFtools.core.undo_chunk"):
            core.create_node()
        type_calls = [
            c for c in cmds.setAttr.call_args_list
            if len(c[0]) >= 2 and c[0][0].endswith(".type")
            and c[0][1] == 1
        ]
        self.assertGreaterEqual(len(type_calls), 1,
            "create_node must call setAttr(<shape>.type, 1) - "
            "M_QUICKWINS Item 3")


# ----------------------------------------------------------------------
# Item 4a - Limit label
# ----------------------------------------------------------------------


class TestM_QUICKWINS_Item4a_LimitLabel(unittest.TestCase):
    """clamp_enabled / clamp_inflation i18n labels rephrased to the
    TD-facing 'Limit' terminology. The underlying clampEnabled /
    clampInflation Maya attributes remain unchanged - this is a
    pure surface rename."""

    def test_en_label_says_limit(self):
        from RBFtools.ui import i18n
        self.assertIn("Limit", i18n._EN["clamp_enabled"],
            "EN clamp_enabled label must use the Limit terminology "
            "(M_QUICKWINS Item 4a)")
        self.assertIn("Limit", i18n._EN["clamp_inflation"],
            "EN clamp_inflation label must use the Limit "
            "terminology (M_QUICKWINS Item 4a)")

    def test_zh_label_uses_xianzhi(self):
        from RBFtools.ui import i18n
        self.assertIn(u"限制",   # 限制
                      i18n._ZH["clamp_enabled"],
            "ZH clamp_enabled must use the 限制 terminology "
            "(M_QUICKWINS Item 4a)")
        self.assertIn(u"限制",
                      i18n._ZH["clamp_inflation"])


# ----------------------------------------------------------------------
# Item 2 - retranslate coverage on persistent widgets
# ----------------------------------------------------------------------


class TestM_QUICKWINS_Item2_RetranslatePresent(unittest.TestCase):
    """Source-scan: every persistent widget that uses tr() must
    expose a retranslate() method so the language-switch path can
    refresh it. Transient dialogs (confirm / import / prune) are
    rebuilt on each open and stay out of scope."""

    PERSISTENT_WIDGETS_REQUIRING_RETRANSLATE = [
        "driver_source_list_editor.py",
        "live_edit_widget.py",
        "output_encoding_combo.py",
        "profile_widget.py",
    ]

    def test_each_persistent_widget_defines_retranslate(self):
        widgets_dir = os.path.join(
            _REPO_ROOT, "modules", "RBFtools", "scripts",
            "RBFtools", "ui", "widgets")
        missing = []
        for w in self.PERSISTENT_WIDGETS_REQUIRING_RETRANSLATE:
            body = _read(os.path.join(widgets_dir, w))
            if "def retranslate" not in body:
                missing.append(w)
        self.assertEqual(missing, [],
            "Persistent widgets missing retranslate(): {} "
            "- M_QUICKWINS Item 2".format(missing))

    def test_main_window_calls_each_retranslate(self):
        main_window_src = _read(os.path.join(
            _REPO_ROOT, "modules", "RBFtools", "scripts",
            "RBFtools", "ui", "main_window.py"))
        # Each new persistent-widget retranslate must be invoked
        # from the _retranslate_all path. We check by attribute
        # name (set on RBFToolsWindow).
        for attr_call in [
                "_driver_source_list.retranslate",
                "_output_encoding_combo.retranslate"]:
            self.assertIn(attr_call, main_window_src,
                "main_window._retranslate_all must invoke {} "
                "(M_QUICKWINS Item 2)".format(attr_call))
        # Live-edit and profile widgets are walked via getattr in
        # the loop; check the loop attribute names are present.
        self.assertIn("_live_edit_widget", main_window_src)
        self.assertIn("_profile_widget", main_window_src)


@unittest.skipIf(conftest._REAL_MAYA,
    "mock-dependent (PySide signal stubs require mocked QtWidgets)")
class TestM_QUICKWINS_Item2_RetranslateLifecycle(unittest.TestCase):
    """Mock-pattern: the new retranslate methods do not raise and
    re-apply current-language strings idempotently."""

    def test_driver_source_list_editor_retranslate_runs(self):
        from RBFtools.ui.widgets.driver_source_list_editor import (
            DriverSourceListEditor)
        editor = DriverSourceListEditor.__new__(DriverSourceListEditor)
        editor._list = mock.MagicMock()
        editor._list.count.return_value = 0
        editor._lbl_header = mock.MagicMock()
        editor._lbl_empty_hint = mock.MagicMock()
        editor.set_label = mock.MagicMock()
        editor.set_empty_hint = mock.MagicMock()
        # base.retranslate goes through _btn_* widgets - stub them.
        editor._btn_add = mock.MagicMock()
        editor._btn_remove = mock.MagicMock()
        editor._btn_up = mock.MagicMock()
        editor._btn_down = mock.MagicMock()
        DriverSourceListEditor.retranslate(editor)
        editor.set_label.assert_called_once()
        editor.set_empty_hint.assert_called_once()

    def test_output_encoding_combo_retranslate_runs(self):
        from RBFtools.ui.widgets.output_encoding_combo import (
            OutputEncodingCombo)
        combo = OutputEncodingCombo.__new__(OutputEncodingCombo)
        combo.blockSignals = mock.MagicMock(return_value=False)
        combo.setItemText = mock.MagicMock()
        combo.setToolTip = mock.MagicMock()
        combo.set_encoding = mock.MagicMock()
        combo.encoding = mock.MagicMock(return_value=0)
        OutputEncodingCombo.retranslate(combo)
        # 3 enum items must be rewritten.
        self.assertEqual(combo.setItemText.call_count, 3)
        combo.setToolTip.assert_called_once()

    def test_profile_widget_retranslate_runs(self):
        from RBFtools.ui.widgets.profile_widget import ProfileWidget
        pw = ProfileWidget.__new__(ProfileWidget)
        pw._btn_refresh = mock.MagicMock()
        pw._txt = mock.MagicMock()
        pw._txt.toPlainText.return_value = ""
        ProfileWidget.retranslate(pw)
        pw._btn_refresh.setText.assert_called_once()
        pw._btn_refresh.setToolTip.assert_called_once()


if __name__ == "__main__":
    unittest.main()
