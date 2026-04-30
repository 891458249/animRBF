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

    def __init__(self, root=None):
        import tkinter as tk
        from tkinter import ttk
        from tkinter import scrolledtext

        self._tk = tk
        self._ttk = ttk
        self._root = root or tk.Tk()
        self._root.title("RBFtools Installer")
        self._root.geometry("680x520")

        self._installable = compute_installable_versions()
        self._version_vars = {}    # version -> BooleanVar
        self._mode_var = tk.StringVar(value="install")
        self._install_dir_var = tk.StringVar(value="")

        self._build()

    def _build(self):
        tk = self._tk
        ttk = self._ttk

        outer = ttk.Frame(self._root, padding=8)
        outer.pack(fill="both", expand=True)

        # Header.
        ttk.Label(
            outer,
            text="Detected Maya versions on this machine:",
            font=("Segoe UI", 10, "bold"),
        ).pack(anchor="w")

        # Version checkboxes.
        ver_frame = ttk.Frame(outer, padding=(12, 4))
        ver_frame.pack(fill="x")
        if not self._installable:
            ttk.Label(
                ver_frame,
                text=(
                    "  (none — install Maya 2022 / 2025 first, "
                    "or check repo plug-ins/win64/<ver>/ "
                    "RBFtools.mll exists)"),
                foreground="#A05000",
            ).pack(anchor="w")
        else:
            for version, maya_path in self._installable:
                var = tk.BooleanVar(value=True)
                self._version_vars[version] = var
                ttk.Checkbutton(
                    ver_frame,
                    text="Maya {}   ({})".format(
                        version, maya_path),
                    variable=var,
                ).pack(anchor="w")

        # Mode radio.
        ttk.Separator(outer, orient="horizontal").pack(
            fill="x", pady=(8, 4))
        mode_frame = ttk.Frame(outer)
        mode_frame.pack(fill="x")
        ttk.Label(
            mode_frame, text="Action:",
            font=("Segoe UI", 10, "bold"),
        ).pack(side="left")
        for value, label in (("install", "Install"),
                              ("uninstall", "Uninstall")):
            ttk.Radiobutton(
                mode_frame, text=label, value=value,
                variable=self._mode_var,
            ).pack(side="left", padx=(8, 0))

        # Install path.
        path_frame = ttk.Frame(outer, padding=(0, 8, 0, 0))
        path_frame.pack(fill="x")
        ttk.Label(
            path_frame, text="Install path:",
            font=("Segoe UI", 9),
        ).pack(side="left")
        ttk.Entry(
            path_frame, textvariable=self._install_dir_var,
            width=60,
        ).pack(side="left", padx=(8, 0), fill="x", expand=True)
        ttk.Label(
            outer,
            text=(
                "  (leave blank for default: "
                "<user>/Documents/maya/modules/RBFtools)"),
            foreground="#606060",
        ).pack(anchor="w")

        # Log panel.
        ttk.Label(
            outer, text="Progress log:",
            font=("Segoe UI", 10, "bold"),
        ).pack(anchor="w", pady=(8, 2))
        from tkinter import scrolledtext
        self._log = scrolledtext.ScrolledText(
            outer, height=14, state="disabled",
            font=("Consolas", 9))
        self._log.pack(fill="both", expand=True)

        # Buttons.
        btn_frame = ttk.Frame(outer, padding=(0, 8, 0, 0))
        btn_frame.pack(fill="x")
        ttk.Button(
            btn_frame, text="Run",
            command=self._on_run_clicked,
        ).pack(side="right")
        ttk.Button(
            btn_frame, text="Close",
            command=self._root.destroy,
        ).pack(side="right", padx=(0, 8))

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
            self._log_line(
                "[ERROR] No Maya version selected; check at "
                "least one box.")
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
                    "[DONE] install ok={}".format(ok))
            elif mode == "uninstall":
                ok = install.uninstall(
                    install_dir=install_dir, verbose=True)
                self._log_line(
                    "[DONE] uninstall ok={}".format(ok))
        except Exception as exc:
            self._log_line(
                "[FATAL] {}".format(exc))
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


def _headless_install_all():
    """Install RBFtools onto every detected Maya version that the
    repo carries a binary for. Used by CI / silent deployment."""
    import install
    versions = [
        v for v, _ in compute_installable_versions()]
    if not versions:
        print("[WARN] No installable Maya version detected.")
        return False
    print("[HEADLESS] Installing for: {}".format(
        ", ".join(versions)))
    return install.install(versions=versions, verbose=True)


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--headless" in argv:
        ok = _headless_install_all()
        sys.exit(0 if ok else 1)
    InstallerWindow().mainloop()


if __name__ == "__main__":
    main()
