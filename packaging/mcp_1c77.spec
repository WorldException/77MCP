# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for a standalone mcp-1c77 executable (onefile).

Build (on Windows, from repo root):
    uv run pyinstaller packaging/mcp_1c77.spec --clean --noconfirm

Output: dist/mcp-1c77.exe
"""

import os

from PyInstaller.utils.hooks import collect_all

# `mcp.cli` requires the optional `mcp[cli]` extra (typer/etc.); the app
# never uses the mcp CLI, and importing it during collection aborts the
# build, so it's excluded explicitly.
_SKIP_PREFIXES = ("mcp.cli",)


def _keep_submodule(name):
    return not any(name == p or name.startswith(p + ".") for p in _SKIP_PREFIXES)

ROOT = os.path.dirname(os.path.abspath(SPECPATH))
SRC = os.path.join(ROOT, "src")

datas = [
    (os.path.join(SRC, "mcp_1c77", "static", "index.html"), os.path.join("mcp_1c77", "static")),
]
binaries = []
hiddenimports = []

# mcp / starlette / uvicorn rely on dynamic/lazy imports (SSE transport,
# protocol/loop selection) that PyInstaller's static analysis won't discover
# on its own, so collect each package wholesale rather than hand-picking
# hidden imports.
for pkg in ("mcp", "starlette", "uvicorn", "pydantic"):
    pkg_datas, pkg_binaries, pkg_hiddenimports = collect_all(pkg, filter_submodules=_keep_submodule)
    datas += pkg_datas
    binaries += pkg_binaries
    hiddenimports += pkg_hiddenimports

a = Analysis(
    [os.path.join(SPECPATH, "entry.py")],
    pathex=[SRC],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="mcp-1c77",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
