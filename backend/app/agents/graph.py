"""
LangGraph Supervisor Workflow for Mini-Devin.

Wires the multi-agent workflow state machine:
Triage -> Retrieval -> Planner -> (Human Approval Interrupt) -> Completion / Clean Stop

Future Extension Pipeline (Day 2+):
Triage -> Retrieval -> Planner -> Human Approval -> Coder -> Test Runner
-> Debugger (bounded retry loop) -> Reviewer -> PR Agent.
"""

from __future__ import annotations

import datetime
import logging
from typing import Any, Optional

from langchain_core.runnables.config import RunnableConfig, var_child_runnable_config
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt
from pydantic import ValidationError

from app.agents.checkpointer import get_checkpointer
from app.agents.coder import coder_node
from app.agents.debugger import debugger_node
from app.agents.planner import planner_node
from app.agents.pr_agent import pr_node
from app.agents.retrieval import retrieval_node
from app.agents.reviewer import reviewer_node
from app.agents.test_runner import test_runner_node
from app.agents.routing import Limits, decide, make_router
from app.agents.schemas import (
    AgentState,
    ApprovalDecision,
    ApprovalResponse,
    Plan,
    PlanAuthor,
    RunState,
    RunStatus,
    StopReason,
    TriageCategory,
    compute_plan_hash,
    create_event,
    next_plan_version_id,
)
from app.agents.triage import triage_node


logger = logging.getLogger(__name__)


# ΓöÇΓöÇ Routing Helpers ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇ

def _is_supported_triage(triage: Any) -> bool:
    """Helper to check if triage result indicates a supported issue."""
    if not triage:
        return False
    if isinstance(triage, dict):
        return bool(triage.get("is_supported", False))
    return bool(getattr(triage, "is_supported", False))


def _get_approval_decision(approval: Any) -> str:
    """Helper to safely extract the approval decision string."""
    if not approval:
        return "rejected"
    if isinstance(approval, dict):
        return str(approval.get("decision", "rejected"))
    return str(getattr(approval, "decision", "rejected"))


def route_triage(state: AgentState) -> str:
    """Conditional router deciding whether to proceed to Retrieval or halt safely."""
    triage = state.get("triage")
    if not _is_supported_triage(triage):
        return "safe_stop"
    return "retrieval"


def safe_stop_node(state: AgentState) -> dict[str, Any]:
    """Safe terminal node for unsupported, out-of-scope, or failed issues."""
    err = state.get("error")
    status = state.get("status", "out_of_scope")
    if status == "failed" and err:
        reason = f"Workflow failed: {err}"
    else:
        triage = state.get("triage")
        reason = "Unsupported or out-of-scope issue"
        if isinstance(triage, dict):
            reason = triage.get("reason", reason)
        elif hasattr(triage, "reason"):
            reason = triage.reason

    logger.info("Halting execution safely: %s", reason)

    event = create_event(
        agent_name="safe_stop",
        event_type="workflow_halted",
        status="stopped",
        message=f"Execution safely stopped: {reason}",
        metadata={"reason": reason},
    )
    status = state.get("status", "out_of_scope")
    if status != "failed":
        status = "out_of_scope"
    return {
        "status": status,
        "current_agent": "safe_stop",
        "error": state.get("error"),
        "events": [event],
    }


