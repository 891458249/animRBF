# ----------------------------------------------------------------------
# install.py
#
# Installation script for the RBF Tools plugin.
# Copies the module to the Maya user preferences and creates
# the .mod file so Maya can discover the plugin at startup.
#
# Usage (drag-and-drop into Maya, or run in Script Editor):
#
#   # --- Option A: Drag this file into a Maya viewport ---
#
#   # --- Option B: Run from Maya Script Editor (Python) ---
#   exec(open(r"X:/Plugins/weightDriver/install.py").read())
#
#   # --- Option C: Run from command line (mayapy) ---
#   mayapy install.py
#
# ----------------------------------------------------------------------

from __future__ import print_function

import errno
import os
import platform
import shutil
import stat
import sys
import time

# ----------------------------------------------------------------------
# constants
# ----------------------------------------------------------------------

INSTALL_ROOT = os.path.dirname(os.path.realpath(__file__))
MODULE_NAME = "RBFtools"
MODULE_VERSION = "4.0.1"
MODULES_SRC = os.path.join(INSTALL_ROOT, "modules")

PLUGIN_NAME = "RBFtools"

# M_P0_INSTALL_DUAL_VERSION (2026-04-30): MAYA_VERSIONS is now
# resolved dynamically by _discover_maya_versions (defined below
# after _current_platform). Pre-fix this was a hardcoded ["2022"]
# list that silently dropped the 2025 routing line from the
# generated .mod file when Maya 2025 binaries were added to the
# repo. The constant assignment lives at module-import time, near
# the bottom of the constants section, so other code keeps
# referencing MAYA_VERSIONS unchanged.
PLATFORMS = {
    "Windows": "win64",
    "Darwin":  "macOS",
    "Linux":   "linux64",
}


# ----------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------

def _current_platform():
    """Return the Maya-style platform string for the running OS."""
    return PLATFORMS.get(platform.system(), "linux64")


def _maya_platform_tag():
    """Return the PLATFORM tag used in .mod files."""
    tags = {"win64": "win64", "macOS": "mac", "linux64": "linux"}
    return tags.get(_current_platform(), "linux")


def _discover_maya_versions():
    """M_P0_INSTALL_DUAL_VERSION (2026-04-30): mirror
    ``dragDropInstaller.getMayaVersions``'s design — dynamically
    scan ``modules/<MODULE_NAME>/plug-ins/<platform>/`` for
    available Maya version subdirs. Replaces the legacy hardcoded
    ``["2022"]`` constant which silently dropped the 2025 routing
    line from the generated ``RBFtools.mod`` file once Maya 2025
    binaries landed in the repo. Future Maya 2026 / 2027
    additions are picked up automatically with no install.py
    edit required.

    Filtering: only include subdirs that look like a Maya version
    (4-digit numeric name) AND actually carry a plugin binary
    (.mll / .so / .bundle). An empty version directory (created
    but never built) is skipped so the generated .mod does not
    point at a broken route.

    Defensive fallback: if the plug-ins directory is missing or
    the scan raises (read-permission corner case), return
    ``["2022", "2025"]`` so the installer can still produce a
    usable .mod for the historically-common 2-version case.
    """
    plat = _current_platform()
    plug_dir = os.path.join(
        MODULES_SRC, MODULE_NAME, "plug-ins", plat)
    try:
        entries = sorted(os.listdir(plug_dir))
    except (OSError, FileNotFoundError):
        return ["2022", "2025"]
    result = []
    for v in entries:
        sub = os.path.join(plug_dir, v)
        if not (os.path.isdir(sub)
                and v.isdigit()
                and len(v) == 4):
            continue
        try:
            files = os.listdir(sub)
        except OSError:
            continue
        if any(f.lower().endswith((".mll", ".so", ".bundle"))
               for f in files):
            result.append(v)
    return result if result else ["2022", "2025"]


