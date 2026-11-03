"""
Evaluation Reporting and Verification Framework for Mini-Devin.

Computes benchmark metrics across runs and generates evaluation reports
distinguishing:
- PASS: Verified passing tests and successful PR creation.
- FAIL: Explicit test failure or review rejection.
- SKIPPED: Safely halted as out_of_scope or unsupported.
- BLOCKED: Missing integration dependency (e.g. sandbox, provider, GitHub client).
- NOT RUN: Subsequent stages that did not execute due to an earlier stop.
- NOT VERIFIED: Sandbox test results missing, unrecorded, or unexecuted.
"""

from __future__ import annotations

import datetime
from enum import Enum
import json
import logging
from typing import Any, Optional, Sequence

logger = logging.getLogger(__name__)


class VerificationStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    SKIPPED = "SKIPPED"
    BLOCKED = "BLOCKED"
    NOT_RUN = "NOT_RUN"
    NOT_VERIFIED = "NOT_VERIFIED"


def categorize_run_outcome(state: dict[str, Any]) -> tuple[VerificationStatus, str]:
    """
    Categorize the outcome of a workflow run with strict distinction between
    verified passing results, unverified results, and integration blockers.
    """
    status = state.get("status", "")
    triage = state.get("triage") or {}
    human_approval = state.get("human_approval") or {}
    test_results = state.get("test_results")
    review_findings = state.get("review_findings")

    # 1. Out of Scope / Unsupported
    if status == "out_of_scope" or not triage.get("is_supported", True):
        return VerificationStatus.SKIPPED, "Issue classified as out_of_scope or unsupported."

    # 2. Plan Rejection
    approval_decision = (
        human_approval.get("decision")
        if isinstance(human_approval, dict)
        else getattr(human_approval, "decision", None)
    )
    if approval_decision in ("rejected", "reject") or status == "rejected":
        return VerificationStatus.FAIL, "Human operator rejected implementation plan."

    # 3. Missing or Unverified Sandbox Tests
    if test_results is None:
        if status in ("coding", "testing", "failed"):
            return (
                VerificationStatus.NOT_VERIFIED,
                "Sandbox verification tests were not recorded or could not execute.",
            )
        return VerificationStatus.NOT_RUN, "Execution did not reach the test verification stage."

    # 4. Explicit Test Failure
    passed = False
    if isinstance(test_results, dict):
        passed = bool(test_results.get("passed", False))
    elif hasattr(test_results, "passed"):
        passed = bool(test_results.passed)

    if not passed:
        details = (
            test_results.get("details", "")
            if isinstance(test_results, dict)
            else getattr(test_results, "details", "")
        )
        if "unimplemented" in details.lower() or "unconfigured" in details.lower():
            return VerificationStatus.BLOCKED, f"Blocked on sandbox integration: {details}"
        return VerificationStatus.FAIL, f"Sandbox verification tests failed: {details}"

    # 5. Review Findings
    review_approved = False
    if review_findings:
        if isinstance(review_findings, dict):
            review_approved = bool(review_findings.get("approved", False))
        elif hasattr(review_findings, "approved"):
            review_approved = bool(review_findings.approved)

    if not review_approved:
        return VerificationStatus.FAIL, "Automated code review rejected the proposed changes."

    # 6. Pull Request
    if status in ("pr_opened", "completed"):
        return VerificationStatus.PASS, "Workflow completed successfully with passing tests and PR."

    return VerificationStatus.NOT_VERIFIED, f"Run concluded in state '{status}' without verified completion."


def generate_evaluation_report(runs: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """
    Generate an evaluation report across a set of runs, ensuring unverified or
    blocked runs are never reported as passing.
    """
    counts = {s.value: 0 for s in VerificationStatus}
    run_details: list[dict[str, Any]] = []

    for idx, run in enumerate(runs, start=1):
        status, reason = categorize_run_outcome(run)
        counts[status.value] += 1
        run_details.append({
            "index": idx,
            "run_id": run.get("run_id", f"run_{idx}"),
            "repo": run.get("repo", "unknown"),
            "status": status.value,
            "reason": reason,
        })

    total = len(runs)
    pass_rate = round(counts[VerificationStatus.PASS.value] / total, 4) if total > 0 else 0.0

    return {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "total_runs": total,
        "counts": counts,
        "pass_rate": pass_rate,
        "runs": run_details,
    }
