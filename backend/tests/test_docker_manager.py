"""Unit tests for DockerSandboxManager using the in-memory FakeDockerClient."""

from __future__ import annotations

import asyncio
import io
import os
import tarfile
from uuid import uuid4
import pytest

from app.config import Settings
from app.sandbox.base import SandboxUnavailableError
from app.sandbox.docker_manager import DockerSandboxManager
from app.sandbox.models import SandboxRunRequest, SandboxStatus
from tests.fake_docker import FakeDockerClient


def _make_dummy_tar() -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tar:
        data = b"print('hello')\n"
        info = tarfile.TarInfo(name="test_script.py")
        info.size = len(data)
        tar.addfile(info, fileobj=io.BytesIO(data))
    buf.seek(0)
    return buf.getvalue()


@pytest.fixture
def fake_settings() -> Settings:
    return Settings(
        SANDBOX_BACKEND="docker",
        SANDBOX_MEMORY_MB=512,
        SANDBOX_CPUS=1.0,
        SANDBOX_PIDS_LIMIT=128,
        SANDBOX_TIMEOUT_SECONDS=30,
        SANDBOX_MAX_CONCURRENT=2,
        SANDBOX_MAX_LOG_BYTES=1024,
        _env_file=None,
    )


class TestContainerHardening:
    """Verifies that all container hardening flags are set exactly as specified."""

    def test_container_creation_hardening_flags(
        self, fake_settings: Settings, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        async def _run():
            # Inject host secret to prove it never leaks into the container
            monkeypatch.setenv("HOST_SUPER_SECRET_TOKEN", "super-secret-xyz-123")

            fake_client = FakeDockerClient(ping_ok=True)
            manager = DockerSandboxManager(fake_settings, docker_client=fake_client)

            req = SandboxRunRequest(
                run_id=uuid4(),
                repo_archive=_make_dummy_tar(),
                test_command=["python", "test_script.py"],
            )

            res = await manager.run(req)
            assert res.status == SandboxStatus.passed

            # Assert container was created and verify its create arguments
            assert len(fake_client.created_history) == 1
            container = fake_client.created_history[0]
            kwargs = container.create_kwargs

            # 1. Privileges and capabilities
            assert kwargs.get("privileged") is False
            assert kwargs.get("cap_drop") == ["ALL"]
            assert kwargs.get("security_opt") == ["no-new-privileges:true"]

            # 2. User & Init
            assert kwargs.get("user") == "1000:1000"
            assert kwargs.get("init") is True

            # 3. Network disabled
            assert kwargs.get("network_disabled") is True

            # 4. Read-only root filesystem
            assert kwargs.get("read_only") is True

            # 5. tmpfs mounts for /workspace and /tmp
            tmpfs = kwargs.get("tmpfs", {})
            assert "/workspace" in tmpfs
            assert "/tmp" in tmpfs

            # 6. NO bind mounts, NO docker socket
            assert "volumes" not in kwargs or not kwargs["volumes"]
            assert "binds" not in kwargs or not kwargs["binds"]

            # 7. Safe fixed environment (NO host variables, NO secrets)
            env = kwargs.get("environment", {})
            assert "HOST_SUPER_SECRET_TOKEN" not in env
            assert "super-secret-xyz-123" not in str(env)
            assert env.get("HOME") == "/tmp"

            # 8. Resource limits
            assert kwargs.get("mem_limit") == "512m"
            assert kwargs.get("memswap_limit") == "512m"
            assert kwargs.get("nano_cpus") == 1_000_000_000
            assert kwargs.get("pids_limit") == 128

            # 9. Labels
            labels = kwargs.get("labels", {})
            assert labels.get("mini-devin.sandbox") == "true"
            assert labels.get("mini-devin.run_id") == str(req.run_id)
            assert "mini-devin.created_at" in labels

            # 10. Container removed in finally
            assert container.removed is True

        asyncio.run(_run())


class TestStatusMapping:
    """Verifies mapping of execution outcomes to SandboxStatus."""

    def test_successful_run_passed(self, fake_settings: Settings) -> None:
        async def _run():
            fake_client = FakeDockerClient(ping_ok=True)
            manager = DockerSandboxManager(fake_settings, docker_client=fake_client)

            req = SandboxRunRequest(
                run_id=uuid4(),
                repo_archive=_make_dummy_tar(),
                test_command=["python", "test_script.py"],
            )
            res = await manager.run(req)
            assert res.status == SandboxStatus.passed
            assert res.exit_code == 0
            assert res.diff_applied is False

        asyncio.run(_run())

    def test_failing_test_status(self, fake_settings: Settings) -> None:
        async def _run():
            fake_client = FakeDockerClient(ping_ok=True)
            fake_client.default_exec_responses["python test_script.py"] = (
                1,
                b"AssertionError: failed\n",
            )
            manager = DockerSandboxManager(fake_settings, docker_client=fake_client)

            req = SandboxRunRequest(
                run_id=uuid4(),
                repo_archive=_make_dummy_tar(),
                test_command=["python", "test_script.py"],
            )
            res = await manager.run(req)
            assert res.status == SandboxStatus.failed
            assert res.exit_code == 1

        asyncio.run(_run())

    def test_git_apply_failure_diff_rejected(self, fake_settings: Settings) -> None:
        async def _run():
            fake_client = FakeDockerClient(ping_ok=True)
            fake_client.default_exec_responses["git apply --check"] = (
                1,
                b"error: patch failed\n",
            )
            manager = DockerSandboxManager(fake_settings, docker_client=fake_client)

            diff = "diff --git a/foo.py b/foo.py\n--- a/foo.py\n+++ b/foo.py\n@@ -1 +1 @@\n-a\n+b\n"
            req = SandboxRunRequest(
                run_id=uuid4(),
                repo_archive=_make_dummy_tar(),
                diff=diff,
                test_command=["python", "test_script.py"],
            )
            res = await manager.run(req)
            assert res.status == SandboxStatus.diff_rejected
            assert res.diff_applied is False
            assert "Git apply check failed" in (res.error or "")

        asyncio.run(_run())

    def test_timeout_status(self, fake_settings: Settings) -> None:
        async def _run():
            fake_client = FakeDockerClient(ping_ok=True)
            fake_settings.SANDBOX_TIMEOUT_SECONDS = 1
            manager = DockerSandboxManager(fake_settings, docker_client=fake_client)

            async def slow_exec(*args, **kwargs):
                await asyncio.sleep(5)
                return 0, "slow"

            manager._exec_command = slow_exec  # type: ignore

            req = SandboxRunRequest(
                run_id=uuid4(),
                repo_archive=_make_dummy_tar(),
                test_command=["python", "hang.py"],
                timeout_seconds=1,
            )
            res = await manager.run(req)
            assert res.status == SandboxStatus.timed_out
            assert "timed out" in (res.error or "")

        asyncio.run(_run())

    def test_cancellation_cleans_up_container(self, fake_settings: Settings) -> None:
        async def _run():
            fake_client = FakeDockerClient(ping_ok=True)
            manager = DockerSandboxManager(fake_settings, docker_client=fake_client)

            async def hanging_exec(*args, **kwargs):
                await asyncio.sleep(10)
                return 0, ""

            manager._exec_command = hanging_exec  # type: ignore

            req = SandboxRunRequest(
                run_id=uuid4(),
                repo_archive=_make_dummy_tar(),
                test_command=["python", "test.py"],
            )

            task = asyncio.create_task(manager.run(req))
            await asyncio.sleep(0.05)
            task.cancel()

            with pytest.raises(asyncio.CancelledError):
                await task

            assert len(fake_client.created_history) == 1
            assert fake_client.created_history[0].removed is True

        asyncio.run(_run())

    def test_unreachable_docker_raises_sandbox_unavailable(
        self, fake_settings: Settings
    ) -> None:
        async def _run():
            fake_client = FakeDockerClient(ping_ok=False)
            manager = DockerSandboxManager(fake_settings, docker_client=fake_client)
            assert await manager.ping() is False

        asyncio.run(_run())


class TestSourceScanNoHostExecution:
    """Proves that no host execution commands exist anywhere in backend/app/sandbox/."""

    def test_no_host_execution_primitives(self) -> None:
        sandbox_dir = os.path.join(os.path.dirname(__file__), "..", "app", "sandbox")
        forbidden = ["subprocess.", "os.system(", "os.popen(", "shell=True"]

        for root, _, files in os.walk(sandbox_dir):
            for file in files:
                if not file.endswith(".py"):
                    continue
                # browser_check_script.py is allowed because it runs INSIDE the container
                if file == "browser_check_script.py":
                    continue

                filepath = os.path.join(root, file)
                with open(filepath, "r", encoding="utf-8") as f:
                    content = f.read()

                for f_word in forbidden:
                    assert (
                        f_word not in content
                    ), f"Forbidden host execution primitive {f_word!r} found in {file}"