# Resolve dynamically at module import. Other code in this file
# keeps the legacy ``MAYA_VERSIONS`` reference unchanged.
MAYA_VERSIONS = _discover_maya_versions()


def _default_modules_dir():
    """Return the default Maya modules directory for the current user.

    On Windows : ~/Documents/maya/modules
    On macOS   : ~/Library/Preferences/Autodesk/maya/modules
    On Linux   : ~/maya/modules
    """
    home = os.path.expanduser("~")
    sys_name = platform.system()
    if sys_name == "Windows":
        docs = os.path.join(home, "Documents")
        if os.path.isdir(os.path.join(home, "maya")):
            return os.path.join(home, "maya", "modules")
        return os.path.join(docs, "maya", "modules")
    elif sys_name == "Darwin":
        return os.path.join(home, "Library", "Preferences",
                            "Autodesk", "maya", "modules")
    else:
        return os.path.join(home, "maya", "modules")


def _ensure_dir(path):
    """Create directory (and parents) if it does not exist."""
    try:
        os.makedirs(path)
    except OSError as exc:
        if exc.errno != errno.EEXIST:
            raise


def _remove_tree(path):
    """Safely remove a directory tree.

    Uses an onerror handler to force-remove read-only or locked files
    on Windows.
    """
    if not os.path.isdir(path):
        return

    def _on_rm_error(func, fpath, exc_info):
        """Try to fix permission and retry once."""
        os.chmod(fpath, stat.S_IWRITE)
        func(fpath)

    shutil.rmtree(path, onerror=_on_rm_error)


def _copy_tree(src, dst):
    """Copy *src* directory to *dst*, removing *dst* first if it exists.

    Retries removal up to 3 times with a short delay to handle
    Windows file locks from recently unloaded Maya plugins.
    """
    for attempt in range(3):
        try:
            _remove_tree(dst)
            break
        except PermissionError:
            if attempt < 2:
                time.sleep(1)
            else:
                raise
    shutil.copytree(src, dst)


def _flatten_icons(icons_dir):
    """Move files from icon sub-directories to the top-level icons dir.

    Required on Linux where Maya does not recursively search icon paths.
    """
    if not os.path.isdir(icons_dir):
        return
    for folder in os.listdir(icons_dir):
        folder_path = os.path.join(icons_dir, folder)
        if os.path.isdir(folder_path):
            for item in os.listdir(folder_path):
                if not item.startswith("."):
                    src = os.path.join(folder_path, item)
                    dst = os.path.join(icons_dir, item)
                    if not os.path.exists(dst):
                        shutil.move(src, icons_dir)
            _remove_tree(folder_path)


# ----------------------------------------------------------------------
# .mod file generation
# ----------------------------------------------------------------------

def _build_mod_content(content_path):
    """Return the text for the RBFtools.mod file.

    *content_path* is where the module content folder lives, e.g.
    ``<maya-modules>/RBFtools``.
    """
    plat = _current_platform()
    plat_tag = _maya_platform_tag()
    recursive_icons = (plat != "linux64")

    lines = []
    for ver in MAYA_VERSIONS:
        plug_dir = os.path.join(MODULES_SRC, MODULE_NAME,
                                "plug-ins", plat, ver)
        if not os.path.isdir(plug_dir):
            continue

        lines.append("+ MAYAVERSION:{ver} PLATFORM:{plat} {name} {version} {path}".format(
            ver=ver, plat=plat_tag, name=MODULE_NAME,
            version=MODULE_VERSION, path=content_path))
        lines.append("plug-ins: plug-ins/{plat}/{ver}".format(plat=plat, ver=ver))

        if recursive_icons:
            lines.append("[r] icons: icons")
        else:
            lines.append("icons: icons")

        lines.append("[r] scripts: scripts")
        lines.append("")

    return "\n".join(lines) + "\n"


# ----------------------------------------------------------------------
# core install / uninstall
# ----------------------------------------------------------------------

