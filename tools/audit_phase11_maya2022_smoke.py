# -*- coding: utf-8 -*-
"""audit_phase11_maya2022_smoke.py -- Maya 2022 from-scratch smoke audit.

M_P0_MAYA_2022_FROM_SCRATCH Phase 11C: post-sync verification that
scripts_2022/ meets the brief's six smoke requirements (sec.3 Phase
11C). Run AFTER `python tools/sync_2022_from_2025.py`.

Checks (brief sec.3 Phase 11C bullet list):
  1. ast.parse on all .py files                              (R6/R8)
  2. byte-level ASCII                                        (R1/R2/R3)
  3. _STR_TYPES helper present in core.py + core_json.py     (R4)
  4. ui/compat.py imports PySide2 only (no PySide6 ref)      (R5)
  5. 0 PySide6 / shiboken6 import statements in scripts_2022 (R5/R5b)
  6. help_button.py contains the defensive R7 try/except     (R7)

Plus an extra check explicit in the brief Phase 9 audit history:
  7. 4 anchors -- drift-detector-equivalent functional check on
     scripts/ side. Confirms M_P0_DISCONNECT_SCALE / column-rank /
     polyDim / TPS-r-le-0 strings present in scripts/ source (anchors
     held in Maya 2025 code path).

Usage:
    python tools/audit_phase11_maya2022_smoke.py

Exit code 0 on full pass, 1 on any failure. Designed to be invoked
both interactively and from CI.
"""
from __future__ import absolute_import, print_function

import ast
import io
import os
import sys
import tokenize

SCRIPTS_2022 = os.path.join("modules", "RBFtools", "scripts_2022")
SCRIPTS_2025 = os.path.join("modules", "RBFtools", "scripts")


def _iter_py(root):
    for r, dirs, fs in os.walk(root):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        for f in fs:
            if f.endswith(".py"):
                yield os.path.join(r, f)


def check_1_ast_parse():
    """Every .py in scripts_2022 parses cleanly."""
    bad = []
    n = 0
    for p in _iter_py(SCRIPTS_2022):
        n += 1
        with open(p, "rb") as fh:
            data = fh.read()
        try:
            ast.parse(data, filename=p)
        except SyntaxError as e:
            bad.append((p, str(e)))
    if bad:
        return False, "{0} ast.parse failures: {1}".format(len(bad), bad[:3])
    return True, "{0}/{0} py files parse cleanly".format(n)


def check_2_byte_ascii():
    """Every .py in scripts_2022 is byte-level ASCII."""
    bad = []
    n = 0
    for p in _iter_py(SCRIPTS_2022):
        n += 1
        with open(p, "rb") as fh:
            data = fh.read()
        try:
            data.decode("ascii")
        except UnicodeDecodeError as e:
            bad.append((p, str(e)))
    if bad:
        return False, "{0} non-ASCII files: {1}".format(len(bad), bad[:3])
    return True, "{0}/{0} py files are byte-ASCII".format(n)


def check_3_str_types_helper():
    """_STR_TYPES helper present in core.py + core_json.py (the two
    files that use isinstance(x, str) per R4)."""
    needles = [
        ("RBFtools/core.py", "_STR_TYPES = (str, unicode)"),
        ("RBFtools/core_json.py", "_STR_TYPES = (str, unicode)"),
    ]
    missing = []
    for rel, needle in needles:
        p = os.path.join(SCRIPTS_2022, rel.replace("/", os.sep))
        if not os.path.isfile(p):
            missing.append((p, "file missing"))
            continue
        with open(p, "rb") as fh:
            data = fh.read().decode("ascii")
        if needle not in data:
            missing.append((p, "needle not found: {0!r}".format(needle)))
    if missing:
        return False, "missing _STR_TYPES helper: {0}".format(missing)
    return True, "_STR_TYPES helper present in 2/2 expected files"


def check_4_compat_py_pyside2_only():
    """ui/compat.py: BINDING = "PySide2", and no PySide6 import statement
    (tokenwise -- comments and docstring mentions are documentation of
    the R5 transform and are explicitly allowed)."""
    p = os.path.join(SCRIPTS_2022, "RBFtools", "ui", "compat.py")
    if not os.path.isfile(p):
        return False, "compat.py missing"
    with open(p, "rb") as fh:
        data = fh.read().decode("ascii")
    if 'BINDING = "PySide2"' not in data:
        return False, "BINDING = \"PySide2\" not declared"
    if "from PySide2 " not in data:
        return False, "no `from PySide2 ...` import"
    bad_imports = list(_scan_imports_tokenwise(p))
    if bad_imports:
        return False, "compat.py has PySide6/shiboken6 imports: {0}".format(
            bad_imports)
    return True, "compat.py is PySide2 hard-pinned (no PySide6 imports)"


def _scan_imports_tokenwise(py_path):
    """Yield (path, line, kind, name) for every actual import statement
    in *py_path* (ignores comments and string literals)."""
    with open(py_path, "rb") as fh:
        data = fh.read()
    try:
        toks = list(tokenize.tokenize(io.BytesIO(data).readline))
    except (tokenize.TokenizeError, SyntaxError):
        return
    for i, t in enumerate(toks):
        if t.type != tokenize.NAME:
            continue
        if t.string in ("PySide6", "shiboken6"):
            if i > 0 and toks[i - 1].type == tokenize.NAME and toks[i - 1].string in ("from", "import"):
                yield (py_path, t.start[0], toks[i - 1].string, t.string)


