"""
Automated tests for Mini-Devin's Day 1 LangGraph workflow and checkpointing.

Verifies:
1. Execution from issue input to Planner interrupt.
2. Preservation of implementation plan at human approval interrupt.
3. Resuming approved plan using the same thread_id.
4. Safe termination of rejected plans without code generation.
5. Out-of-scope issues routed to safe stopping path.
6. Validation and safe handling of missing/invalid issue inputs.
7. Checkpoint state retention across interrupt and resume.
8. Retry limits and initial state defaults.
"""

from __future__ import annotations

import asyncio
import pytest
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from app.agents.checkpointer import create_checkpointer
from app.agents.graph import create_graph, create_workflow_graph
from app.agents.model_router import ModelTier, route
from app.agents.schemas import (
    AgentState,
    ApprovalDecision,
    ImplementationPlan,
    ReviewFindings,
    TestResults,
    TriageClassification,
    create_initial_state,
)

TestResults.__test__ = False


@pytest.fixture
def memory_checkpointer() -> MemorySaver:
    """Provide a fresh, isolated checkpointer for each test."""
    return create_checkpointer()


@pytest.fixture(autouse=True)
def mock_graph_triage_classifier(monkeypatch: pytest.MonkeyPatch):
    """Monkeypatch triage classifier for graph execution tests."""
    monkeypatch.setenv("ALLOW_DETERMINISTIC_FALLBACK", "true")
    def _mock_classify(text: str) -> tuple[str, float]:
        lower = text.lower()
        if any(kw in lower for kw in ["cors", "rfc", "vitepress", "kubernetes", "won't fix"]):
            return "out_of_scope", 0.95
        return "bug_fix", 0.95

    monkeypatch.setattr("app.agents.triage.agent.classify_with_confidence", _mock_classify)


@pytest.fixture(autouse=True)
def enable_opt_in_sandbox_for_graph_tests(monkeypatch: pytest.MonkeyPatch):
    """Enable explicit opt-in host execution for graph pipeline unit tests."""
    from app.config import get_settings
    monkeypatch.setenv("ALLOW_UNSAFE_HOST_EXECUTION", "true")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


# ΓöÇΓöÇ Test 1: Graph execution to planner interrupt ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇ

def test_graph_executes_to_planner_interrupt(memory_checkpointer: MemorySaver):
    """Workflow should execute Triage -> Retrieval -> Planner and pause at Human Approval."""
    graph = create_graph(checkpointer=memory_checkpointer)
    initial_state = create_initial_state(
        issue_title="Fix ZeroDivisionError in calculation endpoint",
        issue_body="When denominator is zero, the service crashes with 500.",
        repo="acme/calculator",
    )
    thread_id = initial_state["thread_id"]
    config = {"configurable": {"thread_id": thread_id}}

    # Invoke graph: should halt at human_approval interrupt
    graph.invoke(initial_state, config=config)

    # Inspect checkpointed state
    saved_state = graph.get_state(config)
    assert saved_state.next == ("human_approval",), "Workflow should be paused waiting for approval"

    values = saved_state.values
    assert values["status"] == "awaiting_approval"
    assert values["current_agent"] == "planner"
    assert values["triage"] is not None
    assert values["triage"]["is_supported"] is True
    assert values["triage"]["classification"] in (
        TriageClassification.BUG.value,
        TriageClassification.FEATURE.value,
    )
    assert values["retrieved_context"] is not None
    assert values["retrieved_context"]["is_mock"] is False
    assert values["retrieved_context"]["retrieval_status"] == "missing_checkout"
    assert values["plan"] is not None
    assert len(values["plan"]["steps"]) > 0
    assert len(values["plan"]["affected_files"]) == 0


# ΓöÇΓöÇ Test 2: Plan preserved at human approval interrupt ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇ

