# -*- coding: utf-8 -*-
"""RBFtools standalone installer GUI (M_P0_INSTALLER_EXE_GUI).

Tkinter-based front-end on top of ``install.py``'s public
``install`` / ``uninstall`` functions. Designed to be packaged
into a single self-contained .exe via PyInstaller (see
``build_installer.spec`` + ``build_installer.bat``).

Workflow
--------
1. Detect every Maya version installed on the host machine
   (filesystem default install paths + Windows-registry fallback).
2. Discover every Maya version the repo carries pre-built binaries
   for (mirrors ``install._discover_maya_versions``).
3. Show the intersection as a checkbox list — the user picks any
   subset.
4. Radio: Install / Uninstall.
5. Run -> dispatch to ``install.install(versions=...)`` /
   ``install.uninstall(...)`` with the GUI's selection. Logs are
   redirected from stdout into a ScrolledText panel so the TD sees
   live progress.

Headless mode
-------------
Pass ``--headless`` to skip the GUI and install on every detected
Maya version. Useful for CI / silent deployment scripts:

    RBFtoolsInstaller.exe --headless

Design constraints
------------------
* tkinter only — Python stdlib, zero external runtime dependency
  beyond what PyInstaller's --onefile bundle ships.
* Reuses ``install.py`` for every filesystem mutation. No
  duplicate copy/remove logic — the dragDropInstaller-vs-install.py
  drift documented in M_P0_INSTALL_DUAL_VERSION + M_P0_DRAGDROP_
  PERMERR_RETRY is the cautionary tale this module follows.
"""

from __future__ import absolute_import

import io
import os
import sys
import threading


# Repository root resolved relative to this file. PyInstaller's
# --onefile bundle exposes _MEIPASS as the unpacked-resources dir;
# we fall back to __file__'s parent for a normal Python run.
def _repo_root():
    if hasattr(sys, "_MEIPASS"):
        return sys._MEIPASS
    return os.path.dirname(os.path.realpath(__file__))


_REPO_ROOT = _repo_root()
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)


# ----------------------------------------------------------------------
# Dark theme palette + asset paths.
#
# Self-contained — no external theme library (sv-ttk / customtkinter
# would bloat the PyInstaller bundle and are not stdlib). The
# palette below is hand-tuned against ttk's "clam" base theme which
# is the most customizable of the three built-ins.
# ----------------------------------------------------------------------


_DARK = {
    "bg":              "#2b2b2b",   # window + frame background
    "fg":              "#e0e0e0",   # default text
    "fg_muted":        "#9a9a9a",   # hint / "leave blank for default" label
    "fg_warn":         "#e6a040",   # "no Maya detected" warning
    "field_bg":        "#3c3c3c",   # entry / log input background
    "field_fg":        "#e6e6e6",
    "border":          "#4a4a4a",   # separator + entry border
    "btn_bg":          "#404040",
    "btn_bg_hover":    "#505050",
    "btn_bg_pressed":  "#5a5a5a",
    "log_bg":          "#1e1e1e",   # darker than field for code-area feel
    "log_fg":          "#d0d0d0",
    "select_bg":       "#264f78",   # VS Code blue selection
    "indicator":       "#4ea1ff",   # checkbox / radio indicator
}


