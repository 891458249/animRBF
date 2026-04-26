"""M1.5.1b — three PERMANENT GUARDs (#19, #20, #21) for the
.mll-rebuild-for-Maya-2025 sub-task.

Background — addendum §M1.5.1b:
    M3 全程 enforced "0 C++ changes". M1.5.1b breaks that lock for
    the first time, but the breach is minimal: 6 cosmetic comment
    lines in source/CMakeLists.txt, 0 lines of C++ source, 1 new
    binary at modules/RBFtools/plug-ins/win64/2025/RBFtools.mll.
    These three guards prevent regression on each of the three
    deliverables.

Guards:

  #19 T_M1_5_1B_BUILD_CONFIG — source/CMakeLists.txt key tokens.
      A future refactor that "tidies up" the CMakeLists must not
      drop any of the tokens that make Maya 2022/2025 dual-build
      possible. Token list locked in addendum §M1.5.1b.N.1.

  #20 T_M1_5_1B_PLUGIN_LOADABLE — .mll file-level structural
      checks. Existence + non-empty + PE32+ "MZ" header. The
      actual mayapy loadPlugin assertion is M1.5.3 territory
      (when ``require_rbftools_plugin`` flips on); this guard
      is the file-level forward-compat anchor that sits in the
      pure-Python layer. NO size-range assertion (toolchain
      version drift can shift size by a few KB; structural-only
      check is regression-stable).

  #21 T_M1_5_1B_2025_DIR_EXISTS — modules/RBFtools/plug-ins/
      win64/2025/ directory exists, symmetric to win64/2022/.
"""

from __future__ import absolute_import

import os
import unittest


_REPO_ROOT = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..")
)
_CMAKELISTS = os.path.join(_REPO_ROOT, "source", "CMakeLists.txt")
_PLUGINS_DIR = os.path.join(_REPO_ROOT, "modules", "RBFtools", "plug-ins")
_WIN64_2022 = os.path.join(_PLUGINS_DIR, "win64", "2022")
_WIN64_2025 = os.path.join(_PLUGINS_DIR, "win64", "2025")
_MLL_2025 = os.path.join(_WIN64_2025, "RBFtools.mll")


# Token list — addendum §M1.5.1b.N.1. Each token is a separate
# subTest so a regression points at the exact missing piece.
_BUILD_CONFIG_TOKENS = [
    "MAYA_DEVKIT_PATH",
    "OpenMaya",
    "OpenMayaUI",
    "OpenMayaAnim",
    "OpenMayaRender",
    "Foundation",
    "NT_PLUGIN",
    "REQUIRE_IOSTREAM",
    'SUFFIX ".mll"',
    'PREFIX ""',
    "RBFtools",
    "pluginMain.cpp",
    "RBFtools.cpp",
    "BRMatrix.cpp",
]


class TestM1_5_1B_BuildConfig(unittest.TestCase):
    """#19 T_M1_5_1B_BUILD_CONFIG."""

    def test_cmakelists_exists(self):
        self.assertTrue(
            os.path.isfile(_CMAKELISTS),
            "source/CMakeLists.txt must exist",
        )

    def test_key_tokens_present(self):
        with open(_CMAKELISTS, "r", encoding="utf-8") as f:
            src = f.read()
        for token in _BUILD_CONFIG_TOKENS:
            with self.subTest(token=token):
                self.assertIn(
                    token, src,
                    "CMakeLists.txt missing required token: %r — "
                    "regression on Maya 2022/2025 dual-build "
                    "support (addendum §M1.5.1b.N.1)" % token,
                )


class TestM1_5_1B_PluginLoadable(unittest.TestCase):
    """#20 T_M1_5_1B_PLUGIN_LOADABLE — file-level structural checks."""

    def test_mll_file_exists(self):
        self.assertTrue(
            os.path.isfile(_MLL_2025),
            "Maya 2025 .mll missing at %s" % _MLL_2025,
        )

    def test_mll_non_empty(self):
        self.assertGreater(
            os.path.getsize(_MLL_2025), 0,
            ".mll file is empty",
        )

    def test_mll_pe32_header(self):
        with open(_MLL_2025, "rb") as f:
            head = f.read(2)
        self.assertEqual(
            head, b"MZ",
            "Maya 2025 .mll header is not PE32+ (expected b'MZ', "
            "got %r)" % head,
        )


class TestM1_5_1B_DirLayout(unittest.TestCase):
    """#21 T_M1_5_1B_2025_DIR_EXISTS — symmetric to win64/2022/."""

    def test_2025_dir_exists(self):
        self.assertTrue(
            os.path.isdir(_WIN64_2025),
            "modules/RBFtools/plug-ins/win64/2025/ missing — "
            "Maya 2025 install location absent (addendum §M1.5.1b)",
        )

    def test_2022_dir_still_exists(self):
        self.assertTrue(
            os.path.isdir(_WIN64_2022),
            "modules/RBFtools/plug-ins/win64/2022/ missing — "
            "D.3 lock requires stale 2022 .mll preserved in place",
        )


if __name__ == "__main__":
    unittest.main()
