# -*- coding: utf-8 -*-
"""M_P0_ENCODING_OUTPUT_GLITCH (2026-04-30) — non-Raw encodings
output garbled values after a UI reload.

User report 2026-04-30: with inputEncoding set to Raw the RBF
solver outputs cleanly, but Quaternion / BendRoll / ExpMap /
SwingTwist all produce "jumpy" driven values after the user
performs any action that triggers a UI reload (node switch,
Refresh, add/remove driver). Raw is unaffected.

Root cause (commit-chain interaction bug):

  M_ENC_AUTOPIPE (commit 673ab13) wires
  ``driver.rotateOrder -> shape.driverInputRotateOrder[d]`` as a
  LIVE Maya connection so the C++ ``applyEncodingToBlock``
  (cpp:1464-1483 + 2606-2624) reads the right rotation order on
  every evaluation. The connection survives transform edits.

  M_ROTORDER_UI_REFACTOR (commit 234dacf) added
  ``controller._resync_rotate_order_length`` that runs on every
  ``_reload_driver_sources`` and self-heals
  ``driverInputRotateOrder[]`` length to match the live driver-
  source count. Pre-fix this self-heal called
  ``core.write_driver_rotate_orders``, which delegates to
  ``core.set_node_multi_attr``.

  ``set_node_multi_attr`` (core.py:227, M2.4a refinement 2) uses
  a transactional clear-then-write protocol:

      for idx in existing:
          cmds.removeMultiInstance(plug[idx], b=True)
      for i, v in enumerate(list_values):
          cmds.setAttr(plug[i], v)

  ``cmds.removeMultiInstance`` tears down ALL incoming
  connections at the indexed plug — including the M_ENC_AUTOPIPE
  live connection. The subsequent ``setAttr`` writes a STATIC
  value (commonly 0). After the reload, ``driverInputRotateOrder
  [d]`` no longer follows ``driver.rotateOrder`` — it is frozen
  at xyz=0. C++ applyEncodingToBlock then preconverts every
  Euler triple as XYZ, and any non-XYZ driver under a non-Raw
  encoding produces a wrong quaternion -> the driven channels
  jump. Raw encoding short-circuits the rotate-order read in
  applyEncodingToBlock and is unaffected — matching the user-
  reported "Raw 正常 + 其他编码乱跳" symptom verbatim.

Path C fix: replace the static write-back with a call into
``core.auto_resolve_generic_rotate_orders`` — the same helper
that established the live connection in the first place. It
uses ``connectAttr force=True`` per source, which is idempotent
and preserves / refreshes the live connection. The helper also
already handles the Raw / Quat clear-on-bypass branch and the
BendRoll / ExpMap / SwingTwist re-derive branch internally —
length self-heal becomes an emergent property of walking the
live driverSource list.

PERMANENT GUARD T_M_P0_ENCODING_OUTPUT_GLITCH locks the new
contract.
"""

from __future__ import absolute_import

import os
import unittest
from unittest import mock

import conftest


_REPO_ROOT = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..")
)
_CORE_PY = os.path.join(
    _REPO_ROOT, "modules", "RBFtools", "scripts", "RBFtools",
    "core.py")
_CTRL_PY = os.path.join(
    _REPO_ROOT, "modules", "RBFtools", "scripts", "RBFtools",
    "controller.py")


def _read(p):
    with open(p, "r", encoding="utf-8") as fh:
        return fh.read()


# ----------------------------------------------------------------------
# PERMANENT GUARD T_M_P0_ENCODING_OUTPUT_GLITCH
# ----------------------------------------------------------------------


