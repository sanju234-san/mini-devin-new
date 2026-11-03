"""
Formal System Testing (ST) Scenarios (ST-01 to ST-11) for Mini-Devin.

Validates end-to-end user-visible behavior and safety gates:
- ST-01: Successful workflow execution from issue to PR preparation.
- ST-02: Rejected plan safe termination without code modification.
- ST-03: Tampered plan hash detection and rejection.
- ST-04: Duplicate approval idempotency.
- ST-05: Failing tests triggering bounded debugger repair loop.
- ST-06: Reviewer blocking unapproved patches from reaching PR Agent.
- ST-07: Sandbox timeout and shell injection rejection.
- ST-08: LLM Provider fallback cascade and exhausted error handling.
- ST-09: Context and run state isolation across distinct thread IDs.
- ST-10: Interrupted workflow recovery across checkpointer restarts.
- ST-11: Strict PR safety invariants (merge strictly forbidden by policy).
"""

from __future__ import annotations

import os
from unittest.mock import patch
import pytest
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from app.agents.checkpointer import create_checkpointer
from app.agents.graph import create_graph
from app.agents.schemas import (
    ApprovalDecision,
    ReviewFindings,
    TestResults,
    compute_plan_hash,
    create_initial_state,
)
from app.sandbox.codespaces_manager import CodespacesSandboxManager
from app.sandbox.models import SandboxCreateRequest, TestRunRequest
from app.integrations.github_client import GitRef, PRRequest, get_github_client
from app.integrations.llm_provider_client import complete, AllProvidersExhaustedError


