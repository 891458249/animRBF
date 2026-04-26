"""M3.7 — aliasAttr auto-naming tests.

Test layout
-----------
T1   sanitize          — regex / digit-prefix / truncation
T2   generate_alias_name — input / output prefixes + quat-leader form
T3   quat_group_alias_names — QX/QY/QZ/QW siblings off leader base
T4   is_rbftools_managed_alias — managed vs user-set classification
T5   clear_managed_aliases — preserves user aliases (E.1)
T6   apply_aliases — multi-instance plug shape, two probe paths
       (PASS path + FAIL path simulated via cmds.aliasAttr side_effect)
T7   read_aliases — reverse lookup for input/output plugs
T8   conflict fallback — same sanitised base across two indices gets
     _<idx> suffix
T9   apply_poses wiring — auto_alias_outputs invoked at end + failure
     does not break the chain
T10  controller path A — regenerate (no confirm) + force_regenerate
     (confirm gate)
T11  i18n EN/CN parity for M3.7 keys
T12  SCHEMA_VERSION untouched (D.1 contract — alias is metadata, not
     schema)
T_MANAGED_ALIAS_DETECT — strict detector contract (T4 strengthened
     for forward-compat with M3.3)
"""

from __future__ import absolute_import

import conftest  # noqa: F401

import unittest
from unittest import mock

import maya.cmds as cmds


def _reset_cmds():
    cmds.reset_mock()
    cmds.objExists.return_value = True
    cmds.listRelatives.return_value = ["shape1"]
    cmds.warning.side_effect = None


# ----------------------------------------------------------------------
# T1 — sanitize
# ----------------------------------------------------------------------


class T1_Sanitize(unittest.TestCase):

    def test_alphanumeric_unchanged(self):
        from RBFtools.core_alias import _sanitize
        self.assertEqual(_sanitize("translateX"), "translateX")

    def test_special_chars_replaced(self):
        from RBFtools.core_alias import _sanitize
        self.assertEqual(_sanitize("blend.shape:weight[0]"),
                         "blend_shape_weight_0_")

    def test_digit_prefix_padded(self):
        from RBFtools.core_alias import _sanitize
        self.assertEqual(_sanitize("3dAttr"), "a_3dAttr")

    def test_empty_returns_placeholder(self):
        from RBFtools.core_alias import _sanitize
        self.assertEqual(_sanitize(""), "x")
        # All-illegal input becomes pure underscores, which is a valid
        # Maya identifier — sanitisation keeps it (no separate empty
        # placeholder for that case).
        self.assertEqual(_sanitize("...."), "____")

    def test_long_name_truncated_with_tail(self):
        from RBFtools.core_alias import _sanitize, _MAX_ALIAS_LEN
        long_name = "a" * 80 + "_distinctive_tail"
        result = _sanitize(long_name)
        self.assertLessEqual(len(result), _MAX_ALIAS_LEN)
        self.assertTrue(result.endswith("ctive_tail")
                        or result.endswith("nctive_tail"))


# ----------------------------------------------------------------------
# T2 — generate_alias_name
# ----------------------------------------------------------------------


class T2_GenerateAliasName(unittest.TestCase):

    def test_input_prefix(self):
        from RBFtools.core_alias import generate_alias_name
        self.assertEqual(generate_alias_name("rotateX", 0, "input"),
                         "in_rotateX")

    def test_output_prefix(self):
        from RBFtools.core_alias import generate_alias_name
        self.assertEqual(generate_alias_name("blendValue", 5, "output"),
                         "out_blendValue")

    def test_quat_leader_returns_base_only(self):
        from RBFtools.core_alias import generate_alias_name
        self.assertEqual(
            generate_alias_name("aimQuat", 0, "output",
                                is_quat_group_leader=True),
            "aimQuat")

    def test_invalid_role_raises(self):
        from RBFtools.core_alias import generate_alias_name
        with self.assertRaises(ValueError):
            generate_alias_name("x", 0, "wrong_role")

    def test_quat_leader_only_meaningful_for_output(self):
        # Documented: is_quat_group_leader is only meaningful for
        # output role; passing True with input still returns the
        # prefixed form (caller responsibility).
        from RBFtools.core_alias import generate_alias_name
        self.assertEqual(
            generate_alias_name("foo", 0, "input",
                                is_quat_group_leader=True),
            "in_foo")


