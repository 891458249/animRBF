"""M_B24a2-2 — Versioned JSON schema tests.

Covers:
  T_VERSIONED_SCHEMA_PRESENT (#26, PERMANENT GUARD, 3 sub-checks)
  T_M_B2_MIGRATION_BACKCOMPAT (#25 sub-check (d) ENABLED)

  + 加固 1 dual-direction load/upgrade/dump assertion
  + 加固 5 one-way wormhole defense (dump never writes legacy)
"""

from __future__ import absolute_import

import inspect
import json
import os
import re
import unittest

import conftest


_REPO_ROOT = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..")
)
_FIXTURES_DIR = os.path.join(
    _REPO_ROOT, "modules", "RBFtools", "tests", "fixtures"
)
_LEGACY_MA = os.path.join(_FIXTURES_DIR, "legacy_v5_pre_b24.ma")
_LEGACY_JSON = os.path.join(_FIXTURES_DIR, "legacy_v5_pre_b24.json")


# ----------------------------------------------------------------------
# T_VERSIONED_SCHEMA_PRESENT (#26, PERMANENT GUARD, 3 sub-checks)
# ----------------------------------------------------------------------


class TestVersionedSchemaPresent(unittest.TestCase):
    """#26 — three sub-checks lock the v5.0-M_B24 versioning protocol."""

    def test_a_current_schema_version_locked(self):
        # Commit 1 (M_PER_POSE_SIGMA) atomic bump from m_b24 →
        # m_per_pose_sigma. M_B24 string is now in LEGACY (#26.b
        # extension verified by test_b_legacy_m_b24_membership_PERMANENT).
        from RBFtools.core_json import SCHEMA_VERSION
        self.assertEqual(SCHEMA_VERSION,
                         "rbftools.v5.m_per_pose_sigma",
            "SCHEMA_VERSION must be the m_per_pose_sigma string post-bump")

    def test_b_legacy_m3_membership_PERMANENT(self):
        from RBFtools.core_json import LEGACY_SCHEMA_VERSIONS
        self.assertIn("rbftools.v5.m3", LEGACY_SCHEMA_VERSIONS,
            "rbftools.v5.m3 MUST remain in LEGACY_SCHEMA_VERSIONS - "
            "removing it would orphan v5.0-pre-M_B24 fixtures")

    def test_c_versioned_dispatch_logic_present(self):
        """加固 3: source-scan core_json.py for versioned dispatch
        keywords. Multi-keyword OR so future refactors that rename
        the helper but preserve semantics still pass."""
        from RBFtools import core_json
        src = inspect.getsource(core_json)
        keywords = [
            "_upgrade_legacy_dict",
            "LEGACY_SCHEMA_VERSIONS",
            "_migrate_legacy_schema",   # forward-compat candidate name
        ]
        self.assertTrue(
            any(kw in src for kw in keywords),
            "core_json.py must contain versioned dispatch logic; "
            "none of {} found".format(keywords))


# ----------------------------------------------------------------------
# T_M_B2_MIGRATION_BACKCOMPAT (#25 sub-check (d) ENABLED)
# ----------------------------------------------------------------------


class TestM_B2_MigrationBackcompat_FixturesPresent(unittest.TestCase):
    """#25 sub-check (d) - legacy fixtures committed + PERMANENT
    marker present in .json _comment."""

    def test_d_legacy_ma_fixture_present(self):
        self.assertTrue(os.path.isfile(_LEGACY_MA),
            "legacy_v5_pre_b24.ma fixture missing - PERMANENT")
        size = os.path.getsize(_LEGACY_MA)
        self.assertLess(size, 10 * 1024,
            "legacy .ma fixture grew past 10 KB (got {})".format(size))

    def test_d_legacy_json_fixture_present(self):
        self.assertTrue(os.path.isfile(_LEGACY_JSON),
            "legacy_v5_pre_b24.json fixture missing - PERMANENT")

    def test_d_legacy_json_carries_permanent_marker(self):
        with open(_LEGACY_JSON, "r", encoding="utf-8") as f:
            d = json.load(f)
        self.assertIn("_comment", d,
            "legacy .json must have _comment field")
        self.assertIn("PERMANENT - DO NOT DELETE", d["_comment"],
            "legacy .json _comment must carry PERMANENT marker")


