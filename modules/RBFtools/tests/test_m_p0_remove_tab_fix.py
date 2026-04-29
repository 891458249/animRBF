# -*- coding: utf-8 -*-
"""M_P0_REMOVE_TAB_FIX (2026-04-30) — driver/driven tab close X
unresponsive (P0).

Repro chain end-to-end:

  1. ``tabCloseRequested(idx)`` -> _TabbedSourceEditorBase._on_tab_close
     (tabbed_source_editor.py:292)
  2. -> ``removeRequested.emit(idx)`` (line 293)
  3. -> main_window connect -> _on_driver_source_remove_requested
  4. -> ``ctrl.remove_driver_source(index)`` (controller.py:249)
  5. -> ``self.ask_confirm(action_id=, title=, summary=)`` was passing
     only THREE kwargs to a signature that demanded FOUR strict
     positionals: ``ask_confirm(self, title, summary, preview_text,
     action_id)``. Python raised TypeError, Qt slot dispatch
     swallowed it, and the X glyph looked dead.

The same drift hit two more callsites:

  * ``remove_driven_source``           (line 419, driven mirror)
  * ``mirror_multi_source_info``       (line 708)

Path A double-belt fix:

  * Signature defaults — ``ask_confirm(self, title, summary,
    preview_text="", action_id="")`` so future M_UIRECONCILE-era
    callers omitting the optional fields stop raising.
  * Per-callsite explicit ``preview_text=""`` at all three drifted
    sites so a future signature revert cannot silently
    re-introduce the same bug.

PERMANENT GUARD T_REMOVE_TAB_CONFIRM_CONTRACT locks both belts.

Lesson #6 (project-methodology candidate): "call-site contract drift
that static grep cannot catch needs an AST guard." Here we walk
``controller.py``'s AST and assert every ``self.ask_confirm(...)``
call passes either four args or relies on the documented defaults
— grep alone wouldn't have caught the kw-only-three-args drift
because the call DID compile.
"""

from __future__ import absolute_import

import ast
import inspect
import os
import unittest
from unittest import mock

import conftest


_REPO_ROOT = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..")
)
_CTRL_PY = os.path.join(
    _REPO_ROOT, "modules", "RBFtools", "scripts", "RBFtools",
    "controller.py")


# Names of the four ask_confirm parameters (matches the signature
# at controller.py:1190 post-fix).
_ASK_CONFIRM_PARAMS = ("title", "summary", "preview_text", "action_id")


def _read(p):
    with open(p, "r", encoding="utf-8") as fh:
        return fh.read()


# ----------------------------------------------------------------------
# PERMANENT GUARD T_REMOVE_TAB_CONFIRM_CONTRACT
# ----------------------------------------------------------------------


