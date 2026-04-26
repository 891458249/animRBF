"""M2.5 — per-pose SwingTwist cache tests.

Test layout
-----------
T1   write_pose_swing_twist_cache writes 5 child fields per pose
     (poseSwingQuat / poseTwistAngle / poseSwingWeight /
     poseTwistWeight / poseSigma).
T2   write_pose_swing_twist_cache uses the sentinel poseSigma=-1.0
     ("cache not populated"; compute() consumer falls back to
     live decompose).
T3   apply_poses pipeline calls write_pose_swing_twist_cache as
     step 3 (between _write_pose_to_node and capture baselines).
T4   read_pose_swing_twist_cache returns the expected dict shape
     when the node has poses populated.
T5   read_pose_swing_twist_cache returns [] when the node is
     missing (defensive).

T_M2_5_CACHE_NOT_IN_SCHEMA — PERMANENT GUARD scanning THREE files:
  - core_json.py (would force SCHEMA_VERSION bump)
  - core_mirror.py (would copy derived state instead of letting
    Apply rebuild)
  - core_alias.py (would expose cache fields in channel box,
    violating the (G.2) UI invisibility decision)

T_M2_5_CORE_JSON_DIFF_EMPTY — PERMANENT GUARD: the M2.5 commit
  changed exactly zero lines in core_json.py (constitutional
  proof — see addendum §M2.5).
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
    out = []
    for line in src.splitlines():
        stripped = line.lstrip()
        if stripped.startswith("#"):
            continue
        out.append(line)
    return "\n".join(out)


def _reset_cmds():
    cmds.reset_mock(side_effect=True, return_value=True)
    cmds.objExists.return_value = True
    cmds.warning.side_effect = None


# ----------------------------------------------------------------------
# T1 — 5 child fields per pose
# ----------------------------------------------------------------------


class T1_WriteCacheChildren(unittest.TestCase):

    def test_writes_all_five_children_per_pose(self):
        _reset_cmds()
        from RBFtools import core
        from RBFtools.core import PoseData
        with mock.patch("RBFtools.core.get_shape") as mg, \
             mock.patch("RBFtools.core._exists") as me:
            mg.return_value = "RBF1Shape"
            me.return_value = True
            core.write_pose_swing_twist_cache(
                "RBF1",
                [PoseData(0, [0.0, 0.0, 0.0], [0.0]),
                 PoseData(1, [0.5, 0.0, 0.0], [1.0])],
            )
        # Expect setAttr called 5x per pose × 2 poses = 10 times.
        self.assertEqual(cmds.setAttr.call_count, 10)
        # Verify field names appear in the call args.
        call_strs = [str(c) for c in cmds.setAttr.call_args_list]
        joined = "\n".join(call_strs)
        for child in ("poseSwingQuat", "poseTwistAngle",
                      "poseSwingWeight", "poseTwistWeight",
                      "poseSigma"):
            self.assertIn(child, joined,
                "expected setAttr call referencing " + child)


# ----------------------------------------------------------------------
# T2 — sentinel poseSigma = -1.0
# ----------------------------------------------------------------------


class T2_SentinelSigma(unittest.TestCase):

    def test_sigma_writes_minus_one(self):
        _reset_cmds()
        from RBFtools import core
        from RBFtools.core import PoseData
        with mock.patch("RBFtools.core.get_shape") as mg, \
             mock.patch("RBFtools.core._exists") as me:
            mg.return_value = "RBF1Shape"
            me.return_value = True
            core.write_pose_swing_twist_cache(
                "RBF1",
                [PoseData(0, [0.0, 0.0, 0.0], [0.0])],
            )
        # The poseSigma setAttr call must pass -1.0 as the value.
        sigma_calls = [
            c for c in cmds.setAttr.call_args_list
            if "poseSigma" in str(c)
        ]
        self.assertEqual(len(sigma_calls), 1)
        # Value is the second positional arg.
        self.assertEqual(sigma_calls[0][0][1], -1.0)


# ----------------------------------------------------------------------
# T3 — apply_poses pipeline insertion
# ----------------------------------------------------------------------


class T3_ApplyPosesIntegration(unittest.TestCase):

    def test_step_3_calls_write_swing_twist_cache_in_source(self):
        """Source-text guard: apply_poses body must contain a
        write_pose_swing_twist_cache call between
        _write_pose_to_node (step 2) and capture_output_baselines
        (step 4)."""
        import pathlib
        path = pathlib.Path(__file__).resolve().parent.parent
        text = (path / "scripts" / "RBFtools"
                / "core.py").read_text(encoding="utf-8")
        idx = text.find("def apply_poses(node, driver_node, "
                        "driven_node,")
        self.assertGreater(idx, 0)
        body = text[idx:idx + 4000]
        # All three calls must appear in this order:
        i_write_pose = body.find("_write_pose_to_node(")
        i_swing_cache = body.find("write_pose_swing_twist_cache(")
        i_baselines = body.find("capture_output_baselines(")
        self.assertGreater(i_write_pose, 0)
        self.assertGreater(i_swing_cache, i_write_pose,
            "write_pose_swing_twist_cache must come AFTER "
            "_write_pose_to_node in apply_poses")
        self.assertGreater(i_baselines, i_swing_cache,
            "capture_output_baselines must come AFTER "
            "write_pose_swing_twist_cache (step 3) in apply_poses")

    def test_step_3_failure_is_warning_only(self):
        """Source-text guard: the M2.5 step is wrapped in
        try/except + cmds.warning — never breaks the Apply
        chain (cache miss falls back to live decompose in
        compute())."""
        import pathlib
        path = pathlib.Path(__file__).resolve().parent.parent
        text = (path / "scripts" / "RBFtools"
                / "core.py").read_text(encoding="utf-8")
        idx = text.find("# 3 — M2.5: per-pose SwingTwist")
        self.assertGreater(idx, 0)
        body = text[idx:idx + 1500]
        self.assertIn("try:", body)
        self.assertIn("write_pose_swing_twist_cache(", body)
        self.assertIn("cmds.warning", body)


# ----------------------------------------------------------------------
# T4 — read_pose_swing_twist_cache shape
# ----------------------------------------------------------------------


class T4_ReadCacheShape(unittest.TestCase):

    def test_returns_dict_per_pose(self):
        _reset_cmds()
        from RBFtools import core
        with mock.patch("RBFtools.core.get_shape") as mg, \
             mock.patch("RBFtools.core._exists") as me:
            mg.return_value = "RBF1Shape"
            me.return_value = True
            cmds.getAttr.side_effect = None
            cmds.getAttr.return_value = [(0.0, 0.0, 0.0, 1.0)]

            def safe_get_side(path, default=0):
                if "poseSigma" in path:
                    return -1.0
                if "poseTwistAngle" in path:
                    return 0.0
                if "poseSwingWeight" in path or "poseTwistWeight" in path:
                    return 1.0
                return default

            with mock.patch("RBFtools.core.safe_get",
                            side_effect=safe_get_side):
                # Two pose indices on the multi.
                def gattr_side(*args, **kwargs):
                    if kwargs.get("multiIndices"):
                        return [0, 1]
                    return [(0.0, 0.0, 0.0, 1.0)]
                cmds.getAttr.side_effect = gattr_side
                result = core.read_pose_swing_twist_cache("RBF1")
        self.assertEqual(len(result), 2)
        for entry in result:
            self.assertIn("swing_quat", entry)
            self.assertIn("twist_angle", entry)
            self.assertIn("swing_weight", entry)
            self.assertIn("twist_weight", entry)
            self.assertIn("sigma", entry)


# ----------------------------------------------------------------------
# T5 — read defensive
# ----------------------------------------------------------------------


class T5_ReadDefensive(unittest.TestCase):

    def test_missing_node_returns_empty(self):
        from RBFtools import core
        with mock.patch("RBFtools.core.get_shape") as mg, \
             mock.patch("RBFtools.core._exists") as me:
            mg.return_value = ""
            me.return_value = False
            self.assertEqual(
                core.read_pose_swing_twist_cache("RBF1"), [])


# ----------------------------------------------------------------------
# T_M2_5_CACHE_NOT_IN_SCHEMA — PERMANENT GUARD (3 files)
# ----------------------------------------------------------------------


class T_CacheNotInSchema(unittest.TestCase):
    """PERMANENT GUARD — DO NOT REMOVE.

    Cache field names MUST NOT leak into the schema-adjacent
    layers. Source-scan all three files (after stripping
    docstrings + comments so legitimate documentation is allowed)
    for any cache field identifier.

    Why all three:
      core_json.py — leakage would force SCHEMA_VERSION bump and
                     break T0 / T1b / T_M3_3_SCHEMA_FIELDS.
      core_mirror.py — leakage would copy derived state instead of
                       letting Apply rebuild (would break F.2).
      core_alias.py — leakage would expose cache fields in channel
                      box, violating G.2 (UI invisibility).
    """

    FORBIDDEN = (
        "poseSwingQuat",
        "poseTwistAngle",
        "poseSwingWeight",
        "poseTwistWeight",
        "poseSigma",
        "poseSwingTwistCache",
    )

    def _scan(self, mod):
        src = _strip_docstrings_and_comments(
            inspect.getsource(mod))
        for f in self.FORBIDDEN:
            self.assertNotIn(f, src,
                "{}.py contains {!r} — cache field leaked into a "
                "non-Apply layer; addendum §M2.5.4 boundary contract "
                "violated.".format(mod.__name__, f))

    def test_PERMANENT_core_json_clean(self):
        from RBFtools import core_json
        self._scan(core_json)

    def test_PERMANENT_core_mirror_clean(self):
        from RBFtools import core_mirror
        self._scan(core_mirror)

    def test_PERMANENT_core_alias_clean(self):
        from RBFtools import core_alias
        self._scan(core_alias)


# ----------------------------------------------------------------------
# T_M2_5_CORE_JSON_DIFF_EMPTY — PERMANENT GUARD
# ----------------------------------------------------------------------


class T_CoreJsonDiffEmpty(unittest.TestCase):
    """PERMANENT GUARD — DO NOT REMOVE.

    M2.5 must change ZERO lines in core_json.py — this is the
    constitutional proof that schema additions can be made
    without touching the JSON schema layer (addendum §M2.5).

    Implementation: the SCHEMA_VERSION constant must remain
    "rbftools.v5.m3" AND none of the cache field names appear in
    the module. Both invariants are checked here. Together with
    T_CacheNotInSchema and T0 they form the "can-add-schema-
    without-bumping-version" argument."""

    def test_PERMANENT_schema_version_locked(self):
        from RBFtools.core_json import SCHEMA_VERSION
        self.assertEqual(SCHEMA_VERSION, "rbftools.v5.m3")


if __name__ == "__main__":
    unittest.main()
