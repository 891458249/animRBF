# -*- coding: utf-8 -*-
"""M_P0_DRAGDROP_PERMERR_RETRY (2026-04-30) — dragDropInstaller's
shutil ops did not retry / catch PermissionError on Windows.

User report 2026-04-30: dragging dragDropInstaller.py into Maya
2022 raised PermissionError on win64\\2025\\RBFtools.mll inside
shutil.py:398. Maya unloadPlugin had just released the .mll but
the Windows OS file handle settle delay (1-3 seconds) was still
in flight; shutil.rmtree fired immediately and hit the lock.

Root cause (grep + install.log forensics):

  dragDropInstaller.copyDir / removeDir each had a single
  ``try: shutil.<op>(...) except shutil.Error:`` block — no
  PermissionError catch, no OSError catch, no retry loop, no
  onerror callback for read-only files. Compare with install.py
  _remove_tree (lines 94-126) which already had the canonical
  defensive pattern:

    - 3-attempt retry loop with sleep(1) between attempts.
    - onerror callback that os.chmod(fpath, S_IWRITE) + retries
      the failed op.
    - Catches PermissionError + OSError in addition to
      shutil.Error.

  install.log timeline at 22:01:04 confirmed the failure point:
  "Deleting previously installed module contents" was logged
  but no follow-on "Removed:" line appeared — the rmtree raised
  before logInfo could fire, the unhandled exception bubbled
  up through Maya's drag-drop dispatcher, and the install
  aborted mid-stream. The user's 17-second retry then half-
  copied the new tree on top of the half-deleted old tree,
  producing the corrupted state in their report.

Path A fix (mirror install.py's defensive pattern in
dragDropInstaller):

  * removeDir: idempotent fast-return when path is already
    gone; onerror callback force-clears read-only; 3-attempt
    retry loop with sleep(1); catches PermissionError + OSError
    in addition to shutil.Error.

  * copyDir: 3-attempt retry loop with sleep(1); catches the
    same exception set; clears any partial destination tree
    between retries (shutil.copytree rejects an existing dest).

  * Top-level imports gain `stat` (for S_IWRITE) and `time`
    (for sleep). install.py is untouched — already correct.

PERMANENT GUARD T_M_P0_DRAGDROP_PERMERR_RETRY.
"""

from __future__ import absolute_import

import ast
import os
import shutil
import sys
import unittest
from unittest import mock


_REPO_ROOT = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..")
)
_DRAGDROP_PY = os.path.join(_REPO_ROOT, "dragDropInstaller.py")
_INSTALL_PY = os.path.join(_REPO_ROOT, "install.py")


def _read(p):
    with open(p, "r", encoding="utf-8") as fh:
        return fh.read()


def _slice_function(src, signature):
    idx = src.find(signature)
    assert idx >= 0, "{} not found".format(signature)
    end = src.find("\ndef ", idx + 1)
    return src[idx:end if end > 0 else len(src)]


def _import_dragdrop():
    """Import dragDropInstaller.py from the repo root with the
    Maya-only modules stubbed out. Returns the loaded module."""
    if _REPO_ROOT not in sys.path:
        sys.path.insert(0, _REPO_ROOT)
    # Stub maya.cmds + maya.api.OpenMaya so the import-time
    # ``import maya.cmds`` / ``from maya.api import OpenMaya``
    # statements do not blow up under pure-Python pytest.
    stubs = {}
    if "maya" not in sys.modules:
        sys.modules["maya"] = mock.MagicMock()
        stubs["maya"] = sys.modules["maya"]
    if "maya.cmds" not in sys.modules:
        sys.modules["maya.cmds"] = mock.MagicMock()
        stubs["maya.cmds"] = sys.modules["maya.cmds"]
    if "maya.api" not in sys.modules:
        sys.modules["maya.api"] = mock.MagicMock()
        stubs["maya.api"] = sys.modules["maya.api"]
    if "maya.api.OpenMaya" not in sys.modules:
        sys.modules["maya.api.OpenMaya"] = mock.MagicMock()
        stubs["maya.api.OpenMaya"] = sys.modules["maya.api.OpenMaya"]
    if "dragDropInstaller" in sys.modules:
        del sys.modules["dragDropInstaller"]
    import dragDropInstaller   # noqa: F401
    return sys.modules["dragDropInstaller"]