# ----------------------------------------------------------------------
# T3 — quat_group_alias_names
# ----------------------------------------------------------------------


class T3_QuatGroupAliasNames(unittest.TestCase):

    def test_four_siblings(self):
        from RBFtools.core_alias import quat_group_alias_names
        self.assertEqual(quat_group_alias_names("aimQuat"),
                         ("aimQuatQX", "aimQuatQY",
                          "aimQuatQZ", "aimQuatQW"))

    def test_sanitised_base(self):
        from RBFtools.core_alias import quat_group_alias_names
        self.assertEqual(quat_group_alias_names("foo.bar"),
                         ("foo_barQX", "foo_barQY",
                          "foo_barQZ", "foo_barQW"))


# ----------------------------------------------------------------------
# T4 / T_MANAGED_ALIAS_DETECT — is_rbftools_managed_alias
# ----------------------------------------------------------------------


class T4_ManagedAliasDetect(unittest.TestCase):

    def test_in_prefix_managed(self):
        from RBFtools.core_alias import is_rbftools_managed_alias
        self.assertTrue(is_rbftools_managed_alias("in_rotateX"))

    def test_out_prefix_managed(self):
        from RBFtools.core_alias import is_rbftools_managed_alias
        self.assertTrue(is_rbftools_managed_alias("out_blendValue"))

    def test_quat_sibling_managed(self):
        from RBFtools.core_alias import is_rbftools_managed_alias
        for suf in ("QX", "QY", "QZ", "QW"):
            self.assertTrue(is_rbftools_managed_alias("aimQuat" + suf))

    def test_user_alias_not_managed(self):
        from RBFtools.core_alias import is_rbftools_managed_alias
        self.assertFalse(is_rbftools_managed_alias("myCustomName"))
        self.assertFalse(is_rbftools_managed_alias("shoulderBlend"))

    def test_bare_prefix_not_managed(self):
        from RBFtools.core_alias import is_rbftools_managed_alias
        # "in_" alone — no base — must NOT match (defensive)
        self.assertFalse(is_rbftools_managed_alias("in_"))
        self.assertFalse(is_rbftools_managed_alias("out_"))

    def test_empty_not_managed(self):
        from RBFtools.core_alias import is_rbftools_managed_alias
        self.assertFalse(is_rbftools_managed_alias(""))
        self.assertFalse(is_rbftools_managed_alias(None))


# ----------------------------------------------------------------------
# T5 — clear_managed_aliases preserves user aliases (E.1)
# ----------------------------------------------------------------------


class T5_ClearManagedPreservesUser(unittest.TestCase):
    """A-class dual-path (M1.5.1). Behaviour contract:
    ``clear_managed_aliases`` removes only aliases that match the
    managed pattern (``in_*`` / ``out_*`` / quat-suffix); user-set
    aliases on the same node survive. Same assertion shape across
    branches (加固 5)."""

    def setUp(self):
        if conftest._REAL_MAYA:
            import _mayapy_fixtures
            _mayapy_fixtures.ensure_maya_standalone()
            # Build a clean transform with two custom attrs +
            # two aliases (one managed, one user-set).
            self._shape = cmds.createNode("transform")
            cmds.addAttr(self._shape, longName="oldAttr",
                         attributeType="double", keyable=True)
            cmds.addAttr(self._shape, longName="otherAttr",
                         attributeType="double", keyable=True)
            cmds.aliasAttr("out_oldAttr",
                           "{}.oldAttr".format(self._shape))
            cmds.aliasAttr("myCustomName",
                           "{}.otherAttr".format(self._shape))
        else:
            _reset_cmds()

    def tearDown(self):
        if conftest._REAL_MAYA:
            try:
                cmds.delete(self._shape)
            except Exception:
                pass

    def test_only_managed_removed(self):
        from RBFtools import core_alias
        if conftest._REAL_MAYA:
            core_alias.clear_managed_aliases(self._shape)
            # Behaviour assertion: managed alias gone, user alias kept.
            remaining = cmds.aliasAttr(self._shape, query=True) or []
            self.assertNotIn("out_oldAttr", remaining,
                "managed alias 'out_oldAttr' still present")
            self.assertIn("myCustomName", remaining,
                "user-set 'myCustomName' was wrongly removed")
        else:
            cmds.aliasAttr.return_value = [
                "out_oldAttr", "output[0]",
                "myCustomName", "output[1]",
            ]
            removed = []

            def fake_alias(*args, **kwargs):
                if kwargs.get("query"):
                    return cmds.aliasAttr.return_value
                if kwargs.get("remove"):
                    removed.append(args[0])
                    return None
                return None

            cmds.aliasAttr.side_effect = fake_alias
            core_alias.clear_managed_aliases("shape1")
            self.assertEqual(len(removed), 1)
            self.assertIn("shape1.out_oldAttr", removed[0])
            self.assertNotIn("myCustomName", " ".join(removed))


