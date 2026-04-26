"""v5.0 FINAL CONSTITUTIONAL EVENT 2/6 — T_V5_PARITY_B2_LIVE +
T_V5_PARITY_B4_LIVE activation tests.

Locks the first two of six v5.0-final acceptance guards. Following
the M_B24a2-2 PROJECT-CONSTITUTIONAL-EVENT atomicity precedent,
these tests land in the SAME commit as the four atomic steps:

  (1) §M_PARITY_AUDIT.B2/B4 status: ⚠️ partial / ❌ → ✅ complete (full)
  (2) 9/15 ✅ counter advances to 11/15
  (3) STUB markdown updated to "LIVE per M_B24b2 commit <hash>"
  (4) Two new permanent guards (#29, #30) registered with full
      sub-checks (this file).

Future v5.0-final commits (M4 → B1, M_B7, M_B11, M_B14) follow the
same atomicity precedent for their respective B-row activations.
"""

from __future__ import absolute_import

import os
import re
import unittest


_REPO_ROOT = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..")
)
_RBF_H = os.path.join(_REPO_ROOT, "source", "RBFtools.h")
_RBF_CPP = os.path.join(_REPO_ROOT, "source", "RBFtools.cpp")


# ----------------------------------------------------------------------
# T_V5_PARITY_B2_LIVE (#29) — 4 sub-checks
# ----------------------------------------------------------------------


class TestV5ParityB2Live(unittest.TestCase):
    """#29 v5.0 FINAL CONSTITUTIONAL EVENT 2/6 - B2 multi-source driver."""

    def test_a_core_multi_source_api_importable(self):
        from RBFtools.core import (
            DriverSource,
            add_driver_source,
            remove_driver_source,
            read_driver_info_multi,
        )
        # Smoke - all four symbols resolve.
        self.assertTrue(callable(add_driver_source))
        self.assertTrue(callable(remove_driver_source))
        self.assertTrue(callable(read_driver_info_multi))
        # DriverSource is a dataclass, not a function.
        ds = DriverSource(node="x", attrs=())
        self.assertEqual(ds.node, "x")

    def test_b_widget_class_importable(self):
        from RBFtools.ui.widgets.driver_source_list_editor import (
            DriverSourceListEditor,
        )
        self.assertTrue(isinstance(DriverSourceListEditor, type),
            "DriverSourceListEditor must be a class")

    def test_c_widget_inherits_ordered_list_editor_base(self):
        from RBFtools.ui.widgets.driver_source_list_editor import (
            DriverSourceListEditor,
        )
        from RBFtools.ui.widgets._ordered_list_editor_base import (
            _OrderedListEditorBase,
        )
        self.assertTrue(issubclass(DriverSourceListEditor,
                                    _OrderedListEditorBase))

    def test_d_docstring_references_mirror_deferred_rationale(self):
        """Hardening 1.B + 2: machine-verifiable docstring reference
        to the mirror DEFERRED rationale section."""
        from RBFtools.core import read_driver_info_multi
        doc = read_driver_info_multi.__doc__ or ""
        self.assertIn("§M_B24b2.mirror-deferred-rationale", doc,
            "read_driver_info_multi docstring must reference "
            "§M_B24b2.mirror-deferred-rationale (Hardening 2 "
            "machine-verifiable form)")

    def test_e_add_driver_source_wires_input_data_path(self):
        """M_B24d sub-check (e) extension: add_driver_source must
        wire driver attrs into shape.input[base+i] (data path),
        not just write driverSource[d] metadata. Source-scan the
        function body for connectAttr-to-input."""
        import inspect
        from RBFtools.core import add_driver_source
        body = inspect.getsource(add_driver_source)
        self.assertIn(".input[", body,
            "add_driver_source must wire data path to "
            "shape.input[base+i] (M_B24d corrective).")
        self.assertIn("connectAttr", body,
            "add_driver_source must call connectAttr for "
            "data-path wiring (M_B24d).")


# ----------------------------------------------------------------------
# T_V5_PARITY_B4_LIVE (#30) — 4 sub-checks
# ----------------------------------------------------------------------


class TestV5ParityB4Live(unittest.TestCase):
    """#30 v5.0 FINAL CONSTITUTIONAL EVENT 2/6 - B4 outputEncoding."""

    def test_a_combo_widget_importable(self):
        from RBFtools.ui.widgets.output_encoding_combo import (
            OutputEncodingCombo,
        )
        self.assertTrue(isinstance(OutputEncodingCombo, type))

    def test_b_expected_node_dict_keys_contains_output_encoding(self):
        from RBFtools.core_json import EXPECTED_NODE_DICT_KEYS
        self.assertIn("output_encoding", EXPECTED_NODE_DICT_KEYS)

    def test_c_rbftools_h_declares_output_encoding(self):
        with open(_RBF_H, "r", encoding="utf-8") as f:
            src = f.read()
        self.assertIn("static MObject outputEncoding;", src)

    def test_d_rbftools_cpp_adds_output_encoding(self):
        with open(_RBF_CPP, "r", encoding="utf-8") as f:
            src = f.read()
        self.assertIsNotNone(
            re.search(r"addAttribute\(\s*outputEncoding\s*\)", src),
            "RBFtools.cpp must contain addAttribute(outputEncoding)")


if __name__ == "__main__":
    unittest.main()
