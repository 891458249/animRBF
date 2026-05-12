# -*- coding: utf-8 -*-
"""sync_2022_from_2025.py -- regenerate scripts_2022/ from scripts/.

M_P0_MAYA_2022_FROM_SCRATCH Phase 11 implementation.

Strategy pivot (2026-05-12): scripts_2022/ is derived ENTIRELY from
scripts/ (the Maya 2025 path) treated as the single source of truth.
No bytes from the prior scripts_2022/ tree are consulted; this script
is the only writer.

Output:
  modules/RBFtools/scripts_2022/   -- byte-level 100% ASCII, py2+py3
                                       compatible, PySide2 hard-pinned.

Usage:
    python tools/sync_2022_from_2025.py            # regenerate
    python tools/sync_2022_from_2025.py --check    # drift detector

Idempotent + deterministic -- two consecutive runs produce identical
output. The drift detector relies on this.

------------------------------------------------------------------
Rule set (Phase 11 R1-R10, brief sec.2)
------------------------------------------------------------------

R1  PEP 263 coding declaration on line 1 (or line 2 after shebang)
    is `# -*- coding: utf-8 -*-` for every .py file. Belt + suspenders
    -- even when the file body is pure ASCII after R2/R3.

R2  Non-ASCII source bytes in STRING tokens promoted to `\\uXXXX`
    escapes with auto-injection of `u` prefix (skipped for `r`/`rb`).
    Triple-quoted docstrings receive the same treatment (R6 below is
    the explicit case of R2 applied to docstrings).

R3  Non-ASCII source bytes in COMMENT tokens transliterated to ASCII
    visual equivalents (em dash -> --, Greek letters spelled out, etc.)
    via a deterministic codepoint map.

R4  isinstance(x, str) -> isinstance(x, _STR_TYPES); the helper
    `_STR_TYPES` is auto-injected into each file that uses it, placed
    after the coding decl + docstring + any `from __future__` import
    so that module-load-time uses are safe.

R5  ui/compat.py is REPLACED WHOLESALE with a PySide2 hard-pinned
    version. Maya 2022 has no PySide6 / shiboken6 at all, so the
    try-PySide6 / fall-back-PySide2 dispatch in scripts/ produces a
    spurious ImportError at every module load. The replacement removes
    that dispatch and statically pins PySide2 + shiboken2, while
    keeping the no-op forward-compat patches (QAction / QShortcut /
    QActionGroup) for code-symmetry with scripts/.

R6  Triple-quoted docstrings: same transform as R2 (handled by the
    tokenize-based pass, which sees a docstring as a STRING token).
    Listed separately in the brief because the failure mode in py2
    is specific -- a triple-quoted string containing literal non-ASCII
    without a `u` prefix decodes byte-by-byte instead of as Unicode.

R7  help_button.py: wrap the lazy `from RBFtools.ui.help_texts import
    get_help_text` call sites in a module-level try/except so that a
    bad help_texts.py source can never crash the UI. After R2/R3 the
    help_texts.py source is pure ASCII so this never triggers in
    normal operation -- belt + suspenders.

R8  (audit only) verify Python 2/3 cross-compat conventions already
    present in scripts/ are preserved: `from __future__ import
    absolute_import`, `super(Cls, self)` two-arg form, `__slots__`
    instead of dataclass, .format() instead of f-string, explicit
    encoding= on open().

R9  (audit only -- Phase 11C smoke test) verify cmds API calls used
    by scripts_2022 are documented to exist on Maya 2022. Carried out
    by tools/audit_phase11_maya2022_smoke.py at deploy time.

R10 (audit only -- Phase 11D dual-build verify) confirm both .mll
    artefacts contain the M_P0_RBF_COLUMN_RANK and
    M_P0_DISCONNECT_SCALE fix strings. Carried out by the Phase 11D
    strings + diff pipeline.

------------------------------------------------------------------
Phase 11 differences vs Phase 7 sync
------------------------------------------------------------------

  * Phase 7 R5 ("help_button defensive") -> Phase 11 R7. Renumber only.
  * Phase 11 R5 is NEW: wholesale compat.py replacement.
  * Phase 11 R6 is a docstring-of-R2 rather than a separate transform.
  * Phase 11 R10 lives outside the sync script (Phase 11D step).

Phase 7's sync ran on Maya 2025 source dual-binding-aware; Phase 11
sync now assumes scripts_2022/ targets Maya 2022 only, so compat.py
no longer needs the PySide6 fallback. The core transformation engine
(tokenize-based STRING/COMMENT rewriter) is reused unchanged because
it is byte-perfect and well-tested.
"""
from __future__ import absolute_import, print_function

