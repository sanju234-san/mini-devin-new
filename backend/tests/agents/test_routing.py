"""Pure tests for the routing module — no LangGraph dependency."""

import pytest

from app.agents.routing import Decision, Limits, LLM_NODES, decide
from app.agents.schemas import (
    ApprovalDecision,
    ApprovalResponse,
    DiffGateResult,
    GuardrailResult,
    ReviewOutcome,
    ReviewResult,
    DimensionAssessment,
    DimensionName,
    DimensionResult,
    RunState,
    RunStatus,
    StopReason,
    TestEvidence,
    TestResult,
    TriageCategory,
    TriageResult,
    Plan,
    PlanAuthor,
    Requirement,
    PlanStep,
)

TestResult.__test__ = False
TestEvidence.__test__ = False

LIMITS = Limits()


def _base_state(**overrides) -> RunState:
    """Minimal RunState with overrides."""
    s: RunState = {
        "run_id": "r1",
        "repo": "o/r",
        "issue_number": 1,
        "issue_text": "Bug",
        "status": RunStatus.RUNNING,
        "plan_schema_retries": 0,
        "diff_schema_retries": 0,
        "plan_revisions": 0,
        "debug_attempts": 0,
        "review_revisions": 0,
        "run_llm_calls": 0,
        "current_step": "",
        "plan_versions": [],
        "artifact_references": {},
    }
    s.update(overrides)
    return s


def _all_pass_dims():
    """All six dimensions passing."""
    return [DimensionAssessment(name=d, result=DimensionResult.PASS, evidence="ok") for d in DimensionName]


# --- node_error rule ---

def test_node_error_overrides():
    """node_error forces escalate regardless of after_node."""
    s = _base_state(node_error=StopReason.ERROR)
    d = decide("triage", s, LIMITS)
    assert d == Decision("escalate", StopReason.ERROR)


# --- intake ---

def test_intake():
    """intake always routes to input_guardrail."""
    assert decide("intake", _base_state(), LIMITS).next_node == "input_guardrail"


# --- input_guardrail ---

def test_guardrail_missing():
    """Missing guardrail_result -> escalate (error)."""
    s = _base_state(guardrail_result=None)
    d = decide("input_guardrail", s, LIMITS)
    assert d == Decision("escalate", StopReason.ERROR)


def test_guardrail_flagged():
    """Flagged -> escalate (injection_suspected)."""
    s = _base_state(guardrail_result=GuardrailResult(flagged=True, reason="bad"))
    d = decide("input_guardrail", s, LIMITS)
    assert d == Decision("escalate", StopReason.INJECTION_SUSPECTED)


def test_guardrail_pass():
    """Not flagged -> triage."""
    s = _base_state(guardrail_result=GuardrailResult(flagged=False))
    assert decide("input_guardrail", s, LIMITS).next_node == "triage"


# --- triage ---

def test_triage_missing():
    """Missing triage_result -> escalate (error)."""
    s = _base_state(triage_result=None)
    d = decide("triage", s, LIMITS)
    assert d == Decision("escalate", StopReason.ERROR)


def test_triage_out_of_scope():
    """out_of_scope -> finish."""
    s = _base_state(triage_result=TriageResult(category=TriageCategory.OUT_OF_SCOPE, confidence=0.9, cleaned_query="q"))
    assert decide("triage", s, LIMITS).next_node == "finish"


def test_triage_in_scope():
    """in scope -> retrieval."""
    s = _base_state(triage_result=TriageResult(category=TriageCategory.BUG_FIX, confidence=0.9, cleaned_query="q"))
    assert decide("triage", s, LIMITS).next_node == "retrieval"


def test_triage_low_confidence_bug_fix():
    """Confidence below threshold escalates with TRIAGE_UNCERTAIN for bug_fix."""
    s = _base_state(triage_result=TriageResult(category=TriageCategory.BUG_FIX, confidence=0.59, cleaned_query="q"))
    d = decide("triage", s, LIMITS)
    assert d == Decision("escalate", StopReason.TRIAGE_UNCERTAIN)


