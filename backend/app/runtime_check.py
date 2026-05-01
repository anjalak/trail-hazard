"""Fail fast on unsupported Python (3.9/3.10 venvs, system pythons, etc.)."""

from __future__ import annotations

import sys

# Aligned with .python-version, CI, and docker-compose `python:3.11-slim`.
_MIN_VERSION = (3, 11)


def ensure_supported_python() -> None:
    if sys.version_info < _MIN_VERSION:
        v = f"{sys.version_info.major}.{sys.version_info.minor}"
        need = f"{_MIN_VERSION[0]}.{_MIN_VERSION[1]}"
        sys.stderr.write(
            f"ERROR: TrailIntel backend requires Python {need}+ (you are {v}).\n"
            f"  Use the repo .python-version with pyenv/asdf, recreate backend/.venv with "
            f"`python{need} -m venv backend/.venv`, and avoid reusing a venv created with 3.9/3.10.\n"
        )
        raise SystemExit(1)