def test_plan_preserved_at_approval_interrupt(memory_checkpointer: MemorySaver):
    """The implementation plan must be accurately persisted in the checkpoint."""
    graph = create_graph(checkpointer=memory_checkpointer)
    initial_state = create_initial_state(
        issue_title="Add OAuth2 token refresh handler",
        repo="org/auth-service",
    )
    config = {"configurable": {"thread_id": initial_state["thread_id"]}}

    graph.invoke(initial_state, config=config)
    saved_state = graph.get_state(config)

    # Check tasks and interrupts
    assert len(saved_state.tasks) > 0
    interrupts = saved_state.tasks[0].interrupts
    assert len(interrupts) > 0

    interrupt_payload = interrupts[0].value
    assert interrupt_payload["action"] == "request_approval"
    assert interrupt_payload["thread_id"] == initial_state["thread_id"]
    assert "plan" in interrupt_payload

    plan = saved_state.values["plan"]
    assert plan["summary"] == "Blocked — Repository Checkout Required: Add OAuth2 token refresh handler"
    assert len(plan["steps"]) == 1
    assert "affected_files" in plan


# ΓöÇΓöÇ Test 3: Approved plan resumes with same thread_id ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇ

def test_approved_plan_resumes_with_same_thread_id(memory_checkpointer: MemorySaver):
    """Resuming with approval must continue the same thread to completion."""
    graph = create_graph(checkpointer=memory_checkpointer)
    initial_state = create_initial_state(
        issue_title="Handle timeout in webhook delivery",
        repo="org/webhooks",
    )
    thread_id = initial_state["thread_id"]
    config = {"configurable": {"thread_id": thread_id}}

    # Phase 1: Pause at interrupt
    graph.invoke(initial_state, config=config)
    state_at_pause = graph.get_state(config)
    assert state_at_pause.next == ("human_approval",)

    # Phase 2: Resume with approval using the exact same thread_id
    approval_response = {
        "decision": "approved",
        "feedback": "Plan approved for automated code generation.",
    }
    resume_cmd = Command(resume=approval_response)
    final_output = graph.invoke(resume_cmd, config=config)

    # Phase 3: Assert final state
    assert final_output["status"] == "reviewing"
    assert final_output["current_agent"] == "reviewer"
    assert final_output["human_approval"]["decision"] == "approved"
    assert final_output["human_approval"]["feedback"] == approval_response["feedback"]

    # Verify coder, test_runner, and reviewer events were appended in sequence
    coder_events = [e for e in final_output["events"] if e.get("agent_name") == "coder"]
    assert len(coder_events) == 2
    assert coder_events[0]["event_type"] == "code_generation_started"
    assert coder_events[0]["status"] == "in_progress"

    test_runner_events = [e for e in final_output["events"] if e.get("agent_name") == "test_runner"]
    assert len(test_runner_events) == 1
    assert test_runner_events[0]["event_type"] in ("tests_started", "tests_completed")
    assert test_runner_events[0]["status"] in ("in_progress", "success")

    reviewer_events = [e for e in final_output["events"] if e.get("agent_name") == "reviewer"]
    assert len(reviewer_events) == 1
    assert reviewer_events[0]["event_type"] in ("review_started", "review_completed")
    assert reviewer_events[0]["status"] in ("in_progress", "success")

    # Verify state in checkpoint is fully finished
    final_state = graph.get_state(config)
    assert final_state.next == (), "Graph should have reached END"
    assert final_state.values["status"] == "reviewing"
    assert final_state.values["current_agent"] == "reviewer"


# ΓöÇΓöÇ Test 4: Rejected plan terminates safely ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇ

def test_rejected_plan_terminates_safely(memory_checkpointer: MemorySaver):
    """Rejected plans must terminate cleanly without proceeding to code generation."""
    graph = create_graph(checkpointer=memory_checkpointer)
    initial_state = create_initial_state(
        issue_title="Rewrite core engine in Rust",
        repo="org/backend",
    )
    thread_id = initial_state["thread_id"]
    config = {"configurable": {"thread_id": thread_id}}

    # Pause at interrupt
    graph.invoke(initial_state, config=config)

    # Resume with rejection
    rejection_response = {
        "decision": "rejected",
        "feedback": "Out of scope for this sprint.",
    }
    resume_cmd = Command(resume=rejection_response)
    final_output = graph.invoke(resume_cmd, config=config)

    assert final_output["status"] == "rejected"
    assert final_output["current_agent"] == "rejection_terminal"
    assert final_output["human_approval"]["decision"] == "rejected"

    # Confirm no downstream code generation occurred
    assert final_output.get("code_changes") is None
    coder_events = [e for e in final_output["events"] if e.get("agent_name") == "coder"]
    assert len(coder_events) == 0, "Rejected plan must not invoke coder stub"
    test_runner_events = [e for e in final_output["events"] if e.get("agent_name") == "test_runner"]
    assert len(test_runner_events) == 0, "Rejected plan must not invoke test_runner stub"

    # Check termination in checkpoint
    final_state = graph.get_state(config)
    assert final_state.next == ()
    assert final_state.values["status"] == "rejected"


