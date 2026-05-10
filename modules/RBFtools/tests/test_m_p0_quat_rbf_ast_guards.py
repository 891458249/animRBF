# -*- coding: utf-8 -*-
"""T_M_P0_QUAT_RBF_LANDING_GUARDS — AST 守护

Pin the 22 字面量不变量 that together prove the multi-driver ×
multi-driven quaternion RBF implementation is N-generic, dispatch-
correct, and that the B1 (QWA) / B2 (outputEncoding) safety nets
are wired. A future refactor that touches encode / distance / QWA
/ nlerp / ExpMap dispatch must update the matching guard here, so
silent drift away from the v5 multi-quat design is impossible.

Why AST and not behaviour: the C++ binary is rebuilt on a different
schedule than the source. AST guards run pure-Python, no mayapy /
.mll dependency, fast feedback in CI / pre-commit. Behaviour is
covered by ``test_m_p0_quat_rbf_e2e.py`` (mayapy) and
``test_m_p0_quat_rbf_unit.py`` (pure-Python math).

See ``docs/设计文档/RBFtools_v5_multi_quat_implementation.md`` for
the full algorithm spec these guards pin.
"""
from __future__ import absolute_import, division, print_function

import io
import os
import re
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(os.path.dirname(_HERE)))
_RBF_H = os.path.join(_REPO, "source", "RBFtools.h")
_RBF_CPP = os.path.join(_REPO, "source", "RBFtools.cpp")
_DOC = os.path.join(
    _REPO, "docs", u"设计文档",
    "RBFtools_v5_multi_quat_implementation.md")


def _read(path):
    with io.open(path, "r", encoding="utf-8") as fh:
        return fh.read()


