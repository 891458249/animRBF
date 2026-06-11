# -*- coding: utf-8 -*-
"""M_P1_ENC_COMBO_FIX (2026-04-29) — two-bug atomic fix.

Bug 1 (P0, regression introduced by enc-1 / 673ab13):
  TD picks Quaternion / BendRoll / ExpMap / SwingTwist on the
  inputEncoding combo and the combo immediately bounces back to
  Raw. Repro path:

    1. user picks idx=4 (SwingTwist)
    2. rbf_section._on_input_encoding(4) emits
       attributeChanged + inputEncodingChanged (M_ENC_AUTOPIPE).
    3. ctrl.on_input_encoding_changed(4) calls
       core.auto_resolve_generic_rotate_orders(...) — OK — then
       calls self._load_settings() to re-fire settingsLoaded
       so rbf_section.load() repopulates the rotate-order editor.
    4. core.get_all_settings(node) returns a dict that
       HISTORICALLY OMITS the inputEncoding key (and 6 other M2.x
       fields — clampEnabled / regularization / solverMethod /
       clampInflation / driverInputRotateOrder /
       outputQuaternionGroupStart).
    5. settingsLoaded -> main_window -> rbf_section.load(data) ->
       data.get("inputEncoding", 0) -> default 0 ->
       setCurrentIndex(0) -> combo bounces back to Raw.

  The same dict gap caused a LATENT "node-switch shows wrong
  inputEncoding combo state" bug for every M2.x field listed,
  pre-dating the enc-1 cascade.

Bug 2 (P1):
  output_encoding combo's HelpButton (added in enc-2 / 6528211)
  pops one merged "output_encoding" bubble describing all three
  encodings at once. TD wants per-item content (Euler / Quaternion
  / ExpMap) the way the input-encoding combo does it (per
  M_HELPTEXT_ENC_PER_KEY).

Fix (P1 atomic, 5 changes in one commit):

  * core.get_all_settings now includes the 7 missing M2.x fields,
    making the UI reload dict complete. Closes the underlying gap
    behind both Bug 1 and the latent node-switch issue.

  * controller declares a NARROW signal
    ``rotateOrderEditorReload(list)`` and
    ``on_input_encoding_changed`` emits it (with the freshly
    read driverInputRotateOrder values) instead of round-tripping
    through ``_load_settings``. Eliminates the cascade that
    surfaced Bug 1 even with the dict gap closed.

  * rbf_section exposes ``set_rotate_order_values(values)`` —
    public hook for the narrow signal.

  * main_window connects the narrow signal to the new public
    method, and replaces the plain HelpButton next to the
    output-encoding combo with a ComboHelpButton that carries
    a per-index key_map [output_enc_euler, output_enc_quaternion,
    output_enc_expmap].

  * help_texts.py grows three per-encoding keys in EN + ZH parity.

PERMANENT GUARD T_M_P1_ENC_COMBO_FIX locks the contract.
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
_CTRL_PY = os.path.join(
    _REPO_ROOT, "modules", "RBFtools", "scripts", "RBFtools",
    "controller.py")
_RBF_SECTION_PY = os.path.join(
    _REPO_ROOT, "modules", "RBFtools", "scripts", "RBFtools",
    "ui", "widgets", "rbf_section.py")
_MAIN_WINDOW_PY = os.path.join(
    _REPO_ROOT, "modules", "RBFtools", "scripts", "RBFtools",
    "ui", "main_window.py")
_HELP_TEXTS_PY = os.path.join(
    _REPO_ROOT, "modules", "RBFtools", "scripts", "RBFtools",
    "ui", "help_texts.py")


_NEW_OUTPUT_ENC_KEYS = (
    "output_enc_euler",
    "output_enc_quaternion",
    "output_enc_expmap",
)


_REQUIRED_GET_ALL_SETTINGS_FIELDS = (
    "inputEncoding",
    "clampEnabled",
    "clampInflation",
    "regularization",
    "solverMethod",
    "driverInputRotateOrder",
    "outputQuaternionGroupStart",
)


def _read(p):
    with open(p, "r", encoding="utf-8") as fh:
        return fh.read()


# ----------------------------------------------------------------------
# PERMANENT GUARD T_M_P1_ENC_COMBO_FIX
# ----------------------------------------------------------------------


class T_M_P1_ENC_COMBO_FIX(unittest.TestCase):
    """PERMANENT GUARD — DO NOT REMOVE.

    The 5-file P1 fix is interlocked: any one piece reverting on
    its own re-opens Bug 1 or Bug 2. This guard locks all five."""

    @classmethod
    def setUpClass(cls):
        cls._core = _read(_CORE_PY)
        cls._ctrl = _read(_CTRL_PY)
        cls._rbf = _read(_RBF_SECTION_PY)
        cls._mw = _read(_MAIN_WINDOW_PY)
        cls._help = _read(_HELP_TEXTS_PY)

    def test_PERMANENT_a_get_all_settings_includes_7_fields(self):
        # Source-scan: each of the 7 M2.x fields appears as a key
        # inside the get_all_settings function body.
        body = self._core.split(
            "def get_all_settings(node):"
        )[1].split("\ndef ")[0]
        for key in _REQUIRED_GET_ALL_SETTINGS_FIELDS:
            self.assertIn(
                '"{}":'.format(key), body,
                "core.get_all_settings missing field {!r} — Bug 1 "
                "root-cause regression: the UI reload dict will "
                "force rbf_section.load() to fall back to the "
                "default 0 / False / [] for this attr, bouncing "
                "any combo bound to it.".format(key))

    def test_PERMANENT_b_controller_declares_narrow_signal(self):
        self.assertIn(
            "rotateOrderEditorReload = QtCore.Signal(list)",
            self._ctrl,
            "controller MUST declare rotateOrderEditorReload "
            "signal — narrow alternative to the _load_settings "
            "cascade that triggered Bug 1.")

    def test_PERMANENT_c_slot_uses_narrow_signal_not_cascade(self):
        body = self._ctrl.split(
            "def on_input_encoding_changed(self, idx):"
        )[1].split("\n    def ")[0]
        self.assertIn(
            "self.rotateOrderEditorReload.emit(", body,
            "Slot MUST emit the narrow rotateOrderEditorReload "
            "signal carrying the freshly-read rotate-order values.")
        self.assertNotIn(
            "self._load_settings()", body,
            "Slot MUST NOT re-enter _load_settings — that cascade "
            "is the Bug 1 trigger. P1 contract is the narrow "
            "signal path.")

    def test_PERMANENT_d_rbf_section_public_helper(self):
        self.assertIn(
            "def set_rotate_order_values(self, values):",
            self._rbf,
            "rbf_section MUST expose set_rotate_order_values "
            "as the narrow-signal entry-point — the slot wiring "
            "in main_window targets it directly.")

    def test_PERMANENT_e_main_window_combohelpbutton(self):
        # Source-scan: main_window MUST instantiate a ComboHelpButton
        # bound to the output encoding combo with the correct
        # 3-key key_map.
        self.assertIn(
            "ComboHelpButton(\n",
            self._mw,
            "main_window expected ComboHelpButton instantiation.")
        for key in _NEW_OUTPUT_ENC_KEYS:
            self.assertIn(
                '"{}"'.format(key), self._mw,
                "main_window ComboHelpButton key_map missing "
                "{!r} — Bug 2 per-item bubble would not "
                "resolve.".format(key))
        self.assertIn(
            "self._output_encoding_combo",
            self._mw,
            "ComboHelpButton MUST bind to "
            "self._output_encoding_combo so currentIndexChanged + "
            "highlighted dispatch through the per-index key_map.")

    def test_PERMANENT_f_main_window_wires_narrow_signal(self):
        self.assertIn(
            "ctrl.rotateOrderEditorReload.connect(",
            self._mw,
            "main_window MUST connect the controller's "
            "rotateOrderEditorReload signal to a slot.")
        self.assertIn(
            "self._rbf_section.set_rotate_order_values",
            self._mw,
            "Wired slot MUST be rbf_section.set_rotate_order_values "
            "— the public narrow-reload entry-point.")

    def test_PERMANENT_g_combohelpbutton_import_present(self):
        # The constructor must be importable in main_window.
        self.assertIn(
            "ComboHelpButton", self._mw.split("class ")[0],
            "main_window must import ComboHelpButton at module "
            "scope — runtime NameError would shadow the user-"
            "visible help-bubble fix.")

    def test_PERMANENT_h_en_zh_parity_for_output_enc_keys(self):
        for key in _NEW_OUTPUT_ENC_KEYS:
            count = self._help.count('"{}":'.format(key))
            self.assertGreaterEqual(
                count, 2,
                "help_texts.py missing EN/ZH parity for {!r} "
                "(found {} occurrences, need >= 2)".format(
                    key, count))

    def test_PERMANENT_i_help_text_lookup_returns_nonempty(self):
        # False-green prevention (d01a964 lesson): source-scan key
        # existence is necessary but not sufficient. Verify the
        # runtime lookup returns non-empty content for each key.
        from RBFtools.ui import help_texts
        for key in _NEW_OUTPUT_ENC_KEYS:
            self.assertTrue(
                help_texts._EN.get(key),
                "_EN[{!r}] empty — ComboHelpButton would render "
                "blank bubble.".format(key))
            self.assertTrue(
                help_texts._ZH.get(key),
                "_ZH[{!r}] empty — ZH locale would render blank "
                "bubble.".format(key))


# ----------------------------------------------------------------------
# Mock E2E — runtime verification (Bug 1 + Bug 2 both)
# ----------------------------------------------------------------------


@unittest.skipIf(conftest._REAL_MAYA,
    "mock-dependent (cmds + Qt minimal shim)")
class TestM_P1_ENC_COMBO_FIX_RuntimeBehavior(unittest.TestCase):

    # ------------------------------------------------------------------
    # Bug 1 — get_all_settings now carries the 7 fields.
    # ------------------------------------------------------------------

    def test_get_all_settings_returns_inputencoding_field(self):
        # The single field most directly responsible for the TD
        # repro: without inputEncoding in the dict, the load()
        # default-0 fallback bounces the combo.
        from RBFtools import core
        cmds_mock = mock.MagicMock()
        cmds_mock.objExists.return_value = True
        cmds_mock.ls.return_value = ["RBF1Shape"]
        cmds_mock.listRelatives.return_value = ["RBF1Shape"]
        cmds_mock.nodeType.return_value = "RBFtools"

        def _safe_get(plug, default=None):
            # Stub safe_get path via attribute query — the real
            # safe_get wraps cmds.getAttr; we patch it directly
            # below for clarity.
            return default

        # Stub all the readers the dict relies on.
        with mock.patch.object(core, "cmds", cmds_mock):
            with mock.patch.object(
                    core, "safe_get",
                    side_effect=lambda plug, default=None: (
                        4 if plug.endswith(".inputEncoding")
                        else default)):
                with mock.patch.object(
                        core, "read_driver_rotate_orders",
                        return_value=[2, 0]):
                    with mock.patch.object(
                            core, "read_quat_group_starts",
                            return_value=[]):
                        data = core.get_all_settings("RBF1")
        self.assertIsNotNone(data)
        self.assertEqual(data.get("inputEncoding"), 4,
            "get_all_settings MUST return the inputEncoding "
            "value read from the shape — NOT fall through to a "
            "data.get(<key>, 0) default downstream.")
        # The 7 fields land as keys.
        for key in _REQUIRED_GET_ALL_SETTINGS_FIELDS:
            self.assertIn(
                key, data,
                "get_all_settings dict MUST carry {!r} key — "
                "Bug 1 / latent node-switch bug closure.".format(
                    key))

    # ------------------------------------------------------------------
    # Bug 1 — controller slot does NOT round-trip through
    # _load_settings; emits narrow signal instead.
    # ------------------------------------------------------------------

    def test_slot_does_not_call_load_settings(self):
        from RBFtools import core
        from RBFtools.controller import MainController
        ctrl = MainController.__new__(MainController)
        ctrl._current_node = "RBF1"
        # If anything still calls _load_settings, this MagicMock
        # captures it and the assertion below catches it.
        ctrl._load_settings = mock.MagicMock()
        ctrl.rotateOrderEditorReload = mock.MagicMock()
        ctrl.driverSourcesChanged = mock.MagicMock()
        with mock.patch.object(
                core, "auto_resolve_generic_rotate_orders"):
            with mock.patch.object(
                    core, "read_driver_rotate_orders",
                    return_value=[1]):
                MainController.on_input_encoding_changed(ctrl, 4)
        ctrl._load_settings.assert_not_called()
        ctrl.rotateOrderEditorReload.emit.assert_called_once_with(
            [1])

    def test_slot_passes_freshly_read_values_through_signal(self):
        # The signal payload MUST be the post-auto-derive read of
        # driverInputRotateOrder, not a stale snapshot.
        from RBFtools import core
        from RBFtools.controller import MainController
        ctrl = MainController.__new__(MainController)
        ctrl._current_node = "RBF1"
        ctrl.rotateOrderEditorReload = mock.MagicMock()
        ctrl.driverSourcesChanged = mock.MagicMock()
        # Simulate auto_resolve writing 3 sources, then read-back
        # giving [0, 5, 2].
        with mock.patch.object(
                core, "auto_resolve_generic_rotate_orders"):
            with mock.patch.object(
                    core, "read_driver_rotate_orders",
                    return_value=[0, 5, 2]):
                MainController.on_input_encoding_changed(ctrl, 3)
        ctrl.rotateOrderEditorReload.emit.assert_called_once_with(
            [0, 5, 2])

    # ------------------------------------------------------------------
    # Hardening 3 — 3-node-switch combo persistence smoke test.
    # ------------------------------------------------------------------

    def test_three_node_switch_each_loads_correct_input_encoding(self):
        # Simulates the user-reported latent bug: 3 nodes carrying
        # different inputEncoding values, navigated A -> B -> A.
        # With the 7-field fix, each load() sees the right value
        # and setCurrentIndex matches the stored attr.
        from RBFtools import core
        per_node_enc = {
            "nodeA": 4,    # SwingTwist
            "nodeB": 2,    # BendRoll
        }

        def _safe_get(plug, default=None):
            for node_name, enc in per_node_enc.items():
                if plug.startswith(node_name) and \
                        plug.endswith(".inputEncoding"):
                    return enc
            return default

        cmds_mock = mock.MagicMock()
        cmds_mock.objExists.return_value = True
        cmds_mock.ls.side_effect = lambda *a, **k: \
            [a[0] + "Shape"] if a else []
        cmds_mock.listRelatives.side_effect = lambda *a, **k: \
            [a[0] + "Shape"] if a else []
        cmds_mock.nodeType.return_value = "RBFtools"

        sequence = ["nodeA", "nodeB", "nodeA"]
        captured = []
        with mock.patch.object(core, "cmds", cmds_mock):
            with mock.patch.object(
                    core, "safe_get", side_effect=_safe_get):
                with mock.patch.object(
                        core, "read_driver_rotate_orders",
                        return_value=[]):
                    with mock.patch.object(
                            core, "read_quat_group_starts",
                            return_value=[]):
                        for node_name in sequence:
                            data = core.get_all_settings(node_name)
                            captured.append(data["inputEncoding"])
        self.assertEqual(
            captured, [4, 2, 4],
            "3-node switch MUST round-trip the per-node "
            "inputEncoding without bouncing — got {}.".format(
                captured))

    # ------------------------------------------------------------------
    # Bug 2 — ComboHelpButton key dispatch.
    # ------------------------------------------------------------------

    def test_combohelpbutton_resolves_per_index(self):
        # The ComboHelpButton._help_key_for_index branch is the
        # exact path the user clicks reach. Build a stub combo
        # exposing only what ComboHelpButton needs.
        from RBFtools.ui.widgets.help_button import ComboHelpButton
        combo_stub = mock.MagicMock()
        combo_stub.currentIndex.return_value = 0
        # ComboHelpButton.__init__ wires currentIndexChanged +
        # highlighted; the MagicMock auto-supplies signal-like
        # attrs so .connect is a no-op stub.
        btn = ComboHelpButton.__new__(ComboHelpButton)
        btn._combo = combo_stub
        btn._key_map = list(_NEW_OUTPUT_ENC_KEYS)
        btn._fallback_key = "output_encoding"
        btn._help_key = "output_encoding"
        # Per-index resolution.
        for idx, expected in enumerate(_NEW_OUTPUT_ENC_KEYS):
            self.assertEqual(
                btn._help_key_for_index(idx), expected,
                "ComboHelpButton index {} should resolve to "
                "{!r} not {!r}".format(
                    idx, expected, btn._help_key_for_index(idx)))
        # Out-of-range falls back.
        self.assertEqual(
            btn._help_key_for_index(99),
            "output_encoding",
            "Out-of-range MUST fall back to fallback_key.")

    def test_each_output_enc_key_has_paragraph_break(self):
        # Spec E.1 multi-paragraph contract.
        from RBFtools.ui.help_texts import _EN
        for key in _NEW_OUTPUT_ENC_KEYS:
            self.assertIn(
                "\n\n", _EN[key],
                "_EN[{!r}] missing paragraph break — bubble "
                "would render as a single wall of text.".format(
                    key))


if __name__ == "__main__":
    unittest.main()
