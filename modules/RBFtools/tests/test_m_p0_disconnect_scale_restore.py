# -*- coding: utf-8 -*-
"""T_M_P0_DISCONNECT_SCALE_RESTORE — defend the post-disconnect
scale=1.0 restoration in core._disconnect_or_purge.

Bug context (M_P0_DISCONNECT_SCALE_RESTORE, 2026-05-10):
  The routed Disconnect path (controller.disconnect_routed →
  core.disconnect_routed) wraps the per-wire sever loop in
  ``_node_state_frozen`` which forces ``shape.nodeState=1``
  (HasNoEffect). With compute() short-circuited, the solver
  ``MFnNumericData::kDouble`` ``output`` plug returns its default
  value 0.0; DG propagates that 0 to every connected driven attr,
  ``cmds.disconnectAttr`` leaves the destination cached at 0, and
  scale-driven joints collapse from 1.0 to 0.0 — t-pose mesh
  implodes the moment Disconnect is clicked.

Fix: in ``_disconnect_or_purge``, after a successful sever on the
output side, when the destination plug names a Maya scale channel,
``cmds.setAttr(other_plug, 1.0)`` to restore multiplicative
identity. Translate / rotate / visibility default to 0 in Maya
(rest pose) and need no remediation; only scale needs special-
casing because its identity is 1, not 0.

This test file pins the source-level invariant: pure-Python AST
scan of core.py asserts the restoration block exists, references
SCALE_ATTR_NAMES, and is gated by side == "output".
"""
from __future__ import absolute_import, division, print_function

import io
import os
import re
import unittest


_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(os.path.dirname(_HERE)))
_CORE = os.path.join(_REPO, "modules", "RBFtools", "scripts",
                     "RBFtools", "core.py")
_CONSTANTS = os.path.join(_REPO, "modules", "RBFtools", "scripts",
                          "RBFtools", "constants.py")


def _read(path):
    with io.open(path, "r", encoding="utf-8") as fh:
        return fh.read()


class TestDisconnectScaleRestore(unittest.TestCase):

    def test_PERMANENT_a_constants_export_scale_attr_names(self):
        """SCALE_ATTR_NAMES must include both long and short names."""
        src = _read(_CONSTANTS)
        self.assertIn("SCALE_ATTR_NAMES", src,
            "constants.py must export SCALE_ATTR_NAMES.")
        self.assertIn("scaleX", src)
        self.assertIn("scaleY", src)
        self.assertIn("scaleZ", src)
        self.assertIn('"sx"', src)
        self.assertIn('"sy"', src)
        self.assertIn('"sz"', src)

    def test_PERMANENT_b_core_imports_scale_attr_names(self):
        """core.py must import SCALE_ATTR_NAMES from constants."""
        src = _read(_CORE)
        self.assertRegex(src,
            r"from\s+RBFtools\.constants\s+import\s*\([^)]*SCALE_ATTR_NAMES",
            "core.py must import SCALE_ATTR_NAMES.")

    def test_PERMANENT_c_disconnect_purge_restores_scale(self):
        """_disconnect_or_purge must restore scale to 1.0 post-sever."""
        src = _read(_CORE)
        # Locate the function body.
        m = re.search(
            r"def\s+_disconnect_or_purge\b[\s\S]+?(?=\n(?:def |class )\b)",
            src)
        self.assertIsNotNone(m,
            "_disconnect_or_purge function not found in core.py.")
        body = m.group(0)
        # Output-side guard
        self.assertRegex(body,
            r'side\s*==\s*"output"\s+and\s+other_plug',
            "Restoration must be gated by side == 'output' to avoid "
            "touching driver / input plugs.")
        # SCALE_ATTR_NAMES gate
        self.assertIn("SCALE_ATTR_NAMES", body,
            "Restoration must check SCALE_ATTR_NAMES so non-scale "
            "channels (translate / rotate) are left alone.")
        # The actual setAttr to 1.0
        self.assertRegex(body,
            r"cmds\.setAttr\s*\(\s*other_plug\s*,\s*1\.0\s*\)",
            "Restoration must call cmds.setAttr(other_plug, 1.0) "
            "(multiplicative identity for scale).")

    def test_PERMANENT_d_landing_tag_in_comment(self):
        """Source-level landing tag for traceability."""
        src = _read(_CORE)
        self.assertIn("M_P0_DISCONNECT_SCALE_RESTORE", src,
            "core.py must mark the fix with the landing tag for "
            "traceability via git blame / git log -G.")

    def test_PERMANENT_e_severance_gating(self):
        """Restoration must run only when severance succeeded."""
        src = _read(_CORE)
        m = re.search(
            r"def\s+_disconnect_or_purge\b[\s\S]+?(?=\n(?:def |class )\b)",
            src)
        body = m.group(0)
        # The setAttr-to-1.0 block sits inside the `if severed:` block
        # so a failed disconnect (e.g., destination was never wired in
        # the first place) doesn't write a phantom 1.0 to a driven
        # joint that the user didn't ask to touch.
        severed_match = re.search(
            r"if\s+severed\s*:[\s\S]+?return\s+severed",
            body)
        self.assertIsNotNone(severed_match,
            "_disconnect_or_purge must end with 'if severed: ... "
            "return severed' block.")
        severed_body = severed_match.group(0)
        self.assertIn("SCALE_ATTR_NAMES", severed_body,
            "Scale restoration must be inside the 'if severed:' block.")


if __name__ == "__main__":
    unittest.main()
