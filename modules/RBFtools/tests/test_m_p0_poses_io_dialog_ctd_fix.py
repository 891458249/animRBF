# -*- coding: utf-8 -*-
"""T_M_P0_POSES_IO_DIALOG_CTD_FIX — defend the dialog-stack
crash-defense in the poses-only export / import UI handlers.

Bug context (M_P0_POSES_IO_DIALOG_CTD_FIX, 2026-05-10):
  User reported "导出 pose 数据时点击 save 闪退" — clicking Save
  in the file dialog crashed Maya during pose export.

  Root cause: stacking two cmds modal dialogs back-to-back
  (cmds.fileDialog2 immediately followed by cmds.confirmDialog)
  on Windows leaves Maya's dialog machinery in an inconsistent
  state — clicking Save in fileDialog2 fires the dialog return,
  but our code IMMEDIATELY enters the success confirmDialog
  before Maya has finished tearing down the native fileDialog2
  window. Result: CTD ("crash to desktop" / 闪退).

  The pre-existing _on_export_selected pattern (no post-export
  confirmDialog, just cmds.warning + statusMessage signal) was
  reported as working. The new poses I/O followed a different
  pattern (post-export confirmDialog) and inherited the bug.

Fix: drop the post-export / post-import confirmDialog entirely.
Feedback flows through cmds.warning + statusMessage signal
(matches existing export pattern). Additionally wrap the
controller call in cmds.evalDeferred so the controller work
runs on Maya's idle tick AFTER the fileDialog2 native window
has fully torn down, eliminating any residual back-to-back
cmds-call CTD risk.

For the import REPLACE/APPEND picker (which is REQUIRED before
the file write to know the user's mode), wrap in evalDeferred
preemptively for the same reason.
"""
from __future__ import absolute_import, division, print_function

import io
import os
import re
import unittest


_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(os.path.dirname(_HERE)))
_MAIN_WINDOW = os.path.join(_REPO, "modules", "RBFtools", "scripts",
                             "RBFtools", "ui", "main_window.py")
_CONTROLLER = os.path.join(_REPO, "modules", "RBFtools", "scripts",
                            "RBFtools", "controller.py")


def _read(path):
    with io.open(path, "r", encoding="utf-8") as fh:
        return fh.read()


