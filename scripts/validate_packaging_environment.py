#!/usr/bin/env python3
"""Preflight checks for the Mantella PyInstaller environment."""

from __future__ import annotations

import importlib.util
import sys


def main() -> int:
    failures: list[str] = []
    try:
        import tkinter  # noqa: F401
        import _tkinter
        print(f"Tk: available ({_tkinter.TK_VERSION})")
    except Exception as exc:
        failures.append(f"Tk support unavailable: {exc}")

    for package in ("gradio", "gradio_client"):
        spec = importlib.util.find_spec(package)
        if spec is None:
            failures.append(f"required package unavailable: {package}")
        else:
            print(f"{package}: {spec.origin}")

    try:
        import PyInstaller
        print(f"PyInstaller: {PyInstaller.__version__}")
    except Exception as exc:
        failures.append(f"PyInstaller unavailable: {exc}")

    if failures:
        for failure in failures:
            print(f"ERROR: {failure}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
