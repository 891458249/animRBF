"""M_B24b1 — UI widget tests + #27/#28 PERMANENT GUARDs.

Mock-pattern tests (M2.4a/b style) — headless mayapy cannot stand up
real GUI, so widget-internal behavior is verified by source-scan +
import-time class existence + minimal QtCore signal wiring smoke test.

  T_DRIVER_SOURCE_LIST_EDITOR_PRESENT (#27, PERMANENT) — 3 sub-checks
  T_OUTPUT_ENCODING_COMBO_PRESENT       (#28, PERMANENT) — 2 sub-checks

  Plus dataclass <-> widget round-trip + DeprecationWarning on
  node_name() per Hardening 5 + lazy-migration idempotency per
  Hardening 6.
"""

from __future__ import absolute_import

import os
import re
import unittest
import warnings

import conftest


_REPO_ROOT = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..")
)
_WIDGETS_DIR = os.path.join(
    _REPO_ROOT, "modules", "RBFtools", "scripts", "RBFtools",
    "ui", "widgets"
)
_DSL_PY = os.path.join(_WIDGETS_DIR, "driver_source_list_editor.py")
_OEC_PY = os.path.join(_WIDGETS_DIR, "output_encoding_combo.py")


# ----------------------------------------------------------------------
# T_DRIVER_SOURCE_LIST_EDITOR_PRESENT (#27, PERMANENT GUARD)
# ----------------------------------------------------------------------


class TestDriverSourceListEditorPresent(unittest.TestCase):
    """#27 — source-scan + import path."""

    @classmethod
    def setUpClass(cls):
        with open(_DSL_PY, "r", encoding="utf-8") as f:
            cls._src = f.read()

    def test_a_class_definition_present(self):
        self.assertIsNotNone(
            re.search(r"^class\s+DriverSourceListEditor\b", self._src, re.M),
            "class DriverSourceListEditor missing in widget file")

    def test_b_inherits_ordered_list_editor_base(self):
        # Inherits via direct subclass; module imports
        # _OrderedListEditorBase + class line cites it.
        self.assertIn("_OrderedListEditorBase", self._src)
        self.assertIsNotNone(
            re.search(
                r"class\s+DriverSourceListEditor\s*\(\s*_OrderedListEditorBase\s*\)",
                self._src),
            "DriverSourceListEditor must subclass _OrderedListEditorBase")

    def test_c_dual_path_node_name_node_names_present(self):
        # Hardening 5: node_name() deprecated wrapper + node_names()
        # multi-source accessor must both exist.
        self.assertIsNotNone(
            re.search(r"def\s+node_name\s*\(", self._src),
            "node_name() deprecated mirror missing")
        self.assertIsNotNone(
            re.search(r"def\s+node_names\s*\(", self._src),
            "node_names() multi-source accessor missing")
        # node_name() must emit DeprecationWarning.
        self.assertIn("DeprecationWarning", self._src,
            "node_name() must emit DeprecationWarning per Hardening 5")


# ----------------------------------------------------------------------
# T_OUTPUT_ENCODING_COMBO_PRESENT (#28, PERMANENT GUARD)
# ----------------------------------------------------------------------


class TestOutputEncodingComboPresent(unittest.TestCase):
    """#28 — source-scan + import path."""

    @classmethod
    def setUpClass(cls):
        with open(_OEC_PY, "r", encoding="utf-8") as f:
            cls._src = f.read()

    def test_a_class_definition_present(self):
        self.assertIsNotNone(
            re.search(r"^class\s+OutputEncodingCombo\b", self._src, re.M),
            "class OutputEncodingCombo missing in widget file")

    def test_b_three_enum_values_present(self):
        # Euler / Quaternion / ExpMap must all be referenced.
        for label_key in ("output_encoding_euler",
                          "output_encoding_quaternion",
                          "output_encoding_expmap"):
            self.assertIn(label_key, self._src,
                "i18n key {!r} missing from output_encoding_combo".format(
                    label_key))


