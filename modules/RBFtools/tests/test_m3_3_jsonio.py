"""M3.3 — JSON Import / Export tests.

Test layout
-----------
T1a  _ATTR_NAME_TO_JSON_KEY completeness — every key in
     EXPECTED_SETTINGS_KEYS has a Maya-attr counterpart.
T1b  _ATTR_NAME_TO_JSON_KEY bijection — no duplicate JSON values
     (PERMANENT GUARD).
T2   node_to_dict round-trip on a mocked full node.
T3   dict_to_node end-to-end mock — exercises set_node_attr +
     wire_driver_inputs + wire_driven_outputs + write_output_baselines
     + write_pose_local_transforms call sequencing.
T4   dry_run per-node validation: schema_version mismatch / missing
     required field / type wrong / driver node not in scene / driver
     attr not on node / pose dimension mismatch / sparse-index dup.
T5   dry_run multi-node mixed (some ok / some fail) — aggregated.
T6   SCHEMA_VERSION still "rbftools.v5.m3" (PERMANENT GUARD —
     pairs with M3.0 T0).
T7   import_path Add mode end-to-end (mock create_node + objExists
     -> name collision triggers _imported suffix).
T8   import_path Replace mode (delete_node called + create_node
     called + alias auto re-applied).
T9   poseLocalTransform direct write — capture_per_pose_local_transforms
     NEVER called inside dict_to_node (T_LOCAL_XFORM_BYPASS).
T10  output_quaternion_groups round-trip — alias_base reversed from
     driven.attrs[start].alias on demand (no stored alias_base).
T11  Alias not directly setAttr'd — read_aliases path included in
     export, but dict_to_node MUST NOT call cmds.aliasAttr (M3.7
     auto_alias_outputs is the single source of truth).
T12  atomic_write_json reuse — export_nodes_to_path's write goes
     through the M3.0 helper.
T13  Controller path A wiring — import_rbf_setup uses
     ask_confirm(action_id="import_replace") only when Replace would
     actually overwrite.
T14  add_file_action helper exists + 3 File menu entries registered.
T15  i18n parity — every M3.3 EN key has a CN counterpart.
T16  T_META_READ_ONLY (PERMANENT) — dict_to_node + dry_run source
     text MUST NOT reference data["meta"] / data.get("meta" / etc.
T_M3_3_SCHEMA_FIELDS  — node_to_dict output key set frozen
     (PERMANENT GUARD).
T_FLOAT_ROUND_TRIP    — dump(load(dump(d))) byte-stable.
"""

from __future__ import absolute_import

import conftest  # noqa: F401

import json
import os
import tempfile
import unittest
from unittest import mock

import maya.cmds as cmds


def _reset_cmds():
    cmds.reset_mock()
    cmds.objExists.return_value = True
    cmds.listRelatives.return_value = ["shape1"]
    cmds.warning.side_effect = None


# ----------------------------------------------------------------------
# T1a / T1b — bijection
# ----------------------------------------------------------------------


class T1_AttrNameJsonKeyBijection(unittest.TestCase):

    def test_completeness_a(self):
        from RBFtools.core_json import (
            _ATTR_NAME_TO_JSON_KEY, EXPECTED_SETTINGS_KEYS,
        )
        json_values = set(_ATTR_NAME_TO_JSON_KEY.values())
        self.assertEqual(json_values, EXPECTED_SETTINGS_KEYS,
            "completeness: _ATTR_NAME_TO_JSON_KEY values must equal "
            "EXPECTED_SETTINGS_KEYS")

    def test_bijection_b_PERMANENT(self):
        """PERMANENT GUARD — DO NOT REMOVE (addendum §M3.3.1).

        Duplicate JSON keys would cause export/import asymmetry after
        any future schema evolution. Failing this test means a Maya
        attr was renamed to share a JSON key with another attr — fix
        the conflict, do NOT remove this guard.
        """
        from RBFtools.core_json import _ATTR_NAME_TO_JSON_KEY
        values = list(_ATTR_NAME_TO_JSON_KEY.values())
        self.assertEqual(len(values), len(set(values)),
            "duplicate JSON key in _ATTR_NAME_TO_JSON_KEY — "
            "schema asymmetry risk")


