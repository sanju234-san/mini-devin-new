"""Fake agent nodes for graph skeleton testing."""

from dataclasses import dataclass, field

from app.agents.routing import LLM_NODES
from app.agents.schemas import (
    ChangeType,
    Diff,
    DiffGateResult,
    DimensionAssessment,
    DimensionName,
    DimensionResult,
    FileChange,
    GuardrailResult,
    Plan,
    PlanAuthor,
    PlanStep,
    Requirement,
    RetrievalResult,
    RetrievedChunk,
    ReviewOutcome,
    ReviewResult,
    RunState,
    StopReason,
    TestEvidence,
    TestResult,
    TriageCategory,
    TriageResult,
    build_reviewer_input,
    next_plan_version_id,
)


def _pop(lst: list):
    """Consume the first item; repeat the last when exhausted."""
    if len(lst) > 1:
        return lst.pop(0)
    return lst[0]


@dataclass
class Scenario:
    """Per-test configuration for fake agent behaviour."""
    guardrail_flagged: bool = False
    triage_category: TriageCategory = TriageCategory.BUG_FIX
    triage_confidence: float = 0.95
    plan_valid: list[bool] = field(default_factory=lambda: [True])
    diff_gate: list[DiffGateResult] = field(default_factory=lambda: [DiffGateResult.CLEAN])
    tests: list[TestResult] = field(default_factory=lambda: [TestResult.PASS])
    reviews: list[ReviewOutcome] = field(default_factory=lambda: [ReviewOutcome.APPROVE])
    node_error_at: str | None = None
    node_error_reason: StopReason = StopReason.ERROR
    trace: list[str] = field(default_factory=list)
    calls: list[str] = field(default_factory=list)


def _make_plan(version_id: str, author: PlanAuthor = PlanAuthor.PLANNER) -> Plan:
    """Create a minimal valid plan."""
    return Plan(
        version_id=version_id,
        author=author,
        intent="Fix issue",
        scope="target module",
        non_goals="none",
        affected_files=["app/target.py"],
        requirements=[Requirement(id="R1", description="Fix", acceptance_criterion="Tests pass")],
        steps=[PlanStep(description="Edit target", requirement_ids=["R1"], files=["app/target.py"])],
        expected_tests=["tests/test_target.py"],
    )


def _make_diff(plan_version_id: str, producer: str) -> Diff:
    """Create a minimal valid diff."""
    return Diff(
        plan_version_id=plan_version_id,
        file_changes=[
            FileChange(path="app/target.py", change_type=ChangeType.MODIFY,
                       diff_text="+ fixed code", requirement_ids=["R1"])
        ],
        tests_added=["tests/test_target.py"],
        deviation_log=[],
        change_summary=f"Changes by {producer}",
    )


def _check_error(name: str, scenario: Scenario) -> dict | None:
    """Return error state if this node should fail."""
    if scenario.node_error_at == name:
        return {"node_error": scenario.node_error_reason, "current_step": name}
    return None