# ----------------------------------------------------------------------
# PERMANENT GUARD T_M_P0_DRAGDROP_PERMERR_RETRY
# ----------------------------------------------------------------------


class T_M_P0_DRAGDROP_PERMERR_RETRY(unittest.TestCase):
    """PERMANENT GUARD — DO NOT REMOVE.

    Locks the dragDropInstaller copyDir / removeDir defensive
    contract. Mirrors install.py _copy_tree / _remove_tree."""

    @classmethod
    def setUpClass(cls):
        cls._dragdrop_src = _read(_DRAGDROP_PY)
        cls._install_src = _read(_INSTALL_PY)

    def test_PERMANENT_a_imports_stat_and_time(self):
        # Top-level imports MUST include stat (for S_IWRITE) and
        # time (for sleep). Without them the runtime path would
        # NameError on the very first retry attempt.
        self.assertIn(
            "\nimport stat\n", self._dragdrop_src,
            "dragDropInstaller MUST import stat at module scope "
            "(needed for S_IWRITE in the onerror callback).")
        self.assertIn(
            "\nimport time\n", self._dragdrop_src,
            "dragDropInstaller MUST import time at module scope "
            "(needed for sleep(1) between retry attempts).")

    def test_PERMANENT_b_copydir_retry_loop_present(self):
        body = _slice_function(
            self._dragdrop_src, "def copyDir(source, destination):")
        self.assertIn(
            "for attempt in range(3):", body,
            "copyDir MUST wrap shutil.copytree in a 3-attempt "
            "retry loop — without retry the post-rmtree settle "
            "delay re-introduces the user-reported "
            "PermissionError.")
        self.assertIn(
            "time.sleep(1)", body,
            "copyDir MUST sleep(1) between retry attempts so "
            "the Windows OS file-handle release lag actually "
            "drains.")

    def test_PERMANENT_c_copydir_catches_permerr_and_oserr(self):
        body = _slice_function(
            self._dragdrop_src, "def copyDir(source, destination):")
        for exc_name in ("PermissionError", "OSError",
                         "shutil.Error"):
            self.assertIn(
                exc_name, body,
                "copyDir MUST catch {} in addition to the "
                "original shutil.Error — the user-reported "
                "failure was specifically PermissionError "
                "which the pre-fix code let propagate "
                "uncaught.".format(exc_name))

    def test_PERMANENT_d_copydir_clears_partial_destination(self):
        body = _slice_function(
            self._dragdrop_src, "def copyDir(source, destination):")
        # Between retries the destination tree must be cleared —
        # shutil.copytree rejects an existing destination.
        self.assertIn(
            "shutil.rmtree", body,
            "copyDir retry loop MUST clear partial destination "
            "tree between attempts (shutil.copytree rejects "
            "existing dest); without this the second attempt "
            "fails with FileExistsError instead of the actual "
            "underlying lock condition.")
        self.assertIn(
            "ignore_errors=True", body,
            "Inter-retry rmtree MUST use ignore_errors=True so "
            "a partial-clean failure does not mask the "
            "original PermissionError on the next attempt.")

    def test_PERMANENT_e_removedir_retry_loop_present(self):
        body = _slice_function(
            self._dragdrop_src, "def removeDir(path):")
        self.assertIn(
            "for attempt in range(3):", body,
            "removeDir MUST wrap shutil.rmtree in a 3-attempt "
            "retry loop.")
        self.assertIn(
            "time.sleep(1)", body)

    def test_PERMANENT_f_removedir_catches_permerr_and_oserr(self):
        body = _slice_function(
            self._dragdrop_src, "def removeDir(path):")
        for exc_name in ("PermissionError", "OSError",
                         "shutil.Error"):
            self.assertIn(exc_name, body)

    def test_PERMANENT_g_removedir_onerror_chmod(self):
        body = _slice_function(
            self._dragdrop_src, "def removeDir(path):")
        self.assertIn(
            "stat.S_IWRITE", body,
            "removeDir's onerror callback MUST call os.chmod "
            "with stat.S_IWRITE to handle read-only files.")
        self.assertIn(
            "onerror=", body,
            "removeDir MUST pass an onerror callback to "
            "shutil.rmtree so the chmod recovery path is "
            "actually invoked.")

    def test_PERMANENT_h_removedir_idempotent_fast_return(self):
        body = _slice_function(
            self._dragdrop_src, "def removeDir(path):")
        self.assertIn(
            "os.path.isdir(", body,
            "removeDir MUST fast-return when the path is "
            "already gone (idempotent — second-Apply users "
            "should not see a noisy error).")

    def test_PERMANENT_i_ast_except_clauses_cover_permerr(self):
        # AST guard (lesson #6): walk both functions and assert
        # each ExceptHandler's exception type tuple includes
        # PermissionError. Static grep can drift if a future
        # refactor renames the tuple to a wrapper alias; the
        # AST walk pins the actual try/except shape.
        tree = ast.parse(self._dragdrop_src)
        targets = ("copyDir", "removeDir")
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef):
                continue
            if node.name not in targets:
                continue
            sees_permerr = False
            for sub in ast.walk(node):
                if not isinstance(sub, ast.ExceptHandler):
                    continue
                exc_type = sub.type
                names = []
                if isinstance(exc_type, ast.Tuple):
                    for elt in exc_type.elts:
                        if isinstance(elt, ast.Name):
                            names.append(elt.id)
                        elif isinstance(elt, ast.Attribute):
                            names.append(elt.attr)
                elif isinstance(exc_type, ast.Name):
                    names.append(exc_type.id)
                if "PermissionError" in names:
                    sees_permerr = True
                    break
            self.assertTrue(
                sees_permerr,
                "AST guard: {} MUST include PermissionError "
                "in at least one except clause's exception "
                "tuple (lesson #6).".format(node.name))

    def test_PERMANENT_j_install_py_pattern_unchanged(self):
        # Cross-installer parity: install.py's _remove_tree +
        # _copy_tree pattern MUST stay the source-of-truth.
        # dragDropInstaller mirrors it; if install.py removed
        # its retry loop in a future refactor, dragDropInstaller
        # would drift.
        self.assertIn(
            "def _remove_tree", self._install_src,
            "install.py MUST keep _remove_tree as the canonical "
            "defensive helper pattern that dragDropInstaller "
            "mirrors.")
        self.assertIn(
            "def _copy_tree", self._install_src,
            "install.py MUST keep _copy_tree similarly.")
        self.assertIn(
            "S_IWRITE", self._install_src,
            "install.py MUST keep the chmod-S_IWRITE recovery — "
            "the dragDropInstaller mirror only makes sense if "
            "the source-of-truth has it too.")


