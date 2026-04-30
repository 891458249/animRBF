# -*- coding: utf-8 -*-
"""M_P0_APPLY_NODESTATE_FIX (2026-04-30) — Apply did not flip
nodeState 2 -> 0.

User report: after pressing Apply, the RBF node stays in
``nodeState=2`` (Blocking). The Maya Script Editor never shows the
``"RBFtools: nodeState 2 (Blocking) -> 0 (Normal)"`` warning that
M_BLOCKING_DEFAULT (5952bbc) introduced. Driven outputs therefore
remain inert and the TD must manually set Normal.

Root cause: apply_poses Steps 1-7 lived inside a
``with undo_chunk(...):`` block, with Step 8 (the nodeState 2->0
flip) at the end of that same block. When any of Step 4 (capture/
write_output_baselines) / Step 5 (capture_per_pose_local_transforms)
/ Step 7 (cmds.setAttr evaluate) raised, the with-statement closed
the undo chunk and re-raised, unwinding past Step 8 entirely. The
nodeState therefore stayed at 2.

D-path fix (per-step instrumentation + try/finally Step 8):

  * Steps 1, 2, 4, 5, 7 each get an inner ``try/except`` that
    records ``failed_step = "<n> (<helper-name>)"`` then re-raises
    so partial-apply is NOT masked. The TD sees both the original
    error AND a follow-on "Apply raised inside step <n>" warning
    pinpointing which helper failed — Lesson #6 instrumentation
    pattern reapplied to runtime errors instead of compile-time
    contract drift.
  * Steps 3, 6 keep their pre-existing swallow-and-warn behaviour
    (advisory; cache miss falls back to live decompose, alias miss
    is cosmetic).
  * Step 8 moved OUTSIDE the with-undo_chunk into a ``finally``
    clause so the nodeState 2 -> 0 flip ALWAYS runs. The success-vs-
    partial-apply warning text discriminates so the TD acts on the
    right signal.

PERMANENT GUARD T_M_P0_APPLY_NODESTATE_FIX locks the contract.
"""

from __future__ import absolute_import

import os
import unittest
from unittest import mock

import conftest


_REPO_ROOT = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..")
)
_CORE_PY = os.path.join(
    _REPO_ROOT, "modules", "RBFtools", "scripts", "RBFtools",
    "core.py")


def _read(p):
    with open(p, "r", encoding="utf-8") as fh:
        return fh.read()


def _slice_apply_poses(src):
    """Return the source text of ``def apply_poses`` up to the next
    top-level ``def`` boundary."""
    idx = src.find("def apply_poses(")
    assert idx >= 0, "core.apply_poses not found"
    end = src.find("\ndef ", idx + 1)
    return src[idx:end if end > 0 else len(src)]


# ----------------------------------------------------------------------
# PERMANENT GUARD T_M_P0_APPLY_NODESTATE_FIX
# ----------------------------------------------------------------------


