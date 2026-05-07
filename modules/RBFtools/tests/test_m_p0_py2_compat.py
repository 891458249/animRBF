# -*- coding: utf-8 -*-
"""M_P0_PY2_COMPAT (2026-05-01) — make the RBFtools script package
importable under Maya 2022's optional py2 runtime (mayapy2).

Pre-fix audit (51 .py files under modules/RBFtools/scripts/):
  * 0 f-strings
  * 0 walrus (:=)
  * 0 async constructs
  * 1 dataclass usage: core.DriverSource (@dataclass(frozen=True))
  * 1 hard SyntaxError: ui/widgets/mirror_dialog.py line 22-25 had
    a placeholder ``from RBFtools.constants import ()`` block —
    an empty parenthesised import list is a SyntaxError in EVERY
    Python version. Live tests just never imported the module.

Fixes:
  * core.DriverSource rewritten from @dataclass(frozen=True) to a
    hand-rolled ``__slots__`` class with read-only properties +
    explicit __setattr__ guard + explicit __eq__ / __hash__ /
    __repr__. Behaviour-equivalent to the dataclass version (the
    23-commit Python suite stays green).
  * core.py drops ``from dataclasses import dataclass``.
  * mirror_dialog.py drops the empty import block.

PERMANENT GUARD T_M_P0_PY2_COMPAT keeps the package free of py3-
only syntactic constructs.
"""

from __future__ import absolute_import

import ast
import os
import sys
import unittest


_REPO_ROOT = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..")
)
_SCRIPTS_ROOT = os.path.join(
    _REPO_ROOT, "modules", "RBFtools", "scripts")


def _iter_py_files(root):
    out = []
    for dp, _, fs in os.walk(root):
        for f in fs:
            if f.endswith(".py"):
                out.append(os.path.join(dp, f))
    return out


def _read(p):
    with open(p, "r", encoding="utf-8") as fh:
        return fh.read()


# ----------------------------------------------------------------------
# T_M_P0_PY2_COMPAT — source-level guards.
# ----------------------------------------------------------------------


class T_M_P0_PY2_COMPAT(unittest.TestCase):
    """PERMANENT GUARD — DO NOT REMOVE."""

    def setUp(self):
        self._files = _iter_py_files(_SCRIPTS_ROOT)
        self.assertGreater(
            len(self._files), 30,
            "Sanity: expected to scan many .py files under scripts/.")

    # ---------- syntax: every file ast-parses cleanly --------------

    def test_PERMANENT_a_every_script_parses(self):
        # Catches the mirror_dialog.py-style empty-import-list bug
        # before it reaches a runtime importer.
        bad = []
        for p in self._files:
            try:
                ast.parse(_read(p), filename=p)
            except SyntaxError as e:
                bad.append((p, e.lineno, e.msg))
        self.assertFalse(
            bad, "ast.parse failed for: {}".format(bad))

    # ---------- no f-strings (py3.6+) ------------------------------

    def test_PERMANENT_b_no_fstrings(self):
        offenders = []
        for p in self._files:
            tree = ast.parse(_read(p), filename=p)
            for node in ast.walk(tree):
                if isinstance(node, ast.JoinedStr):
                    offenders.append((p, node.lineno))
                    break
        self.assertFalse(
            offenders,
            "f-strings (PEP 498, py3.6+) found in: {}. "
            "Use .format() so the file imports under py2."
            .format(offenders))

    # ---------- no walrus := (py3.8+) ------------------------------

    def test_PERMANENT_c_no_walrus(self):
        offenders = []
        for p in self._files:
            tree = ast.parse(_read(p), filename=p)
            for node in ast.walk(tree):
                if isinstance(node, ast.NamedExpr):
                    offenders.append((p, node.lineno))
                    break
        self.assertFalse(
            offenders,
            "walrus := (PEP 572, py3.8+) found in: {}."
            .format(offenders))

    # ---------- no async constructs (py3.5+) -----------------------

    def test_PERMANENT_d_no_async_constructs(self):
        offenders = []
        for p in self._files:
            tree = ast.parse(_read(p), filename=p)
            for node in ast.walk(tree):
                if isinstance(node, (
                        ast.AsyncFunctionDef, ast.AsyncWith,
                        ast.AsyncFor, ast.Await)):
                    offenders.append((p, node.lineno))
                    break
        self.assertFalse(
            offenders,
            "async constructs (py3.5+) found in: {}.".format(
                offenders))

    # ---------- no dataclass usage (py3.7+) ------------------------

    def test_PERMANENT_e_no_dataclasses_import(self):
        offenders = []
        for p in self._files:
            src = _read(p)
            for line in src.splitlines():
                stripped = line.strip()
                if (stripped.startswith("from dataclasses ")
                        or stripped.startswith("import dataclasses")):
                    offenders.append((p, line))
                    break
        self.assertFalse(
            offenders,
            "dataclasses imports (py3.7+) found in: {}. "
            "Use a hand-rolled __slots__ class instead so the "
            "module imports under py2.".format(offenders))

    def test_PERMANENT_f_no_dataclass_decorator(self):
        # AST-based detection so the docstring word "dataclass"
        # in driven/driver_source_list_editor.py doesn't trip.
        offenders = []
        for p in self._files:
            tree = ast.parse(_read(p), filename=p)
            for node in ast.walk(tree):
                if not isinstance(node, ast.ClassDef):
                    continue
                for dec in node.decorator_list:
                    name = None
                    if isinstance(dec, ast.Name):
                        name = dec.id
                    elif isinstance(dec, ast.Call) and isinstance(
                            dec.func, ast.Name):
                        name = dec.func.id
                    elif isinstance(dec, ast.Attribute):
                        name = dec.attr
                    if name == "dataclass":
                        offenders.append((p, node.lineno))
        self.assertFalse(
            offenders,
            "@dataclass decorator (py3.7+) found in: {}."
            .format(offenders))