class T_REMOVE_TAB_CONFIRM_CONTRACT(unittest.TestCase):
    """PERMANENT GUARD — DO NOT REMOVE.

    Locks both belts of the M_P0_REMOVE_TAB_FIX double-belt fix:

      * Signature has empty-string defaults for preview_text +
        action_id so kw-only-three-args callers don't raise.
      * Each existing self.ask_confirm callsite either passes the
        full four params explicitly OR falls within the
        documented defaults — caught by the AST walk."""

    @classmethod
    def setUpClass(cls):
        cls._src = _read(_CTRL_PY)
        cls._tree = ast.parse(cls._src)

    def test_PERMANENT_a_signature_has_defaults(self):
        # Inspect the live MainController class — defaults landed
        # at runtime, not just in source text.
        from RBFtools.controller import MainController
        sig = inspect.signature(MainController.ask_confirm)
        params = sig.parameters
        for name in ("preview_text", "action_id"):
            self.assertIn(
                name, params,
                "ask_confirm signature MUST keep parameter "
                "{!r}".format(name))
            self.assertNotEqual(
                params[name].default,
                inspect.Parameter.empty,
                "ask_confirm({}=...) MUST have a default value — "
                "the M_P0_REMOVE_TAB_FIX double-belt requires it as "
                "the catch-all for any future kw-only callsite "
                "drift.".format(name))
        # Specifically the empty-string defaults so ConfirmDialog's
        # internal ``preview_text or ""`` coercion stays a no-op.
        self.assertEqual(params["preview_text"].default, "")
        self.assertEqual(params["action_id"].default, "")

    def test_PERMANENT_b_signature_source_text_match(self):
        # Defence-in-depth source-scan: the literal default-bearing
        # signature line must appear in the source so a future code
        # mod can't accidentally land defaults at runtime via
        # monkey-patching but lose them in the canonical source.
        self.assertIn(
            'def ask_confirm(self, title, summary, '
            'preview_text="", action_id="")',
            self._src,
            "controller.ask_confirm source line MUST carry the "
            "default-bearing signature verbatim.")

    def test_PERMANENT_c_remove_driver_source_passes_preview(self):
        # The original Bug-1 callsite must explicitly pass
        # preview_text="" — defence in depth, even though the
        # signature default would catch a missing arg.
        body = self._src.split(
            "def remove_driver_source(self, index):"
        )[1].split("\n    def ")[0]
        self.assertIn('preview_text=""', body,
            "remove_driver_source MUST explicitly pass "
            "preview_text=\"\" so a future signature revert "
            "cannot silently reintroduce the TypeError drift.")

    def test_PERMANENT_d_remove_driven_source_passes_preview(self):
        body = self._src.split(
            "def remove_driven_source(self, index):"
        )[1].split("\n    def ")[0]
        self.assertIn('preview_text=""', body,
            "remove_driven_source MUST explicitly pass "
            "preview_text=\"\" — driven mirror of Bug-1.")

    def test_PERMANENT_e_ast_guard_every_callsite_complete(self):
        # AST walk every Call(func=Attribute(attr='ask_confirm'))
        # and assert each passes the full {title, summary,
        # preview_text, action_id} set — either positionally or
        # as kwargs. This is the lesson-#6 drift guard: static
        # grep would not have caught the original Bug because
        # the kw-only-three-args call DID parse + compile.
        callsites = []
        for node in ast.walk(self._tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if not isinstance(func, ast.Attribute):
                continue
            if func.attr != "ask_confirm":
                continue
            # Skip the dispatch call inside ask_confirm itself
            # (ConfirmDialog.confirm forwarding) — its 'attr' is
            # 'confirm', not 'ask_confirm', so it won't match here.
            # We're only matching self.ask_confirm calls.
            kw_names = {kw.arg for kw in node.keywords if kw.arg}
            pos_count = len(node.args)
            # Skip the definition line itself (FunctionDef body
            # lookups would not reach here — Call nodes only).
            callsites.append((node.lineno, kw_names, pos_count))
        self.assertGreaterEqual(
            len(callsites), 8,
            "Expected at least 8 self.ask_confirm callsites "
            "(M3.0 + M_UIRECONCILE additions) — found {}; "
            "AST walker may have missed something.".format(
                len(callsites)))
        # Each callsite must cover the four params via positional
        # OR keyword args. With path-A defaults, omitting
        # preview_text/action_id is technically legal — but the
        # explicit per-callsite contract is "always pass every
        # required kwarg" so a signature regression doesn't
        # cascade. We assert the full set is present at every
        # callsite to catch drift at the call-site layer too.
        missing = []
        for lineno, kw_names, pos_count in callsites:
            covered = set(kw_names)
            # Positional args fill the first N named params in
            # signature order.
            for i in range(pos_count):
                if i < len(_ASK_CONFIRM_PARAMS):
                    covered.add(_ASK_CONFIRM_PARAMS[i])
            need = set(_ASK_CONFIRM_PARAMS) - covered
            if need:
                missing.append((lineno, sorted(need)))
        self.assertEqual(
            missing, [],
            "AST guard: ask_confirm callsites missing required "
            "args (lesson-#6 drift catch). Each tuple is "
            "(lineno, missing-args). The signature defaults are "
            "the catch-all but explicit per-callsite kwargs are "
            "the load-bearing contract.\nDrifted callsites:\n"
            "{}".format(missing))


# ----------------------------------------------------------------------
# Mock E2E — runtime tab-close happy path now reaches core.remove_*
# ----------------------------------------------------------------------


@unittest.skipIf(conftest._REAL_MAYA,
    "mock-dependent (cmds + ConfirmDialog stubs)")
class TestM_P0_REMOVE_TAB_FIX_RuntimeBehavior(unittest.TestCase):
    """Verify the slot dispatch chain reaches core.remove_*_source
    without raising. Pre-fix: TypeError inside ask_confirm bubbled
    up through Qt slot dispatch and was swallowed; post-fix the
    confirm prompt fires and 'OK' lets core.remove_* run."""

    def _make_ctrl(self):
        from RBFtools.controller import MainController
        ctrl = MainController.__new__(MainController)
        ctrl._current_node = "RBF1"
        ctrl.driverSourcesChanged = mock.MagicMock()
        ctrl.drivenSourcesChanged = mock.MagicMock()
        return ctrl

    def test_remove_driver_source_calls_ask_confirm_with_4_args(self):
        # Mock ask_confirm to capture how remove_driver_source
        # invokes it — with the path-A fix the call MUST pass
        # all four kwargs so a future strict-signature revert
        # remains safe.
        from RBFtools import core
        from RBFtools.controller import MainController
        ctrl = self._make_ctrl()
        ctrl.ask_confirm = mock.MagicMock(return_value=True)
        with mock.patch.object(core, "remove_driver_source"):
            MainController.remove_driver_source(ctrl, 0)
        ctrl.ask_confirm.assert_called_once()
        kw = ctrl.ask_confirm.call_args.kwargs
        self.assertEqual(
            set(kw.keys()),
            set(_ASK_CONFIRM_PARAMS),
            "remove_driver_source MUST pass all four ask_confirm "
            "kwargs (post path-A double-belt). Got: "
            "{}".format(sorted(kw.keys())))
        self.assertEqual(kw["action_id"], "remove_driver_source")
        self.assertEqual(kw["preview_text"], "")

    def test_remove_driven_source_calls_ask_confirm_with_4_args(self):
        from RBFtools import core
        from RBFtools.controller import MainController
        ctrl = self._make_ctrl()
        ctrl.ask_confirm = mock.MagicMock(return_value=True)
        with mock.patch.object(core, "remove_driven_source"):
            MainController.remove_driven_source(ctrl, 0)
        ctrl.ask_confirm.assert_called_once()
        kw = ctrl.ask_confirm.call_args.kwargs
        self.assertEqual(
            set(kw.keys()),
            set(_ASK_CONFIRM_PARAMS))
        self.assertEqual(kw["action_id"], "remove_driven_source")
        self.assertEqual(kw["preview_text"], "")

    def test_remove_driver_source_proceeds_when_confirmed(self):
        # Happy path: ask_confirm returns True -> core.remove
        # actually runs, driverSourcesChanged emits.
        from RBFtools import core
        from RBFtools.controller import MainController
        ctrl = self._make_ctrl()
        ctrl.ask_confirm = mock.MagicMock(return_value=True)
        with mock.patch.object(
                core, "remove_driver_source") as core_remove:
            ok = MainController.remove_driver_source(ctrl, 3)
        core_remove.assert_called_once_with("RBF1", 3)
        ctrl.driverSourcesChanged.emit.assert_called_once()
        self.assertTrue(ok)

    def test_remove_driver_source_aborts_on_cancel(self):
        # User clicks Cancel: core.remove must NOT run; signal
        # must NOT fire.
        from RBFtools import core
        from RBFtools.controller import MainController
        ctrl = self._make_ctrl()
        ctrl.ask_confirm = mock.MagicMock(return_value=False)
        with mock.patch.object(
                core, "remove_driver_source") as core_remove:
            ok = MainController.remove_driver_source(ctrl, 0)
        core_remove.assert_not_called()
        ctrl.driverSourcesChanged.emit.assert_not_called()
        self.assertFalse(ok)

    def test_default_signature_tolerates_three_kwargs(self):
        # Belt #1 verification: even if an old caller passes only
        # three kwargs (the original Bug shape), the call must NOT
        # raise TypeError. ConfirmDialog is patched so we don't
        # hit Qt at all; we only assert the function dispatches
        # cleanly with the defaults.
        from RBFtools.controller import MainController
        ctrl = self._make_ctrl()
        with mock.patch(
                "RBFtools.ui.widgets.confirm_dialog.ConfirmDialog"
                ".confirm",
                return_value=True) as cd:
            result = MainController.ask_confirm(
                ctrl,
                title="t",
                summary="s",
                action_id="a")
        self.assertTrue(result)
        # ConfirmDialog.confirm received the empty preview_text
        # default propagated through.
        cd.assert_called_once()
        args = cd.call_args.args
        self.assertEqual(args[0], "t")
        self.assertEqual(args[1], "s")
        self.assertEqual(args[2], "")        # preview_text default
        self.assertEqual(args[3], "a")

    def test_default_signature_tolerates_two_kwargs(self):
        # Even more conservative: only title + summary -> still OK.
        from RBFtools.controller import MainController
        ctrl = self._make_ctrl()
        with mock.patch(
                "RBFtools.ui.widgets.confirm_dialog.ConfirmDialog"
                ".confirm",
                return_value=True):
            # Should not raise.
            result = MainController.ask_confirm(
                ctrl, title="t", summary="s")
        self.assertTrue(result)


if __name__ == "__main__":
    unittest.main()
