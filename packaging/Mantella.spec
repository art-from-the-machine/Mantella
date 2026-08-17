# -*- mode: python ; coding: utf-8 -*-
"""Reproducible onedir build for Mantella.

The build preflight requires a Python installation with Tk support.  Gradio
and gradio_client are collected as complete packages because both load Python
modules and JSON metadata dynamically during UI startup.
"""

import os
from PyInstaller.utils.hooks import collect_all, collect_submodules


source_root = os.path.abspath(os.path.join(SPECPATH, os.pardir))
gradio_datas, gradio_bins, gradio_hidden = collect_all("gradio")
client_datas, client_bins, client_hidden = collect_all("gradio_client")
silero_datas, silero_bins, silero_hidden = collect_all("silero_vad_lite")
moonshine_datas, moonshine_bins, moonshine_hidden = collect_all("moonshine_onnx")
tk_hidden = collect_submodules("tkinter")
tiktoken_datas, tiktoken_bins, tiktoken_hidden = collect_all("tiktoken")
tiktoken_ext_hidden = collect_submodules("tiktoken_ext")

a = Analysis(
    [os.path.join(source_root, "main.py")],
    pathex=[source_root],
    binaries=gradio_bins + client_bins + tiktoken_bins + silero_bins + moonshine_bins,
    datas=gradio_datas + client_datas + tiktoken_datas + silero_datas + moonshine_datas,
    hiddenimports=gradio_hidden + client_hidden + tk_hidden + tiktoken_hidden + tiktoken_ext_hidden + silero_hidden + moonshine_hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Mantella",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    icon=os.path.join(source_root, "Mantella.ico"),
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    contents_directory="_internal",
)
COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="Mantella",
)
