# -*- coding: utf-8 -*-
"""T_M_P0_BATCH_DEFAULT_TRUE (2026-05-11) PERMANENT guard.

Defends the M_P0_BATCH_DEFAULT_TRUE patch:
``TabbedSourceEditor`` (and its TabbedDriverSourceEditor /
TabbedDrivenSourceEditor subclasses) now default ``_chk_batch`` to
``True`` so multi-driver / multi-driven rigs route Connect /
Disconnect across all tabs by default — the False default left
silent connection drop on multi-tab setups (user repro:
3 driver × 10 driven, 90 expected, 9 actual).

Source-scan / AST-based assertions only — PySide instantiation of
the editor is not available in this test environment (mayapy
fixtures live behind the conftest collection-error gate). The
runtime behaviour (routed_targets() returning N entries when N tabs
+ batch=True, vs 1 entry on single-tab) is exercised in the
existing `routed_targets` widget tests under conftest mayapy.

Per Planner spec, three guard categories:
  a. literal+AST: `_chk_batch.setChecked(True)` is the only
     setChecked-on-_chk_batch in `_TabbedSourceEditorBase._build`
  b. negative: `_chk_batch.setChecked(False)` does not appear
     anywhere in the file (no subclass override re-flips it)
  c. structural: subclasses TabbedDriverSourceEditor +
     TabbedDrivenSourceEditor inherit from _TabbedSourceEditorBase
     and do not define their own `_chk_batch` widget (so the base
     default propagates)
"""
from __future__ import absolute_import, division, print_function

import ast
import io
import os
import unittest


_HERE = os.path.dirname(os.path.abspath(__file__))
_TESTS_DIR = os.path.dirname(_HERE)
_REPO = os.path.dirname(os.path.dirname(os.path.dirname(_TESTS_DIR)))
_TABBED_PY = os.path.join(
    _REPO, "modules", "RBFtools", "scripts", "RBFtools",
    "ui", "widgets", "tabbed_source_editor.py")


def _read(path):
    with io.open(path, "r", encoding="utf-8") as fh:
        return fh.read()


class TestBatchDefaultTrue(unittest.TestCase):
    """Three guards on the M_P0_BATCH_DEFAULT_TRUE patch surface."""

    def test_PERMANENT_a_default_true_literal_present(self):
        """`_chk_batch.setChecked(True)` literal must exist (post-patch)."""
        src = _read(_TABBED_PY)
        self.assertIn(
            "self._chk_batch.setChecked(True)", src,
            "M_P0_BATCH_DEFAULT_TRUE: _TabbedSourceEditorBase._build must "
            "default _chk_batch.setChecked(True). The False default was "
            "the silent-multi-tab-connect-drop bug source.")

    def test_PERMANENT_b_default_false_literal_absent(self):
        """`_chk_batch.setChecked(False)` must NOT appear anywhere
        in the file (would re-introduce the bug if a future refactor
        added a subclass-level override or duplicate base call)."""
        src = _read(_TABBED_PY)
        # Filter out commented lines; the rationale comment may
        # mention "False" as historical context.
        live_lines = [ln for ln in src.splitlines()
                      if "_chk_batch.setChecked(False)" in ln
                      and not ln.lstrip().startswith("#")]
        self.assertEqual(
            live_lines, [],
            "M_P0_BATCH_DEFAULT_TRUE: no live setChecked(False) call on "
            "_chk_batch may exist. Found in lines: {!r}".format(live_lines))

    def test_PERMANENT_c_setchecked_call_in_base_build(self):
        """The setChecked(True) call must live inside the base class
        `_TabbedSourceEditorBase._build` method — verified via AST
        walk so a subclass-level duplicate doesn't pass the guard."""
        src = _read(_TABBED_PY)
        tree = ast.parse(src)
        # Find _TabbedSourceEditorBase class
        base_cls = None
        for node in ast.walk(tree):
            if (isinstance(node, ast.ClassDef)
                    and node.name == "_TabbedSourceEditorBase"):
                base_cls = node
                break
        self.assertIsNotNone(base_cls,
            "_TabbedSourceEditorBase class definition not found.")
        # Find _build method
        build_fn = None
        for child in base_cls.body:
            if (isinstance(child, ast.FunctionDef)
                    and child.name == "_build"):
                build_fn = child
                break
        self.assertIsNotNone(build_fn,
            "_TabbedSourceEditorBase._build method not found.")
        # Walk _build body for `self._chk_batch.setChecked(<bool>)` calls.
        setchecked_calls = []
        for sub in ast.walk(build_fn):
            if not isinstance(sub, ast.Call):
                continue
            f = sub.func
            if (isinstance(f, ast.Attribute)
                    and f.attr == "setChecked"
                    and isinstance(f.value, ast.Attribute)
                    and f.value.attr == "_chk_batch"
                    and isinstance(f.value.value, ast.Name)
                    and f.value.value.id == "self"):
                # Capture the literal arg if it is a Constant bool.
                if (len(sub.args) == 1
                        and isinstance(sub.args[0], ast.Constant)
                        and isinstance(sub.args[0].value, bool)):
                    setchecked_calls.append(sub.args[0].value)
        self.assertEqual(
            setchecked_calls, [True],
            "_TabbedSourceEditorBase._build must call "
            "self._chk_batch.setChecked(True) exactly once; "
            "found arg list: {!r}".format(setchecked_calls))

    def test_PERMANENT_d_subclasses_dont_override_chk_batch(self):
        """TabbedDriverSourceEditor + TabbedDrivenSourceEditor must
        not define their own `_chk_batch` widget — the base default
        must reach both at instantiation time."""
        src = _read(_TABBED_PY)
        tree = ast.parse(src)
        for cls_name in ("TabbedDriverSourceEditor",
                         "TabbedDrivenSourceEditor"):
            cls = None
            for node in ast.walk(tree):
                if (isinstance(node, ast.ClassDef)
                        and node.name == cls_name):
                    cls = node
                    break
            self.assertIsNotNone(cls,
                "{} class not found".format(cls_name))
            # Walk the subclass body for any setChecked on _chk_batch.
            offending = []
            for sub in ast.walk(cls):
                if not isinstance(sub, ast.Call):
                    continue
                f = sub.func
                if (isinstance(f, ast.Attribute)
                        and f.attr == "setChecked"
                        and isinstance(f.value, ast.Attribute)
                        and f.value.attr == "_chk_batch"):
                    offending.append(ast.dump(sub))
            self.assertEqual(
                offending, [],
                "{} must not override _chk_batch.setChecked. "
                "Found: {!r}".format(cls_name, offending))


if __name__ == "__main__":
    unittest.main()