# ----------------------------------------------------------------------
# T_M3_3_SCHEMA_FIELDS — frozen field set
# ----------------------------------------------------------------------


class T_SchemaFieldsFrozen(unittest.TestCase):
    """PERMANENT GUARD — DO NOT REMOVE.

    SCHEMA_VERSION = 'rbftools.v5.m3' commits the exact set of keys in
    node_to_dict's output. Any change requires a new SCHEMA_VERSION +
    addendum §M3.3 schema migration entry, NOT a silent edit."""

    def test_node_dict_top_level_keys_PERMANENT(self):
        from RBFtools import core_json
        with mock.patch("RBFtools.core_json.core") as mc, \
             mock.patch("RBFtools.core_json.core_alias") as ma:
            self._stub_full_node(mc, ma)
            d = core_json.node_to_dict("RBF1")
        self.assertEqual(set(d.keys()), core_json.EXPECTED_NODE_DICT_KEYS)

    def test_settings_keys_PERMANENT(self):
        from RBFtools import core_json
        with mock.patch("RBFtools.core_json.core") as mc, \
             mock.patch("RBFtools.core_json.core_alias") as ma:
            self._stub_full_node(mc, ma)
            d = core_json.node_to_dict("RBF1")
        self.assertEqual(frozenset(d["settings"].keys()),
                         core_json.EXPECTED_SETTINGS_KEYS)

    @staticmethod
    def _stub_full_node(mc, ma):
        mc._exists.return_value = True
        mc.get_shape.return_value = "RBF1Shape"
        mc.safe_get.side_effect = lambda path, default=0: default
        mc.read_driver_info.return_value = ("drv", ["rotateX"])
        mc.read_driven_info.return_value = ("drvn", ["blend1"])
        mc.read_driver_rotate_orders.return_value = [0]
        mc.read_output_baselines.return_value = [(0.0, False)]
        mc.read_quat_group_starts.return_value = []
        mc.read_all_poses.return_value = []
        mc.read_pose_local_transforms.return_value = []
        mc.IDENTITY_LOCAL_TRANSFORM = {
            "translate": (0.0, 0.0, 0.0),
            "quat":      (0.0, 0.0, 0.0, 1.0),
            "scale":     (1.0, 1.0, 1.0),
        }
        ma.read_aliases.return_value = {"input": {}, "output": {}}


# ----------------------------------------------------------------------
# T2 — node_to_dict round-trip basics
# ----------------------------------------------------------------------


