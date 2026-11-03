"""Docker sandbox manager: executes untrusted code in ephemeral, hardened containers.

Plain-Language Guide for Beginners:
-----------------------------------
What is a container?
A container is a lightweight, isolated execution environment running on the Linux kernel.
Unlike a full Virtual Machine (which virtualizes hardware and runs a whole separate operating
system), a container shares the host kernel but runs in isolated namespaces (separate file
system, process table, network stack, and user accounts).

What is hardening?
"Hardening" means turning off all unnecessary privileges so that even if the code running
inside the container is malicious or contains an exploit, it cannot break out onto the host
machine or access internal network services.

Hardening Measures Applied in this Manager:
1. `privileged=False`: The container cannot access host hardware devices or reconfigure the kernel.
2. `cap_drop=["ALL"]`: Linux "capabilities" are discrete superpowers (like raw socket creation
   or rebooting). We drop ALL of them.
3. `security_opt=["no-new-privileges:true"]`: Prevents processes inside from gaining more
   privileges via setuid binaries.
4. `read_only=True`: The container root filesystem is 100% read-only.
5. `tmpfs`: Writable temporary space is strictly confined to in-memory tmpfs mounts (/workspace, /tmp)
   with size limits.
6. `network_disabled=True`: Network mode 'none'. The container has no network interface other
   than localhost (lo). It cannot access the internet, cloud metadata endpoints, or the local LAN.
7. `user="1000:1000"`: Runs as an unprivileged user ("sandbox"), never root.
8. NO bind mounts: The host filesystem and Docker socket (/var/run/docker.sock) are NEVER mounted.
9. Sanitized environment: Host environment variables and secrets are NEVER passed to the container.
10. Strict limits: Memory, CPU, and PIDs are bounded.
11. Lifespan guarantee: Containers are ephemeral (per-run) and destroyed in `finally` blocks
    under all circumstances (success, test failure, timeout, cancellation, or shutdown).
"""

from __future__ import annotations

import asyncio
import contextlib
import io
import logging
import os
import tarfile
import time
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from app.sandbox.base import (
    OutputCallback,
    SandboxManager,
    SandboxUnavailableError,
    set_active_sandbox_manager,
)
from app.sandbox.models import (
    SandboxArtifact,
    SandboxRunRequest,
    SandboxRunResult,
    SandboxStatus,
)
from app.sandbox.safety import (
    normalize_repo_archive,
    truncate_text,
    validate_diff,
)

if TYPE_CHECKING:
    from fastapi import FastAPI
    from app.config import Settings

logger = logging.getLogger(__name__)


def _create_tar_with_file(filename: str, content: bytes, mode: int = 0o644) -> bytes:
    """Helper to create an in-memory tarball containing a single file."""
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tar:
        info = tarfile.TarInfo(name=filename)
        info.size = len(content)
        info.mtime = int(time.time())
        info.mode = mode
        info.uid = 1000
        info.gid = 1000
        info.uname = "sandbox"
        info.gname = "sandbox"
        tar.addfile(info, fileobj=io.BytesIO(content))
    buf.seek(0)
    return buf.getvalue()


