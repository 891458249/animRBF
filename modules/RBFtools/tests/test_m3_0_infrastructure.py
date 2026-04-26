"""M3.0 — Shared infrastructure tests.

T0   SCHEMA_VERSION immutability — PERMANENT GUARD
T1   should_show_confirm_dialog logic (default + skip-on + skip-off)
T2   CONFIRM_OPT_VAR_TEMPLATE name format matches addendum spec
T3   reset_all_skip_confirms iterates all matching optionVars
T4   atomic_write_json: tempfile staged, replaced atomically
T5   read_json_with_schema_check: pass on match, raise on mismatch
T6   select_rig_for_node: invalid role → warning, no crash
T7   StatusProgressController: begin / step / end state transitions
T8   i18n M3.0 keys present in EN + CN tables
"""

from __future__ import absolute_import

# Install Maya / PySide mocks BEFORE importing modules.
import conftest  # noqa: F401

import json
import os
import tempfile
import unittest
from unittest import mock

import maya.cmds as cmds


# ----------------------------------------------------------------------
# T0 — SCHEMA_VERSION immutability (PERMANENT GUARD)
# ----------------------------------------------------------------------


class T0_SchemaVersionImmutability(unittest.TestCase):
    """PERMANENT GUARD — DO NOT REMOVE OR MODIFY THIS TEST.

    If this test fails, you are about to break downstream engine
    compatibility. Read addendum §M3.0 Schema Version Immutability
    Contract before changing SCHEMA_VERSION.

    The contract has THREE layers (addendum §M3.0):
      1. Source comment in core_json.py
      2. This test
      3. The contract paragraph in addendum §M3.0

    Any future schema change MUST introduce a NEW version string and
    keep multi-version reader support. The existing string is locked.
    """

    def test_schema_version_unchanged_M3_0(self):
        from RBFtools.core_json import SCHEMA_VERSION
        self.assertEqual(
            SCHEMA_VERSION, "rbftools.v5.m3",
            "SCHEMA_VERSION changed — addendum §M3.0 contract violation. "
            "Schema evolution requires a NEW version string + multi-"
            "version reader, NOT mutation of the existing string.")


# ----------------------------------------------------------------------
# T1 — should_show_confirm_dialog logic
# ----------------------------------------------------------------------


def _reset_optionvar_mock():
    cmds.optionVar.reset_mock()
    cmds.optionVar.side_effect = None


class T1_ShouldShowConfirmDialog(unittest.TestCase):
    """A-class dual-path (M1.5.1): pure-Python uses the conftest
    optionVar mock; mayapy exercises the real ``cmds.optionVar``
    via the session-scoped fixture. Each subtest asserts the SAME
    behaviour contract regardless of branch (加固 5)."""

    _ACTION = "test_m3_0_t1_action"
    _OPTVAR = "RBFtools_skip_confirm_test_m3_0_t1_action"

    def setUp(self):
        if conftest._REAL_MAYA:
            import _mayapy_fixtures
            _mayapy_fixtures.ensure_maya_standalone()
            # Clean slate — real cmds.optionVar persists across tests
            # within the standalone session, so we must explicitly
            # remove the var before each test.
            try:
                if cmds.optionVar(exists=self._OPTVAR):
                    cmds.optionVar(remove=self._OPTVAR)
            except Exception:
                pass
        else:
            _reset_optionvar_mock()

    def tearDown(self):
        if conftest._REAL_MAYA:
            try:
                if cmds.optionVar(exists=self._OPTVAR):
                    cmds.optionVar(remove=self._OPTVAR)
            except Exception:
                pass

    def test_default_shows_when_no_optionvar(self):
        from RBFtools import core
        # Behaviour contract: when the optionVar does not exist,
        # should_show_confirm_dialog returns True. Same assertion
        # under both branches (加固 5).
        if not conftest._REAL_MAYA:
            cmds.optionVar.side_effect = lambda **kw: (
                False if kw.get("exists") else 0)
        # else: setUp already ensured the var is absent.
        self.assertTrue(core.should_show_confirm_dialog(self._ACTION))

    def test_skip_when_optionvar_set_to_1(self):
        from RBFtools import core
        if conftest._REAL_MAYA:
            cmds.optionVar(intValue=(self._OPTVAR, 1))
        else:
            def fake_optionvar(**kw):
                if "exists" in kw:
                    return True
                if "query" in kw:
                    return 1
                return 0
            cmds.optionVar.side_effect = fake_optionvar
        # Same behaviour assertion under both branches.
        self.assertFalse(core.should_show_confirm_dialog(self._ACTION))

    def test_show_when_optionvar_set_to_0(self):
        from RBFtools import core
        if conftest._REAL_MAYA:
            cmds.optionVar(intValue=(self._OPTVAR, 0))
        else:
            def fake_optionvar(**kw):
                if "exists" in kw:
                    return True
                if "query" in kw:
                    return 0
                return 0
            cmds.optionVar.side_effect = fake_optionvar
        self.assertTrue(core.should_show_confirm_dialog(self._ACTION))


