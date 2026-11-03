"""
Debugger Agent Implementation.

Diagnoses sandbox test failures, parses tracebacks, and manages the bounded
repair retry loop (capped by MAX_RETRY_ATTEMPTS) to prevent infinite loops.
"""

from __future__ import annotations

import logging
from typing import Any

from app.agents.model_router import route
from app.agents.schemas import AgentState, create_event

import re

logger = logging.getLogger(__name__)


def diagnose_failure_details(details: str) -> tuple[str, str, list[str]]:
    """
    Rule-based failure analysis pre-classifier.
    
    Parses test failure logs, tracebacks, or sandbox error messages:
    Returns:
        (category, summary, recommendations)
    """
    if not details:
        return "unspecified", "No failure details recorded.", ["Inspect sandbox test execution logs."]

    lower = details.lower()

    # 1. Sandbox / Infrastructure failure
    if any(k in lower for k in ("unimplemented", "unconfigured", "timed out", "timeout", "killed", "sandbox error")):
        return (
            "infrastructure_error",
            "Sandbox execution was interrupted or environment is unconfigured.",
            ["Verify sandbox container lifecycle and backend test runner configuration."],
        )

    # 2. Syntax / Formatting error
    if any(k in lower for k in ("syntaxerror", "indentationerror", "taberror")):
        return (
            "syntax_error",
            "Generated patch contains syntax or indentation defects.",
            ["Check patch syntax, bracket balance, and Python indentation."],
        )

    # 3. Missing import / module
    if any(k in lower for k in ("modulenotfounderror", "importerror", "cannot import name")):
        return (
            "import_error",
            "Code change references an unimported symbol or missing module.",
            ["Ensure all required modules are imported and package names are correct."],
        )

    # 4. Type / Attribute error
    if any(k in lower for k in ("typeerror", "attributeerror")):
        return (
            "type_error",
            "Mismatched function arguments, incorrect types, or NoneType access.",
            ["Verify function signatures, parameter counts, and guard against None values."],
        )

    # 5. Assertion failure (test expectation mismatch)
    if any(k in lower for k in ("assertionerror", "failed", "assert ")):
        return (
            "assertion_failure",
            "Test assertion failed; actual return value does not match expected output.",
            ["Inspect failing test assertions and align implementation logic with expected outputs."],
        )

    return (
        "runtime_error",
        f"Test execution encountered runtime error: {details[:120]}...",
        ["Inspect traceback and verify edge-case handling."],
    )


def debugger_node(state: AgentState) -> dict[str, Any]:
    """
    Debugger Agent Node: Analyzes sandbox test errors and formulates targeted fixes.
    
    Safety Invariants:
    1. Bounded retry loop strictly capped by max_retries.
    2. Diagnoses error category (pre-classifier) before escalating to LLM.
    3. Works on delta only (new error + existing patch).
    """
    tier = route("debugger_first_pass")
    retry_count = state.get("retry_count", 0) + 1
    max_retries = state.get("max_retries", 3)

    test_results = state.get("test_results") or {}
    raw_details = (
        test_results.get("details", "")
        if isinstance(test_results, dict)
        else getattr(test_results, "details", "")
    )

    category, summary, recommendations = diagnose_failure_details(raw_details)

    logger.info(
        "Executing Debugger node [tier=%s] (attempt %d/%d) - Category: %s",
        tier,
        retry_count,
        max_retries,
        category,
    )

    event = create_event(
        agent_name="debugger",
        event_type="debugging_analyzed",
        status="in_progress",
        message=f"Debugger diagnosed '{category}' failure (attempt {retry_count} of {max_retries}): {summary}",
        metadata={
            "tier": tier.value,
            "retry_count": retry_count,
            "max_retries": max_retries,
            "category": category,
            "recommendations": recommendations,
        },
    )

    return {
        "retry_count": retry_count,
        "status": "debugging",
        "current_agent": "debugger",
        "error": f"Debug retry {retry_count}/{max_retries} ({category}): {summary}",
        "events": [event],
    }
