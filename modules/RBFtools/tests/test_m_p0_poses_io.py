# -*- coding: utf-8 -*-
"""T_M_P0_POSES_IO — defend the focused poses-only import / export
plumbing across core_json + controller + UI + i18n.

Feature context (M_P0_POSES_IO, 2026-05-10):
  User asked for a way to save / reload pose data on an existing
  rig during testing iteration without re-creating the whole node
  via the heavy full-schema export/import. The new path is:

    File menu → "Export Poses Only..." → JSON file at user path
    File menu → "Import Poses Only..." → load JSON, validate dims
                                          against current node, then
                                          replace OR append poses

JSON shape — POSES_SCHEMA_VERSION = "rbftools.poses.v1":
  {
    "schema_version": "rbftools.poses.v1",
    "exported_from": {
      "node":  <name>,
      "driver": {"node": <name>, "attrs": [<attr names>]},
      "driven": {"node": <name>, "attrs": [<attr names>]},
      "input_count":  <int>,
      "output_count": <int>,
      "n_poses":      <int>
    },
    "poses": [
      {"index": <int>, "inputs": [...], "values": [...], "radius": <float>},
      ...
    ]
  }

Validation rules on import (matched in this test as PERMANENT
structural assertions):

  HARD FAIL (raises PosesImportValidationError):
    - schema_version mismatch
    - input_count / output_count differ from current node
    - per-pose dim mismatch

  SOFT WARN (returned in result["warnings"]):
    - driver/driven node renames
    - driver/driven attr name changes (positional load proceeds)

This test pins the source-level invariants. Behavioural round-trip
(export -> file -> import on a different node) lives in the mayapy
E2E suite once the dual-runtime fixture supports it.
"""
from __future__ import absolute_import, division, print_function

import io
import os
import re
import unittest


_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(os.path.dirname(_HERE)))
_CORE_JSON = os.path.join(_REPO, "modules", "RBFtools", "scripts",
                           "RBFtools", "core_json.py")
_CONTROLLER = os.path.join(_REPO, "modules", "RBFtools", "scripts",
                            "RBFtools", "controller.py")
_MAIN_WINDOW = os.path.join(_REPO, "modules", "RBFtools", "scripts",
                             "RBFtools", "ui", "main_window.py")
_I18N = os.path.join(_REPO, "modules", "RBFtools", "scripts",
                     "RBFtools", "ui", "i18n.py")


def _read(path):
    with io.open(path, "r", encoding="utf-8") as fh:
        return fh.read()