import argparse
import io
import os
import re
import shutil
import sys
import tokenize

# ----------------------------------------------------------------------
# Paths (relative to repo root which must be the cwd when invoking)
# ----------------------------------------------------------------------
SRC_DIR = os.path.join("modules", "RBFtools", "scripts")
DST_DIR = os.path.join("modules", "RBFtools", "scripts_2022")

# ----------------------------------------------------------------------
# R2 / R6 -- STRING token transformer
# ----------------------------------------------------------------------

_STRING_PREFIX_RE = re.compile(
    r"^([uUbBrRfF]{0,3})(['\"])", flags=re.DOTALL)

_XHH_RE = re.compile(r"\\x([0-9a-fA-F]{2})")


def _is_raw_prefix(prefix):
    return "r" in prefix.lower()


def _is_bytes_prefix(prefix):
    return "b" in prefix.lower()


def _merge_utf8_escapes(body):
    """Find consecutive ``\\xHH`` byte escapes whose HH > 0x7F and merge
    them as UTF-8 if they form a valid multi-byte sequence.

    Replace each merged sequence with the corresponding ``\\uXXXX`` (or
    ``\\UXXXXXXXX`` if > 0xFFFF) escape. Lone high bytes that are not
    part of a UTF-8 sequence become ``\\u00HH`` (Latin-1 codepoint).
    """
    pieces = []
    pos = 0
    for m in _XHH_RE.finditer(body):
        if m.start() > pos:
            pieces.append(("lit", body[pos:m.start()]))
        pieces.append(("xhh", int(m.group(1), 16)))
        pos = m.end()
    if pos < len(body):
        pieces.append(("lit", body[pos:]))

    out = []
    i = 0
    while i < len(pieces):
        kind, val = pieces[i]
        if kind == "lit":
            out.append(val)
            i += 1
            continue
        if val < 0x80:
            out.append("\\x{0:02x}".format(val))
            i += 1
            continue
        run = [val]
        j = i + 1
        while j < len(pieces) and pieces[j][0] == "xhh" and pieces[j][1] >= 0x80:
            run.append(pieces[j][1])
            j += 1
        encoded_run = []
        k = 0
        while k < len(run):
            lead = run[k]
            if 0xC2 <= lead <= 0xDF and k + 1 < len(run) and 0x80 <= run[k + 1] <= 0xBF:
                cont = run[k + 1]
                cp = ((lead & 0x1F) << 6) | (cont & 0x3F)
                encoded_run.append(cp)
                k += 2
            elif (0xE0 <= lead <= 0xEF
                    and k + 2 < len(run)
                    and 0x80 <= run[k + 1] <= 0xBF
                    and 0x80 <= run[k + 2] <= 0xBF):
                cp = ((lead & 0x0F) << 12) | ((run[k + 1] & 0x3F) << 6) | (run[k + 2] & 0x3F)
                encoded_run.append(cp)
                k += 3
            elif (0xF0 <= lead <= 0xF4
                    and k + 3 < len(run)
                    and 0x80 <= run[k + 1] <= 0xBF
                    and 0x80 <= run[k + 2] <= 0xBF
                    and 0x80 <= run[k + 3] <= 0xBF):
                cp = (((lead & 0x07) << 18)
                      | ((run[k + 1] & 0x3F) << 12)
                      | ((run[k + 2] & 0x3F) << 6)
                      | (run[k + 3] & 0x3F))
                encoded_run.append(cp)
                k += 4
            else:
                encoded_run.append(lead)
                k += 1
        for cp in encoded_run:
            if cp <= 0xFFFF:
                out.append("\\u{0:04x}".format(cp))
            else:
                out.append("\\U{0:08x}".format(cp))
        i = j
    return "".join(out)


