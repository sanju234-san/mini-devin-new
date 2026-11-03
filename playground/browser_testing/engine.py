"""
Mini-Devin Browser Test Engine.

Provides BrowserTestRunner — a Playwright-backed engine that:
  1. Validates the target URL against the permitted allowlist.
  2. Opens a real browser, navigates to pages, clicks elements, fills forms.
  3. Captures screenshots at defined checkpoints.
  4. Records console errors and failed network requests.
  5. Writes per-step metadata (URL, timestamp, expected, observed) alongside
     every screenshot into the run artifact directory.
  6. Returns a structured BrowserTestReport that is consumed by the Test Runner
     agent node and stored in AgentState.

This module NEVER:
  - Fabricates screenshots or marks unexecuted steps as passed.
  - Exposes credentials, secrets, or .env values in screenshots or reports.
  - Runs against URLs outside the permitted allowlist.
"""

from __future__ import annotations

import datetime
import json
import logging
import pathlib
import re
import traceback
from dataclasses import dataclass, field, asdict
from typing import Any, Callable

from playwright.sync_api import (
    Browser,
    BrowserContext,
    ConsoleMessage,
    Page,
    Request,
    Response,
    sync_playwright,
    TimeoutError as PlaywrightTimeout,
)

from playground.browser_testing.config import (
    HEADLESS,
    SLOW_MO_MS,
    TIMEOUT_MS,
    is_permitted,
    run_artifact_dir,
)

logger = logging.getLogger(__name__)

# ── Data models ──────────────────────────────────────────────────────────────

@dataclass
class StepResult:
    """Outcome of one browser test step."""
    step_index: int
    step_name: str
    url: str
    timestamp: str
    expected: str
    observed: str
    passed: bool
    screenshot_path: str | None = None   # absolute path, or None if not captured
    console_errors: list[str] = field(default_factory=list)
    failed_requests: list[str] = field(default_factory=list)
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class BrowserTestReport:
    """Aggregate report for one browser test run."""
    run_id: str
    target_url: str
    started_at: str
    finished_at: str
    status: str          # "passed", "failed", "blocked", "error"
    total_steps: int
    passed_steps: int
    failed_steps: int
    steps: list[StepResult] = field(default_factory=list)
    artifact_dir: str = ""
    report_path: str = ""
    blocking_reason: str = ""   # set when status == "blocked"

    @property
    def passed(self) -> bool:
        return self.status == "passed"

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["passed"] = self.passed
        return d


# ── Secret scrubbing ─────────────────────────────────────────────────────────

_SECRET_PATTERNS = [
    re.compile(r"(?i)(token|key|secret|password|bearer|auth)\s*[=:]\s*\S+"),
    re.compile(r"ghp_[A-Za-z0-9]{36}"),            # GitHub PAT
    re.compile(r"sk-[A-Za-z0-9]{48}"),              # OpenAI key shape
]


def _scrub(text: str) -> str:
    """Replace any detected secret patterns with a redaction placeholder."""
    for pat in _SECRET_PATTERNS:
        text = pat.sub("[REDACTED]", text)
    return text


# ── Core runner ──────────────────────────────────────────────────────────────

