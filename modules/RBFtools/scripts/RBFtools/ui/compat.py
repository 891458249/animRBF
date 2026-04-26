# -*- coding: utf-8 -*-
"""
Qt compatibility shim — PySide6 (Maya 2025+) / PySide2 (Maya 2020–2024).

Every other UI module imports Qt symbols **exclusively** from here.
Never ``from PySide2 import ...`` anywhere else in the codebase.

Exported names
--------------
- **QtWidgets, QtCore, QtGui** — the three primary Qt modules.
- **Signal, Slot, Property** — convenience aliases so call-sites
  don't need to qualify ``QtCore.Signal`` etc.
- **wrapInstance** — shiboken helper for pointer → QObject conversion.
- **maya_main_window()** — returns Maya's main window as a ``QWidget``.

Design notes
------------
* PySide6 moved some classes from QtWidgets to QtGui (e.g. ``QAction``,
  ``QShortcut``).  We patch ``QtWidgets.QAction`` back onto QtWidgets
  so downstream code can use a single import path regardless of version.
* The ``BINDING`` constant lets call-sites branch on rare edge cases
  without importing PySide* directly.
"""

from __future__ import absolute_import

# ------------------------------------------------------------------
# PySide6 / PySide2 detection
# ------------------------------------------------------------------

try:
    from PySide6 import QtWidgets, QtCore, QtGui          # noqa: F401
    from shiboken6 import wrapInstance                      # noqa: F401
    BINDING = "PySide6"
except ImportError:
    from PySide2 import QtWidgets, QtCore, QtGui           # noqa: F401
    from shiboken2 import wrapInstance                      # noqa: F401
    BINDING = "PySide2"

# ------------------------------------------------------------------
# Convenience aliases — consistent across both bindings
# ------------------------------------------------------------------

Signal   = QtCore.Signal
Slot     = QtCore.Slot
Property = QtCore.Property

# ------------------------------------------------------------------
# Forward-compat patches (PySide6 API relocations)
# ------------------------------------------------------------------

# QAction moved from QtWidgets to QtGui in Qt6.
if not hasattr(QtWidgets, "QAction"):
    QtWidgets.QAction = QtGui.QAction                       # type: ignore[attr-defined]

# QShortcut moved to QtGui in Qt6.
if not hasattr(QtWidgets, "QShortcut"):
    QtWidgets.QShortcut = QtGui.QShortcut                   # type: ignore[attr-defined]

# QActionGroup moved to QtGui in Qt6 (M_HOTFIX_PYSIDE6 - was missed
# from the original M2.4 shim; user hit AttributeError at production
# install of M_B24b on Maya 2025).
if not hasattr(QtWidgets, "QActionGroup"):
    QtWidgets.QActionGroup = QtGui.QActionGroup             # type: ignore[attr-defined]

# ------------------------------------------------------------------
# Maya main window helper
# ------------------------------------------------------------------

import maya.OpenMayaUI as omui


def maya_main_window():
    """Return the Maya main window as a ``QWidget``.

    Returns ``None`` when called outside of a GUI session (e.g. mayapy).
    """
    ptr = omui.MQtUtil.mainWindow()
    if ptr is not None:
        return wrapInstance(int(ptr), QtWidgets.QWidget)
    return None