class TestPosesIODialogCTDFix(unittest.TestCase):

    def test_PERMANENT_a_export_no_post_confirmdialog(self):
        """_on_export_poses must NOT CALL confirmDialog after the
        controller export call (root cause of the original CTD).
        Comments / docstrings mentioning the word are fine — only
        actual function-call sites are forbidden."""
        src = _read(_MAIN_WINDOW)
        m = re.search(
            r"def\s+_on_export_poses\b[\s\S]+?(?=\n\s{0,4}def\s)", src)
        self.assertIsNotNone(m, "_on_export_poses function not found.")
        body = m.group(0)
        # Strip docstring + comment lines so only executable code is
        # examined.
        executable_lines = []
        in_docstring = False
        for line in body.splitlines():
            stripped = line.strip()
            if stripped.startswith('"""') or stripped.startswith("'''"):
                in_docstring = not in_docstring
                continue
            if in_docstring:
                continue
            if stripped.startswith("#"):
                continue
            executable_lines.append(line)
        executable_body = "\n".join(executable_lines)
        # Only flag actual cmds.confirmDialog( call sites.
        self.assertNotRegex(executable_body,
            r"_?cmds\.confirmDialog\s*\(",
            "_on_export_poses must NOT CALL cmds.confirmDialog. The "
            "post-export confirmDialog was the root cause of the "
            "save-click CTD on Windows. Feedback must flow through "
            "cmds.warning + statusMessage signal only.")

    def test_PERMANENT_b_export_uses_evaldeferred(self):
        """_on_export_poses must defer the controller call via either
        cmds.evalDeferred OR maya.utils.executeDeferred so the
        fileDialog2 native window can fully tear down."""
        src = _read(_MAIN_WINDOW)
        m = re.search(
            r"def\s+_on_export_poses\b[\s\S]+?(?=\n\s{0,4}def\s)", src)
        body = m.group(0)
        # M_P0_POSES_IO_DIALOG_CTD_FIX2 switched to executeDeferred
        # (the documented Python-callable deferral API). Either name
        # is acceptable, but ONE must be present.
        self.assertTrue(
            "executeDeferred" in body or "evalDeferred" in body,
            "_on_export_poses must wrap the controller export call "
            "in maya.utils.executeDeferred (preferred) or "
            "cmds.evalDeferred so the controller work runs after "
            "fileDialog2's native window has torn down.")

    def test_PERMANENT_c_import_no_post_confirmdialog(self):
        """_on_import_poses must NOT CALL confirmDialog AFTER the
        controller import call (only the pre-import REPLACE/APPEND
        picker is allowed). Comments mentioning the word are fine —
        only actual call sites are forbidden."""
        src = _read(_MAIN_WINDOW)
        m = re.search(
            r"def\s+_on_import_poses\b[\s\S]+?(?=\n\s{0,4}def\s)", src)
        body = m.group(0)
        idx = body.find("import_poses_from_path(path, mode=mode)")
        self.assertGreater(idx, 0,
            "Could not locate the controller import call anchor.")
        # Strip comments from the post-call slice and check only
        # executable code.
        post_call = body[idx:]
        post_lines = [
            line for line in post_call.splitlines()
            if not line.strip().startswith("#")
        ]
        post_executable = "\n".join(post_lines)
        self.assertNotRegex(post_executable,
            r"_?cmds\.confirmDialog\s*\(",
            "Code AFTER the controller import call must NOT CALL "
            "cmds.confirmDialog. Post-import dialogs were the import-"
            "side equivalent of the export CTD.")

    def test_PERMANENT_d_import_uses_evaldeferred(self):
        """_on_import_poses must wrap the REPLACE/APPEND picker +
        controller call in executeDeferred (or evalDeferred) to
        avoid back-to-back-modal CTD."""
        src = _read(_MAIN_WINDOW)
        m = re.search(
            r"def\s+_on_import_poses\b[\s\S]+?(?=\n\s{0,4}def\s)", src)
        body = m.group(0)
        self.assertTrue(
            "executeDeferred" in body or "evalDeferred" in body,
            "_on_import_poses must defer the REPLACE/APPEND modal "
            "+ controller call via maya.utils.executeDeferred "
            "(preferred) or cmds.evalDeferred so the prior "
            "fileDialog2 native window has fully torn down.")

    def test_PERMANENT_e_controller_export_defensive(self):
        """controller.export_poses_to_path must validate the path "
        "argument and never raise (always returns bool)."""
        src = _read(_CONTROLLER)
        m = re.search(
            r"def\s+export_poses_to_path[\s\S]+?(?=\n\s{0,4}def\s)", src)
        body = m.group(0)
        # Empty-path guard
        self.assertRegex(body,
            r"if\s+not\s+path\s*:[\s\S]{0,80}?return\s+False",
            "Controller must early-return False when path is empty.")
        # try/except wrapping the core_json call (catch base Exception)
        self.assertRegex(body,
            r"except\s+Exception\s+as\s+exc\s*:[\s\S]{0,150}?return\s+False",
            "Controller must catch base Exception and return False — "
            "the UI layer cannot let any exception escape and crash "
            "the post-dialog handler.")

    def test_PERMANENT_f_landing_tag_present(self):
        n_main = _read(_MAIN_WINDOW).count("M_P0_POSES_IO_DIALOG_CTD_FIX")
        n_ctrl = _read(_CONTROLLER).count("M_P0_POSES_IO_DIALOG_CTD_FIX")
        self.assertGreaterEqual(n_main, 1,
            "main_window must reference M_P0_POSES_IO_DIALOG_CTD_FIX.")
        self.assertGreaterEqual(n_ctrl, 1,
            "controller must reference M_P0_POSES_IO_DIALOG_CTD_FIX.")


if __name__ == "__main__":
    unittest.main()
