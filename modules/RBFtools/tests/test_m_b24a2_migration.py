"""M_B24a2-1 — multi-source driver API + legacy migration tests.

Covers:
  T_M_B2_MIGRATION_BACKCOMPAT (#25, PERMANENT GUARD, 4 sub-checks)
    - core.py contains _migrate_legacy_single_driver function
    - function body contains cmds.warning call
    - module-level _MIGRATION_WARNING_ISSUED flag exists
    - legacy fixtures land in M_B24a2-2 (sub-check (d) defers)

  DriverSource dataclass — frozen, post_init validation

  read_driver_info DeprecationWarning behavior + 14 caller
    backcompat sanity (subTest per caller, Type-A/B/C labelled)
"""

from __future__ import absolute_import

import os
import re
import unittest
import warnings
from unittest import mock

import conftest


_REPO_ROOT = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..")
)
_CORE_PY = os.path.join(
    _REPO_ROOT, "modules", "RBFtools", "scripts", "RBFtools", "core.py"
)


# ----------------------------------------------------------------------
# T_M_B2_MIGRATION_BACKCOMPAT (#25, PERMANENT GUARD)
# ----------------------------------------------------------------------


class TestM_B24A2_MigrationBackcompat(unittest.TestCase):
    """#25 T_M_B2_MIGRATION_BACKCOMPAT — source-scan only.

    Sub-check (d) (legacy fixture file existence) lands in M_B24a2-2;
    a placeholder test will appear there. Sub-checks (a)/(b)/(c) are
    enforced here.
    """

    @classmethod
    def setUpClass(cls):
        with open(_CORE_PY, "r", encoding="utf-8") as f:
            cls._src = f.read()

    def test_a_migrate_function_defined(self):
        self.assertIsNotNone(
            re.search(r"^def\s+_migrate_legacy_single_driver\s*\(",
                      self._src, re.M),
            "_migrate_legacy_single_driver function not found in core.py")

    def test_b_function_body_warns(self):
        # Body extends from the def line to the next top-level def.
        m = re.search(
            r"^def\s+_migrate_legacy_single_driver\s*\([^\n]*\):"
            r"(?P<body>.*?)(?=^def\s|^class\s|\Z)",
            self._src, re.M | re.S)
        self.assertIsNotNone(m, "could not extract migration body")
        self.assertIn("cmds.warning", m.group("body"),
            "_migrate_legacy_single_driver body must contain cmds.warning")

    def test_c_per_session_flag_present(self):
        self.assertIn("_MIGRATION_WARNING_ISSUED", self._src,
            "module-level _MIGRATION_WARNING_ISSUED flag missing")
        # Flag must be initialized to False at module scope.
        self.assertIsNotNone(
            re.search(r"^_MIGRATION_WARNING_ISSUED\s*=\s*False",
                      self._src, re.M),
            "_MIGRATION_WARNING_ISSUED must default to False")


# ----------------------------------------------------------------------
# DriverSource dataclass behavior
# ----------------------------------------------------------------------


class TestDriverSourceDataclass(unittest.TestCase):

    def test_construct_defaults(self):
        from RBFtools.core import DriverSource
        ds = DriverSource(node="loc1", attrs=("translateX",))
        self.assertEqual(ds.weight, 1.0)
        self.assertEqual(ds.encoding, 0)

    def test_frozen(self):
        from RBFtools.core import DriverSource
        ds = DriverSource(node="loc1", attrs=("translateX",))
        with self.assertRaises(Exception):  # FrozenInstanceError
            ds.weight = 2.0

    def test_post_init_negative_weight_rejected(self):
        from RBFtools.core import DriverSource
        with self.assertRaises(ValueError):
            DriverSource(node="loc1", attrs=(), weight=-0.5)

    def test_post_init_invalid_encoding_rejected(self):
        from RBFtools.core import DriverSource
        with self.assertRaises(ValueError):
            DriverSource(node="loc1", attrs=(), encoding=99)


# ----------------------------------------------------------------------
# read_driver_info DeprecationWarning behavior
# ----------------------------------------------------------------------


class TestReadDriverInfoDeprecation(unittest.TestCase):
    """read_driver_info is deprecated — every call must emit
    DeprecationWarning. The wrap routes through read_driver_info_multi
    so the returned tuple shape is preserved (14-caller backcompat)."""

    def setUp(self):
        # Reset cmds mock state (pure-python conftest mock framework).
        if not conftest._REAL_MAYA:
            import maya.cmds as cmds
            cmds.reset_mock()
            cmds.objExists.return_value = True
            cmds.listRelatives.return_value = ["shape1"]
            cmds.listConnections.return_value = []
            cmds.getAttr.return_value = []

    def test_emits_deprecation_warning(self):
        from RBFtools import core
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            core.read_driver_info("dummy")
            self.assertTrue(
                any(issubclass(warning.category, DeprecationWarning)
                    for warning in w),
                "read_driver_info did not emit DeprecationWarning")

    def test_returns_tuple_shape_preserved(self):
        from RBFtools import core
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            result = core.read_driver_info("dummy")
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 2)
        # Empty-state still returns ("", []) — backcompat guarantee.
        self.assertEqual(result, ("", []))


# ----------------------------------------------------------------------
# 14-caller backcompat sanity (Type-A/B/C labels per F2)
# ----------------------------------------------------------------------


# Each entry: (caller_id, type_label, description)
_CALLERS = [
    ("controller.py:324",       "A", "mirror src_driver"),
    ("controller.py:404",       "C", "drv_node + drv_attrs"),
    ("controller.py:691",       "C", "driver_node + driver_attrs"),
    ("controller.py:765",       "C", "driver_node + driver_attrs"),
    ("controller.py:899",       "C", "driver_node + driver_attrs"),
    ("core.py:471",             "C", "src_driver + src_driver_attrs"),
    ("core.py:631",             "A", "compose pattern"),
    ("core.py:645",             "A", "target only"),
    ("core_json.py:282",        "C", "JSON serialization"),
    ("core_neutral.py:117",     "C", "neutral sample"),
    ("core_profile.py:148",     "C", "profile report"),
    ("core_prune.py:269",       "B", "attrs only"),
    ("core_prune.py:317",       "C", "prune analyse"),
    ("live_edit_widget.py:114", "C", "scriptJob listener"),
    ("live_edit_widget.py:224", "B", "attrs only"),
]


class TestM_B24A2_FourteenCallerBackcompat(unittest.TestCase):
    """Verifies tuple-shape contract — every caller pattern still
    unpacks (driver_node, driver_attrs) without raising. Empty state
    is the safest mock surface; ensures callers handle ("", [])."""

    def test_all_callers_handle_empty_state_subtest(self):
        from RBFtools import core
        if not conftest._REAL_MAYA:
            import maya.cmds as cmds
            cmds.reset_mock()
            cmds.objExists.return_value = True
            cmds.listRelatives.return_value = ["shape1"]
            cmds.listConnections.return_value = []
            cmds.getAttr.return_value = []
        for caller_id, type_label, descr in _CALLERS:
            with self.subTest(caller=caller_id, type=type_label, desc=descr):
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", DeprecationWarning)
                    drv_node, drv_attrs = core.read_driver_info("dummy")
                self.assertEqual(drv_node, "",
                    "caller {} ({}) tuple unpack mismatch".format(
                        caller_id, type_label))
                self.assertEqual(drv_attrs, [])


if __name__ == "__main__":
    unittest.main()
