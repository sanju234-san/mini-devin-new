"""Tests for models/plan.py and models/events.py.

Covers:
- PlanDecisionIn: valid bodies accepted; invalid bodies (missing edited_plan,
  extra edited_plan, unknown decision, extra field, oversized plan, long reason)
  rejected with ValidationError.
- AgentEvent: each EventType accepts a valid example; each rejects a missing
  required field; extra field ('reasoning') is rejected; naive datetime rejected.
- Introspect model_fields of every model in events.py: no field name contains
  'reasoning', 'thought', 'scratchpad', or 'chain_of_thought'.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.models.events import AgentEvent, EventType, ToolCallInfo
from app.models.plan import PlanDecision, PlanDecisionIn
from app.models.run import RunStatus


# ---------------------------------------------------------------------------
# PlanDecisionIn validation
# ---------------------------------------------------------------------------

class TestPlanDecisionIn:
    def test_approve_valid(self) -> None:
        body = PlanDecisionIn(decision="approve")
        assert body.decision == "approve"
        assert body.edited_plan is None
        assert body.reason is None

    def test_approve_with_reason(self) -> None:
        body = PlanDecisionIn(decision="approve", reason="Looks good")
        assert body.reason == "Looks good"

    def test_reject_valid(self) -> None:
        body = PlanDecisionIn(decision="reject", reason="Not aligned")
        assert body.decision == "reject"

    def test_edit_valid(self) -> None:
        body = PlanDecisionIn(decision="edit", edited_plan={"summary": "fixed"})
        assert body.edited_plan == {"summary": "fixed"}

    def test_edit_without_edited_plan_raises(self) -> None:
        with pytest.raises(ValidationError, match="edited_plan"):
            PlanDecisionIn(decision="edit")

    def test_approve_with_edited_plan_raises(self) -> None:
        with pytest.raises(ValidationError):
            PlanDecisionIn(decision="approve", edited_plan={"summary": "oops"})

    def test_reject_with_edited_plan_raises(self) -> None:
        with pytest.raises(ValidationError):
            PlanDecisionIn(decision="reject", edited_plan={"summary": "oops"})

    def test_unknown_decision_raises(self) -> None:
        with pytest.raises(ValidationError):
            PlanDecisionIn(decision="maybe")  # type: ignore[arg-type]

    def test_extra_field_raises(self) -> None:
        with pytest.raises(ValidationError):
            PlanDecisionIn(decision="approve", secret="hacked")  # type: ignore[call-arg]

    def test_oversized_edited_plan_raises(self) -> None:
        """A plan > 64 KiB must raise ValidationError."""
        big_plan = {"data": "x" * (65 * 1024)}
        with pytest.raises(ValidationError, match="64 KiB"):
            PlanDecisionIn(decision="edit", edited_plan=big_plan)

    def test_reason_max_length(self) -> None:
        """reason of exactly 2000 chars is valid; 2001 chars is not."""
        PlanDecisionIn(decision="approve", reason="r" * 2000)
        with pytest.raises(ValidationError):
            PlanDecisionIn(decision="approve", reason="r" * 2001)


# ---------------------------------------------------------------------------
# AgentEvent: valid examples per EventType
# ---------------------------------------------------------------------------

def _base_event(**extra) -> dict:
    return {
        "run_id": str(uuid.uuid4()),
        "seq": 0,
        "ts": datetime.now(timezone.utc).isoformat(),
        **extra,
    }


class TestAgentEventValid:
    def test_run_status_valid(self) -> None:
        e = AgentEvent(
            **_base_event(type="run_status", status=RunStatus.running)
        )
        assert e.type == EventType.run_status
        assert e.status == RunStatus.running

    def test_agent_step_valid(self) -> None:
        e = AgentEvent(
            **_base_event(type="agent_step", agent="planner", step="writing_plan")
        )
        assert e.agent == "planner"
        assert e.step == "writing_plan"

    def test_tool_call_valid(self) -> None:
        tool = ToolCallInfo(name="run_tests", state="succeeded", summary="All 10 tests passed")
        e = AgentEvent(
            **_base_event(type="tool_call", agent="coder", tool=tool.model_dump())
        )
        assert e.tool is not None
        assert e.tool.name == "run_tests"

    def test_log_valid(self) -> None:
        e = AgentEvent(
            **_base_event(type="log", level="info", message="Starting triage")
        )
        assert e.level == "info"
        assert e.message == "Starting triage"

    def test_terminal_output_valid(self) -> None:
        e = AgentEvent(
            **_base_event(type="terminal_output", stream="stdout", message="PASSED 10 tests")
        )
        assert e.stream == "stdout"

    def test_artifact_created_valid(self) -> None:
        aid = uuid.uuid4()
        e = AgentEvent(
            **_base_event(type="artifact_created", artifact_id=str(aid))
        )
        assert e.artifact_id == aid

    def test_error_valid(self) -> None:
        e = AgentEvent(
            **_base_event(type="error", message="Sandbox timed out")
        )
        assert e.message == "Sandbox timed out"


# ---------------------------------------------------------------------------
# AgentEvent: missing required field per EventType
# ---------------------------------------------------------------------------

class TestAgentEventMissingRequired:
    def test_run_status_missing_status(self) -> None:
        with pytest.raises(ValidationError, match="status"):
            AgentEvent(**_base_event(type="run_status"))

    def test_agent_step_missing_agent(self) -> None:
        with pytest.raises(ValidationError, match="agent"):
            AgentEvent(**_base_event(type="agent_step", step="s"))

    def test_agent_step_missing_step(self) -> None:
        with pytest.raises(ValidationError, match="step"):
            AgentEvent(**_base_event(type="agent_step", agent="planner"))

    def test_tool_call_missing_agent(self) -> None:
        tool = ToolCallInfo(name="t", state="started")
        with pytest.raises(ValidationError, match="agent"):
            AgentEvent(**_base_event(type="tool_call", tool=tool.model_dump()))

    def test_tool_call_missing_tool(self) -> None:
        with pytest.raises(ValidationError, match="tool"):
            AgentEvent(**_base_event(type="tool_call", agent="coder"))

    def test_log_missing_level(self) -> None:
        with pytest.raises(ValidationError, match="level"):
            AgentEvent(**_base_event(type="log", message="hello"))

    def test_log_missing_message(self) -> None:
        with pytest.raises(ValidationError, match="message"):
            AgentEvent(**_base_event(type="log", level="info"))

    def test_terminal_output_missing_stream(self) -> None:
        with pytest.raises(ValidationError, match="stream"):
            AgentEvent(**_base_event(type="terminal_output", message="line"))

    def test_terminal_output_missing_message(self) -> None:
        with pytest.raises(ValidationError, match="message"):
            AgentEvent(**_base_event(type="terminal_output", stream="stdout"))

    def test_artifact_created_missing_artifact_id(self) -> None:
        with pytest.raises(ValidationError, match="artifact_id"):
            AgentEvent(**_base_event(type="artifact_created"))

    def test_error_missing_message(self) -> None:
        with pytest.raises(ValidationError, match="message"):
            AgentEvent(**_base_event(type="error"))


# ---------------------------------------------------------------------------
# AgentEvent: extra field rejected
# ---------------------------------------------------------------------------

def test_agent_event_extra_field_rejected() -> None:
    """Extra fields (e.g. 'reasoning') must be rejected by AgentEvent."""
    with pytest.raises(ValidationError):
        AgentEvent(
            **_base_event(
                type="error",
                message="oops",
                reasoning="private chain-of-thought",  # must be rejected
            )
        )


# ---------------------------------------------------------------------------
# AgentEvent: naive datetime rejected
# ---------------------------------------------------------------------------

def test_agent_event_naive_datetime_rejected() -> None:
    """A timezone-naive datetime on 'ts' must raise ValidationError."""
    with pytest.raises(ValidationError, match="timezone"):
        AgentEvent(
            run_id=uuid.uuid4(),
            seq=0,
            ts=datetime(2024, 1, 1, 12, 0, 0),  # naive — no tzinfo
            type=EventType.error,
            message="some error",
        )


# ---------------------------------------------------------------------------
# Introspect model_fields: no forbidden field names in events.py models
# ---------------------------------------------------------------------------

FORBIDDEN_FIELD_SUBSTRINGS = frozenset({
    "reasoning",
    "thought",
    "scratchpad",
    "chain_of_thought",
})


def test_no_reasoning_fields_on_agent_event() -> None:
    """AgentEvent must not have any field whose name contains reasoning-trace words."""
    for field_name in AgentEvent.model_fields:
        lower = field_name.lower()
        for forbidden in FORBIDDEN_FIELD_SUBSTRINGS:
            assert forbidden not in lower, (
                f"AgentEvent has a field named '{field_name}' which contains "
                f"the forbidden substring '{forbidden}'. Reasoning-trace fields "
                "must never appear in API-exposed models."
            )


def test_no_reasoning_fields_on_tool_call_info() -> None:
    for field_name in ToolCallInfo.model_fields:
        lower = field_name.lower()
        for forbidden in FORBIDDEN_FIELD_SUBSTRINGS:
            assert forbidden not in lower, (
                f"ToolCallInfo has field '{field_name}' containing '{forbidden}'."
            )


# ---------------------------------------------------------------------------
# ToolCallInfo: summary max_length
# ---------------------------------------------------------------------------

def test_tool_call_summary_max_length() -> None:
    """summary is capped at 500 characters."""
    # Exactly 500 is fine
    ToolCallInfo(name="t", state="started", summary="s" * 500)
    with pytest.raises(ValidationError):
        ToolCallInfo(name="t", state="started", summary="s" * 501)


def test_tool_call_name_max_length() -> None:
    """name is capped at 100 characters."""
    ToolCallInfo(name="n" * 100, state="started")
    with pytest.raises(ValidationError):
        ToolCallInfo(name="n" * 101, state="started")
