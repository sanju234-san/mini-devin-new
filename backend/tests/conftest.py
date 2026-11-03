"""Shared test fixtures for the Mini-Devin backend test suite."""

from __future__ import annotations

import pytest

from app.config import Settings, get_settings


@pytest.fixture(autouse=True)
def _isolate_settings(monkeypatch: pytest.MonkeyPatch):
    """Ensure each test gets a fresh, isolated Settings environment.

    - Clears the ``get_settings`` LRU cache before *and* after each test.
    - Deletes every Settings-known env var so no developer-local values
      leak into tests.
    - Overrides ``model_config["env_file"]`` to ``None`` so a local
      ``.env`` file is never read.
    """
    get_settings.cache_clear()

    for name in Settings.model_fields:
        monkeypatch.delenv(name, raising=False)

    monkeypatch.setitem(Settings.model_config, "env_file", None)

    yield

    get_settings.cache_clear()