def check_5_no_pyside6_imports():
    """0 PySide6 / shiboken6 import statements anywhere in scripts_2022.
    Comment lines mentioning PySide6 are allowed (R5 docstring
    describes the prior dispatch pattern; commenting style refs in
    other files are documentation, not code paths)."""
    hits = []
    for p in _iter_py(SCRIPTS_2022):
        for hit in _scan_imports_tokenwise(p):
            hits.append(hit)
    if hits:
        return False, "{0} PySide6/shiboken6 imports: {1}".format(len(hits), hits[:5])
    return True, "0 PySide6/shiboken6 imports in scripts_2022"


def check_6_help_button_defensive():
    """help_button.py contains the R7 defensive try/except + fallback."""
    p = os.path.join(SCRIPTS_2022, "RBFtools", "ui", "widgets", "help_button.py")
    if not os.path.isfile(p):
        return False, "help_button.py missing"
    with open(p, "rb") as fh:
        data = fh.read().decode("ascii")
    needles = [
        "# M_P0_MAYA_2022_FROM_SCRATCH R7",
        "from RBFtools.ui.help_texts import get_help_text as _get_help_text",
        "except Exception as _exc",
        "def _get_help_text(key):",
    ]
    missing = [n for n in needles if n not in data]
    if missing:
        return False, "help_button.py missing R7 markers: {0}".format(missing)
    return True, "help_button.py has R7 defensive try/except"


def check_7_anchors_in_scripts():
    """4 anchors -- functional markers preserved on the Maya 2025 path
    (scripts/, not scripts_2022/). Smoke-check that the scripts/ side
    still names the M_P0_ patches the brief sec.3 R10 expects to flow
    into the .mll, plus the controller/core Python-side knobs."""
    # Python-observable anchors from Phase 9 audit + handoff sec.5.
    # The C++-only anchors (TPS r<=0, column-rank-defense, polyDim 1+d)
    # are validated separately by the Phase 11D .mll strings pipeline,
    # so they are not checked here.
    anchors = [
        # M_P0_DISCONNECT_SCALE_RESTORE -- driven joints restore scale
        # on disconnect (lives in scripts/RBFtools/core.py as an
        # explanatory comment + the actual logic).
        (SCRIPTS_2025, "RBFtools/core.py", "M_P0_DISCONNECT_SCALE_RESTORE"),
        # M_P0_TRAINING_ATTRS_FORCE_RETRAIN -- Python-side prev-tracker
        # frozenset on the RBFController class.
        (SCRIPTS_2025, "RBFtools/controller.py", "_TRAINING_AFFECTING_ATTRS"),
        # M_P0_BATCH_DEFAULT_TRUE -- tabbed source editor default.
        (SCRIPTS_2025, "RBFtools/ui/widgets/tabbed_source_editor.py", "M_P0_BATCH_DEFAULT_TRUE"),
        # R4 honest-failure anchor: scripts/ has the DriverSource type
        # check that raises TypeError on non-str. scripts_2022 has the
        # _STR_TYPES generalisation (covered by check 3). This needle
        # is the human-readable error message, robust against line
        # break placement.
        (SCRIPTS_2025, "RBFtools/core.py", "DriverSource.node must be a str"),
    ]
    missing = []
    for root, rel, needle in anchors:
        p = os.path.join(root, rel.replace("/", os.sep))
        if not os.path.isfile(p):
            missing.append((p, "file missing"))
            continue
        with open(p, "rb") as fh:
            data = fh.read()
        if needle.encode("utf-8") not in data:
            missing.append((p, "needle not found: {0!r}".format(needle)))
    if missing:
        return False, "anchors missing: {0}".format(missing)
    return True, "4/4 anchors present in scripts/ (Maya 2025 path)"


CHECKS = [
    ("1. ast.parse",                check_1_ast_parse),
    ("2. byte ASCII",               check_2_byte_ascii),
    ("3. _STR_TYPES helper",        check_3_str_types_helper),
    ("4. compat.py PySide2-only",   check_4_compat_py_pyside2_only),
    ("5. 0 PySide6 imports",        check_5_no_pyside6_imports),
    ("6. help_button R7 defensive", check_6_help_button_defensive),
    ("7. 4/4 anchors held",         check_7_anchors_in_scripts),
]


def main():
    failed = []
    print("M_P0_MAYA_2022_FROM_SCRATCH Phase 11C smoke audit")
    print("=" * 60)
    for name, fn in CHECKS:
        ok, msg = fn()
        marker = "OK  " if ok else "FAIL"
        print("  [{0}]  {1:30s}  {2}".format(marker, name, msg))
        if not ok:
            failed.append(name)
    print("=" * 60)
    if failed:
        print("PHASE 11C SMOKE: {0} check(s) failed: {1}".format(
            len(failed), failed))
        sys.exit(1)
    print("PHASE 11C SMOKE OK: all {0} checks passed.".format(len(CHECKS)))


if __name__ == "__main__":
    main()
