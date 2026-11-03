"""Tests for GET /runs/{run_id}/artifacts and GET /runs/{run_id}/artifacts/{artifact_id}."""

from __future__ import annotations

import asyncio
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from app.api.run_store import InMemoryRunStore
from app.main import create_app
from app.models.artifact import ArtifactType
from app.models.run import IssueIn


def test_artifacts_unknown_run_gives_404():
    app = create_app()
    with TestClient(app) as client:
        unknown_run_id = uuid4()
        res_list = client.get(f"/runs/{unknown_run_id}/artifacts")
        assert res_list.status_code == 404
        assert res_list.json()["detail"] == "Run not found"

        unknown_art_id = uuid4()
        res_get = client.get(f"/runs/{unknown_run_id}/artifacts/{unknown_art_id}")
        assert res_get.status_code == 404
        assert res_get.json()["detail"] == "Run not found"


def test_artifacts_unknown_artifact_gives_404():
    app = create_app()
    store: InMemoryRunStore = app.state.run_store

    async def seed():
        return await store.create_run(
            IssueIn(repo="owner/repo", issue_number=1, title="Test", body="")
        )

    run = asyncio.run(seed())

    with TestClient(app) as client:
        unknown_art_id = uuid4()
        res = client.get(f"/runs/{run.id}/artifacts/{unknown_art_id}")
        assert res.status_code == 404
        assert res.json()["detail"] == "Artifact not found"


def test_artifacts_cross_run_scoping_gives_404():
    """Verify an artifact ID belonging to run B returns 404 when requested under run A."""
    app = create_app()
    store: InMemoryRunStore = app.state.run_store

    async def seed():
        run_a = await store.create_run(
            IssueIn(repo="owner/repo", issue_number=1, title="Run A", body="")
        )
        run_b = await store.create_run(
            IssueIn(repo="owner/repo", issue_number=2, title="Run B", body="")
        )
        art_b = await store.add_artifact(
            run_id=run_b.id,
            artifact_type=ArtifactType.implementation_plan,
            name="plan_b.md",
            content="# Plan B",
            content_type="text/markdown",
        )
        return run_a, run_b, art_b

    run_a, run_b, art_b = asyncio.run(seed())

    with TestClient(app) as client:
        # Requesting run_b's artifact under run_a must return 404
        res = client.get(f"/runs/{run_a.id}/artifacts/{art_b.id}")
        assert res.status_code == 404
        assert res.json()["detail"] == "Artifact not found"

        # Requesting it under run_b returns 200
        res_valid = client.get(f"/runs/{run_b.id}/artifacts/{art_b.id}")
        assert res_valid.status_code == 200
        assert res_valid.json()["artifact"]["id"] == str(art_b.id)


def test_artifacts_list_and_text_content_200():
    app = create_app()
    store: InMemoryRunStore = app.state.run_store

    async def seed():
        run = await store.create_run(
            IssueIn(repo="owner/repo", issue_number=1, title="Test", body="")
        )
        plan_art = await store.add_artifact(
            run_id=run.id,
            artifact_type=ArtifactType.implementation_plan,
            name="plan.md",
            content="# Plan\n1. Modify handler",
            content_type="text/markdown",
            agent="planner_agent",
            model_used="claude-3-5-sonnet",
        )
        diff_art = await store.add_artifact(
            run_id=run.id,
            artifact_type=ArtifactType.code_diff,
            name="fix.patch",
            content="--- a/file.py\n+++ b/file.py\n@@ -1 +1 @@\n-old\n+new",
            content_type="text/x-diff",
            agent="coder_agent",
            model_used="claude-3-5-sonnet",
        )
        return run, plan_art, diff_art

    run, plan_art, diff_art = asyncio.run(seed())

    with TestClient(app) as client:
        # List artifacts
        list_res = client.get(f"/runs/{run.id}/artifacts")
        assert list_res.status_code == 200
        artifacts = list_res.json()
        assert len(artifacts) == 2

        # Verify NO private reasoning field anywhere in metadata
        for art in artifacts:
            for forbidden_word in ("reasoning", "thought", "scratchpad", "chain_of_thought"):
                assert forbidden_word not in art

        # Fetch plan content
        content_res = client.get(f"/runs/{run.id}/artifacts/{plan_art.id}")
        assert content_res.status_code == 200
        data = content_res.json()
        assert data["content"] == "# Plan\n1. Modify handler"
        assert data["artifact"]["name"] == "plan.md"
        assert data["artifact"]["type"] == "implementation_plan"
        assert data["artifact"]["agent"] == "planner_agent"
        assert data["artifact"]["model_used"] == "claude-3-5-sonnet"

        # Verify NO private reasoning field in ArtifactContent
        for forbidden_word in ("reasoning", "thought", "scratchpad", "chain_of_thought"):
            assert forbidden_word not in data
            assert forbidden_word not in data["artifact"]


def test_artifacts_binary_screenshot_gives_501():
    app = create_app()
    store: InMemoryRunStore = app.state.run_store

    async def seed():
        run = await store.create_run(
            IssueIn(repo="owner/repo", issue_number=1, title="Test", body="")
        )
        screenshot_art = await store.add_artifact(
            run_id=run.id,
            artifact_type=ArtifactType.screenshot,
            name="error_modal.png",
            content="fake_binary_png_data",
            content_type="image/png",
            agent="test_runner",
        )
        recording_art = await store.add_artifact(
            run_id=run.id,
            artifact_type=ArtifactType.recording,
            name="session.webm",
            content="fake_binary_webm_data",
            content_type="video/webm",
            agent="test_runner",
        )
        return run, screenshot_art, recording_art

    run, screenshot_art, recording_art = asyncio.run(seed())

    with TestClient(app) as client:
        # Screenshot content gives 501
        res1 = client.get(f"/runs/{run.id}/artifacts/{screenshot_art.id}")
        assert res1.status_code == 501
        assert "Binary artifact download not implemented yet" in res1.json()["detail"]

        # Recording content gives 501
        res2 = client.get(f"/runs/{run.id}/artifacts/{recording_art.id}")
        assert res2.status_code == 501
        assert "Binary artifact download not implemented yet" in res2.json()["detail"]
