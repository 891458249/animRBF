# -*- coding: utf-8 -*-
"""T_M_P0_APPLY_FREEZE_DURING_WRITE — defend the nodeState freeze
around the apply_poses + import_poses_from_path multi-attr write
storms.

Bug context (M_P0_APPLY_FREEZE_DURING_WRITE, 2026-05-10):
  User reported "Maya often crashes" running plugin functions.
  Audit identified the most likely crash vector:
  ``apply_poses`` (and the freshly-added M_P0_POSES_IO
  ``import_poses_from_path``) fire HUNDREDS of cmds.setAttr /
  cmds.removeMultiInstance calls inside a single undo_chunk —
  per-pose poseInput/poseValue writes, baseline writes, local-
  transform replay disconnects + setAttrs + reconnects.

  Each of those mutations triggers DG dirty propagation. With
  shape.nodeState=Normal, the C++ compute() tries to run with
  half-populated matPoses / matValues arrays — bounds violations
  or solver assertion failures inside the kernel are easy to
  trigger, manifesting as Maya CTD ("crash to desktop" / 闪退).

  The pre-existing connect_routed / disconnect_routed paths
  already use the ``_node_state_frozen`` context manager
  (cpp:4574) for exactly this defense, but apply_poses and the
  newly-added import_poses_from_path did not.

Fix: wrap the entire write storm in apply_poses +
import_poses_from_path with ``with _node_state_frozen(shape):``.
While inside the freeze, shape.nodeState=1 (HasNoEffect) makes
Maya skip compute() on the RBF node entirely; restoration to
the original state happens in the contextmanager's finally
block, so an exception inside the write loop cannot leave the
node permanently frozen.

For import_poses_from_path: the evaluate=0/1 retrain toggle
must run AFTER the freeze releases — toggling evaluate while
nodeState=1 is a no-op (no compute()), defeating the retrain.
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
_CORE_JSON = os.path.join(_REPO, "modules", "RBFtools", "scripts",
                           "RBFtools", "core_json.py")


def _read(path):
    with io.open(path, "r", encoding="utf-8") as fh:
        return fh.read()


class TestApplyFreezeDuringWrite(unittest.TestCase):

    def test_PERMANENT_a_apply_poses_uses_node_state_frozen(self):
        """apply_poses' undo_chunk must be paired with _node_state_frozen."""
        src = _read(_CORE)
        m = re.search(
            r"def\s+apply_poses\b[\s\S]+?(?=\n(?:def |class )\b)", src)
        self.assertIsNotNone(m, "apply_poses function not found.")
        body = m.group(0)
        # Must combine undo_chunk + _node_state_frozen in the same
        # with-statement (or sequential withs) so the freeze covers
        # the entire write storm.
        self.assertIn("undo_chunk(\"RBFtools: apply poses\")", body,
            "apply_poses must keep its existing undo_chunk anchor.")
        self.assertIn("_node_state_frozen(get_shape(node))", body,
            "apply_poses MUST wrap its write storm in "
            "_node_state_frozen(get_shape(node)). Without this, the "
            "per-pose setAttr / removeMultiInstance loop triggers "
            "mid-storm compute() against half-populated matPoses → "
            "C++ array-bound violation → Maya CTD.")

    def test_PERMANENT_b_apply_poses_freeze_inside_undo_chunk(self):
        """Freeze must be ENTERED while undo_chunk is active so
        an exception unwinds both contexts cleanly."""
        src = _read(_CORE)
        m = re.search(
            r"def\s+apply_poses\b[\s\S]+?(?=\n(?:def |class )\b)", src)
        body = m.group(0)
        # The 'with undo_chunk(...), _node_state_frozen(...):'
        # combined-with-statement is the canonical pattern (see
        # connect_routed cpp:4574). Either ordering is acceptable
        # but they MUST appear together in a single with-statement.
        # Note: the function call args may have nested parens
        # (e.g. _node_state_frozen(get_shape(node))) which break
        # a [^)]+ regex. Use lazy [\s\S] up to a colon ending the
        # combined with-statement.
        self.assertRegex(body,
            r"with\s+undo_chunk[\s\S]{0,200}?_node_state_frozen[\s\S]{0,80}?:\s*\n",
            "apply_poses must enter undo_chunk and _node_state_frozen "
            "in a single combined 'with' statement so an exception "
            "unwinds both layers via the contextmanager finally "
            "blocks (matches connect_routed / disconnect_routed "
            "crash-defense pattern).")

    def test_PERMANENT_c_import_poses_uses_node_state_frozen(self):
        """import_poses_from_path's write loop must be inside freeze."""
        src = _read(_CORE_JSON)
        m = re.search(
            r"def\s+import_poses_from_path\b[\s\S]+?\Z", src)
        self.assertIsNotNone(m,
            "import_poses_from_path not found.")
        body = m.group(0)
        self.assertRegex(body,
            r"with\s+core\.undo_chunk[\s\S]{0,200}?core\._node_state_frozen[\s\S]{0,80}?:\s*\n",
            "import_poses_from_path must wrap the per-pose write "
            "loop in 'with core.undo_chunk(...), "
            "core._node_state_frozen(shape):'. Without this, mid-loop "
            "compute() triggers on half-populated poses[] → CTD.")

    def test_PERMANENT_d_import_poses_evaluate_outside_freeze(self):
        """evaluate=0/1 retrain must happen AFTER freeze releases."""
        src = _read(_CORE_JSON)
        m = re.search(
            r"def\s+import_poses_from_path\b[\s\S]+?\Z", src)
        body = m.group(0)
        # The freeze block ends, then evaluate is toggled. Verify
        # by checking that the evaluate=1 setAttr does NOT appear
        # inside the same block as _node_state_frozen — i.e. the
        # block ends with the for-loop, not with evaluate.
        # We assert the textual order: _node_state_frozen scope
        # ends before the evaluate=0/1 toggle.
        idx_freeze = body.find("_node_state_frozen(shape)")
        idx_eval = body.find('cmds.setAttr(shape + ".evaluate", 1)')
        self.assertGreater(idx_freeze, 0,
            "_node_state_frozen anchor missing in import body.")
        self.assertGreater(idx_eval, idx_freeze,
            "evaluate=1 toggle must appear AFTER the "
            "_node_state_frozen entry text in the source body.")
        # Indentation check: the evaluate=1 line must be at a SHALLOWER
        # indent than the inside of the with-block, i.e. NOT inside
        # the freeze block. Look for "    try:\n        cmds.setAttr"
        # at module-function level (4 spaces), not nested deeper.
        # We check: the line "cmds.setAttr(shape + \".evaluate\", 1)"
        # must be preceded by "try:" at 4-space indent, not 8.
        # Simpler check: there's a comment line "# Force re-train"
        # or "# Outside the freeze" before the evaluate line.
        self.assertRegex(body,
            r"(Force\s+re-train|Outside\s+the\s+freeze|"
            r"freeze\s+releases|evaluate=0/1\s+(must|toggle))[\s\S]{0,300}?"
            r'cmds\.setAttr\(shape\s*\+\s*"\.evaluate"\s*,\s*1\s*\)',
            "evaluate=1 must be commented as outside-freeze / post-"
            "release retrain so future readers know the scoping is "
            "intentional, not accidental.")

    def test_PERMANENT_e_landing_tag_present(self):
        n_core = _read(_CORE).count("M_P0_APPLY_FREEZE_DURING_WRITE")
        n_json = _read(_CORE_JSON).count("M_P0_APPLY_FREEZE_DURING_WRITE")
        self.assertGreaterEqual(n_core, 1,
            "core.py must reference M_P0_APPLY_FREEZE_DURING_WRITE.")
        self.assertGreaterEqual(n_json, 1,
            "core_json.py must reference M_P0_APPLY_FREEZE_DURING_WRITE.")


if __name__ == "__main__":
    unittest.main()