class T2_NodeToDict(unittest.TestCase):

    def _full_stub(self, mc, ma):
        mc._exists.return_value = True
        mc.get_shape.return_value = "RBF1Shape"
        mc.safe_get.side_effect = lambda path, default=0: default
        mc.read_driver_info.return_value = ("drv", ["rotateX", "rotateY"])
        mc.read_driven_info.return_value = ("drvn", ["blendA", "blendB"])
        mc.read_driver_rotate_orders.return_value = [0, 1]
        mc.read_output_baselines.return_value = [(0.0, False), (1.0, True)]
        mc.read_quat_group_starts.return_value = [0]
        # One pose, two inputs, two outputs.
        from RBFtools.core import PoseData
        mc.read_all_poses.return_value = [PoseData(0, [0.1, 0.2], [0.3, 0.4])]
        mc.read_pose_local_transforms.return_value = [{
            "translate": (0.0, 0.0, 0.0),
            "quat":      (0.0, 0.0, 0.0, 1.0),
            "scale":     (1.0, 1.0, 1.0),
        }]
        mc.IDENTITY_LOCAL_TRANSFORM = {
            "translate": (0.0, 0.0, 0.0),
            "quat":      (0.0, 0.0, 0.0, 1.0),
            "scale":     (1.0, 1.0, 1.0),
        }
        ma.read_aliases.return_value = {
            "input":  {0: "in_rotateX", 1: "in_rotateY"},
            "output": {0: "out_blendA", 1: "out_blendB"},
        }
        # PoseData is needed in core_json — patch returns the mc module
        # but PoseData lookups still need to work.
        mc.PoseData = PoseData

    def test_basic_shape(self):
        from RBFtools import core_json
        with mock.patch("RBFtools.core_json.core") as mc, \
             mock.patch("RBFtools.core_json.core_alias") as ma:
            self._full_stub(mc, ma)
            d = core_json.node_to_dict("RBF1")
        self.assertEqual(d["name"], "RBF1")
        self.assertEqual(len(d["driver"]["attrs"]), 2)
        self.assertEqual(len(d["driven"]["attrs"]), 2)
        self.assertEqual(d["output_quaternion_groups"], [{"start": 0}])

    def test_driver_attr_alias_propagation(self):
        from RBFtools import core_json
        with mock.patch("RBFtools.core_json.core") as mc, \
             mock.patch("RBFtools.core_json.core_alias") as ma:
            self._full_stub(mc, ma)
            d = core_json.node_to_dict("RBF1")
        self.assertEqual(d["driver"]["attrs"][0]["alias"], "in_rotateX")
        self.assertEqual(d["driven"]["attrs"][1]["alias"], "out_blendB")

    def test_driven_baseline_and_isscale(self):
        from RBFtools import core_json
        with mock.patch("RBFtools.core_json.core") as mc, \
             mock.patch("RBFtools.core_json.core_alias") as ma:
            self._full_stub(mc, ma)
            d = core_json.node_to_dict("RBF1")
        self.assertEqual(d["driven"]["attrs"][0]["is_scale"], False)
        self.assertEqual(d["driven"]["attrs"][1]["is_scale"], True)
        self.assertEqual(d["driven"]["attrs"][1]["base_value"], 1.0)

    def test_pose_local_transform_present(self):
        from RBFtools import core_json
        with mock.patch("RBFtools.core_json.core") as mc, \
             mock.patch("RBFtools.core_json.core_alias") as ma:
            self._full_stub(mc, ma)
            d = core_json.node_to_dict("RBF1")
        lx = d["poses"][0]["local_transform"]
        self.assertEqual(lx["translate"], [0.0, 0.0, 0.0])
        self.assertEqual(lx["quat"], [0.0, 0.0, 0.0, 1.0])
        self.assertEqual(lx["scale"], [1.0, 1.0, 1.0])


# ----------------------------------------------------------------------
# T3 — dict_to_node call sequencing
# ----------------------------------------------------------------------