class DockerSandboxManager(SandboxManager):
    """Manages ephemeral, hardened Docker containers for testing untrusted code."""

    def __init__(self, settings: Settings, docker_client: Any = None) -> None:
        self.settings = settings
        self._semaphore = asyncio.Semaphore(settings.SANDBOX_MAX_CONCURRENT)
        self._active_containers: set[str] = set()
        self._client = docker_client

    def _get_client(self) -> Any:
        """Return the active docker-py client or create one from environment."""
        if self._client is not None:
            return self._client
        try:
            import docker

            self._client = docker.from_env()
            return self._client
        except Exception as exc:
            raise SandboxUnavailableError(
                f"Docker daemon unreachable or docker-py not installed: {exc}"
            ) from exc

    async def ping(self) -> bool:
        """Check if the Docker daemon is responsive."""
        try:
            client = self._get_client()
            return await asyncio.to_thread(client.ping)
        except Exception as exc:
            logger.warning("Docker ping failed: %s", exc)
            return False

    async def destroy_all(self) -> None:
        """Forcefully kill and remove all tracked active sandbox containers."""
        try:
            client = self._get_client()
        except Exception:
            self._active_containers.clear()
            return

        container_ids = list(self._active_containers)
        for cid in container_ids:
            try:
                container = await asyncio.to_thread(client.containers.get, cid)
                await asyncio.to_thread(container.remove, force=True)
                logger.info("Destroyed sandbox container %s", cid[:12])
            except Exception as exc:
                logger.warning("Failed to remove container %s during destroy_all: %s", cid[:12], exc)
            finally:
                self._active_containers.discard(cid)

    async def _cleanup_container(self, container_id: str) -> None:
        """Safely kill and remove a single container in a background thread."""
        try:
            client = self._get_client()
            container = await asyncio.to_thread(client.containers.get, container_id)
            await asyncio.to_thread(container.remove, force=True)
            logger.debug("Removed container %s", container_id[:12])
        except Exception as exc:
            logger.warning("Error removing container %s: %s", container_id[:12], exc)
        finally:
            self._active_containers.discard(container_id)

    async def _exec_command(
        self,
        container: Any,
        cmd: list[str],
        workdir: str = "/workspace",
        on_output: OutputCallback | None = None,
    ) -> tuple[int, str]:
        """Execute a command inside the container and stream/collect output.

        Returns:
            tuple[int, str]: (exit_code, combined_output)
        """
        client = self._get_client()

        # Execute via low-level API to capture both streaming and exit code safely
        def _start_exec():
            exec_obj = client.api.exec_create(
                container.id,
                cmd,
                workdir=workdir,
                user="1000:1000",
                environment={"HOME": "/tmp", "PATH": "/usr/local/bin:/usr/bin:/bin"},
            )
            return exec_obj["Id"]

        exec_id = await asyncio.to_thread(_start_exec)

        def _stream_output():
            # Returns generator yielding output chunks (demux=False yields combined bytes)
            return client.api.exec_start(exec_id, stream=True, demux=False)

        stream = await asyncio.to_thread(_stream_output)
        collected_chunks: list[str] = []

        def _read_chunk():
            try:
                return next(stream)
            except StopIteration:
                return None

        while True:
            chunk = await asyncio.to_thread(_read_chunk)
            if chunk is None:
                break
            text = chunk.decode("utf-8", errors="replace")
            collected_chunks.append(text)
            if on_output:
                try:
                    await on_output("stdout", text)
                except Exception as cb_exc:
                    logger.debug("Error in on_output callback: %s", cb_exc)

        def _get_exit_code():
            info = client.api.exec_inspect(exec_id)
            return info.get("ExitCode", 1)

        exit_code = await asyncio.to_thread(_get_exit_code)
        return exit_code, "".join(collected_chunks)

    async def run(
        self,
        request: SandboxRunRequest,
        on_output: OutputCallback | None = None,
    ) -> SandboxRunResult:
        """Execute a complete test run inside an ephemeral, hardened container."""
        start_time = time.monotonic()

        # Step 1: Pre-validation of diff and archive before creating container
        try:
            validate_diff(request.diff)
        except ValueError as exc:
            return SandboxRunResult(
                run_id=request.run_id,
                status=SandboxStatus.diff_rejected,
                diff_applied=False,
                error=f"Diff validation rejected: {exc}",
                duration_seconds=round(time.monotonic() - start_time, 3),
            )

        try:
            normalized_tar = normalize_repo_archive(
                request.repo_archive, self.settings.SANDBOX_MAX_ARCHIVE_MB
            )
        except ValueError as exc:
            return SandboxRunResult(
                run_id=request.run_id,
                status=SandboxStatus.diff_rejected,
                diff_applied=False,
                error=f"Repository archive rejected: {exc}",
                duration_seconds=round(time.monotonic() - start_time, 3),
            )

        # Step 2: Acquire concurrency semaphore
        async with self._semaphore:
            container_id: str | None = None
            log_chunks: list[str] = []
            diff_applied = False
            browser_result = None
            artifacts: list[SandboxArtifact] = []

            # Determine container image and resources
            image_name = (
                self.settings.SANDBOX_BROWSER_IMAGE
                if request.browser is not None
                else self.settings.SANDBOX_IMAGE
            )

            # Enforce overall run deadline: min(request.timeout_seconds, SANDBOX_TIMEOUT_SECONDS)
            effective_timeout = (
                min(request.timeout_seconds, self.settings.SANDBOX_TIMEOUT_SECONDS)
                if request.timeout_seconds
                else self.settings.SANDBOX_TIMEOUT_SECONDS
            )

            try:
                client = self._get_client()

                # Step 3: Define hardened container parameters (Section 4.3)
                # Read-only rootfs + tmpfs for /workspace and /tmp
                tmpfs_config = {
                    "/workspace": f"size={self.settings.SANDBOX_MEMORY_MB}m,mode=1777,uid=1000,gid=1000",
                    "/tmp": "size=128m,mode=1777,uid=1000,gid=1000",
                }

                # Safe fixed environment (NO host variables, NO secrets)
                fixed_env = {
                    "HOME": "/tmp",
                    "PATH": "/usr/local/bin:/usr/bin:/bin",
                    "PYTHONUNBUFFERED": "1",
                }

                container_kwargs: dict[str, Any] = {
                    "image": image_name,
                    "command": ["tail", "-f", "/dev/null"],
                    "detach": True,
                    "privileged": False,
                    "cap_drop": ["ALL"],
                    "security_opt": ["no-new-privileges:true"],
                    "user": "1000:1000",
                    "init": True,
                    "network_disabled": True,
                    "read_only": True,
                    "tmpfs": tmpfs_config,
                    "environment": fixed_env,
                    "mem_limit": f"{self.settings.SANDBOX_MEMORY_MB}m",
                    "memswap_limit": f"{self.settings.SANDBOX_MEMORY_MB}m",
                    "nano_cpus": int(self.settings.SANDBOX_CPUS * 1_000_000_000),
                    "pids_limit": self.settings.SANDBOX_PIDS_LIMIT,
                    "ulimits": [{"name": "nofile", "soft": 1024, "hard": 2048}],
                    "labels": {
                        "mini-devin.sandbox": "true",
                        "mini-devin.run_id": str(request.run_id),
                        "mini-devin.created_at": datetime.now(timezone.utc).isoformat(),
                    },
                }

                if request.browser is not None:
                    container_kwargs["shm_size"] = "256m"

                # Step 4: Create and start container under deadline
                async with asyncio.timeout(effective_timeout):
                    container = await asyncio.to_thread(
                        client.containers.create, **container_kwargs
                    )
                    container_id = container.id
                    self._active_containers.add(container_id)

                    await asyncio.to_thread(container.start)

                    # Step 5: Upload normalized repo archive to /workspace
                    await asyncio.to_thread(
                        container.put_archive, "/workspace", normalized_tar
                    )

                    # Step 6: Apply diff if present
                    if request.diff:
                        diff_tar = _create_tar_with_file("patch.diff", request.diff.encode("utf-8"))
                        await asyncio.to_thread(container.put_archive, "/tmp", diff_tar)

                        # Dry-run check: git apply --check /tmp/patch.diff
                        check_code, check_out = await self._exec_command(
                            container,
                            ["git", "apply", "--check", "/tmp/patch.diff"],
                            workdir="/workspace",
                            on_output=on_output,
                        )
                        log_chunks.append(check_out)

                        if check_code != 0:
                            truncated_log, is_trunc = truncate_text(
                                check_out, self.settings.SANDBOX_MAX_LOG_BYTES
                            )
                            return SandboxRunResult(
                                run_id=request.run_id,
                                status=SandboxStatus.diff_rejected,
                                exit_code=check_code,
                                diff_applied=False,
                                log=truncated_log,
                                log_truncated=is_trunc,
                                duration_seconds=round(time.monotonic() - start_time, 3),
                                error="Git apply check failed: patch could not be applied cleanly",
                            )

                        # Real apply: git apply /tmp/patch.diff
                        apply_code, apply_out = await self._exec_command(
                            container,
                            ["git", "apply", "/tmp/patch.diff"],
                            workdir="/workspace",
                            on_output=on_output,
                        )
                        log_chunks.append(apply_out)

                        if apply_code != 0:
                            truncated_log, is_trunc = truncate_text(
                                apply_out, self.settings.SANDBOX_MAX_LOG_BYTES
                            )
                            return SandboxRunResult(
                                run_id=request.run_id,
                                status=SandboxStatus.diff_rejected,
                                exit_code=apply_code,
                                diff_applied=False,
                                log=truncated_log,
                                log_truncated=is_trunc,
                                duration_seconds=round(time.monotonic() - start_time, 3),
                                error="Git apply failed",
                            )

                        diff_applied = True

                    # Step 7: Optional setup command
                    if request.setup_command:
                        _, setup_out = await self._exec_command(
                            container,
                            request.setup_command,
                            workdir="/workspace",
                            on_output=on_output,
                        )
                        log_chunks.append(setup_out)

                    # Step 8: Execute test command
                    test_code, test_out = await self._exec_command(
                        container,
                        request.test_command,
                        workdir="/workspace",
                        on_output=on_output,
                    )
                    log_chunks.append(test_out)

                    # Step 9: Phase B Live Browser Check (if requested)
                    if request.browser is not None:
                        from app.sandbox.playwright_runner import run_browser_check

                        b_res, b_artifacts = await run_browser_check(
                            container=container,
                            check=request.browser,
                            client=client,
                        )
                        browser_result = b_res
                        artifacts.extend(b_artifacts)

                    # Format logs and results
                    full_log = "".join(log_chunks)
                    truncated_log, is_trunc = truncate_text(
                        full_log, self.settings.SANDBOX_MAX_LOG_BYTES
                    )
                    status = SandboxStatus.passed if test_code == 0 else SandboxStatus.failed

                    return SandboxRunResult(
                        run_id=request.run_id,
                        status=status,
                        exit_code=test_code,
                        diff_applied=diff_applied,
                        log=truncated_log,
                        log_truncated=is_trunc,
                        duration_seconds=round(time.monotonic() - start_time, 3),
                        error=None,
                        browser=browser_result,
                        artifacts=artifacts,
                    )

            except (TimeoutError, asyncio.TimeoutError):
                full_log = "".join(log_chunks)
                truncated_log, is_trunc = truncate_text(
                    full_log, self.settings.SANDBOX_MAX_LOG_BYTES
                )
                return SandboxRunResult(
                    run_id=request.run_id,
                    status=SandboxStatus.timed_out,
                    exit_code=None,
                    diff_applied=diff_applied,
                    log=truncated_log,
                    log_truncated=is_trunc,
                    duration_seconds=round(time.monotonic() - start_time, 3),
                    error=f"Execution timed out after {effective_timeout} seconds",
                    browser=browser_result,
                    artifacts=artifacts,
                )

            except SandboxUnavailableError:
                raise

            except Exception as exc:
                logger.error("Sandbox run %s encountered an error: %s", request.run_id, exc)
                return SandboxRunResult(
                    run_id=request.run_id,
                    status=SandboxStatus.error,
                    exit_code=None,
                    diff_applied=diff_applied,
                    log="".join(log_chunks),
                    log_truncated=False,
                    duration_seconds=round(time.monotonic() - start_time, 3),
                    error="Sandbox execution failed due to an internal container error",
                )

            finally:
                # The container must NEVER outlive its run: cleanup always executes
                if container_id is not None:
                    await self._cleanup_container(container_id)