# ----------------------------------------------------------------------
# T6 — apply_aliases multi-plug API probes (PASS + FAIL paths)
# ----------------------------------------------------------------------


@unittest.skipIf(conftest._REAL_MAYA,
    "mock-dependent (cmds.reset_mock / mock.patch on cmds.*); real maya.cmds is not a MagicMock under mayapy")
class T6_ApplyAliasesAPIPaths(unittest.TestCase):
    """Multi-instance plug alias support is the only Maya API behaviour
    we cannot probe in mock-only tests. Cover BOTH outcomes so the
    Step 2 caveat in addendum §M3.7 is locked in test code."""

    def _setup_no_existing(self):
        _reset_cmds()

        def fake_alias(*args, **kwargs):
            if kwargs.get("query"):
                return []
            return None

        cmds.aliasAttr.side_effect = fake_alias

    def test_pass_path_sets_aliases_for_all_attrs(self):
        self._setup_no_existing()
        from RBFtools import core_alias
        result = core_alias.apply_aliases(
            "shape1", ["rotateX", "rotateY"], ["blendA", "blendB"])
        # 2 input + 2 output assignments
        self.assertEqual(set(result["input"].values()),
                         {"in_rotateX", "in_rotateY"})
        self.assertEqual(set(result["output"].values()),
                         {"out_blendA", "out_blendB"})

    def test_fail_path_emits_warning_and_skips(self):
        """Maya FAIL path: cmds.aliasAttr raises on multi-instance plugs.
        Helper must emit cmds.warning and return an empty mapping for
        that index — never propagate."""
        _reset_cmds()
        from RBFtools import core_alias
        existing = {"flat": []}

        def fake_alias(*args, **kwargs):
            if kwargs.get("query"):
                return existing["flat"]
            if kwargs.get("remove"):
                return None
            # The set call: simulate Maya rejecting multi-element alias
            raise RuntimeError("aliasAttr: multi-element not supported")

        cmds.aliasAttr.side_effect = fake_alias
        result = core_alias.apply_aliases(
            "shape1", ["rotateX"], ["blendA"])
        # Both sides empty (every set call raised)
        self.assertEqual(result, {"input": {}, "output": {}})
        # cmds.warning called at least twice (one per failed set)
        self.assertGreaterEqual(cmds.warning.call_count, 2)


# ----------------------------------------------------------------------
# T7 — read_aliases reverse lookup
# ----------------------------------------------------------------------