def test_triage_low_confidence_out_of_scope():
    """Confidence below threshold escalates with TRIAGE_UNCERTAIN for out_of_scope."""
    s = _base_state(triage_result=TriageResult(category=TriageCategory.OUT_OF_SCOPE, confidence=0.5, cleaned_query="q"))
    d = decide("triage", s, LIMITS)
    assert d == Decision("escalate", StopReason.TRIAGE_UNCERTAIN)


def test_triage_threshold_confidence_continues_normally():
    """Confidence exactly at threshold continues normally."""
    s_in = _base_state(triage_result=TriageResult(category=TriageCategory.BUG_FIX, confidence=LIMITS.triage_min_confidence, cleaned_query="q"))
    assert decide("triage", s_in, LIMITS).next_node == "retrieval"

    s_out = _base_state(triage_result=TriageResult(category=TriageCategory.OUT_OF_SCOPE, confidence=LIMITS.triage_min_confidence, cleaned_query="q"))
    assert decide("triage", s_out, LIMITS).next_node == "finish"


# --- retrieval, planner ---

def test_retrieval():
    """retrieval -> planner."""
    assert decide("retrieval", _base_state(), LIMITS).next_node == "planner"


def test_planner():
    """planner -> plan_validation."""
    assert decide("planner", _base_state(), LIMITS).next_node == "plan_validation"


# --- plan_validation ---

def test_plan_validation_missing():
    """Missing plan_validation_ok -> escalate (error)."""
    s = _base_state(plan_validation_ok=None)
    d = decide("plan_validation", s, LIMITS)
    assert d == Decision("escalate", StopReason.ERROR)


def test_plan_validation_valid():
    """valid -> human_approval."""
    s = _base_state(plan_validation_ok=True)
    assert decide("plan_validation", s, LIMITS).next_node == "human_approval"


def test_plan_validation_invalid_under_limit():
    """invalid, retries at limit -> planner."""
    s = _base_state(plan_validation_ok=False, plan_schema_retries=LIMITS.plan_schema_retries)
    assert decide("plan_validation", s, LIMITS).next_node == "planner"


def test_plan_validation_invalid_over_limit():
    """invalid, retries above limit -> escalate."""
    s = _base_state(plan_validation_ok=False, plan_schema_retries=LIMITS.plan_schema_retries + 1)
    d = decide("plan_validation", s, LIMITS)
    assert d == Decision("escalate", StopReason.PLAN_SCHEMA_RETRIES_EXHAUSTED)


# --- human_approval ---

def test_approval_missing():
    """Missing last_approval -> escalate (error)."""
    s = _base_state(last_approval=None)
    d = decide("human_approval", s, LIMITS)
    assert d == Decision("escalate", StopReason.ERROR)


def test_approval_approve():
    """approve -> coder."""
    resp = ApprovalResponse(decision=ApprovalDecision.APPROVE)
    s = _base_state(last_approval=resp)
    assert decide("human_approval", s, LIMITS).next_node == "coder"


def test_approval_edit():
    """edit -> plan_validation."""
    edited = Plan(
        version_id="v-edit",
        author=PlanAuthor.HUMAN,
        intent="New intent",
        scope="target module",
        non_goals="none",
        affected_files=["app/target.py"],
        requirements=[Requirement(id="R1", description="Fix", acceptance_criterion="Tests pass")],
        steps=[PlanStep(description="Edit target", requirement_ids=["R1"], files=["app/target.py"])],
        expected_tests=["tests/test_target.py"],
    )
    resp = ApprovalResponse(decision=ApprovalDecision.EDIT, edited_plan=edited)
    s = _base_state(last_approval=resp)
    assert decide("human_approval", s, LIMITS).next_node == "plan_validation"


def test_approval_reject_under_limit():
    """reject, revisions at limit -> planner."""
    resp = ApprovalResponse(decision=ApprovalDecision.REJECT, feedback="No good")
    s = _base_state(last_approval=resp, plan_revisions=LIMITS.plan_revisions)
    assert decide("human_approval", s, LIMITS).next_node == "planner"


def test_approval_reject_over_limit():
    """reject, revisions over limit -> escalate."""
    resp = ApprovalResponse(decision=ApprovalDecision.REJECT, feedback="No good")
    s = _base_state(last_approval=resp, plan_revisions=LIMITS.plan_revisions + 1)
    d = decide("human_approval", s, LIMITS)
    assert d == Decision("escalate", StopReason.PLAN_REVISIONS_EXHAUSTED)