class BrowserTestRunner:
    """
    Orchestrates a sequence of browser test steps against a single target URL.

    Usage::

        runner = BrowserTestRunner(target_url="http://localhost:8000", run_id="abc123")
        with runner:
            runner.step(
                name="Page loads",
                action=lambda page: None,
                expected="Page title visible",
                assert_fn=lambda page: "Mini-Devin" in page.title(),
            )
        report = runner.report()
    """

    def __init__(
        self,
        target_url: str,
        run_id: str | None = None,
        headless: bool = HEADLESS,
        slow_mo: int = SLOW_MO_MS,
        timeout: int = TIMEOUT_MS,
    ) -> None:
        if not is_permitted(target_url):
            raise PermissionError(
                f"Target URL '{target_url}' is not in the permitted allowlist. "
                "Add it to playground/browser_testing/config.py::PERMITTED_URL_PREFIXES "
                "only after explicit authorisation."
            )
        self._target_url = target_url
        self._run_id = run_id or datetime.datetime.now(datetime.timezone.utc).strftime(
            "%Y%m%dT%H%M%S"
        )
        self._headless = headless
        self._slow_mo = slow_mo
        self._timeout = timeout

        self._artifact_dir: pathlib.Path = run_artifact_dir(self._run_id)
        self._steps: list[StepResult] = []
        self._started_at: str = ""
        self._finished_at: str = ""

        # Playwright internals — set in __enter__
        self._pw = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None
        self._console_errors: list[str] = []
        self._failed_requests: list[str] = []

    # ── Context manager ──────────────────────────────────────────────────────

    def __enter__(self) -> "BrowserTestRunner":
        self._started_at = _now()
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(
            headless=self._headless,
            slow_mo=self._slow_mo,
        )
        self._context = self._browser.new_context(
            viewport={"width": 1280, "height": 800},
            # Never pass stored credentials; auth must be handled per-test
        )
        self._context.set_default_timeout(self._timeout)
        self._page = self._context.new_page()
        self._page.set_default_timeout(self._timeout)

        # Wire console error capture
        self._page.on("console", self._on_console)
        # Wire failed network requests
        self._page.on("requestfailed", self._on_request_failed)

        logger.info("Browser opened. Target: %s  Run: %s", self._target_url, self._run_id)
        return self

    def __exit__(self, *_: Any) -> None:
        try:
            if self._context:
                self._context.close()
            if self._browser:
                self._browser.close()
            if self._pw:
                self._pw.stop()
        except Exception:
            pass
        self._finished_at = _now()

    # ── Event handlers ───────────────────────────────────────────────────────

    def _on_console(self, msg: ConsoleMessage) -> None:
        if msg.type in ("error", "warning"):
            self._console_errors.append(_scrub(f"[{msg.type.upper()}] {msg.text}"))

    def _on_request_failed(self, request: Request) -> None:
        self._failed_requests.append(_scrub(f"FAILED {request.method} {request.url}"))

    # ── Step execution ───────────────────────────────────────────────────────

    def step(
        self,
        name: str,
        action: Callable[[Page], Any],
        expected: str,
        assert_fn: Callable[[Page], bool] | None = None,
        capture_screenshot: bool = True,
    ) -> StepResult:
        """
        Execute one test step.

        Parameters
        ----------
        name:               Human-readable step description.
        action:             Callable that receives the live Page and performs interactions.
        expected:           Description of the expected visible result.
        assert_fn:          Optional boolean predicate; step passes only when True.
        capture_screenshot: Whether to save a screenshot at this checkpoint.
        """
        assert self._page is not None, "Must be used as a context manager"

        step_idx = len(self._steps)
        ts = _now()
        url = self._page.url
        screenshot_path: str | None = None
        console_snapshot = list(self._console_errors)
        failed_snapshot = list(self._failed_requests)
        observed = ""
        error_msg: str | None = None
        passed = False

        try:
            action(self._page)
            url = self._page.url

            if assert_fn is not None:
                result = assert_fn(self._page)
                passed = bool(result)
                observed = "Assertion passed." if passed else "Assertion FAILED — condition returned False."
            else:
                # No assertion = step is a navigation/action; passes unless exception
                passed = True
                observed = "Action completed without exception."

        except PlaywrightTimeout as exc:
            passed = False
            error_msg = f"Timeout: {exc}"
            observed = f"TIMED OUT waiting for element/navigation. ({exc})"
            logger.warning("Step '%s' timed out: %s", name, exc)

        except Exception as exc:
            passed = False
            error_msg = _scrub(traceback.format_exc())
            observed = f"Exception: {_scrub(str(exc))}"
            logger.exception("Step '%s' raised an exception", name)

        finally:
            # Always attempt screenshot if requested, regardless of pass/fail
            if capture_screenshot:
                safe_name = re.sub(r"[^\w\-]", "_", name)[:60]
                status_tag = "PASS" if passed else "FAIL"
                fname = f"{step_idx:02d}_{status_tag}_{safe_name}.png"
                ss_path = self._artifact_dir / fname
                try:
                    self._page.screenshot(path=str(ss_path), full_page=True)
                    screenshot_path = str(ss_path)
                    logger.info("Screenshot saved: %s", screenshot_path)
                except Exception as ss_err:
                    logger.warning("Screenshot failed for step '%s': %s", name, ss_err)

        result = StepResult(
            step_index=step_idx,
            step_name=name,
            url=url,
            timestamp=ts,
            expected=expected,
            observed=observed,
            passed=passed,
            screenshot_path=screenshot_path,
            console_errors=list(self._console_errors[len(console_snapshot):]),
            failed_requests=list(self._failed_requests[len(failed_snapshot):]),
            error=error_msg,
        )
        self._steps.append(result)

        status_symbol = "✅" if passed else "❌"
        logger.info("%s Step [%d] '%s' | expected: %s | observed: %s",
                    status_symbol, step_idx, name, expected, observed)
        return result

    def navigate(self, url: str) -> None:
        """Navigate to *url* inside the current browser context (no step recorded)."""
        assert self._page is not None
        if not is_permitted(url):
            raise PermissionError(f"Navigation target '{url}' is not in the permitted allowlist.")
        self._page.goto(url, wait_until="domcontentloaded")

    # ── Report ───────────────────────────────────────────────────────────────

    def report(self) -> BrowserTestReport:
        """Build and persist the final BrowserTestReport."""
        total = len(self._steps)
        passed_count = sum(1 for s in self._steps if s.passed)
        failed_count = total - passed_count

        status = "passed" if failed_count == 0 and total > 0 else "failed"

        report = BrowserTestReport(
            run_id=self._run_id,
            target_url=self._target_url,
            started_at=self._started_at,
            finished_at=self._finished_at or _now(),
            status=status,
            total_steps=total,
            passed_steps=passed_count,
            failed_steps=failed_count,
            steps=self._steps,
            artifact_dir=str(self._artifact_dir),
        )

        # Persist JSON report alongside screenshots
        report_file = self._artifact_dir / "report.json"
        try:
            report_file.write_text(
                json.dumps(report.to_dict(), indent=2, default=str),
                encoding="utf-8",
            )
            report.report_path = str(report_file)
            logger.info("Browser test report written: %s", report_file)
        except Exception as exc:
            logger.warning("Could not write report JSON: %s", exc)

        return report


