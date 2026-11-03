"""
Unified Issue Intake Service for Chainlit and API endpoints.

Handles:
1. Strict validation of GitHub issue URLs (rejects PR URLs and malformed links).
2. Fetching real issue data through the GitHub MCP client without synthesizing fake text.
3. Untrusted input sanitization through existing input guardrails.
4. Bounded repository snapshot creation for Retrieval.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field

from app.guardrails.input_guardrails import validate_and_sanitize_issue
from app.integrations.mcp_client import (
    GitHubMCPClient,
    MCPClientError,
    MCPRateLimitError,
    MCPResourceNotFoundError,
    MCPTimeoutError,
    get_github_mcp_client,
)
from app.integrations.repo_snapshot import RepositorySnapshotService

logger = logging.getLogger("mini_devin.integrations.intake")

# Strict regex matching only standard GitHub issue URLs
_GITHUB_ISSUE_RE = re.compile(
    r"^https?://github\.com/(?P<owner>[a-zA-Z0-9_.-]+)/(?P<repo>[a-zA-Z0-9_.-]+)/issues/(?P<number>\d+)/?$",
    re.IGNORECASE,
)

_GITHUB_PR_RE = re.compile(
    r"^https?://github\.com/(?P<owner>[a-zA-Z0-9_.-]+)/(?P<repo>[a-zA-Z0-9_.-]+)/pull/(?P<number>\d+)/?$",
    re.IGNORECASE,
)


class IssueIntakeResult(BaseModel):
    """Normalized, validated, and sanitized issue intake result."""
    repo: str
    owner: str
    repo_name: str
    issue_title: str
    issue_body: str
    issue_url: Optional[str] = None
    issue_number: Optional[int] = None
    repo_ref: Optional[str] = None
    commit_sha: Optional[str] = None
    snapshot_path: Optional[str] = None
    snapshot_truncated: bool = False
    snapshot_truncation_reason: Optional[str] = None
    issue_metadata: Optional[Dict[str, Any]] = None
    is_suspicious: bool = False
    guardrail_warnings: List[str] = Field(default_factory=list)


async def process_issue_intake(
    user_input: str,
    mcp_client: Optional[GitHubMCPClient] = None,
    create_snapshot: bool = True,
    allow_shallow_clone_fallback: bool = True,
) -> IssueIntakeResult:
    """
    Process, validate, and fetch issue data.
    
    Raises:
        ValueError: If input is empty, is a PR URL, or is a malformed GitHub URL.
        MCPResourceNotFoundError: If the remote issue does not exist (404).
        MCPRateLimitError: If GitHub rate limits are triggered.
        MCPTimeoutError: If the MCP operation timed out.
        MCPClientError: For general MCP fetch failures.
    """
    raw = (user_input or "").strip()
    if not raw:
        raise ValueError("Issue input cannot be empty.")

    # ── Check for PR URLs or non-issue links ──────────────────────────────────
    if _GITHUB_PR_RE.match(raw) or ("/pull/" in raw and "github.com" in raw):
        raise ValueError(
            "Pull Request URLs are not accepted. Mini-Devin intake requires a GitHub Issue URL "
            "(e.g. 'https://github.com/owner/repo/issues/123')."
        )

    # ── 1. GitHub Issue URL Path ─────────────────────────────────────────────
    issue_match = _GITHUB_ISSUE_RE.match(raw)
    if issue_match:
        owner = issue_match.group("owner")
        repo_name = issue_match.group("repo")
        issue_number = int(issue_match.group("number"))
        repo_slug = f"{owner}/{repo_name}"

        client = mcp_client or get_github_mcp_client()

        # Fetch authentic issue details through genuine MCP client
        logger.info("Fetching real issue details for %s#%d via GitHub MCP...", repo_slug, issue_number)
        issue_data = await client.get_issue(owner=owner, repo=repo_name, issue_number=issue_number)

        raw_title = issue_data.get("title", "")
        raw_body = issue_data.get("body") or ""

        # Enforce input guardrails on real fetched content
        clean_title, clean_body, warnings, is_suspicious = validate_and_sanitize_issue(
            raw_title, raw_body
        )

        labels = [l.get("name", "") for l in issue_data.get("labels", []) if isinstance(l, dict)]
        issue_meta = {
            "state": issue_data.get("state", "open"),
            "labels": labels,
            "author": issue_data.get("user", {}).get("login") if isinstance(issue_data.get("user"), dict) else "unknown",
            "created_at": issue_data.get("created_at"),
            "html_url": issue_data.get("html_url", raw),
        }

        # Resolve default branch dynamically (e.g. main, master, develop)
        default_ref = "main"
        try:
            from app.integrations.github_client import GitRef, get_github_client
            default_ref = get_github_client().fetch_repo(GitRef(owner=owner, repo=repo_name)).rsplit("@", 1)[-1]
        except Exception:
            pass

        # Snapshot resolution
        snapshot_path_str: Optional[str] = None
        commit_sha: Optional[str] = None
        snapshot_truncated: bool = False
        snapshot_truncation_reason: Optional[str] = None
        if create_snapshot:
            snapshot_service = RepositorySnapshotService(mcp_client=client)
            try:
                snapshot_dir = await snapshot_service.create_snapshot(
                    owner=owner,
                    repo=repo_name,
                    ref=default_ref,
                    allow_shallow_clone_fallback=allow_shallow_clone_fallback,
                )
                snapshot_path_str = str(snapshot_dir)
                meta_file = snapshot_dir / "snapshot_metadata.json"
                if meta_file.is_file():
                    meta = json.loads(meta_file.read_text(encoding="utf-8"))
                    commit_sha = meta.get("commit_sha")
                    snapshot_truncated = bool(meta.get("is_truncated", False))
                    snapshot_truncation_reason = meta.get("truncation_reason")
                    if snapshot_truncated:
                        logger.warning(
                            "WARNING: Snapshot for %s was TRUNCATED (%s). Planning will see a partial view.",
                            repo_slug, snapshot_truncation_reason,
                        )
            except Exception as e:
                logger.warning("Could not build repository snapshot for %s: %s", repo_slug, e)

        return IssueIntakeResult(
            repo=repo_slug,
            owner=owner,
            repo_name=repo_name,
            issue_title=clean_title,
            issue_body=clean_body,
            issue_url=raw,
            issue_number=issue_number,
            repo_ref=default_ref,
            commit_sha=commit_sha,
            snapshot_path=snapshot_path_str,
            snapshot_truncated=snapshot_truncated,
            snapshot_truncation_reason=snapshot_truncation_reason,
            issue_metadata=issue_meta,
            is_suspicious=is_suspicious,
            guardrail_warnings=warnings,
        )

    # ── Check for malformed GitHub URLs ──────────────────────────────────────
    if raw.startswith("http://") or raw.startswith("https://") or "github.com/" in raw:
        raise ValueError(
            f"The URL '{raw}' is not a valid GitHub Issue URL. "
            "Expected format: https://github.com/<owner>/<repo>/issues/<number>"
        )

    # ── 2. Free-text and Manual Format Path ──────────────────────────────────
    lines = raw.split("\n", 1)
    first_line = lines[0].strip()
    raw_body = lines[1].strip() if len(lines) > 1 else ""

    if ":" in first_line:
        parts = first_line.split(":", 1)
        repo_candidate = parts[0].strip()
        title_candidate = parts[1].strip()
        if "/" in repo_candidate and title_candidate:
            owner, repo_name = repo_candidate.split("/", 1)
            clean_title, clean_body, warnings, is_suspicious = validate_and_sanitize_issue(
                title_candidate, raw_body
            )
            return IssueIntakeResult(
                repo=repo_candidate,
                owner=owner,
                repo_name=repo_name,
                issue_title=clean_title,
                issue_body=clean_body,
                is_suspicious=is_suspicious,
                guardrail_warnings=warnings,
            )

    # Default local / demo repo
    clean_title, clean_body, warnings, is_suspicious = validate_and_sanitize_issue(
        first_line, raw_body
    )
    return IssueIntakeResult(
        repo="demo-org/demo-repo",
        owner="demo-org",
        repo_name="demo-repo",
        issue_title=clean_title,
        issue_body=clean_body,
        is_suspicious=is_suspicious,
        guardrail_warnings=warnings,
    )
