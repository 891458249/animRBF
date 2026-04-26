# -*- coding: utf-8 -*-
"""
Pose editor — composes two :class:`AttributeList` widgets (driver / driven)
and a :class:`PoseTable`.

This is the bottom half of the main window when in RBF mode.
Signals only — no ``maya.cmds``.
"""

from __future__ import absolute_import

from RBFtools.ui.compat import QtWidgets, QtCore
from RBFtools.ui.i18n import tr
from RBFtools.ui.widgets.collapsible import CollapsibleFrame
from RBFtools.ui.widgets.attribute_list import AttributeList
from RBFtools.ui.widgets.pose_table import PoseTable
from RBFtools.ui.widgets.output_scale_editor import OutputScaleEditor


class PoseEditor(CollapsibleFrame):
    """Full RBF Pose Editor section."""

    # Forwarded from children
    selectNodeRequested = QtCore.Signal(str)          # role
    filtersChanged = QtCore.Signal(str, dict)         # (role, filters)
    addPoseRequested = QtCore.Signal()
    applyRequested = QtCore.Signal()
    connectRequested = QtCore.Signal()
    reloadRequested = QtCore.Signal()
    recallPose = QtCore.Signal(int)
    updatePose = QtCore.Signal(int)
    deletePose = QtCore.Signal(int)
    autoFillChanged = QtCore.Signal(bool)
    outputIsScaleChanged = QtCore.Signal(list)        # M2.4a

    def __init__(self, parent=None):
        super(PoseEditor, self).__init__(
            title=tr("rbf_pose_editor"), parent=parent)
        self._build()

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def _build(self):
        lay = self.content_layout()

        # M_UIRECONCILE (decision C.1 + Hardening 2): multi-source
        # banner. Hidden by default - main_window shows it only when
        # the active node carries > 1 driverSource entries (single-
        # source nodes keep the legacy AttributeList workflow
        # visually unchanged per red line 14 backcompat parity).
        self._lbl_multi_source_banner = QtWidgets.QLabel("")
        self._lbl_multi_source_banner.setWordWrap(True)
        self._lbl_multi_source_banner.setStyleSheet(
            "QLabel {"
            "  background: #3a3320;"
            "  color: #f0d070;"
            "  border: 1px solid #6a5a30;"
            "  border-radius: 4px;"
            "  padding: 6px 8px;"
            "  font-size: 11px;"
            "}"
        )
        self._lbl_multi_source_banner.setVisible(False)
        lay.addWidget(self._lbl_multi_source_banner)

        # Auto-fill checkbox
        self._cb_auto = QtWidgets.QCheckBox(tr("auto_fill_bs"))
        self._cb_auto.toggled.connect(self.autoFillChanged)
        lay.addWidget(self._cb_auto)

        lay.addWidget(self._separator())

        # Driver / Driven split
        split = QtWidgets.QHBoxLayout()

        self._driver_list = AttributeList("driver")
        self._driven_list = AttributeList("driven")

        split.addWidget(self._driver_list, 1)

        divider = QtWidgets.QFrame()
        divider.setFrameShape(QtWidgets.QFrame.VLine)
        divider.setFrameShadow(QtWidgets.QFrame.Sunken)
        split.addWidget(divider)

        split.addWidget(self._driven_list, 1)
        lay.addLayout(split)

        # M2.4a: per-driven-attribute outputIsScale checkbox list.
        # Sits below the driver/driven split so it shadows the driven
        # selection visually. Hidden until set_attributes is called by
        # the parent with the resolved driven attr names.
        self._output_scale_editor = OutputScaleEditor()
        self._output_scale_editor.isScaleChanged.connect(
            self.outputIsScaleChanged)
        lay.addWidget(self._output_scale_editor)

        # Wire child signals
        self._driver_list.selectNodeRequested.connect(
            lambda: self.selectNodeRequested.emit("driver"))
        self._driven_list.selectNodeRequested.connect(
            lambda: self.selectNodeRequested.emit("driven"))
        self._driver_list.filtersChanged.connect(self.filtersChanged)
        self._driven_list.filtersChanged.connect(self.filtersChanged)

        lay.addWidget(self._separator())

        # Pose table
        self._pose_table = PoseTable()
        lay.addWidget(self._pose_table, 1)

        # Wire pose table signals
        self._pose_table.recallPose.connect(self.recallPose)
        self._pose_table.updatePose.connect(self.updatePose)
        self._pose_table.deletePose.connect(self.deletePose)

        lay.addWidget(self._separator())

        # Bottom buttons
        btn_row = QtWidgets.QHBoxLayout()
        self._btn_add = QtWidgets.QPushButton(tr("add_pose"))
        self._btn_apply = QtWidgets.QPushButton(tr("apply"))
        self._btn_apply.setToolTip(tr("pose_editor_apply_tip"))
        self._btn_connect = QtWidgets.QPushButton(tr("connect"))
        self._btn_connect.setToolTip(tr("pose_editor_connect_tip"))
        self._btn_reload = QtWidgets.QPushButton(tr("reload"))

        for btn in (self._btn_add, self._btn_apply,
                    self._btn_connect, self._btn_reload):
            btn_row.addWidget(btn)

        self._btn_add.clicked.connect(self.addPoseRequested)
        self._btn_apply.clicked.connect(self.applyRequested)
        self._btn_connect.clicked.connect(self.connectRequested)
        self._btn_reload.clicked.connect(self.reloadRequested)
        lay.addLayout(btn_row)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def driver_list(self):
        return self._driver_list

    @property
    def driven_list(self):
        return self._driven_list

    @property
    def pose_table(self):
        return self._pose_table

    @property
    def output_scale_editor(self):
        """Public accessor used by main_window/controller to populate
        the per-driven-attribute scale flag rows after the driven attrs
        are resolved."""
        return self._output_scale_editor

    def show_multi_source_banner(self, text):
        """M_UIRECONCILE: surface the multi-source notice. Called by
        main_window when the active node carries > 1 driverSource
        entries so the TD knows the AttributeList below shows only
        the first source."""
        self._lbl_multi_source_banner.setText(text or "")
        self._lbl_multi_source_banner.setVisible(bool(text))

    def hide_multi_source_banner(self):
        """M_UIRECONCILE: hide the banner. Called for single-source
        nodes (the default case under red line 14 backcompat
        parity)."""
        self._lbl_multi_source_banner.setVisible(False)

    def set_auto_fill(self, checked):
        blocked = self._cb_auto.blockSignals(True)
        self._cb_auto.setChecked(checked)
        self._cb_auto.blockSignals(blocked)

    def auto_fill(self):
        return self._cb_auto.isChecked()

    def retranslate(self):
        self.set_title(tr("rbf_pose_editor"))
        self._cb_auto.setText(tr("auto_fill_bs"))
        self._driver_list.retranslate()
        self._driven_list.retranslate()
        self._pose_table.retranslate()
        self._output_scale_editor.retranslate()
        self._btn_add.setText(tr("add_pose"))
        self._btn_apply.setText(tr("apply"))
        self._btn_connect.setText(tr("connect"))
        self._btn_reload.setText(tr("reload"))

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _separator():
        line = QtWidgets.QFrame()
        line.setFrameShape(QtWidgets.QFrame.HLine)
        line.setFrameShadow(QtWidgets.QFrame.Sunken)
        return line
