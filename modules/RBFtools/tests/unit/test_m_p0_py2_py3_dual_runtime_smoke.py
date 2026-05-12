# -*- coding: utf-8 -*-
"""T_M_P0_PY2_PY3_DUAL_RUNTIME_COMPAT smoke (2026-05-12) PERMANENT guard.

Phase A defence — every .py source file under ``modules/RBFtools/scripts``
and ``modules/RBFtools/tests`` that contains any non-ASCII byte MUST
carry a PEP-263 coding declaration on line 1 or line 2.

Without the declaration Maya 2022 optional py2 runtime (mayapy2) raises
``SyntaxError: Non-UTF-8 code starting with ...`` at module import time.
Maya 2025 (py3) does not need the declaration but is unharmed by its
presence.

The test also runs ``ast.parse`` on every source file so any future
SyntaxError (mixing tabs / spaces / illegal escapes / etc.) lights up
before it reaches a runtime.

Parametrised by file path so each violation surfaces as its own
test ID in pytest -v output.
"""
from __future__ import absolute_import

import ast
import os
import re

import pytest


_PEP263_RE = re.compile(rb"coding[:=]\s*[-\w.]+")
_REPO_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__),
                 os.pardir, os.pardir, os.pardir, os.pardir))
_SCAN_ROOTS = (
    os.path.join(_REPO_ROOT, "modules", "RBFtools", "scripts"),
    os.path.join(_REPO_ROOT, "modules", "RBFtools", "tests"),
)


def _collect_py_files():
    files = []
    for root in _SCAN_ROOTS:
        if not os.path.isdir(root):
            continue
        for dp, _dns, fns in os.walk(root):
            for fn in fns:
                if fn.endswith(".py"):
                    files.append(os.path.join(dp, fn))
    files.sort()
    return files


def _has_non_ascii(data):
    for b in data:
        v = b if isinstance(b, int) else ord(b)
        if v > 127:
            return True
    return False


def _has_pep263(data):
    parts = data.split(b"\n", 2)[:2]
    for line in parts:
        s = line.lstrip()
        if s.startswith(b"#") and _PEP263_RE.search(line):
            return True
    return False


_FILES = _collect_py_files()
_IDS = [os.path.relpath(p, _REPO_ROOT).replace(os.sep, "/") for p in _FILES]


@pytest.mark.parametrize("path", _FILES, ids=_IDS)
def test_PERMANENT_a_coding_decl_present_when_non_ascii(path):
    """If the file contains non-ASCII bytes, line 1 or 2 must declare
    a PEP-263 source encoding.  py2 mayapy2 requires this."""
    with open(path, "rb") as f:
        data = f.read()
    if not _has_non_ascii(data):
        pytest.skip("ASCII-only file: PEP-263 decl optional")
    assert _has_pep263(data), (
        "missing PEP-263 coding declaration on line 1/2: " + path)


@pytest.mark.parametrize("path", _FILES, ids=_IDS)
def test_PERMANENT_b_ast_parse_clean(path):
    """Every shipped .py file must parse cleanly under the host
    Python AST.  Catches escape / indent / quote bugs early."""
    with open(path, "rb") as f:
        data = f.read()
    try:
        ast.parse(data, filename=path)
    except SyntaxError as exc:
        pytest.fail("ast.parse failed: {0!s}: {1!s}".format(path, exc))