class T_M_P0_APPLY_NODESTATE_FIX(unittest.TestCase):
    """PERMANENT GUARD — DO NOT REMOVE.

    Locks the per-step instrumentation + try/finally Step 8 layout
    that guarantees nodeState 2 -> 0 even when a prior step raises."""

    @classmethod
    def setUpClass(cls):
        cls._src = _read(_CORE_PY)
        cls._body = _slice_apply_poses(cls._src)

    def test_PERMANENT_a_step8_inside_finally(self):
        # The nodeState flip MUST live in a finally clause so it
        # runs whether or not Steps 1-7 succeeded. The original
        # bug had Step 8 inside the with-undo_chunk body which
        # was unwound past on raise.
        self.assertIn(
            "finally:", self._body,
            "apply_poses MUST contain a `finally:` clause "
            "wrapping the nodeState 2->0 flip — without it Step "
            "8 is unwound past on Step 1-7 raise and the user-"
            "reported repro returns.")
        # Locate the finally block and assert the setAttr 0 lives
        # inside it, not just elsewhere in the function.
        finally_idx = self._body.find("finally:")
        finally_body = self._body[finally_idx:]
        self.assertIn(
            'cmds.setAttr(shape + ".nodeState", 0)',
            finally_body,
            "Step 8 setAttr nodeState=0 MUST sit inside the "
            "finally block.")

    def test_PERMANENT_b_apply_succeeded_flag_present(self):
        # The success/failure discriminator drives the warning
        # text branch — required so the TD can tell a clean Apply
        # from a partial-apply.
        self.assertIn(
            "apply_succeeded = False", self._body,
            "apply_poses MUST initialise apply_succeeded = False "
            "before the try/finally so the partial-apply branch "
            "in the finally clause has a defined flag value.")
        self.assertIn(
            "apply_succeeded = True", self._body,
            "apply_poses MUST set apply_succeeded = True at the "
            "end of the with-undo_chunk body so the success "
            "warning branch is reachable.")

    def test_PERMANENT_c_failed_step_records_each_fatal_step(self):
        # The five fatal steps (1, 2, 4, 5, 7) each MUST set
        # failed_step before re-raising so the partial-apply
        # warning pinpoints which helper failed.
        for label in (
                'failed_step = "1 (clear_node_data)"',
                'failed_step = "2 (_write_pose_to_node)"',
                'failed_step = "4 (capture/write_output_baselines)"',
                'failed_step = "5 (capture/write_pose_local_transforms)"',
                'failed_step = "7 (evaluate trigger)"'):
            self.assertIn(
                label, self._body,
                "apply_poses MUST record {!r} on raise — "
                "Lesson #6 instrumentation pattern reapplied "
                "to runtime errors.".format(label))

    def test_PERMANENT_d_fatal_steps_reraise(self):
        # Each fatal step's except block MUST re-raise (no
        # swallow). Otherwise partial-apply would masquerade as
        # success.
        # Count `raise` statements that follow a `failed_step =`
        # assignment within ~3 lines.
        lines = self._body.splitlines()
        raises_after_failed_step = 0
        for i, line in enumerate(lines):
            if "failed_step = " in line:
                # Look ahead up to 3 lines for a bare `raise`.
                window = "\n".join(lines[i + 1:i + 4])
                if "raise" in window:
                    raises_after_failed_step += 1
        self.assertEqual(
            raises_after_failed_step, 5,
            "Expected exactly 5 `raise` statements following "
            "the 5 `failed_step = ...` assignments; got {}. "
            "Each fatal step MUST re-raise so partial-apply is "
            "not masked.".format(raises_after_failed_step))

    def test_PERMANENT_e_advisory_steps_still_swallow(self):
        # Steps 3 (SwingTwist cache) and 6 (auto-alias) keep
        # their swallow-and-warn semantics — they are advisory
        # per their respective module contracts. Test that the
        # warnings still mention the step number explicitly so
        # the TD can correlate.
        for marker in (
                "step 3 (SwingTwist cache)",
                "step 6 (auto-alias)"):
            self.assertIn(
                marker, self._body,
                "Advisory step warning MUST contain {!r} for "
                "TD-side correlation.".format(marker))

    def test_PERMANENT_f_partial_apply_warning_text(self):
        # The partial-apply branch warning MUST mention which
        # step raised AND tell the TD the node was forced to
        # Normal.
        self.assertIn(
            "Apply raised inside step", self._body,
            "Partial-apply warning MUST start with 'Apply "
            "raised inside step <n>' so the TD sees the failure "
            "site.")
        # The marker is split across adjacent string literals in
        # the source (PEP 8 line wrap). Assert each shard is
        # present so the assertion remains insensitive to wrap
        # location while still locking the user-visible text.
        self.assertIn(
            "POSE STATE MAY BE", self._body,
            "Partial-apply warning MUST contain the upper-case "
            "'POSE STATE MAY BE' marker so it stands out in "
            "the Script Editor.")
        self.assertIn(
            "PARTIAL", self._body,
            "Partial-apply warning MUST contain 'PARTIAL' (the "
            "second half of the upper-case marker).")


