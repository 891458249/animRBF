"""Pytest / unittest discovery shim — Maya + PySide mock framework.

Dual-environment support
------------------------
Loaded automatically by pytest, and explicitly imported by widget tests
(``import conftest # noqa``) to fire the same setup under
``python -m unittest`` discovery.

Two environments are supported:

  * **Pure Python** (``python``): every Maya / PySide / shiboken
    module is mocked at ``sys.modules`` level. ~0.4 s per full
    sweep. Used for development-time fast feedback.

  * **mayapy 2025** (``mayapy.exe``): real ``maya.cmds``,
    ``maya.api.OpenMaya``, ``maya.OpenMayaUI``, ``maya.utils``,
    ``PySide6 6.5.3``, ``shiboken6`` resolve via the normal
    import machinery — **no module-level mocks installed**.
    ~5 s per full sweep (Maya init dominates). Used for
    integration verification + the M1.5 spillover bucket.

Why mocks must be skipped under real mayapy
-------------------------------------------
PySide6's ``shibokensupport`` installs a hook into Python's
``__import__`` that calls ``module.__name__`` on every imported
module. ``MagicMock(name='maya.cmds')`` only sets the *mock's*
own repr name — the dunder ``__name__`` lookup raises
``AttributeError``. The fix is structural: under mayapy we let
the real modules resolve and never plant a mock that the
shiboken hook would later trip over. Verified F3, addendum
§M1.5-conftest.F3.

Detection contract (T_CONFTEST_DUAL_ENV permanent guard)
--------------------------------------------------------
Two conditions both required:

    1. ``sys.executable``'s basename starts with ``mayapy``
       (cross-platform — no ``.exe`` assumption).
    2. ``import maya.cmds`` succeeds.

Both must be checked because (1) alone is fooled when someone
aliases ``python`` to ``mayapy``, and (2) alone is fooled by
our own pre-installed mocks. The conjunction is the right
answer; the probe MUST run BEFORE any mock install.

Mock framework (pure-Python branch)
-----------------------------------
The PySide minimal shim provides real classes for widget
inheritance — ``class Foo(QtWidgets.QWidget)`` requires
``QtWidgets.QWidget`` to be a real class with a working
metaclass; a MagicMock instance triggers Python's metaclass
machinery in a way that makes the *subclass* a MagicMock too,
hiding the user-defined methods we want to introspect (v5
addendum §M2.4a PySide-mock-trap discussion).

The shim is intentionally tiny: just enough to let widget
classes *be defined* and *introspected*. Instantiation requires
a real QApplication and is reserved for M1.5 mayapy E2E tests.

Maya version compatibility
--------------------------
The dual-env support is verified on **Maya 2025 only**
(Python 3.11.4 + PySide6 6.5.3). Maya 2022 (Python 3.7 +
PySide2) compatibility is deferred to M5; until then assume
mayapy testing only passes on Maya 2025. See addendum
§M1.5-conftest caveat block + tests/README.md.
"""

from __future__ import absolute_import

import os
import sys
from unittest import mock


# =====================================================================
# 0. Dual-environment detection (T_CONFTEST_DUAL_ENV PERMANENT GUARD)
# =====================================================================
#
# MUST run before any mock install. The detection probe imports
# maya.cmds — which would succeed against an already-installed
# mock — so the probe lives at the very top of the conftest
# evaluation order.

def _has_real_maya():
    """True iff we're running under a real mayapy interpreter AND
    maya.cmds is importable. Two conditions both required.

    See T_CONFTEST_DUAL_ENV permanent guard — addendum §M1.5-conftest.
    """
    base = os.path.basename(sys.executable).lower()
    if not base.startswith("mayapy"):
        return False
    try:
        import maya.cmds  # noqa: F401
        return True
    except ImportError:
        return False


_REAL_MAYA = _has_real_maya()


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
        # M3.0 / M3.2 additions:
        "QMainWindow", "QFormLayout", "QPlainTextEdit",
        "QRadioButton",
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


_install_package_path()    # always — pure sys.path; no maya dependency

if not _REAL_MAYA:
    # Pure-Python environment: full mock framework. The 12
    # sys.modules mock targets are deliberately enumerated in the
    # _install_*_mocks helpers above so the T_CONFTEST_DUAL_ENV
    # permanent guard can grep their names from this file's source
    # to verify the contract.
    _install_maya_mocks()
    _install_pyside_mocks()
# else: real mayapy — let the real maya.* / PySide6 / shiboken6
# resolve naturally. Skipping mocks is the structural fix for the
# AttributeError __name__ chain (addendum §M1.5-conftest.F3).
#
# T_CONFTEST_DUAL_ENV permanent guard explicitly forbids:
#   - calling maya.standalone.initialize() in this branch
#     (that's M1.5 spillover, NOT this sub-task's responsibility)
#   - removing any mock target name from _install_maya_mocks /
#     _install_pyside_mocks (would silently break pure-Python tests)
