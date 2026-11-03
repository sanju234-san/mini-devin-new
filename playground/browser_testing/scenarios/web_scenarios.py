"""
Mini-Devin Browser Test Scenarios.

Each scenario function accepts a BrowserTestRunner (already opened) and
drives the browser through a specific workflow checkpoint, recording
screenshots and returning a list of StepResult objects.

Scenarios implemented
---------------------
scenario_page_availability   – verify the target URL loads and shows content
scenario_issue_intake         – fill and submit an issue form / textarea
scenario_workflow_status      – inspect workflow status indicators
scenario_unavailable_url      – failure scenario: blocked/unreachable target
"""

from __future__ import annotations

import logging
from typing import Any

from playground.browser_testing.engine import BrowserTestRunner, StepResult

logger = logging.getLogger(__name__)


# ── Scenario 1: Page Availability ────────────────────────────────────────────

def scenario_page_availability(runner: BrowserTestRunner, base_url: str) -> list[StepResult]:
    """
    Verify that the target application's root page loads successfully,
    returns a non-error status, and renders meaningful HTML content.

    Steps
    -----
    1. Navigate to base_url.
    2. Verify page title is non-empty.
    3. Verify at least one visible text element exists.
    4. Check no console errors were emitted during load.
    """
    results: list[StepResult] = []

    # Step 1 – Navigate
    results.append(runner.step(
        name="Navigate to root page",
        action=lambda page: page.goto(base_url, wait_until="domcontentloaded"),
        expected="Page loads without navigation error",
        assert_fn=lambda page: page.url.startswith(base_url.rstrip("/")),
        capture_screenshot=True,
    ))

    # Step 2 – Non-empty title
    results.append(runner.step(
        name="Page title is non-empty",
        action=lambda page: None,
        expected="<title> element has text content",
        assert_fn=lambda page: bool(page.title().strip()),
        capture_screenshot=False,
    ))

    # Step 3 – Visible body text
    results.append(runner.step(
        name="Body has visible text content",
        action=lambda page: None,
        expected="At least one visible paragraph or heading",
        assert_fn=lambda page: _has_visible_text(page),
        capture_screenshot=True,
    ))

    # Step 4 – Console clean
    results.append(runner.step(
        name="No critical console errors on load",
        action=lambda page: None,
        expected="Browser console has no [ERROR] messages",
        assert_fn=lambda page: not any(
            "[ERROR]" in e for e in runner._console_errors
        ),
        capture_screenshot=False,
    ))

    return results


# ── Scenario 2: Issue Intake ──────────────────────────────────────────────────

def scenario_issue_intake(
    runner: BrowserTestRunner,
    base_url: str,
    issue_title: str = "Test: null pointer in payment processor",
    issue_body: str = "When user submits an empty cart, a NullPointerException is raised at checkout.py:42.",
) -> list[StepResult]:
    """
    Simulate submitting an issue through the Mini-Devin UI.

    Attempts to:
    1. Navigate to the root.
    2. Locate a textarea/input for issue entry.
    3. Type the issue title and body.
    4. Submit the form or press Enter.
    5. Verify submission acknowledgement is visible.

    If the UI element cannot be found the step is marked FAIL — not skipped.
    """
    results: list[StepResult] = []

    # Step 1 – Navigate
    results.append(runner.step(
        name="Navigate to issue intake page",
        action=lambda page: page.goto(base_url, wait_until="domcontentloaded"),
        expected="Application root loads",
        assert_fn=lambda page: page.url.startswith(base_url.rstrip("/")),
        capture_screenshot=True,
    ))

    # Step 2 – Locate input
    results.append(runner.step(
        name="Locate issue input element",
        action=lambda page: page.wait_for_selector(
            "textarea, input[type='text'], [contenteditable='true'], "
            "[placeholder*='issue'], [placeholder*='Issue'], [placeholder*='question']",
            timeout=5000,
        ),
        expected="An input area for issue text is visible",
        assert_fn=lambda page: page.query_selector(
            "textarea, input[type='text'], [contenteditable='true']"
        ) is not None,
        capture_screenshot=True,
    ))

    # Step 3 – Fill issue text
    def _fill(page: Any) -> None:
        el = page.query_selector(
            "textarea, input[type='text'], [contenteditable='true']"
        )
        if el is None:
            raise RuntimeError("Input element not found")
        el.click()
        el.fill(f"{issue_title}\n\n{issue_body}")

    results.append(runner.step(
        name="Type issue title and body",
        action=_fill,
        expected="Issue text appears in the input field",
        assert_fn=lambda page: _input_has_content(page),
        capture_screenshot=True,
    ))

    # Step 4 – Submit
    def _submit(page: Any) -> None:
        btn = page.query_selector(
            "button[type='submit'], button:has-text('Send'), "
            "button:has-text('Submit'), button:has-text('Run')"
        )
        if btn:
            btn.click()
        else:
            # Fall back: press Enter in the active element
            page.keyboard.press("Enter")

    results.append(runner.step(
        name="Submit issue",
        action=_submit,
        expected="Submission triggers a visible response or loading indicator",
        assert_fn=lambda page: _submission_acknowledged(page),
        capture_screenshot=True,
    ))

    return results


