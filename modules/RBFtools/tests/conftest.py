"""Pytest / unittest discovery shim — Maya + PySide mock framework.

Loaded automatically by pytest, and explicitly imported by widget tests
(``import conftest # noqa``) to fire the same setup under
``python -m unittest`` discovery.

Mocks installed (in priority order):

    1. ``RBFtools`` package path injection so ``import RBFtools`` resolves.
    2. ``maya`` / ``maya.cmds`` / ``maya.api.OpenMaya`` /
       ``maya.OpenMayaUI`` — permissive MagicMocks.
    3. PySide6 / PySide2 — when neither real binding is installed, a
       **minimal real-class shim** is installed instead of pure
       MagicMock. Reason: ``class Foo(QtWidgets.QWidget)`` requires
       ``QtWidgets.QWidget`` to be a real class with a working metaclass;
       a MagicMock instance triggers Python's metaclass machinery in
       a way that makes the *subclass* a MagicMock too, hiding the
       user-defined methods we want to introspect (v5 addendum §M2.4a
       PySide-mock-trap discussion).

The shim is intentionally tiny: just enough to let widget classes
*be defined* and *introspected*. Instantiation requires a real
QApplication and is reserved for M1.5 mayapy E2E tests.
"""

from __future__ import absolute_import

import os
import sys
from unittest import mock


# ----------------------------------------------------------------------
# 1. Package path
# ----------------------------------------------------------------------


def _install_package_path():
    """Make ``RBFtools`` importable from this test root.

    Layout:
        <repo>/modules/RBFtools/scripts/RBFtools/
        <repo>/modules/RBFtools/tests/        ← this file lives here
    """
    here = os.path.dirname(os.path.abspath(__file__))
    scripts = os.path.normpath(os.path.join(here, os.pardir, "scripts"))
    if scripts not in sys.path:
        sys.path.insert(0, scripts)


# ----------------------------------------------------------------------
# 2. Maya mocks (permissive MagicMock)
# ----------------------------------------------------------------------


def _install_maya_mocks():
    if 'maya' not in sys.modules:
        sys.modules['maya'] = mock.MagicMock(name='maya')
    if 'maya.cmds' not in sys.modules:
        sys.modules['maya.cmds'] = mock.MagicMock(name='maya.cmds')
        sys.modules['maya'].cmds = sys.modules['maya.cmds']
    if 'maya.api' not in sys.modules:
        sys.modules['maya.api'] = mock.MagicMock(name='maya.api')
    if 'maya.api.OpenMaya' not in sys.modules:
        sys.modules['maya.api.OpenMaya'] = mock.MagicMock(
            name='maya.api.OpenMaya')
    if 'maya.OpenMayaUI' not in sys.modules:
        sys.modules['maya.OpenMayaUI'] = mock.MagicMock(
            name='maya.OpenMayaUI')
    if 'maya.utils' not in sys.modules:
        sys.modules['maya.utils'] = mock.MagicMock(name='maya.utils')


# ----------------------------------------------------------------------
# 3. PySide minimal shim — only used when no real binding is installed.
# ----------------------------------------------------------------------


class _Stub(object):
    """Permissive base class — accepts any constructor args, returns
    a MagicMock for any attribute access not explicitly defined. Lets
    widget code under test call ``self._lbl.setText(...)`` etc. without
    blowing up while we only care about class structure."""

    def __init__(self, *args, **kwargs):
        pass

    def __getattr__(self, name):
        # Auto-create permissive mock attrs (setText, addWidget, ...).
        m = mock.MagicMock(name="_Stub.{}".format(name))
        object.__setattr__(self, name, m)
        return m


class _StubSignal(object):
    """Replacement for ``QtCore.Signal``. Class-body usage:
        attributeChanged = Signal(str, object)
    becomes a class attribute that's a *_StubSignal instance*. Tests
    can introspect class.attributeChanged for existence; runtime
    ``.emit(...)`` is a no-op."""

    def __init__(self, *types):
        self.types = types

    def connect(self, *args, **kwargs):
        pass

    def disconnect(self, *args, **kwargs):
        pass

    def emit(self, *args, **kwargs):
        pass