class T_M_P0_ENCODING_OUTPUT_GLITCH(unittest.TestCase):
    """PERMANENT GUARD — DO NOT REMOVE.

    Path C fix: ``_resync_rotate_order_length`` MUST route through
    ``core.auto_resolve_generic_rotate_orders``, NOT through
    ``core.write_driver_rotate_orders``. The latter's clear-then-
    write protocol tears down M_ENC_AUTOPIPE live connections
    silently — this is the user-reported P0 mechanism."""

    @classmethod
    def setUpClass(cls):
        cls._core = _read(_CORE_PY)
        cls._ctrl = _read(_CTRL_PY)

    def test_PERMANENT_a_resync_uses_auto_resolve(self):
        body = self._ctrl.split(
            "def _resync_rotate_order_length(self):"
        )[1].split("\n    def ")[0]
        self.assertIn(
            "core.auto_resolve_generic_rotate_orders(", body,
            "_resync_rotate_order_length MUST call "
            "core.auto_resolve_generic_rotate_orders — the only "
            "path that uses connectAttr force=True (idempotent, "
            "preserves live connection).")

    def test_PERMANENT_b_resync_does_not_call_write_helper(self):
        body = self._ctrl.split(
            "def _resync_rotate_order_length(self):"
        )[1].split("\n    def ")[0]
        self.assertNotIn(
            "core.write_driver_rotate_orders(", body,
            "_resync_rotate_order_length MUST NOT call "
            "core.write_driver_rotate_orders — that path's clear-"
            "then-write contract tears down the M_ENC_AUTOPIPE "
            "live driver.rotateOrder connection (the bug shape).")

    def test_PERMANENT_c_resync_reads_inputEncoding(self):
        body = self._ctrl.split(
            "def _resync_rotate_order_length(self):"
        )[1].split("\n    def ")[0]
        self.assertIn(
            'cmds.getAttr(shape + ".inputEncoding")', body,
            "Helper MUST read the live inputEncoding from the "
            "shape so auto_resolve picks the right branch (Raw/"
            "Quat clear vs BendRoll/ExpMap/SwingTwist re-derive).")

    def test_PERMANENT_d_auto_resolve_uses_force_connect(self):
        # The auto_resolve helper itself MUST keep its
        # connectAttr force=True semantics — that is the
        # connection-preserving primitive. If a future refactor
        # of auto_resolve removed force=True, the bug would
        # re-surface even with the controller-layer fix.
        idx = self._core.find(
            "def auto_resolve_generic_rotate_orders(node, encoding):")
        self.assertGreater(idx, 0,
            "core MUST keep auto_resolve_generic_rotate_orders.")
        end = self._core.find("\ndef ", idx + 1)
        body = self._core[idx:end if end > 0 else idx + 4000]
        self.assertIn(
            "_resolve_driver_rotate_order(", body,
            "auto_resolve MUST delegate per-source to "
            "_resolve_driver_rotate_order which is the connectAttr "
            "force=True caller.")
        # _resolve_driver_rotate_order itself MUST use force=True
        # — locked separately so auto_resolve cannot bypass it
        # with an in-line connectAttr.
        idx2 = self._core.find(
            "def _resolve_driver_rotate_order(shape, driver_node, idx):")
        self.assertGreater(idx2, 0)
        end2 = self._core.find("\ndef ", idx2 + 1)
        body2 = self._core[idx2:end2 if end2 > 0 else idx2 + 1500]
        self.assertIn(
            "force=True", body2,
            "_resolve_driver_rotate_order MUST call connectAttr "
            "with force=True so the live connection is "
            "idempotently preserved across reloads. Without "
            "force=True a re-call after the connection already "
            "exists would raise; the resync path would then "
            "swallow + leave a stale state.")

    def test_PERMANENT_e_set_node_multi_attr_clears_with_remove(self):
        # Negative-control assertion: document why
        # write_driver_rotate_orders MUST NOT be reused — its
        # underlying primitive uses removeMultiInstance which
        # tears down connections. If a future refactor changed
        # set_node_multi_attr to NOT use removeMultiInstance,
        # this guard would fail and the maintainer would notice
        # they could relax the controller-layer no-go list.
        idx = self._core.find(
            "def set_node_multi_attr(node, attr, list_values, "
            "max_length=10000):")
        self.assertGreater(idx, 0)
        end = self._core.find("\ndef ", idx + 1)
        body = self._core[idx:end if end > 0 else idx + 4000]
        self.assertIn(
            "removeMultiInstance(", body,
            "set_node_multi_attr currently uses "
            "removeMultiInstance — this is the connection-tearing "
            "primitive that motivates the Path C controller-layer "
            "carve-out for driverInputRotateOrder[].")


# ----------------------------------------------------------------------
# Mock E2E — verify auto_resolve uses connectAttr force=True per source.
# ----------------------------------------------------------------------


@unittest.skipIf(conftest._REAL_MAYA,
    "mock-dependent (cmds + core stubs)")
