"""Tests for InMemoryRunStore.claim_plan_decision.

Covers:
- approve / edit / reject: status and current_step transitions.
- edit: implementation_plan_approved artifact is created; original is kept.
- NOT_FOUND when run does not exist.
- CONFLICT when status is queued, running, or decision already made.
- Decision record is stored internally.
- Edited plan content is stored verbatim in the artifact.
- Concurrent claims: exactly one OK, rest CONFLICT.
"""

from __future__ import annotations

import asyncio
import json
import uuid

import pytest

from app.api.run_store import InMemoryRunStore, PlanDecisionOutcome
from app.models.artifact import ArtifactType
from app.models.plan import PlanDecision
from app.models.run import IssueIn, RunStatus


def _make_issue() -> IssueIn:
    return IssueIn(
        repo="owner/repo",
        issue_number=1,
        title="Test issue",
        body="Body text",
    )


# ---------------------------------------------------------------------------
# Approve
# ---------------------------------------------------------------------------

def test_approve_transitions_to_running() -> None:
    async def _run() -> None:
        store = InMemoryRunStore()
        run = await store.create_run(_make_issue())
        await store.update_run(run.id, status=RunStatus.awaiting_plan_approval)

        outcome, summary = await store.claim_plan_decision(
            run_id=run.id,
            decision=PlanDecision.approve,
            reason=None,
            edited_plan_content=None,
        )

        assert outcome == PlanDecisionOutcome.OK
        assert summary is not None
        assert summary.status == RunStatus.running
        assert summary.current_step == "plan_approved"

        # Verify persisted in store
        persisted = await store.get_run(run.id)
        assert persisted is not None
        assert persisted.status == RunStatus.running
        assert persisted.current_step == "plan_approved"

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# Edit
# ---------------------------------------------------------------------------

def test_edit_transitions_and_stores_artifact() -> None:
    async def _run() -> None:
        store = InMemoryRunStore()
        run = await store.create_run(_make_issue())
        await store.update_run(run.id, status=RunStatus.awaiting_plan_approval)

        # Pre-existing original artifact
        original = await store.add_artifact(
            run_id=run.id,
            artifact_type=ArtifactType.implementation_plan,
            name="implementation_plan",
            content='{"summary": "original"}',
            content_type="application/json",
            agent="planner",
        )

        edited_content = json.dumps({"summary": "edited", "steps": []})
        outcome, summary = await store.claim_plan_decision(
            run_id=run.id,
            decision=PlanDecision.edit,
            reason="Minor corrections",
            edited_plan_content=edited_content,
        )

        assert outcome == PlanDecisionOutcome.OK
        assert summary is not None
        assert summary.status == RunStatus.running
        assert summary.current_step == "plan_edited"

        # Both artifacts present
        artifacts = await store.list_artifacts(run.id)
        assert artifacts is not None
        names = {a.name for a in artifacts}
        assert "implementation_plan" in names
        assert "implementation_plan_approved" in names

        # Original untouched
        assert original.id in {a.id for a in artifacts}

        # Approved artifact metadata
        approved_meta = next(a for a in artifacts if a.name == "implementation_plan_approved")
        assert approved_meta.agent == "human_review"
        assert approved_meta.content_type == "application/json"
        assert approved_meta.type == ArtifactType.implementation_plan

        # Content is verbatim
        content_pair = await store.get_artifact(run.id, approved_meta.id)
        assert content_pair is not None
        _, raw_content = content_pair
        assert json.loads(raw_content) == {"summary": "edited", "steps": []}

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# Reject
# ---------------------------------------------------------------------------

def test_reject_transitions_to_rejected() -> None:
    async def _run() -> None:
        store = InMemoryRunStore()
        run = await store.create_run(_make_issue())
        await store.update_run(run.id, status=RunStatus.awaiting_plan_approval)

        outcome, summary = await store.claim_plan_decision(
            run_id=run.id,
            decision=PlanDecision.reject,
            reason="Not aligned with requirements",
            edited_plan_content=None,
        )

        assert outcome == PlanDecisionOutcome.OK
        assert summary is not None
        assert summary.status == RunStatus.rejected
        assert summary.current_step == "plan_rejected"

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# NOT_FOUND
# ---------------------------------------------------------------------------