# ----------------------------------------------------------------------
# T2 — CONFIRM_OPT_VAR_TEMPLATE format
# ----------------------------------------------------------------------


class T2_OptionVarNamingContract(unittest.TestCase):
    """The optionVar key format is part of the addendum §M3.0 contract
    — downstream tooling (any reset utility, future M3 menu items)
    relies on the prefix to enumerate-and-clear via the iterator in
    reset_all_skip_confirms. Changing this template breaks them."""

    def test_template_format(self):
        from RBFtools.core import CONFIRM_OPT_VAR_TEMPLATE
        self.assertEqual(
            CONFIRM_OPT_VAR_TEMPLATE,
            "RBFtools_skip_confirm_{action_id}")

    def test_template_yields_expected_name(self):
        from RBFtools.core import CONFIRM_OPT_VAR_TEMPLATE
        self.assertEqual(
            CONFIRM_OPT_VAR_TEMPLATE.format(action_id="prune_poses"),
            "RBFtools_skip_confirm_prune_poses")


# ----------------------------------------------------------------------
# T3 — reset_all_skip_confirms iterates RBFtools_skip_confirm_* vars
# ----------------------------------------------------------------------


class T3_ResetAllSkipConfirms(unittest.TestCase):
    """A-class dual-path (M1.5.1). The behaviour contract is
    identical: reset_all_skip_confirms removes ONLY optionVars
    whose name starts with ``RBFtools_skip_confirm_``. Other
    RBFtools_* vars (filter state, language, auto-fill) survive.
    Same assertion shape across branches (加固 5)."""

    _T_PRUNE = "RBFtools_skip_confirm_test_m3_0_t3_prune"
    _T_MIRROR = "RBFtools_skip_confirm_test_m3_0_t3_mirror"
    _T_KEEP = "RBFtools_filter_driver_test_m3_0_t3_keep"

    def setUp(self):
        if conftest._REAL_MAYA:
            import _mayapy_fixtures
            _mayapy_fixtures.ensure_maya_standalone()
            for v in (self._T_PRUNE, self._T_MIRROR, self._T_KEEP):
                try:
                    if cmds.optionVar(exists=v):
                        cmds.optionVar(remove=v)
                except Exception:
                    pass
        else:
            _reset_optionvar_mock()

    def tearDown(self):
        if conftest._REAL_MAYA:
            for v in (self._T_PRUNE, self._T_MIRROR, self._T_KEEP):
                try:
                    if cmds.optionVar(exists=v):
                        cmds.optionVar(remove=v)
                except Exception:
                    pass

    def test_removes_only_matching_prefix(self):
        from RBFtools import core
        if conftest._REAL_MAYA:
            # Plant three optionVars; reset_all_skip_confirms must
            # remove the two skip_confirm_ prefixed ones and leave
            # the unrelated _filter_driver_ var alone.
            cmds.optionVar(intValue=(self._T_PRUNE, 1))
            cmds.optionVar(intValue=(self._T_MIRROR, 1))
            cmds.optionVar(intValue=(self._T_KEEP, 1))
            core.reset_all_skip_confirms()
            # Behaviour assertion: the two prune/mirror vars are
            # gone; the unrelated keep var survives.
            self.assertFalse(cmds.optionVar(exists=self._T_PRUNE))
            self.assertFalse(cmds.optionVar(exists=self._T_MIRROR))
            self.assertTrue(cmds.optionVar(exists=self._T_KEEP))
        else:
            existing = [
                "RBFtools_skip_confirm_prune_poses",
                "RBFtools_skip_confirm_mirror_node",
                "RBFtools_filter_driver_Keyable",   # MUST NOT be removed
                "RBFtools_language",                 # MUST NOT be removed
                "RBFtoolsAutoFillValues",            # MUST NOT be removed
            ]
            removed = []

            def fake_optionvar(**kw):
                if kw.get("list"):
                    return existing
                if "remove" in kw:
                    removed.append(kw["remove"])
                    return None
                return None
            cmds.optionVar.side_effect = fake_optionvar

            core.reset_all_skip_confirms()
            self.assertEqual(
                sorted(removed),
                sorted([
                    "RBFtools_skip_confirm_prune_poses",
                    "RBFtools_skip_confirm_mirror_node",
                ]))


