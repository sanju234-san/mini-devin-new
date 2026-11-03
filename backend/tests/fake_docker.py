"""Hand-written fake implementation of the docker-py surface used by Mini-Devin.

Plain-Language Guide for Beginners:
-----------------------------------
Why write a fake Docker client?
1. Tests that require real Docker are slow (spin-up takes seconds) and require
   the developer or CI machine to have Docker installed and running.
2. In-memory fakes execute in milliseconds, run anywhere, and allow us to assert
   EXACT security parameters (like checking that privileged is False, capabilities
   are dropped, and no host paths are mounted).
"""

from __future__ import annotations

import io
import tarfile
import time
from typing import Any


class FakeExecResult:
    """Mock result of container.exec_run."""

    def __init__(self, exit_code: int = 0, output: bytes = b"") -> None:
        self.exit_code = exit_code
        self.output = output


class FakeContainer:
    """Mock Docker container tracking state and API calls."""

    def __init__(self, container_id: str, create_kwargs: dict[str, Any]) -> None:
        self.id = container_id
        self.name = f"fake-container-{container_id[:8]}"
        self.create_kwargs = create_kwargs
        self.labels = create_kwargs.get("labels", {})
        self.started = False
        self.removed = False
        self.killed = False
        self.archives: dict[str, bytes] = {}
        # Configurable responses for simulated commands
        self.custom_exec_responses: dict[str, tuple[int, bytes]] = {}
        self.archive_responses: dict[str, bytes] = {}

    def start(self) -> None:
        self.started = True

    def put_archive(self, path: str, data: bytes) -> bool:
        self.archives[path] = data
        return True

    def get_archive(self, path: str) -> tuple[list[bytes], dict[str, Any]]:
        if path in self.archive_responses:
            data = self.archive_responses[path]
            return [data], {"name": path, "size": len(data)}
        # Return empty tar by default
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w"):
            pass
        return [buf.getvalue()], {"name": path, "size": 0}

    def exec_run(self, cmd: list[str], **kwargs) -> FakeExecResult:
        cmd_str = " ".join(cmd) if isinstance(cmd, list) else str(cmd)
        for prefix, (code, out) in self.custom_exec_responses.items():
            if prefix in cmd_str:
                return FakeExecResult(code, out)
        return FakeExecResult(0, b"All tests passed\n")

    def kill(self) -> None:
        self.killed = True

    def remove(self, force: bool = True) -> None:
        self.removed = True


class FakeDockerApi:
    """Mock Docker low-level client API."""

    def __init__(self, fake_client: FakeDockerClient) -> None:
        self.client = fake_client
        self._next_exec_id = 1
        self._exec_table: dict[str, dict[str, Any]] = {}

    def exec_create(self, container_id: str, cmd: list[str], **kwargs) -> dict[str, str]:
        exec_id = f"exec_{self._next_exec_id}"
        self._next_exec_id += 1
        self._exec_table[exec_id] = {
            "container_id": container_id,
            "cmd": cmd,
            "kwargs": kwargs,
        }
        return {"Id": exec_id}

    def exec_start(self, exec_id: str, stream: bool = True, demux: bool = False):
        info = self._exec_table.get(exec_id, {})
        cid = info.get("container_id", "")
        cmd = info.get("cmd", [])
        cmd_str = " ".join(cmd) if isinstance(cmd, list) else str(cmd)

        container = self.client.containers_dict.get(cid)
        exit_code = 0
        output_bytes = b"Running pytest...\n. [100%]\n1 passed in 0.01s\n"

        if container and container.custom_exec_responses:
            for prefix, (code, out) in container.custom_exec_responses.items():
                if prefix in cmd_str:
                    exit_code = code
                    output_bytes = out
                    break

        info["exit_code"] = exit_code

        # Yield chunks
        chunk_size = 1024
        chunks = [
            output_bytes[i : i + chunk_size]
            for i in range(0, max(len(output_bytes), 1), chunk_size)
        ]
        return iter(chunks)

    def exec_inspect(self, exec_id: str) -> dict[str, Any]:
        info = self._exec_table.get(exec_id, {})
        return {"ExitCode": info.get("exit_code", 0)}


class FakeContainerCollection:
    """Mock client.containers manager."""

    def __init__(self, fake_client: FakeDockerClient) -> None:
        self.client = fake_client

    def create(self, **kwargs) -> FakeContainer:
        cid = f"cont_{len(self.client.containers_dict) + 1}_{int(time.time()*1000)}"
        c = FakeContainer(cid, kwargs)
        c.custom_exec_responses.update(self.client.default_exec_responses)
        self.client.containers_dict[cid] = c
        self.client.created_history.append(c)
        return c

    def get(self, container_id: str) -> FakeContainer:
        if container_id in self.client.containers_dict:
            return self.client.containers_dict[container_id]
        raise KeyError(f"Container {container_id} not found")

    def list(self, all: bool = True, filters: dict[str, Any] | None = None) -> list[FakeContainer]:
        result = []
        label_filter = filters.get("label") if filters else None
        for c in self.client.containers_dict.values():
            if c.removed:
                continue
            if label_filter:
                k, v = label_filter.split("=") if "=" in label_filter else (label_filter, None)
                if k in c.labels and (v is None or c.labels[k] == v):
                    result.append(c)
            else:
                result.append(c)
        return result


class FakeDockerClient:
    """Mock DockerClient mimicking docker-py."""

    def __init__(self, ping_ok: bool = True) -> None:
        self.ping_ok = ping_ok
        self.default_exec_responses: dict[str, tuple[int, bytes]] = {}
        self.containers_dict: dict[str, FakeContainer] = {}
        self.created_history: list[FakeContainer] = []
        self.containers = FakeContainerCollection(self)
        self.api = FakeDockerApi(self)

    def ping(self) -> bool:
        if not self.ping_ok:
            raise ConnectionError("Cannot connect to the Docker daemon")
        return True
