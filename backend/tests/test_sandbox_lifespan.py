"""Unit tests for sandbox lifespan hook and orphan container cleanup."""

from __future__ import annotations

import asyncio
from unittest.mock import patch
import pytest
from httpx import ASGITransport, AsyncClient

from app.config import Settings
from app.main import create_app
from app.sandbox.base import (
    SandboxUnavailableError,
    get_sandbox_manager,
    set_active_sandbox_manager,
)
from app.sandbox.docker_manager import lifespan_resource
from tests.fake_docker import FakeContainer, FakeDockerClient


@pytest.fixture(autouse=True)
def clean_sandbox_manager() -> None:
    set_active_sandbox_manager(None)
    yield
    set_active_sandbox_manager(None)


def test_lifespan_startup_and_shutdown() -> None:
    async def _run():
        fake_client = FakeDockerClient(ping_ok=True)

        # Seed an orphan container
        orphan = FakeContainer(
            "orphan_999",
            {"labels": {"mini-devin.sandbox": "true"}},
        )
        fake_client.containers_dict[orphan.id] = orphan

        settings = Settings(
            SANDBOX_BACKEND="docker",
            _env_file=None,
        )
        app = create_app(settings)

        # Patch DockerClient creation
        with patch(
            "app.sandbox.docker_manager.DockerSandboxManager._get_client",
            return_value=fake_client,
        ):
            async with lifespan_resource(app):
                # Assert orphan was cleaned up
                assert orphan.removed is True

                # Assert manager registered
                assert app.state.sandbox_manager is not None
                assert get_sandbox_manager() is app.state.sandbox_manager

            # After shutdown
            assert app.state.sandbox_manager is None
            with pytest.raises(SandboxUnavailableError):
                get_sandbox_manager()

    asyncio.run(_run())


from fastapi.testclient import TestClient


def test_docker_unreachable_recorded_in_failed_hooks() -> None:
    fake_client = FakeDockerClient(ping_ok=False)

    settings = Settings(
        SANDBOX_BACKEND="docker",
        _env_file=None,
    )
    app = create_app(settings)

    with patch(
        "app.sandbox.docker_manager.DockerSandboxManager._get_client",
        return_value=fake_client,
    ):
        with TestClient(app) as client:
            resp = client.get("/health")
            assert resp.status_code == 200
            assert resp.json() == {"status": "ok"}

            # Lifespan should have recorded the failure in failed_hooks without crashing
            assert "app.sandbox.docker_manager" in app.state.failed_hooks

