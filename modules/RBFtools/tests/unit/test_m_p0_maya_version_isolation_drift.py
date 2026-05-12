# -*- coding: utf-8 -*-
"""M_P0_MAYA_VERSION_ISOLATION Phase 6 PERMANENT guard.

scripts_2022/ must exactly match the output of
``tools/sync_2022_from_2025.py`` applied to the current scripts/.
Detects two regression classes:

  1. Drift -- somebody hand-edited scripts_2022/ and forgot to update
     the sync script's transformation rules; OR somebody changed
     scripts/ without re-running sync. Fix path: rerun the sync.
  2. Non-ASCII bytes -- the byte-level ASCII invariant that broke
     v0/v1/v2 must NEVER regress. Independent guard so a future
     change to the sync script's escape logic can't silently let
     non-ASCII through.
"""
from __future__ import absolute_import

import os
import subprocess
import sys

import pytest


# repo_root is 4 levels up from this file:
#   .../modules/RBFtools/tests/unit/test_m_p0_maya_version_isolation_drift.py
# == repo_root / modules / RBFtools / tests / unit / <this_file>
_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.normpath(os.path.join(_HERE, "..", "..", "..", ".."))
_SYNC_SCRIPT = os.path.join(_REPO_ROOT, "tools", "sync_2022_from_2025.py")
_SCRIPTS_2022 = os.path.join(
    _REPO_ROOT, "modules", "RBFtools", "scripts_2022")


def test_PERMANENT_a_scripts_2022_matches_sync_output():
    """Run ``python tools/sync_2022_from_2025.py --check``.

    Exit 0 => scripts_2022/ matches the sync script's deterministic
    output.  Exit 1 => somebody drifted -- either edit scripts_2022/
    by hand, or change scripts/ and forget to re-sync, or update
    the sync script's transformation rules without regenerating.

    Fix path:
        python tools/sync_2022_from_2025.py
        git diff modules/RBFtools/scripts_2022/   # review
        git add modules/RBFtools/scripts_2022/
        git commit ...
    """
    if not os.path.exists(_SYNC_SCRIPT):
        pytest.skip("sync script not present: {0}".format(_SYNC_SCRIPT))
    result = subprocess.Popen(
        [sys.executable, _SYNC_SCRIPT, "--check"],
        cwd=_REPO_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    stdout, stderr = result.communicate()
    rc = result.returncode
    if rc != 0:
        pytest.fail(
            "scripts_2022/ has drifted from sync script output.\n"
            "stdout:\n{0}\nstderr:\n{1}\n"
            "Fix: python tools/sync_2022_from_2025.py".format(
                stdout.decode("utf-8", errors="replace"),
                stderr.decode("utf-8", errors="replace"),
            )
        )


def test_PERMANENT_b_scripts_2022_is_pure_ascii():
    """Every .py file under modules/RBFtools/scripts_2022/ must be
    byte-level 100% ASCII (zero bytes > 0x7F).

    This is the invariant that broke under v0/v1/v2 -- the v1+v2
    patches added a single ASCII-decl + isinstance fix but the
    underlying source still contained raw non-ASCII bytes, so any
    user environment that ignored or stripped the PEP-263
    declaration (Notepad ANSI re-save, stale .pyc, ...) hit a
    SyntaxError at module load time.

    Independent of the sync drift check: even if the sync script
    introduced a regression, this test catches it.
    """
    if not os.path.isdir(_SCRIPTS_2022):
        pytest.skip("scripts_2022 not present: {0}".format(_SCRIPTS_2022))
    offenders = []
    for dp, _, fns in os.walk(_SCRIPTS_2022):
        for fn in fns:
            if not fn.endswith(".py"):
                continue
            path = os.path.join(dp, fn)
            with open(path, "rb") as f:
                data = f.read()
            non_ascii = [i for i, b in enumerate(bytearray(data)) if b > 127]
            if non_ascii:
                offenders.append(
                    (os.path.relpath(path, _REPO_ROOT).replace(os.sep, "/"),
                     non_ascii[:5]))
    if offenders:
        pytest.fail(
            "Non-ASCII bytes found under scripts_2022 -- sync script "
            "regression. Files with offending byte positions (first 5 "
            "each):\n  " + "\n  ".join(
                "{0} -> {1}".format(p, ps) for p, ps in offenders))
