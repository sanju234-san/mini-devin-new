"""Tests for Mini-Devin agent layer schemas and validation rules."""

import pytest
from pydantic import ValidationError

from app.agents.schemas import (
    ApprovalDecision,
    ApprovalResponse,
    ChangeType,
    Deviation,
    Diff,
    DiffGateResult,
    DimensionAssessment,
    DimensionName,
    DimensionResult,
    EventType,
    FileChange,
    Finding,
    ModelInfo,
    ModelKind,
    Plan,
    PlanAuthor,
    PlanStep,
    Requirement,
    RetrievedChunk,
    RetrievalResult,
    ReviewerInput,
    ReviewOutcome,
    ReviewResult,
    RunState,
    RunStatus,
    StepEvent,
    StopReason,
    TestEvidence,
    TestResult,
    TokenUsage,
    build_reviewer_input,
    get_approved_plan,
    plan_state,
    validate_diff_against_plan,
    validate_review_against_plan,
)

# Prevent pytest from attempting to collect imported classes as test cases
TestResult.__test__ = False
TestEvidence.__test__ = False


def sample_plan(version_id: str = "v1") -> Plan:
    """Helper creating a minimal valid Plan."""
    return Plan(
        version_id=version_id,
        author=PlanAuthor.PLANNER,
        intent="Fix bug",
        scope="auth module",
        non_goals="ui",
        affected_files=["app/auth.py"],
        requirements=[
            Requirement(id="R1", description="Check token", acceptance_criterion="Returns 401 if invalid")
        ],
        steps=[
            PlanStep(description="Update validator", requirement_ids=["R1"], files=["app/auth.py"])
        ],
        expected_tests=["tests/test_auth.py"],
    )


def test_valid_plan():
    """Verify standard valid plan construction."""
    plan = sample_plan()
    assert plan.version_id == "v1"
    assert len(plan.requirements) == 1


def test_plan_failures():
    """Verify validation errors on invalid plans."""
    # No requirements
    with pytest.raises(ValidationError, match="at least one requirement"):
        Plan(
            version_id="v1",
            author=PlanAuthor.PLANNER,
            intent="Fix",
            scope="All",
            non_goals="None",
            affected_files=["foo.py"],
            requirements=[],
            steps=[],
            expected_tests=[],
        )

    # Empty affected_files
    with pytest.raises(ValidationError, match="affected_files cannot be empty"):
        Plan(
            version_id="v1",
            author=PlanAuthor.PLANNER,
            intent="Fix",
            scope="All",
            non_goals="None",
            affected_files=[],
            requirements=[Requirement(id="R1", description="D", acceptance_criterion="A")],
            steps=[PlanStep(description="S", requirement_ids=["R1"], files=[])],
            expected_tests=[],
        )

    # Step references unknown requirement id
    with pytest.raises(ValidationError, match="unknown requirement_id 'R2'"):
        Plan(
            version_id="v1",
            author=PlanAuthor.PLANNER,
            intent="Fix",
            scope="All",
            non_goals="None",
            affected_files=["foo.py"],
            requirements=[Requirement(id="R1", description="D", acceptance_criterion="A")],
            steps=[PlanStep(description="S", requirement_ids=["R2"], files=["foo.py"])],
            expected_tests=[],
        )

    # Requirement not covered by any step
    with pytest.raises(ValidationError, match="Requirements not covered"):
        Plan(
            version_id="v1",
            author=PlanAuthor.PLANNER,
            intent="Fix",
            scope="All",
            non_goals="None",
            affected_files=["foo.py"],
            requirements=[
                Requirement(id="R1", description="D1", acceptance_criterion="A1"),
                Requirement(id="R2", description="D2", acceptance_criterion="A2"),
            ],
            steps=[PlanStep(description="S1", requirement_ids=["R1"], files=["foo.py"])],
            expected_tests=[],
        )