def _icon_path():
    """Return the absolute path to the window icon, or None if it
    cannot be located. Searches both the live repo layout and the
    PyInstaller _MEIPASS unpacked-resources directory so the same
    code path works in both dev runs and the bundled .exe."""
    candidates = [
        os.path.join(
            _REPO_ROOT, "modules", "RBFtools", "icons",
            "RBFtools.png"),
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    return None


# ----------------------------------------------------------------------
# i18n — minimal embedded EN + ZH dictionary.
#
# Self-contained so the standalone .exe does not need to import the
# project's full ui/i18n.py (which would pull maya / PySide via
# transitive imports). Keys cover every user-visible string in the
# installer GUI; missing keys fall back to the EN value.
# ----------------------------------------------------------------------


_TR = {
    "en": {
        "window_title":     "RBFtools Installer",
        "language_label":   "Language:",
        "lang_en":          "English",
        "lang_zh":          "中文",
        "header_versions":  "Detected Maya versions on this machine:",
        "no_maya_detected":
            "  (none — install Maya 2022 / 2025 first, "
            "or check repo plug-ins/win64/<ver>/ "
            "RBFtools.mll exists)",
        "version_row":      "Maya {ver}   ({path})",
        "action_label":     "Action:",
        "action_install":   "Install",
        "action_uninstall": "Uninstall",
        "install_path":     "Install path:",
        "install_path_hint":
            "  (leave blank for default: "
            "<user>/Documents/maya/modules/RBFtools)",
        "log_label":        "Progress log:",
        "btn_run":          "Run",
        "btn_close":        "Close",
        "err_no_version":
            "[ERROR] No Maya version selected; check at "
            "least one box.",
        "log_done_install": "[DONE] install ok={ok}",
        "log_done_uninstall": "[DONE] uninstall ok={ok}",
        "log_fatal":        "[FATAL] {exc}",
        "headless_warn":    "[WARN] No installable Maya version detected.",
        "headless_running": "[HEADLESS] Installing for: {versions}",
    },
    "zh": {
        "window_title":     "RBFtools 安装器",
        "language_label":   "语言：",
        "lang_en":          "English",
        "lang_zh":          "中文",
        "header_versions":  "本机检测到的 Maya 版本：",
        "no_maya_detected":
            "  （未检测到——请先安装 Maya 2022 / 2025，"
            "或确认仓库 plug-ins/win64/<版本>/RBFtools.mll 存在）",
        "version_row":      "Maya {ver}   ({path})",
        "action_label":     "操作：",
        "action_install":   "安装",
        "action_uninstall": "卸载",
        "install_path":     "安装路径：",
        "install_path_hint":
            "  （留空使用默认：<用户>/Documents/maya/modules/RBFtools）",
        "log_label":        "进度日志：",
        "btn_run":          "运行",
        "btn_close":        "关闭",
        "err_no_version":
            "[错误] 未选中任何 Maya 版本；请至少勾选一项。",
        "log_done_install": "[完成] 安装 ok={ok}",
        "log_done_uninstall": "[完成] 卸载 ok={ok}",
        "log_fatal":        "[严重错误] {exc}",
        "headless_warn":    "[警告] 未检测到可安装的 Maya 版本。",
        "headless_running": "[无界面模式] 正在安装：{versions}",
    },
}


def _tr(lang, key, **fmt):
    """Look up *key* in the active language; fall back to EN if
    missing. ``fmt`` keyword arguments are str.format applied to
    the result."""
    table = _TR.get(lang) or _TR["en"]
    text = table.get(key)
    if text is None:
        text = _TR["en"].get(key, key)
    if fmt:
        try:
            return text.format(**fmt)
        except (KeyError, IndexError):
            return text
    return text


# ----------------------------------------------------------------------
# Maya version detection (filesystem + registry fallback).
# ----------------------------------------------------------------------


def detect_installed_maya():
    """Return the {version: install_path} map of Maya versions
    detected on the local machine.

    Strategy:
      1. Filesystem scan of ``C:/Program Files/Autodesk/Maya<ver>/
         bin/maya.exe`` for the canonical install paths (Maya's
         default location on Windows). Catches users who installed
         to the default path without changing anything.
      2. Windows registry fallback at
         ``HKLM\\SOFTWARE\\Autodesk\\Maya\\<ver>\\Setup\\InstallPath``
         to pick up users who relocated Maya elsewhere. ``winreg``
         lookups are wrapped in broad except blocks so a missing /
         malformed key never aborts detection.

    The probe space covers Maya 2018..2030 — the realistic range
    of versions a TD might still run on Windows. Adding a future
    version (e.g. 2031) requires no code change provided the
    install path follows Autodesk's convention.
    """
    found = {}
    # Filesystem probe.
    pf = os.environ.get(
        "ProgramFiles", "C:\\Program Files")
    autodesk_root = os.path.join(pf, "Autodesk")
    if os.path.isdir(autodesk_root):
        for entry in os.listdir(autodesk_root):
            if not entry.startswith("Maya"):
                continue
            version_part = entry[len("Maya"):]
            if not (version_part.isdigit()
                    and len(version_part) == 4):
                continue
            install_path = os.path.join(autodesk_root, entry)
            maya_exe = os.path.join(
                install_path, "bin", "maya.exe")
            if os.path.exists(maya_exe):
                found[version_part] = install_path

    # Registry fallback.
    try:
        import winreg   # noqa: F401
    except ImportError:
        return found
    for version in [str(y) for y in range(2018, 2031)]:
        if version in found:
            continue
        for hive in (winreg.HKEY_LOCAL_MACHINE,
                     winreg.HKEY_CURRENT_USER):
            key_path = (
                "SOFTWARE\\Autodesk\\Maya\\{}"
                "\\Setup\\InstallPath".format(version))
            try:
                with winreg.OpenKey(hive, key_path) as key:
                    install_path, _ = winreg.QueryValueEx(
                        key, "MAYA_INSTALL_LOCATION")
            except (OSError, FileNotFoundError):
                continue
            if install_path and os.path.isdir(install_path):
                found[version] = install_path
                break
    return found


def discover_available_versions():
    """Return the list of Maya versions the repo carries pre-
    built RBFtools binaries for. Mirrors
    ``install._discover_maya_versions`` so the two paths stay in
    lock-step — drift would mean a GUI selection silently no-ops
    when the user picks a version that the repo lacks a .mll for.
    """
    import install
    return list(install._discover_maya_versions())


def compute_installable_versions():
    """Return ``[(version, maya_install_path), ...]`` for the
    intersection of detected Maya installs and repo-available
    binaries. The intersection is what the GUI should expose as
    actionable checkboxes — picking a version with no repo binary
    would route the .mod to a non-existent directory.
    """
    detected = detect_installed_maya()
    available = set(discover_available_versions())
    out = []
    for version in sorted(detected.keys()):
        if version in available:
            out.append((version, detected[version]))
    return out


# ----------------------------------------------------------------------
# Stdout redirector — captures install.py's verbose=True print
# stream into the GUI ScrolledText panel.
# ----------------------------------------------------------------------


class _StdoutRedirector(io.IOBase):
    """File-like that forwards each write to a tkinter Text widget."""

    def __init__(self, text_widget):
        self._widget = text_widget

    def writable(self):
        return True

    def write(self, msg):
        try:
            self._widget.configure(state="normal")
            self._widget.insert("end", msg)
            self._widget.see("end")
            self._widget.configure(state="disabled")
            self._widget.update_idletasks()
        except Exception:
            # GUI may have been destroyed mid-write; swallow so
            # install.py's logging never aborts on a closed panel.
            pass
        return len(msg) if msg else 0

    def flush(self):
        return None


# ----------------------------------------------------------------------
# Tkinter GUI.
# ----------------------------------------------------------------------


class InstallerWindow(object):
    """Single-window installer UI. Constructed lazily so unit tests
    can import this module without spinning up tkinter."""

    def __init__(self, root=None, language="en"):
        import tkinter as tk
        from tkinter import ttk
        from tkinter import scrolledtext

        self._tk = tk
        self._ttk = ttk
        self._root = root or tk.Tk()

        # Language state — defaults to English; the user picks via
        # the top-of-window Language radio. _retranslate() walks
        # every tracked widget on switch.
        self._lang = language if language in _TR else "en"
        self._lang_var = tk.StringVar(value=self._lang)

        self._installable = compute_installable_versions()
        self._version_vars = {}    # version -> BooleanVar
        self._mode_var = tk.StringVar(value="install")
        self._install_dir_var = tk.StringVar(value="")

        # Tracked widgets that need retranslation on language
        # switch. Each entry maps a widget to the (key, fmt) pair
        # used to populate its text. Stored in
        # ``self._tr_widgets`` so _retranslate can re-render every
        # label / button / radio without rebuilding the whole UI.
        self._tr_widgets = []

        self._root.title(_tr(self._lang, "window_title"))
        self._root.geometry("720x560")

        # Theme + icon — both are fail-soft. If the dark theme
        # configuration raises (extreme rare; only seen on truly
        # broken Tk installs) the GUI falls back to default light
        # appearance rather than crashing on startup. Same for
        # the icon: a missing file just leaves the default Tk
        # feather.
        self._apply_dark_theme()
        self._apply_window_icon()

        self._build()

    def _apply_dark_theme(self):
        """Configure ttk.Style + raw Tk option_add so every widget
        the GUI uses renders with the _DARK palette. The ``clam``
        base theme is the most customizable of the stdlib trio
        (default / clam / alt); it accepts background + bordercolor
        overrides on every widget class without falling back to
        the OS native renderer."""
        try:
            style = self._ttk.Style(self._root)
        except Exception:
            return
        try:
            style.theme_use("clam")
        except Exception:
            # clam should always be available; skip theming if not.
            return

        # Root window background (raw Tk).
        try:
            self._root.configure(bg=_DARK["bg"])
        except Exception:
            pass

        # ttk widget classes — the ones the GUI uses.
        style.configure(
            ".",
            background=_DARK["bg"],
            foreground=_DARK["fg"],
            fieldbackground=_DARK["field_bg"],
            bordercolor=_DARK["border"],
            lightcolor=_DARK["bg"],
            darkcolor=_DARK["bg"],
            insertcolor=_DARK["fg"],
        )
        style.configure(
            "TFrame", background=_DARK["bg"])
        style.configure(
            "TLabel",
            background=_DARK["bg"], foreground=_DARK["fg"])
        # "Hint" + "Warn" subclasses for the muted / warning labels.
        style.configure(
            "Hint.TLabel",
            background=_DARK["bg"], foreground=_DARK["fg_muted"])
        style.configure(
            "Warn.TLabel",
            background=_DARK["bg"], foreground=_DARK["fg_warn"])
        style.configure(
            "Header.TLabel",
            background=_DARK["bg"], foreground=_DARK["fg"],
            font=("Segoe UI", 10, "bold"))
        style.configure(
            "TCheckbutton",
            background=_DARK["bg"], foreground=_DARK["fg"],
            indicatorcolor=_DARK["field_bg"],
            focuscolor=_DARK["bg"])
        style.map(
            "TCheckbutton",
            background=[("active", _DARK["bg"])],
            foreground=[("active", _DARK["fg"])],
            indicatorcolor=[
                ("selected", _DARK["indicator"]),
                ("!selected", _DARK["field_bg"])])
        style.configure(
            "TRadiobutton",
            background=_DARK["bg"], foreground=_DARK["fg"],
            indicatorcolor=_DARK["field_bg"],
            focuscolor=_DARK["bg"])
        style.map(
            "TRadiobutton",
            background=[("active", _DARK["bg"])],
            foreground=[("active", _DARK["fg"])],
            indicatorcolor=[
                ("selected", _DARK["indicator"]),
                ("!selected", _DARK["field_bg"])])
        style.configure(
            "TButton",
            background=_DARK["btn_bg"], foreground=_DARK["fg"],
            bordercolor=_DARK["border"],
            focuscolor=_DARK["bg"])
        style.map(
            "TButton",
            background=[
                ("pressed", _DARK["btn_bg_pressed"]),
                ("active", _DARK["btn_bg_hover"])],
            foreground=[("disabled", _DARK["fg_muted"])])
        style.configure(
            "TEntry",
            fieldbackground=_DARK["field_bg"],
            foreground=_DARK["field_fg"],
            insertcolor=_DARK["fg"],
            bordercolor=_DARK["border"])
        style.configure(
            "TSeparator", background=_DARK["border"])

    def _apply_window_icon(self):
        """Load the RBF-node PNG icon as the window's title-bar +
        taskbar image. Held on ``self._icon_image`` to defeat the
        Tk garbage collector — a dropped reference would silently
        revert to the default feather icon."""
        path = _icon_path()
        if not path:
            return
        try:
            self._icon_image = self._tk.PhotoImage(file=path)
            # iconphoto(True, ...) makes the image the default for
            # this window AND every subsequent Toplevel created by
            # the same Tk root, which is what the user wants for a
            # consistent title-bar look.
            self._root.iconphoto(True, self._icon_image)
        except Exception:
            self._icon_image = None

    def _track(self, widget, key, **fmt):
        """Register *widget* for retranslation. *key* is the i18n
        key; *fmt* is the optional str.format payload (e.g. for
        the Maya-version row label that interpolates ver + path).
        Sets the widget's text to the current language immediately
        and remembers the binding for future _retranslate calls."""
        self._tr_widgets.append((widget, key, fmt))
        widget.configure(text=_tr(self._lang, key, **fmt))

    def _build(self):
        tk = self._tk
        ttk = self._ttk

        outer = ttk.Frame(self._root, padding=8)
        outer.pack(fill="both", expand=True)

        # Language switch row — first thing the user sees so the
        # whole UI is reachable in either language regardless of
        # which one defaulted at startup. tk.Radiobutton (not
        # ttk) for the same selectcolor trick used by the
        # version + mode rows below.
        lang_frame = ttk.Frame(outer)
        lang_frame.pack(fill="x", anchor="w")
        lang_lbl = ttk.Label(lang_frame, font=("Segoe UI", 9))
        lang_lbl.pack(side="left")
        self._track(lang_lbl, "language_label")
        for code in ("en", "zh"):
            rb = tk.Radiobutton(
                lang_frame,
                value=code,
                variable=self._lang_var,
                command=self._on_language_changed,
                bg=_DARK["bg"], fg=_DARK["fg"],
                activebackground=_DARK["bg"],
                activeforeground=_DARK["fg"],
                selectcolor=_DARK["bg"],
                borderwidth=0, highlightthickness=0,
                font=("Segoe UI", 9))
            rb.pack(side="left", padx=(6, 0))
            self._track(rb, "lang_{}".format(code))

        ttk.Separator(outer, orient="horizontal").pack(
            fill="x", pady=(6, 6))

        # Header.
        header_lbl = ttk.Label(outer, style="Header.TLabel")
        header_lbl.pack(anchor="w")
        self._track(header_lbl, "header_versions")

        # Version checkboxes — raw tk.Checkbutton (NOT ttk).
        # M_P0_INSTALLER_DARK_INDICATOR (2026-05-01): ttk.Check/
        # Radiobutton's indicator selected-state fill cannot be
        # overridden through ttk.Style under the clam base theme
        # (the indicator's "X" / dot mark is a Tcl element with
        # no Python-exposed color knob). The native tk widgets
        # accept a ``selectcolor`` kwarg that controls exactly
        # that filled square / circle. Setting it to the window
        # bg makes the white square disappear; the "✓" / dot
        # mark itself stays visible because it inherits from fg.
        ver_frame = ttk.Frame(outer, padding=(12, 4))
        ver_frame.pack(fill="x")
        if not self._installable:
            empty_lbl = ttk.Label(
                ver_frame, style="Warn.TLabel")
            empty_lbl.pack(anchor="w")
            self._track(empty_lbl, "no_maya_detected")
        else:
            for version, maya_path in self._installable:
                var = tk.BooleanVar(value=True)
                self._version_vars[version] = var
                rb = tk.Checkbutton(
                    ver_frame, variable=var,
                    bg=_DARK["bg"], fg=_DARK["fg"],
                    activebackground=_DARK["bg"],
                    activeforeground=_DARK["fg"],
                    selectcolor=_DARK["bg"],
                    borderwidth=0, highlightthickness=0,
                    font=("Segoe UI", 9))
                rb.pack(anchor="w")
                self._track(
                    rb, "version_row",
                    ver=version, path=maya_path)

        # Mode radio — raw tk.Radiobutton, same selectcolor trick.
        ttk.Separator(outer, orient="horizontal").pack(
            fill="x", pady=(8, 4))
        mode_frame = ttk.Frame(outer)
        mode_frame.pack(fill="x")
        action_lbl = ttk.Label(
            mode_frame, style="Header.TLabel")
        action_lbl.pack(side="left")
        self._track(action_lbl, "action_label")
        for value, key in (("install", "action_install"),
                            ("uninstall", "action_uninstall")):
            rb = tk.Radiobutton(
                mode_frame, value=value,
                variable=self._mode_var,
                bg=_DARK["bg"], fg=_DARK["fg"],
                activebackground=_DARK["bg"],
                activeforeground=_DARK["fg"],
                selectcolor=_DARK["bg"],
                borderwidth=0, highlightthickness=0,
                font=("Segoe UI", 9))
            rb.pack(side="left", padx=(8, 0))
            self._track(rb, key)

        # Install path.
        path_frame = ttk.Frame(outer, padding=(0, 8, 0, 0))
        path_frame.pack(fill="x")
        path_lbl = ttk.Label(path_frame)
        path_lbl.pack(side="left")
        self._track(path_lbl, "install_path")
        ttk.Entry(
            path_frame, textvariable=self._install_dir_var,
            width=60,
        ).pack(side="left", padx=(8, 0), fill="x", expand=True)
        hint_lbl = ttk.Label(outer, style="Hint.TLabel")
        hint_lbl.pack(anchor="w")
        self._track(hint_lbl, "install_path_hint")

        # Log panel — manual tk.Text + tk.Scrollbar so the
        # scrollbar's trough / arrow / thumb colours are
        # controllable. ScrolledText would have hidden the
        # Scrollbar behind a wrapper that defaults to OS-native
        # white-on-grey, which violates the "no white anywhere
        # except text" mandate.
        log_lbl = ttk.Label(outer, style="Header.TLabel")
        log_lbl.pack(anchor="w", pady=(8, 2))
        self._track(log_lbl, "log_label")
        log_frame = tk.Frame(outer, bg=_DARK["bg"], bd=0,
                             highlightthickness=0)
        log_frame.pack(fill="both", expand=True)
        self._log = tk.Text(
            log_frame, height=14, state="disabled",
            font=("Consolas", 9),
            bg=_DARK["log_bg"], fg=_DARK["log_fg"],
            insertbackground=_DARK["fg"],
            selectbackground=_DARK["select_bg"],
            selectforeground=_DARK["fg"],
            borderwidth=0, highlightthickness=0)
        log_scroll = tk.Scrollbar(
            log_frame, command=self._log.yview,
            bg=_DARK["btn_bg"],
            troughcolor=_DARK["log_bg"],
            activebackground=_DARK["btn_bg_hover"],
            highlightthickness=0,
            borderwidth=0,
            elementborderwidth=0,
            width=14)
        self._log.config(yscrollcommand=log_scroll.set)
        log_scroll.pack(side="right", fill="y")
        self._log.pack(side="left", fill="both", expand=True)

        # Buttons.
        btn_frame = ttk.Frame(outer, padding=(0, 8, 0, 0))
        btn_frame.pack(fill="x")
        run_btn = ttk.Button(
            btn_frame, command=self._on_run_clicked)
        run_btn.pack(side="right")
        self._track(run_btn, "btn_run")
        close_btn = ttk.Button(
            btn_frame, command=self._root.destroy)
        close_btn.pack(side="right", padx=(0, 8))
        self._track(close_btn, "btn_close")

    def _on_language_changed(self):
        """User flipped the Language radio. Re-render every
        tracked widget through the new locale's lookup. Window
        title is also refreshed."""
        new_lang = self._lang_var.get()
        if new_lang not in _TR:
            return
        self._lang = new_lang
        self._root.title(_tr(self._lang, "window_title"))
        for widget, key, fmt in self._tr_widgets:
            try:
                widget.configure(
                    text=_tr(self._lang, key, **fmt))
            except Exception:
                # Widget destroyed; skip silently.
                continue

    def _selected_versions(self):
        return [v for v, var in self._version_vars.items()
                if var.get()]

    def _resolve_install_dir(self):
        path = self._install_dir_var.get().strip()
        return path or None

    def _on_run_clicked(self):
        """Dispatch to install/uninstall on a worker thread so the
        GUI stays responsive during the file copies."""
        mode = self._mode_var.get()
        versions = self._selected_versions()
        install_dir = self._resolve_install_dir()
        if mode == "install" and not versions:
            self._log_line(_tr(self._lang, "err_no_version"))
            return
        worker = threading.Thread(
            target=self._run_action,
            args=(mode, versions, install_dir),
            daemon=True)
        worker.start()

    def _run_action(self, mode, versions, install_dir):
        import install
        # Redirect stdout for the duration of the action so
        # install.py's verbose prints land in the GUI panel.
        saved = sys.stdout
        sys.stdout = _StdoutRedirector(self._log)
        try:
            if mode == "install":
                ok = install.install(
                    install_dir=install_dir,
                    versions=versions,
                    verbose=True)
                self._log_line(
                    _tr(self._lang,
                        "log_done_install", ok=ok))
            elif mode == "uninstall":
                ok = install.uninstall(
                    install_dir=install_dir, verbose=True)
                self._log_line(
                    _tr(self._lang,
                        "log_done_uninstall", ok=ok))
        except Exception as exc:
            self._log_line(
                _tr(self._lang, "log_fatal", exc=exc))
        finally:
            sys.stdout = saved

    def _log_line(self, msg):
        try:
            self._log.configure(state="normal")
            self._log.insert("end", msg + "\n")
            self._log.see("end")
            self._log.configure(state="disabled")
        except Exception:
            pass

    def mainloop(self):
        self._root.mainloop()


# ----------------------------------------------------------------------
# Headless entry-point + main().
# ----------------------------------------------------------------------


def _headless_install_all(lang="en"):
    """Install RBFtools onto every detected Maya version that the
    repo carries a binary for. Used by CI / silent deployment.

    *lang* selects the locale for the two console messages
    (no GUI in this path)."""
    import install
    versions = [
        v for v, _ in compute_installable_versions()]
    if not versions:
        print(_tr(lang, "headless_warn"))
        return False
    print(_tr(lang, "headless_running",
              versions=", ".join(versions)))
    return install.install(versions=versions, verbose=True)


def _parse_lang_arg(argv):
    """Extract ``--lang en|zh`` from argv (default 'en'). Unknown
    locales fall back to 'en'."""
    for i, a in enumerate(argv):
        if a == "--lang" and i + 1 < len(argv):
            cand = argv[i + 1]
            if cand in _TR:
                return cand
        elif a.startswith("--lang="):
            cand = a.split("=", 1)[1]
            if cand in _TR:
                return cand
    return "en"


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    lang = _parse_lang_arg(argv)
    if "--headless" in argv:
        ok = _headless_install_all(lang=lang)
        sys.exit(0 if ok else 1)
    InstallerWindow(language=lang).mainloop()


if __name__ == "__main__":
    main()