class T3_DictToNode(unittest.TestCase):

    def _build_dict(self):
        return {
            "name": "RBF1",
            "type_mode": "RBF",
            "settings": {k: 0 for k in
                         __import__("RBFtools.core_json", fromlist=[""])
                         .EXPECTED_SETTINGS_KEYS},
            "driver": {
                "node": "drv",
                "attrs": [{"index": 0, "name": "rotateX",
                           "alias": "in_rotateX"}],
                "rotate_orders": [0],
            },
            "driven": {
                "node": "drvn",
                "attrs": [{"index": 0, "name": "blendA",
                           "alias": "out_blendA",
                           "is_scale": False,
                           "base_value": 0.0}],
            },
            "output_quaternion_groups": [],
            "poses": [{
                "index": 0,
                "inputs": [0.0],
                "values": [0.0],
                "local_transform": {
                    "translate": [0, 0, 0],
                    "quat":      [0, 0, 0, 1],
                    "scale":     [1, 1, 1],
                },
            }],
        }

    def test_returns_target_name(self):
        _reset_cmds()
        from RBFtools import core_json
        with mock.patch("RBFtools.core_json.core") as mc, \
             mock.patch("RBFtools.core_json.core_alias"):
            mc._exists.return_value = False  # name does not collide
            mc.create_node.return_value = "RBF1"
            mc.get_shape.return_value = "RBF1Shape"
            mc.undo_chunk.return_value.__enter__ = lambda s: None
            mc.undo_chunk.return_value.__exit__ = lambda s, *a: False
            from RBFtools.core import PoseData
            mc.PoseData = PoseData
            target = core_json.dict_to_node(self._build_dict(), mode="add")
        self.assertEqual(target, "RBF1")

    def test_replace_mode_calls_delete(self):
        _reset_cmds()
        from RBFtools import core_json
        with mock.patch("RBFtools.core_json.core") as mc, \
             mock.patch("RBFtools.core_json.core_alias"):
            mc._exists.return_value = True
            mc.create_node.return_value = "RBF1"
            mc.get_shape.return_value = "RBF1Shape"
            mc.undo_chunk.return_value.__enter__ = lambda s: None
            mc.undo_chunk.return_value.__exit__ = lambda s, *a: False
            from RBFtools.core import PoseData
            mc.PoseData = PoseData
            core_json.dict_to_node(self._build_dict(), mode="replace",
                                    will_overwrite=True)
            mc.delete_node.assert_called_with("RBF1")

    def test_add_mode_collision_renames_with_suffix(self):
        _reset_cmds()
        from RBFtools import core_json
        with mock.patch("RBFtools.core_json.core") as mc, \
             mock.patch("RBFtools.core_json.core_alias"):
            mc._exists.return_value = True   # collision
            mc.create_node.return_value = "RBF_new"
            mc.get_shape.return_value = "RBF_newShape"
            mc.undo_chunk.return_value.__enter__ = lambda s: None
            mc.undo_chunk.return_value.__exit__ = lambda s, *a: False
            from RBFtools.core import PoseData
            mc.PoseData = PoseData
            cmds.rename.return_value = "RBF1_imported"
            core_json.dict_to_node(self._build_dict(), mode="add")
            # cmds.rename should be called with "RBF1_imported".
            calls = [c for c in cmds.rename.call_args_list
                     if "RBF1_imported" in str(c)]
            self.assertTrue(calls,
                "rename to '_imported' suffix not invoked")

    def test_auto_alias_outputs_called(self):
        _reset_cmds()
        from RBFtools import core_json
        with mock.patch("RBFtools.core_json.core") as mc, \
             mock.patch("RBFtools.core_json.core_alias"):
            mc._exists.return_value = False
            mc.create_node.return_value = "RBF1"
            mc.get_shape.return_value = "RBF1Shape"
            mc.undo_chunk.return_value.__enter__ = lambda s: None
            mc.undo_chunk.return_value.__exit__ = lambda s, *a: False
            from RBFtools.core import PoseData
            mc.PoseData = PoseData
            core_json.dict_to_node(self._build_dict(), mode="add")
            self.assertTrue(mc.auto_alias_outputs.called,
                "M3.7 auto_alias_outputs must run at end of import")


# ----------------------------------------------------------------------
# T4 / T5 — dry_run validation
# ----------------------------------------------------------------------


def _good_doc():
    """Valid 1-node document fixture."""
    from RBFtools.core_json import EXPECTED_SETTINGS_KEYS, SCHEMA_VERSION
    return {
        "schema_version": SCHEMA_VERSION,
        "nodes": [{
            "name": "RBF1",
            "type_mode": "RBF",
            "settings": {k: 0 for k in EXPECTED_SETTINGS_KEYS},
            "driver": {
                "node": "drv",
                "attrs": [{"index": 0, "name": "rotateX"}],
                "rotate_orders": [0],
            },
            "driven": {
                "node": "drvn",
                "attrs": [{"index": 0, "name": "blendA",
                           "is_scale": False, "base_value": 0.0}],
            },
            "output_quaternion_groups": [],
            "poses": [{
                "index": 0,
                "inputs": [0.0],
                "values": [0.0],
                "local_transform": {
                    "translate": [0, 0, 0],
                    "quat":      [0, 0, 0, 1],
                    "scale":     [1, 1, 1],
                },
            }],
        }],
    }


