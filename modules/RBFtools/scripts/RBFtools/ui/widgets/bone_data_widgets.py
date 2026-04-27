# -*- coding: utf-8 -*-
"""Commit 2 (M_UIRECONCILE2): per-bone data widgets.

Two paired widgets implement the *Header Separation* layout the user
specified for the Pose tab refactor:

  * :class:`BoneDataGroupBox` — used ONCE in the header strip per bone
    source. Renders the colored frame (red for driver, blue for driven),
    bone name, and per-attr labels. Width is locked so the row data
    aligns column-by-column.

  * :class:`BoneRowDataWidget` — used per pose row per bone source. A
    bare horizontal cluster of QDoubleSpinBox-es matching the column
    widths from the header. No frame, no labels — visual de-bloating
    per the user's "斑马线一样冗余" critique.

The two share :data:`COL_WIDTH` so column boundaries align without
manual fiddling. PoseRowWidget composes BoneRowDataWidget instances
side-by-side; PoseHeaderWidget composes BoneDataGroupBox instances.
"""

from __future__ import absolute_import

from RBFtools.ui.compat import QtCore, QtWidgets


# Locked column geometry so Header labels sit directly above Row spins.
COL_WIDTH       = 78
COL_SPACING     = 2
COL_MARGIN      = 4

DRIVER_COLOR    = "#b03a48"   # red
DRIVEN_COLOR    = "#3a7a8c"   # blue
RADIUS_COLOR    = "#4a8c5a"   # green


def _pad_to_pose_index(values, n):
    """Pad ``values`` to length n with 0.0; truncate if longer."""
    out = list(values or [])
    if len(out) < n:
        out.extend([0.0] * (n - len(out)))
    return out[:n]


# ----------------------------------------------------------------------
# Header-side: colored GroupBox with bone name + attr labels
# ----------------------------------------------------------------------


class BoneDataGroupBox(QtWidgets.QGroupBox):
    """Header strip for one bone source.

    Layout:
        QVBoxLayout
          - QLabel  bone name        (1 row)
          - QHBoxLayout attr labels  (1 row, n_attrs columns)

    The outer frame uses a colored stylesheet matching ``side``
    (``"driver"`` => red, ``"driven"`` => blue).
    """

    def __init__(self, bone_name, attrs, side, parent=None):
        super(BoneDataGroupBox, self).__init__(parent)
        self._bone_name = str(bone_name or "<unset>")
        self._attrs = list(attrs or [])
        self._side = side

        color = DRIVER_COLOR if side == "driver" else DRIVEN_COLOR
        self.setStyleSheet(
            "QGroupBox {{"
            "  border: 1px solid {color};"
            "  border-radius: 3px;"
            "  margin-top: 2px;"
            "  padding: 2px;"
            "}}"
            "QLabel {{"
            "  color: {color};"
            "}}".format(color=color))

        v = QtWidgets.QVBoxLayout(self)
        v.setContentsMargins(COL_MARGIN, COL_MARGIN,
                             COL_MARGIN, COL_MARGIN)
        v.setSpacing(COL_SPACING)

        self._lbl_bone = QtWidgets.QLabel(self._bone_name)
        self._lbl_bone.setAlignment(QtCore.Qt.AlignLeft)
        self._lbl_bone.setStyleSheet("font-weight: bold;")
        v.addWidget(self._lbl_bone)

        attr_row = QtWidgets.QHBoxLayout()
        attr_row.setContentsMargins(0, 0, 0, 0)
        attr_row.setSpacing(COL_SPACING)
        self._attr_labels = []
        for a in self._attrs:
            lbl = QtWidgets.QLabel(a)
            lbl.setAlignment(QtCore.Qt.AlignCenter)
            lbl.setFixedWidth(COL_WIDTH)
            self._attr_labels.append(lbl)
            attr_row.addWidget(lbl)
        v.addLayout(attr_row)

        # Lock outer width to attrs * COL_WIDTH so row cluster aligns.
        n = max(1, len(self._attrs))
        outer_w = n * COL_WIDTH + (n - 1) * COL_SPACING + 2 * COL_MARGIN + 4
        self.setFixedWidth(outer_w)


# ----------------------------------------------------------------------
# Row-side: bare horizontal cluster of spinboxes for one bone source
# ----------------------------------------------------------------------


class BoneRowDataWidget(QtWidgets.QWidget):
    """One pose row's spinbox cluster for a single bone source.

    Width-locked to ``len(attrs) * COL_WIDTH`` so the cluster sits
    directly under the matching :class:`BoneDataGroupBox` header.

    Signals
    -------
    valueChanged(int attr_idx, float new_value)
        Emitted when any of the spinboxes is edited. ``attr_idx`` is
        the position WITHIN this source's attr list (0..len(attrs)-1)
        — Caller maps it to a global flat index.
    """

    valueChanged = QtCore.Signal(int, float)

    def __init__(self, attrs, initial_values=None, parent=None):
        super(BoneRowDataWidget, self).__init__(parent)
        self._attrs = list(attrs or [])
        vals = _pad_to_pose_index(initial_values, len(self._attrs))

        h = QtWidgets.QHBoxLayout(self)
        h.setContentsMargins(COL_MARGIN, 0, COL_MARGIN, 0)
        h.setSpacing(COL_SPACING)
        self._spins = []
        for i, _attr in enumerate(self._attrs):
            sb = QtWidgets.QDoubleSpinBox()
            sb.setRange(-1e9, 1e9)
            sb.setDecimals(3)
            sb.setFixedWidth(COL_WIDTH)
            try:
                sb.setValue(float(vals[i]))
            except (TypeError, ValueError):
                sb.setValue(0.0)
            sb.valueChanged.connect(
                lambda v, _i=i: self.valueChanged.emit(
                    _i, float(v)))
            self._spins.append(sb)
            h.addWidget(sb)

        n = max(1, len(self._attrs))
        outer_w = n * COL_WIDTH + (n - 1) * COL_SPACING + 2 * COL_MARGIN
        self.setFixedWidth(outer_w)

    def values(self):
        return [s.value() for s in self._spins]
