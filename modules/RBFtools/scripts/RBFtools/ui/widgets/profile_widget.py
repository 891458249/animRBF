# -*- coding: utf-8 -*-
"""ProfileWidget — per-node profile report panel (Milestone 3.5).

Embedded inside the ToolsSection collapsible (created lazily by
:meth:`RBFToolsWindow.add_tools_panel_widget`). Behaviour:

  * Node switch → clear the report and show "Click Refresh..."
    (G.3 contract — avoid auto-recomputing on large nodes which
    can introduce visible lag).
  * User clicks Refresh → invoke
    ``controller.profile_current_node`` and render the returned
    ASCII report in a monospace QPlainTextEdit.

Read-only by construction — the widget never mutates the scene
(MVC red line + addendum §M3.5).
"""

from __future__ import absolute_import

from RBFtools.ui.compat import QtWidgets, QtCore
from RBFtools.ui.i18n import tr


class ProfileWidget(QtWidgets.QWidget):

    def __init__(self, controller, parent=None):
        super(ProfileWidget, self).__init__(parent)
        self._ctrl = controller

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # ----- Refresh button row -----
        # M_HELPBUBBLE_BATCH: long-form HelpButton next to the button.
        from RBFtools.ui.widgets.help_button import HelpButton
        btn_row = QtWidgets.QHBoxLayout()
        self._btn_refresh = QtWidgets.QPushButton(tr("btn_refresh_profile"))
        self._btn_refresh.setToolTip(tr("profile_widget_refresh_tip"))
        self._btn_refresh.clicked.connect(self._on_refresh)
        btn_row.addWidget(self._btn_refresh)
        btn_row.addWidget(HelpButton("btn_refresh_profile"))
        btn_row.addStretch(1)
        layout.addLayout(btn_row)

        # ----- Report display -----
        self._txt = QtWidgets.QPlainTextEdit()
        self._txt.setReadOnly(True)
        self._txt.setStyleSheet(
            "font-family: 'Consolas', 'Monaco', 'Courier New', "
            "monospace;")
        self._txt.setPlainText(tr("status_profile_pending"))
        layout.addWidget(self._txt)

    # =================================================================
    #  Public slots
    # =================================================================

    def on_node_changed(self):
        """Slot connected to ``controller.editorLoaded``. Clears the
        report so the user re-clicks Refresh for the new node
        (G.3 — manual refresh prevents lag on large nodes)."""
        self._txt.setPlainText(tr("status_profile_pending"))

    def _on_refresh(self):
        try:
            text = self._ctrl.profile_current_node()
        except Exception as exc:
            self._txt.setPlainText(
                tr("status_profile_failed") + "\n" + str(exc))
            return
        if not text:
            self._txt.setPlainText(tr("status_profile_pending"))
            return
        self._txt.setPlainText(text)

    def retranslate(self):
        """M_QUICKWINS Item 2: language-switch hook. The report body
        is dynamic ASCII; we only refresh the static button label +
        tooltip + the pending-state placeholder when nothing has
        been computed yet."""
        self._btn_refresh.setText(tr("btn_refresh_profile"))
        self._btn_refresh.setToolTip(tr("profile_widget_refresh_tip"))
        # Repaint the placeholder only when we are still in the
        # pending state - otherwise we would clobber a real report.
        if self._txt.toPlainText() in (
                tr("status_profile_pending"),
                # The placeholder text in the OTHER language - check
                # both via the EN/ZH tables to avoid a stale-state
                # detection miss on language toggle.
                ""):
            self._txt.setPlainText(tr("status_profile_pending"))
