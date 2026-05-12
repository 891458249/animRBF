# -*- coding: utf-8 -*-
"""M_P0_PY2_PY3_DUAL_RUNTIME_COMPAT — mayapy2 import smoke (manual).

Run THIS script under Maya 2022's mayapy2 to confirm the dual-runtime
fixes actually let the package import + accept unicode in the py2
runtime:

    "C:\\Program Files\\Autodesk\\Maya2022\\bin\\mayapy2.exe" ^
        modules\\RBFtools\\tests\\scratch\\smoke_mayapy2_imports.py

Expected output (all PASS lines, exit 0):

    [smoke] importing RBFtools.core ... OK
    [smoke] importing RBFtools.core_json ... OK
    [smoke] importing RBFtools.controller ... OK
    [smoke] importing RBFtools.ui.help_texts ... OK
    [smoke] DriverSource(str)         ... OK
    [smoke] DriverSource(unicode)     ... OK  (py2 only)
    [smoke] DriverSource(123) rejects ... OK
    [smoke] DrivenSource(str)         ... OK
    [smoke] DrivenSource(unicode)     ... OK  (py2 only)
    [smoke] ALL SMOKE PASSED

If any line prints FAIL or the script aborts with SyntaxError, that
is the regression — bring the dump back to the planner.
"""
from __future__ import absolute_import, print_function

import os
import sys
import traceback


_HERE = os.path.abspath(os.path.dirname(__file__))
_REPO_ROOT = os.path.abspath(os.path.join(_HERE, os.pardir, os.pardir, os.pardir, os.pardir))
_SCRIPTS = os.path.join(_REPO_ROOT, "modules", "RBFtools", "scripts")
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)


_failures = []


def _step(label, fn):
    try:
        fn()
        print("[smoke] " + label + " ... OK")
    except Exception as exc:
        print("[smoke] " + label + " ... FAIL: " + repr(exc))
        traceback.print_exc()
        _failures.append(label)


def _do_imports():
    import RBFtools.core           # noqa: F401
    import RBFtools.core_json      # noqa: F401
    import RBFtools.controller     # noqa: F401
    import RBFtools.ui.help_texts  # noqa: F401


def _do_driver_str():
    from RBFtools.core import DriverSource
    ds = DriverSource("pCube1", ["tx", "ty"])
    assert ds.node == "pCube1"


def _do_driver_unicode():
    # py2 has builtin `unicode`; py3 does not — under py3 we use a u""
    # literal which is itself ``str``, so the second tuple element of
    # _STR_TYPES doesn't get exercised. That is fine; the point is
    # that ``unicode`` from Maya cmds.ls() in py2 stops raising.
    from RBFtools.core import DriverSource
    node = u"pCube1"
    ds = DriverSource(node, ["tx", "ty"])
    assert ds.node == u"pCube1"


def _do_driver_rejects_int():
    from RBFtools.core import DriverSource
    try:
        DriverSource(123, ["tx"])
    except TypeError:
        return
    raise AssertionError("DriverSource(int) should have raised TypeError")


def _do_driven_str():
    from RBFtools.core import DrivenSource
    DrivenSource("pSphere1", ["rx"])


def _do_driven_unicode():
    from RBFtools.core import DrivenSource
    DrivenSource(u"pSphere1", ["rx"])


def main():
    _step("importing RBFtools.core",         lambda: __import__("RBFtools.core"))
    _step("importing RBFtools.core_json",    lambda: __import__("RBFtools.core_json"))
    _step("importing RBFtools.controller",   lambda: __import__("RBFtools.controller"))
    _step("importing RBFtools.ui.help_texts", lambda: __import__("RBFtools.ui.help_texts"))
    _step("DriverSource(str)",                _do_driver_str)
    _step("DriverSource(unicode)",            _do_driver_unicode)
    _step("DriverSource(123) rejects",        _do_driver_rejects_int)
    _step("DrivenSource(str)",                _do_driven_str)
    _step("DrivenSource(unicode)",            _do_driven_unicode)

    if _failures:
        print("[smoke] FAILURES: " + ", ".join(_failures))
        sys.exit(1)
    print("[smoke] ALL SMOKE PASSED")
    sys.exit(0)


if __name__ == "__main__":
    main()
