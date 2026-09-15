"""Pytest configuration ensuring deterministic test environment isolation."""

import pytest


@pytest.fixture(autouse=True)
def _isolate_auth_environment(monkeypatch):
    """Isolates test execution from ambient developer shell SHADOWSPARK_* variables."""
    monkeypatch.delenv("SHADOWSPARK_ENV", raising=False)
    monkeypatch.delenv("SHADOWSPARK_API_TOKEN", raising=False)