# ── Lifespan Resource Hook ────────────────────────────────────────────────────

@contextlib.asynccontextmanager
async def lifespan_resource(app: FastAPI) -> AsyncIterator[None]:
    """FastAPI async lifespan resource manager for the Docker sandbox.

    On Startup:
    1. Instantiates DockerSandboxManager from settings.
    2. Pings Docker daemon; if unreachable, raises SandboxUnavailableError so
       main.py records 'app.sandbox.docker_manager' in app.state.failed_hooks.
    3. Cleans up any orphaned containers carrying the 'mini-devin.sandbox=true' label.
    4. Sets app.state.sandbox_manager and the module-level reference for get_sandbox_manager().

    On Shutdown (finally):
    1. Forcefully destroys any active containers.
    2. Clears app.state.sandbox_manager and the module-level reference.
    """
    settings = app.state.settings
    manager = DockerSandboxManager(settings)

    # Health-check Docker connection
    is_alive = await manager.ping()
    if not is_alive:
        raise SandboxUnavailableError("Docker daemon is unreachable at startup")

    # Clean up orphaned containers from previous crashed server runs
    try:
        client = manager._get_client()

        def _clean_orphans():
            orphans = client.containers.list(
                all=True, filters={"label": "mini-devin.sandbox=true"}
            )
            for c in orphans:
                try:
                    c.remove(force=True)
                    logger.info("Cleaned up orphaned sandbox container %s", c.id[:12])
                except Exception as orphan_err:
                    logger.debug("Error removing orphan %s: %s", c.id[:12], orphan_err)

        await asyncio.to_thread(_clean_orphans)
    except Exception as orphan_exc:
        logger.warning("Could not sweep orphaned containers: %s", orphan_exc)

    # Register manager for app and get_sandbox_manager()
    app.state.sandbox_manager = manager
    set_active_sandbox_manager(manager)

    try:
        yield
    finally:
        await manager.destroy_all()
        set_active_sandbox_manager(None)
        app.state.sandbox_manager = None
