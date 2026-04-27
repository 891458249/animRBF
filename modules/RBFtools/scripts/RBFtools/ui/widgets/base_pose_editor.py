# -*- coding: utf-8 -*-
"""Commit 3 (M_BASE_POSE): BaseDrivenPose tab content.

Reuses :class:`PoseHeaderWidget` (red driver / blue driven boxes) and
a single :class:`PoseRowWidget` configured with ``is_base_pose=True``.
The configuration:

  * Pose label reads "Base Pose" instead of an indexed format.
  * pose_index is :data:`PoseRowWidget.BASE_POSE_SENTINEL` (-1) so
    main_window can dispatch BasePose edits to
    :func:`core.write_base_pose_values` instead of the regular
    ``shape.poses[]`` write path.
  * Driver-side spinboxes are present (so the Header sits over a
    matching column track) but disabled — BasePose has no driver
    semantic; only the driven baseline is meaningful.
  * The green Radius box and the Update / Delete action buttons are
    hidden — BasePose is a unique baseline, not a kernel center.

The tab does NOT expose Add Pose / Delete Poses buttons — there is
exactly one BasePose per node, by definition.
"""

from __future__ import absolute_import

from RBFtools.ui.compat import QtCore, QtWidgets
from RBFtools.ui.i18n import tr
from RBFtools.ui.widgets.bone_data_widgets import (
    COL_SPACING, COL_MARGIN,
)
from RBFtools.ui.widgets.pose_row_widget import (
    PoseHeaderWidget, PoseRowWidget,
)


class BasePoseEditor(QtWidgets.QWidget):
    """Single-row editor for the per-output BasePose baseline.

    Signal contract (re-emits the embedded PoseRowWidget):

      poseValueChangedV2(int pose_idx, str side, int source_idx,
                         str attr_name, float val)
        ``pose_idx`` is always BASE_POSE_SENTINEL (-1). Driver-side
        edits never fire (clusters disabled); only ``side == "value"``
        is meaningful for the BasePose baseline.

      poseRecallRequested(int pose_idx)
        ``pose_idx == -1`` => apply the BasePose baseline to the
        driven node attrs (main_window translates).
    """

    poseValueChangedV2  = QtCore.Signal(int, str, int, str, float)
    poseRecallRequested = QtCore.Signal(int)

    def __init__(self, parent=None):
        super(BasePoseEditor, self).__init__(parent)
        self._driver_sources = []
        self._driven_sources = []
        self._base_values    = []   # flat list[float], len = n_driven
        self._header_widget  = None
        self._row_widget     = None
        self._build()

    # ------------------------------------------------------------------
    # Build (one-shot scaffold; refilled by set_data())
    # ------------------------------------------------------------------

    def _build(self):
        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(COL_MARGIN, COL_MARGIN,
                                 COL_MARGIN, COL_MARGIN)
        outer.setSpacing(COL_SPACING)

        self._lbl_empty_hint = QtWidgets.QLabel(
            tr("base_pose_empty_hint_fallback"))
        self._lbl_empty_hint.setStyleSheet(
            "color: gray; font-style: italic;")
        self._lbl_empty_hint.setWordWrap(True)
        outer.addWidget(self._lbl_empty_hint)

        # Global QScrollArea — same UX directive as PoseGridEditor:
        # one outer scroll area for both the header and the single
        # baseline row, NEVER per-cluster scrolling.
        self._scroll = QtWidgets.QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(
            QtCore.Qt.ScrollBarAsNeeded)
        self._scroll.setVerticalScrollBarPolicy(
            QtCore.Qt.ScrollBarAsNeeded)
        self._scroll.setFrameShape(QtWidgets.QFrame.NoFrame)

        self._inner = QtWidgets.QWidget()
        self._inner_layout = QtWidgets.QVBoxLayout(self._inner)
        self._inner_layout.setContentsMargins(0, 0, 0, 0)
        self._inner_layout.setSpacing(COL_SPACING)
        self._inner_layout.addStretch(1)
        self._scroll.setWidget(self._inner)
        outer.addWidget(self._scroll, 1)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_data(self, driver_sources, driven_sources, base_values):
        """Rebuild Header + single BasePose row.

        Parameters
        ----------
        driver_sources, driven_sources : list[DriverSource | DrivenSource]
            Same payload PoseGridEditor receives — Header geometry
            stays identical so the column tracks line up.
        base_values : list[float]
            Per-output baseline, length == sum(len(s.attrs) for s in
            driven_sources). Empty list => zeros (legacy nodes).
        """
        self._driver_sources = list(driver_sources or [])
        self._driven_sources = list(driven_sources or [])
        self._base_values    = list(base_values or [])
        self._rebuild()

    def retranslate(self):
        self._lbl_empty_hint.setText(tr("base_pose_empty_hint_fallback"))

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _clear_inner(self):
        while self._inner_layout.count() > 1:
            item = self._inner_layout.takeAt(0)
            w = item.widget() if item is not None else None
            if w is not None:
                w.deleteLater()
        self._header_widget = None
        self._row_widget    = None

    def _rebuild(self):
        self._clear_inner()
        no_sources = (
            not self._driver_sources and not self._driven_sources)
        self._lbl_empty_hint.setVisible(no_sources)
        self._scroll.setVisible(not no_sources)
        if no_sources:
            return

        # Header (same geometry contract as PoseGridEditor's header
        # so the user perceives a consistent column track across tabs).
        self._header_widget = PoseHeaderWidget(
            self._driver_sources, self._driven_sources)
        self._inner_layout.insertWidget(
            self._inner_layout.count() - 1,  # before stretch
            self._header_widget)

        # Single BasePose row. Driver inputs filled with zeros (the
        # disabled clusters render them as 0.000). Driven inputs are
        # filled from base_values (sparse-safe via PoseRowWidget's
        # cluster slicing).
        n_drv = sum(len(s.attrs) for s in self._driver_sources)
        self._row_widget = PoseRowWidget(
            pose_index=PoseRowWidget.BASE_POSE_SENTINEL,
            driver_sources=self._driver_sources,
            driven_sources=self._driven_sources,
            inputs=[0.0] * n_drv,
            values=list(self._base_values),
            is_base_pose=True)
        self._row_widget.poseValueChangedV2.connect(
            self.poseValueChangedV2)
        self._row_widget.poseRecallRequested.connect(
            self.poseRecallRequested)
        self._inner_layout.insertWidget(
            self._inner_layout.count() - 1,
            self._row_widget)