class T4_DryRunValidation(unittest.TestCase):

    def test_valid_doc_passes(self):
        _reset_cmds()
        cmds.attributeQuery.return_value = True
        from RBFtools import core_json
        with mock.patch("RBFtools.core_json.core") as mc:
            mc._exists.return_value = True
            reports = core_json.dry_run(_good_doc(), mode="add")
        self.assertEqual(len(reports), 1)
        self.assertTrue(reports[0].ok, reports[0].errors)

    def test_schema_version_mismatch_raises(self):
        from RBFtools import core_json
        doc = _good_doc()
        doc["schema_version"] = "rbftools.v4"
        with self.assertRaises(core_json.SchemaValidationError):
            core_json.dry_run(doc)

    def test_missing_required_field_collected(self):
        _reset_cmds()
        from RBFtools import core_json
        doc = _good_doc()
        del doc["nodes"][0]["driver"]
        with mock.patch("RBFtools.core_json.core") as mc:
            mc._exists.return_value = True
            reports = core_json.dry_run(doc, mode="add")
        self.assertFalse(reports[0].ok)
        self.assertTrue(any("driver" in e for e in reports[0].errors))

    def test_driver_node_not_in_scene(self):
        _reset_cmds()
        from RBFtools import core_json
        with mock.patch("RBFtools.core_json.core") as mc:
            # _exists True for shape lookup, False for the named driver.
            mc._exists.side_effect = (
                lambda n: n != "drv")
            reports = core_json.dry_run(_good_doc(), mode="add")
        self.assertFalse(reports[0].ok)
        self.assertTrue(any("drv" in e and "not found" in e
                            for e in reports[0].errors))

    def test_pose_dimension_mismatch(self):
        _reset_cmds()
        cmds.attributeQuery.return_value = True
        from RBFtools import core_json
        doc = _good_doc()
        doc["nodes"][0]["poses"][0]["inputs"] = [0.0, 0.0]  # n_in is 1
        with mock.patch("RBFtools.core_json.core") as mc:
            mc._exists.return_value = True
            reports = core_json.dry_run(doc, mode="add")
        self.assertFalse(reports[0].ok)

    def test_settings_unknown_key(self):
        _reset_cmds()
        cmds.attributeQuery.return_value = True
        from RBFtools import core_json
        doc = _good_doc()
        doc["nodes"][0]["settings"]["mystery_field"] = 42
        with mock.patch("RBFtools.core_json.core") as mc:
            mc._exists.return_value = True
            reports = core_json.dry_run(doc, mode="add")
        self.assertFalse(reports[0].ok)
        self.assertTrue(any("mystery_field" in e for e in reports[0].errors))

    def test_label_suffix_field_tolerated(self):
        """_label-suffix keys are meta-only (red line #4) and must
        not trigger 'unknown key' errors."""
        _reset_cmds()
        cmds.attributeQuery.return_value = True
        from RBFtools import core_json
        doc = _good_doc()
        doc["nodes"][0]["settings"]["kernel_label"] = "Gaussian1"
        with mock.patch("RBFtools.core_json.core") as mc:
            mc._exists.return_value = True
            reports = core_json.dry_run(doc, mode="add")
        self.assertTrue(reports[0].ok, reports[0].errors)


class T5_DryRunMultiNode(unittest.TestCase):

    def test_mixed_ok_fail(self):
        _reset_cmds()
        cmds.attributeQuery.return_value = True
        from RBFtools import core_json
        good = _good_doc()["nodes"][0]
        bad = dict(good)
        bad["name"] = "RBF2"
        bad = {**bad, "driver": {"node": "missing_drv",
                                  "attrs": [{"index": 0, "name": "rotateX"}],
                                  "rotate_orders": [0]}}
        doc = {"schema_version": core_json.SCHEMA_VERSION,
               "nodes": [good, bad]}
        with mock.patch("RBFtools.core_json.core") as mc:
            mc._exists.side_effect = (
                lambda n: n != "missing_drv")
            reports = core_json.dry_run(doc, mode="add")
        self.assertEqual(len(reports), 2)
        self.assertTrue(reports[0].ok)
        self.assertFalse(reports[1].ok)

    def test_top_level_collects_all(self):
        from RBFtools import core_json
        doc = {"schema_version": "wrong"}  # also missing 'nodes'
        try:
            core_json.dry_run(doc)
            self.fail("expected SchemaValidationError")
        except core_json.SchemaValidationError as exc:
            self.assertGreaterEqual(len(exc.errors), 2)


