"""In-memory run and artifact store for Mini-Devin.

This module provides the persistence layer for tracking agent runs,
generated artifacts, and webhook idempotency tokens.

Architecture & Concurrency:
- Single-process only: Render's free tier runs a single Uvicorn worker process.
  State is stored in memory and resets whenever the server restarts.
- Concurrency safety: All mutations and reads in InMemoryRunStore are protected
  by an asyncio.Lock so concurrent HTTP requests cannot corrupt dictionary state.
- Run capacity & eviction: Storage is capped at 1000 runs by default. When capacity
  is reached upon creating a new run, the oldest finished runs (status completed,
  failed, or rejected) are evicted first to make space for the new run.
- Atomic delivery idempotency: `create_run_for_delivery` performs both the
  duplicate check and run creation inside the lock so simultaneous webhook
  deliveries cannot race to create duplicate runs.
- Delivery registry cap: Delivery tokens are capped at 5000 to prevent unbounded
  memory growth, with oldest entries evicted when the cap is reached.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Protocol, runtime_checkable
from uuid import UUID, uuid4

from app.models.artifact import ArtifactOut, ArtifactType
from app.models.plan import PlanDecision, PlanDecisionRecord
from app.models.run import (
    IssueIn,
    IssueRef,
    RunDetail,
    RunList,
    RunStatus,
    RunSummary,
)

# Finished terminal statuses that are eligible for LRU eviction when capacity is reached
EVICTION_STATUSES = frozenset({
    RunStatus.completed,
    RunStatus.failed,
    RunStatus.rejected,
})

# Maximum allowed length for GitHub delivery IDs (longer tokens are ignored)
MAX_DELIVERY_ID_LENGTH = 128


class PlanDecisionOutcome(str):
    """Result code returned by claim_plan_decision.

    Using plain string constants (not an Enum) so callers can compare with
    simple equality without importing an Enum class.

    OK:        Decision was accepted; the run status has been updated.
    NOT_FOUND: No run with that ID exists.
    CONFLICT:  The run exists but is not in awaiting_plan_approval status
               (either wrong current status, or decision already recorded).
    """

PlanDecisionOutcome.OK = "ok"
PlanDecisionOutcome.NOT_FOUND = "not_found"
PlanDecisionOutcome.CONFLICT = "conflict"


@runtime_checkable
class RunStore(Protocol):
    """Protocol defining the operations supported by the run store."""

    async def create_run(
        self,
        issue: IssueIn,
        run_id: UUID | None = None,
    ) -> RunDetail:
        """Create and store a new run initialized in 'queued' status."""
        ...

    async def create_run_for_delivery(
        self,
        delivery_id: str | None,
        issue: IssueIn,
    ) -> tuple[RunDetail, bool]:
        """Atomically get existing run or create a new run for a delivery ID.

        Returns (run, newly_created_boolean).
        """
        ...

    async def get_run(self, run_id: UUID) -> RunDetail | None:
        """Retrieve full details of a run by its ID."""
        ...

    async def list_runs(
        self,
        limit: int = 20,
        offset: int = 0,
    ) -> RunList:
        """List runs ordered newest-first with pagination."""
        ...

    async def update_run(
        self,
        run_id: UUID,
        status: RunStatus | None = None,
        current_step: str | None = None,
        error: str | None = None,
    ) -> RunDetail | None:
        """Update a run's status, step, or error message."""
        ...

    async def add_artifact(
        self,
        run_id: UUID,
        artifact_type: ArtifactType,
        name: str,
        content: str,
        content_type: str = "text/plain",
        agent: str | None = None,
        model_used: str | None = None,
    ) -> ArtifactOut:
        """Record an artifact associated with a run."""
        ...

    async def list_artifacts(self, run_id: UUID) -> list[ArtifactOut] | None:
        """List all artifacts for a run, or None if the run does not exist."""
        ...

    async def get_artifact(
        self,
        run_id: UUID,
        artifact_id: UUID,
    ) -> tuple[ArtifactOut, str] | None:
        """Retrieve an artifact and its content, or None if not found."""
        ...

    async def get_run_by_delivery(self, delivery_id: str) -> RunDetail | None:
        """Look up an existing run by its GitHub delivery ID (idempotency)."""
        ...

    async def record_delivery(self, delivery_id: str, run_id: UUID) -> None:
        """Map a GitHub delivery ID to a run ID for deduplication."""
        ...

    async def claim_plan_decision(
        self,
        run_id: UUID,
        decision: PlanDecision,
        reason: str | None,
        edited_plan_content: str | None,
    ) -> tuple[str, RunSummary | None]:
        """Atomically claim the plan decision for a run.

        Returns (outcome, RunSummary | None) where outcome is one of
        PlanDecisionOutcome.OK, NOT_FOUND, or CONFLICT.
        """
        ...


