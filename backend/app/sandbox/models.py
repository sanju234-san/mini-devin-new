"""
Pydantic schemas and models for the Mini-Devin Sandbox interface.

Conforms strictly to docs/design/sandbox-and-github-contract.md.
"""

from __future__ import annotations

from typing import Dict, List, Optional
from pydantic import BaseModel, Field

# 1 MB size cap for captured stdout / stderr
MAX_OUTPUT_BYTES: int = 1024 * 1024


class SandboxCreateRequest(BaseModel):
    """Request to create an isolated sandbox environment."""
    repo_ref: str = Field(..., description="Repository reference, e.g. 'owner/repo@sha' or branch.")
    timeout_seconds: int = Field(default=300, ge=10, le=1800, description="Maximum lifetime of sandbox.")
    env_vars: Dict[str, str] = Field(default_factory=dict, description="Whitelisted non-secret environment variables.")


class SandboxCreateResponse(BaseModel):
    """Response returned upon sandbox creation."""
    sandbox_id: str = Field(..., description="Unique opaque identifier for the created sandbox.")
    status: str = Field(default="ready", description="Sandbox readiness status.")
    workspace_ref: str = Field(..., description="Opaque reference to the workspace (host paths forbidden).")


class DiffApplyRequest(BaseModel):
    """Request to apply a unified diff to the sandbox workspace."""
    sandbox_id: str = Field(..., description="Target sandbox identifier.")
    diff_text: str = Field(..., description="Unified diff text to apply.")


class DiffApplyResponse(BaseModel):
    """Response returned after diff application."""
    success: bool
    error: Optional[str] = None
    applied_files: List[str] = Field(default_factory=list)


class TestRunRequest(BaseModel):
    """Request to execute a verification command inside the sandbox."""
    __test__ = False
    sandbox_id: str = Field(..., description="Target sandbox identifier.")
    argv: List[str] = Field(..., min_length=1, description="Command argument vector to prevent shell injection.")
    cwd: str = Field(default="/workspace", description="Working directory inside sandbox.")
    timeout_seconds: int = Field(default=60, ge=1, le=600, description="Execution timeout.")


class TestRunResponse(BaseModel):
    """Execution results returned from a sandbox test run."""
    __test__ = False
    exit_code: int = Field(..., description="Process exit code.")
    stdout: str = Field(default="", description="Captured standard output (capped at 1MB).")
    stderr: str = Field(default="", description="Captured standard error (capped at 1MB).")
    duration_ms: int = Field(default=0, ge=0, description="Execution duration in milliseconds.")
    timed_out: bool = Field(default=False, description="Whether command exceeded timeout.")
    artifacts: List[str] = Field(default_factory=list, description="Opaque artifact reference IDs.")


class SandboxError(Exception):
    """Base exception for sandbox operations."""
    pass


class SandboxUnavailableError(SandboxError):
    pass


class HostExecutionBlockedError(SandboxUnavailableError):
    """Raised when execution of untrusted commands on the host is blocked by security policy."""
    pass


class DiffApplyFailedError(SandboxError):
    pass


class TimeoutError(SandboxError):
    pass


class InvalidRequestError(SandboxError):
    pass
