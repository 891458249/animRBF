# -*- coding: utf-8 -*-
"""LiveEditWidget — per-node Live Edit toggle (Milestone 3.4).

Embedded in the per-node ToolsSection collapsible via
:meth:`RBFToolsWindow.add_tools_panel_widget` (M3.0-spillover §3
second consumer). Owns the Maya ``cmds.scriptJob`` lifecycle for
attribute-change listening on the current node's driver attributes
and threads every event through the pure-function throttle in
:mod:`RBFtools.core_live`.

Hard contracts (addendum §M3.4):

  * driver-only listening — never reads driven info / never
    registers scriptJobs against driven_node.
  * actual ``time.monotonic()`` reads happen ONLY here (the Qt
    layer); :mod:`RBFtools.core_live` accepts ``now_ts`` injected
    by this widget. T_THROTTLE_TIME_INJECTION permanent guard.
  * scriptJob ``parent=WINDOW_OBJECT`` so Maya auto-cleans on
    window close + this widget kills jobs explicitly on toggle off
    (double cleanup).
  * toggle off flushes any pending trailing event before killing
    jobs (G.1 — never drop the user's last drag).

Active row tracking (D.2):

  This widget owns the active-row Qt subscription via the pose
  table's selection model. The MainController is intentionally
  NOT involved — keeps the controller surface minimal. If a
  future sub-task (e.g. M5 monitoring) needs controller-level
  access, the listener can be promoted to MainController as
  ``currentPoseRow`` property + signal without changing any
  code in this widget. See addendum §M3.4 (D) forward-compat.
"""

from __future__ import absolute_import

import time
from functools import partial

import maya.cmds as cmds

from RBFtools.ui.compat import QtWidgets, QtCore
from RBFtools.ui.i18n import tr
from RBFtools.constants import WINDOW_OBJECT
from RBFtools import core_live


_TRAILING_TICK_MS = 110  # slightly longer than throttle to ensure due


