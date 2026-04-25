# -*- coding: utf-8 -*-
"""ImportDialog — modal preview / mode-picker for the M3.3 import flow.

Two-stage interaction:

  1. On open, the dialog runs ``core_json.dry_run`` against the JSON
     and renders a per-node OK / FAIL summary in a read-only
     QPlainTextEdit (same widget M3.0 ConfirmDialog uses for preview).
  2. User picks Add / Replace via radios and clicks Import → the
     dialog returns Accepted; the caller (main_window) then delegates
     to ``controller.import_rbf_setup`` which performs the path A
     confirm-and-execute (only when Replace would overwrite).

This dialog itself does NOT mutate the scene — that is the
controller's responsibility (MVC red line).
"""

from __future__ import absolute_import

from RBFtools.ui.compat import QtWidgets, QtCore
from RBFtools.ui.i18n import tr


class ImportDialog(QtWidgets.QDialog):
    """Modal preview + mode-picker for an Import RBF Setup operation."""

    MODE_ADD = "add"
    MODE_REPLACE = "replace"

    def __init__(self, json_path, controller, parent=None):
        super(ImportDialog, self).__init__(parent)
        self._json_path = json_path
        self._ctrl = controller
        self._mode = self.MODE_ADD

        self.setWindowTitle(tr("title_import_rbf"))
        self.setModal(True)

        layout = QtWidgets.QVBoxLayout(self)

        # ----- Mode radios -----
        mode_box = QtWidgets.QHBoxLayout()
        mode_box.addWidget(QtWidgets.QLabel(tr("label_import_mode")))
        self._radio_add = QtWidgets.QRadioButton(tr("import_mode_add"))
        self._radio_replace = QtWidgets.QRadioButton(
            tr("import_mode_replace"))
        self._radio_add.setChecked(True)
        self._radio_add.toggled.connect(self._on_mode_changed)
        self._radio_replace.toggled.connect(self._on_mode_changed)
        mode_box.addWidget(self._radio_add)
        mode_box.addWidget(self._radio_replace)
        mode_box.addStretch(1)
        layout.addLayout(mode_box)

        # ----- Preview pane (dry-run output) -----
        layout.addWidget(QtWidgets.QLabel(tr("label_import_preview")))
        self._preview = QtWidgets.QPlainTextEdit()
        self._preview.setReadOnly(True)
        self._preview.setPlainText(tr("status_dry_run_loading"))
        layout.addWidget(self._preview)

        # ----- Buttons -----
        btn_box = QtWidgets.QHBoxLayout()
        btn_box.addStretch(1)
        self._btn_import = QtWidgets.QPushButton(tr("btn_import"))
        self._btn_cancel = QtWidgets.QPushButton(tr("cancel"))
        self._btn_import.clicked.connect(self.accept)
        self._btn_cancel.clicked.connect(self.reject)
        btn_box.addWidget(self._btn_import)
        btn_box.addWidget(self._btn_cancel)
        layout.addLayout(btn_box)

        # Run dry-run once at open and on every mode change. Sub-tasks
        # may import the dialog without instantiating it (mock tests),
        # so guard the initial render.
        try:
            self._refresh_preview()
        except Exception:
            self._preview.setPlainText(tr("status_dry_run_failed"))

    def _on_mode_changed(self, _checked):
        self._mode = (self.MODE_REPLACE if self._radio_replace.isChecked()
                      else self.MODE_ADD)
        self._refresh_preview()

    def _refresh_preview(self):
        """Re-run dry_run for the current mode and render the report."""
        from RBFtools import core_json
        try:
            data = core_json.read_json_with_schema_check(self._json_path)
            reports = core_json.dry_run(data, mode=self._mode)
        except core_json.SchemaVersionError as exc:
            self._preview.setPlainText(
                tr("status_schema_version_error") + "\n" + str(exc))
            self._btn_import.setEnabled(False)
            return
        except core_json.SchemaValidationError as exc:
            self._preview.setPlainText("\n".join(exc.errors))
            self._btn_import.setEnabled(False)
            return
        # Reuse the controller's static formatter so the preview here
        # and the path A confirm preview look identical.
        from RBFtools.controller import MainController
        text = MainController._format_dry_run_report(reports)
        self._preview.setPlainText(text)
        any_ok = any(r.ok for r in reports)
        self._btn_import.setEnabled(any_ok)

    def get_mode(self):
        """Return ``"add"`` or ``"replace"`` per the radio state."""
        return self._mode
