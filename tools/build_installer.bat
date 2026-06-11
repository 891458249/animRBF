@echo off
REM ====================================================================
REM RBFtools standalone installer build script (M_P0_INSTALLER_EXE_GUI)
REM ====================================================================
REM
REM One-shot build: installs PyInstaller (silently, idempotent) and
REM packages installer_gui.py + install.py + modules/ + resources/
REM into a single windowed installer/RBFtoolsInstaller.exe.
REM
REM Distribution: copy installer\RBFtoolsInstaller.exe to any Windows
REM machine — no Python installation needed on the target.
REM
REM Usage:
REM   double-click this file, or run from a PowerShell / cmd prompt
REM   in the repo root.
REM ====================================================================

REM M_P0_REPO_ROOT_TIDY (2026-05-01): bat lives in tools/, so %~dp0
REM is the tools\ absolute path. Step up one level so PyInstaller
REM treats the repo root as cwd; build/ + installer/ land there.
cd /d "%~dp0..\"

echo.
echo [1/3] Ensuring PyInstaller is installed...
python -m pip install pyinstaller --quiet --disable-pip-version-check
if errorlevel 1 (
    echo [ERROR] pip install pyinstaller failed.
    pause
    exit /b 1
)

echo.
echo [2/3] Building RBFtoolsInstaller.exe ^(this takes ~30s^)...
REM M_P0_RENAME_DIST_INSTALLER (2026-05-01): override PyInstaller's
REM default ``dist/`` output dir to ``installer/`` so the artefact
REM directory name reads as its purpose (the bundled installer .exe)
REM instead of PyInstaller's generic "distribution" shorthand.
python -m PyInstaller tools\build_installer.spec --noconfirm --clean --distpath installer
if errorlevel 1 (
    echo [ERROR] PyInstaller build failed.
    pause
    exit /b 1
)

echo.
echo [3/3] Done.
echo Output: %~dp0..\installer\RBFtoolsInstaller.exe
echo.
echo Distribute that single .exe to any Windows machine and double-
echo click to install RBFtools onto user-selected Maya versions.
echo.
pause
