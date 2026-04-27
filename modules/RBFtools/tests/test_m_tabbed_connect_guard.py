"""M_TABBED_CONNECT_GUARD - Connect / Disconnect pre-flight idempotency
checks (2026-04-27 user request).

Behaviour:

  Connect with empty selection           -> "no attrs selected" notice
  Connect on source that already has attrs -> "already connected" notice
  Connect on source with attrs == []     -> proceed to controller call
  Disconnect on source with attrs == []  -> "nothing to disconnect" notice
  Disconnect on source that has attrs    -> proceed to controller call

Coverage:

* Source-scan: i18n keys + main_window guard helpers exist.
* Mock E2E: each branch of the two guards (driver + driven) drives
  controller.set_*_source_attrs only when the guard allows.
"""

from __future__ import absolute_import

import os
import unittest
from unittest import mock

import conftest


_REPO_ROOT = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..")
)
_MAIN_WINDOW = os.path.join(
    _REPO_ROOT, "modules", "RBFtools", "scripts", "RBFtools",
    "ui", "main_window.py")


def _read(p):
    with open(p, "r", encoding="utf-8") as fh:
        return fh.read()


# ----------------------------------------------------------------------
# Source-scan
# ----------------------------------------------------------------------


class TestM_TABBED_CONNECT_GUARD_SourceScan(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._main = _read(_MAIN_WINDOW)

    def test_helpers_present(self):
        self.assertIn("def _guard_attrs_apply", self._main)
        self.assertIn("def _guard_attrs_clear", self._main)

    def test_message_box_used(self):
        self.assertIn("QtWidgets.QMessageBox.information",
                      self._main,
            "guard helpers must surface a QMessageBox.information "
            "notice when the operation is short-circuited")

    def test_apply_slots_call_guard(self):
        # Both driver + driven Connect slots must consult the guard.
        for slot in ("def _on_driver_source_attrs_apply",
                     "def _on_driven_source_attrs_apply"):
            self.assertIn(slot, self._main)
        self.assertIn("self._guard_attrs_apply(", self._main)
        self.assertIn("self._guard_attrs_clear(", self._main)

    def test_i18n_keys_present(self):
        from RBFtools.ui import i18n
        for k in ("title_already_connected",
                  "msg_already_connected",
                  "title_nothing_to_disconnect",
                  "msg_nothing_to_disconnect",
                  "title_no_attrs_selected",
                  "msg_no_attrs_selected"):
            self.assertIn(k, i18n._EN, "missing EN key {}".format(k))
            self.assertIn(k, i18n._ZH, "missing ZH key {}".format(k))


# ----------------------------------------------------------------------
# Mock E2E for the guard branches
# ----------------------------------------------------------------------


@unittest.skipIf(conftest._REAL_MAYA,
    "mock-dependent (mock.patch on QtWidgets.QMessageBox + controller)")
class TestM_TABBED_CONNECT_GUARD_Lifecycle(unittest.TestCase):

    def _make_window(self, driver_sources=None, driven_sources=None):
        """Stub-construct an RBFToolsWindow without going through
        the real Qt + controller init - we only need _ctrl + the
        guard helpers to be reachable."""
        from RBFtools.ui.main_window import RBFToolsWindow
        win = RBFToolsWindow.__new__(RBFToolsWindow)
        win._ctrl = mock.MagicMock()
        win._ctrl.read_driver_sources.return_value = (
            driver_sources or [])
        win._ctrl.read_driven_sources.return_value = (
            driven_sources or [])
        return win

    def _src(self, attrs):
        from RBFtools.core import DriverSource
        return DriverSource(node="drv1", attrs=tuple(attrs),
                            weight=1.0, encoding=0)

    # ----- Connect guards --------------------------------------------

    def test_driver_apply_blocks_when_empty_selection(self):
        from RBFtools.ui.main_window import RBFToolsWindow
        win = self._make_window(driver_sources=[self._src([])])
        with mock.patch(
                "RBFtools.ui.main_window.QtWidgets.QMessageBox"
        ) as mb:
            RBFToolsWindow._on_driver_source_attrs_apply(win, 0, [])
        mb.information.assert_called_once()
        win._ctrl.set_driver_source_attrs.assert_not_called()

    def test_driver_apply_blocks_when_already_connected(self):
        from RBFtools.ui.main_window import RBFToolsWindow
        win = self._make_window(
            driver_sources=[self._src(["tx", "ty"])])
        with mock.patch(
                "RBFtools.ui.main_window.QtWidgets.QMessageBox"
        ) as mb:
            RBFToolsWindow._on_driver_source_attrs_apply(
                win, 0, ["rx", "ry"])
        mb.information.assert_called_once()
        win._ctrl.set_driver_source_attrs.assert_not_called()

    def test_driver_apply_proceeds_when_clean(self):
        from RBFtools.ui.main_window import RBFToolsWindow
        win = self._make_window(driver_sources=[self._src([])])
        with mock.patch(
                "RBFtools.ui.main_window.QtWidgets.QMessageBox"
        ) as mb:
            RBFToolsWindow._on_driver_source_attrs_apply(
                win, 0, ["tx"])
        mb.information.assert_not_called()
        win._ctrl.set_driver_source_attrs.assert_called_once_with(
            0, ["tx"])

    # ----- Disconnect guards -----------------------------------------

    def test_driver_clear_blocks_when_already_empty(self):
        from RBFtools.ui.main_window import RBFToolsWindow
        win = self._make_window(driver_sources=[self._src([])])
        with mock.patch(
                "RBFtools.ui.main_window.QtWidgets.QMessageBox"
        ) as mb:
            RBFToolsWindow._on_driver_source_attrs_clear(win, 0)
        mb.information.assert_called_once()
        win._ctrl.set_driver_source_attrs.assert_not_called()

    def test_driver_clear_proceeds_when_populated(self):
        """M_DISCONNECT_FIX (Phase 1, 2026-04-27): Disconnect on a
        populated source now routes through
        controller.disconnect_driver_source_attrs (direct
        disconnect) instead of the previous
        set_driver_source_attrs(idx, []) rebuild path."""
        from RBFtools.ui.main_window import RBFToolsWindow
        win = self._make_window(
            driver_sources=[self._src(["tx", "ty"])])
        with mock.patch(
                "RBFtools.ui.main_window.QtWidgets.QMessageBox"
        ) as mb:
            RBFToolsWindow._on_driver_source_attrs_clear(win, 0)
        mb.information.assert_not_called()
        win._ctrl.disconnect_driver_source_attrs.\
            assert_called_once_with(0)
        win._ctrl.set_driver_source_attrs.assert_not_called()

    # ----- Driven side: same shape ----------------------------------

    def test_driven_apply_blocks_when_already_connected(self):
        from RBFtools.ui.main_window import RBFToolsWindow
        from RBFtools.core import DrivenSource
        win = self._make_window(
            driven_sources=[DrivenSource(
                node="d1", attrs=("ty",))])
        with mock.patch(
                "RBFtools.ui.main_window.QtWidgets.QMessageBox"
        ) as mb:
            RBFToolsWindow._on_driven_source_attrs_apply(
                win, 0, ["tx"])
        mb.information.assert_called_once()
        win._ctrl.set_driven_source_attrs.assert_not_called()

    def test_driven_clear_blocks_when_already_empty(self):
        from RBFtools.ui.main_window import RBFToolsWindow
        from RBFtools.core import DrivenSource
        win = self._make_window(
            driven_sources=[DrivenSource(node="d1", attrs=())])
        with mock.patch(
                "RBFtools.ui.main_window.QtWidgets.QMessageBox"
        ) as mb:
            RBFToolsWindow._on_driven_source_attrs_clear(win, 0)
        mb.information.assert_called_once()
        win._ctrl.set_driven_source_attrs.assert_not_called()


# ----------------------------------------------------------------------
# M_TABBED_ADD_GUARD - Add Driver/Driven dedup pre-flight check
# ----------------------------------------------------------------------


class TestM_TABBED_ADD_GUARD_SourceScan(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._main = _read(_MAIN_WINDOW)

    def test_helper_present(self):
        self.assertIn("def _guard_add_dedup", self._main)

    def test_add_slots_call_dedup_guard(self):
        for slot in ("def _on_driver_source_add_requested",
                     "def _on_driven_source_add_requested"):
            self.assertIn(slot, self._main)
        # Both add slots must call the dedup guard.
        self.assertGreaterEqual(
            self._main.count("self._guard_add_dedup("), 2,
            "both driver + driven add slots must call "
            "_guard_add_dedup")

    def test_i18n_keys_present(self):
        from RBFtools.ui import i18n
        for k in ("title_driver_already_added",
                  "msg_driver_all_already_added",
                  "msg_driver_some_already_added",
                  "title_driven_already_added",
                  "msg_driven_all_already_added",
                  "msg_driven_some_already_added"):
            self.assertIn(k, i18n._EN, "missing EN key {}".format(k))
            self.assertIn(k, i18n._ZH, "missing ZH key {}".format(k))


@unittest.skipIf(conftest._REAL_MAYA,
    "mock-dependent (mock.patch on QtWidgets.QMessageBox)")
class TestM_TABBED_ADD_GUARD_Lifecycle(unittest.TestCase):

    def _make_window(self, driver_sources=None, driven_sources=None):
        from RBFtools.ui.main_window import RBFToolsWindow
        win = RBFToolsWindow.__new__(RBFToolsWindow)
        win._ctrl = mock.MagicMock()
        win._ctrl.read_driver_sources.return_value = (
            driver_sources or [])
        win._ctrl.read_driven_sources.return_value = (
            driven_sources or [])
        return win

    def _drv(self, node):
        from RBFtools.core import DriverSource
        return DriverSource(node=node, attrs=tuple(),
                            weight=1.0, encoding=0)

    def _dvn(self, node):
        from RBFtools.core import DrivenSource
        return DrivenSource(node=node, attrs=tuple())

    # ----- Driver -----------------------------------------------

    def test_driver_dedup_returns_all_when_no_overlap(self):
        from RBFtools.ui.main_window import RBFToolsWindow
        win = self._make_window(
            driver_sources=[self._drv("alreadyA")])
        with mock.patch(
                "RBFtools.ui.main_window.QtWidgets.QMessageBox"
        ) as mb:
            new_nodes = RBFToolsWindow._guard_add_dedup(
                win, "driver", ["newA", "newB"])
        self.assertEqual(new_nodes, ["newA", "newB"])
        mb.information.assert_not_called()

    def test_driver_dedup_skips_duplicates_and_notifies(self):
        from RBFtools.ui.main_window import RBFToolsWindow
        win = self._make_window(
            driver_sources=[self._drv("dupA"), self._drv("dupB")])
        with mock.patch(
                "RBFtools.ui.main_window.QtWidgets.QMessageBox"
        ) as mb:
            new_nodes = RBFToolsWindow._guard_add_dedup(
                win, "driver", ["dupA", "newA", "dupB", "newB"])
        self.assertEqual(new_nodes, ["newA", "newB"])
        mb.information.assert_called_once()

    def test_driver_dedup_blocks_when_all_duplicates(self):
        from RBFtools.ui.main_window import RBFToolsWindow
        win = self._make_window(
            driver_sources=[self._drv("a"), self._drv("b")])
        with mock.patch(
                "RBFtools.ui.main_window.QtWidgets.QMessageBox"
        ) as mb:
            new_nodes = RBFToolsWindow._guard_add_dedup(
                win, "driver", ["a", "b"])
        self.assertEqual(new_nodes, [])
        mb.information.assert_called_once()

    # ----- Driven (mirrors) -------------------------------------

    def test_driven_dedup_blocks_when_all_duplicates(self):
        from RBFtools.ui.main_window import RBFToolsWindow
        win = self._make_window(
            driven_sources=[self._dvn("dvnA")])
        with mock.patch(
                "RBFtools.ui.main_window.QtWidgets.QMessageBox"
        ) as mb:
            new_nodes = RBFToolsWindow._guard_add_dedup(
                win, "driven", ["dvnA"])
        self.assertEqual(new_nodes, [])
        mb.information.assert_called_once()


if __name__ == "__main__":
    unittest.main()
