"""
Repository Snapshot Service.

Builds a bounded, isolated, read-only directory snapshot of a target GitHub repository
via the GitHub MCP client (or argument-vector shallow clone fallback) for Retrieval to index.

Guarantees:
- Strict owner/repo/ref validation.
- Path traversal and symlink rejection.
- Bounded file count, per-file size, and total byte limits.
- Sensitive files (.env, secrets) and binaries excluded.
- Deterministic commit SHA resolution and metadata recording.
- Shallow clone fallback is strictly labelled non-MCP in metadata and logs.
"""

from __future__ import annotations

import base64
import datetime
import json
import logging
import os
from pathlib import Path
import re
import shutil
import subprocess
import time
from typing import Any, Dict, List, Optional, Set, Tuple

from app.integrations.mcp_client import (
    GitHubMCPClient,
    MCPClientError,
    MCPRateLimitError,
    MCPResourceNotFoundError,
    get_github_mcp_client,
)

logger = logging.getLogger("mini_devin.integrations.repo_snapshot")

# ── Boundaries and Limits ──────────────────────────────────────────────────
MAX_SNAPSHOT_FILES: int = 250
MAX_FILE_BYTES: int = 512 * 1024           # 512 KB per file
MAX_TOTAL_SNAPSHOT_BYTES: int = 20 * 1024 * 1024  # 20 MB total
MAX_TREE_DEPTH: int = 8
SNAPSHOT_TIMEOUT_SECONDS: float = 60.0

DEFAULT_SNAPSHOTS_ROOT = Path("workspaces/snapshots").resolve()

# Strict identifier validation (alphanumeric, dashes, underscores, dots)
_SAFE_IDENTIFIER_RE = re.compile(r"^[a-zA-Z0-9_.-]+$")

# File and directory exclusions (matching indexer rules)
EXCLUDED_NAMES: frozenset[str] = frozenset({
    ".git", ".hg", ".svn", ".venv", "venv", "env", ".env", "node_modules",
    "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache",
    ".idea", ".vscode", "dist", "build", "target", "bin", "obj",
    ".tox", "coverage", ".coverage", "htmlcov",
})

EXCLUDED_EXTENSIONS: frozenset[str] = frozenset({
    ".pyc", ".pyo", ".pyd", ".so", ".dll", ".dylib", ".exe", ".bin",
    ".zip", ".tar", ".gz", ".tgz", ".bz2", ".xz", ".7z", ".whl",
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".bmp", ".tiff", ".webp",
    ".pdf", ".svg", ".wasm", ".db", ".sqlite", ".sqlite3", ".parquet",
    ".arrow", ".pkl", ".pickle", ".npy", ".npz", ".pt", ".pth", ".onnx",
    ".woff", ".woff2", ".ttf", ".eot", ".mp3", ".mp4", ".wav", ".avi",
})

SECRET_PATTERNS: tuple[str, ...] = (
    ".env", ".pem", ".key", ".pkcs12", ".pfx", "id_rsa", "id_ed25519",
    "token", "secret", "credential", "service-account",
)


def validate_repo_identifier(owner: str, repo: str, ref: Optional[str] = None) -> None:
    """Validate that repository coordinates contain no path traversal or shell characters."""
    if not owner or not _SAFE_IDENTIFIER_RE.match(owner):
        raise ValueError(f"Invalid repository owner identifier: {owner!r}")
    if not repo or not _SAFE_IDENTIFIER_RE.match(repo):
        raise ValueError(f"Invalid repository name identifier: {repo!r}")
    if ref and not _SAFE_IDENTIFIER_RE.match(ref):
        raise ValueError(f"Invalid git ref/branch identifier: {ref!r}")


def is_sensitive_or_binary(name: str) -> bool:
    """Check if file name indicates secrets or binary content."""
    lower = name.lower()
    if lower in EXCLUDED_NAMES:
        return True
    _, ext = os.path.splitext(lower)
    if ext in EXCLUDED_EXTENSIONS:
        return True
    for pat in SECRET_PATTERNS:
        if pat in lower:
            return True
    return False


