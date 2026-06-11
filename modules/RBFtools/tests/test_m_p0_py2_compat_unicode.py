# -*- coding: utf-8 -*-
"""M_P0_PY2_COMPAT_UNICODE (2026-05-01) — eliminate ``str(...)``
coercions on values that may carry non-ASCII unicode.

Bug surface (Maya 2022 py2 mode):
  Calls like ``str(u"中文")`` go through Python 2's ASCII codec
  and raise UnicodeEncodeError. When this fires inside
  _retranslate_all() — which loops every translatable widget —
  the loop aborts mid-way, which is exactly why the user saw
  "only some labels switch language" after toggling EN ↔ ZH.

  In help_button._show_bubble's import path, the same family of
  errors caused a SyntaxError on first hover (``u"... — ★ ..."``
  bytes were misinterpreted by py2 because the user-installed
  copy on Maya 2022 lacked the utf-8 coding declaration that
  the repo file already carries).

Fixes (8 call sites across 4 files):
  * driver_rotate_order_editor.set_label / set_empty_hint /
    set_driver_sources list-comp
  * tabbed_source_editor.set_node_name / _tab_node both branches
  * bone_data_widgets.BoneDataGroupBox.__init__
  * main_window._gather_routed_targets driver+driven list-comps

Pattern: ``str(x or "")`` -> ``x or ""``. Qt accepts unicode and
str interchangeably; the falsy → "" semantics are preserved.

PERMANENT GUARD T_M_P0_PY2_COMPAT_UNICODE prevents the pattern
from creeping back into UI code paths.
"""

from __future__ import absolute_import

import os
import re
import unittest


_REPO_ROOT = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..")
)
_UI_ROOT = os.path.join(
    _REPO_ROOT, "modules", "RBFtools", "scripts", "RBFtools", "ui")


def _iter_py(root):
    out = []
    for dp, _, fs in os.walk(root):
        for f in fs:
            if f.endswith(".py"):
                out.append(os.path.join(dp, f))
    return out


def _read(p):
    with open(p, "r", encoding="utf-8") as fh:
        return fh.read()


def _strip_strings_and_comments(src):
    """Crude lexer: replace string-literal contents and comments with
    spaces so source-scan greps don't trip on documentation /
    history-comment occurrences of ``str(...)``."""
    out = []
    i = 0
    n = len(src)
    while i < n:
        ch = src[i]
        if ch == "#":
            # Comment to end of line.
            j = src.find("\n", i)
            if j < 0:
                j = n
            out.append(" " * (j - i))
            i = j
            continue
        if ch in ('"', "'"):
            # Detect triple quote.
            if src[i:i + 3] in ('"""', "'''"):
                quote = src[i:i + 3]
                j = src.find(quote, i + 3)
                if j < 0:
                    j = n
                else:
                    j += 3
                out.append(" " * (j - i))
                i = j
                continue
            # Single-line string. Scan to matching unescaped quote.
            quote = ch
            j = i + 1
            while j < n and src[j] != quote:
                if src[j] == "\\" and j + 1 < n:
                    j += 2
                    continue
                if src[j] == "\n":
                    break
                j += 1
            if j < n and src[j] == quote:
                j += 1
            out.append(" " * (j - i))
            i = j
            continue
        out.append(ch)
        i += 1
    return "".join(out)