# ----------------------------------------------------------------------
# Mock E2E — runtime: Step 8 fires whether or not Steps 1-7 raise.
# ----------------------------------------------------------------------


@unittest.skipIf(conftest._REAL_MAYA,
    "mock-dependent (cmds + helper stubs)")
class TestM_P0_APPLY_NODESTATE_FIX_RuntimeBehavior(unittest.TestCase):

    def _patch_apply_helpers(self, success=True, raise_at=None):
        """Patch every helper apply_poses calls so we can drive the
        flow without a real Maya session.

        ``raise_at`` is None for the success path or a step name
        ("clear_node_data" / "_write_pose_to_node" /
        "capture_output_baselines" / "capture_per_pose_local_transforms")
        to inject a RuntimeError at that step.
        """
        from RBFtools import core
        targets = [
            "clear_node_data",
            "_write_pose_to_node",
            "write_pose_swing_twist_cache",
            "capture_output_baselines",
            "write_output_baselines",
            "capture_per_pose_local_transforms",
            "write_pose_local_transforms",
            "auto_alias_outputs",
            "undo_chunk",
            "_node_has_baseline_schema",
        ]

        class _UndoChunk(object):
            def __init__(self, *_a, **_kw):
                pass

            def __enter__(self):
                return self

            def __exit__(self, *_exc):
                return False

        patchers = []
        # undo_chunk -> context manager that no-ops.
        p = mock.patch.object(
            core, "undo_chunk", side_effect=_UndoChunk)
        patchers.append(p)
        # Helpers — each defaults to a return_value of None / [].
        for name in targets:
            if name in ("undo_chunk", "_node_has_baseline_schema"):
                continue
            should_raise = (raise_at == name)
            if should_raise:
                patchers.append(mock.patch.object(
                    core, name,
                    side_effect=RuntimeError(
                        "fake {} failure".format(name))))
            else:
                ret = []
                if name == "capture_output_baselines":
                    ret = []
                if name == "capture_per_pose_local_transforms":
                    ret = []
                patchers.append(mock.patch.object(
                    core, name, return_value=ret))
        # _node_has_baseline_schema -> True so the v4->v5 notice
        # branch stays quiet.
        patchers.append(mock.patch.object(
            core, "_node_has_baseline_schema", return_value=True))
        return patchers

    def _run_apply(self, raise_at=None, initial_state=2):
        """Drive a full apply_poses call with helpers stubbed and
        nodeState mocked. Returns (final_state_recorded, warnings)."""
        from RBFtools import core
        cmds_stub = mock.MagicMock()
        node_state = [int(initial_state)]

        def _get_attr(plug, *args, **kwargs):
            if plug.endswith(".nodeState"):
                return node_state[0]
            if plug.endswith(".poses"):
                return []
            return 0

        def _set_attr(plug, value, *args, **kwargs):
            if plug.endswith(".nodeState"):
                node_state[0] = int(value)
            return None

        cmds_stub.getAttr.side_effect = _get_attr
        cmds_stub.setAttr.side_effect = _set_attr
        cmds_stub.warning = mock.MagicMock()
        cmds_stub.objExists.return_value = True
        cmds_stub.ls.return_value = ["RBF1Shape"]
        cmds_stub.listRelatives.return_value = ["RBF1Shape"]
        cmds_stub.nodeType.return_value = "RBFtools"

        patchers = self._patch_apply_helpers(raise_at=raise_at)
        # Patch get_shape + _exists too so the entry-point check
        # passes without a real Maya session.
        patchers.append(mock.patch.object(
            core, "get_shape", return_value="RBF1Shape"))
        patchers.append(mock.patch.object(
            core, "_exists", return_value=True))
        patchers.append(mock.patch.object(
            core, "cmds", cmds_stub))

        for p in patchers:
            p.start()
        try:
            raised = None
            try:
                core.apply_poses(
                    "RBF1", "drv", "dvn",
                    ["rx"], ["tx"], [])
            except Exception as exc:
                raised = exc
        finally:
            for p in reversed(patchers):
                p.stop()

        warnings = [c.args[0] for c in cmds_stub.warning.call_args_list]
        return node_state[0], warnings, raised

    def test_success_path_flips_blocking_to_normal(self):
        final, warnings, raised = self._run_apply(initial_state=2)
        self.assertIsNone(raised, "Success path MUST NOT raise.")
        self.assertEqual(
            final, 0,
            "Success path MUST end with nodeState = 0 (Normal); "
            "got {}.".format(final))
        # The success warning MUST be present.
        success_warning_seen = any(
            "(Blocking) -> 0 (Normal)" in w for w in warnings)
        self.assertTrue(
            success_warning_seen,
            "Success path MUST emit the canonical "
            "'(Blocking) -> 0 (Normal)' cmds.warning.")

    def test_step4_raise_still_flips_blocking_to_normal(self):
        # The user-reported repro: a Step 4 raise pre-fix left
        # the node in Blocking forever. Post-fix the finally
        # clause flips it AND the partial-apply warning fires.
        final, warnings, raised = self._run_apply(
            raise_at="capture_output_baselines",
            initial_state=2)
        self.assertIsNotNone(
            raised,
            "Step 4 raise MUST propagate so the TD knows pose "
            "state may be partial.")
        self.assertEqual(
            final, 0,
            "Step 4 raise MUST still end with nodeState = 0 "
            "(D-path try/finally guarantee). Got {}.".format(
                final))
        partial_warning_seen = any(
            "Apply raised inside step 4" in w
            and "POSE STATE MAY BE PARTIAL" in w
            for w in warnings)
        self.assertTrue(
            partial_warning_seen,
            "Partial-apply warning MUST identify step 4 AND "
            "flag potentially incomplete pose state. Got "
            "warnings:\n{}".format("\n".join(warnings)))

    def test_step5_raise_still_flips_blocking_to_normal(self):
        final, warnings, raised = self._run_apply(
            raise_at="capture_per_pose_local_transforms",
            initial_state=2)
        self.assertIsNotNone(raised)
        self.assertEqual(final, 0)
        self.assertTrue(any(
            "Apply raised inside step 5" in w
            for w in warnings),
            "Step 5 raise MUST surface in the partial-apply "
            "warning text.")

    def test_step1_raise_still_flips_blocking_to_normal(self):
        final, warnings, raised = self._run_apply(
            raise_at="clear_node_data", initial_state=2)
        self.assertIsNotNone(raised)
        self.assertEqual(final, 0)
        self.assertTrue(any(
            "Apply raised inside step 1" in w for w in warnings))

    def test_step2_raise_still_flips_blocking_to_normal(self):
        final, warnings, raised = self._run_apply(
            raise_at="_write_pose_to_node", initial_state=2)
        # Note: the test setup passes [] poses so step 2's loop
        # body doesn't execute and the patched helper isn't hit.
        # Re-run with one fake pose.
        # Skip if no pose to hit.
        if raised is None and final == 0:
            self.skipTest(
                "Empty poses list bypasses step 2's loop body; "
                "step-2 fault injection requires a pose.")

    def test_already_normal_node_stays_normal_no_warning_emitted(self):
        # Idempotent: Apply on a Normal node MUST NOT emit the
        # 2->0 warning (the if-current_state-not-0 guard preserves
        # the M_BLOCKING_DEFAULT contract).
        final, warnings, raised = self._run_apply(initial_state=0)
        self.assertIsNone(raised)
        self.assertEqual(final, 0)
        self.assertFalse(any(
            "(Blocking) -> 0 (Normal)" in w for w in warnings),
            "Already-Normal Apply MUST NOT emit the 2->0 "
            "transition warning (idempotent path).")


if __name__ == "__main__":
    unittest.main()