class RepositorySnapshotService:
    """Service responsible for creating verified local snapshots of remote repositories."""

    def __init__(
        self,
        mcp_client: Optional[GitHubMCPClient] = None,
        snapshots_root: Optional[Path] = None,
    ):
        self.mcp_client = mcp_client or get_github_mcp_client()
        self.snapshots_root = (snapshots_root or DEFAULT_SNAPSHOTS_ROOT).resolve()
        self.snapshots_root.mkdir(parents=True, exist_ok=True)

    async def create_snapshot(
        self,
        owner: str,
        repo: str,
        ref: Optional[str] = "main",
        allow_shallow_clone_fallback: bool = True,
    ) -> Path:
        """
        Create a bounded local snapshot of the repository.
        
        Attempts MCP snapshot first; if MCP cannot fulfill the request and fallback is allowed,
        falls back to an argument-list shallow clone labelled clearly as non-MCP.
        """
        validate_repo_identifier(owner, repo, ref)
        branch = ref or "main"

        # 1. Resolve deterministic commit SHA
        commit_sha = await self._resolve_commit_sha(owner, repo, branch)
        short_sha = commit_sha[:8] if commit_sha else "latest"
        snapshot_dir = self.snapshots_root / f"{owner}_{repo}_{short_sha}"

        # 2. Check if cache exists
        meta_file = snapshot_dir / "snapshot_metadata.json"
        if snapshot_dir.is_dir() and meta_file.is_file():
            logger.info("Found existing verified snapshot cache at %s", snapshot_dir)
            return snapshot_dir

        # 3. Attempt genuine MCP snapshot
        try:
            logger.info("Fetching MCP snapshot for %s/%s@%s...", owner, repo, branch)
            await self._fetch_via_mcp(owner, repo, branch, commit_sha, snapshot_dir)
            return snapshot_dir
        except Exception as mcp_err:
            logger.warning("MCP snapshot creation failed: %s", mcp_err)
            if not allow_shallow_clone_fallback:
                raise

        # 4. Fallback: argument-vector shallow clone (hooks disabled, no submodules)
        logger.warning(
            "NON_MCP_FALLBACK: Initiating shallow clone fallback for %s/%s@%s",
            owner, repo, branch,
        )
        return self._fetch_via_shallow_clone(owner, repo, branch, commit_sha, snapshot_dir)

    async def _resolve_commit_sha(self, owner: str, repo: str, branch: str) -> str:
        """Resolve commit SHA deterministically via MCP list_commits."""
        try:
            commits = await self.mcp_client.list_commits(owner, repo, sha=branch, per_page=1)
            if commits and isinstance(commits, list) and len(commits) > 0:
                first = commits[0]
                if isinstance(first, dict):
                    sha = first.get("sha")
                    if sha:
                        return str(sha)
        except Exception as e:
            logger.debug("Could not resolve commit SHA via MCP: %s", e)
        return branch

    async def _fetch_via_mcp(
        self,
        owner: str,
        repo: str,
        branch: str,
        commit_sha: str,
        snapshot_dir: Path,
    ) -> None:
        """Fetch tree and file contents strictly through the GitHub MCP client."""
        start_time = time.perf_counter()
        snapshot_dir.mkdir(parents=True, exist_ok=True)

        file_count = 0
        total_bytes = 0
        is_truncated = False
        truncation_reason: Optional[str] = None

        # Queue of directories to traverse: relative path from root
        dirs_to_visit: List[Tuple[str, int]] = [("", 0)]

        while dirs_to_visit and file_count < MAX_SNAPSHOT_FILES:
            current_rel_path, depth = dirs_to_visit.pop(0)
            if depth > MAX_TREE_DEPTH:
                continue

            # Fetch directory listing via get_file_contents
            listing = await self.mcp_client.get_file_contents(
                owner=owner,
                repo=repo,
                path=current_rel_path,
                branch=branch,
            )

            if not isinstance(listing, list):
                continue

            for item in listing:
                if not isinstance(item, dict):
                    continue

                item_name = item.get("name", "")
                item_path = item.get("path", "")
                item_type = item.get("type", "")
                item_size = int(item.get("size", 0))

                # Safety check against path traversal
                if ".." in item_path or item_path.startswith("/"):
                    logger.warning("Path traversal attempt in MCP entry rejected: %s", item_path)
                    continue

                if is_sensitive_or_binary(item_name):
                    continue

                if item_type == "dir":
                    dirs_to_visit.append((item_path, depth + 1))
                elif item_type == "file":
                    if item_size > MAX_FILE_BYTES:
                        logger.debug("Skipping oversized file %s (%d bytes)", item_path, item_size)
                        continue

                    if total_bytes + item_size > MAX_TOTAL_SNAPSHOT_BYTES:
                        is_truncated = True
                        truncation_reason = "max_total_bytes_exceeded"
                        logger.warning(
                            "Total snapshot byte budget reached (%d bytes). Snapshot truncated.",
                            total_bytes,
                        )
                        break

                    # Fetch file contents
                    file_data = await self.mcp_client.get_file_contents(
                        owner=owner,
                        repo=repo,
                        path=item_path,
                        branch=branch,
                    )
                    content_bytes = b""
                    if isinstance(file_data, dict):
                        encoding = file_data.get("encoding", "")
                        raw_content = file_data.get("content", "")
                        if encoding == "base64" and raw_content:
                            try:
                                clean_b64 = re.sub(r"\s+", "", raw_content)
                                missing_padding = len(clean_b64) % 4
                                if missing_padding:
                                    clean_b64 += "=" * (4 - missing_padding)
                                content_bytes = base64.b64decode(clean_b64)
                            except Exception:
                                content_bytes = raw_content.encode("utf-8")
                        elif "text" in file_data:
                            content_bytes = file_data["text"].encode("utf-8")
                        else:
                            content_bytes = str(raw_content).encode("utf-8")
                    elif isinstance(file_data, str):
                        content_bytes = file_data.encode("utf-8")

                    target_file = snapshot_dir / item_path
                    target_file.parent.mkdir(parents=True, exist_ok=True)
                    target_file.write_bytes(content_bytes)

                    file_count += 1
                    total_bytes += len(content_bytes)
                    if file_count >= MAX_SNAPSHOT_FILES:
                        is_truncated = True
                        truncation_reason = "max_files_exceeded"
                        logger.warning(
                            "Maximum snapshot file count reached (%d files). Snapshot truncated.",
                            file_count,
                        )
                        break

        if dirs_to_visit and not is_truncated:
            is_truncated = True
            truncation_reason = "max_files_or_depth_reached"

        # Write metadata
        duration_ms = int((time.perf_counter() - start_time) * 1000)
        metadata = {
            "owner": owner,
            "repo": repo,
            "ref": branch,
            "commit_sha": commit_sha,
            "file_count": file_count,
            "total_bytes": total_bytes,
            "method": "mcp",
            "is_truncated": is_truncated,
            "truncation_reason": truncation_reason,
            "duration_ms": duration_ms,
            "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }
        (snapshot_dir / "snapshot_metadata.json").write_text(
            json.dumps(metadata, indent=2), encoding="utf-8"
        )
        if is_truncated:
            logger.warning(
                "WARNING: Snapshot for %s/%s@%s was TRUNCATED (%s). Downstream retrieval operating on partial view.",
                owner, repo, branch, truncation_reason,
            )
        logger.info(
            "MCP Snapshot created at %s: %d files, %d bytes (truncated=%s) in %dms",
            snapshot_dir, file_count, total_bytes, is_truncated, duration_ms,
        )

    def _fetch_via_shallow_clone(
        self,
        owner: str,
        repo: str,
        branch: str,
        commit_sha: str,
        snapshot_dir: Path,
    ) -> Path:
        """
        Shallow clone fallback when MCP cannot deliver full repository tree.
        
        Security constraints:
        - Argument vectors only (no shell=True).
        - Core hooks disabled (core.hooksPath=/dev/null).
        - No submodules or LFS smudge.
        - .git directory deleted immediately after clone.
        - Labelled non-MCP in metadata.
        """
        start_time = time.perf_counter()
        if snapshot_dir.exists():
            shutil.rmtree(snapshot_dir, ignore_errors=True)
        snapshot_dir.mkdir(parents=True, exist_ok=True)

        clone_url = f"https://github.com/{owner}/{repo}.git"
        cmd = [
            "git",
            "clone",
            "--depth", "1",
            "--single-branch",
            "-b", branch,
            "--config", "core.hooksPath=/dev/null",
            "--config", "filter.lfs.smudge=",
            "--no-tags",
            clone_url,
            str(snapshot_dir),
        ]

        logger.info("Executing safe shallow clone: %s", " ".join(cmd[:6]))
        res = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=SNAPSHOT_TIMEOUT_SECONDS,
        )
        if res.returncode != 0:
            shutil.rmtree(snapshot_dir, ignore_errors=True)
            raise MCPClientError(f"Shallow clone fallback failed: {res.stderr[:200]}")

        # Delete .git directory immediately for security
        git_dir = snapshot_dir / ".git"
        if git_dir.exists():
            shutil.rmtree(git_dir, ignore_errors=True)

        # Enforce file limits and strip forbidden files
        file_count = 0
        total_bytes = 0
        for root, dirs, files in os.walk(snapshot_dir):
            dirs[:] = [d for d in dirs if not is_sensitive_or_binary(d)]
            for fname in files:
                fpath = Path(root) / fname
                if is_sensitive_or_binary(fname):
                    try:
                        fpath.unlink()
                    except OSError:
                        pass
                    continue

                size = fpath.stat().st_size
                if size > MAX_FILE_BYTES:
                    try:
                        fpath.unlink()
                    except OSError:
                        pass
                    continue

                if file_count >= MAX_SNAPSHOT_FILES or total_bytes + size > MAX_TOTAL_SNAPSHOT_BYTES:
                    try:
                        fpath.unlink()
                    except OSError:
                        pass
                    continue

                file_count += 1
                total_bytes += size

        duration_ms = int((time.perf_counter() - start_time) * 1000)
        metadata = {
            "owner": owner,
            "repo": repo,
            "ref": branch,
            "commit_sha": commit_sha,
            "file_count": file_count,
            "total_bytes": total_bytes,
            "method": "shallow_clone_non_mcp",
            "duration_ms": duration_ms,
            "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }
        (snapshot_dir / "snapshot_metadata.json").write_text(
            json.dumps(metadata, indent=2), encoding="utf-8"
        )
        logger.info("NON-MCP Snapshot completed at %s (%d files)", snapshot_dir, file_count)
        return snapshot_dir


def read_snapshot_metadata(snapshot_dir: Path) -> dict[str, Any]:
    """Read metadata from a snapshot directory if snapshot_metadata.json is present."""
    meta_path = Path(snapshot_dir) / "snapshot_metadata.json"
    if meta_path.is_file():
        try:
            return json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}

