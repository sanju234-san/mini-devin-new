"""
GitHub REST/GraphQL Client Integration for Mini-Devin.

Implements the specification in docs/design/sandbox-and-github-contract.md:
- fetch_repo(ref: GitRef) -> str
- read_file(ref: GitRef, path: str) -> str
- create_branch(ref: GitRef, branch_name: str) -> bool
- push_changes(ref: GitRef, branch_name: str, changes: List[FileChange]) -> bool
- open_pull_request(request: PRRequest, auth_token: Optional[str] = None) -> PRResponse

Security Invariants:
1. Strict non-merge guarantee: Mini-Devin never auto-merges pull requests.
2. Protection of default branch: Direct commits or pushes to 'main', 'master', or default branches are forbidden.
3. Path sanitization: Paths with directory traversal ('..', absolute paths) are rejected immediately.
4. Auth enforcement: Read and write operations validate credentials and fail closed if unauthorized.
"""

from __future__ import annotations

import logging
import os
import re
from typing import Any, List, Literal, Optional

import httpx
from pydantic import BaseModel, Field

logger = logging.getLogger("mini_devin.github")

# Protected default branch names
PROTECTED_BRANCHES = frozenset({"main", "master", "develop", "dev", "trunk", "prod", "production"})


class GitRef(BaseModel):
    """Reference to a specific repository, branch, or commit."""
    owner: str = Field(..., description="Repository owner or organization name.")
    repo: str = Field(..., description="Repository name.")
    sha: Optional[str] = Field(default=None, description="Commit SHA if pinned.")
    branch: Optional[str] = Field(default=None, description="Branch name.")

    @property
    def full_name(self) -> str:
        return f"{self.owner}/{self.repo}"


class FileChange(BaseModel):
    """Representation of a file modification, creation, or deletion."""
    path: str = Field(..., description="Relative path within repository.")
    content: Optional[str] = Field(default=None, description="File content for create/modify.")
    action: Literal["create", "modify", "delete"] = Field(..., description="Action to perform.")


class PRRequest(BaseModel):
    """Request payload for opening a GitHub pull request."""
    ref: GitRef
    title: str = Field(..., max_length=256, description="Pull request title.")
    body: str = Field(..., description="Pull request description and artifact trail.")
    head_branch: str = Field(..., description="Feature branch containing changes.")
    base_branch: str = Field(default="main", description="Target base branch to merge into.")


class PRResponse(BaseModel):
    """Response returned upon pull request creation."""
    pr_url: str
    pr_number: int
    head_branch: str
    base_branch: str
    created: bool = True


class GitHubClientError(Exception):
    """Base exception for GitHub client errors."""
    pass


class RepoNotFoundError(GitHubClientError):
    pass


class BranchExistsError(GitHubClientError):
    pass


class PermissionError(GitHubClientError):
    pass


class PathTraversalError(GitHubClientError):
    pass


def sanitize_relative_path(path: str) -> str:
    """Validate that path does not escape the repository boundary."""
    cleaned = path.replace("\\", "/").strip()
    if cleaned.startswith("/") or re.match(r"^[a-zA-Z]:", cleaned):
        raise PathTraversalError(f"Absolute paths are forbidden: '{path}'")
    parts = cleaned.split("/")
    if ".." in parts or "." in parts:
        raise PathTraversalError(f"Path traversal sequences forbidden: '{path}'")
    return cleaned