def _ascii_escape_string_token(tok_string):
    """R2 + R6 applied to a single STRING token. Returns an equivalent
    string literal whose source bytes are pure ASCII; the runtime value
    is unchanged.
    """
    m = _STRING_PREFIX_RE.match(tok_string)
    if not m:
        return tok_string
    prefix = m.group(1)
    quote_char = m.group(2)
    after_prefix = tok_string[len(prefix):]
    if after_prefix.startswith(quote_char * 3):
        quote = quote_char * 3
    else:
        quote = quote_char
    body = after_prefix[len(quote):-len(quote)]

    if _is_raw_prefix(prefix):
        if not any(ord(c) > 127 for c in body):
            return tok_string
        return _split_raw_string_with_unicode(prefix, quote, body)

    new_body = _merge_utf8_escapes(body)
    has_non_ascii = any(ord(c) > 127 for c in new_body)
    has_unicode_escape = bool(
        re.search(r'(?<!\\)(?:\\\\)*\\[uU][0-9a-fA-F]{4}', new_body)
    )

    if has_non_ascii:
        escaped = []
        for c in new_body:
            cp = ord(c)
            if cp < 128:
                escaped.append(c)
            elif cp <= 0xFFFF:
                escaped.append("\\u{0:04x}".format(cp))
            else:
                escaped.append("\\U{0:08x}".format(cp))
        new_body = "".join(escaped)

    if (has_non_ascii or has_unicode_escape) and not (
            _is_bytes_prefix(prefix) or "u" in prefix.lower()):
        prefix = "u" + prefix

    return prefix + quote + new_body + quote


def _split_raw_string_with_unicode(prefix, quote, body):
    out = []
    cur = []
    for ch in body:
        if ord(ch) < 128:
            cur.append(ch)
        else:
            if cur:
                out.append(prefix + quote + "".join(cur) + quote)
                cur = []
            cp = ord(ch)
            if cp <= 0xFFFF:
                u_escape = "\\u{0:04x}".format(cp)
            else:
                u_escape = "\\U{0:08x}".format(cp)
            if _is_bytes_prefix(prefix):
                cur.append("?")
            else:
                bridge_quote = '"' if quote != '"' else "'"
                out.append("u" + bridge_quote + u_escape + bridge_quote)
    if cur:
        out.append(prefix + quote + "".join(cur) + quote)
    return " ".join(out)


# ----------------------------------------------------------------------
# R3 -- COMMENT transliteration
# ----------------------------------------------------------------------

_COMMENT_MAP = {
    u"—": "--",
    u"–": "-",
    u"−": "-",
    u"·": "*",
    u"•": "*",
    u"★": "*",
    u"☆": "*",
    u"°": " deg",
    u"²": "^2",
    u"³": "^3",
    u"×": "x",
    u"÷": "/",
    u"√": "sqrt",
    u"∞": "inf",
    u"≈": "~=",
    u"≠": "!=",
    u"≤": "<=",
    u"≥": ">=",
    u"→": "->",
    u"←": "<-",
    u"±": "+/-",
    u"«": "<<",
    u"»": ">>",
    u"‘": "'",
    u"’": "'",
    u"“": "\"",
    u"”": "\"",
    u"…": "...",
    u"φ": "phi",
    u"θ": "theta",
    u"π": "pi",
    u"λ": "lambda",
    u"α": "alpha",
    u"β": "beta",
    u"γ": "gamma",
    u"σ": "sigma",
    u"ρ": "rho",
    u"μ": "mu",
    u"τ": "tau",
    u"ω": "omega",
    u"Δ": "Delta",
    u"Σ": "Sigma",
    u"Ω": "Omega",
    u"Φ": "Phi",
    u"§": "sec.",
    u"¶": "para",
}


def _ascii_transliterate_comment(comment):
    out = []
    for ch in comment:
        if ord(ch) < 128:
            out.append(ch)
        elif ch in _COMMENT_MAP:
            out.append(_COMMENT_MAP[ch])
        else:
            out.append("?")
    return "".join(out)


