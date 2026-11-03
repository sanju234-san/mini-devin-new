"""Integration tests against a real Docker daemon (opt-in via RUN_DOCKER_TESTS=1).

Plain-Language Guide for Beginners:
-----------------------------------
These tests run against a REAL Docker engine. Because not all development or CI
environments have Docker installed (for instance, on Render web services), these tests
are automatically skipped unless:
1. Docker daemon is reachable and responding.
2. The environment variable RUN_DOCKER_TESTS=1 is set.
"""

from __future__ import annotations

import io
import os
import tarfile
from uuid import uuid4
import pytest

from app.config import Settings
from app.sandbox.docker_manager import DockerSandboxManager
from app.sandbox.models import (
    BrowserCheck,
    SandboxRunRequest,
    SandboxStatus,
)


def _docker_is_available() -> bool:
    if os.environ.get("RUN_DOCKER_TESTS") != "1":
        return False
    try:
        import docker

        client = docker.from_env()
        return bool(client.ping())
    except Exception:
        return False


def _browser_tests_enabled() -> bool:
    if os.environ.get("RUN_BROWSER_TESTS") != "1":
        return False
    return _docker_is_available()


skip_unless_docker = pytest.mark.skipif(
    not _docker_is_available(),
    reason="Requires active Docker daemon and RUN_DOCKER_TESTS=1",
)

skip_unless_browser = pytest.mark.skipif(
    not _browser_tests_enabled(),
    reason="Requires active Docker daemon and RUN_BROWSER_TESTS=1",
)


def _make_repo_tar(files: dict[str, str]) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tar:
        for name, text in files.items():
            data = text.encode("utf-8")
            info = tarfile.TarInfo(name=name)
            info.size = len(data)
            tar.addfile(info, fileobj=io.BytesIO(data))
    buf.seek(0)
    return buf.getvalue()


@pytest.fixture
def real_settings() -> Settings:
    return Settings(
        SANDBOX_BACKEND="docker",
        SANDBOX_MEMORY_MB=512,
        SANDBOX_CPUS=1.0,
        SANDBOX_PIDS_LIMIT=64,
        SANDBOX_TIMEOUT_SECONDS=15,
        _env_file=None,
    )


@skip_unless_docker
class TestRealDockerSandbox:
    """End-to-end integration tests using real ephemeral Docker containers."""

    def test_simple_python_execution(self, real_settings: Settings) -> None:
        async def _run():
            manager = DockerSandboxManager(real_settings)
            repo = _make_repo_tar({"main.py": "print('INTEGRATION_PASSED')\n"})

            req = SandboxRunRequest(
                run_id=uuid4(),
                repo_archive=repo,
                test_command=["python", "main.py"],
            )

            res = await manager.run(req)
            assert res.status == SandboxStatus.passed
            assert res.exit_code == 0
            assert "INTEGRATION_PASSED" in res.log

        import asyncio
        asyncio.run(_run())

    def test_network_isolation_fails_external_socket(
        self, real_settings: Settings
    ) -> None:
        """Asserts that network_disabled=True prevents connecting to external internet."""
        async def _run():
            manager = DockerSandboxManager(real_settings)
            # Attempt connection to public DNS 1.1.1.1
            script = (
                "import socket, sys\n"
                "try:\n"
                "    s = socket.create_connection(('1.1.1.1', 53), timeout=1)\n"
                "    sys.exit(0)\n"
                "except Exception:\n"
                "    sys.exit(42)\n"
            )
            repo = _make_repo_tar({"test_net.py": script})

            req = SandboxRunRequest(
                run_id=uuid4(),
                repo_archive=repo,
                test_command=["python", "test_net.py"],
            )

            res = await manager.run(req)
            # Exit code 42 indicates connection failed as expected
            assert res.exit_code == 42
            assert res.status == SandboxStatus.failed

        import asyncio
        asyncio.run(_run())

    def test_infinite_loop_times_out_and_cleans_up(
        self, real_settings: Settings
    ) -> None:
        """Verifies watchdog timeout kills the container."""
        async def _run():
            manager = DockerSandboxManager(real_settings)
            script = "import time\nwhile True: time.sleep(0.1)\n"
            repo = _make_repo_tar({"hang.py": script})

            req = SandboxRunRequest(
                run_id=uuid4(),
                repo_archive=repo,
                test_command=["python", "hang.py"],
                timeout_seconds=3,
            )

            res = await manager.run(req)
            assert res.status == SandboxStatus.timed_out

        import asyncio
        asyncio.run(_run())


@skip_unless_browser
class TestRealBrowserVerification:
    """Live Playwright browser tests over CDP inside the sandbox."""

    def test_http_server_and_screenshot(self, real_settings: Settings) -> None:
        async def _run():
            manager = DockerSandboxManager(real_settings)
            html = "<html><head><title>Mini-Devin Test Page</title></head><body><h1>Hello World</h1></body></html>"
            repo = _make_repo_tar({"index.html": html})

            req = SandboxRunRequest(
                run_id=uuid4(),
                repo_archive=repo,
                test_command=["python", "-c", "print('Ready')"],
                browser=BrowserCheck(
                    start_command=["python", "-m", "http.server", "8088"],
                    url="http://127.0.0.1:8088",
                    paths=["/index.html"],
                    screenshot=True,
                ),
            )

            res = await manager.run(req)
            assert res.browser is not None
            assert res.browser.ok is True
            assert res.browser.page_title == "Mini-Devin Test Page"
            assert len(res.artifacts) >= 1
            assert res.artifacts[0].name.startswith("screenshot_")

        import asyncio
        asyncio.run(_run())
