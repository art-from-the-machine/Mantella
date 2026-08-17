#!/usr/bin/env python3
"""Build and gate a complete Mantella onedir distribution."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


def run(command: list[str], cwd: Path) -> None:
    print("+", " ".join(command))
    subprocess.run(command, cwd=cwd, check=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--dist", type=Path, required=True)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--config-template", type=Path)
    parser.add_argument("--user-folder", type=Path)
    args = parser.parse_args()
    source = args.source.resolve()
    dist = args.dist.resolve()
    work = args.work.resolve()

    run([sys.executable, str(source / "scripts" / "validate_packaging_environment.py")], source)
    run(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            "--clean",
            str(source / "packaging" / "Mantella.spec"),
            "--distpath",
            str(dist),
            "--workpath",
            str(work),
        ],
        source,
    )

    package = dist / "Mantella"
    # Mantella resolves application data relative to the distribution working
    # directory (not PyInstaller's _internal directory). Copy tracked source
    # data as part of the build, never from a previous/rollback installation.
    source_data = source / "data"
    target_data = package / "data"
    if source_data.is_dir():
        shutil.copytree(source_data, target_data, dirs_exist_ok=True)
    source_custom_folder = source / "custom_user_folder.ini"
    if source_custom_folder.is_file():
        shutil.copy2(source_custom_folder, package / source_custom_folder.name)
    source_icon = source / "Mantella.ico"
    if source_icon.is_file():
        shutil.copy2(source_icon, package / source_icon.name)
    source_runtime_assets = source / "src"
    target_runtime_assets = package / "src"
    if source_runtime_assets.is_dir():
        shutil.copytree(source_runtime_assets, target_runtime_assets, dirs_exist_ok=True)
    internal = package / "_internal"
    required = [
        package / "Mantella.exe",
        internal / "gradio_client",
        internal / "gradio" / "blocks_events.py",
        internal / "gradio_client" / "types.json",
        internal / "silero_vad_lite" / "data" / "silero_vad_lite.dll",
        internal / "silero_vad_lite" / "data" / "silero_vad.onnx",
        internal / "moonshine_onnx" / "assets" / "tokenizer.json",
        internal / "moonshine_onnx" / "assets" / "beckett.wav",
        package / "data" / "language_support.csv",
        package / "src" / "ui" / "style.css",
        package / "Mantella.ico",
    ]
    missing = [str(path) for path in required if not path.exists()]
    tk_binary = list(internal.glob("_tkinter*.pyd")) + list(internal.glob("**/_tkinter*.pyd"))
    if not tk_binary and not (internal / "tkinter").exists():
        missing.append(f"{internal} (Tk runtime: tkinter package or _tkinter DLL)")
    if missing:
        raise SystemExit("Packaged distribution is incomplete:\n" + "\n".join(missing))

    run(
        [
            sys.executable,
            str(source / "scripts" / "run_packaged_startup_smoke.py"),
            "--exe",
            str(package / "Mantella.exe"),
            "--working-dir",
            str(package),
            "--timeout",
            str(args.timeout),
            "--probe-mantella-init",
            "--probe-conversation-start",
            *( ["--config-template", str(args.config_template.resolve())] if args.config_template else [] ),
            *( ["--user-folder", str(args.user_folder.resolve())] if args.user_folder else [] ),
        ],
        source,
    )
    print(f"PASS complete packaged distribution: {package}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
