# -*- coding: utf-8 -*-
"""M_P0_RBF_HIERARCHICAL_TWO_LEVEL (2026-05-18) -- Phase 16 schema
permanent guards.

Phase 16 ships in two stages per the staged-delivery escalation
plan:
  * Stage 1 (this commit chain): Schema + cache invalidation +
    baseNet legacy passthrough + controller writers + .mll deploy +
    these tests.
  * Stage 2 (Phase 16.2): true two-level training (delta-net subset
    training + RHS = Actual - Predicted_Base), Shepard-gated three-
    pass inference, pose-grid UI columns. Deferred because the
    deeper C++ refactor in the 5963-line solver requires Maya
    runtime tests to validate the math (the executor environment
    has no mayapy in the sweep).

This file locks the Stage 1 invariants so a future Phase 16.2
refactor cannot silently regress the schema surface:

Source-introspection (header):
  1. struct RBFSubNet declared with 5 fields (wMat, polyMat,
     activeDrivers, poseIndices, isActiveLinear)
  2. static MObject poseParentIndex + poseDriverMask declared on
     the RBFtools class
  3. Instance members baseNet + deltaNets + subnetCacheDirty +
     prevPoseParentArr + prevPoseDriverMaskArr declared private
     (hard rail #12: never static)

Source-introspection (cpp):
  4. MObject definitions for poseParentIndex + poseDriverMask
  5. addAttribute registrations
  6. 2 attributeAffects pairs (NOT 4 -- prev-state cache compare
     handles evalInput promotion per the corrected design)
  7. Constructor inits subnetCacheDirty(true) so first compute
     always rebuilds
  8. Initialize() creates poseParentIndex with default -1
  9. Initialize() creates poseDriverMask as kIntArray multi
  10. compute() block contains the prev-state cache compare that
      reads currentPoseParentArr / currentPoseDriverMaskArr and
      promotes evalInput on drift
  11. End of training populates baseNet from wMat + polyMat

Source-introspection (controller):
  12. set_pose_parent_index method present + writes
      shape.poseParentIndex[row]
  13. set_pose_driver_mask method present + writes
      shape.poseDriverMask[row] as Int32Array

Cross-binary:
  14. Both .mll contain "poseParentIndex" + "poseDriverMask" ASCII
      strings, AND retain the Phase 15 strings as proof that the
      anti-overshoot work was not regressed.
"""

from __future__ import absolute_import

import io
import os
import sys
import unittest

_TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
if _TESTS_DIR not in sys.path:
    sys.path.insert(0, _TESTS_DIR)

import conftest  # noqa: E402


_REPO_ROOT = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..")
)
_RBF_H = os.path.join(_REPO_ROOT, "source", "RBFtools.h")
_RBF_CPP = os.path.join(_REPO_ROOT, "source", "RBFtools.cpp")
_CTRL_PY = os.path.join(
    _REPO_ROOT, "modules", "RBFtools", "scripts", "RBFtools",
    "controller.py")
_MLL_2022 = os.path.join(
    _REPO_ROOT, "modules", "RBFtools", "plug-ins",
    "win64", "2022", "RBFtools.mll")
_MLL_2025 = os.path.join(
    _REPO_ROOT, "modules", "RBFtools", "plug-ins",
    "win64", "2025", "RBFtools.mll")


def _read(path):
    with io.open(path, "r", encoding="utf-8") as fh:
        return fh.read()


def _read_bin(path):
    with open(path, "rb") as fh:
        return fh.read()


# ----------------------------------------------------------------------
# Source introspection -- RBFtools.h
# ----------------------------------------------------------------------