# ΓöÇΓöÇ Test 5: Out-of-scope issues follow safe stopping path ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇ

@pytest.mark.parametrize(
    "out_of_scope_title",
    [
        "Question: How do I configure CORS for this app?",
        "Discussion: RFC on architectural direction",
        "[out-of-scope] Migrate documentation to VitePress",
        "How to deploy this on Kubernetes?",
        "Won't fix: Deprecate legacy auth",
    ],
)
def test_out_of_scope_issues_safe_stopping_path(
    memory_checkpointer: MemorySaver, out_of_scope_title: str
):
    """Non-actionable or out-of-scope issues must halt at safe_stop without reaching planner."""
    graph = create_graph(checkpointer=memory_checkpointer)
    initial_state = create_initial_state(
        issue_title=out_of_scope_title,
        repo="org/app",
    )
    config = {"configurable": {"thread_id": initial_state["thread_id"]}}

    final_output = graph.invoke(initial_state, config=config)

    assert final_output["status"] == "out_of_scope"
    assert final_output["current_agent"] == "safe_stop"
    assert final_output["triage"]["is_supported"] is False
    assert final_output["triage"]["classification"] == TriageClassification.OUT_OF_SCOPE.value

    # Planner and approval must never have been reached
    assert final_output.get("plan") is None
    assert final_output.get("human_approval") is None


# ΓöÇΓöÇ Test 6: Missing or invalid issue input ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇ

def test_missing_or_invalid_issue_input():
    """Initial state creation must reject invalid inputs with clear errors."""
    with pytest.raises(ValueError, match="Repository identifier"):
        create_initial_state(issue_title="Some issue", repo="")

    with pytest.raises(ValueError, match="Repository identifier"):
        create_initial_state(issue_title="Some issue", repo="   ")

    with pytest.raises(ValueError, match="Issue title cannot be empty"):
        create_initial_state(issue_title="", repo="org/repo")

    with pytest.raises(ValueError, match="Issue title cannot be empty"):
        create_initial_state(issue_title="   ", repo="org/repo")


def test_triage_node_handles_empty_title_safely():
    """Triage node must safely handle edge cases if an empty title bypasses factory."""
    from app.agents.graph import triage_node

    raw_state: AgentState = {
        "run_id": "test_run",
        "thread_id": "test_thread",
        "repo": "org/repo",
        "issue_title": "",
        "issue_body": "",
        "retry_count": 0,
        "max_retries": 3,
        "status": "pending",
        "events": [],
    }

    result = triage_node(raw_state)
    assert result["status"] == "unsupported"
    assert result["triage"]["is_supported"] is False


# ΓöÇΓöÇ Test 7: Checkpoint state across resume ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇ

def test_checkpoint_state_across_resume(memory_checkpointer: MemorySaver):
    """
    Events log and completed stage data must accumulate and persist cleanly
    across separate graph invocations on the same checkpointer.
    """
    thread_id = "test_thread_persistence"
    initial_state = create_initial_state(
        issue_title="Fix race condition in session store",
        repo="acme/auth",
        thread_id=thread_id,
    )
    config = {"configurable": {"thread_id": thread_id}}

    # Instance 1: Run to interrupt
    graph1 = create_graph(checkpointer=memory_checkpointer)
    graph1.invoke(initial_state, config=config)

    paused_state = graph1.get_state(config)
    events_at_pause = paused_state.values["events"]
    assert len(events_at_pause) >= 3  # workflow_started, triage_completed, retrieval_completed, plan_generated

    # Instance 2: Resume from the same checkpointer with a new graph instance
    graph2 = create_graph(checkpointer=memory_checkpointer)
    resumed_result = graph2.invoke(
        Command(resume={"decision": "approved", "feedback": "LGTM"}),
        config=config,
    )

    events_after_resume = resumed_result["events"]
    assert len(events_after_resume) > len(events_at_pause)

    # Check chronological ordering of events
    agent_names = [e["agent_name"] for e in events_after_resume]
    assert "orchestrator" in agent_names
    assert "triage" in agent_names
    assert "retrieval" in agent_names
    assert "planner" in agent_names
    assert "human_approval" in agent_names
    assert "coder" in agent_names
    assert "test_runner" in agent_names
    assert "reviewer" in agent_names