class TestPosesIO(unittest.TestCase):

    # ----- core_json: schema constant -----

    def test_PERMANENT_a_poses_schema_version_constant(self):
        src = _read(_CORE_JSON)
        self.assertRegex(src,
            r'POSES_SCHEMA_VERSION\s*=\s*"rbftools\.poses\.v1"',
            "core_json must define POSES_SCHEMA_VERSION = "
            "'rbftools.poses.v1' (the immutable string downstream "
            "validators key on).")

    # ----- core_json: PosesImportValidationError -----

    def test_PERMANENT_b_validation_error_class_defined(self):
        src = _read(_CORE_JSON)
        self.assertRegex(src,
            r"class\s+PosesImportValidationError\s*\(\s*Exception\s*\)\s*:",
            "core_json must define PosesImportValidationError "
            "(distinct from SchemaValidationError to avoid coupling "
            "the new poses-only path with the full-node validator).")

    # ----- core_json: export function -----

    def test_PERMANENT_c_export_function_signature(self):
        src = _read(_CORE_JSON)
        self.assertRegex(src,
            r"def\s+export_poses_to_path\s*\(\s*node\s*,\s*path\s*\)\s*:",
            "core_json.export_poses_to_path must take (node, path).")
        # Must use atomic_write_json so a crash mid-write doesn't
        # leave a half-written JSON the importer would choke on.
        m = re.search(
            r"def\s+export_poses_to_path[\s\S]+?(?=\ndef\s|\nclass\s)", src)
        self.assertIsNotNone(m)
        body = m.group(0)
        self.assertIn("atomic_write_json", body,
            "Export must use atomic_write_json for crash-safety.")
        self.assertIn("POSES_SCHEMA_VERSION", body,
            "Export must stamp POSES_SCHEMA_VERSION into the file.")

    def test_PERMANENT_d_export_includes_signature_metadata(self):
        """Export JSON must include enough metadata to validate "
        "import dim consistency."""
        src = _read(_CORE_JSON)
        m = re.search(
            r"def\s+export_poses_to_path[\s\S]+?(?=\ndef\s|\nclass\s)", src)
        body = m.group(0)
        for key in ('"input_count"', '"output_count"', '"driver"',
                    '"driven"', '"poses"', '"n_poses"'):
            self.assertIn(key, body,
                "Export payload must include {} for import-time "
                "validation.".format(key))

    # ----- core_json: import function -----

    def test_PERMANENT_e_import_function_signature(self):
        src = _read(_CORE_JSON)
        self.assertRegex(src,
            r"def\s+import_poses_from_path\s*\(\s*node\s*,\s*path\s*,\s*"
            r"mode\s*=\s*\"replace\"\s*\)\s*:",
            "core_json.import_poses_from_path must take "
            "(node, path, mode='replace') with default 'replace'.")

    def test_PERMANENT_f_validate_payload_helper(self):
        src = _read(_CORE_JSON)
        self.assertRegex(src,
            r"def\s+_validate_poses_payload\s*\(\s*data\s*,\s*target_node\s*\)\s*:",
            "core_json must define _validate_poses_payload helper.")

    def test_PERMANENT_g_hard_fail_dim_mismatch(self):
        """Validator raises on input_count / output_count mismatch."""
        src = _read(_CORE_JSON)
        m = re.search(
            r"def\s+_validate_poses_payload[\s\S]+?(?=\ndef\s|\nclass\s)", src)
        body = m.group(0)
        # Must compare file_in_count vs target_in_count
        self.assertIn("file_in_count != target_in_count", body,
            "Validator must hard-fail on input count mismatch.")
        self.assertIn("file_out_count != target_out_count", body,
            "Validator must hard-fail on output count mismatch.")
        # Must raise the correct exception type
        self.assertIn("raise PosesImportValidationError", body,
            "Hard-fail path must raise PosesImportValidationError.")

    def test_PERMANENT_h_soft_warn_renames(self):
        """Validator collects rename-detected warnings (no raise)."""
        src = _read(_CORE_JSON)
        m = re.search(
            r"def\s+_validate_poses_payload[\s\S]+?(?=\ndef\s|\nclass\s)", src)
        body = m.group(0)
        self.assertIn("warnings_list", body,
            "Validator must collect a warnings_list for rename "
            "detection (driver / driven node + attrs).")
        self.assertIn("driver node renamed", body,
            "Validator must surface driver-node-renamed soft warning.")
        self.assertIn("driven node renamed", body,
            "Validator must surface driven-node-renamed soft warning.")

    def test_PERMANENT_i_per_pose_dim_check(self):
        """Each pose's inputs/values length must match counts."""
        src = _read(_CORE_JSON)
        m = re.search(
            r"def\s+_validate_poses_payload[\s\S]+?(?=\ndef\s|\nclass\s)", src)
        body = m.group(0)
        self.assertIn("len(ins) != file_in_count", body,
            "Per-pose inputs-length check must raise on mismatch.")
        self.assertIn("len(outs) != file_out_count", body,
            "Per-pose values-length check must raise on mismatch.")

    def test_PERMANENT_j_replace_clears_existing_poses(self):
        """mode='replace' must remove existing poses[] indices."""
        src = _read(_CORE_JSON)
        m = re.search(
            r"def\s+import_poses_from_path[\s\S]+?(?=\ndef\s|\nclass\s|\Z)",
            src)
        body = m.group(0) if m else src[src.find("def import_poses_from_path"):]
        self.assertIn('mode == "replace"', body,
            "Import must branch on mode == 'replace' to clear "
            "existing poses before writing.")
        self.assertIn("removeMultiInstance", body,
            "Replace path must call removeMultiInstance to clear "
            "the existing poses[] indices.")

    def test_PERMANENT_k_append_uses_next_free_index(self):
        """mode='append' must compute write_base from existing max+1."""
        src = _read(_CORE_JSON)
        m = re.search(
            r"def\s+import_poses_from_path[\s\S]+?(?=\ndef\s|\nclass\s|\Z)",
            src)
        body = m.group(0) if m else src[src.find("def import_poses_from_path"):]
        self.assertRegex(body,
            r"max\s*\(\s*existing\s*\)\s*\+\s*1",
            "Append path must use 'max(existing) + 1' as the write "
            "base index so file poses do not collide with current.")

    def test_PERMANENT_l_import_triggers_retrain(self):
        """Import must toggle evaluate so the new poses train."""
        src = _read(_CORE_JSON)
        m = re.search(
            r"def\s+import_poses_from_path[\s\S]+?(?=\ndef\s|\nclass\s|\Z)",
            src)
        body = m.group(0) if m else src[src.find("def import_poses_from_path"):]
        self.assertRegex(body,
            r'cmds\.setAttr\([^)]*\.evaluate[^)]*,\s*0\s*\)',
            "Import must evaluate=0 then evaluate=1 so the C++ "
            "compute() retrains under the new poses.")
        self.assertRegex(body,
            r'cmds\.setAttr\([^)]*\.evaluate[^)]*,\s*1\s*\)')

    # ----- controller wiring -----

    def test_PERMANENT_m_controller_export_method(self):
        src = _read(_CONTROLLER)
        self.assertRegex(src,
            r"def\s+export_poses_to_path\s*\(\s*self\s*,\s*path\s*\)\s*:",
            "controller.export_poses_to_path(self, path) must exist.")

    def test_PERMANENT_n_controller_import_method(self):
        src = _read(_CONTROLLER)
        self.assertRegex(src,
            r"def\s+import_poses_from_path\s*\(\s*self\s*,\s*path\s*,\s*"
            r"mode\s*=\s*\"replace\"\s*\)\s*:",
            "controller.import_poses_from_path(self, path, "
            "mode='replace') must exist.")

    # ----- UI menu wiring -----

    def test_PERMANENT_o_ui_registers_menu_actions(self):
        src = _read(_MAIN_WINDOW)
        self.assertIn(
            'add_file_action("menu_export_poses",', src,
            "main_window must register the Export Poses Only menu "
            "action via add_file_action('menu_export_poses', ...).")
        self.assertIn(
            'add_file_action("menu_import_poses",', src,
            "main_window must register the Import Poses Only menu "
            "action via add_file_action('menu_import_poses', ...).")

    def test_PERMANENT_p_ui_handlers_defined(self):
        src = _read(_MAIN_WINDOW)
        self.assertRegex(src,
            r"def\s+_on_export_poses\s*\(\s*self\s*\)\s*:",
            "main_window must define _on_export_poses(self).")
        self.assertRegex(src,
            r"def\s+_on_import_poses\s*\(\s*self\s*\)\s*:",
            "main_window must define _on_import_poses(self).")

    def test_PERMANENT_q_ui_handler_routes_through_controller(self):
        src = _read(_MAIN_WINDOW)
        m = re.search(
            r"def\s+_on_import_poses[\s\S]+?(?=\n\s{0,4}def\s)", src)
        self.assertIsNotNone(m)
        body = m.group(0)
        self.assertIn("import_poses_from_path", body,
            "_on_import_poses must call self._ctrl."
            "import_poses_from_path(...) — UI does not bypass the "
            "controller.")

    # ----- i18n strings -----

    def test_PERMANENT_r_i18n_keys_present_both_langs(self):
        src = _read(_I18N)
        # English block
        self.assertIn('"menu_export_poses":', src)
        self.assertIn('"menu_import_poses":', src)
        self.assertIn('"msg_import_poses_failed":', src)
        # Both occurrences = en + zh blocks (i18n pattern is two
        # dicts with the same keys; both must carry the new keys).
        self.assertGreaterEqual(src.count('"menu_export_poses":'), 2,
            "menu_export_poses must be defined in BOTH en and zh "
            "translation dicts.")
        self.assertGreaterEqual(src.count('"menu_import_poses":'), 2,
            "menu_import_poses must be defined in BOTH en and zh "
            "translation dicts.")

    # ----- Landing tag -----

    def test_PERMANENT_s_landing_tag_referenced(self):
        n_core = _read(_CORE_JSON).count("M_P0_POSES_IO")
        n_ctrl = _read(_CONTROLLER).count("M_P0_POSES_IO")
        n_ui = _read(_MAIN_WINDOW).count("M_P0_POSES_IO")
        n_i18n = _read(_I18N).count("M_P0_POSES_IO")
        self.assertGreaterEqual(n_core, 1)
        self.assertGreaterEqual(n_ctrl, 1)
        self.assertGreaterEqual(n_ui, 1)
        self.assertGreaterEqual(n_i18n, 1)


if __name__ == "__main__":
    unittest.main()