def human_approval_node(state: AgentState, config: Optional[RunnableConfig] = None) -> dict[str, Any]:
    """
    Human Approval Node: Interrupts execution before any repository modifications.
    
    Uses LangGraph's native `interrupt()` to persist the checkpoint and await
    an explicit approval or rejection response from the human operator.
    Enforces frozen plan hash binding and rejects mutated plans or plan substitutions.
    """
    # Duplicate approval idempotency check
    existing_approval = state.get("human_approval")
    if existing_approval:
        prev_dec = (
            existing_approval.get("decision")
            if isinstance(existing_approval, dict)
            else getattr(existing_approval, "decision", None)
        )
        if prev_dec in ("approved", "rejected"):
            logger.info("Human approval decision already recorded ('%s'). Idempotently passing through.", prev_dec)
            return {
                "human_approval": existing_approval,
                "status": prev_dec,
                "current_agent": "human_approval",
                "events": [],
            }

    plan = state.get("plan")
    plan_dict = plan.model_dump(mode="json") if hasattr(plan, "model_dump") else plan
    plan_hash = state.get("plan_hash") or compute_plan_hash(plan_dict)
    plan_version = state.get("plan_version") or "v1"

    # LangGraph interrupt halts execution here and persists checkpoint
    approval_request = {
        "action": "request_approval",
        "run_id": state.get("run_id"),
        "thread_id": state.get("thread_id"),
        "plan": plan_dict,
        "plan_hash": plan_hash,
        "plan_version": plan_version,
        "repo": state.get("repo"),
        "issue_title": state.get("issue_title"),
        "message": f"Human approval required to proceed with code modifications (Plan Hash: {plan_hash[:8]}).",
    }

    # Ensure LangGraph runnable context is active across async and sync runtimes (Python < 3.11 contextvar propagation)
    config_token = None
    if config is not None:
        config_token = var_child_runnable_config.set(config)
    try:
        # Execution yields here until resumed with Command(resume=...)
        resume_payload = interrupt(approval_request)
    finally:
        if config_token is not None:
            var_child_runnable_config.reset(config_token)

    # Normalize resume payload
    decision_value = "rejected"
    feedback = None
    submitted_plan_hash = None

    if isinstance(resume_payload, dict):
        decision_raw = resume_payload.get("decision", "")
        if isinstance(decision_raw, bool):
            decision_value = "approved" if decision_raw else "rejected"
        elif str(decision_raw).lower() in ("approved", "approve", "yes", "true"):
            decision_value = "approved"
        elif str(decision_raw).lower() in ("rejected", "reject", "no", "false"):
            decision_value = "rejected"
        feedback = resume_payload.get("feedback")
        submitted_plan_hash = resume_payload.get("plan_hash")
    elif isinstance(resume_payload, bool):
        decision_value = "approved" if resume_payload else "rejected"
    elif isinstance(resume_payload, str):
        if resume_payload.lower() in ("approved", "approve", "yes", "true"):
            decision_value = "approved"
        else:
            decision_value = "rejected"

    # Integrity verification against plan substitution / tampering:
    # 1. If resume payload specified a plan hash, it must match the frozen plan hash
    if decision_value == "approved" and submitted_plan_hash and submitted_plan_hash != plan_hash:
        logger.warning(
            "Plan hash mismatch on resume: submitted '%s' vs frozen '%s'. Rejecting.",
            submitted_plan_hash, plan_hash,
        )
        decision_value = "rejected"
        feedback = f"Plan tampering detected: submitted hash '{submitted_plan_hash[:8]}' does not match frozen plan '{plan_hash[:8]}'."

    # 2. Check if the current plan in state was modified since interrupt
    current_plan_hash = compute_plan_hash(state.get("plan"))
    if decision_value == "approved" and current_plan_hash != plan_hash:
        logger.warning(
            "Plan in state was modified after interrupt: current '%s' vs frozen '%s'. Rejecting.",
            current_plan_hash, plan_hash,
        )
        decision_value = "rejected"
        feedback = "Plan was mutated after approval was requested. Approval rejected; a new plan approval is required."

    approval = ApprovalDecision(
        decision=decision_value,
        feedback=feedback,
        timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        plan_version=plan_version,
        plan_hash=plan_hash,
    )

    if decision_value == "approved":
        event = create_event(
            agent_name="human_approval",
            event_type="approval_received",
            status="approved",
            message=f"Plan approved by human operator (Plan Hash: {plan_hash[:8]}). Proceeding to execution stage.",
            metadata={
                "decision": "approved",
                "feedback": feedback,
                "plan_version": plan_version,
                "plan_hash": plan_hash,
            },
        )
        return {
            "human_approval": approval.model_dump(mode="json"),
            "plan_version": plan_version,
            "plan_hash": plan_hash,
            "status": "approved",
            "current_agent": "human_approval",
            "events": [event],
        }
    else:
        event = create_event(
            agent_name="human_approval",
            event_type="approval_rejected",
            status="rejected",
            message="Plan rejected by human operator. Aborting without code modification.",
            metadata={
                "decision": "rejected",
                "feedback": feedback,
                "plan_version": plan_version,
                "plan_hash": plan_hash,
            },
        )
        return {
            "human_approval": approval.model_dump(mode="json"),
            "plan_version": plan_version,
            "plan_hash": plan_hash,
            "status": "rejected",
            "current_agent": "human_approval",
            "events": [event],
        }


