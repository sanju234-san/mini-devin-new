"""Unit tests for InMemoryRunStore and RunStore protocol operations."""

from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest

from app.api.run_store import InMemoryRunStore
from app.models.artifact import ArtifactType
from app.models.run import IssueIn, RunStatus


def test_run_store_create_and_get():
    async def _test():
        store = InMemoryRunStore()
        issue = IssueIn(
            repo="octocat/Hello-World",
            issue_number=1,
            title="Initial issue",
            body="Issue description",
        )
        created = await store.create_run(issue)
        assert created.status == RunStatus.queued
        assert created.issue.repo == "octocat/Hello-World"
        assert created.issue_body == "Issue description"
        assert created.current_step is None
        assert created.error is None

        fetched = await store.get_run(created.id)
        assert fetched is not None
        assert fetched.id == created.id
        assert fetched.issue_body == "Issue description"

        missing = await store.get_run(uuid4())
        assert missing is None

    asyncio.run(_test())


def test_run_store_list_ordering_and_pagination():
    async def _test():
        store = InMemoryRunStore()
        for i in range(1, 6):
            issue = IssueIn(
                repo="octocat/Hello-World",
                issue_number=i,
                title=f"Issue {i}",
                body=f"Body {i}",
            )
            await store.create_run(issue)
            await asyncio.sleep(0.005)

        # List all runs
        res = await store.list_runs(limit=10, offset=0)
        assert res.total == 5
        assert len(res.items) == 5
        assert res.items[0].issue.issue_number == 5
        assert res.items[4].issue.issue_number == 1
        assert not hasattr(res.items[0], "issue_body")

        # Pagination
        page = await store.list_runs(limit=2, offset=1)
        assert page.total == 5
        assert len(page.items) == 2
        assert page.items[0].issue.issue_number == 4
        assert page.items[1].issue.issue_number == 3

    asyncio.run(_test())


def test_run_store_update():
    async def _test():
        store = InMemoryRunStore()
        issue = IssueIn(
            repo="octocat/Hello-World",
            issue_number=10,
            title="Bug title",
            body="Bug body",
        )
        run = await store.create_run(issue)
        created_at = run.created_at
        updated_at_orig = run.updated_at

        await asyncio.sleep(0.005)
        updated = await store.update_run(
            run.id,
            status=RunStatus.running,
            current_step="coder_agent",
            error=None,
        )
        assert updated is not None
        assert updated.status == RunStatus.running
        assert updated.current_step == "coder_agent"
        assert updated.updated_at >= updated_at_orig
        assert updated.created_at == created_at

        missing_update = await store.update_run(uuid4(), status=RunStatus.completed)
        assert missing_update is None

    asyncio.run(_test())


def test_run_store_eviction_at_cap():
    async def _test():
        store = InMemoryRunStore(max_runs=3)

        run1 = await store.create_run(
            IssueIn(repo="owner/repo", issue_number=1, title="1", body="")
        )
        await asyncio.sleep(0.005)
        run2 = await store.create_run(
            IssueIn(repo="owner/repo", issue_number=2, title="2", body="")
        )
        await asyncio.sleep(0.005)
        run3 = await store.create_run(
            IssueIn(repo="owner/repo", issue_number=3, title="3", body="")
        )

        await store.update_run(run1.id, status=RunStatus.completed)
        await store.record_delivery("delivery-1", run1.id)
        assert await store.get_run_by_delivery("delivery-1") is not None

        await asyncio.sleep(0.005)
        run4 = await store.create_run(
            IssueIn(repo="owner/repo", issue_number=4, title="4", body="")
        )

        res = await store.list_runs(limit=10)
        assert res.total == 3
        run_ids = {r.id for r in res.items}
        assert run1.id not in run_ids
        assert run2.id in run_ids
        assert run3.id in run_ids
        assert run4.id in run_ids
        assert await store.get_run_by_delivery("delivery-1") is None

    asyncio.run(_test())


