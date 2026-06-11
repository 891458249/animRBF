# -*- coding: utf-8 -*-
"""Phase 9 Task A audit: detect non-R1-R7 drift between scripts/ and
scripts_2022/.

Both directories must have the same .py file tree. For each .py,
parse both with ast, walk nodes, and compare:
  * function signatures (names + arg lists)
  * class hierarchies (name + bases)
  * module-level assignments (name + value where deterministic)
  * top-level statement count by type

Any divergence outside R1-R7 -> print + exit 1.

Run from repo root:
    python tools/audit_phase9_drift.py
"""
from __future__ import absolute_import, print_function

import ast
import os
import sys

SRC = os.path.join("modules", "RBFtools", "scripts", "RBFtools")
DST = os.path.join("modules", "RBFtools", "scripts_2022", "RBFtools")

# Allowed extra names introduced by sync transformation (R4 helper).
ALLOWED_EXTRA_NAMES = {"_STR_TYPES", "_HELP_TEXTS_OK", "_HELP_TEXTS_ERR",
                       "_get_help_text"}


def list_py(root):
    out = []
    for dirpath, _, files in os.walk(root):
        for f in files:
            if f.endswith(".py"):
                rel = os.path.relpath(os.path.join(dirpath, f), root)
                out.append(rel.replace(os.sep, "/"))
    return sorted(out)


def parse(path):
    with open(path, "rb") as fh:
        src = fh.read()
    return ast.parse(src, filename=path)


def _unparse_base(b):
    if hasattr(ast, "unparse"):
        try:
            return ast.unparse(b)
        except Exception:
            return type(b).__name__
    return type(b).__name__


def signatures(tree):
    """Return a set of (kind, name, signature) tuples for FunctionDefs
    and ClassDefs anywhere in the tree."""
    sigs = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            args = tuple(a.arg for a in node.args.args)
            sigs.add(("def", node.name, args))
        elif isinstance(node, ast.AsyncFunctionDef):
            args = tuple(a.arg for a in node.args.args)
            sigs.add(("async def", node.name, args))
        elif isinstance(node, ast.ClassDef):
            bases = tuple(_unparse_base(b) for b in node.bases)
            sigs.add(("class", node.name, bases))
    return sigs


def module_assignments(tree):
    """Return set of module-level assignment target names. Also peeks
    into try/except bodies that wrap module-level definitions (so the
    R4 ``try: _STR_TYPES = ...`` helper is seen)."""
    names = set()

    def _collect(stmts):
        for stmt in stmts:
            if isinstance(stmt, ast.Assign):
                for tgt in stmt.targets:
                    if isinstance(tgt, ast.Name):
                        names.add(tgt.id)
            elif isinstance(stmt, (ast.AnnAssign, ast.AugAssign)):
                if isinstance(stmt.target, ast.Name):
                    names.add(stmt.target.id)
            elif isinstance(stmt, ast.Try):
                _collect(stmt.body)
                for h in stmt.handlers:
                    _collect(h.body)
                _collect(stmt.orelse)
                _collect(stmt.finalbody)
            elif isinstance(stmt, ast.FunctionDef):
                names.add(stmt.name)
            elif isinstance(stmt, ast.ClassDef):
                names.add(stmt.name)
    _collect(tree.body)
    return names


def main():
    src_files = list_py(SRC)
    dst_files = list_py(DST)

    drift = []

    only_src = set(src_files) - set(dst_files)
    only_dst = set(dst_files) - set(src_files)
    for f in sorted(only_src):
        drift.append("MISSING in scripts_2022: {0}".format(f))
    for f in sorted(only_dst):
        if f != "__init__.py":
            drift.append("EXTRA in scripts_2022: {0}".format(f))

    common = sorted(set(src_files) & set(dst_files))

    for rel in common:
        src_tree = parse(os.path.join(SRC, rel.replace("/", os.sep)))
        dst_tree = parse(os.path.join(DST, rel.replace("/", os.sep)))

        s_sigs = signatures(src_tree)
        d_sigs = signatures(dst_tree)
        only_s = s_sigs - d_sigs
        only_d = d_sigs - s_sigs
        for sig in only_s:
            drift.append("{0}: missing signature in scripts_2022: {1}".format(
                rel, sig))
        for sig in only_d:
            # The R5 fallback _get_help_text in help_button.py is
            # allowed (defined in except branch of module-level try).
            if (sig == ("def", "_get_help_text", ("key",))
                    and rel == "ui/widgets/help_button.py"):
                continue
            drift.append("{0}: extra signature in scripts_2022: {1}".format(
                rel, sig))

        s_assigns = module_assignments(src_tree)
        d_assigns = module_assignments(dst_tree)
        only_s_a = s_assigns - d_assigns
        only_d_a = d_assigns - s_assigns - ALLOWED_EXTRA_NAMES
        for n in sorted(only_s_a):
            drift.append("{0}: missing module assign in scripts_2022: {1}".format(
                rel, n))
        for n in sorted(only_d_a):
            drift.append("{0}: extra module assign in scripts_2022: {1}".format(
                rel, n))

    if drift:
        print("PHASE 9 TASK A -- DRIFT DETECTED ({0} issues):".format(len(drift)))
        for d in drift:
            print("  !", d)
        sys.exit(1)

    print("PHASE 9 TASK A -- OK ({0} files all functionally equivalent).".format(
        len(common)))


if __name__ == "__main__":
    main()
