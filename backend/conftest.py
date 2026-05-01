from __future__ import annotations

import pytest

from app.runtime_check import ensure_supported_python


def pytest_configure(config: pytest.Config) -> None:
    ensure_supported_python()