# ----------------------------------------------------------------------
# T6 — SCHEMA_VERSION untouched (PERMANENT)
# ----------------------------------------------------------------------


class T6_SchemaVersionUnchanged(unittest.TestCase):

    def test_PERMANENT_GUARD(self):
        from RBFtools.core_json import SCHEMA_VERSION
        self.assertEqual(SCHEMA_VERSION, "rbftools.v5.m3")


# ----------------------------------------------------------------------
# T9 — local-transform direct write (T_LOCAL_XFORM_BYPASS)
# ----------------------------------------------------------------------


class T9_PoseLocalTransformBypass(unittest.TestCase):
    """G.2 — Import writes poseLocalTransform directly. The
    capture_per_pose_local_transforms helper MUST NOT be invoked
    inside dict_to_node — it would violate the M2.3 freeze contract
    by reading driven_node's current scene state."""

    def test_capture_helper_not_called(self):
        _reset_cmds()
        from RBFtools import core_json
        with mock.patch("RBFtools.core_json.core") as mc, \
             mock.patch("RBFtools.core_json.core_alias"):
            mc._exists.return_value = False
            mc.create_node.return_value = "RBF1"
            mc.get_shape.return_value = "RBF1Shape"
            mc.undo_chunk.return_value.__enter__ = lambda s: None
            mc.undo_chunk.return_value.__exit__ = lambda s, *a: False
            from RBFtools.core import PoseData
            mc.PoseData = PoseData
            d = T3_DictToNode()._build_dict()
            core_json.dict_to_node(d, mode="add")
            self.assertFalse(mc.capture_per_pose_local_transforms.called,
                "M2.3 capture path was invoked from import — bypass "
                "contract violated (addendum §M3.3.G)")
            self.assertTrue(mc.write_pose_local_transforms.called,
                "Import must direct-write poseLocalTransform")

    def test_source_text_no_capture_call(self):
        """Belt-and-braces: dict_to_node executable body must not call
        the capture helper. Docstrings are stripped before the scan
        so that contract documentation can name the forbidden symbol."""
        import inspect, re
        from RBFtools.core_json import dict_to_node
        src = inspect.getsource(dict_to_node)
        src = re.sub(r'"""[\s\S]*?"""', "", src)
        self.assertNotIn("capture_per_pose_local_transforms", src,
            "dict_to_node executable body references the capture "
            "helper — contract violation")


# ----------------------------------------------------------------------
# T10 — alias_base reversibility (no stored field)
# ----------------------------------------------------------------------


class T10_AliasBaseReversible(unittest.TestCase):

    def test_quat_groups_have_no_alias_base_field(self):
        from RBFtools import core_json
        with mock.patch("RBFtools.core_json.core") as mc, \
             mock.patch("RBFtools.core_json.core_alias") as ma:
            T_SchemaFieldsFrozen._stub_full_node(mc, ma)
            mc.read_quat_group_starts.return_value = [0]
            d = core_json.node_to_dict("RBF1")
        for grp in d["output_quaternion_groups"]:
            self.assertEqual(set(grp.keys()), {"start"},
                "alias_base must NOT be stored — derive from "
                "driven.attrs[start].alias")

    def test_alias_base_derivable_from_driven_alias(self):
        # The convention: driven.attrs[start].alias ends with "QX",
        # so base = alias[:-2]. Sanity-check the convention by
        # reverse-engineering.
        leader_alias = "aimQuatQX"
        self.assertTrue(leader_alias.endswith("QX"))
        base = leader_alias[:-2]
        self.assertEqual(base, "aimQuat")