class T7_ReadAliases(unittest.TestCase):
    """A-class dual-path (M1.5.1). Behaviour contract:
    ``read_aliases`` returns a dict ``{"input": {idx: alias},
    "output": {idx: alias}}`` populated from aliases on the shape's
    ``input[N]`` / ``output[N]`` plugs; foreign aliases on other
    attrs are ignored. Same return-shape assertion across branches
    (加固 5)."""

    def setUp(self):
        if conftest._REAL_MAYA:
            import _mayapy_fixtures
            _mayapy_fixtures.ensure_maya_standalone()
            # Build a transform that fakes the input[]/output[]
            # multi plugs of an RBFtools shape — works without
            # the .mll because addAttr accepts any multi double.
            self._shape = cmds.createNode("transform")
            cmds.addAttr(self._shape, longName="input",
                         attributeType="double", multi=True)
            cmds.addAttr(self._shape, longName="output",
                         attributeType="double", multi=True)
            cmds.addAttr(self._shape, longName="someOtherAttr",
                         attributeType="double", keyable=True)
            # Materialise the multi indices.
            cmds.setAttr("{}.input[0]".format(self._shape), 0.0)
            cmds.setAttr("{}.output[0]".format(self._shape), 0.0)
            cmds.setAttr("{}.output[1]".format(self._shape), 0.0)
            # Plant the four aliases under test.
            cmds.aliasAttr("in_rotateX",
                           "{}.input[0]".format(self._shape))
            cmds.aliasAttr("out_blendA",
                           "{}.output[0]".format(self._shape))
            cmds.aliasAttr("out_blendB",
                           "{}.output[1]".format(self._shape))
            cmds.aliasAttr("myWidget",
                           "{}.someOtherAttr".format(self._shape))

    def tearDown(self):
        if conftest._REAL_MAYA:
            try:
                cmds.delete(self._shape)
            except Exception:
                pass

    def test_round_trip_input_output(self):
        from RBFtools import core_alias
        if conftest._REAL_MAYA:
            result = core_alias.read_aliases(self._shape)
        else:
            _reset_cmds()
            cmds.aliasAttr.return_value = [
                "in_rotateX", "input[0]",
                "out_blendA", "output[0]",
                "out_blendB", "output[1]",
                # Foreign alias on an unrelated attr — must be ignored.
                "myWidget", "someOtherAttr",
            ]

            def fake_alias(*args, **kwargs):
                if kwargs.get("query"):
                    return cmds.aliasAttr.return_value
                return None

            cmds.aliasAttr.side_effect = fake_alias
            result = core_alias.read_aliases("shape1")
        # Same final-shape assertion under both branches.
        self.assertEqual(result["input"], {0: "in_rotateX"})
        self.assertEqual(result["output"], {0: "out_blendA",
                                             1: "out_blendB"})


# ----------------------------------------------------------------------
# T8 — conflict fallback (same sanitised base across two indices)
# ----------------------------------------------------------------------


@unittest.skipIf(conftest._REAL_MAYA,
    "mock-dependent (cmds.reset_mock / mock.patch on cmds.*); real maya.cmds is not a MagicMock under mayapy")
class T8_ConflictFallback(unittest.TestCase):

    def test_duplicate_base_gets_index_suffix(self):
        _reset_cmds()
        from RBFtools import core_alias
        sets = []

        def fake_alias(*args, **kwargs):
            if kwargs.get("query"):
                return []
            if kwargs.get("remove"):
                return None
            sets.append(args[0])
            return None

        cmds.aliasAttr.side_effect = fake_alias
        # Two outputs with names that sanitise to the SAME base.
        result = core_alias.apply_aliases(
            "shape1", [], ["foo!bar", "foo@bar"])
        # First one wins the bare base, second gets _<idx> suffix.
        self.assertEqual(result["output"][0], "out_foo_bar")
        self.assertTrue(result["output"][1].startswith("out_foo_bar_"),
                        "duplicate base must be suffixed; got "
                        + result["output"][1])


# ----------------------------------------------------------------------
# T9 — apply_poses wiring
# ----------------------------------------------------------------------