def test_run_store_delivery_registry_and_cap():
    async def _test():
        # Test delivery registry capacity eviction with max_deliveries=3
        store = InMemoryRunStore(max_deliveries=3)
        run = await store.create_run(
            IssueIn(repo="owner/repo", issue_number=1, title="Test", body="")
        )

        await store.record_delivery("del-1", run.id)
        await store.record_delivery("del-2", run.id)
        await store.record_delivery("del-3", run.id)

        assert await store.get_run_by_delivery("del-1") is not None
        assert await store.get_run_by_delivery("del-2") is not None
        assert await store.get_run_by_delivery("del-3") is not None

        # 4th delivery evicts the oldest (del-1)
        await store.record_delivery("del-4", run.id)
        assert await store.get_run_by_delivery("del-1") is None
        assert await store.get_run_by_delivery("del-4") is not None

        # Delivery ID > 128 characters is rejected/ignored
        oversize_delivery = "d" * 129
        await store.record_delivery(oversize_delivery, run.id)
        assert await store.get_run_by_delivery(oversize_delivery) is None

    asyncio.run(_test())


def test_run_store_atomic_create_run_for_delivery():
    async def _test():
        store = InMemoryRunStore(max_deliveries=5)
        issue = IssueIn(repo="owner/repo", issue_number=1, title="Test", body="Body")

        # First delivery creates the run
        run1, created1 = await store.create_run_for_delivery("deliv-abc", issue)
        assert created1 is True
        assert run1.status == RunStatus.queued

        # Second delivery with same token returns existing run and created=False
        run2, created2 = await store.create_run_for_delivery("deliv-abc", issue)
        assert created2 is False
        assert run2.id == run1.id

        # None delivery creates new run every time
        run3, created3 = await store.create_run_for_delivery(None, issue)
        assert created3 is True
        assert run3.id != run1.id

        # Oversize delivery token (> 128 chars) is ignored and treated as missing
        oversize_token = "x" * 129
        run4, created4 = await store.create_run_for_delivery(oversize_token, issue)
        assert created4 is True
        assert run4.id != run1.id
        assert await store.get_run_by_delivery(oversize_token) is None

    asyncio.run(_test())


def test_run_store_concurrent_delivery_and_creates_safe():
    async def _test():
        store = InMemoryRunStore(max_runs=100)
        issue = IssueIn(repo="owner/repo", issue_number=1, title="Concurrent", body="")

        # 20 simultaneous requests with the exact same delivery ID
        results = await asyncio.gather(
            *(store.create_run_for_delivery("identical-delivery-id", issue) for _ in range(20))
        )
        assert len(results) == 20
        # Exactly one call should have created=True
        created_flags = [c for _, c in results]
        assert created_flags.count(True) == 1
        assert created_flags.count(False) == 19

        # All 20 calls must receive the exact same run ID
        run_ids = {r.id for r, _ in results}
        assert len(run_ids) == 1

        # Total runs in store must be exactly 1
        res = await store.list_runs()
        assert res.total == 1

    asyncio.run(_test())


def test_run_store_artifacts():
    async def _test():
        store = InMemoryRunStore()
        run = await store.create_run(
            IssueIn(repo="owner/repo", issue_number=1, title="Title", body="")
        )

        assert await store.list_artifacts(uuid4()) is None
        assert await store.get_artifact(uuid4(), uuid4()) is None

        art = await store.add_artifact(
            run_id=run.id,
            artifact_type=ArtifactType.implementation_plan,
            name="plan.md",
            content="# Plan\n1. Do something",
            content_type="text/markdown",
            agent="planner",
            model_used="claude-3-5-sonnet",
        )
        assert art.type == ArtifactType.implementation_plan
        assert art.name == "plan.md"
        assert art.agent == "planner"
        assert art.model_used == "claude-3-5-sonnet"
        assert art.size_bytes > 0

        art_list = await store.list_artifacts(run.id)
        assert art_list is not None
        assert len(art_list) == 1
        assert art_list[0].id == art.id

        retrieved = await store.get_artifact(run.id, art.id)
        assert retrieved is not None
        out, content = retrieved
        assert out.id == art.id
        assert content == "# Plan\n1. Do something"

    asyncio.run(_test())