# ----------------------------------------------------------------------
# R4 -- isinstance(x, str) -> isinstance(x, _STR_TYPES) + helper
# ----------------------------------------------------------------------

_ISINSTANCE_STR_RE = re.compile(
    r"isinstance\(\s*([^,()]+?)\s*,\s*str\s*\)")

_STR_TYPES_HELPER = (
    "# M_P0_MAYA_2022_FROM_SCRATCH R4: py2 unicode / py3 str dual\n"
    "# accept tuple. Auto-injected by tools/sync_2022_from_2025.py.\n"
    "try:\n"
    "    _STR_TYPES = (str, unicode)  # noqa: F821 -- py2-only name\n"
    "except NameError:\n"
    "    _STR_TYPES = (str,)\n"
)


def _apply_isinstance_rule(src):
    new_src = _ISINSTANCE_STR_RE.sub(r"isinstance(\1, _STR_TYPES)", src)
    if "_STR_TYPES" in new_src and "_STR_TYPES = (str, unicode)" not in new_src:
        new_src = _inject_str_types_helper(new_src)
    return new_src


def _inject_str_types_helper(src):
    """Insert the ``_STR_TYPES`` helper at the EARLIEST safe position:
    after the coding declaration, after any leading module docstring,
    and after any ``from __future__`` import. This ordering ensures
    every isinstance(x, _STR_TYPES) call -- including module-load-time
    ones via default arguments or class attributes -- finds the helper
    already bound.
    """
    import ast as _ast
    try:
        tree = _ast.parse(src)
    except SyntaxError:
        return _prepend_helper_after_decl(src)

    lines = src.split("\n")

    insert_at = 0
    if lines and lines[0].startswith("#!"):
        insert_at = 1
    if (insert_at < len(lines)
            and "coding" in lines[insert_at]
            and lines[insert_at].lstrip().startswith("#")):
        insert_at += 1

    if tree.body:
        first = tree.body[0]
        is_docstring = (
            isinstance(first, _ast.Expr)
            and isinstance(getattr(first, "value", None), _ast.Constant)
            and isinstance(first.value.value, str))
        if not is_docstring:
            is_docstring = (
                isinstance(first, _ast.Expr)
                and first.value.__class__.__name__ == "Str")
        if is_docstring:
            end = getattr(first, "end_lineno", first.lineno)
            insert_at = max(insert_at, end)

    for node in tree.body:
        if (isinstance(node, _ast.ImportFrom)
                and node.module == "__future__"):
            end_line = getattr(node, "end_lineno", node.lineno)
            insert_at = max(insert_at, end_line)

    helper_lines = ["", ""] + _STR_TYPES_HELPER.rstrip("\n").split("\n") + [""]
    lines[insert_at:insert_at] = helper_lines
    return "\n".join(lines)


def _prepend_helper_after_decl(src):
    lines = src.split("\n")
    decl_at = 0
    for i in range(min(2, len(lines))):
        if "coding" in lines[i] and lines[i].lstrip().startswith("#"):
            decl_at = i + 1
            break
    helper_lines = [""] + _STR_TYPES_HELPER.rstrip("\n").split("\n") + [""]
    lines[decl_at:decl_at] = helper_lines
    return "\n".join(lines)


# ----------------------------------------------------------------------
# R5b -- shiboken2/6 try/except flattener for main_window.py
# ----------------------------------------------------------------------
#
# scripts/RBFtools/ui/main_window.py:_is_alive() wraps the shiboken
# import in a try (shiboken2) / except ImportError (shiboken6) so the
# same source serves both Maya 2022 and Maya 2025. On Maya 2022 the try
# always succeeds and the except branch is dead code -- but the source
# still contains a `from shiboken6 import isValid` line, which the
# Phase 11C smoke test reports as a residual PySide6 reference. The
# brief mandates 0 PySide6 imports in scripts_2022 (sec.3 Phase 11C
# bullet 5), so R5b strips the fallback to keep the bytecode 100%
# Maya 2022.

_MAIN_WINDOW_SHIBOKEN_TRY = (
    "    try:\n"
    "        # shiboken: isValid works for both PySide2 and PySide6\n"
    "        from shiboken2 import isValid\n"
    "    except ImportError:\n"
    "        from shiboken6 import isValid\n"
)