def make_fake_nodes(scenario: Scenario) -> dict[str, callable]:
    """Build 12 fake node functions driven by a Scenario."""

    def intake(state: RunState) -> dict:
        """Pass through identity and issue."""
        scenario.calls.append("intake")
        err = _check_error("intake", scenario)
        if err:
            return err
        return {"current_step": "intake"}

    def input_guardrail(state: RunState) -> dict:
        """Check guardrail flag."""
        scenario.calls.append("input_guardrail")
        err = _check_error("input_guardrail", scenario)
        if err:
            return err
        return {
            "guardrail_result": GuardrailResult(
                flagged=scenario.guardrail_flagged,
                reason="Flagged" if scenario.guardrail_flagged else None,
            ),
            "current_step": "input_guardrail",
        }

    def triage(state: RunState) -> dict:
        """Classify the issue."""
        scenario.calls.append("triage")
        err = _check_error("triage", scenario)
        if err:
            return err
        return {
            "triage_result": TriageResult(
                category=scenario.triage_category,
                confidence=scenario.triage_confidence,
                cleaned_query="fix the bug",
            ),
            "current_step": "triage",
        }

    def retrieval(state: RunState) -> dict:
        """Return one fake chunk."""
        scenario.calls.append("retrieval")
        err = _check_error("retrieval", scenario)
        if err:
            return err
        calls = state.get("run_llm_calls", 0)
        return {
            "retrieval_result": RetrievalResult(
                chunks=[RetrievedChunk(file_path="app/target.py", snippet="def fix():", reference="ref1")]
            ),
            "run_llm_calls": calls + 1,
            "current_step": "retrieval",
        }

    def planner(state: RunState) -> dict:
        """Append a new plan version."""
        scenario.calls.append("planner")
        err = _check_error("planner", scenario)
        if err:
            return err
        vid = next_plan_version_id(state)
        plan = _make_plan(vid)
        calls = state.get("run_llm_calls", 0)
        return {
            "plan_versions": [plan],
            "run_llm_calls": calls + 1,
            "current_step": "planner",
        }

    def plan_validation(state: RunState) -> dict:
        """Check plan validity from scenario list."""
        scenario.calls.append("plan_validation")
        err = _check_error("plan_validation", scenario)
        if err:
            return err
        valid = _pop(scenario.plan_valid)
        result: dict = {"plan_validation_ok": valid, "current_step": "plan_validation"}
        if not valid:
            result["plan_schema_retries"] = state.get("plan_schema_retries", 0) + 1
        return result

    def coder(state: RunState) -> dict:
        """Produce a diff; reasoning goes only to scenario.trace."""
        scenario.calls.append("coder")
        err = _check_error("coder", scenario)
        if err:
            return err
        scenario.trace.append("Coder reasoning: decided to edit app/target.py")
        approved = state["approved_version"]
        calls = state.get("run_llm_calls", 0)
        return {
            "current_diff": _make_diff(approved, "coder"),
            "diff_producer": "coder",
            "run_llm_calls": calls + 1,
            "current_step": "coder",
        }

    def diff_gate(state: RunState) -> dict:
        """Check diff validity from scenario list."""
        scenario.calls.append("diff_gate")
        err = _check_error("diff_gate", scenario)
        if err:
            return err
        gate_result = _pop(scenario.diff_gate)
        result: dict = {"diff_gate_result": gate_result, "current_step": "diff_gate"}
        if gate_result == DiffGateResult.SCHEMA_INVALID:
            result["diff_schema_retries"] = state.get("diff_schema_retries", 0) + 1
        return result

    def test_runner(state: RunState) -> dict:
        """Run tests from scenario list."""
        scenario.calls.append("test_runner")
        err = _check_error("test_runner", scenario)
        if err:
            return err
        test_result = _pop(scenario.tests)
        return {
            "test_evidence": TestEvidence(
                result=test_result,
                summary=f"Tests {test_result.value}",
            ),
            "current_step": "test_runner",
        }

    def debugger(state: RunState) -> dict:
        """Revise the diff."""
        scenario.calls.append("debugger")
        err = _check_error("debugger", scenario)
        if err:
            return err
        approved = state["approved_version"]
        calls = state.get("run_llm_calls", 0)
        attempts = state.get("debug_attempts", 0)
        return {
            "current_diff": _make_diff(approved, "debugger"),
            "diff_producer": "debugger",
            "debug_attempts": attempts + 1,
            "run_llm_calls": calls + 1,
            "current_step": "debugger",
        }

    def reviewer(state: RunState) -> dict:
        """Review the diff using build_reviewer_input."""
        scenario.calls.append("reviewer")
        err = _check_error("reviewer", scenario)
        if err:
            return err
        # Prove the writer-blind slice works
        _ = build_reviewer_input(state)
        outcome = _pop(scenario.reviews)
        dims = [
            DimensionAssessment(name=d, result=DimensionResult.PASS, evidence="OK")
            for d in DimensionName
        ]
        approved = state["approved_version"]
        revision_instructions = "Please fix" if outcome == ReviewOutcome.REVISE else None
        block_reason = "Security issue" if outcome == ReviewOutcome.BLOCK else None
        calls = state.get("run_llm_calls", 0)
        result: dict = {
            "review_result": ReviewResult(
                outcome=outcome,
                plan_version_checked=approved,
                dimensions=dims,
                findings=[],
                revision_instructions=revision_instructions,
                block_reason=block_reason,
            ),
            "run_llm_calls": calls + 1,
            "current_step": "reviewer",
        }
        if outcome == ReviewOutcome.REVISE:
            result["review_revisions"] = state.get("review_revisions", 0) + 1
        return result

    def pr_agent(state: RunState) -> dict:
        """Write artifact references with a fake PR link."""
        scenario.calls.append("pr_agent")
        err = _check_error("pr_agent", scenario)
        if err:
            return err
        calls = state.get("run_llm_calls", 0)
        return {
            "artifact_references": {"pr_link": "https://github.com/owner/repo/pull/1"},
            "run_llm_calls": calls + 1,
            "current_step": "pr_agent",
        }

    return {
        "intake": intake,
        "input_guardrail": input_guardrail,
        "triage": triage,
        "retrieval": retrieval,
        "planner": planner,
        "plan_validation": plan_validation,
        "coder": coder,
        "diff_gate": diff_gate,
        "test_runner": test_runner,
        "debugger": debugger,
        "reviewer": reviewer,
        "pr_agent": pr_agent,
    }