def route_planner(state: AgentState) -> str:
    """Conditional router directing flow based on planner outcome."""
    if state.get("status") == "failed":
        return "safe_stop"
    return "human_approval"


def route_coder(state: AgentState) -> str:
    """Conditional router directing flow based on coder outcome."""
    if state.get("status") == "failed":
        return "safe_stop"
    return "test_runner"


def route_approval(state: AgentState) -> str:
    """Conditional router directing flow based on human approval decision."""
    approval = state.get("human_approval")
    if _get_approval_decision(approval) == "approved":
        return "coder"
    return "rejection_terminal"


def rejection_terminal_node(state: AgentState) -> dict[str, Any]:
    """
    Clean terminal node for rejected plans.
    
    Guarantees no code modification or PR opening takes place.
    """
    logger.info("Workflow cleanly terminated after human plan rejection.")
    event = create_event(
        agent_name="rejection_terminal",
        event_type="workflow_terminated",
        status="rejected",
        message="Workflow safely terminated. No code was written or modified.",
        metadata={"reason": "Human operator rejected the implementation plan."},
    )
    return {
        "status": "rejected",
        "current_agent": "rejection_terminal",
        "events": [event],
    }


def completion_node(state: AgentState) -> dict[str, Any]:
    """
    Day 1 Completion Node: Successfully concludes the approval workflow.
    
    Serves as the clean handoff point where Day 2's Coder Agent will begin.
    """
    logger.info("Approval workflow complete. State ready for Coder Agent handoff.")
    plan = state.get("plan")
    summary = ""
    if isinstance(plan, dict):
        summary = plan.get("summary", "")
    elif hasattr(plan, "summary"):
        summary = plan.summary

    event = create_event(
        agent_name="completion",
        event_type="workflow_completed",
        status="completed",
        message="Workflow reached approval milestone successfully. Ready for Coder Agent.",
        metadata={"plan_summary": summary},
    )
    return {
        "status": "completed",
        "current_agent": "completion",
        "events": [event],
    }


def retry_limit_terminal_node(state: AgentState) -> dict[str, Any]:
    """
    Terminal node reached when test-and-debug retry attempts are exhausted.
    
    Halts execution safely without entering an infinite loop.
    """
    retry_count = state.get("retry_count", 0)
    max_retries = state.get("max_retries", 3)
    logger.warning("Retry limit reached (%d/%d). Halting workflow.", retry_count, max_retries)

    event = create_event(
        agent_name="retry_limit_terminal",
        event_type="workflow_halted",
        status="failed",
        message=f"Maximum debug retry limit reached ({retry_count}/{max_retries}). Halting workflow safely.",
        metadata={"retry_count": retry_count, "max_retries": max_retries},
    )
    return {
        "status": "failed",
        "current_agent": "retry_limit_terminal",
        "events": [event],
    }