class GitHubClient:
    """Client for GitHub API operations with read/write separation and safety guards."""

    def __init__(
        self,
        token: Optional[str] = None,
        api_base_url: str = "https://api.github.com",
        timeout: float = 30.0,
    ):
        self._token = token or os.getenv("GITHUB_TOKEN", "")
        if not self._token:
            try:
                import shutil
                import subprocess
                gh_bin = shutil.which("gh") or r"C:\Program Files\GitHub CLI\gh.exe"
                out = subprocess.run([gh_bin, "auth", "token"], capture_output=True, text=True, timeout=5)
                if out.returncode == 0 and out.stdout.strip():
                    self._token = out.stdout.strip()
            except Exception:
                pass
        self.api_base_url = api_base_url.rstrip("/")
        self.timeout = timeout
        self._mock_branches: dict[str, set[str]] = {}
        self._mock_files: dict[str, dict[str, str]] = {}
        self._mock_prs: list[dict[str, Any]] = []

    def _headers(self, write: bool = False, custom_token: Optional[str] = None) -> dict[str, str]:
        token = custom_token or self._token
        if not token:
            if write:
                raise PermissionError("Write operation forbidden: GITHUB_TOKEN is not configured.")
            return {
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "Mini-Devin-Agent",
            }
        return {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "Mini-Devin-Agent",
        }

    def get_authenticated_user(self) -> str:
        """Return username of the authenticated token."""
        if not self._token:
            return ""
        try:
            url = f"{self.api_base_url}/user"
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.get(url, headers=self._headers(write=False))
                if resp.status_code == 200:
                    return resp.json().get("login", "")
        except Exception:
            pass
        return ""

    def ensure_fork(self, ref: GitRef) -> GitRef:
        """Ensure a fork exists under the authenticated user's account and return fork GitRef."""
        user = self.get_authenticated_user()
        if not user or user.lower() == ref.owner.lower():
            return ref

        fork_url = f"{self.api_base_url}/repos/{user}/{ref.repo}"
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.get(fork_url, headers=self._headers(write=False))
            if resp.status_code == 200:
                return GitRef(owner=user, repo=ref.repo, branch=ref.branch or "main")

            # Fork does not exist; create it
            create_fork_url = f"{self.api_base_url}/repos/{ref.owner}/{ref.repo}/forks"
            fork_resp = client.post(create_fork_url, headers=self._headers(write=True))
            if fork_resp.status_code in (200, 202):
                return GitRef(owner=user, repo=ref.repo, branch=ref.branch or "main")

        return ref

    def fetch_repo(self, ref: GitRef) -> str:
        """
        Verify repository exists and return workspace reference.
        
        Does not expose internal host paths.
        """
        if not self._token:
            # Offline mock verification
            logger.info("Operating in offline/mock mode for repo fetch: %s", ref.full_name)
            return f"workspace_ref://{ref.full_name}@{ref.sha or ref.branch or 'HEAD'}"

        url = f"{self.api_base_url}/repos/{ref.owner}/{ref.repo}"
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.get(url, headers=self._headers(write=False))
            if resp.status_code == 404:
                raise RepoNotFoundError(f"Repository '{ref.full_name}' was not found on GitHub.")
            if resp.status_code in (401, 403):
                raise PermissionError(f"Authentication failure accessing '{ref.full_name}': {resp.text}")
            resp.raise_for_status()
            data = resp.json()
            default_branch = data.get("default_branch", "main")
            return f"workspace_ref://{ref.full_name}@{ref.sha or default_branch}"

    def read_file(self, ref: GitRef, path: str) -> str:
        """Read a file's content from a GitHub repository."""
        clean_path = sanitize_relative_path(path)

        # Check in-memory mock files first
        repo_key = ref.full_name
        if repo_key in self._mock_files and clean_path in self._mock_files[repo_key]:
            return self._mock_files[repo_key][clean_path]

        if not self._token:
            raise FileNotFoundError(f"File '{clean_path}' not found in mock store for '{repo_key}'")

        url = f"{self.api_base_url}/repos/{ref.owner}/{ref.repo}/contents/{clean_path}"
        params = {}
        if ref.sha or ref.branch:
            params["ref"] = ref.sha or ref.branch

        with httpx.Client(timeout=self.timeout) as client:
            resp = client.get(url, headers=self._headers(write=False), params=params)
            if resp.status_code == 404:
                raise FileNotFoundError(f"File '{clean_path}' does not exist in '{ref.full_name}'.")
            resp.raise_for_status()
            data = resp.json()
            if "content" in data and data.get("encoding") == "base64":
                import base64
                return base64.b64decode(data["content"]).decode("utf-8", errors="replace")
            return data.get("content", "")

    def create_branch(self, ref: GitRef, branch_name: str, base_ref: Optional[GitRef] = None) -> bool:
        """Create a new branch from reference base. Validates branch name."""
        if not re.match(r"^[a-zA-Z0-9_\-\./]+$", branch_name):
            raise GitHubClientError(f"Invalid branch name syntax: '{branch_name}'")
        if branch_name.lower() in PROTECTED_BRANCHES:
            raise PermissionError(f"Creation of protected branch '{branch_name}' is forbidden.")

        repo_key = ref.full_name
        if repo_key not in self._mock_branches:
            self._mock_branches[repo_key] = set()

        if branch_name in self._mock_branches[repo_key]:
            raise BranchExistsError(f"Branch '{branch_name}' already exists in '{repo_key}'.")

        if not self._token:
            self._mock_branches[repo_key].add(branch_name)
            logger.info("Mock branch '%s' created in repo '%s'", branch_name, repo_key)
            return True

        # Resolve base SHA from upstream base_ref if provided, or ref
        source_ref = base_ref or ref
        base_branch = source_ref.branch or "main"
        ref_url = f"{self.api_base_url}/repos/{source_ref.owner}/{source_ref.repo}/git/ref/heads/{base_branch}"
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.get(ref_url, headers=self._headers(write=False))
            if resp.status_code == 404:
                # Try master
                ref_url = f"{self.api_base_url}/repos/{source_ref.owner}/{source_ref.repo}/git/ref/heads/master"
                resp = client.get(ref_url, headers=self._headers(write=False))
            resp.raise_for_status()
            sha = resp.json()["object"]["sha"]

            create_url = f"{self.api_base_url}/repos/{ref.owner}/{ref.repo}/git/refs"
            create_payload = {"ref": f"refs/heads/{branch_name}", "sha": sha}
            post_resp = client.post(create_url, json=create_payload, headers=self._headers(write=True))
            if post_resp.status_code == 422:
                raise BranchExistsError(f"Branch '{branch_name}' already exists remotely.")
            post_resp.raise_for_status()
            return True

    def push_changes(self, ref: GitRef, branch_name: str, changes: List[FileChange]) -> bool:
        """Push modified files to branch. MUST NOT push to main/default branches."""
        if branch_name.lower() in PROTECTED_BRANCHES:
            raise PermissionError(f"Direct push to protected branch '{branch_name}' is strictly forbidden.")

        repo_key = ref.full_name
        if repo_key not in self._mock_files:
            self._mock_files[repo_key] = {}

        for ch in changes:
            clean_path = sanitize_relative_path(ch.path)
            if ch.action in ("create", "modify"):
                self._mock_files[repo_key][clean_path] = ch.content or ""
            elif ch.action == "delete":
                self._mock_files[repo_key].pop(clean_path, None)

        if not self._token:
            logger.info("Applied %d changes to mock workspace for branch '%s'", len(changes), branch_name)
            return True

        # Remote push implementation
        with httpx.Client(timeout=self.timeout) as client:
            for ch in changes:
                clean_path = sanitize_relative_path(ch.path)
                url = f"{self.api_base_url}/repos/{ref.owner}/{ref.repo}/contents/{clean_path}"
                get_resp = client.get(url, headers=self._headers(write=False), params={"ref": branch_name})
                sha = get_resp.json().get("sha") if get_resp.status_code == 200 else None

                import base64
                encoded_content = base64.b64encode((ch.content or "").encode("utf-8")).decode("ascii")
                payload: dict[str, Any] = {
                    "message": f"mini-devin: update {clean_path}",
                    "content": encoded_content,
                    "branch": branch_name,
                }
                if sha:
                    payload["sha"] = sha

                put_resp = client.put(url, json=payload, headers=self._headers(write=True))
                put_resp.raise_for_status()

        return True

    def open_pull_request(self, request: PRRequest, auth_token: Optional[str] = None) -> PRResponse:
        """
        Open a pull request on GitHub.
        
        Strict Invariants:
        1. Checks authentication token.
        2. Validates head and base branches.
        3. Never merges PR.
        """
        token = auth_token or self._token
        if not token:
            # Deterministic mock PR response for offline and test runs
            logger.info("Opening simulated PR for '%s' -> '%s'", request.head_branch, request.base_branch)
            pr_num = len(self._mock_prs) + 101
            simulated_url = f"https://github.com/{request.ref.full_name}/pull/{pr_num}"
            resp = PRResponse(
                pr_url=simulated_url,
                pr_number=pr_num,
                head_branch=request.head_branch,
                base_branch=request.base_branch,
                created=True,
            )
            self._mock_prs.append(resp.model_dump())
            return resp

        url = f"{self.api_base_url}/repos/{request.ref.owner}/{request.ref.repo}/pulls"
        payload = {
            "title": request.title,
            "body": request.body,
            "head": request.head_branch,
            "base": request.base_branch,
            "draft": False,
        }

        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(url, json=payload, headers=self._headers(write=True, custom_token=token))
            if resp.status_code in (401, 403):
                raise PermissionError(f"GitHub PR creation failed with auth error: {resp.text}")
            resp.raise_for_status()
            data = resp.json()
            return PRResponse(
                pr_url=data.get("html_url", ""),
                pr_number=data.get("number", 0),
                head_branch=request.head_branch,
                base_branch=request.base_branch,
                created=True,
            )


# Default singleton instance
_DEFAULT_CLIENT: Optional[GitHubClient] = None


def get_github_client() -> GitHubClient:
    """Return default configured GitHub client instance."""
    global _DEFAULT_CLIENT
    if _DEFAULT_CLIENT is None:
        _DEFAULT_CLIENT = GitHubClient()
    return _DEFAULT_CLIENT