# ----------------------------------------------------------------------
# Mock E2E — runtime behaviour with PermissionError injection.
# ----------------------------------------------------------------------


class TestM_P0_DRAGDROP_PERMERR_RETRY_RuntimeBehavior(
        unittest.TestCase):

    # ----- removeDir branches ---------------------------------------

    def test_removedir_succeeds_after_one_permerr(self):
        # Simulate the user repro: rmtree raises PermissionError
        # the first time, succeeds on the second. removeDir MUST
        # retry and ultimately return True.
        dragdrop = _import_dragdrop()
        attempts = {"count": 0}

        def _flaky_rmtree(path, **kw):
            attempts["count"] += 1
            if attempts["count"] == 1:
                raise PermissionError(
                    "Maya still holds the .mll handle")
            # Second call succeeds.

        with mock.patch("os.path.isdir", return_value=True):
            with mock.patch("shutil.rmtree", side_effect=_flaky_rmtree):
                with mock.patch("time.sleep"):  # don't actually wait
                    result = dragdrop.removeDir("/fake/RBFtools")
        self.assertTrue(
            result,
            "removeDir MUST return True after the retry loop "
            "absorbs the first PermissionError.")
        self.assertEqual(
            attempts["count"], 2,
            "Exactly 2 attempts expected (1 fail + 1 success); "
            "got {}.".format(attempts["count"]))

    def test_removedir_succeeds_after_two_permerr(self):
        # Edge: the retry loop has 3 attempts total. Two
        # PermissionErrors followed by a success MUST still
        # return True.
        dragdrop = _import_dragdrop()
        attempts = {"count": 0}

        def _flaky_rmtree(path, **kw):
            attempts["count"] += 1
            if attempts["count"] < 3:
                raise PermissionError("still locked")

        with mock.patch("os.path.isdir", return_value=True):
            with mock.patch("shutil.rmtree", side_effect=_flaky_rmtree):
                with mock.patch("time.sleep"):
                    result = dragdrop.removeDir("/fake/path")
        self.assertTrue(result)
        self.assertEqual(attempts["count"], 3)

    def test_removedir_fails_cleanly_after_three_permerr(self):
        # Worst case: every attempt fails. removeDir MUST return
        # False (NOT raise) so the calling drag-drop dispatcher
        # can surface a clean error to the user.
        dragdrop = _import_dragdrop()
        with mock.patch("os.path.isdir", return_value=True):
            with mock.patch(
                    "shutil.rmtree",
                    side_effect=PermissionError("locked forever")):
                with mock.patch("time.sleep"):
                    try:
                        result = dragdrop.removeDir("/fake/path")
                    except PermissionError:
                        self.fail(
                            "removeDir MUST NOT propagate "
                            "PermissionError even after 3 "
                            "failed retries.")
        self.assertFalse(
            result,
            "removeDir MUST return False on terminal failure.")

    def test_removedir_idempotent_when_path_missing(self):
        # Path already gone -> fast-return True; rmtree never
        # invoked.
        dragdrop = _import_dragdrop()
        with mock.patch("os.path.isdir", return_value=False):
            with mock.patch("shutil.rmtree") as rm:
                result = dragdrop.removeDir("/already/gone")
        self.assertTrue(result)
        rm.assert_not_called()

    # ----- copyDir branches -----------------------------------------

    def test_copydir_succeeds_after_one_permerr(self):
        # User repro mirror on the copy side.
        dragdrop = _import_dragdrop()
        attempts = {"count": 0}

        def _flaky_copytree(src, dst):
            attempts["count"] += 1
            if attempts["count"] == 1:
                raise PermissionError(
                    "destination still holds residue")

        with mock.patch("shutil.copytree", side_effect=_flaky_copytree):
            with mock.patch("os.path.isdir", return_value=False):
                with mock.patch("time.sleep"):
                    result = dragdrop.copyDir(
                        "/fake/src", "/fake/dst")
        self.assertTrue(result)
        self.assertEqual(attempts["count"], 2)

    def test_copydir_clears_partial_destination_between_retries(self):
        # When the first copytree partially populates the dest,
        # the second attempt would fail with FileExistsError
        # unless we clear it. Confirm the mid-retry rmtree is
        # invoked.
        dragdrop = _import_dragdrop()
        copytree_calls = {"count": 0}
        rmtree_paths = []

        def _flaky_copytree(src, dst):
            copytree_calls["count"] += 1
            if copytree_calls["count"] == 1:
                raise PermissionError("partial copy then fail")

        def _spy_rmtree(path, **kw):
            rmtree_paths.append(path)

        with mock.patch("shutil.copytree", side_effect=_flaky_copytree):
            with mock.patch("os.path.isdir", return_value=True):
                with mock.patch(
                        "shutil.rmtree", side_effect=_spy_rmtree):
                    with mock.patch("time.sleep"):
                        result = dragdrop.copyDir(
                            "/fake/src", "/fake/dst")
        self.assertTrue(result)
        # Inter-retry rmtree fired against the destination.
        self.assertIn(
            "/fake/dst", rmtree_paths,
            "copyDir MUST rmtree the destination between "
            "retries; got rmtree calls on: {}".format(
                rmtree_paths))

    def test_copydir_fails_cleanly_after_three_permerr(self):
        dragdrop = _import_dragdrop()
        with mock.patch(
                "shutil.copytree",
                side_effect=PermissionError("never unlocks")):
            with mock.patch("os.path.isdir", return_value=False):
                with mock.patch("time.sleep"):
                    try:
                        result = dragdrop.copyDir(
                            "/fake/src", "/fake/dst")
                    except PermissionError:
                        self.fail(
                            "copyDir MUST NOT propagate "
                            "PermissionError after 3 retries.")
        self.assertFalse(result)

    def test_copydir_succeeds_first_try_no_retry_overhead(self):
        # Sanity: when the copy works the first time, no retry
        # loop overhead is incurred. The test ensures the happy
        # path is bit-for-bit equivalent to the legacy contract.
        dragdrop = _import_dragdrop()
        with mock.patch("shutil.copytree") as ct:
            with mock.patch("os.path.isdir", return_value=False):
                result = dragdrop.copyDir(
                    "/fake/src", "/fake/dst")
        self.assertTrue(result)
        self.assertEqual(
            ct.call_count, 1,
            "Successful copy MUST invoke copytree exactly once.")


if __name__ == "__main__":
    unittest.main()