def test_approval_response_rules():
    """Verify ApprovalResponse payload validation rules."""
    plan = sample_plan()
    # Approve valid
    resp = ApprovalResponse(decision=ApprovalDecision.APPROVE)
    assert resp.decision == ApprovalDecision.APPROVE

    # Approve with extra payload raises
    with pytest.raises(ValidationError, match="Decision 'approve' requires neither"):
        ApprovalResponse(decision=ApprovalDecision.APPROVE, feedback="Not needed")

    # Edit requires edited_plan
    with pytest.raises(ValidationError, match="Decision 'edit' requires edited_plan"):
        ApprovalResponse(decision=ApprovalDecision.EDIT)

    resp_edit = ApprovalResponse(decision=ApprovalDecision.EDIT, edited_plan=plan)
    assert resp_edit.edited_plan is not None

    # Reject requires feedback
    with pytest.raises(ValidationError, match="Decision 'reject' requires non-empty feedback"):
        ApprovalResponse(decision=ApprovalDecision.REJECT)

    resp_rej = ApprovalResponse(decision=ApprovalDecision.REJECT, feedback="Too complex")
    assert resp_rej.feedback == "Too complex"


def test_valid_diff():
    """Verify constructing a valid diff."""
    diff = Diff(
        plan_version_id="v1",
        file_changes=[
            FileChange(
                path="app/auth.py",
                change_type=ChangeType.MODIFY,
                diff_text="+ new code",
                requirement_ids=["R1"],
            )
        ],
        tests_added=["tests/test_auth.py"],
        deviation_log=[],
        change_summary="Modified auth",
    )
    assert diff.plan_version_id == "v1"


def test_diff_failures():
    """Verify validation errors on diff construction."""
    # FileChange lacking requirement ids
    with pytest.raises(ValidationError, match="must have at least one requirement_id"):
        FileChange(
            path="app/auth.py",
            change_type=ChangeType.MODIFY,
            diff_text="+ code",
            requirement_ids=[],
        )

    # Diff with no file changes
    with pytest.raises(ValidationError, match="Diff must contain at least one file change"):
        Diff(
            plan_version_id="v1",
            file_changes=[],
            tests_added=[],
            deviation_log=[],
            change_summary="Summary",
        )

    # Diff rejects extra "reasoning" field
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        Diff(
            plan_version_id="v1",
            file_changes=[
                FileChange(
                    path="app/auth.py",
                    change_type=ChangeType.MODIFY,
                    diff_text="+ code",
                    requirement_ids=["R1"],
                )
            ],
            tests_added=[],
            deviation_log=[],
            change_summary="Summary",
            reasoning="Private thinking",  # type: ignore
        )


def test_validate_diff_against_plan():
    """Verify diff consistency checks against plan."""
    plan = sample_plan("v1")

    # Mismatched version
    diff_wrong_ver = Diff(
        plan_version_id="v2",
        file_changes=[
            FileChange(
                path="app/auth.py",
                change_type=ChangeType.MODIFY,
                diff_text="+ code",
                requirement_ids=["R1"],
            )
        ],
        tests_added=[],
        deviation_log=[],
        change_summary="Summary",
    )
    errs = validate_diff_against_plan(diff_wrong_ver, plan)
    assert any("Diff plan_version_id 'v2' != plan version_id 'v1'" in e for e in errs)

    # Unknown requirement id
    diff_unknown_req = Diff(
        plan_version_id="v1",
        file_changes=[
            FileChange(
                path="app/auth.py",
                change_type=ChangeType.MODIFY,
                diff_text="+ code",
                requirement_ids=["R99"],
            )
        ],
        tests_added=[],
        deviation_log=[],
        change_summary="Summary",
    )
    errs = validate_diff_against_plan(diff_unknown_req, plan)
    assert any("references unknown requirement 'R99'" in e for e in errs)

    # File outside affected_files without deviation
    diff_unlisted_file = Diff(
        plan_version_id="v1",
        file_changes=[
            FileChange(
                path="app/other.py",
                change_type=ChangeType.MODIFY,
                diff_text="+ code",
                requirement_ids=["R1"],
            )
        ],
        tests_added=[],
        deviation_log=[],
        change_summary="Summary",
    )
    errs = validate_diff_against_plan(diff_unlisted_file, plan)
    assert any("not in plan affected_files and lacks a deviation entry" in e for e in errs)

    # Same file with deviation entry is valid
    diff_with_dev = Diff(
        plan_version_id="v1",
        file_changes=[
            FileChange(
                path="app/other.py",
                change_type=ChangeType.MODIFY,
                diff_text="+ code",
                requirement_ids=["R1"],
            )
        ],
        tests_added=[],
        deviation_log=[
            Deviation(
                file_path="app/other.py",
                description="app/other.py helper",
                reason="Needed for R1",
                requirement_id="R1",
            )
        ],
        change_summary="Summary",
    )
    assert validate_diff_against_plan(diff_with_dev, plan) == []


