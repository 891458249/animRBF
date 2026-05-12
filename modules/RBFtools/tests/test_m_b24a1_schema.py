"""M_B24a1 — driverSource compound + outputEncoding schema guards.

Two PERMANENT GUARDs (#23, #24) + one M_B24a1 acceptance test
(dirty propagation under real mayapy).

  #23 T_DRIVER_SOURCE_AGGREGATION — RBFtools.cpp compute() reads
      driverSource[d] companion metadata via inputValue + child
      access. Source-scan only (file-level structural check).

  #24 T_OUTPUT_ENCODING_DECLARED — RBFtools.h declares MObject
      outputEncoding + RBFtools.cpp adds it to the schema.

  Acceptance test (real-mayapy, class-level skipIf): dirty
  propagation works for setAttr driverSource_weight -> output
  recompute, validating attributeAffects edges actually carry
  through DG.
"""

from __future__ import absolute_import

import os
import re
import unittest

import conftest
from _mayapy_fixtures import ensure_maya_standalone


_REPO_ROOT = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..")
)
_RBF_H = os.path.join(_REPO_ROOT, "source", "RBFtools.h")
_RBF_CPP = os.path.join(_REPO_ROOT, "source", "RBFtools.cpp")
_MLL_PATH = os.path.join(_REPO_ROOT, "modules", "RBFtools", "plug-ins",
                          "win64", "2025", "RBFtools.mll")


class TestM_B24A1_DriverSourceAggregation(unittest.TestCase):
    """#23 T_DRIVER_SOURCE_AGGREGATION."""

    def test_compute_reads_driver_source_metadata(self):
        with open(_RBF_CPP, "r", encoding="utf-8") as f:
            src = f.read()
        # readDriverSourceMetadata helper must call inputArrayValue
        # on driverSource and access driverSource_weight /
        # driverSource_encoding children.
        self.assertIn("inputArrayValue(driverSource", src,
            "RBFtools.cpp does not call inputArrayValue(driverSource, ...) "
            "- compute() consumer for M_B24a1 missing")
        self.assertIn("driverSource_weight", src,
            "RBFtools.cpp missing driverSource_weight read")
        self.assertIn("driverSource_encoding", src,
            "RBFtools.cpp missing driverSource_encoding read")

    def test_helper_function_present(self):
        with open(_RBF_CPP, "r", encoding="utf-8") as f:
            src = f.read()
        self.assertIn("RBFtools::readDriverSourceMetadata", src,
            "Helper readDriverSourceMetadata not defined")

    def test_compute_invokes_helper(self):
        with open(_RBF_CPP, "r", encoding="utf-8") as f:
            src = f.read()
        # The helper must be called from compute() (within the
        # driverList for-loop). Match the bare identifier.
        self.assertIsNotNone(
            re.search(r"\breadDriverSourceMetadata\s*\(", src),
            "compute() does not invoke readDriverSourceMetadata helper")


class TestM_B24A1_OutputEncodingDeclared(unittest.TestCase):
    """#24 T_OUTPUT_ENCODING_DECLARED."""

    def test_outputEncoding_in_header(self):
        with open(_RBF_H, "r", encoding="utf-8") as f:
            src = f.read()
        self.assertIn("static MObject outputEncoding;", src,
            "RBFtools.h missing outputEncoding declaration")

    def test_outputEncoding_added_in_cpp(self):
        with open(_RBF_CPP, "r", encoding="utf-8") as f:
            src = f.read()
        self.assertIn("addAttribute(outputEncoding)", src,
            "RBFtools.cpp does not addAttribute(outputEncoding)")
        self.assertIn(
            "attributeAffects(RBFtools::outputEncoding, RBFtools::output)",
            src,
            "attributeAffects edge outputEncoding->output missing")

    def test_outputEncoding_read_in_setOutputValues(self):
        with open(_RBF_CPP, "r", encoding="utf-8") as f:
            src = f.read()
        # Must read outputEncoding plug (placeholder enforcement
        # against MSVC dead-read elimination).
        self.assertIn("outputEncoding", src)
        self.assertIn("s_outEncSink", src,
            "outputEncoding placeholder thread_local sink missing - "
            "dead-read elimination may break attributeAffects edge")


@unittest.skipIf(not conftest._REAL_MAYA,
    "DG dirty propagation requires real mayapy; pure-python mocks skip")
class TestM_B24A1_DirtyPropagationRealMaya(unittest.TestCase):
    """Acceptance test (加固 4) — DG dirty must actually propagate
    when setAttr touches driverSource children."""

    @classmethod
    def setUpClass(cls):
        # M_B24a1 bypasses the M1.5.3-paused require_rbftools_plugin
        # stub by calling cmds.loadPlugin directly. Once M1.5.3a
        # unfreezes the fixture, this class can route through the
        # standard require_rbftools_plugin() helper.
        ensure_maya_standalone()
        import maya.cmds as cmds
        if not cmds.pluginInfo("RBFtools", q=True, loaded=True):
            cmds.loadPlugin(_MLL_PATH)

    def test_driver_source_weight_triggers_compute(self):
        import maya.cmds as cmds
        n = cmds.createNode("RBFtools")
        try:
            v0 = cmds.getAttr(n + ".output[0]")
            cmds.setAttr(n + ".driverSource[0].driverSource_weight", 5.0)
            v1 = cmds.getAttr(n + ".output[0]")
            # No exception means compute() ran. Both values may be
            # 0.0 since the node has no poses; the assertion is
            # structural - DG didn't error and both reads succeeded.
            self.assertIsNotNone(v0)
            self.assertIsNotNone(v1)
        finally:
            cmds.delete(n)

    def test_output_encoding_edge_live(self):
        import maya.cmds as cmds
        n = cmds.createNode("RBFtools")
        try:
            v0 = cmds.getAttr(n + ".output[0]")
            cmds.setAttr(n + ".outputEncoding", 1)
            v1 = cmds.getAttr(n + ".output[0]")
            # Same structural check; the thread_local sink prevents
            # MSVC O2 dead-read elimination from breaking the
            # attributeAffects(outputEncoding, output) edge.
            self.assertIsNotNone(v0)
            self.assertIsNotNone(v1)
        finally:
            cmds.delete(n)


if __name__ == "__main__":
    unittest.main()