def install(install_dir=None, mod_dir=None, verbose=True):
    """Install the RBF Tools module.

    Parameters
    ----------
    install_dir : str or None
        Where to copy the module content folder.  Defaults to
        ``<maya-modules>/RBFtools``.
    mod_dir : str or None
        Where to write the ``.mod`` file.  Defaults to the same parent
        as *install_dir*.
    verbose : bool
        Print progress messages.

    Returns
    -------
    bool
        True on success.
    """
    log = print if verbose else (lambda *a, **k: None)

    modules_base = os.path.normpath(_default_modules_dir())
    if install_dir is None:
        install_dir = os.path.normpath(os.path.join(modules_base, MODULE_NAME))
    else:
        install_dir = os.path.normpath(install_dir)
    if mod_dir is None:
        mod_dir = os.path.normpath(os.path.dirname(install_dir))
    else:
        mod_dir = os.path.normpath(mod_dir)

    source = os.path.join(MODULES_SRC, MODULE_NAME)
    if not os.path.isdir(source):
        log("[ERROR] Source folder not found: {}".format(source))
        return False

    log("=" * 60)
    log("  RBF Tools Installer")
    log("=" * 60)
    log("")
    log("  Source       : {}".format(source))
    log("  Install to   : {}".format(install_dir))
    log("  .mod file in : {}".format(mod_dir))
    log("")

    # --- hot-teardown if running inside Maya ---
    if _in_maya():
        _hot_teardown(log)

    # --- copy content ---
    log("[1/4] Copying module content ...")
    _ensure_dir(os.path.dirname(install_dir))
    _copy_tree(source, install_dir)
    log("      -> {}".format(install_dir))

    # Flatten icons on Linux
    if _current_platform() == "linux64":
        _flatten_icons(os.path.join(install_dir, "icons"))
        log("      -> Flattened icons for Linux.")

    # --- write .mod file ---
    log("[2/4] Writing .mod file ...")
    _ensure_dir(mod_dir)
    mod_path = os.path.join(mod_dir, MODULE_NAME + ".mod")
    mod_content = _build_mod_content(install_dir)
    with open(mod_path, "w") as fh:
        fh.write(mod_content)
    log("      -> {}".format(mod_path))

    # --- hot-activate if running inside Maya ---
    if _in_maya():
        log("[3/4] Activating plugin (hot install) ...")
        _hot_activate(install_dir, log)
        log("[4/4] Installation complete! RBF Tools is ready to use.")
    else:
        log("[3/4] Skipped (not running inside Maya).")
        log("[4/4] Installation complete!")
        log("      Start Maya and RBF Tools will be available.")
    log("")

    return True


def uninstall(install_dir=None, mod_dir=None, verbose=True):
    """Remove a previous RBF Tools installation.

    Parameters
    ----------
    install_dir : str or None
        The module content folder to remove.
    mod_dir : str or None
        The folder containing the .mod file.
    verbose : bool
        Print progress messages.

    Returns
    -------
    bool
        True on success.
    """
    log = print if verbose else (lambda *a, **k: None)

    modules_base = os.path.normpath(_default_modules_dir())
    if install_dir is None:
        install_dir = os.path.normpath(os.path.join(modules_base, MODULE_NAME))
    else:
        install_dir = os.path.normpath(install_dir)
    if mod_dir is None:
        mod_dir = os.path.normpath(os.path.dirname(install_dir))
    else:
        mod_dir = os.path.normpath(mod_dir)

    log("=" * 60)
    log("  RBF Tools Uninstaller")
    log("=" * 60)
    log("")

    # --- hot-teardown: menu, plugin, paths, modules ---
    if _in_maya():
        _hot_teardown(log)

    mod_path = os.path.normpath(os.path.join(mod_dir, MODULE_NAME + ".mod"))
    if os.path.isfile(mod_path):
        os.remove(mod_path)
        log("  Removed .mod file : {}".format(mod_path))
    else:
        log("  No .mod file found at: {}".format(mod_path))

    if os.path.isdir(install_dir):
        _remove_tree(install_dir)
        log("  Removed content   : {}".format(install_dir))
    else:
        log("  No content folder found at: {}".format(install_dir))

    log("")
    log("  Uninstall complete. RBF Tools has been fully removed.")
    log("")

    return True