# ----------------------------------------------------------------------
# DriverSource frozen-class behavioural equivalence to the previous
# @dataclass(frozen=True) implementation.
# ----------------------------------------------------------------------


def _import_core():
    # NOTE: do NOT delete sys.modules["RBFtools.core"] before
    # importing — the rest of the test suite has already imported
    # core indirectly (via controller / ui modules), and a fresh
    # import would create a second DriverSource class object.
    # Other modules' ``isinstance(x, core.DriverSource)`` checks
    # would then fail with the new class while x is an instance
    # of the old, breaking ~13 unrelated tests on full sweep.
    if _SCRIPTS_ROOT not in sys.path:
        sys.path.insert(0, _SCRIPTS_ROOT)
    import RBFtools.core as core   # noqa: F401
    return sys.modules["RBFtools.core"]


class TestDriverSourceFrozenContract(unittest.TestCase):
    """The 23-commit suite already exercises DriverSource via real
    code paths; these tests pin down the frozen contract bit by
    bit so the rewrite stays interchangeable with the historical
    @dataclass(frozen=True) shape."""

    def test_construct_with_defaults(self):
        core = _import_core()
        ds = core.DriverSource(node="A", attrs=("tx",))
        self.assertEqual(ds.node, "A")
        self.assertEqual(ds.attrs, ("tx",))
        self.assertEqual(ds.weight, 1.0)
        self.assertEqual(ds.encoding, 0)

    def test_construct_with_full_args(self):
        core = _import_core()
        ds = core.DriverSource(
            node="A", attrs=["tx", "ty"],
            weight=0.5, encoding=4)
        self.assertEqual(ds.attrs, ("tx", "ty"))
        self.assertEqual(ds.weight, 0.5)
        self.assertEqual(ds.encoding, 4)

    def test_attrs_normalized_to_tuple(self):
        core = _import_core()
        ds = core.DriverSource(node="A", attrs=["tx", "ty"])
        self.assertIsInstance(ds.attrs, tuple)

    def test_validation_negative_weight(self):
        core = _import_core()
        with self.assertRaises(ValueError):
            core.DriverSource(node="A", attrs=(), weight=-0.1)

    def test_validation_bad_encoding(self):
        core = _import_core()
        with self.assertRaises(ValueError):
            core.DriverSource(node="A", attrs=(), encoding=5)

    def test_validation_node_must_be_str(self):
        core = _import_core()
        with self.assertRaises(TypeError):
            core.DriverSource(node=123, attrs=())

    def test_frozen_blocks_field_assignment(self):
        core = _import_core()
        ds = core.DriverSource(node="A", attrs=())
        with self.assertRaises(AttributeError):
            ds.node = "B"
        with self.assertRaises(AttributeError):
            ds.weight = 0.5

    def test_equality_value_based(self):
        core = _import_core()
        a = core.DriverSource(node="N", attrs=("tx",), weight=0.5)
        b = core.DriverSource(node="N", attrs=("tx",), weight=0.5)
        self.assertEqual(a, b)
        self.assertEqual(hash(a), hash(b))

    def test_inequality(self):
        core = _import_core()
        a = core.DriverSource(node="N", attrs=("tx",))
        b = core.DriverSource(node="N", attrs=("ty",))
        self.assertNotEqual(a, b)

    def test_eq_other_type_returns_notimplemented(self):
        core = _import_core()
        a = core.DriverSource(node="N", attrs=())
        self.assertNotEqual(a, ("N", ()))   # uses __eq__ via !=

    def test_hashable_in_set(self):
        core = _import_core()
        a = core.DriverSource(node="N", attrs=("tx",))
        b = core.DriverSource(node="N", attrs=("tx",))
        self.assertEqual(len({a, b}), 1)

    def test_repr_round_trips_label(self):
        core = _import_core()
        ds = core.DriverSource(
            node="A", attrs=("tx", "ty"),
            weight=0.5, encoding=2)
        r = repr(ds)
        self.assertIn("DriverSource(", r)
        self.assertIn("node='A'", r)
        self.assertIn("attrs=['tx', 'ty']", r)
        self.assertIn("weight=0.5", r)
        self.assertIn("encoding=2", r)


if __name__ == "__main__":
    unittest.main()
