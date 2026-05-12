# -*- coding: utf-8 -*-
"""T_M_P0_PY2_PY3_DUAL_RUNTIME_COMPAT isinstance compat (2026-05-12).

Phase B defence — DriverSource / DrivenSource / core_json.validate
must accept BOTH ``str`` and (under py2) ``unicode`` for the ``node``
and ``name`` fields.  In Maya 2022's optional py2 runtime (mayapy2)
Maya's ``cmds.ls`` returns ``unicode`` objects; rejecting them broke
the UI's "添加驱动" (Add Driver) button.

Each isinstance site that gates a public API on string-ness must use
the module-local ``_STR_TYPES`` tuple, which collapses to ``(str,)``
under py3 via the ``try / except NameError`` guard.

Six PERMANENT guards, ASCII-only source-scan tests (no runtime import
of ``RBFtools.core`` — that would require maya.cmds at collection
time).
"""
from __future__ import absolute_import

import os
import re


_REPO_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), os.pardir, os.pardir, os.pardir, os.pardir))
_CORE = os.path.join(
    _REPO_ROOT, "modules", "RBFtools", "scripts", "RBFtools", "core.py")
_CORE_JSON = os.path.join(
    _REPO_ROOT, "modules", "RBFtools", "scripts", "RBFtools", "core_json.py")


def _read(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def test_PERMANENT_a_core_defines_STR_TYPES_guard():
    """core.py declares a module-local _STR_TYPES tuple guarded by a
    try / except NameError block (py2 has ``unicode``, py3 does not)."""
    src = _read(_CORE)
    assert "try:\n    _STR_TYPES = (str, unicode)" in src, \
        "core.py missing _STR_TYPES try-block"
    assert "except NameError:\n    _STR_TYPES = (str,)" in src, \
        "core.py missing _STR_TYPES NameError fallback"


def test_PERMANENT_b_core_json_defines_STR_TYPES_guard():
    """core_json.py defines its OWN _STR_TYPES (no cross-module
    import of the private name)."""
    src = _read(_CORE_JSON)
    assert "try:\n    _STR_TYPES = (str, unicode)" in src, \
        "core_json.py missing _STR_TYPES try-block"
    assert "except NameError:\n    _STR_TYPES = (str,)" in src, \
        "core_json.py missing _STR_TYPES NameError fallback"
    # Defensive: must NOT import the private name from core (would
    # re-introduce a cross-module private leak).
    assert "from .core import _STR_TYPES" not in src
    assert "from RBFtools.core import _STR_TYPES" not in src


def test_PERMANENT_c_no_isinstance_node_str_left():
    """No bare ``isinstance(node, str)`` survives in core.py — every
    site must go through _STR_TYPES."""
    src = _read(_CORE)
    assert "isinstance(node, str)" not in src, \
        "core.py still has isinstance(node, str)"


def test_PERMANENT_d_no_isinstance_name_str_left():
    """No bare ``isinstance(name, str)`` survives in core_json.py."""
    src = _read(_CORE_JSON)
    assert "isinstance(name, str)" not in src, \
        "core_json.py still has isinstance(name, str)"


def test_PERMANENT_e_DriverSource_uses_STR_TYPES():
    """DriverSource.__init__ gates ``node`` on _STR_TYPES."""
    src = _read(_CORE)
    # Match the DriverSource isinstance line directly.
    m = re.search(
        r"class DriverSource[\s\S]+?def __init__\(self, node, attrs[\s\S]+?isinstance\(node,\s*_STR_TYPES\)",
        src)
    assert m is not None, "DriverSource.__init__ does not gate node on _STR_TYPES"


def test_PERMANENT_f_DrivenSource_uses_STR_TYPES():
    """DrivenSource.__init__ gates ``node`` on _STR_TYPES."""
    src = _read(_CORE)
    m = re.search(
        r"class DrivenSource[\s\S]+?def __init__\(self, node, attrs\)[\s\S]+?isinstance\(node,\s*_STR_TYPES\)",
        src)
    assert m is not None, "DrivenSource.__init__ does not gate node on _STR_TYPES"


def test_PERMANENT_g_core_json_validate_uses_STR_TYPES():
    """core_json validate-block uses isinstance(name, _STR_TYPES)."""
    src = _read(_CORE_JSON)
    assert "isinstance(name, _STR_TYPES) or not name" in src, \
        "core_json validation does not gate name on _STR_TYPES"


def test_PERMANENT_h_runtime_anchor_referenced():
    """Both modules cite the patch id in a comment so future audits
    can grep the audit trail."""
    anchor = "M_P0_PY2_PY3_DUAL_RUNTIME_COMPAT"
    assert anchor in _read(_CORE), "core.py missing patch-id anchor"
    assert anchor in _read(_CORE_JSON), \
        "core_json.py missing patch-id anchor"
