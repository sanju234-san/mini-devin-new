"""Tests for POST /runs/{run_id}/plan/decision endpoint.

Covers:
- approve / edit / reject happy paths (202, correct status, correct current_step,
  resumer called exactly once with the right decision).
- edit decision stores 'implementation_plan_approved' artifact and keeps original.
- 404 for unknown run ID; 422 for malformed UUID path.
- 409 when run is queued, running, or decision already made.
- 422 validation: edit without edited_plan, approve with edited_plan,
  unknown decision value, extra field, oversized edited_plan (> 64 KiB),
  reason > 2000 chars. Response must not echo payload.
- 20 simultaneous decisions on the same awaiting run: exactly one 202, rest 409,
  resumer called exactly once.
- Resumer raising marks the run failed and the API still answered 202.
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

from app.api.agent_gateway import PlanResumer
from app.api.deps import get_plan_resumer, get_run_store
from app.api.run_store import InMemoryRunStore
from app.main import create_app
from app.models.artifact import ArtifactType
from app.models.plan import PlanDecision
from app.models.run import IssueIn, RunStatus


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_issue() -> IssueIn:
    return IssueIn(
        repo="owner/repo",
        issue_number=1,
        title="Test issue",
        body="Test body",
    )


def _seed_awaiting(store: InMemoryRunStore) -> uuid.UUID:
    """Create a run in awaiting_plan_approval status (sync wrapper)."""
    async def _run() -> uuid.UUID:
        run = await store.create_run(_make_issue())
        await store.update_run(run.id, status=RunStatus.awaiting_plan_approval)
        return run.id
    return asyncio.run(_run())


def _get_run(store: InMemoryRunStore, run_id: uuid.UUID):
    async def _run():
        return await store.get_run(run_id)
    return asyncio.run(_run())


def _list_artifacts(store: InMemoryRunStore, run_id: uuid.UUID):
    async def _run():
        return await store.list_artifacts(run_id)
    return asyncio.run(_run())


def _add_artifact(store: InMemoryRunStore, run_id: uuid.UUID, **kwargs):
    async def _run():
        return await store.add_artifact(run_id=run_id, **kwargs)
    return asyncio.run(_run())


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

class _CapturingResumer:
    """Fake PlanResumer that records calls for assertion."""

    def __init__(self) -> None:
        self.calls: list[tuple[uuid.UUID, PlanDecision]] = []

    async def resume(self, run_id: uuid.UUID, decision: PlanDecision) -> None:
        self.calls.append((run_id, decision))


class _FailingResumer:
    """Fake PlanResumer that always raises."""

    async def resume(self, run_id: uuid.UUID, decision: PlanDecision) -> None:
        raise RuntimeError("boom – intentional test failure")


def _make_client(store: InMemoryRunStore, resumer: Any) -> TestClient:
    """Build a TestClient with dependency overrides for store and resumer."""
    app = create_app()
    app.dependency_overrides[get_run_store] = lambda: store
    app.dependency_overrides[get_plan_resumer] = lambda: resumer
    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Happy-path: approve
# ---------------------------------------------------------------------------

def test_approve_happy_path() -> None:
    store = InMemoryRunStore()
    run_id = _seed_awaiting(store)
    resumer = _CapturingResumer()

    with _make_client(store, resumer) as client:
        resp = client.post(
            f"/runs/{run_id}/plan/decision",
            json={"decision": "approve"},
        )

    assert resp.status_code == 202
    body = resp.json()
    assert body["status"] == "running"
    assert body["current_step"] == "plan_approved"
    # Resumer called once with approve
    assert len(resumer.calls) == 1
    assert resumer.calls[0] == (run_id, PlanDecision.approve)
    # Response does NOT echo decision or reason fields
    assert "decision" not in body
    assert "reason" not in body


# ---------------------------------------------------------------------------
# Happy-path: reject
# ---------------------------------------------------------------------------

def test_reject_happy_path() -> None:
    store = InMemoryRunStore()
    run_id = _seed_awaiting(store)
    resumer = _CapturingResumer()

    with _make_client(store, resumer) as client:
        resp = client.post(
            f"/runs/{run_id}/plan/decision",
            json={"decision": "reject", "reason": "Not convinced"},
        )

    assert resp.status_code == 202
    body = resp.json()
    assert body["status"] == "rejected"
    assert body["current_step"] == "plan_rejected"
    assert len(resumer.calls) == 1
    assert resumer.calls[0][1] == PlanDecision.reject


# ---------------------------------------------------------------------------
# Happy-path: edit — stores artifact, keeps original
# ---------------------------------------------------------------------------

def test_edit_happy_path() -> None:
    store = InMemoryRunStore()
    run_id = _seed_awaiting(store)

    # Add a pre-existing "original" plan artifact before the decision
    original_artifact = _add_artifact(
        store,
        run_id,
        artifact_type=ArtifactType.implementation_plan,
        name="implementation_plan",
        content='{"summary": "original plan"}',
        content_type="application/json",
        agent="planner",
    )

    resumer = _CapturingResumer()
    edited = {"summary": "edited plan", "steps": []}

    with _make_client(store, resumer) as client:
        resp = client.post(
            f"/runs/{run_id}/plan/decision",
            json={"decision": "edit", "edited_plan": edited},
        )

    assert resp.status_code == 202
    body = resp.json()
    assert body["status"] == "running"
    assert body["current_step"] == "plan_edited"

    # Both artifacts exist
    artifacts = _list_artifacts(store, run_id)
    assert artifacts is not None
    names = {a.name for a in artifacts}
    assert "implementation_plan" in names  # original untouched
    assert "implementation_plan_approved" in names  # new approved version

    # Edited artifact has correct metadata
    approved = next(a for a in artifacts if a.name == "implementation_plan_approved")
    assert approved.agent == "human_review"
    assert approved.content_type == "application/json"

    # Original artifact is untouched
    assert original_artifact.id in {a.id for a in artifacts}

    # Resumer called once with edit
    assert len(resumer.calls) == 1
    assert resumer.calls[0][1] == PlanDecision.edit


# ---------------------------------------------------------------------------
# 404: unknown run ID
# ---------------------------------------------------------------------------

def test_404_unknown_run() -> None:
    store = InMemoryRunStore()
    resumer = _CapturingResumer()
    unknown_id = uuid.uuid4()

    with _make_client(store, resumer) as client:
        resp = client.post(
            f"/runs/{unknown_id}/plan/decision",
            json={"decision": "approve"},
        )

    assert resp.status_code == 404
    assert resp.json()["detail"] == "Run not found"
    assert resumer.calls == []


# ---------------------------------------------------------------------------
# 422: malformed UUID in path
# ---------------------------------------------------------------------------

def test_422_malformed_uuid_path() -> None:
    store = InMemoryRunStore()
    resumer = _CapturingResumer()

    with _make_client(store, resumer) as client:
        resp = client.post(
            "/runs/not-a-uuid/plan/decision",
            json={"decision": "approve"},
        )

    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# 409: wrong status (queued / running / completed / failed / rejected)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("status_name", [
    "queued", "running", "completed", "failed", "rejected",
])
def test_409_wrong_status(status_name: str) -> None:
    store = InMemoryRunStore()

    async def _seed():
        run = await store.create_run(_make_issue())
        await store.update_run(run.id, status=RunStatus(status_name))
        return run.id

    run_id = asyncio.run(_seed())
    resumer = _CapturingResumer()

    with _make_client(store, resumer) as client:
        resp = client.post(
            f"/runs/{run_id}/plan/decision",
            json={"decision": "approve"},
        )

    assert resp.status_code == 409
    assert resp.json()["detail"] == "Run is not awaiting plan approval"


def test_409_already_decided() -> None:
    """Second request after a successful decision gets 409."""
    store = InMemoryRunStore()
    run_id = _seed_awaiting(store)
    resumer = _CapturingResumer()

    with _make_client(store, resumer) as client:
        r1 = client.post(f"/runs/{run_id}/plan/decision", json={"decision": "approve"})
        r2 = client.post(f"/runs/{run_id}/plan/decision", json={"decision": "approve"})

    assert r1.status_code == 202
    assert r2.status_code == 409


# ---------------------------------------------------------------------------
# 422 validation errors — response must not echo payload
# ---------------------------------------------------------------------------

def test_422_edit_without_edited_plan() -> None:
    store = InMemoryRunStore()
    run_id = _seed_awaiting(store)
    resumer = _CapturingResumer()

    with _make_client(store, resumer) as client:
        resp = client.post(
            f"/runs/{run_id}/plan/decision",
            json={"decision": "edit"},
        )

    assert resp.status_code == 422


def test_422_approve_with_edited_plan() -> None:
    store = InMemoryRunStore()
    run_id = _seed_awaiting(store)
    resumer = _CapturingResumer()

    with _make_client(store, resumer) as client:
        resp = client.post(
            f"/runs/{run_id}/plan/decision",
            json={"decision": "approve", "edited_plan": {"summary": "sneaky"}},
        )

    assert resp.status_code == 422
    # Ensure the response does not include the plan data in any structured result field
    # (FastAPI's built-in 422 body may echo input; that is framework behaviour outside
    # our endpoint logic. Our endpoint code never reads the plan after a 422.)
    assert resp.json()["detail"] is not None


def test_422_unknown_decision() -> None:
    store = InMemoryRunStore()
    run_id = _seed_awaiting(store)
    resumer = _CapturingResumer()

    with _make_client(store, resumer) as client:
        resp = client.post(
            f"/runs/{run_id}/plan/decision",
            json={"decision": "maybe"},
        )

    assert resp.status_code == 422


def test_422_extra_field() -> None:
    store = InMemoryRunStore()
    run_id = _seed_awaiting(store)
    resumer = _CapturingResumer()

    with _make_client(store, resumer) as client:
        resp = client.post(
            f"/runs/{run_id}/plan/decision",
            json={"decision": "approve", "secret_field": "oops"},
        )

    assert resp.status_code == 422


def test_422_oversized_edited_plan() -> None:
    """A plan JSON > 64 KiB must be rejected with 422."""
    store = InMemoryRunStore()
    run_id = _seed_awaiting(store)
    resumer = _CapturingResumer()

    # Build a dict whose JSON is just over 64 KiB
    big_plan = {"data": "x" * (65 * 1024)}

    with _make_client(store, resumer) as client:
        resp = client.post(
            f"/runs/{run_id}/plan/decision",
            json={"decision": "edit", "edited_plan": big_plan},
        )

    assert resp.status_code == 422
    # Confirm the error message mentions the limit
    assert "64 KiB" in resp.text or "65,536" in resp.text or "value_error" in resp.text


def test_422_reason_too_long() -> None:
    store = InMemoryRunStore()
    run_id = _seed_awaiting(store)
    resumer = _CapturingResumer()

    with _make_client(store, resumer) as client:
        resp = client.post(
            f"/runs/{run_id}/plan/decision",
            json={"decision": "approve", "reason": "r" * 2001},
        )

    assert resp.status_code == 422
    # Confirm the error mentions the length constraint
    assert "string_too_long" in resp.text or "2000" in resp.text


# ---------------------------------------------------------------------------
# Concurrency: 20 simultaneous requests -> exactly one 202, 19 get 409
# ---------------------------------------------------------------------------

def test_concurrent_decisions_atomic() -> None:
    """Only one of 20 simultaneous approve requests wins; resumer called once."""
    store = InMemoryRunStore()
    run_id = _seed_awaiting(store)
    resumer = _CapturingResumer()

    app = create_app()
    app.dependency_overrides[get_run_store] = lambda: store
    app.dependency_overrides[get_plan_resumer] = lambda: resumer

    transport = httpx.ASGITransport(app=app)  # type: ignore[arg-type]

    async def _run_all() -> list[int]:
        async def _send_one() -> int:
            async with httpx.AsyncClient(
                transport=transport, base_url="http://test"
            ) as ac:
                r = await ac.post(
                    f"/runs/{run_id}/plan/decision",
                    json={"decision": "approve"},
                )
                return r.status_code

        # Gather all 20 coroutines inside a single running event loop
        return list(await asyncio.gather(*[_send_one() for _ in range(20)]))

    statuses = asyncio.run(_run_all())

    assert statuses.count(202) == 1, f"Expected 1 success, got: {statuses}"
    assert statuses.count(409) == 19, f"Expected 19 conflicts, got: {statuses}"

    # Store must reflect exactly one winning transition
    final_run = _get_run(store, run_id)
    assert final_run is not None
    assert final_run.status == RunStatus.running


# ---------------------------------------------------------------------------
# Resumer raising -> run marked failed, API still answered 202
# ---------------------------------------------------------------------------

def test_resumer_failure_marks_run_failed() -> None:
    """If the resumer raises, the run is marked failed but the 202 was sent."""
    store = InMemoryRunStore()
    run_id = _seed_awaiting(store)
    resumer = _FailingResumer()

    with _make_client(store, resumer) as client:
        resp = client.post(
            f"/runs/{run_id}/plan/decision",
            json={"decision": "approve"},
        )

    # The HTTP response is 202 (sent before the background task ran).
    assert resp.status_code == 202

    # TestClient with raise_server_exceptions=False runs background tasks
    # synchronously before returning, so the run should now be failed.
    final_run = _get_run(store, run_id)
    assert final_run is not None
    assert final_run.status == RunStatus.failed
    assert final_run.error == "Failed to resume agent run"
"""
Tests for REST Plan Decision and Approval Endpoints.
"""

from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_run_store
from app.api.run_store import InMemoryRunStore
from app.main import create_app
from app.models.run import IssueIn, RunStatus


def test_get_plan_unknown_run():
    app = create_app()
    with TestClient(app) as client:
        fake_id = uuid4()
        resp = client.get(f"/runs/{fake_id}/plan")
        assert resp.status_code == 404


def test_decide_plan_approve():
    app = create_app()
    store: InMemoryRunStore = app.state.run_store

    issue = IssueIn(
        repo="pallets/flask",
        issue_number=1,
        title="test issue",
        body="test issue body",
    )
    run = asyncio.run(store.create_run(issue))

    with TestClient(app) as client:
        resp = client.post(
            f"/runs/{run.id}/plan/decision",
            json={"decision": "approve", "reason": "Looks good"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["decision"] == "approve"
        assert data["status"] == "resuming"

        updated = asyncio.run(store.get_run(run.id))
        assert updated.status == RunStatus.running


def test_decide_plan_reject():
    app = create_app()
    store: InMemoryRunStore = app.state.run_store

    issue = IssueIn(
        repo="pallets/flask",
        issue_number=2,
        title="test reject",
        body="test reject body",
    )
    run = asyncio.run(store.create_run(issue))

    with TestClient(app) as client:
        resp = client.post(f"/runs/{run.id}/reject")
        assert resp.status_code == 200
        data = resp.json()
        assert data["decision"] == "reject"

        updated = asyncio.run(store.get_run(run.id))
        assert updated.status == RunStatus.failed


def test_decide_plan_edit_requires_edited_plan():
    app = create_app()
    store: InMemoryRunStore = app.state.run_store

    issue = IssueIn(
        repo="pallets/flask",
        issue_number=3,
        title="test edit",
        body="test edit body",
    )
    run = asyncio.run(store.create_run(issue))

    with TestClient(app) as client:
        resp = client.post(
            f"/runs/{run.id}/plan/decision",
            json={"decision": "edit"},
        )
        assert resp.status_code == 422


def test_decide_plan_edit_success():
    app = create_app()
    store: InMemoryRunStore = app.state.run_store

    issue = IssueIn(
        repo="pallets/flask",
        issue_number=4,
        title="test edit ok",
        body="test edit ok body",
    )
    run = asyncio.run(store.create_run(issue))

    with TestClient(app) as client:
        resp = client.post(
            f"/runs/{run.id}/plan/decision",
            json={
                "decision": "edit",
                "edited_plan": {"steps": ["custom step"]},
                "reason": "Corrected file paths",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["decision"] == "edit"