def test_validate_diff_deviation_file_path_rules():
    """Verify exact matching of Deviation.file_path for unlisted changed files."""
    plan = sample_plan("v1")

    # (a) A deviation with matching file_path covers a file outside affected_files
    diff_match = Diff(
        plan_version_id="v1",
        file_changes=[
            FileChange(path="app/unlisted.py", change_type=ChangeType.ADD, diff_text="+ new", requirement_ids=["R1"])
        ],
        tests_added=[],
        deviation_log=[
            Deviation(file_path="app/unlisted.py", description="New helper", reason="Required for R1", requirement_id="R1")
        ],
        change_summary="Added unlisted helper",
    )
    assert validate_diff_against_plan(diff_match, plan) == []

    # (b) A deviation whose file_path is a different file does not cover it
    diff_different_file = Diff(
        plan_version_id="v1",
        file_changes=[
            FileChange(path="app/unlisted.py", change_type=ChangeType.ADD, diff_text="+ new", requirement_ids=["R1"])
        ],
        tests_added=[],
        deviation_log=[
            Deviation(file_path="app/different.py", description="Different helper", reason="Required for R1", requirement_id="R1")
        ],
        change_summary="Added unlisted helper with wrong deviation",
    )
    errs_diff = validate_diff_against_plan(diff_different_file, plan)
    assert any("Changed file 'app/unlisted.py' not in plan affected_files and lacks a deviation entry" in e for e in errs_diff)

    # (c) Mentioning the path only in description or reason does not count
    diff_text_mention_only = Diff(
        plan_version_id="v1",
        file_changes=[
            FileChange(path="app/unlisted.py", change_type=ChangeType.ADD, diff_text="+ new", requirement_ids=["R1"])
        ],
        tests_added=[],
        deviation_log=[
            Deviation(
                file_path="app/different.py",
                description="Modifies app/unlisted.py for R1",
                reason="See app/unlisted.py notes",
                requirement_id="R1",
            )
        ],
        change_summary="Path mentioned only in description and reason",
    )
    errs_text = validate_diff_against_plan(diff_text_mention_only, plan)
    assert any("Changed file 'app/unlisted.py' not in plan affected_files and lacks a deviation entry" in e for e in errs_text)


def all_dimensions(pass_all: bool = True) -> list[DimensionAssessment]:
    """Helper returning 6 dimensions assessments."""
    res = DimensionResult.PASS if pass_all else DimensionResult.FAIL
    return [
        DimensionAssessment(name=dim, result=res, evidence="Evidence")
        for dim in DimensionName
    ]


def test_review_result_rules():
    """Verify review schema validation rules."""
    # Valid approve
    rev = ReviewResult(
        outcome=ReviewOutcome.APPROVE,
        plan_version_checked="v1",
        dimensions=all_dimensions(pass_all=True),
        findings=[],
    )
    assert rev.outcome == ReviewOutcome.APPROVE

    # Revise without revision_instructions
    with pytest.raises(ValidationError, match="requires non-empty revision_instructions"):
        ReviewResult(
            outcome=ReviewOutcome.REVISE,
            plan_version_checked="v1",
            dimensions=all_dimensions(pass_all=True),
            findings=[],
        )

    # Block without block_reason
    with pytest.raises(ValidationError, match="requires non-empty block_reason"):
        ReviewResult(
            outcome=ReviewOutcome.BLOCK,
            plan_version_checked="v1",
            dimensions=all_dimensions(pass_all=True),
            findings=[],
        )

    # Approve with failing dimension (PROPOSED rule)
    with pytest.raises(ValidationError, match="Cannot approve when any review dimension failed"):
        ReviewResult(
            outcome=ReviewOutcome.APPROVE,
            plan_version_checked="v1",
            dimensions=all_dimensions(pass_all=False),
            findings=[],
        )

    # Missing dimension
    dims_missing = all_dimensions(pass_all=True)[:-1]
    with pytest.raises(ValidationError, match="must assess all 6 dimensions"):
        ReviewResult(
            outcome=ReviewOutcome.APPROVE,
            plan_version_checked="v1",
            dimensions=dims_missing,
            findings=[],
        )

    # Duplicate dimension
    dims_dup = all_dimensions(pass_all=True)[:-1] + [all_dimensions(pass_all=True)[0]]
    with pytest.raises(ValidationError, match="must assess all 6 dimensions"):
        ReviewResult(
            outcome=ReviewOutcome.APPROVE,
            plan_version_checked="v1",
            dimensions=dims_dup,
            findings=[],
        )


