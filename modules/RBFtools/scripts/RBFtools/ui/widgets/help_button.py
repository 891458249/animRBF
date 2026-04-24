# -*- coding: utf-8 -*-
"""
Help button widget — '?' button with hover/pin tooltip bubble.
"""

from __future__ import absolute_import

from RBFtools.ui.compat import QtWidgets, QtCore


class HelpBubble(QtWidgets.QWidget):
    """A floating tooltip-like bubble that can be pinned.

    - Unpinned: appears on hover, disappears on leave.
    - Pinned: stays visible and follows the main window.
    """

    def __init__(self, parent=None):
        super(HelpBubble, self).__init__(
            parent,
            QtCore.Qt.Tool
            | QtCore.Qt.FramelessWindowHint
            | QtCore.Qt.WindowStaysOnTopHint
        )
        self.setAttribute(QtCore.Qt.WA_ShowWithoutActivating)
        self.setStyleSheet(
            "HelpBubble {"
            "  background: #2b2b2b;"
            "  border: 1px solid #555;"
            "  border-radius: 6px;"
            "  padding: 8px;"
            "}"
            "QLabel {"
            "  color: #ddd;"
            "  font-size: 12px;"
            "  background: transparent;"
            "}"
        )
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(10, 8, 10, 8)
        self._label = QtWidgets.QLabel()
        self._label.setWordWrap(True)
        self._label.setMaximumWidth(280)
        lay.addWidget(self._label)

    def set_text(self, text):
        self._label.setText(text)
        self.adjustSize()

    def reposition(self, anchor_global_pos):
        """Position the bubble to the right of the anchor point."""
        self.move(anchor_global_pos.x() + 20, anchor_global_pos.y() - 10)


class HelpButton(QtWidgets.QToolButton):
    """Small '?' button with hover and click tooltip behavior."""

    # Class-level tracking: only one pinned bubble at a time
    _active_pinned = None

    def __init__(self, help_key, parent=None):
        super(HelpButton, self).__init__(parent)
        self._help_key = help_key
        self._pinned = False
        self._bubble = None
        self._main_window = None

        self.setText("?")
        self.setFixedSize(18, 18)
        self.setStyleSheet(
            "QToolButton {"
            "  border: 1px solid #666;"
            "  border-radius: 9px;"
            "  background: #3a3a3a;"
            "  color: #aaa;"
            "  font-size: 11px;"
            "  font-weight: bold;"
            "}"
            "QToolButton:hover {"
            "  background: #505050;"
            "  color: #fff;"
            "  border-color: #888;"
            "}"
        )
        self.setCursor(QtCore.Qt.PointingHandCursor)
        self.clicked.connect(self._on_click)

    def _get_bubble(self):
        if self._bubble is None:
            self._bubble = HelpBubble()
        return self._bubble

    def _find_main_window(self):
        """Walk up the parent chain to find the QMainWindow."""
        if self._main_window is not None:
            return self._main_window
        w = self.parent()
        while w is not None:
            if isinstance(w, QtWidgets.QMainWindow):
                self._main_window = w
                return w
            w = w.parent()
        return None

    def _show_bubble(self):
        bubble = self._get_bubble()
        from RBFtools.ui.help_texts import get_help_text
        bubble.set_text(get_help_text(self._help_key))
        bubble.reposition(self.mapToGlobal(QtCore.QPoint(self.width(), 0)))
        bubble.show()

    def _hide_bubble(self):
        if self._bubble is not None:
            self._bubble.hide()

    def _on_click(self):
        if self._pinned:
            self._pinned = False
            self._hide_bubble()
            self._uninstall_move_filter()
            if HelpButton._active_pinned is self:
                HelpButton._active_pinned = None
        else:
            if HelpButton._active_pinned is not None and HelpButton._active_pinned is not self:
                HelpButton._active_pinned._on_click()
            self._pinned = True
            HelpButton._active_pinned = self
            self._show_bubble()
            self._install_move_filter()

    def _install_move_filter(self):
        win = self._find_main_window()
        if win:
            win.installEventFilter(self)

    def _uninstall_move_filter(self):
        win = self._find_main_window()
        if win:
            win.removeEventFilter(self)

    def eventFilter(self, obj, event):
        """Track main window move/resize to reposition pinned bubble."""
        if event.type() in (QtCore.QEvent.Move, QtCore.QEvent.Resize):
            if self._pinned and self._bubble and self._bubble.isVisible():
                self._bubble.reposition(
                    self.mapToGlobal(QtCore.QPoint(self.width(), 0)))
        return False

    def enterEvent(self, event):
        if not self._pinned:
            self._show_bubble()
        super(HelpButton, self).enterEvent(event)

    def leaveEvent(self, event):
        if not self._pinned:
            self._hide_bubble()
        super(HelpButton, self).leaveEvent(event)

    def hideEvent(self, event):
        """Clean up when the button itself is hidden."""
        if self._pinned:
            self._pinned = False
            if HelpButton._active_pinned is self:
                HelpButton._active_pinned = None
            self._uninstall_move_filter()
        self._hide_bubble()
        super(HelpButton, self).hideEvent(event)


class ComboHelpButton(HelpButton):
    """HelpButton that dynamically shows help text based on a QComboBox's
    current selection or hovered item in the open dropdown.

    - Hover / click '?': shows help for the *current* combo index.
    - While pinned + combo dropdown open: hovering over items updates
      the bubble text in real time.
    - When dropdown closes or item is selected: updates to the final
      selected index.

    Parameters
    ----------
    combo : QComboBox
        The combo box to observe.
    key_map : list[str]
        Help text keys indexed by combo index.
    fallback_key : str
        Static key used if combo index is out of range.
    """

    def __init__(self, combo, key_map, fallback_key="", parent=None):
        super(ComboHelpButton, self).__init__(
            fallback_key or key_map[0], parent)
        self._combo = combo
        self._key_map = key_map
        self._fallback_key = fallback_key
        # Update when an item is actually selected
        self._combo.currentIndexChanged.connect(self._on_combo_changed)
        # Update when an item is merely hovered/highlighted in the open popup
        self._combo.highlighted.connect(self._on_combo_highlighted)

    def _help_key_for_index(self, idx):
        if 0 <= idx < len(self._key_map):
            return self._key_map[idx]
        return self._fallback_key or self._help_key

    def _current_help_key(self):
        return self._help_key_for_index(self._combo.currentIndex())

    def _show_bubble(self):
        bubble = self._get_bubble()
        from RBFtools.ui.help_texts import get_help_text
        bubble.set_text(get_help_text(self._current_help_key()))
        bubble.reposition(self.mapToGlobal(QtCore.QPoint(self.width(), 0)))
        bubble.show()

    def _refresh_bubble_for_index(self, idx):
        """Update an already-visible pinned bubble to show help for *idx*."""
        if self._pinned and self._bubble is not None and self._bubble.isVisible():
            from RBFtools.ui.help_texts import get_help_text
            self._bubble.set_text(get_help_text(self._help_key_for_index(idx)))

    def _on_combo_changed(self, index):
        """Fired when user actually selects (clicks) an item."""
        self._refresh_bubble_for_index(index)

    def _on_combo_highlighted(self, index):
        """Fired when user hovers over an item in the open dropdown popup."""
        self._refresh_bubble_for_index(index)