# ΓöÇΓöÇ Test 8: Retry limits and initial state defaults ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇ

def test_retry_limits_and_initial_defaults():
    """Verify that initial state sets correct defaults for retry tracking."""
    state = create_initial_state(
        issue_title="Sample bug",
        repo="org/repo",
        max_retries=5,
    )

    assert state["retry_count"] == 0
    assert state["max_retries"] == 5
    assert state["code_changes"] is None
    assert state["test_results"] is None
    assert state["review_findings"] is None
    assert state["pull_request_url"] is None
    assert state["status"] == "pending"


# ΓöÇΓöÇ Test 9: Model router integration ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇ

def test_model_router_tier_integration():
    """Verify that model_router appropriately routes agent tiers."""
    assert route("triage") == ModelTier.CLASSIFIER
    assert route("retrieval") == ModelTier.EMBEDDING
    assert route("planner") == ModelTier.LLM
    assert route("coder") == ModelTier.LLM
    assert route("debugger_first_pass") == ModelTier.CLASSIFIER
    assert route("reviewer_first_pass") == ModelTier.STATIC_ANALYSIS
    assert route("pr") == ModelTier.LLM


# ── Test 10: Plan hash tamper protection prevents coder execution ─────────────

def test_tampered_plan_hash_rejects_and_skips_coder(memory_checkpointer: MemorySaver):
    """
    Submitting an altered plan_hash on resume must be caught by tamper protection,
    forcing rejection and immediately terminating without invoking the coder stub.
    """
    graph = create_graph(checkpointer=memory_checkpointer)
    initial_state = create_initial_state(
        issue_title="Fix rate limiter timeout on burst requests",
        repo="org/gateway",
    )
    thread_id = initial_state["thread_id"]
    config = {"configurable": {"thread_id": thread_id}}

    # Execute until human_approval interrupt
    graph.invoke(initial_state, config=config)
    paused_state = graph.get_state(config)
    assert paused_state.next == ("human_approval",)

    # Resume with approval but spoofed plan_hash
    tampered_response = {
        "decision": "approved",
        "plan_hash": "tampered_spoofed_hash_00000000",
        "feedback": "Approved spoofed plan.",
    }
    resume_cmd = Command(resume=tampered_response)
    final_output = graph.invoke(resume_cmd, config=config)

    # Must be forced to rejection
    assert final_output["status"] == "rejected"
    assert final_output["current_agent"] == "rejection_terminal"
    assert final_output["human_approval"]["decision"] == "rejected"
    assert "tampering detected" in final_output["human_approval"]["feedback"].lower()

    # Coder and downstream stubs must never be reached
    coder_events = [e for e in final_output["events"] if e.get("agent_name") == "coder"]
    assert len(coder_events) == 0, "Tampered plan must never reach coder agent"
    test_runner_events = [e for e in final_output["events"] if e.get("agent_name") == "test_runner"]
    assert len(test_runner_events) == 0, "Tampered plan must never reach test runner agent"
    debugger_events = [e for e in final_output["events"] if e.get("agent_name") == "debugger"]
    assert len(debugger_events) == 0, "Tampered plan must never reach debugger agent"
    reviewer_events = [e for e in final_output["events"] if e.get("agent_name") == "reviewer"]
    assert len(reviewer_events) == 0, "Tampered plan must never reach reviewer agent"

    # Verify execution reached END cleanly
    final_state = graph.get_state(config)
    assert final_state.next == (), "Graph should terminate at END after rejection"
    assert final_state.values["status"] == "rejected"


