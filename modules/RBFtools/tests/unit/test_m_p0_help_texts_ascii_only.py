# -*- coding: utf-8 -*-
"""M_P0_PY2_PY3_DUAL_RUNTIME_COMPAT_v2 Phase E PERMANENT guard.

help_texts.py must be 100% ASCII at byte level so it imports cleanly
under Maya 2022 mayapy2 even when the PEP-263 coding declaration is
ignored / stripped by an end-user environment quirk (Notepad ANSI
re-save, stale .pyc, sys.setdefaultencoding rewrite, etc.).

In addition the loaded _EN dict must still contain the original
Unicode characters (em dash, black star, middle dot, degree sign)
after the ``\\uXXXX`` escape transformation, proving the transform
is value-preserving.
"""
from __future__ import absolute_import

import os
import sys
import types

import pytest


HERE = os.path.dirname(os.path.abspath(__file__))
HELP_TEXTS_PATH = os.path.normpath(os.path.join(
    HERE, "..", "..", "scripts", "RBFtools", "ui", "help_texts.py"))
_SCRIPTS_DIR = os.path.normpath(os.path.join(
    HERE, "..", "..", "scripts"))


def _install_maya_stub():
    """Inject a minimal maya / maya.cmds stub so help_texts.py
    (which transitively imports i18n.py -> maya.cmds.optionVar)
    can be imported in a vanilla Python interpreter for tests."""
    if "maya" not in sys.modules:
        sys.modules["maya"] = types.ModuleType("maya")
    if "maya.cmds" not in sys.modules:
        cmds = types.ModuleType("maya.cmds")
        cmds.optionVar = lambda **kw: False
        sys.modules["maya.cmds"] = cmds


def _fresh_import_help_texts():
    """Force a clean re-import of help_texts so each test sees the
    current file bytes (no module cache from a prior test run)."""
    _install_maya_stub()
    for mod in list(sys.modules):
        if mod == "RBFtools" or mod.startswith("RBFtools."):
            del sys.modules[mod]
    if _SCRIPTS_DIR not in sys.path:
        sys.path.insert(0, _SCRIPTS_DIR)
    from RBFtools.ui import help_texts as ht
    return ht


def test_PERMANENT_a_help_texts_is_100_percent_ascii_bytes():
    """Byte-level guarantee: file parseable even if the coding
    declaration is stripped or ignored. Repro guard for the
    line-464 SyntaxError seen on user's Maya 2022 py2 runtime."""
    with open(HELP_TEXTS_PATH, "rb") as f:
        data = f.read()
    non_ascii = [(i, b) for i, b in enumerate(bytearray(data)) if b > 127]
    assert not non_ascii, (
        "help_texts.py contains {0} non-ASCII bytes (first 5: {1}). "
        "Phase E requires 100% ASCII source: use \\uXXXX escapes for "
        "string literals, ASCII visual equivalents (-- / *) for "
        "comments and docstrings."
    ).format(len(non_ascii), non_ascii[:5])


def test_PERMANENT_b_en_dict_known_keys_decoded_correctly():
    """Roundtrip: after \\uXXXX escape transformation, the loaded
    _EN dict values must still contain the original Unicode
    characters at runtime (em dash, black star, middle dot)."""
    ht = _fresh_import_help_texts()

    expmap = ht._EN.get("enc_expmap", "")
    assert u"—" in expmap, "em dash missing in enc_expmap"
    assert u"★" in expmap, "black star missing in enc_expmap"

    swingtwist = ht._EN.get("enc_swingtwist", "")
    assert u"—" in swingtwist, "em dash missing in enc_swingtwist"
    assert u"★" in swingtwist, "black star missing in enc_swingtwist"
    assert u"·" in swingtwist, "middle dot missing in enc_swingtwist"


def test_PERMANENT_c_get_help_text_returns_value_with_unicode_chars():
    """API contract: get_help_text returns a non-empty value that
    still contains the original Unicode characters under both py2
    (unicode) and py3 (str) runtimes."""
    ht = _fresh_import_help_texts()
    val = ht.get_help_text("enc_expmap")
    assert val, "get_help_text returned empty for enc_expmap"
    assert u"—" in val, "em dash missing in get_help_text output"