# --- coder, debugger -> diff_gate ---

def test_coder_to_diff_gate():
    """coder -> diff_gate."""
    assert decide("coder", _base_state(), LIMITS).next_node == "diff_gate"


def test_debugger_to_diff_gate():
    """debugger -> diff_gate."""
    assert decide("debugger", _base_state(), LIMITS).next_node == "diff_gate"


# --- diff_gate ---

def test_diff_gate_clean():
    """clean -> test_runner."""
    s = _base_state(diff_gate_result=DiffGateResult.CLEAN)
    assert decide("diff_gate", s, LIMITS).next_node == "test_runner"


def test_diff_gate_denylist():
    """denylist_hit -> escalate (diff_blocked)."""
    s = _base_state(diff_gate_result=DiffGateResult.DENYLIST_HIT)
    d = decide("diff_gate", s, LIMITS)
    assert d == Decision("escalate", StopReason.DIFF_BLOCKED)


def test_diff_gate_schema_invalid_under_limit_coder():
    """schema_invalid from coder, retries at limit -> coder."""
    s = _base_state(
        diff_gate_result=DiffGateResult.SCHEMA_INVALID,
        diff_producer="coder",
        diff_schema_retries=LIMITS.diff_schema_retries,
    )
    assert decide("diff_gate", s, LIMITS).next_node == "coder"


def test_diff_gate_schema_invalid_under_limit_debugger():
    """schema_invalid from debugger, retries at limit -> debugger."""
    s = _base_state(
        diff_gate_result=DiffGateResult.SCHEMA_INVALID,
        diff_producer="debugger",
        diff_schema_retries=LIMITS.diff_schema_retries,
    )
    assert decide("diff_gate", s, LIMITS).next_node == "debugger"


@pytest.mark.parametrize("bad_producer", [None, "unknown", "reviewer", "planner"])
def test_diff_gate_schema_invalid_bad_producer(bad_producer):
    """schema_invalid with bad/unknown/None producer -> escalate (error)."""
    s = _base_state(
        diff_gate_result=DiffGateResult.SCHEMA_INVALID,
        diff_producer=bad_producer,
        diff_schema_retries=LIMITS.diff_schema_retries,
    )
    d = decide("diff_gate", s, LIMITS)
    assert d == Decision("escalate", StopReason.ERROR)


def test_diff_gate_schema_invalid_missing_producer():
    """schema_invalid with missing diff_producer field -> escalate (error)."""
    s = _base_state(
        diff_gate_result=DiffGateResult.SCHEMA_INVALID,
        diff_schema_retries=LIMITS.diff_schema_retries,
    )
    s.pop("diff_producer", None)
    d = decide("diff_gate", s, LIMITS)
    assert d == Decision("escalate", StopReason.ERROR)


def test_diff_gate_schema_invalid_over_limit():
    """schema_invalid, retries over limit -> escalate."""
    s = _base_state(
        diff_gate_result=DiffGateResult.SCHEMA_INVALID,
        diff_producer="coder",
        diff_schema_retries=LIMITS.diff_schema_retries + 1,
    )
    d = decide("diff_gate", s, LIMITS)
    assert d == Decision("escalate", StopReason.DIFF_SCHEMA_RETRIES_EXHAUSTED)


# --- test_runner ---

def test_test_runner_pass():
    """tests pass -> reviewer."""
    s = _base_state(test_evidence=TestEvidence(result=TestResult.PASS, summary="ok"))
    assert decide("test_runner", s, LIMITS).next_node == "reviewer"


def test_test_runner_error():
    """result error -> escalate (sandbox_error)."""
    s = _base_state(test_evidence=TestEvidence(result=TestResult.ERROR, summary="timeout"))
    d = decide("test_runner", s, LIMITS)
    assert d == Decision("escalate", StopReason.SANDBOX_ERROR)


def test_test_runner_fail_under_limit():
    """fail, debug_attempts < limit -> debugger."""
    s = _base_state(
        test_evidence=TestEvidence(result=TestResult.FAIL, summary="failed"),
        debug_attempts=LIMITS.debug_attempts - 1,
    )
    assert decide("test_runner", s, LIMITS).next_node == "debugger"