# ----------------------------------------------------------------------
# Maya integration helpers
# ----------------------------------------------------------------------

# Python modules that belong to RBF Tools and should be purged from
# sys.modules on teardown so they can be freshly imported afterwards.
_OWN_MODULES = [
    "RBFtools", "RBFtoolsUI", "RBFtoolsMenu",
    "weightDriverMenu", "weightDriverUI",
]


def _in_maya():
    """Return True if running inside Maya."""
    try:
        import maya.cmds  # noqa: F401
        return True
    except ImportError:
        return False


def _hot_teardown(log):
    """Fully tear down a live RBF Tools session inside Maya.

    1. Remove the top-level menu.
    2. Close any open RBF Tools windows.
    3. Unload the compiled plugin (flushes undo first).
    4. Remove scripts path from sys.path.
    5. Purge our Python modules from sys.modules.
    """
    import maya.cmds as cmds

    # 1 -- Remove menu
    try:
        import RBFtoolsMenu
        RBFtoolsMenu.remove()
        log("  Removed RBF Tools menu.")
    except Exception:
        # Menu module might not be importable yet; remove manually.
        if cmds.menu("RBFtoolsMainMenu", exists=True):
            cmds.deleteUI("RBFtoolsMainMenu")
            log("  Removed RBF Tools menu.")

    # 2 -- Close windows (legacy cmds windows + new Qt window)
    for win in ("RBFtoolsMainUI", "weightDriverMainUI",
                "weightDriverEditRBFWin", "RBFtoolsEditRBFWin"):
        if cmds.window(win, exists=True):
            cmds.deleteUI(win)
            log("  Closed window: {}".format(win))
    # Close the new Qt-based main window
    try:
        from RBFtools.ui.compat import QtWidgets
        app = QtWidgets.QApplication.instance()
        if app:
            from RBFtools.constants import WINDOW_OBJECT
            existing = app.findChild(QtWidgets.QMainWindow, WINDOW_OBJECT)
            if existing:
                existing.close()
                existing.deleteLater()
                log("  Closed Qt window: {}".format(WINDOW_OBJECT))
    except Exception:
        pass

    # 3 -- Delete all RBFtools nodes so plugin can be unloaded
    if cmds.pluginInfo(PLUGIN_NAME, query=True, loaded=True):
        wd_nodes = cmds.ls(type="RBFtools") or []
        if wd_nodes:
            # Delete the transform parents (takes shape nodes with them)
            to_delete = []
            for n in wd_nodes:
                parents = cmds.listRelatives(n, parent=True) or []
                to_delete.extend(parents if parents else [n])
            if to_delete:
                cmds.delete(to_delete)
                log("  Deleted {} RBFtools node(s).".format(len(wd_nodes)))

        # 4 -- Unload plugin
        log("  Unloading plugin ...")
        cmds.flushUndo()
        try:
            cmds.unloadPlugin(PLUGIN_NAME)
            log("  -> Plugin unloaded.")
            time.sleep(0.5)  # Let Windows release .mll file lock
        except Exception as exc:
            # Force unload as last resort
            try:
                cmds.unloadPlugin(PLUGIN_NAME, force=True)
                log("  -> Plugin force-unloaded.")
                time.sleep(0.5)  # Let Windows release .mll file lock
            except Exception:
                log("  [WARNING] Could not unload plugin: {}".format(exc))

    # 4 -- Remove scripts paths from sys.path
    new_path = []
    for p in sys.path:
        normed = os.path.normpath(p)
        if MODULE_NAME in normed and "scripts" in normed:
            log("  Removed from sys.path: {}".format(p))
        else:
            new_path.append(p)
    sys.path[:] = new_path

    # 5 -- Purge Python modules
    for mod_name in list(sys.modules.keys()):
        for own in _OWN_MODULES:
            if mod_name == own or mod_name.startswith(own + "."):
                del sys.modules[mod_name]
                log("  Purged module: {}".format(mod_name))
                break


