# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for RBFtools standalone installer GUI.

Run via ``tools/build_installer.bat`` or directly:

    python -m PyInstaller tools/build_installer.spec --noconfirm --clean

Produces ``dist/RBFtoolsInstaller.exe`` — a single self-contained
binary that ships:

  * tkinter GUI (Python stdlib, bundled by PyInstaller)
  * install.py + installer_gui.py (the install logic + UI)
  * modules/ (the entire RBFtools content tree, including
    plug-ins/win64/<ver>/RBFtools.mll for every supported Maya
    version, plus scripts/ + icons/)
  * resources/module_template.mod (used by install.py if present)

Distribution: copy dist/RBFtoolsInstaller.exe to any Windows
machine — no Python installation needed on the target.
"""

import os

block_cipher = None
# M_P0_REPO_ROOT_TIDY (2026-05-01): SPEC is a global injected by
# PyInstaller pointing at this .spec file's absolute path. Resolve
# the repo root from SPEC (one level up from tools/) so the build
# works regardless of cwd at invocation time.
HERE = os.path.dirname(os.path.dirname(os.path.abspath(SPEC)))


a = Analysis(
    [os.path.join(HERE, 'installer_gui.py')],
    pathex=[HERE],
    binaries=[],
    datas=[
        # Bundle the entire modules/ tree so the installer can
        # copy the module content into the user's Maya modules
        # directory at runtime. The (src, dst) tuple's dst is
        # relative to the unpacked _MEIPASS root at runtime.
        (os.path.join(HERE, 'modules'), 'modules'),
        (os.path.join(HERE, 'resources'), 'resources'),
    ],
    hiddenimports=[
        # M_P0_INSTALLER_INLINE (2026-05-01): install.py was
        # folded into installer_gui.py; no separate hidden
        # import needed.
        'installer_gui',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Trim the bundle: we don't need numpy / matplotlib / Maya
        # SDK pulls. Tkinter is auto-detected by PyInstaller.
        'numpy',
        'matplotlib',
        'maya',
        'maya.cmds',
        'maya.api',
        'pytest',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(
    a.pure, a.zipped_data,
    cipher=block_cipher,
)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='RBFtoolsInstaller',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,    # windowed app — no black cmd window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # Windows file-explorer / taskbar icon. PyInstaller 6.x
    # accepts a .png path and converts internally; for older
    # versions provide a .ico instead. The same image is also
    # loaded at runtime via tk.PhotoImage(file=...) so the
    # title-bar matches the file-explorer thumbnail.
    icon=os.path.join(
        HERE, 'modules', 'RBFtools', 'icons', 'RBFtools.png'),
)
