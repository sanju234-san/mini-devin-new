"""WebSocket event models for the Mini-Devin live run stream.

Plain-language overview
-----------------------
Every significant thing that happens during a run is broadcast as a
structured AgentEvent over the WebSocket connection. The dashboard and
Chainlit console receive these events and update the UI in real time.

Events carry only structured, action-level information:
  - Which agent is running and what step it is performing.
  - Whether a tool was called, succeeded, or failed (name and brief summary only).
  - Log lines (at a severity level).
  - Terminal output from the sandbox (stdout or stderr lines).
  - Notification that an artifact was stored.
  - Error notifications.

SECURITY RULE: No field on any model in this file may carry private
reasoning, chain-of-thought, scratchpad, or internal model deliberation.
Violating this rule leaks proprietary model internals to the browser.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.run import RunStatus


class EventType(str, Enum):
    """Category of a streaming event emitted during a run.

    Values:
        run_status:       The run's overall status changed (e.g. queued -> running).
        agent_step:       An agent node started or completed a logical work step.
        tool_call:        The agent invoked an external tool (GitHub, sandbox, etc.).
        log:              A structured log line from the agent or orchestrator.
        terminal_output:  A line of stdout or stderr captured from the sandbox.
        artifact_created: A new artifact (plan, diff, log, screenshot) was stored.
        error:            A recoverable or fatal error occurred in the workflow.
    """

    run_status = "run_status"
    agent_step = "agent_step"
    tool_call = "tool_call"
    log = "log"
    terminal_output = "terminal_output"
    artifact_created = "artifact_created"
    error = "error"


class ToolCallInfo(BaseModel):
    """Structured metadata about a single tool invocation.

    The 'summary' field is a short, redacted, human-readable description of
    what the tool did. It MUST NOT contain raw arguments, API tokens, file
    contents, secrets, or any other sensitive data. It is meant for display
    in the dashboard only.
    """

    name: str = Field(
        ...,
        max_length=100,
        description=(
            "Name of the tool that was called "
            "(e.g. 'create_file', 'run_tests', 'open_pull_request')."
        ),
    )
    state: Literal["started", "succeeded", "failed"] = Field(
        ...,
        description="Current state of the tool call.",
    )
    summary: str | None = Field(
        default=None,
        max_length=500,
        description=(
            "Short, redacted description of what the tool did or returned. "
            "Must never contain raw tool arguments, API tokens, secrets, "
            "file contents, or any other sensitive information."
        ),
    )


class AgentEvent(BaseModel):
    """A single structured event emitted during an agent run.

    Required fields per event type (enforced by the model_validator below):

        run_status       -> status
        agent_step       -> agent, step
        tool_call        -> agent, tool
        log              -> level, message
        terminal_output  -> stream, message
        artifact_created -> artifact_id
        error            -> message

    All other fields are optional context that may be present for any type.

    IMPORTANT: There is intentionally NO field for private reasoning,
    chain-of-thought, scratchpad, or internal model deliberation on this
    model. Every field serves a specific, structured observability purpose.
    """

    # extra='forbid' so accidental reasoning-trace fields are rejected at
    # construction time and never make it into the WebSocket stream.
    model_config = ConfigDict(extra="forbid")

    run_id: UUID = Field(
        ...,
        description="ID of the run this event belongs to.",
    )
    seq: int = Field(
        ...,
        ge=0,
        description=(
            "Monotonically increasing sequence number per run (0-based). "
            "Clients use this to detect gaps or out-of-order delivery."
        ),
    )
    ts: datetime = Field(
        ...,
        description=(
            "UTC timestamp when the event was emitted. "
            "Must be timezone-aware (naive datetimes are rejected)."
        ),
    )
    type: EventType = Field(
        ...,
        description="Category of this event (determines which optional fields are required).",
    )

    # --- Optional context fields ----------------------------------------
    # Each is required for certain event types; see the model_validator below.

    agent: str | None = Field(
        default=None,
        description=(
            "Name of the agent that emitted the event "
            "(e.g. 'planner', 'coder', 'test_runner')."
        ),
    )
    step: str | None = Field(
        default=None,
        description=(
            "Human-readable label of the workflow step being executed "
            "(e.g. 'writing_diff', 'running_tests', 'opening_pr')."
        ),
    )
    status: RunStatus | None = Field(
        default=None,
        description=(
            "New overall run status. Present only for run_status events. "
            "Uses the same RunStatus enum as the run list/detail endpoints."
        ),
    )
    tool: ToolCallInfo | None = Field(
        default=None,
        description=(
            "Tool invocation details. Present only for tool_call events."
        ),
    )
    model_used: str | None = Field(
        default=None,
        description=(
            "Identifier of the model or classifier that handled this step "
            "(e.g. 'gemini-1.5-pro', 'bm25_classifier'). "
            "This is the model name ONLY, never its output or internal state."
        ),
    )
    level: Literal["debug", "info", "warning", "error"] | None = Field(
        default=None,
        description="Log severity level. Present for log events.",
    )
    stream: Literal["stdout", "stderr"] | None = Field(
        default=None,
        description="Terminal stream source. Present for terminal_output events.",
    )
    message: str | None = Field(
        default=None,
        max_length=8192,
        description=(
            "Human-readable event message (max 8 KiB). "
            "Must not contain private reasoning, chain-of-thought, or secrets."
        ),
    )
    artifact_id: UUID | None = Field(
        default=None,
        description=(
            "ID of the artifact that was stored. "
            "Present only for artifact_created events."
        ),
    )

    @model_validator(mode="after")
    def _validate_required_fields_per_type(self) -> "AgentEvent":
        """Enforce that each event type carries its required fields.

        WHY A MODEL VALIDATOR INSTEAD OF SEPARATE MODELS:
        A single AgentEvent type is simpler to stream over WebSocket (one
        message schema, one deserialiser on the client side).  The trade-off
        is that optional fields must be validated at the model level rather
        than at the type level.
        """
        t = self.type

        if t == EventType.run_status:
            if self.status is None:
                raise ValueError("run_status events require the 'status' field.")

        elif t == EventType.agent_step:
            if self.agent is None:
                raise ValueError("agent_step events require the 'agent' field.")
            if self.step is None:
                raise ValueError("agent_step events require the 'step' field.")

        elif t == EventType.tool_call:
            if self.agent is None:
                raise ValueError("tool_call events require the 'agent' field.")
            if self.tool is None:
                raise ValueError("tool_call events require the 'tool' field.")

        elif t == EventType.log:
            if self.level is None:
                raise ValueError("log events require the 'level' field.")
            if self.message is None:
                raise ValueError("log events require the 'message' field.")

        elif t == EventType.terminal_output:
            if self.stream is None:
                raise ValueError("terminal_output events require the 'stream' field.")
            if self.message is None:
                raise ValueError("terminal_output events require the 'message' field.")

        elif t == EventType.artifact_created:
            if self.artifact_id is None:
                raise ValueError(
                    "artifact_created events require the 'artifact_id' field."
                )

        elif t == EventType.error:
            if self.message is None:
                raise ValueError("error events require the 'message' field.")

        # Reject naive (timezone-unaware) datetimes. All timestamps must be
        # UTC-aware so the client can always compare them correctly.
        if self.ts.tzinfo is None:
            raise ValueError(
                "AgentEvent.ts must be timezone-aware. "
                "Use datetime.now(timezone.utc) or attach tzinfo explicitly."
            )

        return self