class T_M_P0_PY2_COMPAT_UNICODE(unittest.TestCase):
    """PERMANENT GUARD — DO NOT REMOVE."""

    # ---------- no str() over text-ish locals --------------------

    def test_PERMANENT_a_no_str_coerce_on_text_args_in_ui(self):
        # ``str(text or "")`` / ``str(name or "...")`` /
        # ``str(label or ...)`` / ``str(title or ...)`` /
        # ``str(node or ...)`` / ``str(msg or ...)`` patterns are
        # forbidden inside scripts/RBFtools/ui/.
        # Strip strings + comments first so doc-history mentions
        # of the forbidden pattern (this very file's docstring,
        # any commit-history comment) don't trip the guard.
        offenders = []
        bad_re = re.compile(
            r"\bstr\(\s*(text|label|title|name|msg|tip|hint|node|"
            r"bone_name|a|n|content)\b[^)]*\bor\b")
        for p in _iter_py(_UI_ROOT):
            code = _strip_strings_and_comments(_read(p))
            for m in bad_re.finditer(code):
                offenders.append(
                    (os.path.relpath(p, _UI_ROOT),
                     code[:m.start()].count("\n") + 1,
                     m.group(0)))
        self.assertFalse(
            offenders,
            "py2 unsafe str(<text> or ...) coercion found in UI "
            "code (str(u'中文') raises UnicodeEncodeError under "
            "mayapy2):\n  "
            + "\n  ".join("{}:{}  {}".format(p, ln, s)
                          for p, ln, s in offenders))

    # ---------- every UI .py keeps a utf-8 coding header ---------

    def test_PERMANENT_b_ui_files_have_utf8_coding_header(self):
        # Files in ui/ commonly contain Chinese / em-dash chars in
        # docstrings or u"..." literals. py2 requires an explicit
        # coding declaration in the first two lines or it parses
        # the file as ASCII and raises SyntaxError on the first
        # non-ASCII byte (the help_texts.py:464 traceback the user
        # reported was exactly this).
        bad = []
        for p in _iter_py(_UI_ROOT):
            with open(p, "rb") as fh:
                head = fh.read(200)
            head_lines = head.split(b"\n", 3)[:2]
            has = any(
                b"coding" in ln and (b"utf-8" in ln or b"utf8" in ln)
                for ln in head_lines)
            if not has:
                # Only flag files that actually contain non-ASCII.
                with open(p, "rb") as fh:
                    raw = fh.read()
                if any(b > 0x7F for b in raw):
                    bad.append(os.path.relpath(p, _UI_ROOT))
        self.assertFalse(
            bad, "UI files with non-ASCII content but missing "
            "``# -*- coding: utf-8 -*-`` header (py2 SyntaxError "
            "risk): " + str(bad))

    # ---------- specific call-site fixes locked in ---------------

    def test_PERMANENT_c_driver_rotate_order_editor_no_str(self):
        # Read raw — assertions below rely on the literal ``""``
        # string contents that the lexer in (a) blanks out.
        p = os.path.join(
            _UI_ROOT, "widgets", "driver_rotate_order_editor.py")
        src = _read(p)
        self.assertIn("self._label_text = text or \"\"", src)
        self.assertIn("self._empty_hint_text = text or \"\"", src)
        self.assertIn(
            "[(n or \"\") for n in (names or [])]", src,
            "set_driver_sources MUST normalise names via "
            "``[(n or '') for n in (names or [])]`` (no str()).")

    def test_PERMANENT_d_tabbed_source_editor_no_str(self):
        p = os.path.join(
            _UI_ROOT, "widgets", "tabbed_source_editor.py")
        src = _read(p)
        self.assertIn("self._node_name = name or \"\"", src)
        self.assertIn("return content.node_name() or \"\"", src)

    def test_PERMANENT_e_bone_data_widgets_no_str(self):
        p = os.path.join(_UI_ROOT, "widgets", "bone_data_widgets.py")
        src = _read(p)
        self.assertIn(
            "self._bone_name = bone_name or \"<unset>\"", src,
            "BoneDataGroupBox.__init__ MUST normalise bone_name "
            "via ``bone_name or '<unset>'`` (no str() encode).")

    def test_PERMANENT_f_main_window_gather_no_str(self):
        p = os.path.join(_UI_ROOT, "main_window.py")
        src = _read(p)
        body = src.split("def _gather_routed_targets(self):", 1)
        self.assertEqual(
            len(body), 2,
            "_gather_routed_targets must exist in main_window.py.")
        body = body[1].split("\n    def ", 1)[0]
        self.assertIn("(node or \"\")", body)
        # str() coercion would re-introduce the py2 encode error.
        self.assertNotRegex(
            body, r"\bstr\(\s*node\b")
        self.assertNotRegex(
            body, r"\bstr\(\s*a\s*\)")


if __name__ == "__main__":
    unittest.main()
