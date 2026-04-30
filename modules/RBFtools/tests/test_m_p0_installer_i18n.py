# -*- coding: utf-8 -*-
"""M_P0_INSTALLER_I18N (2026-05-01) — installer GUI bilingual
support (EN + ZH).

User mandate 2026-05-01: the standalone RBFtoolsInstaller.exe
GUI must support runtime English / Chinese language switching.

Design (recap):

  * Self-contained ``_TR`` dict at module scope in
    installer_gui.py — EN + ZH tables, no transitive import of
    the project's ui/i18n.py (which would pull maya / PySide
    via the M_BLUEPRINT layer and bloat the PyInstaller
    bundle).
  * ``_tr(lang, key, **fmt)`` lookup helper. Missing keys fall
    back to EN; missing format args fall back to the raw
    template.
  * InstallerWindow takes a ``language`` constructor kwarg
    (default "en"). Stores tracked widgets in
    ``self._tr_widgets``; ``_on_language_changed`` re-renders
    every tracked widget through the new locale's lookup +
    refreshes the window title.
  * ``--lang en|zh`` argv flag selects the startup language for
    both GUI and headless modes.

PERMANENT GUARD T_M_P0_INSTALLER_I18N.
"""

from __future__ import absolute_import

import ast
import os
import sys
import unittest
from unittest import mock


_REPO_ROOT = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..")
)
_GUI_PY = os.path.join(_REPO_ROOT, "installer_gui.py")


def _read(p):
    with open(p, "r", encoding="utf-8") as fh:
        return fh.read()


def _import_gui():
    if _REPO_ROOT not in sys.path:
        sys.path.insert(0, _REPO_ROOT)
    if "installer_gui" in sys.modules:
        del sys.modules["installer_gui"]
    import installer_gui   # noqa: F401
    return sys.modules["installer_gui"]


# Required i18n keys — the InstallerWindow uses every one of
# these to populate a widget. EN + ZH parity is the load-bearing
# contract: a missing ZH key would silently fall back to EN and
# leave a single English string surrounded by Chinese on the
# language-switched UI.
_REQUIRED_KEYS = (
    "window_title",
    "language_label",
    "lang_en",
    "lang_zh",
    "header_versions",
    "no_maya_detected",
    "version_row",
    "action_label",
    "action_install",
    "action_uninstall",
    "install_path",
    "install_path_hint",
    "log_label",
    "btn_run",
    "btn_close",
    "err_no_version",
    "log_done_install",
    "log_done_uninstall",
    "log_fatal",
    "headless_warn",
    "headless_running",
)


# ----------------------------------------------------------------------
# PERMANENT GUARD T_M_P0_INSTALLER_I18N
# ----------------------------------------------------------------------


