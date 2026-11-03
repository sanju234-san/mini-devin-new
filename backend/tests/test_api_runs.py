"""Tests for GET /runs and GET /runs/{run_id} routes."""

from __future__ import annotations

import asyncio
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.run_store import InMemoryRunStore
from app.main import create_app
from app.models.run import IssueIn


def test_list_runs_empty():
    app = create_app()
    with TestClient(app) as client:
        response = client.get("/runs")
        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0
        assert data["limit"] == 20
        assert data["offset"] == 0


def test_list_runs_pagination_and_ordering():
    app = create_app()
    store: InMemoryRunStore = app.state.run_store

    async def seed():
        for i in range(1, 6):
            await store.create_run(
                IssueIn(
                    repo="octocat/Hello-World",
                    issue_number=i,
                    title=f"Run {i}",
                    body=f"Secret Body {i}",
                )
            )
            await asyncio.sleep(0.005)

    asyncio.run(seed())

    with TestClient(app) as client:
        # Default query: returns newest first
        res = client.get("/runs")
        assert res.status_code == 200
        data = res.json()
        assert data["total"] == 5
        assert len(data["items"]) == 5
        assert data["items"][0]["issue"]["issue_number"] == 5
        assert data["items"][4]["issue"]["issue_number"] == 1

        # Check detail includes issue_body but list does NOT
        assert "issue_body" not in data["items"][0]

        # Pagination: limit=2, offset=1
        page_res = client.get("/runs?limit=2&offset=1")
        assert page_res.status_code == 200
        page_data = page_res.json()
        assert page_data["total"] == 5
        assert len(page_data["items"]) == 2
        assert page_data["items"][0]["issue"]["issue_number"] == 4
        assert page_data["items"][1]["issue"]["issue_number"] == 3


@pytest.mark.parametrize("invalid_limit", [0, 101, -1])
def test_list_runs_invalid_limit(invalid_limit: int):
    app = create_app()
    with TestClient(app) as client:
        res = client.get(f"/runs?limit={invalid_limit}")
        assert res.status_code == 422


def test_list_runs_negative_offset():
    app = create_app()
    with TestClient(app) as client:
        res = client.get("/runs?offset=-1")
        assert res.status_code == 422


def test_get_run_detail_200():
    app = create_app()
    store: InMemoryRunStore = app.state.run_store

    async def seed():
        return await store.create_run(
            IssueIn(
                repo="octocat/Hello-World",
                issue_number=42,
                title="Critical bug",
                body="Full issue body with detailed steps",
            )
        )

    run = asyncio.run(seed())

    with TestClient(app) as client:
        res = client.get(f"/runs/{run.id}")
        assert res.status_code == 200
        data = res.json()
        assert data["id"] == str(run.id)
        assert data["status"] == "queued"
        assert data["issue"]["repo"] == "octocat/Hello-World"
        assert data["issue"]["issue_number"] == 42
        assert data["issue_body"] == "Full issue body with detailed steps"


def test_get_run_unknown_id_404():
    app = create_app()
    with TestClient(app) as client:
        unknown_id = uuid4()
        res = client.get(f"/runs/{unknown_id}")
        assert res.status_code == 404
        assert res.json()["detail"] == "Run not found"


def test_get_run_malformed_id_422():
    app = create_app()
    with TestClient(app) as client:
        res = client.get("/runs/not-a-valid-uuid")
        assert res.status_code == 422