# ── Scenario 3: Workflow Status ───────────────────────────────────────────────

def scenario_workflow_status(runner: BrowserTestRunner, base_url: str) -> list[StepResult]:
    """
    Check that the UI surfaces recognisable workflow-stage labels
    (triage, retrieval, planning, approval, etc.).
    """
    results: list[StepResult] = []

    results.append(runner.step(
        name="Navigate to application",
        action=lambda page: page.goto(base_url, wait_until="domcontentloaded"),
        expected="Application loads",
        assert_fn=lambda page: page.url.startswith(base_url.rstrip("/")),
        capture_screenshot=True,
    ))

    status_keywords = ["triage", "retriev", "plan", "approv", "test", "review", "pr"]

    def _has_status_keyword(page: Any) -> bool:
        body_text = (page.inner_text("body") or "").lower()
        return any(kw in body_text for kw in status_keywords)

    results.append(runner.step(
        name="Workflow status keywords visible",
        action=lambda page: None,
        expected="At least one workflow stage label is visible in the page body",
        assert_fn=_has_status_keyword,
        capture_screenshot=True,
    ))

    return results


# ── Scenario 4: Unavailable URL (Failure Scenario) ──────────────────────────

def scenario_unavailable_url(runner: BrowserTestRunner) -> list[StepResult]:
    """
    Deliberate failure scenario: attempt to navigate to a port that is not
    listening (localhost:19999) and verify the failure is detected and recorded
    honestly rather than silently swallowed.

    This test PASSES when the engine correctly reports the navigation failure.
    """
    from playwright.sync_api import Error as PlaywrightError

    results: list[StepResult] = []

    # We attempt navigation to a non-listening port.
    # The step should be marked FAIL (navigation error), and the report
    # should not be fabricated as a pass.
    unreachable = "http://localhost:19999"

    def _navigate_unreachable(page: Any) -> None:
        # Deliberately try a non-listening port; expect an exception
        page.goto(unreachable, wait_until="domcontentloaded", timeout=4000)

    results.append(runner.step(
        name="Navigate to unavailable URL (expected failure)",
        action=_navigate_unreachable,
        expected="Navigation fails — FAIL is reported honestly",
        # assert_fn intentionally absent; step should fail from exception in action
        assert_fn=None,
        capture_screenshot=True,
    ))

    # Override: for THIS specific test the engine's failure IS the correct outcome.
    # Mark the step pass-equivalent by wrapping the outcome in a meta-step.
    step = results[0]
    meta_result = StepResult(
        step_index=len(results),
        step_name="Failure correctly detected and recorded",
        url="about:blank",
        timestamp=step.timestamp,
        expected="Engine reports FAIL for unreachable URL; does not fabricate pass",
        observed=(
            "Navigation failure correctly recorded as FAIL."
            if not step.passed
            else "WARNING: navigation to non-listening port incorrectly reported as PASS"
        ),
        passed=not step.passed,   # meta-step passes when the nav step failed
        screenshot_path=None,
        console_errors=[],
        failed_requests=[],
    )
    results.append(meta_result)

    return results


# ── Helpers ──────────────────────────────────────────────────────────────────

def _has_visible_text(page: Any) -> bool:
    try:
        text = page.inner_text("body") or ""
        return len(text.strip()) > 20
    except Exception:
        return False


def _input_has_content(page: Any) -> bool:
    try:
        el = page.query_selector("textarea, input[type='text'], [contenteditable='true']")
        if el is None:
            return False
        val = el.input_value() if el.get_attribute("contenteditable") is None else el.inner_text()
        return bool(val and val.strip())
    except Exception:
        return False


def _submission_acknowledged(page: Any) -> bool:
    """Return True when the page shows any response to submission."""
    try:
        body = (page.inner_text("body") or "").lower()
        indicators = [
            "processing", "thinking", "loading", "received",
            "submitted", "working", "running", "triage",
        ]
        return any(ind in body for ind in indicators)
    except Exception:
        return False