class InMemoryRunStore:
    """Thread-safe, in-memory implementation of the RunStore protocol.

    Keeps runs, artifacts, and webhook delivery IDs in RAM. Suitable for
    single-process environments (such as Render free tier single worker).
    """

    def __init__(self, max_runs: int = 1000, max_deliveries: int = 5000) -> None:
        self._max_runs = max_runs
        self._max_deliveries = max_deliveries
        self._runs: dict[UUID, RunDetail] = {}
        # Stores artifacts keyed by run_id -> {artifact_id -> (ArtifactOut, content_str)}
        self._artifacts: dict[UUID, dict[UUID, tuple[ArtifactOut, str]]] = {}
        # Stores delivery_id -> run_id mapping for webhook idempotency
        self._deliveries: dict[str, UUID] = {}
        # Internal audit log of plan decisions. Never exposed via API.
        self._decision_records: dict[UUID, PlanDecisionRecord] = {}
        # Mutex lock to guard concurrent operations in async coroutines
        self._lock = asyncio.Lock()

    def _evict_oldest_finished_unlocked(self) -> None:
        """Evict the oldest completed/failed/rejected run. Must be called with lock held."""
        candidates = [
            r for r in self._runs.values()
            if r.status in EVICTION_STATUSES
        ]
        if candidates:
            # Sort by created_at ascending to find the oldest finished run
            victim = min(candidates, key=lambda r: r.created_at)
        else:
            # Fallback if no run is finished yet: evict the oldest run overall to respect cap
            victim = min(self._runs.values(), key=lambda r: r.created_at)

        victim_id = victim.id
        self._runs.pop(victim_id, None)
        self._artifacts.pop(victim_id, None)
        # Clean up any delivery mapping associated with the evicted run
        for delivery_id, run_id in list(self._deliveries.items()):
            if run_id == victim_id:
                del self._deliveries[delivery_id]

    def _record_delivery_unlocked(self, delivery_id: str, run_id: UUID) -> None:
        """Store a delivery ID mapping, evicting the oldest if capacity is reached."""
        if len(delivery_id) > MAX_DELIVERY_ID_LENGTH:
            # Reject overly long tokens by ignoring them to prevent memory abuse
            return
        if len(self._deliveries) >= self._max_deliveries and delivery_id not in self._deliveries:
            # Python dictionaries maintain insertion order, so next(iter(...)) yields the oldest entry
            oldest_id = next(iter(self._deliveries))
            del self._deliveries[oldest_id]
        self._deliveries[delivery_id] = run_id

    async def create_run(
        self,
        issue: IssueIn,
        run_id: UUID | None = None,
    ) -> RunDetail:
        """Create and store a new run initialized in 'queued' status."""
        async with self._lock:
            # If storage reached capacity, evict the oldest finished run
            if len(self._runs) >= self._max_runs:
                self._evict_oldest_finished_unlocked()

            # Always generate a UUIDv4 unless explicitly provided (e.g. for deterministic testing)
            rid = run_id or uuid4()
            now = datetime.now(timezone.utc)
            run = RunDetail(
                id=rid,
                status=RunStatus.queued,
                current_step=None,
                issue=IssueRef(
                    repo=issue.repo,
                    issue_number=issue.issue_number,
                    title=issue.title,
                ),
                issue_body=issue.body,
                created_at=now,
                updated_at=now,
                error=None,
            )
            self._runs[rid] = run
            self._artifacts[rid] = {}
            return run

    async def create_run_for_delivery(
        self,
        delivery_id: str | None,
        issue: IssueIn,
    ) -> tuple[RunDetail, bool]:
        """Atomically get existing run or create a new run for a delivery ID.

        WHY ATOMIC WITH LOCK:
        If two concurrent requests with the same delivery ID arrive simultaneously,
        checking for existence and inserting the run in separate operations creates
        a race condition where both requests see 'not found' and create duplicate runs.
        Running both check and create inside self._lock guarantees exactly one run is
        created and returned with created=True, while subsequent requests get created=False.
        """
        async with self._lock:
            # Validate delivery ID length: tokens over 128 characters are ignored (treated as missing)
            valid_delivery_id: str | None = None
            if delivery_id and len(delivery_id) <= MAX_DELIVERY_ID_LENGTH:
                valid_delivery_id = delivery_id

            # Check if this delivery was already processed
            if valid_delivery_id and valid_delivery_id in self._deliveries:
                existing_run_id = self._deliveries[valid_delivery_id]
                existing_run = self._runs.get(existing_run_id)
                if existing_run is not None:
                    return existing_run, False

            # Not seen before; create a new run
            if len(self._runs) >= self._max_runs:
                self._evict_oldest_finished_unlocked()

            rid = uuid4()
            now = datetime.now(timezone.utc)
            run = RunDetail(
                id=rid,
                status=RunStatus.queued,
                current_step=None,
                issue=IssueRef(
                    repo=issue.repo,
                    issue_number=issue.issue_number,
                    title=issue.title,
                ),
                issue_body=issue.body,
                created_at=now,
                updated_at=now,
                error=None,
            )
            self._runs[rid] = run
            self._artifacts[rid] = {}

            if valid_delivery_id:
                self._record_delivery_unlocked(valid_delivery_id, rid)

            return run, True

    async def get_run(self, run_id: UUID) -> RunDetail | None:
        """Retrieve full details of a run by its ID."""
        async with self._lock:
            return self._runs.get(run_id)

    async def list_runs(
        self,
        limit: int = 20,
        offset: int = 0,
    ) -> RunList:
        """List runs ordered newest-first with pagination."""
        async with self._lock:
            # Order newest first based on created_at descending
            sorted_runs = sorted(
                self._runs.values(),
                key=lambda r: r.created_at,
                reverse=True,
            )
            total = len(sorted_runs)
            page = sorted_runs[offset : offset + limit]
            # Convert to RunSummary so issue_body is excluded from list responses
            items = [
                RunSummary(
                    id=r.id,
                    status=r.status,
                    current_step=r.current_step,
                    issue=r.issue,
                    created_at=r.created_at,
                    updated_at=r.updated_at,
                    error=r.error,
                )
                for r in page
            ]
            return RunList(items=items, total=total, limit=limit, offset=offset)

    async def update_run(
        self,
        run_id: UUID,
        status: RunStatus | None = None,
        current_step: str | None = None,
        error: str | None = None,
    ) -> RunDetail | None:
        """Update a run's status, step, or error message."""
        async with self._lock:
            run = self._runs.get(run_id)
            if run is None:
                return None
            now = datetime.now(timezone.utc)
            updated = run.model_copy(
                update={
                    "status": status if status is not None else run.status,
                    "current_step": current_step if current_step is not None else run.current_step,
                    "error": error if error is not None else run.error,
                    "updated_at": now,
                }
            )
            self._runs[run_id] = updated
            return updated

    def _add_artifact_unlocked(
        self,
        run_id: UUID,
        artifact_type: ArtifactType,
        name: str,
        content: str,
        content_type: str = "text/plain",
        agent: str | None = None,
        model_used: str | None = None,
    ) -> ArtifactOut:
        """Add an artifact WITHOUT acquiring the lock.

        WHY THIS HELPER EXISTS:
        claim_plan_decision already holds self._lock when it needs to store
        the edited plan artifact. Calling the public add_artifact() from within
        that context would deadlock on the same asyncio.Lock. This helper
        performs the same logic but assumes the caller already owns the lock.
        MUST only be called while self._lock is held.
        """
        artifact_id = uuid4()
        now = datetime.now(timezone.utc)
        size_bytes = len(content.encode("utf-8"))
        art_out = ArtifactOut(
            id=artifact_id,
            run_id=run_id,
            type=artifact_type,
            name=name,
            content_type=content_type,
            size_bytes=size_bytes,
            created_at=now,
            agent=agent,
            model_used=model_used,
        )
        if run_id not in self._artifacts:
            self._artifacts[run_id] = {}
        self._artifacts[run_id][artifact_id] = (art_out, content)
        return art_out

    async def add_artifact(
        self,
        run_id: UUID,
        artifact_type: ArtifactType,
        name: str,
        content: str,
        content_type: str = "text/plain",
        agent: str | None = None,
        model_used: str | None = None,
    ) -> ArtifactOut:
        """Record an artifact associated with a run."""
        async with self._lock:
            if run_id not in self._runs:
                raise KeyError(f"Run {run_id} not found")
            # Delegate to unlocked helper (we already hold the lock here)
            return self._add_artifact_unlocked(
                run_id, artifact_type, name, content, content_type, agent, model_used
            )

    async def list_artifacts(self, run_id: UUID) -> list[ArtifactOut] | None:
        """List all artifacts for a run, or None if the run does not exist."""
        async with self._lock:
            if run_id not in self._runs:
                return None
            run_arts = self._artifacts.get(run_id, {})
            # Return list of metadata objects
            return [meta for meta, _ in run_arts.values()]

    async def get_artifact(
        self,
        run_id: UUID,
        artifact_id: UUID,
    ) -> tuple[ArtifactOut, str] | None:
        """Retrieve an artifact and its content, scoped to the specific run_id."""
        async with self._lock:
            # Verify the run exists first
            if run_id not in self._runs:
                return None
            run_arts = self._artifacts.get(run_id, {})
            # Scoped lookup: artifact must belong to this specific run_id
            return run_arts.get(artifact_id)

    async def get_run_by_delivery(self, delivery_id: str) -> RunDetail | None:
        """Look up an existing run by its GitHub delivery ID (idempotency)."""
        async with self._lock:
            run_id = self._deliveries.get(delivery_id)
            if run_id is None:
                return None
            return self._runs.get(run_id)

    async def record_delivery(self, delivery_id: str, run_id: UUID) -> None:
        """Map a GitHub delivery ID to a run ID for deduplication."""
        async with self._lock:
            self._record_delivery_unlocked(delivery_id, run_id)

    async def claim_plan_decision(
        self,
        run_id: UUID,
        decision: PlanDecision,
        reason: str | None,
        edited_plan_content: str | None,
    ) -> tuple[str, RunSummary | None]:
        """Atomically claim the plan decision for a run.

        WHY THIS MUST BE ONE ATOMIC OPERATION:
        Two simultaneous HTTP requests for the same run could both pass a
        simple 'status == awaiting_plan_approval' check and both try to
        transition the run. By doing the status CHECK and STATUS TRANSITION
        inside a single asyncio.Lock acquisition, only the first request
        wins. The second request will see the already-updated status and
        receive CONFLICT.

        Returns:
            (PlanDecisionOutcome.OK, RunSummary): Decision accepted, run updated.
            (PlanDecisionOutcome.NOT_FOUND, None): No run with this ID exists.
            (PlanDecisionOutcome.CONFLICT, None): Run is not awaiting plan approval
                (wrong status, or decision already made).
        """
        async with self._lock:
            run = self._runs.get(run_id)
            if run is None:
                return PlanDecisionOutcome.NOT_FOUND, None

            # This single status check is the atomic gate.
            # - If status is queued or running: the run is not ready yet.
            # - If status is running/rejected/failed after a prior decision:
            #   the transition already happened (a previous request won the race).
            # In all cases, any status other than awaiting_plan_approval is CONFLICT.
            if run.status != RunStatus.awaiting_plan_approval:
                return PlanDecisionOutcome.CONFLICT, None

            now = datetime.now(timezone.utc)

            # Map each decision to the appropriate new status and step label
            if decision == PlanDecision.approve:
                new_status = RunStatus.running
                new_step = "plan_approved"
            elif decision == PlanDecision.edit:
                new_status = RunStatus.running
                new_step = "plan_edited"
            else:  # reject
                new_status = RunStatus.rejected
                new_step = "plan_rejected"

            # Perform the atomic status transition
            updated = run.model_copy(update={
                "status": new_status,
                "current_step": new_step,
                "updated_at": now,
            })
            self._runs[run_id] = updated

            # Store the internal decision audit record (never returned to callers)
            self._decision_records[run_id] = PlanDecisionRecord(
                decision=decision,
                reason=reason,
                decided_at=now,
            )

            # For 'edit': store the modified plan as a new artifact.
            # The original plan artifact is untouched. We use the unlocked
            # helper because we already hold self._lock.
            if decision == PlanDecision.edit and edited_plan_content is not None:
                self._add_artifact_unlocked(
                    run_id=run_id,
                    artifact_type=ArtifactType.implementation_plan,
                    name="implementation_plan_approved",
                    content=edited_plan_content,
                    content_type="application/json",
                    agent="human_review",
                )

            summary = RunSummary(
                id=updated.id,
                status=updated.status,
                current_step=updated.current_step,
                issue=updated.issue,
                created_at=updated.created_at,
                updated_at=updated.updated_at,
                error=updated.error,
            )
            return PlanDecisionOutcome.OK, summary
