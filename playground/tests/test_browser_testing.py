"""
Pytest suite for Mini-Devin browser testing infrastructure.

These tests verify the browser testing capability WITHOUT requiring a live
web server. They cover:

1. Configuration & URL allowlist enforcement
2. Blocked-report generation when no URL is configured
3. Blocked-report generation when URL is not permitted
4. BrowserTestRunner with a real Chromium + httpserver (pytest-localserver or
   a minimal inline HTTP server)
5. The unavailable_url failure scenario
6. Secret scrubbing in observed text
7. AgentState browser fields
8. test_runner_node browser extension (mocked runner)
9. Screenshot artifact directory creation

Live-server tests are skipped automatically when the pytest-localserver plugin
is unavailable, maintaining CI compatibility.

Run
---
  python -m pytest playground/tests/test_browser_testing.py -v
"""

from __future__ import annotations

import json
import os
import pathlib
import sys
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# Ensure repo root is on path
_REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT))


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def artifact_tmp(tmp_path_factory):
    """Dedicated temporary directory for all artifact output in this module."""
    return tmp_path_factory.mktemp("browser_artifacts")


@pytest.fixture(scope="module")
def mini_http_server():
    """
    Spin up a tiny inline HTTP server on localhost for the duration of this
    test module. Serves a minimal HTML page that satisfies page_availability
    and workflow_status scenarios.
    """
    html = b"""<!DOCTYPE html>
<html><head><title>Mini-Devin Test App</title></head>
<body>
  <h1>Mini-Devin</h1>
  <p>Issue triage and retrieval planning workflow.</p>
  <textarea placeholder="Enter your issue here"></textarea>
  <button type="submit">Send</button>
  <div id="status">Triage ready. Planning approval pending.</div>
</body>
</html>"""

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(html)

        def log_message(self, *args):
            pass  # Suppress server access logs during tests

    server = HTTPServer(("127.0.0.1", 0), Handler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{port}"
    yield base_url
    server.shutdown()


# ── Config & Allowlist ────────────────────────────────────────────────────────

class TestConfig:
    def test_localhost_permitted(self):
        from playground.browser_testing.config import is_permitted
        assert is_permitted("http://localhost:8000")
        assert is_permitted("http://127.0.0.1:9000")
        assert is_permitted("https://localhost/app")

    def test_external_url_not_permitted(self):
        from playground.browser_testing.config import is_permitted
        assert not is_permitted("https://example.com")
        assert not is_permitted("https://production.myapp.io")
        assert not is_permitted("http://0.0.0.0:8000")

    def test_run_artifact_dir_created(self, artifact_tmp, monkeypatch):
        monkeypatch.setenv("SCREENSHOT_DIR", str(artifact_tmp))
        # Re-import to pick up monkeypatched env
        import importlib
        import playground.browser_testing.config as cfg
        importlib.reload(cfg)
        d = cfg.run_artifact_dir("test_run_123")
        assert d.exists()
        assert d.is_dir()
        # Cleanup reload
        importlib.reload(cfg)


# ── Blocked Report ────────────────────────────────────────────────────────────

class TestBlockedReport:
    def test_no_url_produces_blocked(self, artifact_tmp, monkeypatch):
        monkeypatch.delenv("MINI_DEVIN_TEST_URL", raising=False)
        monkeypatch.setenv("SCREENSHOT_DIR", str(artifact_tmp))
        from playground.browser_testing.engine import blocked_report
        report = blocked_report(target_url=None, reason="Test: no URL", run_id="no_url_test")
        assert report.status == "blocked"
        assert not report.passed
        assert report.total_steps == 0
        assert "Test: no URL" in report.blocking_reason

    def test_blocked_report_writes_json(self, artifact_tmp, monkeypatch):
        monkeypatch.setenv("SCREENSHOT_DIR", str(artifact_tmp))
        from playground.browser_testing.engine import blocked_report
        report = blocked_report(
            target_url="http://localhost:9999",
            reason="Port not listening",
            run_id="blocked_json_test",
            artifact_dir=artifact_tmp / "blocked_json_test",
        )
        assert report.report_path
        p = pathlib.Path(report.report_path)
        assert p.exists()
        data = json.loads(p.read_text(encoding="utf-8"))
        assert data["status"] == "blocked"

    def test_run_browser_tests_no_url_blocked(self, monkeypatch):
        monkeypatch.delenv("MINI_DEVIN_TEST_URL", raising=False)
        from app.agents.test_runner.browser_runner import run_browser_tests_for_agent
        report = run_browser_tests_for_agent(target_url=None)
        assert report["status"] == "blocked"
        assert not report["passed"]

    def test_run_browser_tests_unpermitted_url_blocked(self):
        from app.agents.test_runner.browser_runner import run_browser_tests_for_agent
        report = run_browser_tests_for_agent(target_url="https://external-site.example.com")
        assert report["status"] == "blocked"
        assert "not in the permitted allowlist" in report["blocking_reason"]


# ── BrowserTestRunner with Real Browser ──────────────────────────────────────

class TestBrowserTestRunner:
    """
    Integration tests that launch real Chromium via Playwright.
    Skipped when PLAYWRIGHT_SKIP_BROWSER_TESTS=1 (e.g. CI without Chromium).
    """

    @pytest.fixture(autouse=True)
    def skip_if_no_browser(self):
        if os.environ.get("PLAYWRIGHT_SKIP_BROWSER_TESTS") == "1":
            pytest.skip("PLAYWRIGHT_SKIP_BROWSER_TESTS=1 — skipping real browser tests")

    def test_page_availability_passes(self, mini_http_server, artifact_tmp, monkeypatch):
        monkeypatch.setenv("SCREENSHOT_DIR", str(artifact_tmp))
        from playground.browser_testing.engine import BrowserTestRunner
        from playground.browser_testing.scenarios.web_scenarios import scenario_page_availability

        with BrowserTestRunner(target_url=mini_http_server, run_id="avail_test") as runner:
            steps = scenario_page_availability(runner, mini_http_server)
            report = runner.report()

        assert report.total_steps == len(steps)
        assert report.status == "passed", f"Steps: {[(s.step_name, s.passed, s.observed) for s in report.steps]}"

    def test_screenshots_are_saved(self, mini_http_server, artifact_tmp, monkeypatch):
        monkeypatch.setenv("SCREENSHOT_DIR", str(artifact_tmp))
        from playground.browser_testing.engine import BrowserTestRunner
        from playground.browser_testing.scenarios.web_scenarios import scenario_page_availability

        with BrowserTestRunner(target_url=mini_http_server, run_id="screenshot_test") as runner:
            scenario_page_availability(runner, mini_http_server)
            report = runner.report()

        screenshots = [
            pathlib.Path(s.screenshot_path)
            for s in report.steps
            if s.screenshot_path
        ]
        assert len(screenshots) > 0, "Expected at least one screenshot"
        for ss in screenshots:
            assert ss.exists(), f"Screenshot file missing: {ss}"
            assert ss.stat().st_size > 0, f"Screenshot is empty: {ss}"

    def test_report_json_is_written(self, mini_http_server, artifact_tmp, monkeypatch):
        monkeypatch.setenv("SCREENSHOT_DIR", str(artifact_tmp))
        from playground.browser_testing.engine import BrowserTestRunner
        from playground.browser_testing.scenarios.web_scenarios import scenario_page_availability

        with BrowserTestRunner(target_url=mini_http_server, run_id="report_json_test") as runner:
            scenario_page_availability(runner, mini_http_server)
            report = runner.report()

        p = pathlib.Path(report.report_path)
        assert p.exists()
        data = json.loads(p.read_text())
        assert data["status"] in ("passed", "failed")
        assert "steps" in data

    def test_unavailable_url_failure_scenario(self, mini_http_server, artifact_tmp, monkeypatch):
        """The unavailable_url scenario must report FAIL for the nav step and
        PASS for the meta-step that confirms honest failure detection."""
        monkeypatch.setenv("SCREENSHOT_DIR", str(artifact_tmp))
        from playground.browser_testing.engine import BrowserTestRunner
        from playground.browser_testing.scenarios.web_scenarios import scenario_unavailable_url

        with BrowserTestRunner(target_url=mini_http_server, run_id="unreach_test") as runner:
            steps = scenario_unavailable_url(runner)

        nav_step = steps[0]
        meta_step = steps[1]
        assert not nav_step.passed, "Navigation to non-listening port should fail"
        assert meta_step.passed, "Meta-step should pass when nav step correctly failed"

    def test_unpermitted_url_raises_permission_error(self):
        from playground.browser_testing.engine import BrowserTestRunner
        with pytest.raises(PermissionError, match="not in the permitted allowlist"):
            BrowserTestRunner(target_url="https://external.example.com")

    def test_issue_intake_scenario(self, mini_http_server, artifact_tmp, monkeypatch):
        """Issue intake scenario should at minimum complete navigate + locate steps."""
        monkeypatch.setenv("SCREENSHOT_DIR", str(artifact_tmp))
        from playground.browser_testing.engine import BrowserTestRunner
        from playground.browser_testing.scenarios.web_scenarios import scenario_issue_intake

        with BrowserTestRunner(target_url=mini_http_server, run_id="intake_test") as runner:
            steps = scenario_issue_intake(runner, mini_http_server)

        # First two steps (navigate, locate input) must pass on our test HTML
        assert steps[0].passed, f"Navigate step failed: {steps[0].observed}"
        assert steps[1].passed, f"Locate input step failed: {steps[1].observed}"

    def test_console_errors_captured(self, mini_http_server, artifact_tmp, monkeypatch):
        """Console error capture must work even when no errors are present."""
        monkeypatch.setenv("SCREENSHOT_DIR", str(artifact_tmp))
        from playground.browser_testing.engine import BrowserTestRunner

        with BrowserTestRunner(target_url=mini_http_server, run_id="console_test") as runner:
            runner.step(
                name="Load page and check console",
                action=lambda page: page.goto(mini_http_server, wait_until="domcontentloaded"),
                expected="Page loads",
                assert_fn=lambda page: True,
            )
            # console_errors should be a list (empty or not)
            assert isinstance(runner._console_errors, list)

    def test_full_run_via_agent_shim(self, mini_http_server, monkeypatch, artifact_tmp):
        """End-to-end: invoke run_browser_tests_for_agent as the agent would."""
        monkeypatch.setenv("SCREENSHOT_DIR", str(artifact_tmp))
        from app.agents.test_runner.browser_runner import run_browser_tests_for_agent

        report = run_browser_tests_for_agent(
            target_url=mini_http_server,
            run_id="agent_shim_test",
            scenarios=["availability", "unavailable_url"],
        )
        assert report["status"] in ("passed", "failed", "error")
        assert "steps" in report
        assert "artifact_dir" in report


# ── Secret Scrubbing ──────────────────────────────────────────────────────────

class TestSecretScrubbing:
    def test_token_scrubbed(self):
        from playground.browser_testing.engine import _scrub
        dirty = "Authorization: Bearer ghp_abcdefghijklmnopqrstuvwxyz0123456789"
        cleaned = _scrub(dirty)
        assert "ghp_" not in cleaned
        assert "[REDACTED]" in cleaned

    def test_api_key_scrubbed(self):
        from playground.browser_testing.engine import _scrub
        dirty = "api_key=sk-abcdefghijklmnopqrstuvwxyz01234567890123456789"
        cleaned = _scrub(dirty)
        assert "[REDACTED]" in cleaned

    def test_clean_text_unchanged(self):
        from playground.browser_testing.engine import _scrub
        clean = "User clicked the Submit button. Form submitted successfully."
        assert _scrub(clean) == clean


# ── AgentState Browser Fields ─────────────────────────────────────────────────

class TestAgentStateBrowserFields:
    def test_browser_test_url_accepted_in_state(self):
        from app.agents.schemas import create_initial_state
        state = create_initial_state(
            issue_title="Test issue",
            repo="demo/repo",
        )
        # TypedDict accepts arbitrary keys at runtime
        state["browser_test_url"] = "http://localhost:8000"
        state["browser_test_results"] = None
        assert state["browser_test_url"] == "http://localhost:8000"


# ── test_runner_node Browser Extension ───────────────────────────────────────

class TestTestRunnerNodeBrowserExtension:
    """Test the node's browser branch with a mocked runner (no real browser)."""

    def test_node_calls_browser_runner_when_url_present(self):
        from app.agents.schemas import create_initial_state
        from app.agents.test_runner.agent import test_runner_node

        state = create_initial_state(issue_title="Bug fix test", repo="demo/repo")
        state["browser_test_url"] = "http://localhost:8000"

        fake_report = {
            "status": "blocked",
            "passed": False,
            "total_steps": 0,
            "passed_steps": 0,
            "failed_steps": 0,
            "steps": [],
            "blocking_reason": "No server at localhost:8000 during unit test",
            "artifact_dir": "/tmp/fake",
            "report_path": "",
            "target_url": "http://localhost:8000",
        }

        with patch(
            "app.agents.test_runner.agent._run_browser_tests",
            return_value=fake_report,
        ) as mock_run:
            result = test_runner_node(state)

        mock_run.assert_called_once_with(url="http://localhost:8000", run_id=state["run_id"])
        assert "browser_test_results" in result
        assert result["browser_test_results"]["status"] == "blocked"

    def test_node_skips_browser_runner_when_no_url(self):
        from app.agents.schemas import create_initial_state
        from app.agents.test_runner.agent import test_runner_node

        state = create_initial_state(issue_title="No browser URL", repo="demo/repo")
        # browser_test_url intentionally absent

        with patch("app.agents.test_runner.agent._run_browser_tests") as mock_run:
            result = test_runner_node(state)

        mock_run.assert_not_called()
        assert "browser_test_results" not in result

    def test_node_adds_browser_event_to_events(self):
        from app.agents.schemas import create_initial_state
        from app.agents.test_runner.agent import test_runner_node

        state = create_initial_state(issue_title="Event check", repo="demo/repo")
        state["browser_test_url"] = "http://127.0.0.1:8000"

        fake_report = {
            "status": "blocked", "passed": False, "total_steps": 0,
            "passed_steps": 0, "failed_steps": 0, "steps": [],
            "blocking_reason": "unit test mock", "artifact_dir": "",
            "report_path": "", "target_url": "http://127.0.0.1:8000",
        }

        with patch("app.agents.test_runner.agent._run_browser_tests", return_value=fake_report):
            result = test_runner_node(state)

        events = result.get("events", [])
        browser_events = [e for e in events if e.get("event_type") == "browser_tests_completed"]
        assert len(browser_events) == 1
