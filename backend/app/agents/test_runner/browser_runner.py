"""
Browser Runner — Test Runner Agent Integration Shim.

Called by test_runner_node when AgentState contains a `browser_test_url`.

Contract
--------
- Returns a BrowserTestReport (serialised as dict) or a blocked-report dict.
- Never claims a test passed unless a real browser ran and asserted it.
- Never modifies production data; all interactions are read/navigate/observe only
  unless a test scenario explicitly requires form submission (issue intake).
- URL is validated against the permitted allowlist before any browser is launched.
- Secrets are scrubbed from all captured text before storage.

Integration with Test Runner node
----------------------------------
The test_runner_node reads `browser_test_url` from state and calls
`run_browser_tests_for_agent()`. The resulting dict is stored in
`browser_test_results` on the state for downstream agents and UI rendering.
"""

from __future__ import annotations

import datetime
import logging
import pathlib
import sys
import uuid

# Make playground importable when called from within the backend
_REPO_ROOT = pathlib.Path(__file__).resolve().parents[4]  # …/mini-devin
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from playground.browser_testing.config import TARGET_URL, is_permitted, run_artifact_dir
from playground.browser_testing.engine import BrowserTestRunner, BrowserTestReport, blocked_report
from playground.browser_testing.scenarios.web_scenarios import (
    scenario_page_availability,
    scenario_issue_intake,
    scenario_workflow_status,
    scenario_unavailable_url,
)

logger = logging.getLogger(__name__)


def run_browser_tests_for_agent(
    target_url: str | None = None,
    run_id: str | None = None,
    scenarios: list[str] | None = None,
) -> dict:
    """
    Entry point for the Test Runner agent node.

    Parameters
    ----------
    target_url : Explicit target URL.  If None, falls back to MINI_DEVIN_TEST_URL
                 environment variable.  If still None → BLOCKED report.
    run_id     : Workflow run identifier to use for artifact directory naming.
    scenarios  : List of scenario names to run.  Defaults to all standard scenarios.
                 Valid values: "availability", "issue_intake", "workflow_status",
                               "unavailable_url".

    Returns
    -------
    dict  –  BrowserTestReport serialised as a plain dict.
    """
    url = target_url or TARGET_URL
    rid = run_id or (
        datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%S")
        + "_" + uuid.uuid4().hex[:6]
    )
    art_dir = run_artifact_dir(rid)

    # ── Guard: no URL configured ─────────────────────────────────────────────
    if not url:
        reason = (
            "No browser test URL configured. "
            "Set MINI_DEVIN_TEST_URL environment variable or pass browser_test_url "
            "in AgentState to enable live browser testing."
        )
        return blocked_report(
            target_url=None, reason=reason, run_id=rid, artifact_dir=art_dir
        ).to_dict()

    # ── Guard: URL not permitted ─────────────────────────────────────────────
    if not is_permitted(url):
        reason = (
            f"Target URL '{url}' is not in the permitted allowlist "
            "(playground/browser_testing/config.py::PERMITTED_URL_PREFIXES). "
            "Live browser test NOT RUN."
        )
        return blocked_report(
            target_url=url, reason=reason, run_id=rid, artifact_dir=art_dir
        ).to_dict()

    # ── Run scenarios ────────────────────────────────────────────────────────
    active_scenarios = scenarios or ["availability", "issue_intake", "workflow_status", "unavailable_url"]
    all_steps = []

    logger.info("Starting browser test run '%s' against %s", rid, url)

    try:
        with BrowserTestRunner(target_url=url, run_id=rid) as runner:
            for name in active_scenarios:
                if name == "availability":
                    steps = scenario_page_availability(runner, url)
                elif name == "issue_intake":
                    steps = scenario_issue_intake(runner, url)
                elif name == "workflow_status":
                    steps = scenario_workflow_status(runner, url)
                elif name == "unavailable_url":
                    steps = scenario_unavailable_url(runner)
                else:
                    logger.warning("Unknown scenario '%s' — skipping", name)
                    continue
                all_steps.extend(steps)

            report = runner.report()
    except PermissionError as exc:
        return blocked_report(
            target_url=url, reason=str(exc), run_id=rid, artifact_dir=art_dir
        ).to_dict()
    except Exception as exc:
        logger.exception("Browser test run failed with an unexpected error")
        err_report = blocked_report(
            target_url=url,
            reason=f"Unexpected error during browser test execution: {exc}",
            run_id=rid,
            artifact_dir=art_dir,
        )
        err_report.status = "error"
        return err_report.to_dict()

    return report.to_dict()