# ── Blocked report factory ────────────────────────────────────────────────────

def blocked_report(
    target_url: str | None,
    reason: str,
    run_id: str | None = None,
    artifact_dir: pathlib.Path | None = None,
) -> BrowserTestReport:
    """
    Create a BLOCKED report when a live run cannot be executed
    (no URL configured, URL not permitted, or prerequisite missing).
    Never marks a step as passed.
    """
    ts = _now()
    rid = run_id or ts
    art_dir = artifact_dir or run_artifact_dir(rid)
    # Ensure directory exists even when caller passes a not-yet-created path
    art_dir.mkdir(parents=True, exist_ok=True)

    report = BrowserTestReport(
        run_id=rid,
        target_url=target_url or "NOT_CONFIGURED",
        started_at=ts,
        finished_at=ts,
        status="blocked",
        total_steps=0,
        passed_steps=0,
        failed_steps=0,
        steps=[],
        artifact_dir=str(art_dir),
        blocking_reason=reason,
    )
    report_file = art_dir / "report.json"
    try:
        report_file.write_text(
            json.dumps(report.to_dict(), indent=2, default=str),
            encoding="utf-8",
        )
        report.report_path = str(report_file)
    except Exception:
        pass
    logger.warning("Browser test BLOCKED: %s", reason)
    return report


# ── Helpers ──────────────────────────────────────────────────────────────────

def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()
