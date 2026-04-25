# -*- coding: utf-8 -*-
"""ConfirmDialog — modal preview-and-confirm dialog (Milestone 3.0).

Layout::

    ┌─────────────────────────────────────────┐
    │ Summary: <one-line description>         │
    ├─────────────────────────────────────────┤
    │ ┌─────────────────────────────────────┐ │
    │ │ Preview text                        │ │
    │ │ (QPlainTextEdit, read-only,         │ │
    │ │  monospace; caller serialises       │ │
    │ │  preview content to ASCII)          │ │
    │ └─────────────────────────────────────┘ │
    ├─────────────────────────────────────────┤
    │ [✓] Don't ask again for this action     │
    │              [Cancel]   [OK]            │
    └─────────────────────────────────────────┘

Used by every M3.x destructive operation (Pruner / Mirror / Import).
Sub-tasks should call ``MainController.ask_confirm(...)`` rather than
this class directly — keeps the MVC red line clean (addendum §M3.0
access path A).

The "Don't ask again" preference is persisted via Maya optionVars
named ``RBFtools_skip_confirm_<action_id>``. The persistence helpers
live in ``RBFtools.core`` (alongside the filter persistence helpers)
per addendum §M3.0 soft-suggestion centralisation.
"""

from __future__ import absolute_import

from RBFtools.ui.compat import QtWidgets, QtCore
from RBFtools.ui.i18n import tr


class ConfirmDialog(QtWidgets.QDialog):
    """Modal confirm-with-preview dialog.

    Parameters
    ----------
    title : str
        Window title (already translated by caller).
    summary : str
        One-line description shown above the preview pane.
    preview_text : str
        Multi-line ASCII preview body (monospace). Caller serialises
        complex preview data to plain text — addendum §M3.0 (A)①.
    action_id : str
        Stable snake_case identifier used to persist the
        "Don't ask again" preference (e.g. ``"prune_poses"``).
    parent : QWidget or None
        Parent widget (typically the main window).
    """

    def __init__(self, title, summary, preview_text,
                 action_id, parent=None):
        super(ConfirmDialog, self).__init__(parent)
        self._action_id = action_id
        self.setWindowTitle(title)
        self.setModal(True)
        self.resize(480, 320)
        self._build(summary, preview_text)

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def _build(self, summary, preview_text):
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(10, 10, 10, 10)
        lay.setSpacing(8)

        self._lbl_summary = QtWidgets.QLabel(summary)
        self._lbl_summary.setWordWrap(True)
        self._lbl_summary.setStyleSheet("font-weight: bold;")
        lay.addWidget(self._lbl_summary)

        self._txt_preview = QtWidgets.QPlainTextEdit()
        self._txt_preview.setReadOnly(True)
        self._txt_preview.setPlainText(preview_text or "")
        # Monospace: caller serialises to text, alignment via spaces.
        self._txt_preview.setStyleSheet(
            "font-family: 'Consolas', 'Monaco', 'Courier New', monospace;")
        lay.addWidget(self._txt_preview, 1)

        self._cb_dont_ask = QtWidgets.QCheckBox(tr("confirm_dont_ask"))
        lay.addWidget(self._cb_dont_ask)

        btn_row = QtWidgets.QHBoxLayout()
        btn_row.addStretch()
        self._btn_cancel = QtWidgets.QPushButton(tr("cancel"))
        self._btn_ok = QtWidgets.QPushButton(tr("ok"))
        self._btn_ok.setDefault(True)
        self._btn_cancel.clicked.connect(self.reject)
        self._btn_ok.clicked.connect(self.accept)
        btn_row.addWidget(self._btn_cancel)
        btn_row.addWidget(self._btn_ok)
        lay.addLayout(btn_row)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def is_dont_ask_again_checked(self):
        return self._cb_dont_ask.isChecked()

    @classmethod
    def confirm(cls, title, summary, preview_text, action_id,
                parent=None):
        """Synchronous confirm helper. Returns ``True`` if the user
        clicked OK (or had previously silenced this action), ``False``
        on Cancel / close.

        Side effect: when the user clicks OK with "Don't ask again"
        checked, persists the preference via :func:`core.set_skip_confirm`
        so subsequent calls with the same ``action_id`` skip the
        dialog and return True immediately.
        """
        # Lazy import — keeps confirm_dialog from depending on core
        # at module-import time (cheaper test mocks).
        from RBFtools import core
        if not core.should_show_confirm_dialog(action_id):
            return True
        dlg = cls(title, summary, preview_text, action_id, parent)
        result = dlg.exec_()
        if result == QtWidgets.QDialog.Accepted:
            if dlg.is_dont_ask_again_checked():
                core.set_skip_confirm(action_id, True)
            return True
        return False