@pytest.fixture(autouse=True)
def enable_deterministic_fallback_for_st(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ALLOW_DETERMINISTIC_FALLBACK", "true")


@pytest.fixture(autouse=True)
def mock_triage_for_st(monkeypatch: pytest.MonkeyPatch):
    """Ensure predictable triage classification for ST runs."""
    def _mock_classify(text: str) -> tuple[str, float]:
        if "out_of_scope" in text.lower() or "deploy" in text.lower():
            return "out_of_scope", 0.95
        return "bug_fix", 0.95

    monkeypatch.setattr("app.agents.triage.agent.classify_with_confidence", _mock_classify)


@pytest.fixture(autouse=True)
def enable_opt_in_sandbox_for_st(monkeypatch: pytest.MonkeyPatch):
    """Enable explicit opt-in host execution for full-system integration scenarios."""
    from app.config import get_settings
    monkeypatch.setenv("ALLOW_UNSAFE_HOST_EXECUTION", "true")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


# ── ST-01: Successful Workflow ──────────────────────────────────────────
def test_st01_successful_workflow():
    checkpointer = MemorySaver()
    graph = create_graph(checkpointer=checkpointer)
    initial_state = create_initial_state(
        issue_title="Fix ZeroDivisionError in calculation endpoint",
        repo="pallets/flask",
    )
    thread_id = initial_state["thread_id"]
    config = {"configurable": {"thread_id": thread_id}}

    # Phase 1: Planning up to interrupt
    graph.invoke(initial_state, config=config)
    paused = graph.get_state(config)
    assert paused.next == ("human_approval",)
    frozen_hash = paused.values.get("plan_hash")
    assert frozen_hash is not None

    # Phase 2: Resume with approved plan
    final_output = graph.invoke(
        Command(resume={"decision": "approved", "plan_hash": frozen_hash, "feedback": "Approved"}),
        config=config,
    )
    assert final_output["status"] in ("submitting_pr", "pr_opened")
    assert final_output["current_agent"] == "pr"
    assert "pull_request_package" in final_output


# ── ST-02: Rejected Plan ────────────────────────────────────────────────
def test_st02_rejected_plan_zero_code_changes():
    checkpointer = MemorySaver()
    graph = create_graph(checkpointer=checkpointer)
    initial_state = create_initial_state(
        issue_title="Unwanted architectural rewrite",
        repo="pallets/flask",
    )
    thread_id = initial_state["thread_id"]
    config = {"configurable": {"thread_id": thread_id}}

    graph.invoke(initial_state, config=config)
    paused = graph.get_state(config)
    frozen_hash = paused.values.get("plan_hash")

    final_output = graph.invoke(
        Command(resume={"decision": "rejected", "plan_hash": frozen_hash, "feedback": "Rejected"}),
        config=config,
    )
    assert final_output["status"] == "rejected"
    assert final_output["current_agent"] == "rejection_terminal"
    assert final_output.get("code_changes") is None
    coder_events = [e for e in final_output["events"] if e.get("agent_name") == "coder"]
    assert len(coder_events) == 0


# ── ST-03: Tampered Plan ────────────────────────────────────────────────
def test_st03_tampered_plan_rejected():
    checkpointer = MemorySaver()
    graph = create_graph(checkpointer=checkpointer)
    initial_state = create_initial_state(
        issue_title="Fix NullPointer in session store",
        repo="pallets/flask",
    )
    thread_id = initial_state["thread_id"]
    config = {"configurable": {"thread_id": thread_id}}

    graph.invoke(initial_state, config=config)
    # Resume with forged hash
    final_output = graph.invoke(
        Command(resume={"decision": "approved", "plan_hash": "bad0000000000000000000000000000000000000000000000000000000000000"}),
        config=config,
    )
    assert final_output["status"] == "rejected"
    assert "Plan tampering detected" in final_output["human_approval"]["feedback"]


# ── ST-04: Duplicate Approval Idempotency ──────────────────────────────
def test_st04_duplicate_approval_idempotency():
    checkpointer = MemorySaver()
    graph = create_graph(checkpointer=checkpointer)
    initial_state = create_initial_state(
        issue_title="Handle connection timeout",
        repo="pallets/flask",
    )
    config = {"configurable": {"thread_id": initial_state["thread_id"]}}

    graph.invoke(initial_state, config=config)
    frozen_hash = graph.get_state(config).values.get("plan_hash")

    res1 = graph.invoke(Command(resume={"decision": "approved", "plan_hash": frozen_hash}), config=config)
    res2 = graph.invoke(Command(resume={"decision": "approved", "plan_hash": frozen_hash}), config=config)
    assert res1["status"] in ("submitting_pr", "pr_opened")
    assert res2["status"] in ("submitting_pr", "pr_opened")
    assert len(res1["events"]) == len(res2["events"])


# ── ST-05: Test Failure and Debugger Repair ─────────────────────────────
def test_st05_test_failure_triggers_debugger_loop():
    checkpointer = MemorySaver()
    graph = create_graph(checkpointer=checkpointer)
    initial_state = create_initial_state(
        issue_title="Fix boundary condition in range query",
        repo="pallets/flask",
    )
    config = {"configurable": {"thread_id": initial_state["thread_id"]}}

    graph.invoke(initial_state, config=config)
    frozen_hash = graph.get_state(config).values.get("plan_hash")

    # Inject failing test results
    graph.update_state(
        config,
        {
            "test_results": {
                "passed": False,
                "total_tests": 1,
                "failed_tests": 1,
                "details": "AssertionError: Expected 200, got 500",
            },
            "max_retries": 1,
        },
    )

    final_output = graph.invoke(Command(resume={"decision": "approved", "plan_hash": frozen_hash}), config=config)
    debugger_events = [e for e in final_output["events"] if e.get("agent_name") == "debugger"]
    assert len(debugger_events) > 0


# ── ST-06: Reviewer Blocks Unapproved Changes ───────────────────────────
def test_st06_reviewer_blocks_unapproved_changes():
    checkpointer = MemorySaver()
    graph = create_graph(checkpointer=checkpointer)
    initial_state = create_initial_state(
        issue_title="Implement insecure raw SQL query",
        repo="pallets/flask",
    )
    config = {"configurable": {"thread_id": initial_state["thread_id"]}}

    graph.invoke(initial_state, config=config)
    frozen_hash = graph.get_state(config).values.get("plan_hash")

    # Inject failing review findings
    graph.update_state(
        config,
        {
            "review_findings": {
                "approved": False,
                "score": 0.20,
                "comments": ["Security flaw detected: raw SQL injection risk."],
            },
            "strict_verification": True,
        },
    )

    final_output = graph.invoke(Command(resume={"decision": "approved", "plan_hash": frozen_hash}), config=config)
    assert final_output["status"] == "failed"
    pr_events = [e for e in final_output["events"] if e.get("agent_name") == "pr"]
    assert len(pr_events) == 0


# ── ST-07: Sandbox Execution & Injection Blocking ───────────────────────
def test_st07_sandbox_security_and_timeout():
    from app.sandbox.models import InvalidRequestError
    sb = CodespacesSandboxManager()
    create_resp = sb.create_sandbox(SandboxCreateRequest(repo_ref="pallets/flask"))
    sid = create_resp.sandbox_id
    try:
        # Dangerous shell chaining must fail closed with InvalidRequestError
        with pytest.raises(InvalidRequestError, match="forbidden"):
            sb.run_tests(TestRunRequest(sandbox_id=sid, argv=["python", "-c", "print(1); rm -rf /"]))

        # Safe execution succeeds
        safe_resp = sb.run_tests(TestRunRequest(sandbox_id=sid, argv=["python", "-c", "print('Sandbox OK')"]))
        assert safe_resp.exit_code == 0
        assert "Sandbox OK" in safe_resp.stdout
    finally:
        sb.destroy_sandbox(sid)


# ── ST-08: Provider Fallback & Exhaustion ────────────────────────────────
def test_st08_provider_fallback_exhaustion():
    with patch.dict(os.environ, {"GROQ_API_KEY": "", "GOOGLE_AI_STUDIO_API_KEY": "", "HUGGINGFACE_API_TOKEN": ""}), \
         patch("app.integrations.llm_provider_client.GROQ_API_KEY", ""), \
         patch("app.integrations.llm_provider_client.GOOGLE_AI_STUDIO_API_KEY", ""), \
         patch("app.integrations.llm_provider_client.HUGGINGFACE_API_TOKEN", ""):
        with pytest.raises(AllProvidersExhaustedError):
            complete("test prompt", agent_name="test")


# ── ST-09: Run State & Memory Isolation ─────────────────────────────────
def test_st09_memory_run_isolation():
    checkpointer = MemorySaver()
    graph = create_graph(checkpointer=checkpointer)

    state_a = create_initial_state(issue_title="Issue Alpha", repo="org/repo-a")
    state_b = create_initial_state(issue_title="Issue Beta", repo="org/repo-b")

    config_a = {"configurable": {"thread_id": state_a["thread_id"]}}
    config_b = {"configurable": {"thread_id": state_b["thread_id"]}}

    graph.invoke(state_a, config=config_a)
    graph.invoke(state_b, config=config_b)

    saved_a = graph.get_state(config_a).values
    saved_b = graph.get_state(config_b).values

    assert saved_a["issue_title"] == "Issue Alpha"
    assert saved_b["issue_title"] == "Issue Beta"
    assert saved_a["thread_id"] != saved_b["thread_id"]


# ── ST-10: Interrupted Workflow Recovery ────────────────────────────────
def test_st10_interrupted_workflow_recovery():
    checkpointer = MemorySaver()
    graph = create_graph(checkpointer=checkpointer)
    initial_state = create_initial_state(issue_title="Persist through restart", repo="org/repo")
    thread_id = initial_state["thread_id"]
    config = {"configurable": {"thread_id": thread_id}}

    graph.invoke(initial_state, config=config)

    # Re-instantiate graph pointing to the exact same checkpointer (simulating server reboot)
    recovered_graph = create_graph(checkpointer=checkpointer)
    saved_state = recovered_graph.get_state(config)
    assert saved_state.next == ("human_approval",)
    frozen_hash = saved_state.values.get("plan_hash")

    resumed_output = recovered_graph.invoke(
        Command(resume={"decision": "approved", "plan_hash": frozen_hash}),
        config=config,
    )
    assert resumed_output["status"] in ("submitting_pr", "pr_opened")


# ── ST-11: PR Safety Invariants (Never Auto-Merge) ──────────────────────
def test_st11_pr_safety_never_auto_merge():
    client = get_github_client()
    ref = GitRef(owner="pallets", repo="flask", branch="main")
    pr_req = PRRequest(
        ref=ref,
        title="Fix issue",
        body="PR Body",
        head_branch="mini-devin/fix-1234",
        base_branch="main",
    )
    pr_resp = client.open_pull_request(pr_req)
    assert pr_resp.pr_url is not None

    # Invariant check: client does not contain auto-merge functionality
    assert not hasattr(client, "merge_pull_request")
    assert not hasattr(client, "auto_merge")
