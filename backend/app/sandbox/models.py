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


# ── Container / Browser Sandbox Compatibility Schemas ─────────────────────────

from enum import Enum
from urllib.parse import urlparse
from uuid import UUID
from pydantic import field_validator


class SandboxStatus(str, Enum):
    passed = "passed"
    failed = "failed"
    timed_out = "timed_out"
    diff_rejected = "diff_rejected"
    error = "error"


class SandboxArtifact(BaseModel):
    name: str
    type: str = "screenshot"
    content_type: str = "application/octet-stream"
    size_bytes: int = 0
    data: bytes = b""


class BrowserCheck(BaseModel):
    start_command: List[str] = Field(..., min_length=1)
    url: str
    paths: List[str] = Field(default_factory=lambda: ["/"])
    readiness_timeout_seconds: int = Field(default=15, ge=1, le=120)
    startup_timeout_seconds: int = Field(default=15, ge=1, le=120)
    check_timeout_seconds: int = Field(default=30, ge=1, le=180)
    screenshot: bool = True
    record_video: bool = False

    @field_validator("url")
    @classmethod
    def _validate_url(cls, v: str) -> str:
        parsed = urlparse(v)
        if parsed.username or parsed.password or "@" in (parsed.netloc or ""):
            raise ValueError("URL must not contain userinfo")
        if parsed.hostname not in ("127.0.0.1", "localhost"):
            raise ValueError("URL hostname must be 127.0.0.1 or localhost")
        if parsed.port is None:
            raise ValueError("URL must include an explicit port number")
        if not (1024 <= parsed.port <= 65535):
            raise ValueError("URL port must be between 1024 and 65535")
        return v

    @field_validator("paths")
    @classmethod
    def _validate_paths(cls, v: List[str]) -> List[str]:
        if not (1 <= len(v) <= 5):
            raise ValueError("paths count must be between 1 and 5")
        for p in v:
            if not p.startswith("/"):
                raise ValueError("Each path must be a relative route starting with '/'")
        return v


class BrowserCheckResult(BaseModel):
    ok: bool = False
    error: Optional[str] = None
    http_status: Dict[str, int] = Field(default_factory=dict)
    page_title: Optional[str] = None
    console_errors: List[str] = Field(default_factory=list)
    page_errors: List[str] = Field(default_factory=list)
    failed_requests: List[str] = Field(default_factory=list)
    server_log_tail: Optional[str] = None
    video_supported: bool = False
    duration_seconds: float = 0.0


class SandboxRunRequest(BaseModel):
    run_id: UUID
    repo_archive: bytes
    diff: Optional[str] = None
    setup_command: Optional[List[str]] = None
    test_command: List[str] = Field(..., min_length=1)
    timeout_seconds: Optional[int] = None
    browser: Optional[BrowserCheck] = None


class SandboxRunResult(BaseModel):
    run_id: UUID
    status: SandboxStatus
    exit_code: Optional[int] = None
    diff_applied: bool = False
    log: str = ""
    log_truncated: bool = False
    duration_seconds: float = 0.0
    error: Optional[str] = None
    browser: Optional[BrowserCheckResult] = None
    artifacts: List[SandboxArtifact] = Field(default_factory=list)
