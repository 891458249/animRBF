"""M_HOTFIX_PYSIDE6 - T_PYSIDE6_COMPAT (#32 PERMANENT GUARD).

Maya 2025 PySide6 strictly enforces Qt5 -> Qt6 migration:
  QtWidgets.QAction      -> QtGui.QAction
  QtWidgets.QActionGroup -> QtGui.QActionGroup
  QtWidgets.QShortcut    -> QtGui.QShortcut

User hit AttributeError on production install of M_B24b commits
because compat.py shim covered QAction + QShortcut but missed
QActionGroup. Mock-pattern UI tests don't catch this regression
(MagicMock returns truthy for any attr access).

This guard ensures the shim itself stays complete. Widget files
using the QtWidgets.X form rely on this shim; deleting the shim
line re-breaks production.

Scope decision: per the M_HOTFIX_PYSIDE6.guard-scope-decision
section in the addendum, this guard does NOT scan the widgets/
directory for Qt5-style usage (would conflict with the project
convention of "widgets use QtWidgets.X + compat shim provides
the symbol"). It instead locks the compat.py shim integrity for
all three migrated symbols (QAction / QShortcut / QActionGroup).

Real PySide6 import path validation is M5 GUI long-tail scope.
Until then, this source-scan guards the compat shim.
"""

from __future__ import absolute_import

import os
import re
import unittest


_REPO_ROOT = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..")
)
_SCRIPTS_ROOT = os.path.join(
    _REPO_ROOT, "modules", "RBFtools", "scripts", "RBFtools"
)
_COMPAT_PY = os.path.join(_SCRIPTS_ROOT, "ui", "compat.py")


def _strip_docstrings_and_comments(src):
    """Strip docstrings (triple-quoted) + line comments so the scan
    only inspects executable code. Same pattern as
    T_M1_5_FIXTURE_BOUNDARY (#18) and T_CONFTEST_DUAL_ENV (#17)."""
    src = re.sub(r'"""[\s\S]*?"""', "", src)
    src = re.sub(r"'''[\s\S]*?'''", "", src)
    out = []
    for line in src.splitlines():
        stripped = line.lstrip()
        if stripped.startswith("#"):
            continue
        out.append(line)
    return "\n".join(out)


class T_PYSIDE6_COMPAT(unittest.TestCase):
    """#32 PERMANENT GUARD - DO NOT REMOVE.

    Three sub-checks lock the compat.py shim integrity for the
    full Qt5 -> Qt6 symbol migration set."""

    @classmethod
    def setUpClass(cls):
        with open(_COMPAT_PY, "r", encoding="utf-8") as f:
            raw = f.read()
        cls._src = _strip_docstrings_and_comments(raw)

    def test_PERMANENT_b1_compat_shim_has_qactiongroup(self):
        """Sub-check (b.1): compat.py declares QActionGroup symbol.

        The original M_B24b ship missed this; production install
        on Maya 2025 hit AttributeError at node_selector.py:73."""
        self.assertIn("QActionGroup", self._src,
            "compat.py MUST shim QActionGroup for PySide6 compat - "
            "production install on Maya 2025 fails without it "
            "(M_HOTFIX_PYSIDE6 anchor)")

    def test_PERMANENT_b2_compat_shim_points_to_qtgui(self):
        """Sub-check (b.2): the QActionGroup shim RHS is
        QtGui.QActionGroup (Qt6 location), not QtWidgets.QActionGroup
        (which does not exist under Qt6)."""
        self.assertIn("QtGui.QActionGroup", self._src,
            "compat.py shim MUST point to QtGui.QActionGroup "
            "(Qt6 location); using QtWidgets.QActionGroup as RHS "
            "would re-break production")

    def test_PERMANENT_b3_three_symbol_shim_integrity(self):
        """Sub-check (b.3): all three migrated symbols are present
        in the shim. Prevents a future "compat.py cleanup" from
        silently removing any of QAction / QShortcut /
        QActionGroup, which would re-break the production widgets
        that rely on QtWidgets.X form."""
        for sym in ("QAction", "QShortcut", "QActionGroup"):
            self.assertIn(
                "QtGui.{}".format(sym), self._src,
                "compat.py shim MUST preserve QtGui.{} - "
                "removal would re-break production widget code "
                "that uses QtWidgets.{} form".format(sym, sym))


if __name__ == "__main__":
    unittest.main()
