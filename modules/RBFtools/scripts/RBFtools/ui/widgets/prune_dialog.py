# -*- coding: utf-8 -*-
"""PruneDialog — modal dry-run preview for the M3.1 Pose Pruner.

Three-checkbox interaction (addendum §M3.1 G.2): user toggles which
of Duplicate / Redundant-input / Constant-output classes to act on.
On every toggle, the dialog re-runs ``core_prune.analyse_node`` for
the current options and rerenders the preview pane.

Click "Prune" → dialog returns Accepted; the caller (main_window)
delegates to ``controller.prune_current_node(opts)`` which performs
the path A confirm + execute. The dialog itself does NOT mutate the
scene (MVC red line) — even for the dry-run analysis it only calls
the core read-only helper.
"""

from __future__ import absolute_import

from RBFtools.ui.compat import QtWidgets, QtCore
from RBFtools.ui.i18n import tr


class PruneDialog(QtWidgets.QDialog):
    """Modal preview + per-class checkboxes for one Prune Poses
    operation."""

    def __init__(self, node_name, controller, parent=None):
        super(PruneDialog, self).__init__(parent)
        self._node_name = node_name
        self._ctrl = controller

        self.setWindowTitle(tr("title_prune_poses"))
        self.setModal(True)

        layout = QtWidgets.QVBoxLayout(self)

        # ----- Three independent checkboxes (G.2) -----
        self._cb_duplicates = QtWidgets.QCheckBox(tr("prune_cb_duplicates"))
        self._cb_redundant = QtWidgets.QCheckBox(tr("prune_cb_redundant"))
        self._cb_constant = QtWidgets.QCheckBox(tr("prune_cb_constant"))
        self._cb_duplicates.setChecked(True)
        self._cb_redundant.setChecked(True)
        self._cb_constant.setChecked(True)
        for cb in (self._cb_duplicates, self._cb_redundant,
                   self._cb_constant):
            cb.toggled.connect(self._refresh_preview)
            layout.addWidget(cb)

        # ----- Preview pane -----
        layout.addWidget(QtWidgets.QLabel(tr("label_prune_preview")))
        self._preview = QtWidgets.QPlainTextEdit()
        self._preview.setReadOnly(True)
        self._preview.setStyleSheet(
            "font-family: 'Consolas', 'Monaco', 'Courier New', monospace;")
        layout.addWidget(self._preview)

        # ----- Buttons -----
        btn_box = QtWidgets.QHBoxLayout()
        btn_box.addStretch(1)
        self._btn_prune = QtWidgets.QPushButton(tr("btn_prune"))
        self._btn_prune.setToolTip(tr("prune_dialog_btn_tip"))
        self._btn_cancel = QtWidgets.QPushButton(tr("cancel"))
        self._btn_prune.clicked.connect(self.accept)
        self._btn_cancel.clicked.connect(self.reject)
        btn_box.addWidget(self._btn_prune)
        btn_box.addWidget(self._btn_cancel)
        layout.addLayout(btn_box)

        # Initial render.
        try:
            self._refresh_preview()
        except Exception:
            self._preview.setPlainText(tr("status_prune_failed"))

    def _refresh_preview(self, *_):
        """Re-run dry-run for the current checkbox state and render."""
        from RBFtools import core_prune
        from RBFtools.controller import MainController
        opts = self.get_options()
        try:
            action = core_prune.analyse_node(self._node_name, opts)
        except Exception as exc:
            self._preview.setPlainText(
                tr("status_prune_failed") + "\n" + str(exc))
            self._btn_prune.setEnabled(False)
            return
        text = MainController._format_prune_report(self._node_name, action)
        self._preview.setPlainText(text)
        # Enable Prune button only when at least one class actually
        # applies (conflict pairs alone do NOT count — H.3).
        self._btn_prune.setEnabled(action.has_changes())

    def get_options(self):
        """Return a :class:`core_prune.PruneOptions` reflecting the
        current checkbox state."""
        from RBFtools import core_prune
        return core_prune.PruneOptions(
            duplicates=self._cb_duplicates.isChecked(),
            redundant_inputs=self._cb_redundant.isChecked(),
            constant_outputs=self._cb_constant.isChecked(),
        )