class T_M_P0_RBF_HIERARCHICAL_TWO_LEVEL_Header(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._h = _read(_RBF_H)

    def test_PERMANENT_01_subnet_struct_declared(self):
        """RBFSubNet struct MUST exist with the 5 documented fields.
        polyMat is the anchor-4 lifeline (M_P0_RBF_POLYNOMIAL_
        AUGMENTATION); isActiveLinear is anchor-3 (M_P0_RBF_
        COLUMN_RANK_DEFENSE). Both ride per-sub-net so Phase 16.2
        can extend without regressing anchors."""
        self.assertIn("struct RBFSubNet {", self._h)
        for field in (
                "BRMatrix          wMat;",
                "BRMatrix          polyMat;",
                "std::vector<int>  activeDrivers;",
                "std::vector<int>  poseIndices;",
                "std::vector<bool> isActiveLinear;"):
            self.assertIn(field, self._h,
                "RBFSubNet MUST declare {!r}".format(field))

    def test_PERMANENT_02_schema_mobjects_declared(self):
        self.assertIn(
            "static MObject poseParentIndex;", self._h)
        self.assertIn(
            "static MObject poseDriverMask;", self._h)

    def test_PERMANENT_03_instance_members_not_static(self):
        """Hard rail #12 -- baseNet / deltaNets / subnetCacheDirty
        + the two prev-state arrays MUST be instance, NOT static.
        Two RBFtools nodes in one scene MUST NOT share state."""
        for needle in (
                "RBFSubNet                          baseNet;",
                "std::unordered_map<int, RBFSubNet> deltaNets;",
                "bool                               subnetCacheDirty;",
                "std::vector<int>              prevPoseParentArr;",
                "std::vector<std::vector<int>> prevPoseDriverMaskArr;"):
            self.assertIn(needle, self._h,
                "Instance member MUST be declared: {!r}".format(
                    needle))
        # Explicitly: none of the above lines is prefixed by `static`.
        for line in self._h.splitlines():
            if "baseNet;" in line or "deltaNets;" in line or \
                    "subnetCacheDirty;" in line:
                self.assertNotIn("static", line,
                    "Hard rail #12: {!r} MUST NOT be static".format(
                        line.strip()))


# ----------------------------------------------------------------------
# Source introspection -- RBFtools.cpp
# ----------------------------------------------------------------------


class T_M_P0_RBF_HIERARCHICAL_TWO_LEVEL_Cpp(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._cpp = _read(_RBF_CPP)

    def test_PERMANENT_04_mobject_definitions(self):
        self.assertIn(
            "MObject RBFtools::poseParentIndex;", self._cpp)
        self.assertIn(
            "MObject RBFtools::poseDriverMask;", self._cpp)

    def test_PERMANENT_05_addattribute_calls(self):
        self.assertIn(
            "addAttribute(poseParentIndex);", self._cpp)
        self.assertIn(
            "addAttribute(poseDriverMask);", self._cpp)

    def test_PERMANENT_06_two_attributeaffects_not_four(self):
        """The CORRECTED design: only 2 attributeAffects pairs.
        Promotion to evalInput=true happens via the prev-state
        cache compare (test 10 below), NOT via attributeAffects on
        evaluate / evalInput. Re-adding attributeAffects on those
        targets would not actually trip retrain (cpp:1791-1793
        documents this for the prevBaseValueArr precedent)."""
        self.assertIn(
            "attributeAffects(RBFtools::poseParentIndex, "
            "RBFtools::output);", self._cpp)
        self.assertIn(
            "attributeAffects(RBFtools::poseDriverMask,  "
            "RBFtools::output);", self._cpp)
        # NOT 4 -- no affects on evaluate / evalInput target.
        for forbidden in (
                "attributeAffects(RBFtools::poseParentIndex, "
                "RBFtools::evaluate)",
                "attributeAffects(RBFtools::poseDriverMask, "
                "RBFtools::evaluate)"):
            self.assertNotIn(forbidden, self._cpp,
                "Hard rail correction: attributeAffects on "
                "evaluate does NOT trigger evalInput=true; "
                "the prev-state cache compare is the right "
                "mechanism. Re-adding {!r} would mislead the "
                "next maintainer.".format(forbidden))

    def test_PERMANENT_07_constructor_dirty_true(self):
        """First compute after construction MUST treat the cache as
        dirty so a freshly-loaded .ma rebuilds the sub-nets."""
        self.assertIn(
            "subnetCacheDirty(true)", self._cpp)

    def test_PERMANENT_08_poseparentindex_default_neg1(self):
        body_idx = self._cpp.find(
            'poseParentIndex = nAttr.create(')
        self.assertGreater(body_idx, 0,
            "poseParentIndex create call missing")
        slice_ = self._cpp[body_idx:body_idx + 600]
        self.assertIn('nAttr.setDefault(-1);', slice_,
            "poseParentIndex MUST default to -1 (= base pose) so "
            "legacy nodes silently keep Phase 15 single-layer "
            "behaviour")
        self.assertIn('nAttr.setArray(true);', slice_)
        self.assertIn('nAttr.setUsesArrayDataBuilder(true);', slice_)

    def test_PERMANENT_09_posedrivermask_intarray_multi(self):
        body_idx = self._cpp.find(
            'poseDriverMask = tAttr.create(')
        self.assertGreater(body_idx, 0,
            "poseDriverMask MUST be created via "
            "MFnTypedAttribute")
        slice_ = self._cpp[body_idx:body_idx + 400]
        self.assertIn('MFnData::kIntArray', slice_,
            "poseDriverMask MUST be a kIntArray (one mask per pose)")
        self.assertIn('tAttr.setArray(true);', slice_)

    def test_PERMANENT_10_prev_state_cache_compare(self):
        """compute() MUST read currentPoseParentArr +
        currentPoseDriverMaskArr each tick, compare to prev, and
        on drift promote evalInput + refresh prev + mark
        subnetCacheDirty. Mirrors the prevBaseValueArr precedent
        (cpp:1791-1851)."""
        self.assertIn(
            "currentPoseParentArr", self._cpp)
        self.assertIn(
            "currentPoseDriverMaskArr", self._cpp)
        self.assertIn(
            "currentPoseParentArr     != prevPoseParentArr",
            self._cpp,
            "Cache compare MUST trip on parent drift")
        self.assertIn(
            "currentPoseDriverMaskArr != prevPoseDriverMaskArr",
            self._cpp,
            "Cache compare MUST trip on mask drift")
        # On drift -> promote + refresh.
        self.assertIn("subnetCacheDirty      = true;", self._cpp,
            "Cache compare MUST mark subnetCacheDirty on drift")
        # MFnIntArrayData is used to read the mask
        self.assertIn("MFnIntArrayData iadFn", self._cpp,
            "Cache compare MUST read kIntArray via MFnIntArrayData")

    def test_PERMANENT_11_basenet_passthrough_populated(self):
        """End of training MUST capture wMat + polyMat into
        baseNet so Phase 16.2 (true subset training) has a known
        anchor to extend from. deltaNets stays empty in this
        stage."""
        self.assertIn("baseNet.wMat = wMat;", self._cpp)
        self.assertIn("baseNet.polyMat = polyMat;", self._cpp)
        self.assertIn("deltaNets.clear();", self._cpp)
        self.assertIn("subnetCacheDirty = false;", self._cpp,
            "Successful training MUST clear the dirty flag so the "
            "next inference tick can rely on the populated cache")


# ----------------------------------------------------------------------
# Source introspection -- controller.py
# ----------------------------------------------------------------------


class T_M_P0_RBF_HIERARCHICAL_TWO_LEVEL_Controller(
        unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._ctrl = _read(_CTRL_PY)

    def test_PERMANENT_12_set_pose_parent_index_method(self):
        self.assertIn(
            "def set_pose_parent_index(self, row, parent_index):",
            self._ctrl,
            "Controller MUST expose set_pose_parent_index")
        # The format-string concatenation may straddle a newline
        # after `shape` for readability; assert on the stable
        # fragment that survives any line wrap.
        self.assertIn(
            '"{}.poseParentIndex[{}]"', self._ctrl,
            "Controller MUST write to shape.poseParentIndex[row]")
        self.assertIn(
            "poseParentIndexChanged = QtCore.Signal", self._ctrl,
            "Controller MUST emit poseParentIndexChanged signal")

    def test_PERMANENT_13_set_pose_driver_mask_method(self):
        self.assertIn(
            "def set_pose_driver_mask(self, row, mask):",
            self._ctrl)
        # Empty mask path + Int32Array type.
        self.assertIn(
            'type="Int32Array"', self._ctrl,
            "Mask write MUST use the Int32Array attribute type")
        # Signal declaration uses double-space alignment with the
        # parent-index sibling; assert on the import-stable
        # substring instead of an exact whitespace match.
        self.assertIn(
            "poseDriverMaskChanged", self._ctrl,
            "Controller MUST emit poseDriverMaskChanged signal")
        self.assertIn(
            "QtCore.Signal(int, list)", self._ctrl,
            "poseDriverMaskChanged signature MUST carry (int, list) "
            "for (row, sanitised_mask)")


# ----------------------------------------------------------------------
# Cross-binary
# ----------------------------------------------------------------------


class T_M_P0_RBF_HIERARCHICAL_TWO_LEVEL_Binary(unittest.TestCase):

    _PHASE16_STRINGS = [
        b"poseParentIndex",
        b"poseDriverMask",
    ]
    # Phase 15 strings MUST still be present -- proof Phase 16 did
    # not silently regress the anti-overshoot output clamp.
    _PHASE15_PRESERVED = [
        b"outputClampEnabled",
        b"outputClampInflation",
    ]

    def _assert_in(self, path, needles, label):
        if not os.path.isfile(path):
            self.skipTest("{} not present".format(path))
        data = _read_bin(path)
        for n in needles:
            self.assertIn(
                n, data,
                "{}: missing marker {!r}".format(label, n))

    def test_PERMANENT_14_dual_mll_contains_phase16_strings(self):
        """Both .mll MUST contain the Phase 16 attribute names +
        the Phase 15 anti-overshoot anchors -- proof the dual SDK
        rebuild caught the new schema AND did not regress."""
        for path, label in (
                (_MLL_2022, "2022.mll"),
                (_MLL_2025, "2025.mll")):
            self._assert_in(path, self._PHASE16_STRINGS, label)
            self._assert_in(
                path, self._PHASE15_PRESERVED,
                "{} (Phase 15 preservation)".format(label))


if __name__ == "__main__":
    unittest.main()
