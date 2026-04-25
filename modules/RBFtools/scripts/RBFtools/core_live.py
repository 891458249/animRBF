# -*- coding: utf-8 -*-
"""Live Edit Mode — pure throttle + scriptJob lifecycle (Milestone 3.4).

============================================================
Hard contracts (addendum §M3.4)
============================================================

  driver-only listening:
    Live Edit listens on driver_node attributes ONLY. Listening
    on driven_node would create a feedback loop with the RBF
    compute that writes those attributes (the compute would
    re-trigger the throttle, which would re-write inputs, which
    would re-trigger compute …). T_LIVE_NO_DRIVEN_LISTEN
    PERMANENT GUARD source-scans this module for any leakage of
    driven-side identifiers. NEVER add driven_node /
    driven_attrs / read_driven_info references to this module.

  time injection:
    Throttle pure functions accept ``now_ts`` as a parameter and
    NEVER call ``time.time()`` / ``time.monotonic()`` /
    ``datetime.now()`` directly. Caller (LiveEditWidget,
    operating in the Qt layer) is the only place a real-time
    source is read. Keeps every throttle decision deterministic
    under unit test. T_THROTTLE_TIME_INJECTION PERMANENT GUARD
    source-scans this module.

  scriptJob lifecycle:
    Caller (LiveEditWidget) is responsible for the actual
    ``cmds.scriptJob`` calls. This module owns the *decisions*
    (when to register / kill / flush) but NOT the Maya API
    invocations. That separation lets us test the lifecycle
    state machine without a Maya runtime.

  zero core.py changes:
    M3.4 is the 4th consecutive M3.x sub-task with no core.py
    edits. This module imports nothing from core except for
    annotation purposes — and even those imports are deferred
    inside callers, not at module load.

============================================================
M1.5 spillover (addendum §M3.4 末尾 scope lock)
============================================================
Real Maya scriptJob attributeChange triggering, parent=
auto-cleanup behaviour under window close, and end-to-end
viewport-drag throttle behaviour land in M1.5 mayapy
integration tests. The pure-function API in this module is
the M1.5 forward-compat interface — it is locked.
"""

from __future__ import absolute_import


# =====================================================================
#  Throttle state + pure decision functions
# =====================================================================


class ThrottleState(object):
    """Mutable state for a hybrid leading+trailing throttle.

    Caller threads ``now_ts`` (a monotonic seconds float) through
    every transition function — never reads time directly. The
    permanent guard T_THROTTLE_TIME_INJECTION enforces this.

    Attributes
    ----------
    last_emit_ts : float
        Wall-clock-equivalent timestamp of the most recent emit.
        ``0.0`` when no emit has fired yet.
    pending_event_ts : float or None
        Most recent event timestamp inside a throttle window.
        Set by :func:`should_emit_now` when an event arrives but
        the window has not elapsed; consumed by
        :func:`trailing_due` / :func:`flush_pending`.
    throttle_sec : float
        Window length in seconds (default 0.1 ≡ 100 ms).
    """

    __slots__ = ("last_emit_ts", "pending_event_ts", "throttle_sec")

    def __init__(self, throttle_ms=100):
        self.last_emit_ts = 0.0
        self.pending_event_ts = None
        self.throttle_sec = throttle_ms / 1000.0

    def reset(self):
        self.last_emit_ts = 0.0
        self.pending_event_ts = None


def should_emit_now(state, now_ts):
    """Decide whether an arriving event should emit immediately.

    Returns
    -------
    (emit_now : bool, schedule_trailing : bool)
        ``emit_now`` True means caller should fire its update
        callback right now (leading edge).
        ``schedule_trailing`` True means caller should arm a
        single-shot timer that will call :func:`trailing_due`
        ``state.throttle_sec`` from now.

    Side effects
    ------------
    - On leading emit: ``state.last_emit_ts`` advances to
      ``now_ts`` and ``pending_event_ts`` is cleared.
    - On in-window event: ``pending_event_ts`` is set to
      ``now_ts``; ``last_emit_ts`` is unchanged.
    """
    if state.last_emit_ts == 0.0 or \
       (now_ts - state.last_emit_ts) >= state.throttle_sec:
        # Leading edge — fire immediately and start a fresh window.
        state.last_emit_ts = now_ts
        state.pending_event_ts = None
        return (True, False)
    # Inside the throttle window — record event for trailing emit.
    state.pending_event_ts = now_ts
    return (False, True)


def trailing_due(state, now_ts):
    """Caller's deferred timer asks: is the trailing emit due?

    Returns True iff there is a pending event AND
    ``state.throttle_sec`` has elapsed since the last emit. The
    caller then performs the update and calls :func:`mark_emitted`
    to advance the state.
    """
    if state.pending_event_ts is None:
        return False
    return (now_ts - state.last_emit_ts) >= state.throttle_sec


def mark_emitted(state, now_ts):
    """Advance the state after the caller has actually fired its
    update callback (whether leading or trailing). Pure function
    on state — no side effects beyond mutating the state slots."""
    state.last_emit_ts = now_ts
    state.pending_event_ts = None


def flush_pending(state, now_ts):
    """Caller invokes this on toggle-off. Returns True iff there
    is a pending event that should be flushed RIGHT NOW (caller
    fires its update callback regardless of throttle window) so
    the user's last drag does not get dropped.

    After the caller fires, it is the caller's responsibility to
    invoke :func:`mark_emitted` (or simply :meth:`ThrottleState.reset`
    since toggle-off implies state teardown)."""
    return state.pending_event_ts is not None


# =====================================================================
#  Live Edit lifecycle state machine (pure — no Maya cmds)
# =====================================================================


class LiveEditState(object):
    """Permitted lifecycle states. Single-letter constants keep
    diagnostic logs compact."""
    IDLE = "I"
    LISTENING = "L"


def can_toggle_on(current_state, driver_attrs):
    """Pure decision: may we transition IDLE -> LISTENING?

    Returns
    -------
    (ok : bool, reason : str)
        ``reason`` is empty on success, a one-line warning string
        otherwise. Caller (Widget layer) emits the warning to the
        user and resets its checkbox without registering jobs.
    """
    if current_state != LiveEditState.IDLE:
        return (False, "live edit already on")
    if not driver_attrs:
        # E.1 — fail fast when there is nothing to listen on
        # (addendum §M3.4 Q4).
        return (False, "no driver attrs to listen on")
    return (True, "")


def can_toggle_off(current_state):
    """Pure decision: may we transition LISTENING -> IDLE?

    Always True from LISTENING, False from IDLE (toggle-off on an
    already-idle controller is a no-op the caller can short-circuit).
    """
    return current_state == LiveEditState.LISTENING


def planned_transition_on_node_change(current_state, new_driver_attrs):
    """Caller invokes this when the active RBFtools node changes
    while Live Edit is on. Returns the planned action sequence:

      ("teardown_only",)         — old jobs killed; new node has no
                                   driver attrs (E.1) so we settle
                                   in IDLE.
      ("teardown", "register")   — full cycle: kill old jobs, then
                                   register against the new node.
      ("noop",)                  — Live Edit is off; nothing to do.

    The caller does the actual ``cmds.scriptJob`` calls; this
    function only sequences them.
    """
    if current_state != LiveEditState.LISTENING:
        return ("noop",)
    if not new_driver_attrs:
        return ("teardown_only",)
    return ("teardown", "register")