class TestQuatRBFASTGuards(unittest.TestCase):

    # ----- §2 input encode N-generic 不变量 (6 项) -----

    def test_PERMANENT_a01_inDim_from_array_length(self):
        """cpp:2560 — inDim 来自 Maya input[] 全数组, 非 first source"""
        cpp = _read(_RBF_CPP)
        self.assertIn("unsigned inDim = inputIds.length();", cpp,
            "cpp:2560 must compute inDim from inputIds.length() — "
            "any change to first-source-only would break N-generic.")

    def test_PERMANENT_a02_groups_formula(self):
        """cpp:2670 — groups = inDim / 3 自动推 N"""
        cpp = _read(_RBF_CPP)
        # Match the actual formula 'groups = inDim / 3' as ternary RHS
        self.assertRegex(cpp, r"groups\s*=\s*encActive\s*\?\s*\(inDim\s*/\s*3\)\s*:\s*0",
            "cpp:2670 must keep groups = inDim/3 N-generic dispatch.")

    def test_PERMANENT_a03_quat_eff_dim_formula(self):
        """cpp:2672 — Quat: effectiveInDim = groups * 4"""
        cpp = _read(_RBF_CPP)
        self.assertIn("effectiveInDim = groups * 4;", cpp,
            "cpp:2672 must compute Quat eff dim as groups * 4 (N×4).")

    def test_PERMANENT_a04_swingtwist_eff_dim_formula(self):
        """cpp:2674 — SwingTwist: effectiveInDim = groups * 5"""
        cpp = _read(_RBF_CPP)
        self.assertIn("effectiveInDim = groups * 5;", cpp,
            "cpp:2674 must compute SwingTwist eff dim as groups * 5.")

    def test_PERMANENT_a05_driver_assign_uses_eff_dim(self):
        """cpp:2683 — driver.assign(effectiveInDim, 0.0) 无 hardcode"""
        cpp = _read(_RBF_CPP)
        self.assertIn("driver.assign(effectiveInDim, 0.0);", cpp,
            "cpp:2683 must size driver with effectiveInDim (no hardcode).")

    def test_PERMANENT_a06_posedata_setsize_uses_eff_dim(self):
        """cpp:2757 — poseData.setSize(P, effectiveInDim) Generic 路径"""
        cpp = _read(_RBF_CPP)
        self.assertIn("poseData.setSize(poseCount, effectiveInDim);", cpp,
            "cpp:2757 must size poseData with effectiveInDim "
            "(Generic-mode N-generic invariant).")

    # ----- §2 encode 循环 N-generic (4 项) -----

    def test_PERMANENT_a07_quat_encode_loop_groups(self):
        """cpp:2686 / 2842 — Quat encode 循环 g < groups (driver + pose row)"""
        cpp = _read(_RBF_CPP)
        # Driver vector + pose-row encode each have a groups-bounded loop.
        # We don't pin exact line numbers — just both occurrences of
        # encodeEulerToQuaternion-paired loop existing.
        n = len(re.findall(r"for\s*\(unsigned\s+g\s*=\s*0;\s*g\s*<\s*groups",
                          cpp))
        self.assertGreaterEqual(n, 4,
            "Expected ≥4 'for (unsigned g = 0; g < groups' loops "
            "(driver Quat/ExpMap/BendRoll/SwingTwist + pose-row mirror); "
            "fewer means an encoding branch lost N-generic dispatch.")

    def test_PERMANENT_a08_pose_row_encode_uses_groups(self):
        """cpp:2842 / 2855 / 2869 / 2882 — pose row encode 4 encoding 分支"""
        cpp = _read(_RBF_CPP)
        # Inside getPoseData, after the matValues fill, there's a
        # branch ladder mirroring driver encoding for poseData rows.
        # Each branch must use poseData(i, g*<stride>+...) writes.
        for stride in (4, 3, 5):
            self.assertRegex(cpp,
                r"poseData\(i,\s*g\s*\*\s*" + str(stride),
                "Pose-row encode must write poseData(i, g*{} + k) for "
                "the corresponding encoding stride (N-generic per-row "
                "encode).".format(stride))

    # ----- §3 distance 层不变量 (2 项) -----

    def test_PERMANENT_a09_quat_dispatch_to_block_distance(self):
        """cpp:3091-3095 — encoding==1 调度 getQuatBlockDistance"""
        cpp = _read(_RBF_CPP)
        self.assertRegex(cpp,
            r"if\s*\(\s*encoding\s*==\s*1\s*\)[^}]*getQuatBlockDistance",
            "Generic-mode distance dispatch must route encoding==1 "
            "to getQuatBlockDistance (per-block 1-|q·q| L2).")

    def test_PERMANENT_a10_quat_block_distance_formula(self):
        """cpp:3174 — 含 1.0 - fabs(dot)"""
        cpp = _read(_RBF_CPP)
        self.assertRegex(cpp,
            r"const\s+double\s+d\s*=\s*1\.0\s*-\s*fabs\s*\(\s*dot\s*\)",
            "getQuatBlockDistance must use d = 1.0 - fabs(dot) per "
            "v5 PART G.2 (chord-style, double-cover invariant).")

    # ----- §5.1 QWA / Power Iteration 不变量 (4 项) -----

    def test_PERMANENT_a11_scalar_sum_skips_quat_member(self):
        """cpp:4302 — getPoseWeights 标量 sum 跳过 quat-member 列"""
        cpp = _read(_RBF_CPP)
        self.assertRegex(cpp,
            r"if\s*\(\s*haveMask\s+&&\s+isQuatMember\s*\[\s*j\s*\]\s*\)\s*continue",
            "getPoseWeights must skip quat-member columns in the "
            "scalar accumulate loop (cpp:4302) so QWA owns those "
            "outputs verbatim.")

    def test_PERMANENT_a12_qwa_psd_clamp_negative_phi(self):
        """cpp:4313-4317 — phiQwa < 0 → clamp 0 + 警告"""
        cpp = _read(_RBF_CPP)
        self.assertIn("phiQwa = 0.0;", cpp,
            "QWA must clamp negative kernel activations to 0 to "
            "preserve PSD property of M_g (addendum §M2.2 Q8).")
        self.assertIn("qwaAnyClippedOut = true;", cpp,
            "QWA negative-phi clamp must raise qwaAnyClippedOut for "
            "the once-per-rig warning.")

    def test_PERMANENT_a13_qwa_zero_mass_returns_identity(self):
        """cpp:3791-3796 — trace(M) < EPS 返回 identity quat"""
        cpp = _read(_RBF_CPP)
        self.assertRegex(cpp,
            r"trace\s*<\s*EPS_M[\s\S]{0,200}?outQ\[3\]\s*=\s*1\.0;",
            "computeQWAForGroup must return identity quat (0,0,0,1) "
            "on zero-mass M_g (addendum §M2.2 (E)).")

    def test_PERMANENT_a14_power_iter_canonicalize_qw_positive(self):
        """cpp:3770-3773 — q_w<0 → 全负翻号 (canonical hemisphere)"""
        cpp = _read(_RBF_CPP)
        self.assertRegex(cpp,
            r"if\s*\(\s*result\[3\]\s*<\s*0\.0\s*\)[\s\S]{0,200}?"
            r"result\[0\]\s*=\s*-result\[0\]",
            "powerIterationMaxEigenvec4x4 must canonicalize to q_w >= 0 "
            "hemisphere (addendum §M2.2 (G), matches SwingTwist sign).")

    # ----- §5.2 nlerp / outputEncoding inverse 不变量 (3 项) -----

    def test_PERMANENT_a15_nlerp_function_exists(self):
        """cpp:3324 — nlerpQuaternions 函数定义存在"""
        cpp = _read(_RBF_CPP)
        self.assertIn("void RBFtools::nlerpQuaternions", cpp,
            "nlerpQuaternions definition must exist (B2 Quat path).")

    def test_PERMANENT_a16_nlerp_short_arc(self):
        """cpp:3344-3348 — dot < 0 → 翻号 (短弧选择)"""
        cpp = _read(_RBF_CPP)
        self.assertRegex(cpp,
            r"const\s+double\s+dot\s*=\s*qx\s*\*\s*rx[\s\S]{0,400}?"
            r"if\s*\(\s*dot\s*<\s*0\.0\s*\)[\s\S]{0,200}?"
            r"qx\s*=\s*-qx",
            "nlerp must select short-arc representative against the "
            "reference quat (avoid double-cover near-zero average).")

    def test_PERMANENT_a17_output_encoding_dispatch_only_1_or_2(self):
        """cpp:3461 — outputEncoding 仅 1/2 触发 (M_P0_OUTPUT_EXPMAP_FIX)"""
        cpp = _read(_RBF_CPP)
        self.assertIn("if (outputEncoding != 1 && outputEncoding != 2) return;",
                      cpp,
            "applyOutputEncodingBlend must early-return for "
            "outputEncoding ∉ {1, 2}; M_P0_OUTPUT_EXPMAP_FIX renumbered "
            "ExpMap from 3 → 2 to match the schema.")

    # ----- §5.2 Quat / ExpMap inverse 分支 (2 项) -----

    def test_PERMANENT_a18_output_encoding_quat_branch(self):
        """cpp:3475 — outputEncoding == 1 → encode/nlerp/decode"""
        cpp = _read(_RBF_CPP)
        # Locate the branch body (ends at next else/closing brace pair).
        m = re.search(
            r"if\s*\(\s*outputEncoding\s*==\s*1\s*\)\s*\{([\s\S]+?)\}\s*else",
            cpp)
        self.assertIsNotNone(m, "outputEncoding == 1 branch not found.")
        body = m.group(1)
        self.assertIn("nlerpQuaternions", body,
            "outputEncoding==1 branch body must call nlerpQuaternions.")
        self.assertIn("encodeEulerToQuaternion", body,
            "outputEncoding==1 branch must encode pose Eulers to quat.")

    def test_PERMANENT_a19_output_encoding_expmap_branch(self):
        """cpp:3500 — outputEncoding == 2 → log/sum/exp"""
        cpp = _read(_RBF_CPP)
        # Locate the else-if branch start.
        idx = cpp.find("else if (outputEncoding == 2)")
        self.assertGreaterEqual(idx, 0,
            "outputEncoding == 2 branch start not found.")
        # Take a 1500-char window — large enough to cover the full
        # ExpMap inverse body (log → weighted sum → exp → decode).
        window = cpp[idx:idx + 1500]
        self.assertIn("encodeQuaternionToExpMap", window,
            "outputEncoding==2 branch must call encodeQuaternionToExpMap "
            "(M_P0_OUTPUT_EXPMAP_FIX kept the math, only renumbered).")
        self.assertIn("decodeExpMapToEuler", window,
            "outputEncoding==2 branch must decode ExpMap back to Euler.")

    # ----- §5.4.1 B1↔B2 overlap disclose (M_P0_QUAT_RBF_OVERLAP_DISCLOSE) -----

    def test_PERMANENT_a20_overlap_skip_in_apply_block(self):
        """applyOutputEncodingBlend 接 isQuatMember + 跳重叠块"""
        cpp = _read(_RBF_CPP)
        h = _read(_RBF_H)
        # Header signature must mention isQuatMember (added by overlap fix).
        self.assertRegex(h,
            r"static\s+void\s+applyOutputEncodingBlend\s*\([\s\S]{0,500}?"
            r"isQuatMember",
            "applyOutputEncodingBlend signature must include "
            "isQuatMember mask (M_P0_QUAT_RBF_OVERLAP_DISCLOSE).")
        # Body must contain the overlap-skip warning literal. C++
        # adjacent-string concatenation may split the message across
        # lines, so check for unique substrings instead of the full
        # phrase: 'overlaps quaternion' (start) + 'preserve B1 QWA' (end).
        self.assertIn("overlaps quaternion", cpp,
            "applyOutputEncodingBlend body must emit the once-per-rig "
            "overlap warning (B1 takes precedence over B2).")
        self.assertIn("preserve B1 QWA", cpp,
            "Overlap warning must explain why the block was skipped "
            "(B1 QWA Power Iter is preferred over B2 nlerp / ExpMap).")
        # Once-per-rig flag and member.
        self.assertIn("outputEncodingOverlapWarningIssued", h,
            "Header must declare the once-per-rig overlap warning flag.")
        self.assertIn("outputEncodingOverlapWarningIssued", cpp,
            "compute() must read/write the overlap warning flag.")

    # ----- §2.4 + Matrix 互斥安全网 (2 项) -----

    def test_PERMANENT_a21_matrix_mode_encoding_reset(self):
        """cpp:1539 — Matrix 模式强制 effectiveEncoding = 0"""
        cpp = _read(_RBF_CPP)
        self.assertRegex(cpp,
            r"//\s*Matrix\s+mode\s+ignores\s+inputEncoding[\s\S]{0,300}?"
            r"effectiveEncoding\s*=\s*0;",
            "Matrix mode must reset effectiveEncoding to 0 to enforce "
            "(F)① contract — getDistances / getPoseWeights never get "
            "(isMatrixMode=true, encoding≠0) pair.")

    def test_PERMANENT_a22_non_triple_safety_net(self):
        """cpp:1473-1486 — inDim%3≠0 + non-Raw → fallback Raw + 警告"""
        cpp = _read(_RBF_CPP)
        self.assertRegex(cpp,
            r"const\s+bool\s+nonTriple\s*=\s*\(\s*wantsEncoded\s*&&\s*"
            r"rawInDim\s*%\s*3\s*!=\s*0\s*\)",
            "Non-3-divisible inDim safety net must trigger via "
            "nonTriple = (wantsEncoded && rawInDim % 3 != 0).")
        self.assertIn("Falling back to Raw.", cpp,
            "Non-triple inDim path must emit the user-facing "
            "'Falling back to Raw.' warning.")

    # ----- 文档存在性守护 -----

    def test_PERMANENT_a23_doc_exists_and_references_landing(self):
        """权威算法文档存在且引用本 landing"""
        self.assertTrue(os.path.exists(_DOC),
            "RBFtools_v5_multi_quat_implementation.md must exist "
            "as the authoritative algorithm spec.")
        doc = _read(_DOC)
        self.assertIn("M_P0_QUAT_RBF_LANDING_GUARDS", doc,
            "Doc must reference the M_P0_QUAT_RBF_LANDING_GUARDS "
            "landing tag for cross-reference.")
        self.assertIn("M_P0_QUAT_RBF_OVERLAP_DISCLOSE", doc,
            "Doc must reference the overlap-disclose safety net.")


if __name__ == "__main__":
    unittest.main()
