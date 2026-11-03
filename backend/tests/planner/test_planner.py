"""
Comprehensive unit and integration test suite for Milestone 2:
Evidence-Grounded Planner and Frozen Plan Approval.

Verifies:
1. Detailed plan generation grounded in authentic retrieved code snippets.
2. Accurate symbol and line-range evidence attribution.
3. Handling of missing checkout, indexing failure, and empty results.
4. Deterministic plan serialization and stable cryptographic hashing.
5. Plan tampering detection and rejection on hash mismatch.
6. Plan modification after approval requiring new approval.
7. Duplicate approval clicks handled idempotently.
8. Rejection safety guaranteeing no downstream execution.
9. Markdown preview formatting for Chainlit side panel.
10. Mocked LLM completion vs. deterministic synthesis fallback.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from app.agents.graph import create_graph
from app.agents.planner.agent import planner_node, synthesize_deterministic_plan
from app.agents.schemas import (
    ApprovalDecision,
    ImplementationPlan,
    PlanEvidence,
    PlanStep,
    RootCauseAnalysis,
    compute_plan_hash,
    create_initial_state,
    format_plan_as_markdown,
    serialize_plan_canonical,
)


@pytest.fixture(autouse=True)
def enable_opt_in_sandbox_for_planner_tests(monkeypatch: pytest.MonkeyPatch):
    """Enable explicit opt-in host execution for planner approval downstream tests."""
    from app.config import get_settings
    monkeypatch.setenv("ALLOW_UNSAFE_HOST_EXECUTION", "true")
    monkeypatch.setenv("ALLOW_DETERMINISTIC_FALLBACK", "true")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def sample_retrieved_context() -> dict:
    """Fixture providing authentic repository retrieval evidence."""
    return {
        "files": ["src/calculator.py", "tests/test_calculator.py"],
        "snippets": [
            {
                "file_path": "src/calculator.py",
                "start_line": 10,
                "end_line": 25,
                "content": (
                    "class Calculator:\n"
                    "    def divide(self, a: float, b: float) -> float:\n"
                    "        if b == 0:\n"
                    "            raise ZeroDivisionError('Division by zero is undefined')\n"
                    "        return a / b\n"
                ),
                "score": 4.5,
                "score_type": "lexical_bm25",
            },
            {
                "file_path": "tests/test_calculator.py",
                "start_line": 1,
                "end_line": 15,
                "content": (
                    "import pytest\n"
                    "from src.calculator import Calculator\n\n"
                    "def test_divide_valid():\n"
                    "    calc = Calculator()\n"
                    "    assert calc.divide(10, 2) == 5\n"
                ),
                "score": 3.8,
                "score_type": "lexical_bm25",
            },
        ],
        "summary": "Retrieved 2 snippets across 2 files via lexical_bm25.",
        "is_mock": False,
        "retrieval_status": "success",
        "retrieval_method": "lexical_bm25",
    }


# ── Test 1: Detailed Plan Generated from Real Snippets ────────────────

def test_detailed_plan_generated_from_real_snippets(sample_retrieved_context: dict):
    """Planner produces a fully detailed plan grounded in real code evidence."""
    state = {
        "repo": "local/calc_repo",
        "issue_title": "Fix ZeroDivisionError handling in Calculator.divide",
        "issue_body": "Passing b=0 causes unhandled crash in API",
        "retrieved_context": sample_retrieved_context,
        "events": [],
    }

    result = planner_node(state)
    assert result["status"] == "awaiting_approval"
    assert result["current_agent"] == "planner"
    assert "plan" in result
    assert "plan_hash" in result
    assert len(result["plan_hash"]) == 64  # SHA-256

    plan = result["plan"]
    # 1. Summary and explanation
    assert "Fix: Fix ZeroDivisionError handling" in plan["summary"]
    assert "src/calculator.py" in plan["explanation"]

    # 2. Evidence items grounded in snippets
    evidence = plan.get("evidence_items", [])
    assert len(evidence) >= 1
    ev0 = evidence[0]
    assert ev0["file_path"] == "src/calculator.py"
    assert ev0["start_line"] == 10
    assert ev0["end_line"] == 25
    assert "Calculator" in ev0["symbol"] or "divide" in ev0["symbol"]

    # 3. Root cause separating evidence from hypotheses
    rc = plan.get("root_cause")
    assert rc is not None
    assert len(rc["evidence_backed_findings"]) > 0
    assert len(rc["hypotheses"]) > 0

    # 4. File changes and steps
    assert len(plan["steps"]) >= 3
    assert plan["affected_files"] == ["src/calculator.py", "tests/test_calculator.py"]

    # 5. Engineering sections
    assert len(plan["acceptance_criteria"]) >= 2
    assert "existing_tests_to_inspect" in plan["test_strategy"]
    assert "tests/test_calculator.py" in plan["test_strategy"]["existing_tests_to_inspect"]
    assert len(plan["security_considerations"]) > 0
    assert len(plan["risks_and_assumptions"]) > 0
    assert len(plan["suggested_verification_commands"]) > 0
    assert plan["provenance"] == "deterministic_evidence_synthesis"


# ── Test 2: Missing Checkout Handling ─────────────────────────────────

def test_planner_handles_missing_checkout_truthfully():
    """When repo checkout is missing, planner does not invent fake facts or lines."""
    state = {
        "repo": "acme/uncloned_repo",
        "issue_title": "Add rate limiter",
        "issue_body": "Protect endpoint against abuse",
        "retrieved_context": {
            "files": [],
            "snippets": [],
            "summary": "Target repository is not checked out locally.",
            "is_mock": False,
            "retrieval_status": "missing_checkout",
            "retrieval_method": "none",
        },
        "events": [],
    }

    result = planner_node(state)
    plan = result["plan"]
    # Summary now starts with 'Blocked — Repository Checkout Required:'
    assert "Blocked" in plan["summary"] or "Add rate limiter" in plan["summary"]
    # Must NOT invent file paths when no files were retrieved.
    assert plan["affected_files"] == []
    # Exactly one step (inspect only, no invented modify steps).
    assert len(plan["steps"]) == 1
    assert plan["steps"][0]["action"] == "inspect"
    # Provenance must indicate missing checkout.
    assert plan["provenance"] == "deterministic_unverified_missing_checkout"


# ── Test 3: No Results Handling ───────────────────────────────────────

def test_planner_handles_no_matching_results_truthfully():
    """When retrieval yields no results, planner requests additional context."""
    state = {
        "repo": "local/empty_match_repo",
        "issue_title": "Update cosmic rays detector",
        "issue_body": "Hardware interface sensor",
        "retrieved_context": {
            "files": [],
            "snippets": [],
            "summary": "No matching code snippets found.",
            "is_mock": False,
            "retrieval_status": "no_results",
            "retrieval_method": "lexical_bm25",
        },
        "events": [],
    }

    result = planner_node(state)
    plan = result["plan"]
    assert "No Matching Snippets" in plan["summary"]
    assert plan["affected_files"] == []
    assert plan["evidence_items"] == []
    assert plan["provenance"] == "deterministic_no_results"


# ── Test 4: Deterministic Plan Serialization & Stable Hashing ─────────

def test_deterministic_plan_serialization_and_hashing(sample_retrieved_context: dict):
    """Plan serialization and hashing must be deterministic across calls and orderings."""
    plan1 = synthesize_deterministic_plan(
        title="Fix division by zero",
        body="details",
        retrieved=sample_retrieved_context,
        repo="local/repo",
    )
    plan2 = synthesize_deterministic_plan(
        title="Fix division by zero",
        body="details",
        retrieved=sample_retrieved_context,
        repo="local/repo",
    )

    hash1 = compute_plan_hash(plan1)
    hash2 = compute_plan_hash(plan2)
    assert hash1 == hash2
    assert len(hash1) == 64

    # Any mutation in the plan must produce a different hash
    plan1_dict = plan1.model_dump(mode="json")
    plan1_dict["summary"] = "Fix division by zero (modified)"
    hash_modified = compute_plan_hash(plan1_dict)
    assert hash_modified != hash1


# ── Test 5: Approval Bound to Frozen Plan Hash in Workflow ───────────

def test_workflow_approval_bound_to_frozen_plan_hash(sample_retrieved_context: dict):
    """Human approval node successfully binds to the exact frozen plan hash."""
    checkpointer = MemorySaver()
    graph = create_graph(checkpointer=checkpointer)

    initial_state = create_initial_state(
        issue_title="Fix ZeroDivisionError in calculation endpoint",
        issue_body="When denominator is zero, the service crashes with 500.",
        repo="local/calculator",
    )
    initial_state["retrieved_context"] = sample_retrieved_context
    thread_id = initial_state["thread_id"]
    config = {"configurable": {"thread_id": thread_id}}

    # Phase 1: Run to interrupt
    graph.invoke(initial_state, config=config)
    saved_state = graph.get_state(config)
    assert saved_state.next == ("human_approval",)

    frozen_hash = saved_state.values.get("plan_hash")
    frozen_version = saved_state.values.get("plan_version")
    assert frozen_hash is not None
    assert frozen_version is not None

    # Phase 2: Resume with matching frozen hash
    resume_cmd = Command(
        resume={
            "decision": "approved",
            "feedback": "Approved by reviewer",
            "plan_hash": frozen_hash,
            "plan_version": frozen_version,
        }
    )
    final_output = graph.invoke(resume_cmd, config=config)
    # After approval the graph advances through coder/reviewer stubs to PR agent.
    # Accept any post-approval status (graph has grown since this test was written).
    assert final_output["status"] in {"completed", "reviewing", "approved", "submitting_pr", "pr_opened"}, (
        f"Unexpected post-approval status: {final_output['status']!r}"
    )


# ── Test 6: Plan Tampering / Hash Mismatch Rejection ─────────────────

def test_approval_rejects_plan_hash_mismatch(sample_retrieved_context: dict):
    """Resuming with a mismatched plan hash is rejected as plan tampering."""
    checkpointer = MemorySaver()
    graph = create_graph(checkpointer=checkpointer)

    initial_state = create_initial_state(
        issue_title="Fix ZeroDivisionError in calculation endpoint",
        issue_body="When denominator is zero, the service crashes with 500.",
        repo="local/calculator",
    )
    initial_state["retrieved_context"] = sample_retrieved_context
    config = {"configurable": {"thread_id": initial_state["thread_id"]}}

    graph.invoke(initial_state, config=config)

    # Resume with wrong plan hash (simulating tampering)
    resume_cmd = Command(
        resume={
            "decision": "approved",
            "plan_hash": "0000000000000000000000000000000000000000000000000000000000000000",
        }
    )
    final_output = graph.invoke(resume_cmd, config=config)
    # Tampering forces rejection
    assert final_output["status"] == "rejected"
    assert "Plan tampering detected" in final_output["human_approval"]["feedback"]


# ── Test 7: Duplicate Approval Idempotency ────────────────────────────

def test_duplicate_approval_is_idempotent(sample_retrieved_context: dict):
    """Submitting duplicate approvals does not re-execute or duplicate events."""
    checkpointer = MemorySaver()
    graph = create_graph(checkpointer=checkpointer)

    initial_state = create_initial_state(
        issue_title="Fix ZeroDivisionError in calculation endpoint",
        issue_body="When denominator is zero, the service crashes with 500.",
        repo="local/calculator",
    )
    initial_state["retrieved_context"] = sample_retrieved_context
    config = {"configurable": {"thread_id": initial_state["thread_id"]}}

    graph.invoke(initial_state, config=config)
    saved_state = graph.get_state(config)
    frozen_hash = saved_state.values.get("plan_hash")

    first_res = graph.invoke(
        Command(resume={"decision": "approved", "plan_hash": frozen_hash}),
        config=config,
    )
    # After approval the graph advances through reviewer/coder stubs to PR agent.
    assert first_res["status"] in {"completed", "reviewing", "approved", "submitting_pr", "pr_opened"}, (
        f"Unexpected post-approval status: {first_res['status']!r}"
    )
    first_event_count = len(first_res["events"])

    # Duplicate approval invocation (graph already past interrupt — should be idempotent)
    second_res = graph.invoke(
        Command(resume={"decision": "approved", "plan_hash": frozen_hash}),
        config=config,
    )
    # Must remain in a post-approval state without duplicate event explosion
    assert second_res["status"] in {"completed", "reviewing", "approved", "submitting_pr", "pr_opened"}
    assert len(second_res["events"]) == first_event_count


# ── Test 8: Rejection Terminates Safely ────────────────────────────────

def test_plan_rejection_terminates_safely(sample_retrieved_context: dict):
    """Plan rejection cleanly halts workflow at rejection_terminal without code handoff."""
    checkpointer = MemorySaver()
    graph = create_graph(checkpointer=checkpointer)

    initial_state = create_initial_state(
        issue_title="Fix ZeroDivisionError in calculation endpoint",
        issue_body="When denominator is zero, the service crashes with 500.",
        repo="local/calculator",
    )
    initial_state["retrieved_context"] = sample_retrieved_context
    config = {"configurable": {"thread_id": initial_state["thread_id"]}}

    graph.invoke(initial_state, config=config)

    # Resume with rejection
    res = graph.invoke(
        Command(resume={"decision": "rejected", "feedback": "Unacceptable architectural scope"}),
        config=config,
    )
    assert res["status"] == "rejected"
    assert res["current_agent"] == "rejection_terminal"
    assert res["human_approval"]["decision"] == "rejected"
    assert res["status"] == "rejected"
    assert res["current_agent"] == "rejection_terminal"
    assert res["human_approval"]["decision"] == "rejected"


# ── Test 9: Markdown Formatting for Preview ──────────────────────────

def test_format_plan_as_markdown(sample_retrieved_context: dict):
    """Verify Markdown preview generates all 11 required sections cleanly."""
    plan = synthesize_deterministic_plan(
        title="Handle ZeroDivisionError in Calculator",
        body="Divide by zero details",
        retrieved=sample_retrieved_context,
        repo="local/calc",
    )
    plan.plan_hash = compute_plan_hash(plan)

    md = format_plan_as_markdown(plan)

    # Verify key sections are present
    assert "# 📋 Implementation Plan: Fix: Handle ZeroDivisionError" in md
    assert "## 1. Summary & Intended Behavior" in md
    assert "## 2. Root Cause Analysis" in md
    assert "### 🔍 Evidence-Supported Findings" in md
    assert "### 💡 Hypotheses (Awaiting Further Evidence)" in md
    assert "## 3. Grounded Code Evidence" in md
    assert "## 4. Proposed Changes by File" in md
    assert "## 5. Implementation Steps" in md
    assert "## 6. Acceptance Criteria" in md
    assert "## 7. Test Strategy" in md
    assert "## 8. Dependencies & Interfaces" in md
    assert "## 9. Security & Guardrail Considerations" in md
    assert "## 10. Risks & Assumptions" in md
    assert "## 11. Suggested Verification Commands" in md
    assert "Plan Hash:" in md


# ── Test 10: Mocked LLM Provider Integration ─────────────────────────

def test_mocked_llm_provider_generation(sample_retrieved_context: dict):
    """When LLM provider succeeds, its output is parsed and labeled as llm_generated."""
    fake_llm_plan = {
        "summary": "Fix: Handle ZeroDivisionError via LLM",
        "explanation": "LLM synthesized analysis grounded in code evidence.",
        "steps": [
            {
                "step_number": 1,
                "description": "Add zero check to divide()",
                "target_file": "src/calculator.py",
                "action": "modify",
            }
        ],
        "affected_files": ["src/calculator.py"],
        "estimated_complexity": "low",
        "plan_version": "v1",
        "acceptance_criteria": ["Zero division raises graceful exception"],
    }

    with patch("app.integrations.llm_provider_client.complete", return_value=json.dumps(fake_llm_plan)):
        state = {
            "repo": "local/calc_repo",
            "issue_title": "Fix division",
            "issue_body": "denominator zero",
            "retrieved_context": sample_retrieved_context,
            "events": [],
        }
        res = planner_node(state)
        assert res["plan"]["provenance"] == "llm_generated"
        assert res["plan"]["summary"] == "Fix: Handle ZeroDivisionError via LLM"
        assert len(res["plan_hash"]) == 64


# ── Test 11: Missing Checkout Produces No Invented File Paths ─────────

def test_missing_checkout_produces_no_invented_file_paths():
    """Missing checkout must not produce invented src/<kw>.py or tests/test_<kw>.py paths."""
    plan = synthesize_deterministic_plan(
        title="Fix cosmic ray burst handler",
        body="Sensor hardware interface is broken",
        retrieved={
            "files": [],
            "snippets": [],
            "retrieval_status": "missing_checkout",
            "retrieval_method": "none",
        },
        repo="acme/hardware-sensors",
    )
    # No affected files at all — checkout required first.
    assert plan.affected_files == [], (
        f"Expected no invented file paths, got: {plan.affected_files}"
    )
    # No steps should reference invented file paths like src/*.py or tests/test_*.py.
    for step in plan.steps:
        assert step.target_file not in (
            "src/cosmic.py", "src/burst.py",
            "tests/test_cosmic.py", "tests/test_burst.py",
        ), f"Invented file path in step target_file: {step.target_file}"
        assert step.action == "inspect", (
            f"Expected only inspect steps in missing-checkout plan, got: {step.action}"
        )
    assert plan.provenance == "deterministic_unverified_missing_checkout"


# ── Test 12: No Matching Snippets Produces No Invented Affected Files ──

def test_no_matching_snippets_produces_no_invented_affected_files():
    """When retrieval yields no snippets, affected_files must remain empty."""
    plan = synthesize_deterministic_plan(
        title="Update cosmic rays detector",
        body="Hardware interface sensor",
        retrieved={
            "files": [],
            "snippets": [],
            "retrieval_status": "no_results",
            "retrieval_method": "lexical_bm25",
        },
        repo="local/empty_match_repo",
    )
    assert plan.affected_files == [], (
        f"Expected empty affected_files for no-results, got: {plan.affected_files}"
    )
    assert plan.evidence_items == []
    # Hypotheses must not be presented as evidence-backed findings.
    assert plan.root_cause is not None
    assert plan.root_cause.evidence_backed_findings == []
    assert plan.provenance == "deterministic_no_results"


# ── Test 13: Evidence-Backed Plans Preserve Authentic File Paths ───────

def test_evidence_backed_plan_preserves_authentic_file_paths(sample_retrieved_context: dict):
    """Evidence-backed plans must only include file paths from retrieved evidence."""
    plan = synthesize_deterministic_plan(
        title="Fix ZeroDivisionError handling",
        body="b=0 crashes API",
        retrieved=sample_retrieved_context,
        repo="local/calc_repo",
    )
    retrieved_files = set(sample_retrieved_context["files"])
    for f in plan.affected_files:
        assert f in retrieved_files, (
            f"affected_file '{f}' was not in retrieved evidence {retrieved_files}"
        )
    for ev in plan.evidence_items:
        assert ev.file_path in retrieved_files, (
            f"evidence_item file_path '{ev.file_path}' not in retrieved evidence"
        )


# ── Test 14: Insufficient Evidence Produces a Cautious Investigation Plan

def test_insufficient_evidence_produces_cautious_plan():
    """When snippets exist but no files list is provided, plan must not invent a target."""
    # Snippets only — no files list (e.g. retrieval only returned content, not paths)
    plan = synthesize_deterministic_plan(
        title="Fix null pointer in auth service",
        body="Login endpoint crashes on empty token",
        retrieved={
            # files list is empty even though snippets exist — edge case
            "files": [],
            "snippets": [
                {
                    "file_path": "auth/login.py",
                    "start_line": 10,
                    "end_line": 20,
                    "content": "def login(token):\n    if not token:\n        raise ValueError('empty token')",
                    "score": 3.0,
                }
            ],
            "retrieval_status": "success",
            "retrieval_method": "lexical_bm25",
        },
        repo="local/auth_repo",
    )
    # The snippet's file_path may be used since it was retrieved — but if files=[]
    # and we only have snippet content, at minimum we must not claim a test path.
    assert "tests/test_login.py" not in plan.affected_files, (
        "Planner invented a test file path that was not in retrieved evidence."
    )
    # Evidence items should map to the retrieved snippet
    assert len(plan.evidence_items) >= 1
    assert plan.evidence_items[0].file_path == "auth/login.py"


# ── Test 15: LLM Output With Unsupported Paths Is Flagged ─────────────

def test_llm_output_with_unsupported_paths_flagged_as_unverified(sample_retrieved_context: dict):
    """LLM plan paths not in retrieved evidence are flagged as unverified hypotheses."""
    fake_llm_plan = {
        "summary": "Fix ZeroDivisionError via LLM",
        "explanation": "LLM analysis.",
        "steps": [
            {
                "step_number": 1,
                "description": "Modify the unrelated file.",
                "target_file": "lib/completely_unrelated.py",
                "action": "modify",
            }
        ],
        # Path not in retrieved files=["src/calculator.py", "tests/test_calculator.py"]
        "affected_files": ["lib/completely_unrelated.py"],
        "estimated_complexity": "low",
        "plan_version": "v1",
        "acceptance_criteria": ["Test passes"],
    }

    with patch("app.integrations.llm_provider_client.complete", return_value=json.dumps(fake_llm_plan)):
        state = {
            "repo": "local/calc_repo",
            "issue_title": "Fix division",
            "issue_body": "denominator zero",
            "retrieved_context": sample_retrieved_context,
            "events": [],
        }
        res = planner_node(state)
        plan = res["plan"]
        # Provenance must signal unverified paths.
        assert plan["provenance"] == "llm_generated_unverified_paths", (
            f"Expected 'llm_generated_unverified_paths', got: {plan['provenance']}"
        )
        # The unverified path must appear in risks_and_assumptions.
        risks_text = " ".join(plan.get("risks_and_assumptions", []))
        assert "completely_unrelated.py" in risks_text or "unverified" in risks_text.lower(), (
            "Expected unverified path warning in risks_and_assumptions."
        )
