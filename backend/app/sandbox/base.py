"""
Abstract Base Sandbox Manager Protocol.

Defines the contract for creating, executing in, and destroying ephemeral sandboxes.
"""

from __future__ import annotations

import abc
from typing import Optional

from app.sandbox.models import (
    DiffApplyRequest,
    DiffApplyResponse,
    SandboxCreateRequest,
    SandboxCreateResponse,
    TestRunRequest,
    TestRunResponse,
)


class SandboxManager(abc.ABC):
    """Abstract interface for all sandbox backends (Codespaces, Docker, local isolated)."""

    @abc.abstractmethod
    def create_sandbox(self, req: SandboxCreateRequest) -> SandboxCreateResponse:
        """Create an ephemeral sandbox workspace."""
        raise NotImplementedError

    @abc.abstractmethod
    def apply_diff(self, req: DiffApplyRequest) -> DiffApplyResponse:
        """Apply a patch to the sandbox."""
        raise NotImplementedError

    @abc.abstractmethod
    def run_tests(self, req: TestRunRequest) -> TestRunResponse:
        """Execute a verification command inside the sandbox."""
        raise NotImplementedError

    @abc.abstractmethod
    def destroy_sandbox(self, sandbox_id: str) -> bool:
        """Destroy the sandbox workspace idempotently."""
        raise NotImplementedError