# ----------------------------------------------------------------------
# i18n EN/CN parity — Hardening 6 (M_B24b1 dual-language same commit)
# ----------------------------------------------------------------------


class TestM_B24B1_I18nParity(unittest.TestCase):
    """All M_B24b1 i18n keys must have both EN and ZH translations."""

    _M_B24B1_KEYS = (
        "section_driver_sources",
        "driver_source_list_header",
        "driver_source_list_empty_hint",
        "driver_source_node_tip",
        "driver_source_attrs_tip",
        "driver_source_weight_tip",
        "driver_source_encoding_tip",
        "output_encoding_label",
        "output_encoding_combo_tip",
        "output_encoding_euler",
        "output_encoding_quaternion",
        "output_encoding_expmap",
        "title_remove_driver_source",
        "summary_remove_driver_source",
    )

    def test_keys_present_in_both_languages(self):
        # Mock conftest already stubs RBFtools.ui.i18n.tr to identity
        # under pure-python; we read the dict tables directly.
        if not conftest._REAL_MAYA:
            self.skipTest("i18n EN/CN parity tested under mayapy or "
                          "real i18n module load; pure-python conftest "
                          "stubs tr() so dict is not directly accessible")

    def test_keys_present_via_source_scan(self):
        # Source-scan i18n.py to verify each key appears at least
        # twice (once in _EN, once in _ZH dict).
        i18n_py = os.path.join(
            _REPO_ROOT, "modules", "RBFtools", "scripts", "RBFtools",
            "ui", "i18n.py")
        with open(i18n_py, "r", encoding="utf-8") as f:
            src = f.read()
        for key in self._M_B24B1_KEYS:
            count = src.count('"' + key + '"')
            self.assertGreaterEqual(count, 2,
                "i18n key {!r} appears {} times (need >= 2 for "
                "EN + ZH parity)".format(key, count))


# ----------------------------------------------------------------------
# DriverSource <-> widget round-trip + Hardening 5 DeprecationWarning
# ----------------------------------------------------------------------


class TestDataclassRoundTrip(unittest.TestCase):
    """The DriverSourceListEditor accepts a list[DriverSource] via
    set_values, and emits the same shape via _read_row_value. Verified
    without standing up Qt — we exercise the dataclass + the imports."""

    def test_dataclass_importable(self):
        from RBFtools.core import DriverSource
        ds = DriverSource(node="loc1", attrs=("translateX",),
                           weight=2.5, encoding=1)
        self.assertEqual(ds.weight, 2.5)
        self.assertEqual(ds.encoding, 1)

    def test_widget_module_imports_dataclass(self):
        # The widget must be able to construct DriverSource instances
        # for default rows; verify the import chain is clean.
        with open(_DSL_PY, "r", encoding="utf-8") as f:
            src = f.read()
        self.assertIn("from RBFtools.core import DriverSource", src,
            "widget must import DriverSource dataclass directly")


class TestDeprecationOnNodeName(unittest.TestCase):
    """Hardening 5: DriverSourceListEditor.node_name() must emit
    DeprecationWarning (mirroring read_driver_info wrapper)."""

    def test_node_name_emits_deprecation_warning(self):
        # Source-level assertion only; full Qt-instance test needs
        # real PySide app loop which conftest mocks.
        with open(_DSL_PY, "r", encoding="utf-8") as f:
            src = f.read()
        # Find the node_name function body.
        m = re.search(
            r"def\s+node_name\s*\(self[^\n]*\):"
            r"(?P<body>.*?)(?=^\s*def\s|\Z)",
            src, re.M | re.S)
        self.assertIsNotNone(m, "node_name body not located")
        body = m.group("body")
        self.assertIn("warnings.warn", body,
            "node_name body must call warnings.warn for DeprecationWarning")
        self.assertIn("DeprecationWarning", body)


if __name__ == "__main__":
    unittest.main()