# ── Test 11: Approved path executes coder, test_runner, reviewer and terminates

def test_approved_path_invokes_coder_test_runner_and_reviewer(memory_checkpointer: MemorySaver):
    """
    Verifies that the approved path invokes coder, transitions to test_runner,
    and upon passing tests advances to reviewer before cleanly terminating at END.
    """
    graph = create_graph(checkpointer=memory_checkpointer)
    initial_state = create_initial_state(
        issue_title="Implement healthcheck endpoint",
        repo="org/microservice",
    )
    thread_id = initial_state["thread_id"]
    config = {"configurable": {"thread_id": thread_id}}

    graph.invoke(initial_state, config=config)
    state_at_pause = graph.get_state(config)
    assert state_at_pause.next == ("human_approval",)

    # Resume with legitimate approval
    resume_cmd = Command(resume={"decision": "approved", "feedback": "Looks great, please code and test it."})
    final_output = graph.invoke(resume_cmd, config=config)

    # Verify terminal status and agent
    assert final_output["status"] == "reviewing"
    assert final_output["current_agent"] == "reviewer"

    # Verify coder event
    coder_events = [e for e in final_output["events"] if e.get("agent_name") == "coder"]
    assert len(coder_events) == 2
    assert coder_events[0]["event_type"] == "code_generation_started"
    assert coder_events[0]["status"] == "in_progress"
    assert "Coder Agent initialized" in coder_events[0]["message"]
    assert coder_events[0]["metadata"]["tier"] == ModelTier.LLM.value

    # Verify test_runner event
    test_runner_events = [e for e in final_output["events"] if e.get("agent_name") == "test_runner"]
    assert len(test_runner_events) == 1
    assert test_runner_events[0]["event_type"] in ("tests_started", "tests_completed")
    assert test_runner_events[0]["status"] in ("in_progress", "success")
    assert "Test Runner executing verification test suite" in test_runner_events[0]["message"]

    # Verify reviewer event
    reviewer_events = [e for e in final_output["events"] if e.get("agent_name") == "reviewer"]
    assert len(reviewer_events) == 1
    assert reviewer_events[0]["event_type"] in ("review_started", "review_completed")
    assert reviewer_events[0]["status"] in ("in_progress", "success")
    assert reviewer_events[0]["metadata"]["tier"] == ModelTier.STATIC_ANALYSIS.value

    # Verify event ordering: coder -> test_runner -> reviewer
    event_agents = [e.get("agent_name") for e in final_output["events"]]
    coder_idx = event_agents.index("coder")
    test_runner_idx = event_agents.index("test_runner")
    reviewer_idx = event_agents.index("reviewer")
    assert coder_idx < test_runner_idx < reviewer_idx, "Events must follow coder -> test_runner -> reviewer"

    # Graph must terminate at END immediately after reviewer
    final_state = graph.get_state(config)
    assert final_state.next == (), "Workflow must terminate at END after reviewer stub"


# ── Test 12: Graph structure registers all workflow nodes ─────────────────────

def test_graph_structure_registers_all_workflow_nodes():
    """Verify create_workflow_graph includes coder, test_runner, debugger, reviewer, retry terminal."""
    builder = create_workflow_graph()
    compiled = builder.compile()
    graph_spec = compiled.get_graph()

    assert "coder" in graph_spec.nodes
    assert "test_runner" in graph_spec.nodes
    assert "debugger" in graph_spec.nodes
    assert "reviewer" in graph_spec.nodes
    assert "pr_agent" in graph_spec.nodes
    assert "retry_limit_terminal" in graph_spec.nodes
    assert "human_approval" in graph_spec.nodes
    assert "rejection_terminal" in graph_spec.nodes


# ── Test 13: Bounded debugger retry loop on failing tests ─────────────────────