# ----------------------------------------------------------------------
# T4 — atomic_write_json
# ----------------------------------------------------------------------


class T4_AtomicWriteJson(unittest.TestCase):

    def test_write_then_read_roundtrip(self):
        from RBFtools.core_json import (
            SCHEMA_VERSION, atomic_write_json, read_json_with_schema_check,
        )
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "out.json")
            payload = {
                "schema_version": SCHEMA_VERSION,
                "node": "RBFnode1",
                "poses": [],
            }
            atomic_write_json(path, payload)
            self.assertTrue(os.path.exists(path))
            got = read_json_with_schema_check(path)
            self.assertEqual(got["node"], "RBFnode1")
            self.assertEqual(got["schema_version"], SCHEMA_VERSION)

    def test_write_replaces_existing(self):
        from RBFtools.core_json import (
            SCHEMA_VERSION, atomic_write_json,
        )
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "out.json")
            with open(path, "w", encoding="utf-8") as f:
                f.write('{"old": true}')
            atomic_write_json(path, {"schema_version": SCHEMA_VERSION,
                                     "node": "new"})
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.assertEqual(data.get("node"), "new")

    def test_write_does_not_leave_temp_files(self):
        """Atomic write must not litter .tmp files on success."""
        from RBFtools.core_json import (
            SCHEMA_VERSION, atomic_write_json,
        )
        with tempfile.TemporaryDirectory() as d:
            atomic_write_json(os.path.join(d, "x.json"),
                              {"schema_version": SCHEMA_VERSION})
            leftovers = [n for n in os.listdir(d) if n.endswith(".tmp")]
            self.assertEqual(leftovers, [])


# ----------------------------------------------------------------------
# T5 — read_json_with_schema_check
# ----------------------------------------------------------------------


class T5_ReadJsonSchemaCheck(unittest.TestCase):

    def test_match_returns_data(self):
        from RBFtools.core_json import (
            SCHEMA_VERSION, read_json_with_schema_check,
        )
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "ok.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump({"schema_version": SCHEMA_VERSION,
                           "data": 42}, f)
            data = read_json_with_schema_check(path)
            self.assertEqual(data["data"], 42)

    def test_mismatch_raises(self):
        from RBFtools.core_json import (
            SchemaVersionError, read_json_with_schema_check,
        )
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "bad.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump({"schema_version": "rbftools.v4",
                           "data": 1}, f)
            with self.assertRaises(SchemaVersionError):
                read_json_with_schema_check(path)

    def test_missing_field_raises(self):
        from RBFtools.core_json import (
            SchemaVersionError, read_json_with_schema_check,
        )
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "no_ver.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump({"data": 1}, f)
            with self.assertRaises(SchemaVersionError):
                read_json_with_schema_check(path)


# ----------------------------------------------------------------------
# T6 — select_rig_for_node defensive behaviour
# ----------------------------------------------------------------------


