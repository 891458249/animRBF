"""M3.4 — Live Edit Mode tests (algo only).

Test layout
-----------
T1  ThrottleState defaults + reset.
T2  should_emit_now leading edge — first event fires immediately.
T3  should_emit_now in-window event — defers to trailing.
T4  should_emit_now after-window event — leading again.
T5  trailing_due / mark_emitted state advancement.
T6  flush_pending — true iff a trailing event is queued.
T7  can_toggle_on — IDLE + non-empty attrs OK; empty attrs E.1
    rejected; LISTENING rejected.
T8  can_toggle_off — only from LISTENING.
T9  planned_transition_on_node_change — three branches:
      noop / teardown_only / teardown+register.
T10 controller.live_edit_apply_inputs guards (no node / no row /
    no driver) before calling update_pose.
T11 ToolsSection wiring — main_window registers
    "live_edit_toggle" via spillover §3 (source-text).
T12 i18n parity — all 6 M3.4 keys present in EN + CN.

T_LIVE_NO_DRIVEN_LISTEN (PERMANENT) — core_live.py executable body
    must NOT mention any driven-side identifier
    (read_driven_info / driven_node / driven_attrs). Source-scan
    after stripping docstrings + comments — listening on driven
    would create a feedback loop with the RBF compute.

T_THROTTLE_TIME_INJECTION (PERMANENT) — core_live.py executable
    body must NOT call time.time() / time.monotonic() /
    datetime.now() / datetime.utcnow(). Throttle pure functions
    accept now_ts as parameter. Caller (Qt widget) is the only
    real-time source.
"""

from __future__ import absolute_import

import conftest  # noqa: F401

import inspect
import re
import unittest
from unittest import mock

import maya.cmds as cmds


def _strip_docstrings_and_comments(src):
    src = re.sub(r'"""[\s\S]*?"""', "", src)
    # Strip line comments, but only those that are pure-comment
    # lines (preserve inline string literals untouched).
    out = []
    for line in src.splitlines():
        stripped = line.lstrip()
        if stripped.startswith("#"):
            continue
        out.append(line)
    return "\n".join(out)


# ----------------------------------------------------------------------
# T1 — ThrottleState defaults
# ----------------------------------------------------------------------


class T1_ThrottleStateDefaults(unittest.TestCase):

    def test_initial_state(self):
        from RBFtools.core_live import ThrottleState
        s = ThrottleState(throttle_ms=100)
        self.assertEqual(s.last_emit_ts, 0.0)
        self.assertIsNone(s.pending_event_ts)
        self.assertAlmostEqual(s.throttle_sec, 0.1)

    def test_reset(self):
        from RBFtools.core_live import ThrottleState
        s = ThrottleState(throttle_ms=200)
        s.last_emit_ts = 5.0
        s.pending_event_ts = 5.05
        s.reset()
        self.assertEqual(s.last_emit_ts, 0.0)
        self.assertIsNone(s.pending_event_ts)
        # throttle_sec is preserved.
        self.assertAlmostEqual(s.throttle_sec, 0.2)


# ----------------------------------------------------------------------
# T2-T4 — should_emit_now / window logic
# ----------------------------------------------------------------------


class T2_LeadingEdge(unittest.TestCase):

    def test_first_event_fires_immediately(self):
        from RBFtools.core_live import ThrottleState, should_emit_now
        s = ThrottleState(100)
        emit, sched = should_emit_now(s, 1000.0)
        self.assertTrue(emit)
        self.assertFalse(sched)
        self.assertAlmostEqual(s.last_emit_ts, 1000.0)
        self.assertIsNone(s.pending_event_ts)


class T3_InWindowEvent(unittest.TestCase):

    def test_event_inside_window_defers(self):
        from RBFtools.core_live import ThrottleState, should_emit_now
        s = ThrottleState(100)
        # Leading at t=1000
        should_emit_now(s, 1000.0)
        # In-window event at t=1000.05 (50 ms later, < 100 ms)
        emit, sched = should_emit_now(s, 1000.05)
        self.assertFalse(emit)
        self.assertTrue(sched)
        self.assertAlmostEqual(s.pending_event_ts, 1000.05)
        self.assertAlmostEqual(s.last_emit_ts, 1000.0)


class T4_AfterWindowEvent(unittest.TestCase):

    def test_event_after_window_leads_again(self):
        from RBFtools.core_live import ThrottleState, should_emit_now
        s = ThrottleState(100)
        should_emit_now(s, 1000.0)
        # Event at t=1000.5 (500 ms later, well past window)
        emit, sched = should_emit_now(s, 1000.5)
        self.assertTrue(emit)
        self.assertFalse(sched)
        self.assertAlmostEqual(s.last_emit_ts, 1000.5)


