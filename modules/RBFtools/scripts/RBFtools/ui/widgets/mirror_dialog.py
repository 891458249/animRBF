# -*- coding: utf-8 -*-
"""MirrorDialog — modal configuration dialog for the Mirror Tool (M3.2).

Two-stage interaction (addendum §M3.2 Q10):

  1. User picks source / mirror axis / naming rule + sees auto-resolved
     target name preview, validation status (no_match / both_match
     / unchanged) live-updates the Mirror button enabled state.
  2. User clicks Mirror → controller wires path A confirm dialog
     (preview text per §Q8) before actual execution.

Signals only — never imports ``RBFtools.core`` at module level (MVC).
The lazy-import inside ``_recompute_target_preview`` is acceptable
because the controller already imported core_mirror at the call-site.
"""

from __future__ import absolute_import

from RBFtools.ui.compat import QtWidgets, QtCore
from RBFtools.ui.i18n import tr
from RBFtools.ui.widgets.help_button import HelpButton
from RBFtools.constants import (
    # No M3.2-specific constant additions; we read the naming rule
    # presets directly from RBFtools.core_mirror at run time.
)


class MirrorDialog(QtWidgets.QDialog):
    """Modal Mirror configuration dialog. Returns a dict via
    ``get_config()`` after ``exec_()`` returns Accepted, or None on
    Cancel."""

    def __init__(self, source_node, parent=None):
        super(MirrorDialog, self).__init__(parent)
        self._source_node = source_node
        self.setWindowTitle(tr("title_mirror_node"))
        self.setModal(True)
        self.resize(520, 380)
        self._build()
        self._recompute_target_preview()

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def _build(self):
        from RBFtools import core_mirror
        lay = QtWidgets.QFormLayout(self)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setVerticalSpacing(8)

        # Source (read-only display).
        self._lbl_src_caption = QtWidgets.QLabel(tr("label_source_node"))
        self._lbl_src_value = QtWidgets.QLabel(self._source_node)
        self._lbl_src_value.setStyleSheet("font-weight: bold;")
        lay.addRow(self._lbl_src_caption, self._lbl_src_value)

        # Mirror axis dropdown.
        self._lbl_axis = QtWidgets.QLabel(tr("label_mirror_axis"))
        self._cmb_axis = QtWidgets.QComboBox()
        for key in ("mirror_axis_yz", "mirror_axis_xz", "mirror_axis_xy"):
            self._cmb_axis.addItem(tr(key))
        self._cmb_axis.setCurrentIndex(core_mirror.AXIS_X)
        self._cmb_axis.currentIndexChanged.connect(
            self._recompute_target_preview)
        lay.addRow(self._lbl_axis, self._cmb_axis)

        # Naming rule dropdown.
        self._lbl_rule = QtWidgets.QLabel(tr("label_naming_rule"))
        self._cmb_rule = QtWidgets.QComboBox()
        for _fp, _fr, _rp, _rr, label_key in core_mirror.NAMING_PRESETS:
            self._cmb_rule.addItem(tr(label_key))
        self._cmb_rule.addItem(tr("naming_rule_custom"))
        self._cmb_rule.currentIndexChanged.connect(self._on_rule_changed)
        lay.addRow(self._lbl_rule, self._cmb_rule)

        # Direction radio.
        self._lbl_dir = QtWidgets.QLabel(tr("label_direction"))
        dir_row = QtWidgets.QHBoxLayout()
        self._rb_auto = QtWidgets.QRadioButton(tr("dir_auto"))
        self._rb_fwd = QtWidgets.QRadioButton(tr("dir_forward"))
        self._rb_rev = QtWidgets.QRadioButton(tr("dir_reverse"))
        self._rb_auto.setChecked(True)
        for rb in (self._rb_auto, self._rb_fwd, self._rb_rev):
            rb.toggled.connect(self._recompute_target_preview)
            dir_row.addWidget(rb)
        dir_row.addStretch()
        dir_widget = QtWidgets.QWidget()
        dir_widget.setLayout(dir_row)
        lay.addRow(self._lbl_dir, dir_widget)

        # Custom pattern fields (hidden unless rule == Custom).
        self._lbl_pat = QtWidgets.QLabel(tr("label_custom_pattern"))
        self._txt_pat = QtWidgets.QLineEdit()
        self._txt_pat.textChanged.connect(self._recompute_target_preview)
        lay.addRow(self._lbl_pat, self._txt_pat)

        self._lbl_rep = QtWidgets.QLabel(tr("label_custom_replacement"))
        self._txt_rep = QtWidgets.QLineEdit()
        self._txt_rep.textChanged.connect(self._recompute_target_preview)
        lay.addRow(self._lbl_rep, self._txt_rep)

        # Target preview (read-only, updates live).
        self._lbl_tgt_caption = QtWidgets.QLabel(tr("label_target_preview"))
        self._lbl_tgt_value = QtWidgets.QLabel("")
        self._lbl_tgt_value.setStyleSheet("font-weight: bold;")
        lay.addRow(self._lbl_tgt_caption, self._lbl_tgt_value)

        # Status / warning line.
        self._lbl_status = QtWidgets.QLabel("")
        self._lbl_status.setStyleSheet("color: #c33;")
        lay.addRow(QtWidgets.QLabel(""), self._lbl_status)

        # Buttons.
        btn_row = QtWidgets.QHBoxLayout()
        btn_row.addStretch()
        self._btn_cancel = QtWidgets.QPushButton(tr("cancel"))
        self._btn_mirror = QtWidgets.QPushButton(tr("btn_mirror"))
        self._btn_mirror.setDefault(True)
        self._btn_cancel.clicked.connect(self.reject)
        self._btn_mirror.clicked.connect(self.accept)
        btn_row.addWidget(self._btn_cancel)
        btn_row.addWidget(self._btn_mirror)
        btn_widget = QtWidgets.QWidget()
        btn_widget.setLayout(btn_row)
        lay.addRow(btn_widget)

        # Initial: hide custom rows.
        self._set_custom_visible(False)

    # ------------------------------------------------------------------
    # Live-preview / validation
    # ------------------------------------------------------------------

    def _on_rule_changed(self, idx):
        from RBFtools import core_mirror
        self._set_custom_visible(idx == core_mirror.CUSTOM_RULE_INDEX)
        self._recompute_target_preview()

    def _set_custom_visible(self, visible):
        for w in (self._lbl_pat, self._txt_pat,
                  self._lbl_rep, self._txt_rep):
            w.setVisible(visible)

    def _recompute_target_preview(self, *_):
        """Recompute the auto-resolved target name and update the
        Mirror-button enabled state per addendum §M3.2 naming-rule
        edge contract (no_match disables, both_match warns, unchanged
        warns)."""
        from RBFtools import core_mirror
        rule_idx = self._cmb_rule.currentIndex()
        custom = None
        if rule_idx == core_mirror.CUSTOM_RULE_INDEX:
            custom = (self._txt_pat.text(), self._txt_rep.text())
        if self._rb_fwd.isChecked():
            direction = "forward"
        elif self._rb_rev.isChecked():
            direction = "reverse"
        else:
            direction = "auto"
        new_name, status = core_mirror.apply_naming_rule(
            self._source_node, rule_idx, custom, direction)

        self._lbl_tgt_value.setText(new_name)

        if status == "ok":
            self._lbl_status.setText("")
            self._btn_mirror.setEnabled(True)
        elif status == "both_match":
            self._lbl_status.setText(tr("warn_both_directions_match"))
            self._btn_mirror.setEnabled(True)
        elif status == "unchanged":
            self._lbl_status.setText(tr("warn_name_unchanged"))
            self._btn_mirror.setEnabled(False)
        else:
            self._lbl_status.setText(tr("warn_name_no_match"))
            self._btn_mirror.setEnabled(False)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_config(self):
        """Return the user's Mirror configuration as a dict consumable
        by ``controller.mirror_current_node``."""
        from RBFtools import core_mirror
        rule_idx = self._cmb_rule.currentIndex()
        custom = None
        if rule_idx == core_mirror.CUSTOM_RULE_INDEX:
            custom = (self._txt_pat.text(), self._txt_rep.text())
        if self._rb_fwd.isChecked():
            direction = "forward"
        elif self._rb_rev.isChecked():
            direction = "reverse"
        else:
            direction = "auto"
        return {
            "target_name": self._lbl_tgt_value.text(),
            "mirror_axis": int(self._cmb_axis.currentIndex()),
            "naming_rule_index": int(rule_idx),
            "custom": custom,
            "naming_direction": direction,
        }

    def retranslate(self):
        self.setWindowTitle(tr("title_mirror_node"))
        self._lbl_src_caption.setText(tr("label_source_node"))
        self._lbl_axis.setText(tr("label_mirror_axis"))
        self._lbl_rule.setText(tr("label_naming_rule"))
        self._lbl_dir.setText(tr("label_direction"))
        self._lbl_pat.setText(tr("label_custom_pattern"))
        self._lbl_rep.setText(tr("label_custom_replacement"))
        self._lbl_tgt_caption.setText(tr("label_target_preview"))
        self._rb_auto.setText(tr("dir_auto"))
        self._rb_fwd.setText(tr("dir_forward"))
        self._rb_rev.setText(tr("dir_reverse"))
        self._btn_cancel.setText(tr("cancel"))
        self._btn_mirror.setText(tr("btn_mirror"))