class T6_SelectRigForNode(unittest.TestCase):
    """A-class dual-path (M1.5.1). Behaviour contract: passing an
    invalid role string produces a warning and does NOT mutate
    the selection. Under mayapy we observe selection by reading
    ``cmds.ls(selection=True)``; under pure-Python we observe via
    mock call counts. Same final-state assertion: selection is
    empty / unchanged (加固 5)."""

    def setUp(self):
        if conftest._REAL_MAYA:
            import _mayapy_fixtures
            _mayapy_fixtures.ensure_maya_standalone()
            cmds.select(clear=True)
        else:
            _reset_optionvar_mock()
            cmds.warning.reset_mock()
            cmds.warning.side_effect = None
            cmds.select.reset_mock()
            cmds.select.side_effect = None

    def test_invalid_role_warns(self):
        from RBFtools import core
        if conftest._REAL_MAYA:
            # Pre-state: empty selection. Under real cmds, calling
            # select_rig_for_node with an invalid role should not
            # mutate the selection.
            core.select_rig_for_node("node1", "bogus")
            sel = cmds.ls(selection=True) or []
            self.assertEqual(sel, [],
                "invalid role mutated selection (real cmds path)")
        else:
            core.select_rig_for_node("node1", "bogus")
            self.assertGreaterEqual(cmds.warning.call_count, 1)
            # No selection attempt for invalid role.
            self.assertEqual(cmds.select.call_count, 0)


# ----------------------------------------------------------------------
# T7 — StatusProgressController state transitions
# ----------------------------------------------------------------------


class T7_StatusProgressController(unittest.TestCase):

    def test_begin_step_end_calls(self):
        from RBFtools.ui.main_window import StatusProgressController
        bar = mock.MagicMock(name="bar")
        label = mock.MagicMock(name="label")
        ctrl = StatusProgressController(bar, label)

        ctrl.begin("starting")
        bar.setRange.assert_called_with(0, 0)
        bar.setVisible.assert_called_with(True)
        label.setText.assert_called_with("starting")

        ctrl.step(3, 10, "step 3")
        bar.setRange.assert_called_with(0, 10)
        bar.setValue.assert_called_with(3)

        ctrl.end("done")
        bar.setVisible.assert_called_with(False)
        label.setText.assert_called_with("done")

    def test_end_with_empty_message_clears_label(self):
        from RBFtools.ui.main_window import StatusProgressController
        bar = mock.MagicMock(name="bar")
        label = mock.MagicMock(name="label")
        ctrl = StatusProgressController(bar, label)
        ctrl.end()
        label.setText.assert_called_with("")

    def test_step_clamps_zero_total_to_one(self):
        # Avoid a 0/0 division-style edge case in QProgressBar.
        from RBFtools.ui.main_window import StatusProgressController
        bar = mock.MagicMock(name="bar")
        label = mock.MagicMock(name="label")
        ctrl = StatusProgressController(bar, label)
        ctrl.step(0, 0)
        bar.setRange.assert_called_with(0, 1)


# ----------------------------------------------------------------------
# T8 — i18n M3.0 keys present
# ----------------------------------------------------------------------


class T8_i18nKeysM3_0(unittest.TestCase):

    M3_0_KEYS = [
        "menu_file", "menu_edit", "menu_tools", "menu_help",
        "menu_reset_confirms", "reset_confirms_done",
        "confirm_dont_ask", "ok", "cancel",
    ]

    def test_keys_present_in_both_tables(self):
        import pathlib
        path = pathlib.Path(__file__).resolve().parent.parent
        i18n_path = (path / "scripts" / "RBFtools" / "ui" / "i18n.py")
        text = i18n_path.read_text(encoding="utf-8")
        missing = []
        for key in self.M3_0_KEYS:
            needle = '"{}":'.format(key)
            count = text.count(needle)
            if count < 2:
                missing.append("{} (count={})".format(key, count))
        self.assertEqual(missing, [],
            "M3.0 i18n keys missing from EN or CN table:\n  "
            + "\n  ".join(missing))


if __name__ == "__main__":
    unittest.main()