# ----------------------------------------------------------------------
# T5 — trailing_due / mark_emitted
# ----------------------------------------------------------------------


class T5_TrailingDueAndMark(unittest.TestCase):

    def test_no_pending_means_not_due(self):
        from RBFtools.core_live import ThrottleState, trailing_due
        s = ThrottleState(100)
        s.last_emit_ts = 1000.0
        s.pending_event_ts = None
        self.assertFalse(trailing_due(s, 9999.0))

    def test_pending_within_window_not_due(self):
        from RBFtools.core_live import ThrottleState, trailing_due
        s = ThrottleState(100)
        s.last_emit_ts = 1000.0
        s.pending_event_ts = 1000.05
        self.assertFalse(trailing_due(s, 1000.05))

    def test_pending_after_window_due(self):
        from RBFtools.core_live import ThrottleState, trailing_due
        s = ThrottleState(100)
        s.last_emit_ts = 1000.0
        s.pending_event_ts = 1000.05
        self.assertTrue(trailing_due(s, 1000.15))

    def test_mark_emitted_clears_pending(self):
        from RBFtools.core_live import (
            ThrottleState, mark_emitted, trailing_due,
        )
        s = ThrottleState(100)
        s.last_emit_ts = 1000.0
        s.pending_event_ts = 1000.05
        mark_emitted(s, 1000.15)
        self.assertAlmostEqual(s.last_emit_ts, 1000.15)
        self.assertIsNone(s.pending_event_ts)
        self.assertFalse(trailing_due(s, 1000.30))


# ----------------------------------------------------------------------
# T6 — flush_pending
# ----------------------------------------------------------------------


class T6_FlushPending(unittest.TestCase):

    def test_no_pending_returns_false(self):
        from RBFtools.core_live import ThrottleState, flush_pending
        s = ThrottleState(100)
        self.assertFalse(flush_pending(s, 9999.0))

    def test_with_pending_returns_true(self):
        from RBFtools.core_live import ThrottleState, flush_pending
        s = ThrottleState(100)
        s.last_emit_ts = 1000.0
        s.pending_event_ts = 1000.05
        self.assertTrue(flush_pending(s, 1000.05))


# ----------------------------------------------------------------------
# T7 — can_toggle_on
# ----------------------------------------------------------------------


class T7_CanToggleOn(unittest.TestCase):

    def test_idle_with_attrs_ok(self):
        from RBFtools.core_live import can_toggle_on, LiveEditState
        ok, reason = can_toggle_on(LiveEditState.IDLE, ["rotateX"])
        self.assertTrue(ok)
        self.assertEqual(reason, "")

    def test_idle_empty_attrs_rejected_E1(self):
        from RBFtools.core_live import can_toggle_on, LiveEditState
        ok, reason = can_toggle_on(LiveEditState.IDLE, [])
        self.assertFalse(ok)
        self.assertIn("no driver attrs", reason)

    def test_listening_state_rejected(self):
        from RBFtools.core_live import can_toggle_on, LiveEditState
        ok, reason = can_toggle_on(LiveEditState.LISTENING, ["rotateX"])
        self.assertFalse(ok)
        self.assertIn("already on", reason)


# ----------------------------------------------------------------------
# T8 — can_toggle_off
# ----------------------------------------------------------------------


class T8_CanToggleOff(unittest.TestCase):

    def test_listening_can_toggle_off(self):
        from RBFtools.core_live import can_toggle_off, LiveEditState
        self.assertTrue(can_toggle_off(LiveEditState.LISTENING))

    def test_idle_cannot_toggle_off(self):
        from RBFtools.core_live import can_toggle_off, LiveEditState
        self.assertFalse(can_toggle_off(LiveEditState.IDLE))


# ----------------------------------------------------------------------
# T9 — planned_transition_on_node_change
# ----------------------------------------------------------------------


class T9_PlannedTransition(unittest.TestCase):

    def test_idle_is_noop(self):
        from RBFtools.core_live import (
            planned_transition_on_node_change as plan, LiveEditState,
        )
        self.assertEqual(plan(LiveEditState.IDLE, ["rotateX"]),
                         ("noop",))
        self.assertEqual(plan(LiveEditState.IDLE, []), ("noop",))

    def test_listening_empty_attrs_teardown_only(self):
        from RBFtools.core_live import (
            planned_transition_on_node_change as plan, LiveEditState,
        )
        self.assertEqual(plan(LiveEditState.LISTENING, []),
                         ("teardown_only",))

    def test_listening_with_attrs_full_cycle(self):
        from RBFtools.core_live import (
            planned_transition_on_node_change as plan, LiveEditState,
        )
        self.assertEqual(plan(LiveEditState.LISTENING, ["rotateX"]),
                         ("teardown", "register"))


