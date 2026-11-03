"""
Abstract Base Sandbox Manager Protocol.

Defines the contract for creating, executing in, and destroying ephemeral sandboxes.
"""

from __future__ import annotations

import abc
from collections.abc import Awaitable, Callable
from typing import Any, Optional

from app.sandbox.models import (
    DiffApplyRequest,
    DiffApplyResponse,
    SandboxCreateRequest,
    SandboxCreateResponse,
    SandboxUnavailableError,
    TestRunRequest,
    TestRunResponse,
)

OutputCallback = Callable[[str, str], Awaitable[None]]

_ACTIVE_SANDBOX_MANAGER: Any = None


def set_active_sandbox_manager(manager: Any) -> None:
    """Set the active sandbox manager registered during FastAPI lifespan."""
    global _ACTIVE_SANDBOX_MANAGER
    _ACTIVE_SANDBOX_MANAGER = manager


def get_sandbox_manager() -> Any:
    """Return the active lifespan sandbox manager, or raise SandboxUnavailableError."""
    if _ACTIVE_SANDBOX_MANAGER is None:
        raise SandboxUnavailableError("No active sandbox manager registered.")
    return _ACTIVE_SANDBOX_MANAGER


class SandboxManager(abc.ABC):
    """Abstract interface for all sandbox backends (Codespaces, Docker, local isolated)."""

    def create_sandbox(self, req: SandboxCreateRequest) -> SandboxCreateResponse:
        """Create an ephemeral sandbox workspace."""
        raise NotImplementedError

    def apply_diff(self, req: DiffApplyRequest) -> DiffApplyResponse:
        """Apply a patch to the sandbox."""
        raise NotImplementedError

    def run_tests(self, req: TestRunRequest) -> TestRunResponse:
        """Execute a verification command inside the sandbox."""
        raise NotImplementedError

    def destroy_sandbox(self, sandbox_id: str) -> bool:
        """Destroy the sandbox workspace idempotently."""
        raise NotImplementedError
