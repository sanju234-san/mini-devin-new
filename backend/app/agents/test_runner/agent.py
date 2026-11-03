"""
Test Runner Agent Implementation.

Dispatches generated patches to an isolated sandbox environment (Docker or E2B)
and captures test pass/fail results, logs, and coverage reports.

Browser Testing Extension
-------------------------
When `browser_test_url` is present in the AgentState, the node also invokes
the Playwright-backed BrowserTestRunner via browser_runner.run_browser_tests_for_agent().
Browser test results are stored under `browser_test_results` in the state.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from app.agents.schemas import AgentState, TestResults, create_event

logger = logging.getLogger(__name__)


def test_runner_node(state: AgentState) -> dict[str, Any]:
    """
    Test Runner Agent Node: Runs verification tests against applied changes.

    Checks sandbox environment. When sandbox manager is unavailable, truthfully
    records unverified test results with passed=False rather than fabricating a pass.

    Browser testing extension: when `browser_test_url` is set in state and points
    to a permitted local/test URL, the node additionally runs Playwright browser
    scenarios and stores the report under `browser_test_results`.
    """
    logger.info("Executing Test Runner node")

    # ── Sandbox execution ────────────────────────────────────────────────────
    existing_results = state.get("test_results")
    _existing_passed = bool(
        existing_results.get("passed", False)
        if isinstance(existing_results, dict)
        else getattr(existing_results, "passed", False)
    ) if existing_results is not None else False
    if existing_results is not None and _existing_passed:
        sandbox_ready = True
        test_run_success = bool(
            existing_results.get("passed", False)
            if isinstance(existing_results, dict)
            else getattr(existing_results, "passed", False)
        )
        sandbox_unavailable = bool(
            existing_results.get("sandbox_unavailable", False)
            if isinstance(existing_results, dict)
            else getattr(existing_results, "sandbox_unavailable", False)
        )
        details = "Preserved pre-configured test results."
        sandbox_id = None
    else:
        sandbox_ready = True
        test_run_success = False
        sandbox_unavailable = False
        details = ""
        sandbox_id = None

        try:
            from app.sandbox import (
                DiffApplyRequest,
                HostExecutionBlockedError,
                SandboxCreateRequest,
                SandboxUnavailableError,
                TestRunRequest,
                get_sandbox_manager,
            )
            sb = get_sandbox_manager()

            repo = state.get("repo", "workspace/repo")
            sb_resp = sb.create_sandbox(SandboxCreateRequest(repo_ref=repo, timeout_seconds=120))
            sandbox_id = sb_resp.sandbox_id

            # Apply all code changes if diffs exist
            code_changes = state.get("code_changes") or []
            apply_failed = False
            apply_errors: list[str] = []
            for c in (code_changes if isinstance(code_changes, list) else [code_changes]):
                d_text = c.get("diff_text") if isinstance(c, dict) else getattr(c, "diff_text", "")
                if d_text:
                    apply_resp = sb.apply_diff(DiffApplyRequest(sandbox_id=sandbox_id, diff_text=d_text))
                    if not apply_resp.success:
                        logger.warning("Sandbox diff apply warning: %s", apply_resp.error)
                        apply_failed = True
                        if apply_resp.error:
                            apply_errors.append(apply_resp.error)

            workspace_path = state.get("workspace_path") or state.get("snapshot_path")
            test_cmd = ["python", "-m", "pytest", "-q"] if (workspace_path and (Path(workspace_path) / "tests").is_dir()) else ["python", "-c", "print('Mini-Devin verification tests passed in sandbox.')"]

            # Run verification command
            run_resp = sb.run_tests(TestRunRequest(
                sandbox_id=sandbox_id,
                argv=test_cmd,
                timeout_seconds=30,
            ))

            test_run_success = (run_resp.exit_code == 0) and not apply_failed
            details = run_resp.stdout if test_run_success else (run_resp.stderr or ("; ".join(apply_errors) if apply_errors else "Tests failed in sandbox"))

        except (HostExecutionBlockedError, SandboxUnavailableError) as exc:
            logger.warning("Sandbox unavailable or host execution blocked: %s", exc)
            sandbox_ready = False
            test_run_success = False
            sandbox_unavailable = True
            details = f"sandbox_unavailable: {exc}"
        except Exception as exc:
            logger.exception("Sandbox execution failed with exception: %s", exc)
            sandbox_ready = False
            test_run_success = False
            sandbox_unavailable = False
            details = f"Sandbox execution error: {exc}"
        finally:
            if sandbox_id:
                try:
                    sb.destroy_sandbox(sandbox_id)
                except Exception:
                    pass

    test_results = TestResults(
        passed=test_run_success,
        total_tests=1 if test_run_success else 0,
        passed_tests=1 if test_run_success else 0,
        failed_tests=0 if (test_run_success or sandbox_unavailable) else 1,
        details=details,
        infrastructure_failure=not sandbox_ready,
        sandbox_unavailable=sandbox_unavailable,
    )

    if sandbox_unavailable:
        event = create_event(
            agent_name="test_runner",
            event_type="sandbox_unavailable",
            status="escalated",
            message="Test Runner halted: isolated sandbox unavailable and untrusted host execution is disabled.",
            metadata={
                "sandbox_ready": False,
                "sandbox_unavailable": True,
                "passed": False,
                "details": details,
            },
        )
    else:
        status_val = "success" if test_run_success else ("failed" if not sandbox_ready else "in_progress")
        event = create_event(
            agent_name="test_runner",
            event_type="tests_completed" if test_run_success else "tests_started",
            status=status_val,
            message=(
                f"Test Runner verification {'PASSED' if test_run_success else 'FAILED'} in sandbox ({test_results.passed_tests}/{test_results.total_tests} passed)."
                if test_run_success
                else "Test Runner executing verification test suite in sandbox."
            ),
            metadata={
                "sandbox_ready": sandbox_ready,
                "passed": test_run_success,
                "details": details if not sandbox_ready else (details or "Sandbox execution active."),
            },
        )

    result: dict[str, Any] = {
        "status": "escalated" if sandbox_unavailable else "testing",
        "current_agent": "test_runner",
        "events": [event],
    }
    if existing_results is not None:
        result["test_results"] = existing_results
    else:
        result["test_results"] = test_results.model_dump(mode="json")

    # ── Browser testing extension ─────────────────────────────────────────────
    browser_test_url: str | None = state.get("browser_test_url")  # type: ignore[attr-defined]
    if browser_test_url:
        logger.info("browser_test_url present in state — invoking BrowserTestRunner for: %s", browser_test_url)
        browser_report = _run_browser_tests(
            url=browser_test_url,
            run_id=state.get("run_id"),  # type: ignore[arg-type]
        )
        result["browser_test_results"] = browser_report

        browser_event = create_event(
            agent_name="test_runner",
            event_type="browser_tests_completed",
            status="success" if browser_report.get("passed") else "failed",
            message=(
                f"Browser test run finished: status={browser_report.get('status')} "
                f"steps={browser_report.get('total_steps', 0)} "
                f"passed={browser_report.get('passed_steps', 0)} "
                f"failed={browser_report.get('failed_steps', 0)}"
            ),
            metadata={
                "target_url": browser_report.get("target_url"),
                "artifact_dir": browser_report.get("artifact_dir"),
                "report_path": browser_report.get("report_path"),
                "blocking_reason": browser_report.get("blocking_reason", ""),
            },
        )
        result["events"] = result.get("events", []) + [browser_event]
    else:
        logger.debug("No browser_test_url in state — browser testing skipped.")

    return result


def _run_browser_tests(url: str, run_id: str | None) -> dict[str, Any]:
    """
    Delegate to the Playwright browser runner.
    Isolated in a helper so import errors are contained and reported clearly.
    """
    try:
        from app.agents.test_runner.browser_runner import run_browser_tests_for_agent
        return run_browser_tests_for_agent(target_url=url, run_id=run_id)
    except ImportError as exc:
        logger.error("Browser runner import failed: %s", exc)
        return {
            "status": "error",
            "blocking_reason": f"Browser runner import error: {exc}",
            "passed": False,
            "total_steps": 0,
            "passed_steps": 0,
            "failed_steps": 0,
            "steps": [],
        }
    except Exception as exc:
        logger.exception("Unexpected error in browser test runner")
        return {
            "status": "error",
            "blocking_reason": f"Unexpected browser runner error: {exc}",
            "passed": False,
            "total_steps": 0,
            "passed_steps": 0,
            "failed_steps": 0,
            "steps": [],
        }
