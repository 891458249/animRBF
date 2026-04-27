# -*- coding: utf-8 -*-
"""2026-04-28 (M_IDEMPOTENT_CONNECT + bone-name cache).

Coverage:
* core: _src_already_drives_node / _node_already_drives_dst dedup
  helpers, connect_routed honours them.
* widget: _SourceTabContent.node_name() reads from a Python cache,
  not from the QLineEdit — immune to any Qt lazy-render edge case
  that might leave non-active tabs' fields un-synced.
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
_TABBED_PY = os.path.join(
    _REPO_ROOT, "modules", "RBFtools", "scripts", "RBFtools",
    "ui", "widgets", "tabbed_source_editor.py")


def _read(p):
    with open(p, "r", encoding="utf-8") as fh:
        return fh.read()


class TestM_IDEMPOTENT_SourceScan(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._core = _read(_CORE_PY)

    def test_dedup_helpers_present(self):
        self.assertIn("def _src_already_drives_node", self._core)
        self.assertIn("def _node_already_drives_dst", self._core)

    def test_connect_routed_uses_dedup(self):
        body = self._core.split(
            "def connect_routed(")[1].split("\ndef ")[0]
        self.assertIn("_src_already_drives_node(src, node)", body)
        self.assertIn("_node_already_drives_dst(node, dst)", body)
        # Skip path must `continue` so the input[i] cursor does NOT
        # advance for skipped sources — otherwise a sparse-cursor
        # scenario would leak an empty slot.
        self.assertIn("continue", body)
        self.assertIn("next_input_idx", body)
        self.assertIn("next_output_idx", body)

    def test_dedup_walks_listConnections(self):
        body = self._core.split(
            "def _src_already_drives_node(")[1].split(
            "\ndef ")[0]
        self.assertIn("listConnections", body)
        self.assertIn("destination=True", body)
        self.assertIn("plugs=True", body)


class TestM_BONE_NAME_CACHE_SourceScan(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._tab = _read(_TABBED_PY)

    def test_source_tab_caches_node_name(self):
        # Cache initialised in __init__ (so reads before any
        # set_node_name get a deterministic empty string), updated
        # in set_node_name, returned by node_name().
        body_init = self._tab.split(
            "def __init__(self, role, parent=None):")[1].split(
            "\n    def ")[0]
        self.assertIn("self._node_name = \"\"", body_init)

        body_setter = self._tab.split(
            "def set_node_name(self, name):")[1].split(
            "\n    def ")[0]
        self.assertIn("self._node_name = str(name", body_setter)

        body_getter = self._tab.split(
            "def node_name(self):")[1].split("\n    def ")[0]
        # Getter must RETURN the cache, NOT the QLineEdit. Strip
        # comment lines before scanning so a doc-comment mentioning
        # the forbidden API doesn't trip the guard.
        code_lines = [
            ln for ln in body_getter.splitlines()
            if not ln.strip().startswith("#")
        ]
        code_only = "\n".join(code_lines)
        self.assertIn("_node_name", code_only)
        self.assertNotIn("_field_node.text()", code_only,
            "node_name() must read from the Python cache, not the "
            "LineEdit text — the cache is the source of truth that "
            "survives any Qt lazy-render edge case on non-active "
            "tabs.")


@unittest.skipIf(conftest._REAL_MAYA,
    "mock-dependent (cmds + PySide stubs)")
class TestM_IDEMPOTENT_RuntimeBehavior(unittest.TestCase):

    def test_dedup_helper_returns_true_for_existing_wire(self):
        from RBFtools import core
        with mock.patch.object(core, "cmds") as mc, \
             mock.patch.object(core, "get_shape",
                               return_value="rbfShape"):
            mc.listConnections.return_value = ["rbfShape.input[0]"]
            self.assertTrue(
                core._src_already_drives_node("boneA.tx", "rbf1"))

    def test_dedup_helper_false_when_no_overlap(self):
        from RBFtools import core
        with mock.patch.object(core, "cmds") as mc, \
             mock.patch.object(core, "get_shape",
                               return_value="rbfShape"):
            mc.listConnections.return_value = [
                "otherNode.input[0]"]
            self.assertFalse(
                core._src_already_drives_node("boneA.tx", "rbf1"))

    def test_dedup_helper_false_when_no_connections(self):
        from RBFtools import core
        with mock.patch.object(core, "cmds") as mc, \
             mock.patch.object(core, "get_shape",
                               return_value="rbfShape"):
            mc.listConnections.return_value = None
            self.assertFalse(
                core._src_already_drives_node("boneA.tx", "rbf1"))


@unittest.skipIf(conftest._REAL_MAYA,
    "mock-dependent (PySide stubs)")
class TestM_BONE_NAME_CACHE_RuntimeBehavior(unittest.TestCase):

    def test_node_name_returns_cache_after_set(self):
        from RBFtools.ui.widgets.tabbed_source_editor import (
            _SourceTabContent)
        c = _SourceTabContent.__new__(_SourceTabContent)
        c._node_name = ""
        c._field_node = mock.MagicMock()
        _SourceTabContent.set_node_name(c, "boneAlpha")
        self.assertEqual(_SourceTabContent.node_name(c), "boneAlpha")

    def test_node_name_immune_to_lineedit_state(self):
        # Even if the QLineEdit text is somehow desynced (the
        # Qt-lazy-load scenario the user reported), node_name()
        # returns the cached Python value.
        from RBFtools.ui.widgets.tabbed_source_editor import (
            _SourceTabContent)
        c = _SourceTabContent.__new__(_SourceTabContent)
        c._node_name = "bone_from_cache"
        c._field_node = mock.MagicMock()
        c._field_node.text.return_value = ""   # LineEdit lies
        self.assertEqual(_SourceTabContent.node_name(c),
                         "bone_from_cache")


if __name__ == "__main__":
    unittest.main()