class TestM_P0_ENCODING_OUTPUT_GLITCH_RuntimeBehavior(unittest.TestCase):
    """Mock E2E — drives _resolve_driver_rotate_order with a
    fake cmds and asserts the connectAttr call lands with
    force=True on the right plug. This is the connection-
    preserving primitive at the heart of the Path C fix."""

    def test_resolve_helper_uses_connectAttr_force_true(self):
        from RBFtools import core
        cmds_mock = mock.MagicMock()
        cmds_mock.attributeQuery.return_value = True
        cmds_mock.connectAttr = mock.MagicMock()
        with mock.patch.object(core, "cmds", cmds_mock):
            core._resolve_driver_rotate_order(
                "RBF1Shape", "drv0", 0)
        cmds_mock.connectAttr.assert_called_once()
        args, kwargs = cmds_mock.connectAttr.call_args
        self.assertEqual(args[0], "drv0.rotateOrder")
        self.assertEqual(args[1], "RBF1Shape.driverInputRotateOrder[0]")
        self.assertTrue(
            kwargs.get("force") is True,
            "connectAttr MUST be called with force=True so the "
            "call is idempotent across reloads — without it the "
            "Path C resync would raise on the second invocation "
            "and the live connection would not be re-established.")

    def test_auto_resolve_clears_for_raw_encoding(self):
        # Raw / Quat -> clear-on-bypass branch in auto_resolve.
        # The clear path internally DOES use the multi-clear
        # primitive (write_driver_rotate_orders -> set_node_
        # multi_attr) but ONLY when there are no live connections
        # to preserve (encoding is rotate-order-independent in
        # those cases). Verify the branch fires for encoding=0.
        from RBFtools import core
        cmds_mock = mock.MagicMock()
        cmds_mock.objExists.return_value = True
        cmds_mock.ls.return_value = ["RBF1Shape"]
        cmds_mock.listRelatives.return_value = ["RBF1Shape"]
        cmds_mock.nodeType.return_value = "RBFtools"
        cmds_mock.getAttr.return_value = []  # no existing entries
        with mock.patch.object(core, "cmds", cmds_mock):
            with mock.patch.object(
                    core, "write_driver_rotate_orders") as w:
                core.auto_resolve_generic_rotate_orders("RBF1", 0)
        # No drivers + Raw -> early return without writing.
        # (Prior test_m_enc_autopipe coverage already locks the
        # write-back-on-clear path; we only verify here that
        # encoding=0 takes the clear branch, not the connect
        # branch.)
        # The connect branch would have called connectAttr; assert
        # it wasn't.
        cmds_mock.connectAttr.assert_not_called()

    def test_auto_resolve_connects_for_expmap_encoding(self):
        # ExpMap / BendRoll / SwingTwist -> per-source connect.
        from RBFtools import core
        cmds_mock = mock.MagicMock()
        cmds_mock.objExists.return_value = True
        cmds_mock.ls.return_value = ["RBF1Shape"]
        cmds_mock.listRelatives.return_value = ["RBF1Shape"]
        cmds_mock.nodeType.return_value = "RBFtools"

        def _get_attr(plug, multiIndices=False):
            if multiIndices:
                if plug.endswith(".driverSource"):
                    return [0, 1]
            return None

        cmds_mock.getAttr.side_effect = _get_attr

        def _list_conns(plug, source=False, destination=False, plugs=False):
            if ".driverSource_node" in plug:
                d = int(
                    plug.split("driverSource[")[1].split("]")[0])
                return ["drv{}".format(d)]
            return []

        cmds_mock.listConnections.side_effect = _list_conns
        cmds_mock.attributeQuery.return_value = True
        cmds_mock.connectAttr = mock.MagicMock()

        with mock.patch.object(core, "cmds", cmds_mock):
            core.auto_resolve_generic_rotate_orders("RBF1", 3)

        # Two driverSource entries -> two connectAttr calls per
        # rotateOrder line, each with force=True.
        rotate_calls = [
            c for c in cmds_mock.connectAttr.call_args_list
            if ".rotateOrder" in str(c)
            and "driverInputRotateOrder" in str(c)
        ]
        self.assertEqual(len(rotate_calls), 2,
            "ExpMap (encoding=3) MUST connect rotateOrder for "
            "every driverSource entry; got "
            "{}.".format(len(rotate_calls)))
        for call in rotate_calls:
            self.assertTrue(
                call.kwargs.get("force") is True,
                "Every rotateOrder connectAttr MUST use "
                "force=True for idempotent reload safety.")


# ----------------------------------------------------------------------
# Wiring proof — controller helper calls auto_resolve, not write_*.
# ----------------------------------------------------------------------


@unittest.skipIf(conftest._REAL_MAYA,
    "mock-dependent (controller stub)")
class TestM_P0_ENCODING_OUTPUT_GLITCH_ControllerWiring(unittest.TestCase):

    def test_resync_calls_auto_resolve_with_live_encoding(self):
        from RBFtools.controller import MainController
        from RBFtools import controller as ctrl_mod
        ctrl = MainController.__new__(MainController)
        ctrl._current_node = "RBF1"

        cmds_stub = mock.MagicMock()
        cmds_stub.getAttr.return_value = 4    # SwingTwist
        cmds_stub.warning = mock.MagicMock()

        with mock.patch.multiple(
                ctrl_mod, cmds=cmds_stub,
                core=mock.MagicMock(
                    get_shape=mock.MagicMock(
                        return_value="RBF1Shape"),
                    auto_resolve_generic_rotate_orders=mock.MagicMock(),
                )):
            result = MainController._resync_rotate_order_length(ctrl)
            ctrl_mod.core.auto_resolve_generic_rotate_orders \
                .assert_called_once_with("RBF1", 4)
        self.assertTrue(result)

    def test_resync_does_not_invoke_write_helper(self):
        from RBFtools.controller import MainController
        from RBFtools import controller as ctrl_mod
        ctrl = MainController.__new__(MainController)
        ctrl._current_node = "RBF1"

        cmds_stub = mock.MagicMock()
        cmds_stub.getAttr.return_value = 2    # BendRoll
        cmds_stub.warning = mock.MagicMock()

        core_stub = mock.MagicMock(
            get_shape=mock.MagicMock(return_value="RBF1Shape"),
            auto_resolve_generic_rotate_orders=mock.MagicMock(),
            write_driver_rotate_orders=mock.MagicMock(),
        )

        with mock.patch.multiple(
                ctrl_mod, cmds=cmds_stub, core=core_stub):
            MainController._resync_rotate_order_length(ctrl)

        core_stub.write_driver_rotate_orders.assert_not_called()
        core_stub.auto_resolve_generic_rotate_orders \
            .assert_called_once()


if __name__ == "__main__":
    unittest.main()