def test_failing_tests_trigger_debugger_bounded_retry_loop(memory_checkpointer: MemorySaver):
    """
    When tests fail, the workflow must loop: debugger -> coder -> test_runner
    until retry_count reaches max_retries, halting at retry_limit_terminal safely.
    """
    graph = create_graph(checkpointer=memory_checkpointer)
    initial_state = create_initial_state(
        issue_title="Fix memory leak in buffer pool",
        repo="org/memory-pool",
        max_retries=2,
    )
    thread_id = initial_state["thread_id"]
    config = {"configurable": {"thread_id": thread_id}}

    # Run to human approval interrupt
    graph.invoke(initial_state, config=config)
    assert graph.get_state(config).next == ("human_approval",)

    # Inject failing test results before resuming
    graph.update_state(
        config,
        {"test_results": {"passed": False, "failed_tests": 1, "details": "AssertionError"}},
    )

    # Resume with approval
    final_output = graph.invoke(
        Command(resume={"decision": "approved", "feedback": "Go ahead"}),
        config=config,
    )

    # Verify execution halted at retry_limit_terminal
    assert final_output["status"] == "failed"
    assert final_output["current_agent"] == "retry_limit_terminal"
    assert final_output["retry_count"] == 2

    # Debugger should have executed exactly max_retries (2) times
    debugger_events = [e for e in final_output["events"] if e.get("agent_name") == "debugger"]
    assert len(debugger_events) == 2, f"Expected 2 debugger attempts, got {len(debugger_events)}"

    # Reviewer must never have been reached
    reviewer_events = [e for e in final_output["events"] if e.get("agent_name") == "reviewer"]
    assert len(reviewer_events) == 0, "Reviewer must not execute on failed test run"

    # Verify execution reached END cleanly without recursion error
    final_state = graph.get_state(config)
    assert final_state.next == (), "Workflow must terminate cleanly at END"
    assert final_state.values["status"] == "failed"


# ── Test 14: Zero max_retries halts immediately on test failure ────────────────

def test_zero_max_retries_halts_immediately_on_failure(memory_checkpointer: MemorySaver):
    """If max_retries is 0, failing tests immediately halt at retry_limit_terminal."""
    graph = create_graph(checkpointer=memory_checkpointer)
    initial_state = create_initial_state(
        issue_title="Fix broken parser logic",
        repo="org/parser",
        max_retries=0,
    )
    thread_id = initial_state["thread_id"]
    config = {"configurable": {"thread_id": thread_id}}

    graph.invoke(initial_state, config=config)
    graph.update_state(config, {"test_results": {"passed": False}})

    final_output = graph.invoke(
        Command(resume={"decision": "approved", "feedback": "Try once"}),
        config=config,
    )

    assert final_output["status"] == "failed"
    assert final_output["current_agent"] == "retry_limit_terminal"
    assert final_output["retry_count"] == 0

    debugger_events = [e for e in final_output["events"] if e.get("agent_name") == "debugger"]
    assert len(debugger_events) == 0, "Debugger must not run when max_retries is 0"


# ── Test 15: Pydantic TestResults object compatibility ────────────────────────

def test_pydantic_test_results_passing_reaches_reviewer(memory_checkpointer: MemorySaver):
    """Pydantic TestResults model with passed=True routes directly to reviewer."""
    graph = create_graph(checkpointer=memory_checkpointer)
    initial_state = create_initial_state(
        issue_title="Add caching layer to user service",
        repo="org/user-svc",
    )
    thread_id = initial_state["thread_id"]
    config = {"configurable": {"thread_id": thread_id}}

    graph.invoke(initial_state, config=config)
    graph.update_state(
        config,
        {"test_results": TestResults(passed=True, total_tests=10, passed_tests=10)},
    )

    final_output = graph.invoke(
        Command(resume={"decision": "approved", "feedback": "Approved"}),
        config=config,
    )

    assert final_output["status"] == "reviewing"
    assert final_output["current_agent"] == "reviewer"

    debugger_events = [e for e in final_output["events"] if e.get("agent_name") == "debugger"]
    assert len(debugger_events) == 0, "Debugger must not run when tests pass"


# ── Test 16: Explicit review approval routes to PR Agent ──────────────────────