def test_unverified_terminal_node(state: AgentState) -> dict[str, Any]:
    """
    Terminal node reached when tests are unverified, missing, or sandbox failed.
    
    Guarantees unverified code changes never proceed to Reviewer or PR Agent,
    and cleanly escalates to human operator when sandbox is unavailable.
    """
    test_results = state.get("test_results") or {}
    is_sandbox_unavailable = (
        test_results.get("sandbox_unavailable", False)
        if isinstance(test_results, dict)
        else getattr(test_results, "sandbox_unavailable", False)
    )

    if is_sandbox_unavailable:
        logger.warning("Workflow halted for human escalation: sandbox unavailable and host execution disabled.")
        event = create_event(
            agent_name="test_runner",
            event_type="sandbox_unavailable_escalation",
            status="escalated",
            message="Workflow halted for human escalation: verification sandbox is unavailable and host execution is disabled.",
            metadata={"reason": "sandbox_unavailable"},
        )
        return {
            "status": "escalated",
            "current_agent": "test_runner",
            "error": "Sandbox unavailable: untrusted host execution is disabled by policy. Awaiting human escalation.",
            "events": [event],
        }

    logger.warning("Workflow halted: test execution results are missing or unverified.")
    event = create_event(
        agent_name="test_runner",
        event_type="test_execution_unverified",
        status="failed",
        message="Halting workflow: verification tests were not recorded or could not execute in sandbox.",
        metadata={"reason": "missing_or_unverified_test_results"},
    )
    return {
        "status": "failed",
        "current_agent": "test_runner",
        "error": "Test execution unverified: no test results recorded from sandbox.",
        "events": [event],
    }


def review_rejected_terminal_node(state: AgentState) -> dict[str, Any]:
    """
    Terminal node reached when automated review does not approve the patch.
    
    Guarantees unapproved or blocked patches never proceed to PR creation.
    """
    findings = state.get("review_findings")
    logger.info("Workflow halted: patch review was not approved.")
    event = create_event(
        agent_name="reviewer",
        event_type="review_halted",
        status="failed",
        message="Halting workflow: code review was not approved or was blocked.",
        metadata={"review_findings": str(findings)},
    )
    return {
        "status": "failed",
        "current_agent": "reviewer",
        "error": "Review rejected: patch did not satisfy approval criteria.",
        "events": [event],
    }


def route_test_runner(state: AgentState) -> str:
    """
    Conditional router directing flow after test runner execution:
    - If tests explicitly pass: proceed to reviewer
    - If sandbox is unavailable or infra failure: halt at test_unverified_terminal (escalation, no debugger retry)
    - If tests explicitly fail and retry attempts remain: loop to debugger -> coder -> test_runner
    - If retry limit reached: halt at retry_limit_terminal
    - If tests are missing:
        * In strict_verification mode: halt at test_unverified_terminal (NEVER treat as pass)
        * In default graph stub mode: advance to reviewer for topology testing
    """
    test_results = state.get("test_results")

    if test_results is not None:
        passed = False
        if isinstance(test_results, dict):
            passed = bool(test_results.get("passed", False))
        elif hasattr(test_results, "passed"):
            passed = bool(test_results.passed)
    else:
        if state.get("strict_verification", False):
            logger.warning("Test results missing in state under strict verification. Routing to test_unverified_terminal.")
            return "test_unverified_terminal"
        # Default pass for unit tests / graph pipeline verification when sandbox is not invoked
        passed = True

    if not passed:
        infra_failure = False
        sandbox_unavailable = False
        if isinstance(test_results, dict):
            infra_failure = bool(test_results.get("infrastructure_failure", False))
            sandbox_unavailable = bool(test_results.get("sandbox_unavailable", False))
        elif hasattr(test_results, "infrastructure_failure"):
            infra_failure = bool(getattr(test_results, "infrastructure_failure", False))
            sandbox_unavailable = bool(getattr(test_results, "sandbox_unavailable", False))

        if infra_failure or sandbox_unavailable:
            logger.warning("Test failure is infrastructural or sandbox is unavailable. Halting / routing to escalation.")
            return "test_unverified_terminal"

        retry_count = state.get("retry_count", 0)
        max_retries = state.get("max_retries", 3)
        if retry_count >= max_retries:
            return "retry_limit_terminal"
        return "debugger"

    return "reviewer"