def test_validate_review_against_plan():
    """Verify review version check against approved plan."""
    rev = ReviewResult(
        outcome=ReviewOutcome.APPROVE,
        plan_version_checked="v1",
        dimensions=all_dimensions(pass_all=True),
        findings=[],
    )
    assert validate_review_against_plan(rev, "v1") == []
    errs = validate_review_against_plan(rev, "v2")
    assert len(errs) == 1
    assert "does not match approved" in errs[0]


def test_step_event_rules():
    """Verify tool_name, token, and extra field rules on StepEvent."""
    model_llm = ModelInfo(kind=ModelKind.LLM, name="llama3", provider="groq", tier="strong")
    model_class = ModelInfo(kind=ModelKind.CLASSIFIER, name="distilbert", provider="hf", tier="cheap")

    # tool_call requires tool_name
    with pytest.raises(ValidationError, match="Event type 'tool_call' requires tool_name"):
        StepEvent(
            run_id="r1",
            event_id="e1",
            timestamp="2026-10-03T00:00:00Z",
            agent="coder",
            step="editing",
            event_type=EventType.TOOL_CALL,
            tool_name=None,
            model_info=model_llm,
            message="Calling tool",
        )

    # non-tool_call forbids tool_name
    with pytest.raises(ValidationError, match="tool_name must be None when event_type is not 'tool_call'"):
        StepEvent(
            run_id="r1",
            event_id="e1",
            timestamp="2026-10-03T00:00:00Z",
            agent="coder",
            step="editing",
            event_type=EventType.STARTED,
            tool_name="edit_file",
            model_info=model_llm,
            message="Started",
        )

    # tokens allowed only for LLM
    with pytest.raises(ValidationError, match="tokens is allowed only when model_info.kind is 'llm'"):
        StepEvent(
            run_id="r1",
            event_id="e1",
            timestamp="2026-10-03T00:00:00Z",
            agent="triage",
            step="classifying",
            event_type=EventType.COMPLETED,
            model_info=model_class,
            tokens=TokenUsage(input_tokens=10, output_tokens=5),
            message="Classified",
        )

    # StepEvent rejects extra reasoning field
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        StepEvent(
            run_id="r1",
            event_id="e1",
            timestamp="2026-10-03T00:00:00Z",
            agent="coder",
            step="running",
            event_type=EventType.COMPLETED,
            model_info=model_llm,
            message="Done",
            reasoning="Hidden thoughts",  # type: ignore
        )


def test_stop_reason_values():
    """Verify StopReason enum contains exactly the 12 designated stop reasons."""
    expected = {
        "injection_suspected",
        "plan_schema_retries_exhausted",
        "plan_revisions_exhausted",
        "diff_blocked",
        "diff_schema_retries_exhausted",
        "debugger_limit",
        "reviewer_limit",
        "reviewer_block",
        "run_budget",
        "sandbox_error",
        "error",
        "triage_uncertain",
    }
    actual = {r.value for r in StopReason}
    assert actual == expected