def test_test_runner_fail_at_limit():
    """fail, debug_attempts at limit -> escalate (debugger_limit)."""
    s = _base_state(
        test_evidence=TestEvidence(result=TestResult.FAIL, summary="failed"),
        debug_attempts=LIMITS.debug_attempts,
    )
    d = decide("test_runner", s, LIMITS)
    assert d == Decision("escalate", StopReason.DEBUGGER_LIMIT)


# --- reviewer ---

def test_reviewer_approve():
    """approve -> pr_agent."""
    rr = ReviewResult(outcome=ReviewOutcome.APPROVE, plan_version_checked="v1", dimensions=_all_pass_dims(), findings=[])
    s = _base_state(review_result=rr)
    assert decide("reviewer", s, LIMITS).next_node == "pr_agent"


def test_reviewer_revise_under_limit():
    """revise, revisions at limit -> coder."""
    rr = ReviewResult(outcome=ReviewOutcome.REVISE, plan_version_checked="v1", dimensions=_all_pass_dims(), findings=[], revision_instructions="fix")
    s = _base_state(review_result=rr, review_revisions=LIMITS.review_revisions)
    assert decide("reviewer", s, LIMITS).next_node == "coder"


def test_reviewer_revise_over_limit():
    """revise, revisions over limit -> escalate."""
    rr = ReviewResult(outcome=ReviewOutcome.REVISE, plan_version_checked="v1", dimensions=_all_pass_dims(), findings=[], revision_instructions="fix")
    s = _base_state(review_result=rr, review_revisions=LIMITS.review_revisions + 1)
    d = decide("reviewer", s, LIMITS)
    assert d == Decision("escalate", StopReason.REVIEWER_LIMIT)


def test_reviewer_block():
    """block -> escalate (reviewer_block)."""
    rr = ReviewResult(outcome=ReviewOutcome.BLOCK, plan_version_checked="v1", dimensions=_all_pass_dims(), findings=[], block_reason="security")
    s = _base_state(review_result=rr)
    d = decide("reviewer", s, LIMITS)
    assert d == Decision("escalate", StopReason.REVIEWER_BLOCK)


# --- pr_agent ---

def test_pr_agent():
    """pr_agent -> finish."""
    assert decide("pr_agent", _base_state(), LIMITS).next_node == "finish"


# --- run budget ---

@pytest.mark.parametrize("llm_node", sorted(LLM_NODES))
def test_run_budget_escalates_llm_nodes(llm_node):
    """Budget exhausted before any LLM node -> escalate (run_budget)."""
    # Build a state where each node would normally route to `llm_node`
    overrides: dict = {"run_llm_calls": LIMITS.run_budget}
    if llm_node == "retrieval":
        overrides["triage_result"] = TriageResult(category=TriageCategory.BUG_FIX, confidence=0.9, cleaned_query="q")
        after = "triage"
    elif llm_node == "planner":
        after = "retrieval"
    elif llm_node == "coder":
        overrides["last_approval"] = ApprovalResponse(decision=ApprovalDecision.APPROVE)
        after = "human_approval"
    elif llm_node == "debugger":
        overrides["test_evidence"] = TestEvidence(result=TestResult.FAIL, summary="f")
        overrides["debug_attempts"] = 0
        after = "test_runner"
    elif llm_node == "reviewer":
        overrides["test_evidence"] = TestEvidence(result=TestResult.PASS, summary="ok")
        after = "test_runner"
    elif llm_node == "pr_agent":
        rr = ReviewResult(outcome=ReviewOutcome.APPROVE, plan_version_checked="v1", dimensions=_all_pass_dims(), findings=[])
        overrides["review_result"] = rr
        after = "reviewer"
    else:
        pytest.skip(f"Unknown LLM node {llm_node}")
        return

    s = _base_state(**overrides)
    d = decide(after, s, LIMITS)
    assert d == Decision("escalate", StopReason.RUN_BUDGET)


def test_run_budget_does_not_affect_non_llm():
    """Budget should not block non-LLM nodes like test_runner."""
    s = _base_state(
        diff_gate_result=DiffGateResult.CLEAN,
        run_llm_calls=LIMITS.run_budget,
    )
    d = decide("diff_gate", s, LIMITS)
    assert d.next_node == "test_runner"