_MAIN_WINDOW_SHIBOKEN_FLAT = (
    "    # shiboken: PySide2 hard-pin for Maya 2022 (R5b -- the\n"
    "    # scripts/ source has an `except ImportError: from shiboken6\n"
    "    # ...` fallback for Maya 2025; that branch is dead code on\n"
    "    # Maya 2022 and stripped here to satisfy the Phase 11C smoke\n"
    "    # test's `0 PySide6/shiboken6 imports` requirement).\n"
    "    from shiboken2 import isValid\n"
)


def _apply_main_window_rule(src):
    if _MAIN_WINDOW_SHIBOKEN_TRY in src:
        src = src.replace(
            _MAIN_WINDOW_SHIBOKEN_TRY, _MAIN_WINDOW_SHIBOKEN_FLAT, 1)
    return src


# ----------------------------------------------------------------------
# R5 -- wholesale compat.py replacement (Maya 2022 PySide2 hard-pin)
# ----------------------------------------------------------------------

_COMPAT_PY_PHASE11_R5 = (
    '# -*- coding: utf-8 -*-\n'
    'u"""Qt compatibility shim -- PySide2 hard-pin for Maya 2022.\n'
    '\n'
    'M_P0_MAYA_2022_FROM_SCRATCH Phase 11 R5: this file replaces the\n'
    'scripts/RBFtools/ui/compat.py try-PySide6 / fall-back-PySide2\n'
    'dispatch with a direct PySide2 import. Maya 2022 has no PySide6 /\n'
    'shiboken6, so the original try block always raised ImportError;\n'
    'removing it eliminates a spurious exception at every module load\n'
    'and makes the import path easy to audit.\n'
    '\n'
    'The forward-compat patches (QAction, QShortcut, QActionGroup) are\n'
    'kept as no-ops in Qt5: the if-not-hasattr guards never fire because\n'
    'PySide2 already exposes those classes on QtWidgets. The block is\n'
    'retained for code symmetry with scripts/ so call sites can use\n'
    'QtWidgets.QAction unconditionally regardless of which scripts tree\n'
    'is on sys.path.\n'
    '\n'
    'Auto-generated by tools/sync_2022_from_2025.py -- do not hand-edit.\n'
    '"""\n'
    'from __future__ import absolute_import\n'
    '\n'
    '# ------------------------------------------------------------------\n'
    '# PySide2 hard-pin (Maya 2022)\n'
    '# ------------------------------------------------------------------\n'
    '\n'
    'from PySide2 import QtWidgets, QtCore, QtGui   # noqa: F401\n'
    'from shiboken2 import wrapInstance              # noqa: F401\n'
    'BINDING = "PySide2"\n'
    '\n'
    '# ------------------------------------------------------------------\n'
    '# Convenience aliases\n'
    '# ------------------------------------------------------------------\n'
    '\n'
    'Signal   = QtCore.Signal\n'
    'Slot     = QtCore.Slot\n'
    'Property = QtCore.Property\n'
    '\n'
    '# ------------------------------------------------------------------\n'
    '# Forward-compat patches (no-ops on PySide2; kept for code symmetry\n'
    '# with scripts/ so call sites can always do QtWidgets.QAction).\n'
    '# ------------------------------------------------------------------\n'
    '\n'
    'if not hasattr(QtWidgets, "QAction"):\n'
    '    QtWidgets.QAction = QtGui.QAction\n'
    'if not hasattr(QtWidgets, "QShortcut"):\n'
    '    QtWidgets.QShortcut = QtGui.QShortcut\n'
    'if not hasattr(QtWidgets, "QActionGroup"):\n'
    '    QtWidgets.QActionGroup = QtGui.QActionGroup\n'
    '\n'
    '# ------------------------------------------------------------------\n'
    '# Maya main window helper\n'
    '# ------------------------------------------------------------------\n'
    '\n'
    'import maya.OpenMayaUI as omui\n'
    '\n'
    '\n'
    'def maya_main_window():\n'
    '    """Return the Maya main window as a QWidget.\n'
    '\n'
    '    Returns None when called outside a GUI session (e.g. mayapy).\n'
    '    """\n'
    '    ptr = omui.MQtUtil.mainWindow()\n'
    '    if ptr is not None:\n'
    '        return wrapInstance(int(ptr), QtWidgets.QWidget)\n'
    '    return None\n'
)