class LiveEditWidget(QtWidgets.QWidget):
    """Toggle + status label + scriptJob orchestration."""

    def __init__(self, controller, pose_table_view, parent=None):
        super(LiveEditWidget, self).__init__(parent)
        self._ctrl = controller
        self._table_view = pose_table_view

        # Pure throttle state (lives in core_live).
        self._throttle = core_live.ThrottleState(throttle_ms=100)
        self._state = core_live.LiveEditState.IDLE
        self._jobs = []
        self._active_row = None

        # Trailing-edge poll timer — fires _TRAILING_TICK_MS after
        # a in-window event so the trailing emit lands on time.
        self._trailing_timer = QtCore.QTimer(self)
        self._trailing_timer.setSingleShot(True)
        self._trailing_timer.setInterval(_TRAILING_TICK_MS)
        self._trailing_timer.timeout.connect(self._on_trailing_tick)

        # ----- Build UI -----
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._cb = QtWidgets.QCheckBox(tr("live_edit_toggle_label"))
        self._cb.setToolTip(tr("live_edit_toggle_tip"))
        self._cb.toggled.connect(self._on_toggled)
        layout.addWidget(self._cb)
        self._status = QtWidgets.QLabel(tr("live_edit_status_idle"))
        layout.addWidget(self._status)
        layout.addStretch(1)

        # ----- Row tracking via pose-table selection model -----
        try:
            sm = self._table_view.selectionModel()
            if sm is not None:
                sm.currentChanged.connect(self._on_row_changed)
        except Exception:
            # Headless / mock paths — selection model may be absent.
            pass

        # ----- Node change → re-register jobs against new driver -----
        try:
            self._ctrl.editorLoaded.connect(self._on_editor_loaded)
        except Exception:
            pass

    # =================================================================
    #  Toggle handlers
    # =================================================================

    def _on_toggled(self, checked):
        if checked:
            self._toggle_on()
        else:
            self._toggle_off()

    def _toggle_on(self):
        node = self._ctrl.current_node
        if not node:
            self._fail_to_idle(tr("live_edit_warn_no_node"))
            return
        try:
            from RBFtools import core as _core
            # M_B24b2: multi-source listen. List[(node, attr)] preserves
            # source order (C.2). Legacy single-driver auto-migrates so
            # the result is byte-equivalent to the previous (drv_node,
            # drv_attrs) pair, expanded into pairs.
            sources = _core.read_driver_info_multi(node)
            pairs = [(src.node, attr) for src in sources for attr in src.attrs]
            drv_attrs = [a for _n, a in pairs]
        except Exception as exc:
            self._fail_to_idle(str(exc))
            return
        ok, reason = core_live.can_toggle_on(self._state, drv_attrs)
        if not ok:
            self._fail_to_idle(tr("live_edit_warn_no_attrs"))
            return
        # Register a scriptJob per driver attr (C.2 — per-attr
        # precision), parented to the window for auto-cleanup.
        self._jobs = []
        for drv_node, attr in pairs:
            try:
                jid = cmds.scriptJob(
                    attributeChange=[
                        "{}.{}".format(drv_node, attr),
                        partial(self._on_driver_attr_changed, attr),
                    ],
                    parent=WINDOW_OBJECT,
                )
                self._jobs.append(jid)
            except Exception as exc:
                cmds.warning(
                    "live_edit: scriptJob register failed for "
                    "{}.{}: {}".format(drv_node, attr, exc))
        self._state = core_live.LiveEditState.LISTENING
        self._status.setText(
            tr("live_edit_status_listening").format(n=len(self._jobs)))

    def _toggle_off(self):
        if not core_live.can_toggle_off(self._state):
            return
        # G.1 — flush a pending trailing event before tearing down
        # so the user's last drag does not get dropped.
        if core_live.flush_pending(self._throttle, time.monotonic()):
            self._do_emit()
        self._kill_jobs()
        self._throttle.reset()
        self._state = core_live.LiveEditState.IDLE
        self._status.setText(tr("live_edit_status_idle"))

    def _kill_jobs(self):
        for jid in self._jobs:
            try:
                cmds.scriptJob(kill=jid, force=True)
            except Exception:
                # parent=WINDOW_OBJECT may have already cleaned up
                # (window close path) — absorb.
                pass
        self._jobs = []

    def _fail_to_idle(self, msg):
        cmds.warning("live_edit: " + msg)
        # Reset checkbox without re-entering toggle handler
        self._cb.blockSignals(True)
        self._cb.setChecked(False)
        self._cb.blockSignals(False)
        self._state = core_live.LiveEditState.IDLE
        self._status.setText(tr("live_edit_status_idle"))

    # =================================================================
    #  Event handlers
    # =================================================================

    def _on_driver_attr_changed(self, _attr_name):
        """Maya scriptJob callback. Threads now_ts through the
        pure-function throttle and decides whether to leading-emit
        or schedule a trailing tick."""
        now = time.monotonic()
        emit_now, schedule_trailing = core_live.should_emit_now(
            self._throttle, now)
        if emit_now:
            self._do_emit()
        elif schedule_trailing:
            self._trailing_timer.start()

    def _on_trailing_tick(self):
        now = time.monotonic()
        if core_live.trailing_due(self._throttle, now):
            self._do_emit()
        # If not due (e.g. another leading emit happened in the
        # meantime), simply drop the tick — pending_event_ts was
        # cleared by mark_emitted.

    def _do_emit(self):
        """Single point that actually calls into the controller."""
        if self._active_row is None or self._active_row < 0:
            return
        self._ctrl.live_edit_apply_inputs(self._active_row)
        core_live.mark_emitted(self._throttle, time.monotonic())

    # =================================================================
    #  External event hooks
    # =================================================================

    def _on_row_changed(self, current, _previous):
        """Pose-table selection changed → update active row index."""
        try:
            self._active_row = current.row() if current.isValid() else None
        except Exception:
            self._active_row = None

    def _on_editor_loaded(self):
        """Controller editorLoaded signal: node or attrs may have
        changed. Re-plan scriptJob registration accordingly."""
        try:
            from RBFtools import core as _core
            node = self._ctrl.current_node
            drv_attrs = []
            if node:
                # M_B24b2: multi-source aggregate (legacy auto-migrates).
                _sources = _core.read_driver_info_multi(node)
                drv_attrs = [a for src in _sources for a in src.attrs]
        except Exception:
            drv_attrs = []
        plan = core_live.planned_transition_on_node_change(
            self._state, drv_attrs)
        if plan == ("noop",):
            return
        # Both teardown_only and teardown+register start with kill.
        if core_live.flush_pending(self._throttle, time.monotonic()):
            self._do_emit()
        self._kill_jobs()
        self._throttle.reset()
        self._state = core_live.LiveEditState.IDLE
        self._status.setText(tr("live_edit_status_idle"))
        if plan == ("teardown_only",):
            # New node has no driver attrs → drop checkbox.
            self._cb.blockSignals(True)
            self._cb.setChecked(False)
            self._cb.blockSignals(False)
            return
        # Re-register against the new node's drivers.
        self._cb.blockSignals(True)
        self._cb.setChecked(True)
        self._cb.blockSignals(False)
        self._toggle_on()