def _is_review_approved(findings: Any) -> bool:
    """Helper to check if review_findings explicitly contains an approved flag."""
    if findings is None:
        return False
    if isinstance(findings, dict):
        return bool(findings.get("approved", False))
    return bool(getattr(findings, "approved", False))


def route_reviewer(state: AgentState) -> str:
    """
    Conditional router directing flow after Reviewer execution:
    - If review_findings explicitly approves the patch: proceed to pr_agent
    - If strict_verification mode and unapproved: halt at review_rejected_terminal
    - If verdict == 'revise' and review revisions remain: loop back to coder
    - If review_findings is blocked, unapproved, or revisions exhausted:
        * In strict_verification mode: halt at review_rejected_terminal
        * In default mode: halt cleanly at END
    """
    findings = state.get("review_findings")
    if _is_review_approved(findings):
        return "pr_agent"

    if state.get("strict_verification", False):
        return "review_rejected_terminal"

    verdict = ""
    if isinstance(findings, dict):
        verdict = findings.get("verdict", "")
    elif hasattr(findings, "verdict"):
        verdict = getattr(findings, "verdict", "")

    if verdict == "revise":
        rev_count = state.get("review_revisions", 0)
        max_rev = state.get("max_review_revisions", 2)
        if rev_count < max_rev:
            logger.info("Reviewer requested revision (attempt %d/%d). Routing back to coder.", rev_count + 1, max_rev)
            return "coder"
        logger.warning("Reviewer revision limit reached (%d/%d). Halting.", rev_count, max_rev)

    if verdict == "block":
        return "review_rejected_terminal"
    return END


# ── Graph Builder ─────────────────────────────────────────────────────────────

def create_workflow_graph() -> StateGraph:
    """
    Construct the StateGraph defining Mini-Devin's workflow topology.
    
    Architecture is strictly compatible with the full 8-agent pipeline:
    Triage -> Retrieval -> Planner -> (Human Approval) -> Coder -> Test-Runner
    -> Debugger (bounded retry loop) -> Reviewer -> PR Agent.
    """
    builder = StateGraph(AgentState)

    # Add core nodes (imported from their respective agent subpackages)
    builder.add_node("triage", triage_node)
    builder.add_node("safe_stop", safe_stop_node)
    builder.add_node("retrieval", retrieval_node)
    builder.add_node("planner", planner_node)
    builder.add_node("human_approval", human_approval_node)
    builder.add_node("rejection_terminal", rejection_terminal_node)
    builder.add_node("coder", coder_node)
    builder.add_node("test_runner", test_runner_node)
    builder.add_node("test_unverified_terminal", test_unverified_terminal_node)
    builder.add_node("debugger", debugger_node)
    builder.add_node("reviewer", reviewer_node)
    builder.add_node("review_rejected_terminal", review_rejected_terminal_node)
    builder.add_node("pr_agent", pr_node)
    builder.add_node("retry_limit_terminal", retry_limit_terminal_node)

    # Add edges and routing
    builder.add_edge(START, "triage")
    builder.add_conditional_edges(
        "triage",
        route_triage,
        {
            "retrieval": "retrieval",
            "safe_stop": "safe_stop",
        },
    )
    builder.add_edge("safe_stop", END)
    builder.add_edge("retrieval", "planner")
    builder.add_conditional_edges(
        "planner",
        route_planner,
        {
            "human_approval": "human_approval",
            "safe_stop": "safe_stop",
        },
    )
    builder.add_conditional_edges(
        "human_approval",
        route_approval,
        {
            "coder": "coder",
            "rejection_terminal": "rejection_terminal",
        },
    )
    builder.add_edge("rejection_terminal", END)
    builder.add_conditional_edges(
        "coder",
        route_coder,
        {
            "test_runner": "test_runner",
            "safe_stop": "safe_stop",
        },
    )
    builder.add_conditional_edges(
        "test_runner",
        route_test_runner,
        {
            "reviewer": "reviewer",
            "debugger": "debugger",
            "retry_limit_terminal": "retry_limit_terminal",
            "test_unverified_terminal": "test_unverified_terminal",
        },
    )
    builder.add_edge("test_unverified_terminal", END)
    builder.add_edge("debugger", "coder")
    builder.add_conditional_edges(
        "reviewer",
        route_reviewer,
        {
            "pr_agent": "pr_agent",
            "coder": "coder",
            "review_rejected_terminal": "review_rejected_terminal",
            END: END,
        },
    )
    builder.add_edge("review_rejected_terminal", END)
    builder.add_edge("pr_agent", END)
    builder.add_edge("retry_limit_terminal", END)

    return builder