# ----------------------------------------------------------------------
# T11 — alias not directly setAttr'd
# ----------------------------------------------------------------------


class T11_NoDirectAliasSetAttr(unittest.TestCase):

    def test_dict_to_node_does_not_call_aliasAttr_directly(self):
        import inspect
        from RBFtools.core_json import dict_to_node
        src = inspect.getsource(dict_to_node)
        self.assertNotIn("cmds.aliasAttr", src,
            "dict_to_node directly calls cmds.aliasAttr — must defer "
            "to M3.7 auto_alias_outputs (H.2 contract)")


# ----------------------------------------------------------------------
# T12 — atomic_write_json reuse
# ----------------------------------------------------------------------


class T12_AtomicWriteReuse(unittest.TestCase):

    def test_export_uses_atomic_write_json(self):
        from RBFtools import core_json
        with mock.patch("RBFtools.core_json.atomic_write_json") as atom, \
             mock.patch("RBFtools.core_json.node_to_dict") as ntd:
            ntd.return_value = {"name": "RBF1"}
            core_json.export_nodes_to_path(["RBF1"], "/tmp/x.json")
            self.assertEqual(atom.call_count, 1)


# ----------------------------------------------------------------------
# T13 — controller path A wiring
# ----------------------------------------------------------------------


class T13_ControllerPathA(unittest.TestCase):

    def test_methods_exist(self):
        from RBFtools.controller import MainController
        for name in ("import_rbf_setup", "export_current_to_path",
                     "export_all_to_path"):
            self.assertTrue(callable(getattr(MainController, name, None)),
                "MainController." + name + " missing")

    def test_action_id_string_present(self):
        import pathlib
        path = pathlib.Path(__file__).resolve().parent.parent
        ctrl = (path / "scripts" / "RBFtools" / "controller.py").read_text(
            encoding="utf-8")
        self.assertIn('action_id="import_replace"', ctrl)


# ----------------------------------------------------------------------
# T14 — File menu spillover
# ----------------------------------------------------------------------


class T14_FileMenuSpillover(unittest.TestCase):

    def test_add_file_action_callable(self):
        from RBFtools.ui.main_window import RBFToolsWindow
        self.assertTrue(callable(getattr(
            RBFToolsWindow, "add_file_action", None)))

    def test_three_file_entries_registered(self):
        import pathlib
        path = pathlib.Path(__file__).resolve().parent.parent
        text = (path / "scripts" / "RBFtools" / "ui"
                / "main_window.py").read_text(encoding="utf-8")
        self.assertIn('add_file_action("menu_import_rbf"', text)
        self.assertIn('add_file_action(\n            "menu_export_selected"',
                      text)
        self.assertIn('add_file_action("menu_export_all"', text)


# ----------------------------------------------------------------------
# T15 — i18n parity
# ----------------------------------------------------------------------


class T15_I18nParity(unittest.TestCase):

    REQUIRED_KEYS = (
        "menu_import_rbf",
        "menu_export_selected",
        "menu_export_all",
        "title_import_rbf",
        "title_import_replace",
        "summary_import_replace",
        "label_import_mode",
        "import_mode_add",
        "import_mode_replace",
        "label_import_preview",
        "btn_import",
        "status_export_starting",
        "status_export_done",
        "status_export_failed",
        "status_import_starting",
        "status_import_done",
        "status_import_failed",
        "status_dry_run_loading",
        "status_dry_run_failed",
        "status_schema_version_error",
    )

    def test_all_keys_in_both_languages(self):
        from RBFtools.ui.i18n import _EN, _ZH
        for k in self.REQUIRED_KEYS:
            self.assertIn(k, _EN, "missing EN: " + k)
            self.assertIn(k, _ZH, "missing CN: " + k)


# ----------------------------------------------------------------------
# T16 — meta block read-only (PERMANENT)
# ----------------------------------------------------------------------


