"""Pydantic v2 schemas for agent runs and issue ingestion.

This module defines the data contracts for Mini-Devin runs. When a user
submits an issue or a webhook triggers intake, an agent run is created.
The schemas here validate incoming payloads and structure responses for
listing, retrieving, and tracking run statuses.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class RunStatus(str, Enum):
    """Lifecycle status of an autonomous agent run.

    Values:
        queued: Run created and waiting for background execution.
        running: Agents are actively analyzing, coding, or testing.
        awaiting_plan_approval: Paused waiting for human developer review of the plan.
        completed: Run successfully generated a verified pull request.
        failed: Run failed due to an error, timeout, or exhausted retries.
        rejected: Plan or PR was explicitly rejected by the human reviewer.
        escalated: Stopped by safety guardrails or required human intervention.
    """

    queued = "queued"
    running = "running"
    awaiting_plan_approval = "awaiting_plan_approval"
    completed = "completed"
    failed = "failed"
    rejected = "rejected"
    escalated = "escalated"


class IssueIn(BaseModel):
    """Request schema for ingesting a GitHub issue to start a run.

    Enforces strict validation on repository name format, issue number,
    title length, and maximum body size to protect against malformed or
    malicious input.
    """

    # Forbid unknown extra fields on request payloads to catch client typos early
    model_config = ConfigDict(extra="forbid")

    repo: str = Field(
        ...,
        pattern=r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$",
        description="Repository in 'owner/repo' format",
        examples=["octocat/Hello-World"],
    )
    issue_number: int = Field(
        ...,
        ge=1,
        description="GitHub issue number (positive integer)",
        examples=[42],
    )
    title: str = Field(
        ...,
        min_length=1,
        max_length=256,
        description="Issue title (1 to 256 characters)",
        examples=["Fix ZeroDivisionError in calculation handler"],
    )
    body: str = Field(
        default="",
        max_length=65536,
        description="Issue description/body (max 64 KiB plain text)",
    )


class IssueRef(BaseModel):
    """Summary reference to the GitHub issue associated with a run."""

    model_config = ConfigDict(extra="forbid")

    repo: str = Field(
        ...,
        pattern=r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$",
        description="Repository in 'owner/repo' format",
    )
    issue_number: int = Field(
        ...,
        ge=1,
        description="GitHub issue number",
    )
    title: str = Field(
        ...,
        min_length=1,
        max_length=256,
        description="Issue title",
    )


class RunSummary(BaseModel):
    """Summary representation of an agent run (used in lists and status polls)."""

    id: UUID = Field(..., description="Unique run identifier (UUIDv4)")
    status: RunStatus = Field(..., description="Current status of the run")
    current_step: str | None = Field(
        default=None,
        description="Current agent or action step being executed",
    )
    issue: IssueRef = Field(..., description="Reference to the ingested issue")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp when the run was created (UTC)",
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp when the run was last updated (UTC)",
    )
    error: str | None = Field(
        default=None,
        description="Error message if the run failed or escalated",
    )


class RunDetail(RunSummary):
    """Detailed representation of an agent run, including full issue body."""

    issue_body: str = Field(
        default="",
        description="Full text body of the ingested GitHub issue",
    )


class RunList(BaseModel):
    """Paginated list of agent run summaries."""

    items: list[RunSummary] = Field(
        default_factory=list,
        description="List of run summaries ordered newest first",
    )
    total: int = Field(
        ...,
        ge=0,
        description="Total number of runs matching the query",
    )
    limit: int = Field(
        ...,
        ge=1,
        le=100,
        description="Page size limit",
    )
    offset: int = Field(
        ...,
        ge=0,
        description="Offset from start of list",
    )