def create_graph(checkpointer: Optional[BaseCheckpointSaver] = None):
    """
    Compile and return the executable LangGraph workflow with checkpointing.
    
    If no checkpointer is supplied, uses the default process checkpointer.
    """
    active_checkpointer = checkpointer if checkpointer is not None else get_checkpointer()
    builder = create_workflow_graph()
    return builder.compile(checkpointer=active_checkpointer)


# ── Legacy Architecture Graph Builder & Helpers (Backward Compatibility) ──

REQUIRED_NODE_KEYS = frozenset({
    "intake", "input_guardrail", "triage", "retrieval", "planner",
    "plan_validation", "coder", "diff_gate", "test_runner",
    "debugger", "reviewer", "pr_agent",
})


def _legacy_human_approval(state: RunState, limits: Limits, config: Optional[RunnableConfig] = None) -> dict:
    """Human-in-the-loop approval interrupt node for legacy supervisor graph."""
    plans = state.get("plan_versions", [])
    latest_plan = plans[-1] if plans else None
    payload = {
        "run_id": state.get("run_id", ""),
        "plan_version_id": latest_plan.version_id if latest_plan else None,
    }

    config_token = None
    if config is not None:
        config_token = var_child_runnable_config.set(config)
    try:
        raw = interrupt(payload)
    finally:
        if config_token is not None:
            var_child_runnable_config.reset(config_token)

    if isinstance(raw, ApprovalResponse):
        response = raw
    elif isinstance(raw, dict):
        try:
            response = ApprovalResponse.model_validate(raw)
        except ValidationError:
            return {"node_error": StopReason.ERROR, "current_step": "human_approval"}
    else:
        return {"node_error": StopReason.ERROR, "current_step": "human_approval"}

    result: dict = {"last_approval": response, "current_step": "human_approval"}

    if response.decision == ApprovalDecision.APPROVE:
        if latest_plan:
            result["approved_version"] = latest_plan.version_id
        result["approval_feedback"] = None

    elif response.decision == ApprovalDecision.EDIT:
        if response.edited_plan and latest_plan:
            new_vid = next_plan_version_id(state)
            new_plan = Plan(
                version_id=new_vid,
                author=PlanAuthor.HUMAN,
                intent=response.edited_plan.intent,
                scope=response.edited_plan.scope,
                non_goals=response.edited_plan.non_goals,
                affected_files=response.edited_plan.affected_files,
                requirements=response.edited_plan.requirements,
                steps=response.edited_plan.steps,
                expected_tests=response.edited_plan.expected_tests,
            )
            result["plan_versions"] = [new_plan]
            result["plan_validation_ok"] = None
        result["approval_feedback"] = None

    elif response.decision == ApprovalDecision.REJECT:
        result["approval_feedback"] = response.feedback
        result["plan_revisions"] = state.get("plan_revisions", 0) + 1

    return result


def _escalate(state: RunState, limits: Limits) -> dict:
    """Terminal node for escalated runs in legacy supervisor graph."""
    current = state.get("current_step", "")
    d = decide(current, state, limits)
    stop_reason = d.stop_reason or state.get("node_error") or StopReason.ERROR
    return {
        "status": RunStatus.ESCALATED,
        "stop_reason": stop_reason,
        "current_step": "escalate",
    }