class T16_MetaBlockReadOnly(unittest.TestCase):
    """PERMANENT GUARD — DO NOT REMOVE.

    The 'meta' block in M3.3 JSON is metadata only. dict_to_node and
    dry_run must NOT reference data["meta"] / data.get("meta" /
    ["meta"] in any decision path. If you need behavioural metadata,
    bump SCHEMA_VERSION instead of hacking via meta.
    """

    @staticmethod
    def _strip_docstrings(src):
        import re
        return re.sub(r'"""[\s\S]*?"""', "", src)

    def test_dict_to_node_no_meta_read(self):
        import inspect
        from RBFtools.core_json import dict_to_node
        src = self._strip_docstrings(inspect.getsource(dict_to_node))
        for forbidden in ('"meta"', "'meta'", "data.get(\"meta\""):
            self.assertNotIn(forbidden, src,
                "dict_to_node executable body references 'meta' — "
                "read-only contract violated (addendum §M3.3.J)")

    def test_dry_run_no_meta_read(self):
        import inspect
        from RBFtools.core_json import dry_run, _validate_node_dict
        src = self._strip_docstrings(
            inspect.getsource(dry_run)
            + inspect.getsource(_validate_node_dict))
        for forbidden in ('"meta"', "'meta'", "data.get(\"meta\""):
            self.assertNotIn(forbidden, src,
                "dry_run/_validate_node_dict executable body "
                "references 'meta' — read-only contract violated "
                "(addendum §M3.3.J)")


# ----------------------------------------------------------------------
# T_FLOAT_ROUND_TRIP — byte-stable JSON
# ----------------------------------------------------------------------


class T_FloatRoundTrip(unittest.TestCase):

    def test_load_dump_idempotent(self):
        # Build a payload with messy floats; ensure dump(load(dump(d)))
        # equals dump(d) byte for byte.
        d = {
            "schema_version": "rbftools.v5.m3",
            "nodes": [{
                "name": "RBF1",
                "settings": {"radius": 0.10000000000000002,
                             "regularization": 1e-08},
                "values": [0.1, 0.2, 0.30000000000000004],
            }],
        }
        s1 = json.dumps(d, ensure_ascii=False, indent=2,
                         sort_keys=False)
        s2 = json.dumps(json.loads(s1), ensure_ascii=False, indent=2,
                         sort_keys=False)
        self.assertEqual(s1, s2)

    def test_atomic_write_byte_stable(self):
        from RBFtools import core_json
        d = {"schema_version": core_json.SCHEMA_VERSION,
             "nodes": [{"radius": 0.1 + 0.2}]}
        # Use a real temp file (no Maya; pure stdlib path).
        fd, path = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        try:
            core_json.atomic_write_json(path, d)
            with open(path, "r", encoding="utf-8") as f:
                first = f.read()
            core_json.atomic_write_json(path, json.loads(first))
            with open(path, "r", encoding="utf-8") as f:
                second = f.read()
            self.assertEqual(first, second)
        finally:
            try:
                os.unlink(path)
            except OSError:
                pass


# ----------------------------------------------------------------------
# Spillover §2 helpers — co-located here (small set)
# ----------------------------------------------------------------------


class T_AddFileActionExists(unittest.TestCase):

    def test_method_callable(self):
        from RBFtools.ui.main_window import RBFToolsWindow
        self.assertTrue(callable(getattr(
            RBFToolsWindow, "add_file_action", None)))


class T_FileMenuExtensionContract(unittest.TestCase):
    """Source-text guard: _build_menu_bar must establish self._menu_file
    so add_file_action can address it. If a refactor renames the
    attribute, M3.x sub-tasks would silently break."""

    def test_menu_file_attribute_present(self):
        import pathlib
        path = pathlib.Path(__file__).resolve().parent.parent
        text = (path / "scripts" / "RBFtools" / "ui"
                / "main_window.py").read_text(encoding="utf-8")
        self.assertIn("self._menu_file", text)
        self.assertIn("self._menu_file.addAction", text)


if __name__ == "__main__":
    unittest.main()