class T_M_P0_INSTALLER_I18N(unittest.TestCase):
    """PERMANENT GUARD — DO NOT REMOVE.

    Locks the embedded EN + ZH dictionary and the Window's
    retranslation contract."""

    @classmethod
    def setUpClass(cls):
        cls._gui_src = _read(_GUI_PY)
        cls._gui = _import_gui()

    def test_PERMANENT_a_tr_dict_present(self):
        self.assertTrue(
            hasattr(self._gui, "_TR"),
            "installer_gui MUST expose the ``_TR`` dict at "
            "module scope so PERMANENT guards + runtime lookups "
            "share the same source of truth.")
        self.assertIn("en", self._gui._TR)
        self.assertIn("zh", self._gui._TR)

    def test_PERMANENT_b_en_zh_parity_for_required_keys(self):
        en = self._gui._TR["en"]
        zh = self._gui._TR["zh"]
        for key in _REQUIRED_KEYS:
            self.assertIn(
                key, en,
                "_TR['en'] missing required key {!r}.".format(
                    key))
            self.assertIn(
                key, zh,
                "_TR['zh'] missing required key {!r} — would "
                "fall back to EN and break the language-switch "
                "experience for this widget.".format(key))
            self.assertTrue(
                en[key] and zh[key],
                "Empty translation for {!r}: en={!r}, "
                "zh={!r}.".format(key, en[key], zh[key]))

    def test_PERMANENT_c_zh_strings_actually_chinese(self):
        # Defence-in-depth: a stale ZH table that just mirrors
        # EN would silently regress the bilingual UX. Assert a
        # representative subset contains CJK codepoints.
        zh = self._gui._TR["zh"]
        cjk_keys = [
            "window_title", "header_versions",
            "action_install", "action_uninstall",
            "btn_run", "btn_close",
        ]
        for key in cjk_keys:
            text = zh[key]
            has_cjk = any(
                "一" <= ch <= "鿿" for ch in text)
            self.assertTrue(
                has_cjk,
                "_TR['zh'][{!r}] = {!r} contains no CJK "
                "characters — likely a stale EN copy.".format(
                    key, text))

    def test_PERMANENT_d_tr_helper_falls_back_on_missing_key(self):
        # _tr MUST tolerate an unknown key (returns the key
        # itself rather than raising) — defensive shape so a
        # future refactor that drops a key doesn't crash the
        # GUI.
        result = self._gui._tr("zh", "this_key_does_not_exist")
        self.assertEqual(result, "this_key_does_not_exist")

    def test_PERMANENT_e_tr_helper_falls_back_to_en_on_missing_lang(self):
        # Unknown locale -> EN.
        result = self._gui._tr("klingon", "window_title")
        self.assertEqual(result, "RBFtools Installer")

    def test_PERMANENT_f_tr_format_kwargs_applied(self):
        result = self._gui._tr(
            "en", "version_row", ver="2025", path="C:/Maya")
        self.assertIn("2025", result)
        self.assertIn("C:/Maya", result)
        result_zh = self._gui._tr(
            "zh", "version_row", ver="2025", path="C:/Maya")
        self.assertIn("2025", result_zh)
        self.assertIn("C:/Maya", result_zh)

    def test_PERMANENT_g_window_class_takes_language_kwarg(self):
        # AST guard: InstallerWindow.__init__ MUST declare a
        # ``language`` kwarg so main() can forward --lang.
        tree = ast.parse(self._gui_src)
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            if node.name != "InstallerWindow":
                continue
            for child in node.body:
                if not (isinstance(child, ast.FunctionDef)
                        and child.name == "__init__"):
                    continue
                args = [a.arg for a in child.args.args]
                self.assertIn(
                    "language", args,
                    "InstallerWindow.__init__ MUST accept a "
                    "``language`` kwarg.")
                return
        self.fail("InstallerWindow class not found.")

    def test_PERMANENT_h_retranslate_method_present(self):
        # The runtime language switch entry-point.
        self.assertIn(
            "def _on_language_changed(self):", self._gui_src,
            "InstallerWindow MUST expose "
            "_on_language_changed — Language radio command.")

    def test_PERMANENT_i_track_widget_helper_present(self):
        self.assertIn(
            "def _track(self, widget, key", self._gui_src,
            "InstallerWindow MUST expose _track helper that "
            "records each translatable widget for retranslation. "
            "Without this, switching language would only refresh "
            "a hand-maintained subset and miss future widget "
            "additions.")

    def test_PERMANENT_j_lang_arg_parser_present(self):
        # main() -> _parse_lang_arg -> InstallerWindow(language=)
        # chain MUST exist.
        self.assertIn(
            "def _parse_lang_arg(argv):", self._gui_src)
        # main MUST forward to InstallerWindow with language kwarg.
        body = self._gui_src.split(
            "def main(argv=None):"
        )[1].split("\ndef ")[0]
        self.assertIn(
            "InstallerWindow(language=", body,
            "main() MUST construct InstallerWindow with "
            "language=lang so --lang flag actually reaches the "
            "GUI.")


# ----------------------------------------------------------------------
# Mock E2E — runtime: lookup, fallback, language-switch retranslate.
# ----------------------------------------------------------------------