def _is_compat_py(rel_path):
    return rel_path.replace(os.sep, "/").endswith("RBFtools/ui/compat.py")


# ----------------------------------------------------------------------
# R7 -- defensive import in help_button.py
# ----------------------------------------------------------------------

_HELP_BUTTON_PATCH_HEADER = "# M_P0_MAYA_2022_FROM_SCRATCH R7"


def _apply_help_button_rule(src):
    """Wrap the lazy ``from RBFtools.ui.help_texts import get_help_text``
    imports in ``help_button.py`` with a module-level try/except and an
    ASCII-only fallback. Belt-and-suspenders: scripts_2022/help_texts.py
    is pure ASCII after R2, so this fallback never triggers in normal
    operation.
    """
    if _HELP_BUTTON_PATCH_HEADER in src:
        return src

    bs = chr(0x5C)
    warn_escape = bs + "u26a0"
    nl_escape = bs + "n"
    nlnl_escape = nl_escape + nl_escape
    bs_uXXXX = bs + bs + "uXXXX"

    fallback_lines = [
        _HELP_BUTTON_PATCH_HEADER + " (auto-injected): defensive import.",
        "# Module-level try/except so a bad help_texts.py source cannot",
        "# crash the UI. After sync, scripts_2022/help_texts.py is 100%",
        "# ASCII at byte level so this fallback never triggers in normal",
        "# operation -- belt-and-suspenders, not graceful degradation.",
        "try:",
        "    from RBFtools.ui.help_texts import get_help_text as _get_help_text",
        "    _HELP_TEXTS_OK = True",
        "    _HELP_TEXTS_ERR = None",
        "except Exception as _exc:  # noqa: BLE001",
        "    import warnings as _warnings",
        "    _warnings.warn(",
        '        "RBFtools.ui.help_texts failed to import (likely py2 "',
        '        "encoding issue). Help bubbles will show diagnostic "',
        '        "placeholder. Error: {0}".format(_exc),',
        "        RuntimeWarning,",
        "    )",
        "    _HELP_TEXTS_OK = False",
        "    _HELP_TEXTS_ERR = _exc",
        "",
        "    def _get_help_text(key):",
        '        return (',
        '            u"[' + warn_escape + ' RBFtools help_texts.py import "',
        '            u"failed - see Maya Script Editor warning]'
        + nlnl_escape + '"',
        '            u"Error: {0}' + nlnl_escape + '"',
        '            u"Patch ID: M_P0_MAYA_2022_FROM_SCRATCH R7 fallback. "',
        '            u"Re-run tools/sync_2022_from_2025.py to refresh "',
        '            u"scripts_2022 from the canonical scripts/ (Maya "',
        '            u"2025 path). A non-ASCII byte sneaked in without "',
        '            u"a ' + bs_uXXXX + ' escape."',
        '            .format(_HELP_TEXTS_ERR)',
        '        )',
        "",
    ]

    src = src.replace(
        "        bubble = self._get_bubble()\n"
        "        from RBFtools.ui.help_texts import get_help_text\n"
        "        bubble.set_text(get_help_text(self._help_key))\n",
        "        bubble = self._get_bubble()\n"
        "        bubble.set_text(_get_help_text(self._help_key))\n",
    )
    src = src.replace(
        "        bubble = self._get_bubble()\n"
        "        from RBFtools.ui.help_texts import get_help_text\n"
        "        bubble.set_text(get_help_text(self._current_help_key()))\n",
        "        bubble = self._get_bubble()\n"
        "        bubble.set_text(_get_help_text(self._current_help_key()))\n",
    )
    src = src.replace(
        "        if self._pinned and self._bubble is not None and self._bubble.isVisible():\n"
        "            from RBFtools.ui.help_texts import get_help_text\n"
        "            self._bubble.set_text(get_help_text(self._help_key_for_index(idx)))\n",
        "        if self._pinned and self._bubble is not None and self._bubble.isVisible():\n"
        "            self._bubble.set_text(_get_help_text(self._help_key_for_index(idx)))\n",
    )

    anchor = "from RBFtools.ui.compat import QtWidgets, QtCore\n"
    if anchor in src:
        insertion = anchor + "\n" + "\n".join(fallback_lines)
        src = src.replace(anchor, insertion, 1)
    return src