def test_approved_review_findings_advances_to_pr_agent(memory_checkpointer: MemorySaver):
    """
    When review_findings explicitly has approved=True, workflow advances
    from reviewer to pr_agent and terminates cleanly at END.
    """
    graph = create_graph(checkpointer=memory_checkpointer)
    initial_state = create_initial_state(
        issue_title="Implement database health metric",
        repo="org/metrics-service",
    )
    thread_id = initial_state["thread_id"]
    config = {"configurable": {"thread_id": thread_id}}

    graph.invoke(initial_state, config=config)
    assert graph.get_state(config).next == ("human_approval",)

    # Inject explicit review approval before resuming
    graph.update_state(
        config,
        {
            "review_findings": {
                "approved": True,
                "score": 1.0,
                "comments": ["Patch conforms cleanly to agreed plan."],
            }
        },
    )

    final_output = graph.invoke(
        Command(resume={"decision": "approved", "feedback": "Ready for PR"}),
        config=config,
    )

    # Verify terminal status and agent
    assert final_output["status"] == "submitting_pr"
    assert final_output["current_agent"] == "pr"

    # Verify PR Agent event
    pr_events = [e for e in final_output["events"] if e.get("agent_name") == "pr"]
    assert len(pr_events) == 1
    assert pr_events[0]["event_type"] in ("pr_creation_started", "pr_created")
    assert pr_events[0]["status"] in ("in_progress", "success")
    assert pr_events[0]["metadata"]["tier"] == ModelTier.LLM.value

    # Verify event ordering: coder -> test_runner -> reviewer -> pr
    event_agents = [e.get("agent_name") for e in final_output["events"]]
    coder_idx = event_agents.index("coder")
    test_runner_idx = event_agents.index("test_runner")
    reviewer_idx = event_agents.index("reviewer")
    pr_idx = event_agents.index("pr")
    assert coder_idx < test_runner_idx < reviewer_idx < pr_idx, (
        "Events must follow coder -> test_runner -> reviewer -> pr"
    )

    # Graph must terminate at END immediately after PR agent
    final_state = graph.get_state(config)
    assert final_state.next == (), "Workflow must terminate at END after pr_agent stub"


# ── Test 17: Missing or rejected review never reaches PR Agent ────────────────

def test_missing_or_rejected_review_never_invokes_pr_agent(memory_checkpointer: MemorySaver):
    """
    Safety invariant: PR Agent is never reached when review_findings is absent
    or when approved=False. Never treat missing review data as approval.
    """
    # Case A: Missing review data (review_findings is None)
    graph_a = create_graph(checkpointer=memory_checkpointer)
    state_a = create_initial_state(
        issue_title="Add pagination to user list endpoint",
        repo="org/users",
        thread_id="thread_missing_review",
    )
    config_a = {"configurable": {"thread_id": state_a["thread_id"]}}

    graph_a.invoke(state_a, config=config_a)
    out_a = graph_a.invoke(
        Command(resume={"decision": "approved", "feedback": "Approved"}),
        config=config_a,
    )

    # Should halt after reviewer without calling PR agent
    assert out_a["status"] == "reviewing"
    assert out_a["current_agent"] == "reviewer"
    pr_events_a = [e for e in out_a["events"] if e.get("agent_name") == "pr"]
    assert len(pr_events_a) == 0, "PR Agent must NOT be invoked when review data is absent"

    # Case B: Review explicitly rejected (approved=False)
    graph_b = create_graph(checkpointer=memory_checkpointer)
    state_b = create_initial_state(
        issue_title="Fix TLS cipher negotiation vulnerability",
        repo="org/infra",
        thread_id="thread_rejected_review",
    )
    config_b = {"configurable": {"thread_id": state_b["thread_id"]}}

    graph_b.invoke(state_b, config=config_b)
    graph_b.update_state(
        config_b,
        {
            "review_findings": {
                "approved": False,
                "score": 0.2,
                "comments": ["Diff introduces unexpected modifications to auth.py"],
            }
        },
    )

    out_b = graph_b.invoke(
        Command(resume={"decision": "approved", "feedback": "Approved"}),
        config=config_b,
    )

    # Must halt without calling PR agent
    assert out_b["current_agent"] == "reviewer"
    pr_events_b = [e for e in out_b["events"] if e.get("agent_name") == "pr"]
    assert len(pr_events_b) == 0, "PR Agent must NOT be invoked when review is rejected"