def _hot_activate(install_dir, log):
    """Activate RBF Tools live inside the running Maya session.

    1. Add the scripts directory to sys.path.
    2. Add the icons directory to XBMLANGPATH.
    3. Add the correct plugin directory to MAYA_PLUG_IN_PATH.
    4. Load the compiled plugin.
    5. Create the top-level menu.
    """
    import maya.cmds as cmds
    import maya.mel as mel

    install_dir = os.path.normpath(install_dir)
    scripts_dir = os.path.normpath(os.path.join(install_dir, "scripts"))
    icons_dir = os.path.normpath(os.path.join(install_dir, "icons"))
    maya_ver = str(cmds.about(version=True))
    plat = _current_platform()
    plugin_dir = os.path.normpath(os.path.join(install_dir, "plug-ins", plat, maya_ver))

    # 1 -- scripts: remove any stale entries first, then force-insert at front
    sys.path[:] = [p for p in sys.path
                   if os.path.normpath(p) != scripts_dir]
    sys.path.insert(0, scripts_dir)
    log("      sys.path    += {}".format(scripts_dir))

    # 2 -- icons
    sep = ";" if plat == "win64" else ":"
    xbm = os.environ.get("XBMLANGPATH", "")
    if icons_dir not in xbm:
        os.environ["XBMLANGPATH"] = icons_dir + sep + xbm
    log("      XBMLANGPATH += {}".format(icons_dir))

    # 3 -- plugin path
    plug_env = os.environ.get("MAYA_PLUG_IN_PATH", "")
    if plugin_dir not in plug_env:
        os.environ["MAYA_PLUG_IN_PATH"] = plugin_dir + sep + plug_env
    log("      PLUG_IN_PATH += {}".format(plugin_dir))

    # 4 -- load plugin
    try:
        cmds.loadPlugin(PLUGIN_NAME)
        log("      Plugin loaded: {}".format(PLUGIN_NAME))
    except Exception as exc:
        log("      [WARNING] Could not load plugin: {}".format(exc))

    # 5 -- verify imports work
    try:
        import RBFtools  # noqa: F401
        log("      Verified: RBFtools package importable.")
    except ImportError as exc:
        log("      [WARNING] RBFtools not importable: {}".format(exc))
        log("      sys.path[0] = {}".format(sys.path[0] if sys.path else "EMPTY"))

    # 6 -- create menu
    try:
        import RBFtoolsMenu
        try:
            reload(RBFtoolsMenu)
        except NameError:
            import importlib
            importlib.reload(RBFtoolsMenu)
        RBFtoolsMenu.create()
        log("      RBF Tools menu created.")
    except Exception as exc:
        log("      [WARNING] Could not create menu: {}".format(exc))


# ----------------------------------------------------------------------
# Maya drag-and-drop entry point
# ----------------------------------------------------------------------

def _find_existing_installation():
    """Search known module paths for an existing RBF Tools installation.

    Returns (install_dir, mod_dir) if found, or (None, None).
    """
    default_dir = os.path.normpath(_default_modules_dir())
    default_install = os.path.normpath(os.path.join(default_dir, MODULE_NAME))
    default_mod = os.path.normpath(os.path.join(default_dir, MODULE_NAME + ".mod"))

    if os.path.isdir(default_install) or os.path.isfile(default_mod):
        return default_install, default_dir

    # Also check MAYA_MODULE_PATH for non-default locations.
    sep = ";" if _current_platform() == "win64" else ":"
    env_paths = os.environ.get("MAYA_MODULE_PATH", "")
    for mod_path in env_paths.split(sep):
        if not mod_path or not os.path.isdir(mod_path):
            continue
        mod_file = os.path.normpath(os.path.join(mod_path, MODULE_NAME + ".mod"))
        if os.path.isfile(mod_file):
            content_dir = os.path.normpath(os.path.join(mod_path, MODULE_NAME))
            return content_dir, os.path.normpath(mod_path)

    return None, None


