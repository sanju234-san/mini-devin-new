"""Tests for POST /issues/ingest route."""

from __future__ import annotations

from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.api.agent_gateway import AgentGateway
from app.api.deps import get_agent_gateway
from app.api.run_store import InMemoryRunStore
from app.main import create_app
from app.models.run import IssueIn, RunStatus


def test_ingest_issue_happy_path():
    app = create_app()
    with TestClient(app) as client:
        payload = {
            "repo": "octocat/Hello-World",
            "issue_number": 42,
            "title": "Fix nil pointer exception in logger",
            "body": "Detailed description of bug",
        }
        response = client.post("/issues/ingest", json=payload)
        assert response.status_code == 202
        data = response.json()
        assert data["status"] == "queued"
        assert data["issue"]["repo"] == "octocat/Hello-World"
        assert data["issue"]["issue_number"] == 42
        assert data["issue"]["title"] == "Fix nil pointer exception in logger"
        assert "id" in data
        assert "created_at" in data
        assert "updated_at" in data
        assert data["error"] is None

        # Verify run was saved in the store
        store: InMemoryRunStore = app.state.run_store
        run_id = UUID(data["id"])
        # In-memory store read
        run = client.get(f"/runs/{run_id}").json()
        assert run["id"] == str(run_id)
        assert run["issue_body"] == "Detailed description of bug"


@pytest.mark.parametrize(
    "invalid_repo",
    [
        "invalid_repo_name_without_slash",
        "owner/repo/extra",
        "/missing-owner",
        "missing-repo/",
        "owner/with spaces/repo",
    ],
)
def test_ingest_issue_invalid_repo(invalid_repo: str):
    app = create_app()
    with TestClient(app) as client:
        payload = {
            "repo": invalid_repo,
            "issue_number": 1,
            "title": "Valid title",
            "body": "Valid body",
        }
        response = client.post("/issues/ingest", json=payload)
        assert response.status_code == 422


def test_ingest_issue_zero_issue_number():
    app = create_app()
    with TestClient(app) as client:
        payload = {
            "repo": "octocat/Hello-World",
            "issue_number": 0,
            "title": "Valid title",
            "body": "Valid body",
        }
        response = client.post("/issues/ingest", json=payload)
        assert response.status_code == 422


def test_ingest_issue_empty_title():
    app = create_app()
    with TestClient(app) as client:
        payload = {
            "repo": "octocat/Hello-World",
            "issue_number": 1,
            "title": "",
            "body": "Valid body",
        }
        response = client.post("/issues/ingest", json=payload)
        assert response.status_code == 422


def test_ingest_issue_oversize_body():
    app = create_app()
    with TestClient(app) as client:
        payload = {
            "repo": "octocat/Hello-World",
            "issue_number": 1,
            "title": "Valid title",
            "body": "A" * 65537,
        }
        response = client.post("/issues/ingest", json=payload)
        assert response.status_code == 422


def test_ingest_issue_extra_field_forbidden():
    app = create_app()
    with TestClient(app) as client:
        payload = {
            "repo": "octocat/Hello-World",
            "issue_number": 1,
            "title": "Valid title",
            "body": "Valid body",
            "unexpected_extra_field": "disallowed",
        }
        response = client.post("/issues/ingest", json=payload)
        assert response.status_code == 422


def test_ingest_issue_gateway_exception_handled():
    class CrashingAgentGateway:
        async def start_run(self, run_id: UUID, issue: IssueIn) -> None:
            raise RuntimeError("Sandbox launch failed")

    app = create_app()
    app.dependency_overrides[get_agent_gateway] = lambda: CrashingAgentGateway()

    with TestClient(app) as client:
        payload = {
            "repo": "octocat/Hello-World",
            "issue_number": 99,
            "title": "Bug causing crash",
            "body": "Details",
        }
        # Ingestion API still succeeds with 202
        response = client.post("/issues/ingest", json=payload)
        assert response.status_code == 202
        run_data = response.json()
        run_id = run_data["id"]

        # Because TestClient runs background tasks synchronously upon response generation,
        # the background wrapper will have executed and caught the exception.
        run_res = client.get(f"/runs/{run_id}")
        assert run_res.status_code == 200
        run_detail = run_res.json()
        assert run_detail["status"] == RunStatus.failed.value
        assert run_detail["error"] == "Failed to start agent run"
