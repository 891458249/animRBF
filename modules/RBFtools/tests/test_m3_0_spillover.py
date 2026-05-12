"""M3.0-spillover tests (added in M3.2 commit per addendum §M3.0.5).

Helpers tested:
  * RBFToolsWindow.add_tools_action(label_key, callback)
  * _PoseEditorPanel.add_pose_row_action(label_key, callback, danger)

These tests live in their own file (not test_m3_2_mirror.py) so future
M3.x sub-tasks discovering "how do I extend the menu / right-click?"
find the test coverage for the helper API in one place.
"""

from __future__ import absolute_import

import conftest  # noqa: F401

import unittest


class T_AddToolsActionExists(unittest.TestCase):

    def test_method_callable(self):
        from RBFtools.ui.main_window import RBFToolsWindow
        self.assertTrue(callable(getattr(
            RBFToolsWindow, "add_tools_action", None)))


class T_AddPoseRowActionExists(unittest.TestCase):

    def test_method_callable(self):
        from RBFtools.ui.main_window import _PoseEditorPanel
        self.assertTrue(callable(getattr(
            _PoseEditorPanel, "add_pose_row_action", None)))


class T_RowMenuExtensionContract(unittest.TestCase):
    """Source-text contract: _show_row_menu MUST iterate
    self._extra_row_actions when present. This guards against
    refactors that drop the extension hook."""

    def test_show_row_menu_consumes_extra_actions(self):
        import pathlib
        path = pathlib.Path(__file__).resolve().parent.parent
        mw_path = (path / "scripts" / "RBFtools" / "ui" / "main_window.py")
        text = mw_path.read_text(encoding="utf-8")
        # Locate _show_row_menu body and confirm it references
        # _extra_row_actions.
        marker = "def _show_row_menu(self, pos):"
        idx = text.find(marker)
        self.assertGreater(idx, 0)
        # Take next ~80 lines as the method body.
        body = text[idx:idx + 4000]
        self.assertIn("_extra_row_actions", body,
            "_show_row_menu does not consume _extra_row_actions — "
            "addendum §M3.0.5 spillover contract violation")


if __name__ == "__main__":
    unittest.main()