class _StubEnum(int):
    """Convenience for Qt enum-like ints."""
    pass


def _build_qtcore():
    qtcore = mock.MagicMock(name="QtCore")
    qtcore.Signal = _StubSignal
    qtcore.Slot = lambda *a, **kw: (lambda f: f)
    qtcore.Property = lambda *a, **kw: None
    qtcore.QObject = _Stub

    # Qt enum bag — additions are auto-created as MagicMocks via
    # MagicMock's default behaviour, but we set the most-used ones as
    # real ints so equality / setData work.
    qtcore.Qt = mock.MagicMock(name="QtCore.Qt")
    qtcore.Qt.UserRole = _StubEnum(32)
    qtcore.Qt.CustomContextMenu = _StubEnum(0)
    qtcore.Qt.ItemIsEditable = _StubEnum(2)
    return qtcore


def _build_qtwidgets():
    qtw = mock.MagicMock(name="QtWidgets")
    # Concrete real-class stubs used as base classes in widget files.
    for cls_name in (
        "QWidget", "QFrame", "QLabel", "QPushButton", "QLineEdit",
        "QComboBox", "QCheckBox", "QSpinBox", "QDoubleSpinBox",
        "QListWidget", "QListWidgetItem", "QTableWidget",
        "QTableWidgetItem", "QHBoxLayout", "QVBoxLayout",
        "QGridLayout", "QMenu", "QAbstractItemView",
        "QHeaderView", "QSizePolicy", "QToolButton",
        "QDialog", "QScrollArea", "QApplication",
    ):
        setattr(qtw, cls_name, type(cls_name, (_Stub,), {}))

    # QFrame.HLine / Sunken / etc. — set on the class so widget code
    # ``QtWidgets.QFrame.HLine`` lookups resolve.
    qtw.QFrame.HLine = _StubEnum(4)
    qtw.QFrame.VLine = _StubEnum(5)
    qtw.QFrame.Sunken = _StubEnum(48)

    qtw.QAbstractItemView.NoSelection = _StubEnum(0)
    qtw.QAbstractItemView.SingleSelection = _StubEnum(1)
    qtw.QAbstractItemView.ExtendedSelection = _StubEnum(2)
    qtw.QAbstractItemView.SelectRows = _StubEnum(1)

    qtw.QHeaderView.Stretch = _StubEnum(1)
    qtw.QHeaderView.Fixed = _StubEnum(2)

    return qtw


def _install_pyside_mocks():
    """Try real PySide first; fall back to minimal shim."""
    try:
        import PySide6                # noqa: F401
        return
    except ImportError:
        pass
    try:
        import PySide2                # noqa: F401
        return
    except ImportError:
        pass

    qtcore = _build_qtcore()
    qtwidgets = _build_qtwidgets()
    qtgui = mock.MagicMock(name="QtGui")
    # QAction lives on QtGui in Qt6; on QtWidgets in Qt5. Provide both
    # so the compat shim's hasattr fix-up paths don't blow up.
    qtgui.QAction = type("QAction", (_Stub,), {})
    qtgui.QShortcut = type("QShortcut", (_Stub,), {})

    pyside6 = mock.MagicMock(name="PySide6")
    pyside6.QtCore = qtcore
    pyside6.QtWidgets = qtwidgets
    pyside6.QtGui = qtgui
    sys.modules['PySide6'] = pyside6
    sys.modules['PySide6.QtCore'] = qtcore
    sys.modules['PySide6.QtWidgets'] = qtwidgets
    sys.modules['PySide6.QtGui'] = qtgui

    sys.modules['shiboken6'] = mock.MagicMock(name='shiboken6')
    sys.modules['shiboken2'] = mock.MagicMock(name='shiboken2')


_install_package_path()
_install_maya_mocks()
_install_pyside_mocks()