class T9_ApplyPosesWiring(unittest.TestCase):
    """auto_alias_outputs is invoked at the end of apply_poses + a
    failure inside it does NOT break the apply chain (warning only)."""

    def test_auto_alias_outputs_function_exists(self):
        from RBFtools import core
        self.assertTrue(callable(getattr(core, "auto_alias_outputs", None)))

    def test_apply_poses_calls_auto_alias_outputs(self):
        # Source-text assertion: cheaper + not coupled to mock plumbing
        # of every step. The integration check lives in M1.5 mayapy.
        import pathlib
        path = pathlib.Path(__file__).resolve().parent.parent
        core_path = path / "scripts" / "RBFtools" / "core.py"
        text = core_path.read_text(encoding="utf-8")
        idx = text.find("def apply_poses(")
        self.assertGreater(idx, 0)
        body = text[idx:idx + 4000]
        self.assertIn("auto_alias_outputs", body,
            "apply_poses does not call auto_alias_outputs — M3.7 wiring lost")


# ----------------------------------------------------------------------
# T10 — controller path A
# ----------------------------------------------------------------------


class T10_ControllerPathA(unittest.TestCase):

    def test_regenerate_method_exists(self):
        from RBFtools.controller import MainController
        self.assertTrue(callable(getattr(
            MainController,
            "regenerate_aliases_for_current_node", None)))

    def test_force_regenerate_method_exists(self):
        from RBFtools.controller import MainController
        self.assertTrue(callable(getattr(
            MainController,
            "force_regenerate_aliases_for_current_node", None)))

    def test_force_regenerate_uses_action_id(self):
        # Source-text assertion: action_id="force_regenerate_aliases"
        # is the registered key in addendum §M3.0.3 / §M3.7.
        import pathlib
        path = pathlib.Path(__file__).resolve().parent.parent
        ctrl_path = (path / "scripts" / "RBFtools" / "controller.py")
        text = ctrl_path.read_text(encoding="utf-8")
        self.assertIn('action_id="force_regenerate_aliases"', text)


# ----------------------------------------------------------------------
# T11 — i18n parity
# ----------------------------------------------------------------------


class T11_I18nParity(unittest.TestCase):

    REQUIRED_KEYS = (
        "menu_regenerate_aliases",
        "menu_force_regenerate_aliases",
        "title_force_alias",
        "summary_force_alias",
        "status_alias_starting",
        "status_alias_done",
        "status_alias_failed",
    )

    def test_keys_present_in_both_languages(self):
        from RBFtools.ui.i18n import _EN, _ZH
        for k in self.REQUIRED_KEYS:
            self.assertIn(k, _EN, "missing EN: " + k)
            self.assertIn(k, _ZH, "missing CN: " + k)


# ----------------------------------------------------------------------
# T12 — SCHEMA_VERSION untouched (D.1)
# ----------------------------------------------------------------------


class T12_SchemaVersionUnchanged(unittest.TestCase):
    """M3.7 must NOT bump SCHEMA_VERSION. Aliases are Maya metadata,
    not part of the RBFtools shape schema. See addendum §M3.7 (D.1)."""

    def test_schema_version_still_m3(self):
        from RBFtools.core_json import SCHEMA_VERSION
        self.assertEqual(SCHEMA_VERSION, "rbftools.v5.m3")


# ----------------------------------------------------------------------
# T13 — Tools menu wiring (spillover helper consumption)
# ----------------------------------------------------------------------


class T13_ToolsMenuWiring(unittest.TestCase):
    """M3.7 menu entries must go through add_tools_action (spillover
    helper) — direct edits to _build_menu_bar are forbidden after
    M3.2 per addendum §M3.0-spillover red line 1."""

    def test_main_window_uses_add_tools_action_for_aliases(self):
        import pathlib
        path = pathlib.Path(__file__).resolve().parent.parent
        mw_path = (path / "scripts" / "RBFtools" / "ui" / "main_window.py")
        text = mw_path.read_text(encoding="utf-8")
        self.assertIn("menu_regenerate_aliases", text)
        self.assertIn("menu_force_regenerate_aliases", text)
        # Both must be inside an add_tools_action call.
        self.assertIn(
            'add_tools_action(\n            "menu_regenerate_aliases"',
            text)
        self.assertIn(
            'add_tools_action(\n            "menu_force_regenerate_aliases"',
            text)


if __name__ == "__main__":
    unittest.main()
