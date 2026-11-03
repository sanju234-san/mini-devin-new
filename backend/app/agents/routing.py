"""Pure routing logic for the Mini-Devin supervisor graph."""

from dataclasses import dataclass

from app.agents.schemas import (
    ApprovalDecision,
    DiffGateResult,
    ReviewOutcome,
    RunState,
    StopReason,
    TestResult,
    TriageCategory,
)

LLM_NODES = {"retrieval", "planner", "coder", "debugger", "reviewer", "pr_agent"}


@dataclass(frozen=True)
class Limits:
    """Counter limits for bounded retry loops.

    Placeholders, not decisions — to be agreed with Tamanna.
    """
    plan_schema_retries: int = 2
    diff_schema_retries: int = 2
    plan_revisions: int = 3
    debug_attempts: int = 3
    review_revisions: int = 2
    run_budget: int = 40
    triage_min_confidence: float = 0.6  # placeholder, not a decision


@dataclass(frozen=True)
class Decision:
    """Routing decision: next node name and optional stop reason."""
    next_node: str
    stop_reason: StopReason | None = None


def decide(after_node: str, state: RunState, limits: Limits) -> Decision:
    """Decide the next node based on the current state and routing rules.

    Counter semantics: plan_schema_retries, diff_schema_retries,
    plan_revisions (rejects only) and review_revisions are incremented
    by the node when it triggers the loop, so retry is allowed while
    counter <= limit.  debug_attempts is incremented by the debugger
    when it runs, so debugger is allowed while debug_attempts < limit.
    """
    # 0. node_error overrides everything
    node_error = state.get("node_error")
    if node_error is not None:
        return Decision("escalate", node_error)

    result: Decision

    if after_node == "intake":
        result = Decision("input_guardrail")

    elif after_node == "input_guardrail":
        gr = state.get("guardrail_result")
        if gr is None:
            result = Decision("escalate", StopReason.ERROR)
        elif gr.flagged:
            result = Decision("escalate", StopReason.INJECTION_SUSPECTED)
        else:
            result = Decision("triage")

    elif after_node == "triage":
        tr = state.get("triage_result")
        if tr is None:
            result = Decision("escalate", StopReason.ERROR)
        elif tr.confidence < limits.triage_min_confidence:
            result = Decision("escalate", StopReason.TRIAGE_UNCERTAIN)
        elif tr.category == TriageCategory.OUT_OF_SCOPE:
            result = Decision("finish")
        else:
            result = Decision("retrieval")

    elif after_node == "retrieval":
        result = Decision("planner")

    elif after_node == "planner":
        result = Decision("plan_validation")

    elif after_node == "plan_validation":
        valid = state.get("plan_validation_ok")
        if valid is None:
            result = Decision("escalate", StopReason.ERROR)
        elif valid:
            result = Decision("human_approval")
        else:
            retries = state.get("plan_schema_retries", 0)
            if retries <= limits.plan_schema_retries:
                result = Decision("planner")
            else:
                result = Decision("escalate", StopReason.PLAN_SCHEMA_RETRIES_EXHAUSTED)

    elif after_node == "human_approval":
        last = state.get("last_approval")
        if last is None:
            result = Decision("escalate", StopReason.ERROR)
        elif last.decision == ApprovalDecision.APPROVE:
            result = Decision("coder")
        elif last.decision == ApprovalDecision.EDIT:
            result = Decision("plan_validation")
        elif last.decision == ApprovalDecision.REJECT:
            revisions = state.get("plan_revisions", 0)
            if revisions <= limits.plan_revisions:
                result = Decision("planner")
            else:
                result = Decision("escalate", StopReason.PLAN_REVISIONS_EXHAUSTED)
        else:
            result = Decision("escalate", StopReason.ERROR)

    elif after_node in ("coder", "debugger"):
        result = Decision("diff_gate")

    elif after_node == "diff_gate":
        dgr = state.get("diff_gate_result")
        if dgr == DiffGateResult.CLEAN:
            result = Decision("test_runner")
        elif dgr == DiffGateResult.DENYLIST_HIT:
            result = Decision("escalate", StopReason.DIFF_BLOCKED)
        elif dgr == DiffGateResult.SCHEMA_INVALID:
            retries = state.get("diff_schema_retries", 0)
            if retries <= limits.diff_schema_retries:
                producer = state.get("diff_producer")
                if producer in ("coder", "debugger"):
                    result = Decision(producer)
                else:
                    result = Decision("escalate", StopReason.ERROR)
            else:
                result = Decision("escalate", StopReason.DIFF_SCHEMA_RETRIES_EXHAUSTED)
        else:
            result = Decision("escalate", StopReason.ERROR)

    elif after_node == "test_runner":
        te = state.get("test_evidence")
        if te is None:
            result = Decision("escalate", StopReason.ERROR)
        elif te.result == TestResult.PASS:
            result = Decision("reviewer")
        elif te.result == TestResult.ERROR:
            result = Decision("escalate", StopReason.SANDBOX_ERROR)
        elif te.result == TestResult.FAIL:
            attempts = state.get("debug_attempts", 0)
            if attempts < limits.debug_attempts:
                result = Decision("debugger")
            else:
                result = Decision("escalate", StopReason.DEBUGGER_LIMIT)
        else:
            result = Decision("escalate", StopReason.ERROR)

    elif after_node == "reviewer":
        rr = state.get("review_result")
        if rr is None:
            result = Decision("escalate", StopReason.ERROR)
        elif rr.outcome == ReviewOutcome.APPROVE:
            result = Decision("pr_agent")
        elif rr.outcome == ReviewOutcome.REVISE:
            revisions = state.get("review_revisions", 0)
            if revisions <= limits.review_revisions:
                result = Decision("coder")
            else:
                result = Decision("escalate", StopReason.REVIEWER_LIMIT)
        elif rr.outcome == ReviewOutcome.BLOCK:
            result = Decision("escalate", StopReason.REVIEWER_BLOCK)
        else:
            result = Decision("escalate", StopReason.ERROR)

    elif after_node == "pr_agent":
        result = Decision("finish")

    else:
        result = Decision("escalate", StopReason.ERROR)

    # 11. Budget rule: if next is an LLM node and budget exhausted, escalate
    if result.next_node in LLM_NODES:
        llm_calls = state.get("run_llm_calls", 0)
        if llm_calls >= limits.run_budget:
            return Decision("escalate", StopReason.RUN_BUDGET)

    return result


def make_router(after_node: str, limits: Limits):
    """Return a routing function for use as a conditional edge."""
    def router(state: RunState) -> str:
        """Route to the next node."""
        return decide(after_node, state, limits).next_node
    return router