def test_build_reviewer_input():
    """Verify writer-blind ReviewerInput construction from RunState."""
    plan1 = sample_plan("v1")
    plan2 = sample_plan("v2")

    diff = Diff(
        plan_version_id="v1",
        file_changes=[
            FileChange(
                path="app/auth.py",
                change_type=ChangeType.MODIFY,
                diff_text="+ code",
                requirement_ids=["R1"],
            )
        ],
        tests_added=[],
        deviation_log=[],
        change_summary="Summary",
    )

    state: RunState = {
        "run_id": "r1",
        "repo": "owner/repo",
        "issue_number": 42,
        "issue_text": "Bug description",
        "plan_versions": [plan1, plan2],
        "approved_version": "v1",
        "approval_feedback": "Looks good",
        "current_diff": diff,
        "test_evidence": TestEvidence(result=TestResult.PASS, summary="All tests passed"),
        "retrieval_result": RetrievalResult(
            chunks=[RetrievedChunk(file_path="app/auth.py", snippet="def auth():", reference="ref1")]
        ),
    }

    # Returns approved version (v1), not latest (v2)
    reviewer_input = build_reviewer_input(state)
    assert reviewer_input.approved_plan.version_id == "v1"
    assert reviewer_input.diff.plan_version_id == "v1"
    assert len(reviewer_input.retrieval_chunks) == 1
    assert reviewer_input.test_evidence is not None
    assert reviewer_input.test_evidence.result == TestResult.PASS

    # Verify ReviewerInput has no field for coder reasoning
    assert "reasoning" not in ReviewerInput.model_fields
    assert "coder_reasoning" not in ReviewerInput.model_fields

    # Raises when approved_version is missing
    state_no_approved = dict(state)
    state_no_approved.pop("approved_version")
    with pytest.raises(ValueError, match="Missing 'approved_version' in state"):
        build_reviewer_input(state_no_approved)  # type: ignore

    # Raises when approved_version does not match any plan
    state_bad_version = dict(state, approved_version="v99")
    with pytest.raises(ValueError, match="Approved plan version 'v99' not found"):
        build_reviewer_input(state_bad_version)


def test_diff_gate_result_enum():
    """Verify DiffGateResult enum values."""
    assert DiffGateResult.CLEAN.value == "clean"
    assert DiffGateResult.SCHEMA_INVALID.value == "schema_invalid"
    assert DiffGateResult.DENYLIST_HIT.value == "denylist_hit"


def test_run_state_extensions():
    """Verify RunState accepts the graph routing fields."""
    state: RunState = {
        "run_id": "r-1",
        "plan_validation_ok": True,
        "diff_gate_result": DiffGateResult.CLEAN,
        "diff_producer": "coder",
        "last_approval": ApprovalResponse(decision=ApprovalDecision.APPROVE),
        "node_error": StopReason.ERROR,
    }
    assert state.get("plan_validation_ok") is True
    assert state.get("diff_gate_result") == DiffGateResult.CLEAN
    assert state.get("diff_producer") == "coder"
    assert state.get("last_approval").decision == ApprovalDecision.APPROVE  # type: ignore
    assert state.get("node_error") == StopReason.ERROR


def test_plan_status_field_rejected():
    """Constructing a Plan with a status field is rejected (extra="forbid")."""
    with pytest.raises(ValidationError):
        Plan(
            version_id="v1",
            author=PlanAuthor.PLANNER,
            status="draft",  # extra field — must be rejected
            intent="Fix",
            scope="All",
            non_goals="None",
            affected_files=["foo.py"],
            requirements=[Requirement(id="R1", description="D", acceptance_criterion="A")],
            steps=[PlanStep(description="S", requirement_ids=["R1"], files=["foo.py"])],
            expected_tests=[],
        )


def test_plan_state_returns_correct_values():
    """plan_state returns approved, superseded and pending correctly."""
    p1 = sample_plan("v1")
    p2 = sample_plan("v2")
    p3 = sample_plan("v3")
    state: RunState = {
        "plan_versions": [p1, p2, p3],
        "approved_version": "v2",
    }
    assert plan_state(state, "v2") == "approved"
    assert plan_state(state, "v1") == "superseded"
    assert plan_state(state, "v3") == "pending"


def test_plan_state_raises_for_unknown_version():
    """plan_state raises ValueError for an unknown version id."""
    p1 = sample_plan("v1")
    state: RunState = {
        "plan_versions": [p1],
        "approved_version": "v1",
    }
    with pytest.raises(ValueError, match="not found in state plan_versions"):
        plan_state(state, "v99")