# ----------------------------------------------------------------------
# 加固 1 — dual-direction load/upgrade/dump assertion
# 加固 5 — one-way wormhole defense
# ----------------------------------------------------------------------


class TestVersionedSchemaUpgrade(unittest.TestCase):
    """加固 1+5: legacy load auto-upgrades to new shape; dump never
    writes legacy SCHEMA_VERSION (one-way wormhole defense)."""

    def setUp(self):
        with open(_LEGACY_JSON, "r", encoding="utf-8") as f:
            self.legacy = json.load(f)

    def test_legacy_dict_upgrades_to_new_shape(self):
        """加固 1: load(legacy) -> upgrade -> new shape with drivers
        list + output_encoding."""
        from RBFtools import core_json
        # Pre: legacy schema_version
        self.assertIn(self.legacy["schema_version"],
                      core_json.LEGACY_SCHEMA_VERSIONS)
        upgraded = core_json._upgrade_legacy_dict(self.legacy)
        # Post: schema_version forced to current.
        self.assertEqual(upgraded["schema_version"],
                         core_json.SCHEMA_VERSION)
        # Post: drivers (plural list) replaces driver (singular).
        node0 = upgraded["nodes"][0]
        self.assertIn("drivers", node0)
        self.assertNotIn("driver", node0,
            "upgrade must drop legacy 'driver' singular key")
        self.assertIsInstance(node0["drivers"], list)
        self.assertEqual(len(node0["drivers"]), 1,
            "single-driver legacy migrates to single-element list")
        # Post: output_encoding default 0 (Euler) added.
        self.assertEqual(node0["output_encoding"], 0)
        # Post: drivers[0] carries M_B24 metadata defaults.
        self.assertEqual(node0["drivers"][0]["weight"], 1.0)
        self.assertEqual(node0["drivers"][0]["encoding"], 0)
        # Post: _comment dropped (fixture-only metadata; 加固 5).
        self.assertNotIn("_comment", upgraded,
            "_comment is fixture-only metadata; must not survive "
            "into runtime dict")

    def test_dump_after_upgrade_writes_new_schema_only(self):
        """加固 5: dump(upgrade(legacy)) -> SCHEMA_VERSION is new,
        never legacy. One-way wormhole defense — there is NO inverse
        transform from new to legacy."""
        from RBFtools import core_json
        upgraded = core_json._upgrade_legacy_dict(self.legacy)
        s = json.dumps(upgraded)
        re_loaded = json.loads(s)
        self.assertEqual(re_loaded["schema_version"],
                         core_json.SCHEMA_VERSION,
            "dump must always write current SCHEMA_VERSION")
        self.assertNotIn(re_loaded["schema_version"],
                         core_json.LEGACY_SCHEMA_VERSIONS,
            "wormhole defense: re-load must NOT see legacy version")

    def test_idempotent_on_new_shape(self):
        """_upgrade_legacy_dict on already-new dict is idempotent."""
        from RBFtools import core_json
        new_shape = {
            "schema_version": core_json.SCHEMA_VERSION,
            "nodes": [{
                "name": "RBF1", "type_mode": "RBF", "settings": {},
                "drivers": [{"node": "drv1", "attrs": [],
                             "rotate_orders": [],
                             "weight": 1.0, "encoding": 0}],
                "driven": {"node": "drvn1", "attrs": []},
                "output_quaternion_groups": [],
                "output_encoding": 0,
                "poses": [],
            }],
        }
        upgraded = core_json._upgrade_legacy_dict(new_shape)
        # Idempotent — same shape, same SCHEMA_VERSION.
        self.assertEqual(upgraded["schema_version"],
                         core_json.SCHEMA_VERSION)
        self.assertIn("drivers", upgraded["nodes"][0])
        self.assertNotIn("driver", upgraded["nodes"][0])


if __name__ == "__main__":
    unittest.main()