def test_not_found_unknown_run() -> None:
    async def _run() -> None:
        store = InMemoryRunStore()
        outcome, summary = await store.claim_plan_decision(
            run_id=uuid.uuid4(),
            decision=PlanDecision.approve,
            reason=None,
            edited_plan_content=None,
        )
        assert outcome == PlanDecisionOutcome.NOT_FOUND
        assert summary is None

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# CONFLICT: wrong status
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("bad_status", [
    RunStatus.queued,
    RunStatus.running,
    RunStatus.completed,
    RunStatus.failed,
    RunStatus.rejected,
    RunStatus.escalated,
])
def test_conflict_wrong_status(bad_status: RunStatus) -> None:
    async def _run() -> None:
        store = InMemoryRunStore()
        run = await store.create_run(_make_issue())
        await store.update_run(run.id, status=bad_status)

        outcome, summary = await store.claim_plan_decision(
            run_id=run.id,
            decision=PlanDecision.approve,
            reason=None,
            edited_plan_content=None,
        )
        assert outcome == PlanDecisionOutcome.CONFLICT
        assert summary is None

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# CONFLICT: double-claim
# ---------------------------------------------------------------------------

def test_conflict_double_claim() -> None:
    """Second claim on the same run returns CONFLICT."""
    async def _run() -> None:
        store = InMemoryRunStore()
        run = await store.create_run(_make_issue())
        await store.update_run(run.id, status=RunStatus.awaiting_plan_approval)

        outcome1, _ = await store.claim_plan_decision(
            run_id=run.id,
            decision=PlanDecision.approve,
            reason=None,
            edited_plan_content=None,
        )
        outcome2, _ = await store.claim_plan_decision(
            run_id=run.id,
            decision=PlanDecision.approve,
            reason=None,
            edited_plan_content=None,
        )
        assert outcome1 == PlanDecisionOutcome.OK
        assert outcome2 == PlanDecisionOutcome.CONFLICT

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# Internal decision record
# ---------------------------------------------------------------------------

def test_decision_record_stored_internally() -> None:
    async def _run() -> None:
        store = InMemoryRunStore()
        run = await store.create_run(_make_issue())
        await store.update_run(run.id, status=RunStatus.awaiting_plan_approval)

        await store.claim_plan_decision(
            run_id=run.id,
            decision=PlanDecision.reject,
            reason="Reason text",
            edited_plan_content=None,
        )

        # Access internal record for test verification
        record = store._decision_records.get(run.id)
        assert record is not None
        assert record.decision == PlanDecision.reject
        assert record.reason == "Reason text"
        assert record.decided_at is not None

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# Concurrent: many simultaneous claims on the same run
# ---------------------------------------------------------------------------

def test_concurrent_claim_exactly_one_wins() -> None:
    """20 concurrent approve claims -> exactly one OK, 19 CONFLICT."""
    async def _run() -> None:
        store = InMemoryRunStore()
        run = await store.create_run(_make_issue())
        await store.update_run(run.id, status=RunStatus.awaiting_plan_approval)

        results = await asyncio.gather(*[
            store.claim_plan_decision(
                run_id=run.id,
                decision=PlanDecision.approve,
                reason=None,
                edited_plan_content=None,
            )
            for _ in range(20)
        ])

        outcomes = [r[0] for r in results]
        assert outcomes.count(PlanDecisionOutcome.OK) == 1, f"Outcomes: {outcomes}"
        assert outcomes.count(PlanDecisionOutcome.CONFLICT) == 19

        # Final run state must be running
        persisted = await store.get_run(run.id)
        assert persisted is not None
        assert persisted.status == RunStatus.running

    asyncio.run(_run())
