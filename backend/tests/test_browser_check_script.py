"""Unit tests for browser_check_script — import safety and helper functions."""

from __future__ import annotations

import pytest


def test_browser_check_script_imports_without_playwright() -> None:
    """The script must import cleanly without raising ImportError even if Playwright is absent."""
    import app.sandbox.browser_check_script as bcs

    assert hasattr(bcs, "run_browser_verification")
    assert hasattr(bcs, "RESULT_PREFIX")


def test_run_browser_verification_missing_config_returns_error() -> None:
    from app.sandbox.browser_check_script import run_browser_verification

    result = run_browser_verification("/nonexistent/path/config.json")
    assert result["ok"] is False
    assert "Failed to load browser check config" in result["error"]
