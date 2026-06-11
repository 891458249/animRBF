# -*- coding: utf-8 -*-
"""Phase 9 Task C: py2/py3 syntax check on scripts_2022.

Validates that every .py under modules/RBFtools/scripts_2022/RBFtools:
  1. Has no non-ASCII bytes at source level (byte-level pure ASCII)
  2. Parses cleanly under the host Python (ast.parse)
  3. Still parses after the PEP-263 coding declaration is stripped
     (simulates user environment that ignores the declaration)
  4. Contains no py3-only syntax (f-strings, walrus, async, nonlocal)

If mayapy2 is available on PATH, a real py2 syntax check via
``mayapy2 -m py_compile`` is recommended (see brief sec.4.3) -- this
script does the heuristic equivalent so the audit works on any host.

Run from repo root:
    python tools/audit_phase9_syntax.py
"""
from __future__ import absolute_import, print_function

import ast
import os
import re
import sys

DST = os.path.join("modules", "RBFtools", "scripts_2022", "RBFtools")


def main():
    issues = []
    py_files = 0

    py3_only_patterns = [
        (re.compile(rb'\bf["\']'), 'f-string'),
        (re.compile(rb'\basync\s+def\b'), 'async def'),
        (re.compile(rb'\bawait\b'), 'await'),
        (re.compile(rb':='), 'walrus'),
        (re.compile(rb'\bnonlocal\b'), 'nonlocal'),
    ]

    for dirpath, _, files in os.walk(DST):
        for f in files:
            if not f.endswith(".py"):
                continue
            py_files += 1
            path = os.path.join(dirpath, f)
            rel = os.path.relpath(path, DST).replace(os.sep, "/")

            with open(path, "rb") as fh:
                data = fh.read()

            # 1. Byte-level ASCII
            non_ascii = [(i, b) for i, b in enumerate(bytearray(data))
                         if b > 127]
            if non_ascii:
                issues.append("{0}: non-ASCII bytes at positions {1}".format(
                    rel, non_ascii[:5]))

            # 2. py3 ast.parse on raw bytes
            try:
                ast.parse(data, filename=path)
            except SyntaxError as e:
                issues.append("{0}: py3 SyntaxError: {1}".format(rel, e))

            # 3. py3 ast.parse with coding decl stripped
            data_stripped = re.sub(rb'^#.*coding.*\n', b'', data)
            try:
                ast.parse(data_stripped, filename=path)
            except SyntaxError as e:
                issues.append(
                    "{0}: py3 SyntaxError after stripping coding decl: {1}".format(
                        rel, e))

            # 4. py3-only patterns
            for pat, name in py3_only_patterns:
                if pat.search(data):
                    issues.append("{0}: py3-only syntax detected ({1})".format(
                        rel, name))

    if issues:
        print("PHASE 9 TASK C -- ISSUES ({0}):".format(len(issues)))
        for i in issues:
            print("  !", i)
        sys.exit(1)

    print(
        "PHASE 9 TASK C -- OK ({0} files pass py2+py3 syntax checks).".format(
            py_files))


if __name__ == "__main__":
    main()