# ----------------------------------------------------------------------
# R1 -- coding declaration
# ----------------------------------------------------------------------

_PEP263_RE = re.compile(r"coding[:=]\s*[-\w.]+")


def _ensure_coding_decl(src):
    lines = src.split("\n")
    head = lines[:2]
    for h in head:
        if h.lstrip().startswith("#") and _PEP263_RE.search(h):
            return src
    decl = "# -*- coding: utf-8 -*-"
    if lines and lines[0].startswith("#!"):
        lines.insert(1, decl)
    else:
        lines.insert(0, decl)
    return "\n".join(lines)


# ----------------------------------------------------------------------
# R8 -- audit-only py3-only syntax scan
# ----------------------------------------------------------------------

_PY3_ONLY_PATTERNS = [
    (re.compile(r'\bf"'), "f-string"),
    (re.compile(r":="), "walrus operator"),
    (re.compile(r"\bnonlocal\b"), "nonlocal keyword"),
    (re.compile(r"\bsuper\(\)"), "super() no-arg form"),
]


def _audit_py3_only_syntax(src, rel_path):
    for pat, label in _PY3_ONLY_PATTERNS:
        if pat.search(src):
            print("WARN: {0}: py3-only syntax found: {1}".format(
                rel_path, label))


# ----------------------------------------------------------------------
# Token-based transform driver
# ----------------------------------------------------------------------

def transform_source(src_bytes, rel_path):
    """Apply R1-R8 to one Python source. Returns transformed bytes
    (pure ASCII).

    R5 (compat.py wholesale replacement) is handled before this function
    is reached; this function operates only on non-compat .py files.

    Output line endings are ALWAYS LF, independent of the source file's
    line endings. This stability matters for the drift detector across
    checkouts with different ``core.autocrlf`` settings.
    """
    src = src_bytes.decode("utf-8")
    src = src.replace("\r\n", "\n").replace("\r", "\n")

    src = _ensure_coding_decl(src)

    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(src).readline))
    except tokenize.TokenizeError as exc:
        raise RuntimeError("tokenize failed in {0}: {1}".format(rel_path, exc))

    new_tokens = []
    for tok in tokens:
        ttype = tok[0]
        tstr = tok[1]
        if ttype == tokenize.STRING:
            new_tokens.append(tok._replace(string=_ascii_escape_string_token(tstr)))
        elif ttype == tokenize.COMMENT:
            new_tokens.append(tok._replace(string=_ascii_transliterate_comment(tstr)))
        else:
            new_tokens.append(tok)

    out_src = _untokenize_preserving_layout(new_tokens, src)
    out_src = _apply_isinstance_rule(out_src)

    if rel_path.replace(os.sep, "/").endswith("ui/widgets/help_button.py"):
        out_src = _apply_help_button_rule(out_src)

    if rel_path.replace(os.sep, "/").endswith("RBFtools/ui/main_window.py"):
        out_src = _apply_main_window_rule(out_src)

    _audit_py3_only_syntax(out_src, rel_path)

    try:
        out_bytes = out_src.encode("ascii")
    except UnicodeEncodeError as exc:
        raise RuntimeError(
            "Non-ASCII byte survived transform in {0}: {1}".format(
                rel_path, exc))

    return out_bytes