def onMayaDroppedPythonFile(*args, **kwargs):
    """Called automatically when this file is dragged into a Maya viewport."""
    if not _in_maya():
        return

    import maya.cmds as cmds

    existing_dir, existing_mod_dir = _find_existing_installation()
    already_installed = existing_dir is not None

    if already_installed:
        # ----- Already installed: show reinstall / uninstall dialog -----
        result = cmds.confirmDialog(
            title="RBF Tools",
            message=(
                "RBF Tools is already installed.\n\n"
                "  Install path:  {}\n\n"
                "What would you like to do?"
            ).format(existing_dir),
            button=["Reinstall", "Uninstall", "Cancel"],
            defaultButton="Reinstall",
            cancelButton="Cancel")

        if result == "Reinstall":
            install(install_dir=existing_dir, mod_dir=existing_mod_dir)
            cmds.confirmDialog(
                title="RBF Tools",
                message="Reinstall complete.\n\n"
                        "RBF Tools is ready to use.",
                button=["OK"])
        elif result == "Uninstall":
            uninstall(install_dir=existing_dir, mod_dir=existing_mod_dir)
            cmds.confirmDialog(
                title="RBF Tools",
                message="Uninstall complete.\n\n"
                        "RBF Tools has been fully removed.",
                button=["OK"])

    else:
        # ----- Not installed: fresh install -----
        default_dir = _default_modules_dir()
        _ensure_dir(default_dir)

        custom = cmds.confirmDialog(
            title="RBF Tools",
            message="Install to default location?\n\n{}".format(
                os.path.join(default_dir, MODULE_NAME)),
            button=["Install", "Choose Path", "Cancel"],
            defaultButton="Install",
            cancelButton="Cancel")

        if custom == "Cancel":
            return
        elif custom == "Choose Path":
            paths = cmds.fileDialog2(
                caption="Select Module Install Directory",
                startingDirectory=default_dir,
                fileMode=3, okCaption="Select")
            if not paths:
                return
            install_dir = os.path.join(paths[0], MODULE_NAME)
            mod_dir = paths[0]
        else:
            install_dir = os.path.join(default_dir, MODULE_NAME)
            mod_dir = default_dir

        install(install_dir=install_dir, mod_dir=mod_dir)
        cmds.confirmDialog(
            title="RBF Tools",
            message="Installation complete.\n\n"
                    "RBF Tools is ready to use.\n"
                    "Check the top menu bar for the 'RBF Tools' menu.",
            button=["OK"])


# ----------------------------------------------------------------------
# command-line entry point (for mayapy or standalone Python)
# ----------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Install or uninstall the RBF Tools Maya plugin.")
    parser.add_argument("action", nargs="?", default="install",
                        choices=["install", "uninstall"],
                        help="Action to perform (default: install)")
    parser.add_argument("--install-dir",
                        help="Override the module content install path")
    parser.add_argument("--mod-dir",
                        help="Override the .mod file output directory")
    parser.add_argument("-q", "--quiet", action="store_true",
                        help="Suppress progress output")

    args = parser.parse_args()

    if args.action == "install":
        success = install(
            install_dir=args.install_dir,
            mod_dir=args.mod_dir,
            verbose=not args.quiet)
    else:
        success = uninstall(
            install_dir=args.install_dir,
            mod_dir=args.mod_dir,
            verbose=not args.quiet)

    sys.exit(0 if success else 1)