# ----------------------------------------------------------------------
# T10 — controller.live_edit_apply_inputs guards
# ----------------------------------------------------------------------


class T10_ControllerGuards(unittest.TestCase):

    def test_method_callable(self):
        from RBFtools.controller import MainController
        self.assertTrue(callable(getattr(
            MainController, "live_edit_apply_inputs", None)))

    def test_no_current_node_short_circuits(self):
        # Source-text guard: the method must return early when
        # _current_node is empty before calling update_pose.
        import pathlib
        path = pathlib.Path(__file__).resolve().parent.parent
        text = (path / "scripts" / "RBFtools"
                / "controller.py").read_text(encoding="utf-8")
        idx = text.find("def live_edit_apply_inputs(self, row):")
        self.assertGreater(idx, 0)
        body = text[idx:idx + 1500]
        self.assertIn("if not self._current_node", body)
        self.assertIn("self.update_pose(", body)


# ----------------------------------------------------------------------
# T11 — ToolsSection wiring (spillover §3 second consumer)
# ----------------------------------------------------------------------


class T11_ToolsSectionWiring(unittest.TestCase):

    def test_live_edit_toggle_registered(self):
        import pathlib
        path = pathlib.Path(__file__).resolve().parent.parent
        text = (path / "scripts" / "RBFtools" / "ui"
                / "main_window.py").read_text(encoding="utf-8")
        self.assertIn('add_tools_panel_widget(\n            '
                      '"live_edit_toggle"', text)


# ----------------------------------------------------------------------
# T12 — i18n parity
# ----------------------------------------------------------------------


class T12_I18nParity(unittest.TestCase):

    REQUIRED = (
        "live_edit_toggle_label",
        "live_edit_status_idle",
        "live_edit_status_listening",
        "live_edit_warn_no_node",
        "live_edit_warn_no_attrs",
        "live_edit_warn_failed",
    )

    def test_keys_present_in_both_languages(self):
        from RBFtools.ui.i18n import _EN, _ZH
        for k in self.REQUIRED:
            self.assertIn(k, _EN, "missing EN: " + k)
            self.assertIn(k, _ZH, "missing CN: " + k)


# ----------------------------------------------------------------------
# T_LIVE_NO_DRIVEN_LISTEN — PERMANENT GUARD
# ----------------------------------------------------------------------


class T_LiveNoDrivenListen(unittest.TestCase):
    """PERMANENT GUARD — DO NOT REMOVE.

    Live Edit must NEVER listen on driven_node attributes. Source-
    scan core_live.py executable body (docstrings + comments
    stripped) for any leakage of driven-side identifiers. Doing so
    would create a feedback loop with the RBF compute that writes
    those attributes — see addendum §M3.4 (A) decision."""

    def test_PERMANENT_no_driven_references(self):
        from RBFtools import core_live
        src = _strip_docstrings_and_comments(
            inspect.getsource(core_live))
        forbidden = ("read_driven_info", "driven_node", "driven_attrs")
        for f in forbidden:
            self.assertNotIn(f, src,
                "core_live.py executable body contains {!r} — Live "
                "Edit MUST NOT touch driven side; would cause "
                "feedback loop with RBF compute. See addendum §M3.4 "
                "(A) decision.".format(f))


# ----------------------------------------------------------------------
# T_THROTTLE_TIME_INJECTION — PERMANENT GUARD
# ----------------------------------------------------------------------


class T_ThrottleTimeInjection(unittest.TestCase):
    """PERMANENT GUARD — DO NOT REMOVE.

    Throttle pure functions must accept now_ts as a parameter; they
    must NOT call time.time() / time.monotonic() / datetime.now()
    directly. Keeps the state machine deterministic under unit
    tests and prevents subtle ordering bugs from time drift.
    Caller (LiveEditWidget) is the only real-time source — see
    addendum §M3.4 (B) decision."""

    def test_PERMANENT_no_time_calls_in_executable_body(self):
        from RBFtools import core_live
        src = _strip_docstrings_and_comments(
            inspect.getsource(core_live))
        forbidden = (
            "time.time(",
            "time.monotonic(",
            "datetime.now(",
            "datetime.utcnow(",
        )
        for f in forbidden:
            self.assertNotIn(f, src,
                "core_live.py executable body calls {} — throttle "
                "functions must inject now_ts; see addendum §M3.4 "
                "(B) decision.".format(f))


if __name__ == "__main__":
    unittest.main()