def _untokenize_preserving_layout(tokens, original_src):
    src_lines = original_src.split("\n")
    out_lines = list(src_lines)
    edits = []
    for tok in tokens:
        if tok[0] not in (tokenize.STRING, tokenize.COMMENT):
            continue
        start = tok[2]
        end = tok[3]
        new_text = tok[1]
        edits.append((start, end, new_text))

    edits.sort(key=lambda e: (e[0][0], e[0][1]), reverse=True)
    for (srow, scol), (erow, ecol), new_text in edits:
        if srow == erow:
            line = out_lines[srow - 1]
            out_lines[srow - 1] = line[:scol] + new_text + line[ecol:]
        else:
            first = out_lines[srow - 1]
            last = out_lines[erow - 1]
            new_first = first[:scol] + new_text
            new_last = last[ecol:]
            new_block = (new_first + new_last).split("\n")
            out_lines[srow - 1:erow] = new_block
    return "\n".join(out_lines)


# ----------------------------------------------------------------------
# File walker / driver
# ----------------------------------------------------------------------

def _compute_transformed(src_path, rel_path):
    if _is_compat_py(rel_path):
        return _COMPAT_PY_PHASE11_R5.encode("ascii")
    with open(src_path, "rb") as fh:
        src_bytes = fh.read()
    return transform_source(src_bytes, rel_path)


def sync_all(check_only=False, verbose=False):
    """Walk SRC_DIR, transform every .py, mirror non-.py files
    byte-for-byte (with EOL normalised to LF). Return (diffs, py_count,
    other_count).
    """
    diffs = []
    py_count = 0
    other_count = 0

    if not check_only:
        if os.path.exists(DST_DIR):
            shutil.rmtree(DST_DIR)
        os.makedirs(DST_DIR)

    for dirpath, dirnames, filenames in os.walk(SRC_DIR):
        dirnames[:] = [d for d in dirnames if d != "__pycache__"]
        rel = os.path.relpath(dirpath, SRC_DIR)
        dst_dirpath = (DST_DIR if rel == "." else os.path.join(DST_DIR, rel))
        if not check_only and not os.path.exists(dst_dirpath):
            os.makedirs(dst_dirpath)
        for fn in sorted(filenames):
            src_path = os.path.join(dirpath, fn)
            dst_path = os.path.join(dst_dirpath, fn)
            rel_path = os.path.relpath(dst_path, "modules").replace(os.sep, "/")
            if fn.endswith(".py"):
                py_count += 1
                try:
                    expected = _compute_transformed(src_path, rel_path)
                except Exception as exc:
                    diffs.append((dst_path, "transform error: {0}".format(exc)))
                    continue
                if check_only:
                    if not os.path.exists(dst_path):
                        diffs.append((dst_path, "missing"))
                        continue
                    with open(dst_path, "rb") as fh:
                        actual = fh.read()
                    if actual != expected:
                        diffs.append((dst_path, "content differs"))
                else:
                    with open(dst_path, "wb") as fh:
                        fh.write(expected)
                    if verbose:
                        print("WROTE: {0} ({1} bytes)".format(
                            dst_path, len(expected)))
            else:
                other_count += 1
                with open(src_path, "rb") as fh:
                    src_bytes = fh.read()
                expected = src_bytes.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
                if check_only:
                    if not os.path.exists(dst_path):
                        diffs.append((dst_path, "missing"))
                        continue
                    with open(dst_path, "rb") as fh:
                        actual = fh.read()
                    if actual != expected:
                        diffs.append((dst_path, "byte differs"))
                else:
                    with open(dst_path, "wb") as fh:
                        fh.write(expected)
    return diffs, py_count, other_count


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--check", action="store_true",
                   help="drift detector mode (exit 1 on diff, do not write)")
    p.add_argument("--verbose", action="store_true",
                   help="print one line per written file")
    args = p.parse_args()

    diffs, py_count, other_count = sync_all(
        check_only=args.check, verbose=args.verbose)
    if args.check:
        if diffs:
            print("ERROR: scripts_2022/ drift detected vs sync output:")
            for path, reason in diffs:
                print("  ! {0}: {1}".format(path, reason))
            print("Fix: run `python tools/sync_2022_from_2025.py`.")
            sys.exit(1)
        print("PHASE 11 SYNC --check OK: scripts_2022/ matches "
              "({0} py + {1} other files).".format(py_count, other_count))
    else:
        print("PHASE 11 SYNC OK: scripts_2022/ generated "
              "({0} py + {1} other files).".format(py_count, other_count))


if __name__ == "__main__":
    main()