class TestM_P0_INSTALLER_I18N_RuntimeBehavior(unittest.TestCase):

    def test_default_language_is_en(self):
        gui = _import_gui()
        self.assertEqual(
            gui._tr("en", "btn_run"), "Run")

    def test_zh_btn_run_is_chinese(self):
        gui = _import_gui()
        text = gui._tr("zh", "btn_run")
        self.assertNotEqual(text, "Run")
        self.assertTrue(any("一" <= ch <= "鿿"
                            for ch in text))

    def test_parse_lang_arg_picks_up_double_dash_form(self):
        gui = _import_gui()
        self.assertEqual(
            gui._parse_lang_arg(["--lang", "zh"]), "zh")
        self.assertEqual(
            gui._parse_lang_arg(["--lang=zh"]), "zh")
        self.assertEqual(gui._parse_lang_arg([]), "en")
        # Unknown locale falls through to EN.
        self.assertEqual(
            gui._parse_lang_arg(["--lang", "klingon"]), "en")

    def test_parse_lang_arg_ignores_unrelated_flags(self):
        gui = _import_gui()
        self.assertEqual(
            gui._parse_lang_arg(
                ["--headless", "--lang", "zh"]),
            "zh")
        self.assertEqual(
            gui._parse_lang_arg(["--headless"]), "en")

    def test_main_headless_with_zh_lang_uses_zh_messages(self):
        gui = _import_gui()
        captured = []
        with mock.patch("builtins.print",
                        side_effect=lambda m: captured.append(m)):
            with mock.patch.object(
                    gui, "compute_installable_versions",
                    return_value=[]):
                with self.assertRaises(SystemExit):
                    gui.main(["--headless", "--lang", "zh"])
        # ZH "no Maya detected" warning fired.
        self.assertTrue(captured)
        self.assertIn(
            gui._tr("zh", "headless_warn"), captured)
        # And the EN one DID NOT fire (the whole point of --lang).
        self.assertNotIn(
            gui._tr("en", "headless_warn"), captured)

    def test_tr_format_with_extra_kwargs_does_not_raise(self):
        # Defensive: extra fmt kwargs that the template does not
        # reference MUST NOT raise. Underlying str.format with
        # **fmt would normally accept extras silently, but a
        # KeyError on a MISSING template placeholder must also
        # be tolerated by the helper.
        gui = _import_gui()
        # Template with no placeholders + fmt args = passthrough.
        result = gui._tr("en", "btn_run", ignored="x")
        self.assertEqual(result, "Run")


# ----------------------------------------------------------------------
# Tracking contract — every user-visible string in InstallerWindow
# MUST flow through _track() so retranslate covers it.
# ----------------------------------------------------------------------


class TestM_P0_INSTALLER_I18N_TrackingContract(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._gui_src = _read(_GUI_PY)

    def test_no_hardcoded_user_visible_strings_in_build(self):
        # AST walk inside InstallerWindow._build: every
        # widget.configure(text=...) or widget(text=...) call
        # MUST source the text from a _tr() call (directly or via
        # _track which calls _tr). A bare string literal as the
        # text argument is the regression shape we lock out.
        tree = ast.parse(self._gui_src)
        violations = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            if node.name != "InstallerWindow":
                continue
            for func in node.body:
                if not (isinstance(func, ast.FunctionDef)
                        and func.name == "_build"):
                    continue
                for sub in ast.walk(func):
                    if not isinstance(sub, ast.Call):
                        continue
                    for kw in sub.keywords:
                        if kw.arg != "text":
                            continue
                        # Bare string literal? regression.
                        if isinstance(kw.value, ast.Constant) \
                                and isinstance(
                                    kw.value.value, str):
                            violations.append(
                                "line {}: hardcoded text="
                                "{!r}".format(
                                    sub.lineno, kw.value.value))
        self.assertEqual(
            violations, [],
            "AST guard: InstallerWindow._build MUST NOT pass "
            "bare string literals to text= kwargs — every "
            "user-visible string flows through _tr/_track. "
            "Drift here would leave widgets in English on "
            "ZH switch.\nViolations:\n{}".format(
                "\n".join(violations)))


if __name__ == "__main__":
    unittest.main()