# ── Test 18: Pydantic ReviewFindings model compatibility ──────────────────────

def test_pydantic_review_findings_approved_reaches_pr_agent(memory_checkpointer: MemorySaver):
    """Pydantic ReviewFindings(approved=True) triggers routing to pr_agent."""
    graph = create_graph(checkpointer=memory_checkpointer)
    initial_state = create_initial_state(
        issue_title="Fix deadlock in connection pool",
        repo="org/db-pool",
    )
    thread_id = initial_state["thread_id"]
    config = {"configurable": {"thread_id": thread_id}}

    graph.invoke(initial_state, config=config)
    graph.update_state(
        config,
        {"review_findings": ReviewFindings(approved=True, score=0.98, comments=["Clean patch"])},
    )

    final_output = graph.invoke(
        Command(resume={"decision": "approved", "feedback": "Approved"}),
        config=config,
    )

    assert final_output["status"] == "submitting_pr"
    assert final_output["current_agent"] == "pr"

    pr_events = [e for e in final_output["events"] if e.get("agent_name") == "pr"]
    assert len(pr_events) == 1


# ── Test 19 & 20: Async planning phase & RunnableConfig regression tests ─────

def test_async_workflow_planning_phase_with_github_issue_url(memory_checkpointer: MemorySaver):
    """
    Regression test for: Called get_config outside of a runnable context.
    Executes the workflow graph via graph.ainvoke() with a GitHub issue URL,
    verifying it cleanly executes Triage -> Retrieval -> Planner and pauses at
    human_approval without failing on missing RunnableConfig context.
    """
    async def _test():
        graph = create_graph(checkpointer=memory_checkpointer)
        initial_state = create_initial_state(
            repo="octocat/Hello-World",
            issue_title="Fix defect reported in #42 for octocat/Hello-World",
            issue_body="Automated bug report imported from https://github.com/octocat/Hello-World/issues/42.",
            issue_url="https://github.com/octocat/Hello-World/issues/42",
            issue_number=42,
        )
        thread_id = initial_state["thread_id"]
        config = {"configurable": {"thread_id": thread_id}}

        # Phase 1: ainvoke up to human_approval interrupt
        res = await graph.ainvoke(initial_state, config=config)
        assert "__interrupt__" in res

        saved = graph.get_state(config)
        assert saved.next == ("human_approval",)
        assert saved.values["status"] == "awaiting_approval"
        assert saved.values["plan"] is not None
        plan_hash = saved.values["plan_hash"]
        assert plan_hash is not None

        # Phase 2: ainvoke resume with approval
        approval_payload = {
            "decision": "approved",
            "plan_hash": plan_hash,
            "plan_version": "v1",
        }
        resume_res = await graph.ainvoke(Command(resume=approval_payload), config=config)
        assert resume_res is not None
        saved_after = graph.get_state(config)
        assert saved_after.values["status"] in ("approved", "completed", "reviewing", "submitting_pr")

    asyncio.run(_test())


def test_async_workflow_planning_phase_rejection(memory_checkpointer: MemorySaver):
    """Verifies that async execution with rejection cleanly terminates."""
    async def _test():
        graph = create_graph(checkpointer=memory_checkpointer)
        initial_state = create_initial_state(
            repo="octocat/Hello-World",
            issue_title="Feature request #99",
            issue_body="Add new feature",
            issue_url="https://github.com/octocat/Hello-World/issues/99",
            issue_number=99,
        )
        thread_id = initial_state["thread_id"]
        config = {"configurable": {"thread_id": thread_id}}

        res = await graph.ainvoke(initial_state, config=config)
        assert "__interrupt__" in res

        saved = graph.get_state(config)
        assert saved.next == ("human_approval",)

        # Reject
        resume_res = await graph.ainvoke(Command(resume={"decision": "rejected"}), config=config)
        assert resume_res is not None
        saved_after = graph.get_state(config)
        assert saved_after.values["status"] == "rejected"
        assert saved_after.next == ()

    asyncio.run(_test())




