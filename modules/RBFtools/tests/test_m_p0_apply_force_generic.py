# -*- coding: utf-8 -*-
"""T_M_P0_APPLY_FORCE_GENERIC — defend the rbfMode=0 force-write
in core.apply_poses (entry + exit guard).

Bug context (M_P0_APPLY_FORCE_GENERIC, 2026-05-10):
  User reported clicking Apply flipped the RBF Mode UI dropdown
  from "通用 RBF" (Generic, rbfMode=0) to "矩阵 RBF" (Matrix,
  rbfMode=1) and the driver→driven link broke. Maya scriptJob
  ``attributeChange`` monitor on rbfMode caught 4 writes during
  Apply — all writing value 0 — yet ``cmds.getAttr`` after Apply
  returned 1. The flip path is unmapped (likely a non-cmds
  write like a connection-driven cascade) but the SCRIPT couldn't
  capture it.

  M_P0_RBF_MODE_UI_RESYNC fixed the **view-layer** desync (UI
  dropdown not tracking node attr). It does NOT fix the underlying
  flip — if the node attr genuinely flips to 1 by some mechanism,
  the UI just shows the truth (Matrix), but the Generic-mode pose
  data + input[] wiring becomes incompatible with the Matrix
  compute path → garbage solver output → no driving.

Fix: defensive pin in core.apply_poses. The routed Apply flow
signature (driver_node + driver_attrs + driven_node + driven_attrs)
is Generic-mode-only BY CONTRACT — Matrix mode uses
add_driver_source + driverList[] wiring, a completely different
entry point. So forcing rbfMode=0 at apply_poses entry AND exit
is safe (no Matrix-mode caller can reach this function).

Two-point defense:
  * Step 0 (entry, before clear_node_data): catches a stranded
    rbfMode=1 from a prior session / UI desync / unknown flip.
  * Step 7b (exit, after evaluate trigger): catches any mid-apply
    write that happens between step 1 and step 7.

This test pins both write sites and the landing tag.
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


def _read(path):
    with io.open(path, "r", encoding="utf-8") as fh:
        return fh.read()


class TestApplyForceGeneric(unittest.TestCase):

    def test_PERMANENT_a_apply_poses_function_present(self):
        """apply_poses must exist (anchor for the other guards)."""
        src = _read(_CORE)
        self.assertRegex(src, r"def\s+apply_poses\s*\(\s*node\s*,\s*driver_node",
            "core.apply_poses signature changed; review M_P0_APPLY_FORCE_GENERIC.")

    def test_PERMANENT_b_entry_force_rbfmode_zero(self):
        """Step 0 (entry) must force rbfMode=0 BEFORE clear_node_data."""
        src = _read(_CORE)
        m = re.search(
            r"def\s+apply_poses\b[\s\S]+?(?=\n(?:def |class )\b)", src)
        self.assertIsNotNone(m, "apply_poses function body not found.")
        body = m.group(0)
        # Locate two anchors:
        #   anchor1: 'with undo_chunk("RBFtools: apply poses"):'
        #   anchor2: 'clear_node_data(node)'
        anchor1 = body.find('with undo_chunk("RBFtools: apply poses")')
        anchor2 = body.find("clear_node_data(node)")
        self.assertGreater(anchor1, 0, "undo_chunk anchor missing.")
        self.assertGreater(anchor2, anchor1, "clear_node_data anchor missing.")
        # Look for setAttr rbfMode=0 between anchor1 and anchor2.
        between = body[anchor1:anchor2]
        self.assertRegex(between,
            r'cmds\.setAttr\s*\(\s*shape\s*\+\s*"\.rbfMode"\s*,\s*0\s*\)',
            "Step 0 must force shape.rbfMode=0 BEFORE clear_node_data "
            "(M_P0_APPLY_FORCE_GENERIC entry guard).")

    def test_PERMANENT_c_exit_force_rbfmode_zero(self):
        """Step 7b (exit) must force rbfMode=0 AFTER evaluate trigger."""
        src = _read(_CORE)
        m = re.search(
            r"def\s+apply_poses\b[\s\S]+?(?=\n(?:def |class )\b)", src)
        body = m.group(0)
        # Locate evaluate trigger anchor.
        eval_anchor = body.find('cmds.setAttr(shape + ".evaluate", 1)')
        self.assertGreater(eval_anchor, 0,
            "evaluate trigger anchor missing.")
        # Locate apply_succeeded = True anchor (end of try block).
        success_anchor = body.find("apply_succeeded = True", eval_anchor)
        self.assertGreater(success_anchor, eval_anchor,
            "apply_succeeded anchor missing after evaluate trigger.")
        # Look for setAttr rbfMode=0 between evaluate trigger and
        # apply_succeeded = True.
        between = body[eval_anchor:success_anchor]
        self.assertRegex(between,
            r'cmds\.setAttr\s*\(\s*shape\s*\+\s*"\.rbfMode"\s*,\s*0\s*\)',
            "Step 7b must force shape.rbfMode=0 AFTER evaluate trigger "
            "(M_P0_APPLY_FORCE_GENERIC exit guard).")

    def test_PERMANENT_d_landing_tag_in_comment(self):
        """Source-level landing tag for traceability."""
        src = _read(_CORE)
        n = src.count("M_P0_APPLY_FORCE_GENERIC")
        self.assertGreaterEqual(n, 2,
            "core.py must reference M_P0_APPLY_FORCE_GENERIC at least "
            "twice (entry + exit guard sites) for git-blame traceability.")


if __name__ == "__main__":
    unittest.main()