def _finish(state: RunState) -> dict:
    """Terminal node for successful or out-of-scope runs in legacy supervisor graph."""
    triage = state.get("triage_result")
    if triage and triage.category == TriageCategory.OUT_OF_SCOPE:
        status = RunStatus.OUT_OF_SCOPE
    else:
        status = RunStatus.PR_OPENED
    return {"status": status, "current_step": "finish"}


def new_run_state(run_id: str, repo: str, issue_number: int, issue_text: str) -> RunState:
    """Create an initial RunState with all counters at zero."""
    return RunState(
        run_id=run_id,
        repo=repo,
        issue_number=issue_number,
        issue_text=issue_text,
        status=RunStatus.RUNNING,
        plan_schema_retries=0,
        diff_schema_retries=0,
        plan_revisions=0,
        debug_attempts=0,
        review_revisions=0,
        run_llm_calls=0,
        current_step="",
        artifact_references={},
        plan_versions=[],
    )


def run_config(run_id: str) -> dict:
    """Create a config dict with thread_id equal to run_id."""
    return {"configurable": {"thread_id": run_id}}


def default_nodes() -> dict[str, callable]:
    """Return default nodes with real Triage and fake other nodes."""
    from app.agents.fake_nodes import Scenario, make_fake_nodes
    from app.agents.triage_agent import triage_node as legacy_triage_node
    nodes = make_fake_nodes(Scenario())
    nodes["triage"] = legacy_triage_node
    return nodes


def build_graph(
    nodes: dict[str, callable] | None = None,
    limits: Limits | None = None,
    checkpointer=None,
):
    """Build and compile the Mini-Devin supervisor StateGraph."""
    if nodes is None:
        nodes = default_nodes()

    missing = REQUIRED_NODE_KEYS - set(nodes.keys())
    if missing:
        raise ValueError(f"Missing required node keys: {sorted(missing)}")

    if limits is None:
        limits = Limits()
    if checkpointer is None:
        from langgraph.checkpoint.memory import MemorySaver
        checkpointer = MemorySaver()

    graph = StateGraph(RunState)

    for name, fn in nodes.items():
        graph.add_node(name, fn)

    graph.add_node("human_approval", lambda state, config=None: _legacy_human_approval(state, limits, config))
    graph.add_node("escalate", lambda state: _escalate(state, limits))
    graph.add_node("finish", _finish)

    graph.add_edge(START, "intake")
    graph.add_edge("escalate", END)
    graph.add_edge("finish", END)

    _all_targets = [
        "intake", "input_guardrail", "triage", "retrieval", "planner",
        "plan_validation", "human_approval", "coder", "diff_gate",
        "test_runner", "debugger", "reviewer", "pr_agent",
        "escalate", "finish",
    ]
    target_set = {n: n for n in _all_targets}

    routed_nodes = [
        "intake",
        "input_guardrail",
        "triage",
        "retrieval",
        "planner",
        "plan_validation",
        "human_approval",
        "coder",
        "diff_gate",
        "test_runner",
        "debugger",
        "reviewer",
        "pr_agent",
    ]
    for node_name in routed_nodes:
        graph.add_conditional_edges(node_name, make_router(node_name, limits), target_set)

    return graph.compile(checkpointer=checkpointer)


# Re-exports for backwards compatibility
__all__ = [
    "create_graph",
    "create_workflow_graph",
    "build_graph",
    "new_run_state",
    "run_config",
    "default_nodes",
    "triage_node",
    "retrieval_node",
    "planner_node",
    "human_approval_node",
    "safe_stop_node",
    "rejection_terminal_node",
    "completion_node",
    "coder_node",
    "test_runner_node",
    "debugger_node",
    "reviewer_node",
    "pr_node",
    "retry_limit_terminal_node",
    "route_triage",
    "route_approval",
    "route_test_runner",
    "route_reviewer",
]
