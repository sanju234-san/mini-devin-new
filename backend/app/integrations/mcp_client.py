"""
Genuine Model Context Protocol (MCP) Client for GitHub.

Connects to the official GitHub MCP server via stdio transport (or custom transport),
discovers available tools dynamically at runtime, and enforces a strict read-only allowlist
in code to prevent any write-capable or unknown tools from being invoked.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import shutil
from typing import Any, Dict, List, Optional, Set

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import Tool

logger = logging.getLogger("mini_devin.integrations.mcp_client")

# ── Read-Only Allowlist and Write Denylist ──────────────────────────────────
# Discovered live from official github-mcp-server (v0.6.2)
READ_ONLY_TOOL_ALLOWLIST: frozenset[str] = frozenset({
    "get_issue",
    "get_file_contents",
    "list_commits",
    "search_code",
    "search_issues",
    "search_repositories",
    "search_users",
    "list_issues",
    "list_pull_requests",
    "get_pull_request",
    "get_pull_request_files",
    "get_pull_request_status",
    "get_pull_request_comments",
    "get_pull_request_reviews",
})

WRITE_CAPABLE_TOOL_DENYLIST: frozenset[str] = frozenset({
    "create_or_update_file",
    "create_repository",
    "push_files",
    "create_issue",
    "create_pull_request",
    "fork_repository",
    "create_branch",
    "update_issue",
    "add_issue_comment",
    "create_pull_request_review",
    "merge_pull_request",
    "update_pull_request_branch",
})


# ── Exception Hierarchy ───────────────────────────────────────────────────

class MCPClientError(Exception):
    """Base exception for all MCP client operations."""
    pass


class MCPConnectionError(MCPClientError):
    """Raised when failing to connect to or initialize the MCP server."""
    pass


class MCPTimeoutError(MCPClientError):
    """Raised when an MCP operation exceeds the configured timeout."""
    pass


class MCPToolBlockedError(MCPClientError):
    """Raised when an unallowlisted or write-capable tool is requested."""
    pass


class MCPRateLimitError(MCPClientError):
    """Raised when GitHub API rate limits are encountered."""
    pass


class MCPResourceNotFoundError(MCPClientError):
    """Raised when the requested issue, repository, or file is not found (404)."""
    pass


# ── Token Redaction ────────────────────────────────────────────────────────

def redact_token(text: str, token: Optional[str] = None) -> str:
    """Redact sensitive tokens and auth strings from error messages and logs."""
    if not text:
        return ""
    redacted = text
    if token and len(token) > 4:
        redacted = redacted.replace(token, "[REDACTED_GITHUB_TOKEN]")

    # Redact common token patterns (ghp_, gho_, github_pat_, Bearer ...)
    redacted = re.sub(r"gh[pousr]_[A-Za-z0-9_]{16,}", "[REDACTED_GITHUB_TOKEN]", redacted)
    redacted = re.sub(r"github_pat_[A-Za-z0-9_]{22,}", "[REDACTED_GITHUB_TOKEN]", redacted)
    redacted = re.sub(r"Bearer\s+[A-Za-z0-9_.-]+", "Bearer [REDACTED_TOKEN]", redacted, flags=re.IGNORECASE)
    return redacted


# ── GitHub MCP Client ─────────────────────────────────────────────────────

class GitHubMCPClient:
    """
    Async client managing an MCP session connected to the GitHub MCP server.
    
    Guarantees:
    1. Read-only allowlist enforced in code; all write-capable and unknown tools blocked.
    2. Token passed only via child process environment or constructor, never into prompts or traces.
    3. Secrets strictly redacted from all error messages and logs.
    4. Bounded retries with exponential backoff on transient errors.
    """

    def __init__(
        self,
        token: Optional[str] = None,
        command: Optional[str] = None,
        args: Optional[List[str]] = None,
        timeout_seconds: Optional[float] = None,
        max_retries: int = 3,
        server_params: Optional[StdioServerParameters] = None,
        session: Optional[ClientSession] = None,
    ):
        # Resolve token from arguments or configuration
        if token is not None:
            self._token = token
        else:
            try:
                from app.config import get_settings
                settings = get_settings()
                self._token = settings.GITHUB_TOKEN.get_secret_value() if settings.GITHUB_TOKEN else ""
            except Exception:
                self._token = os.getenv("GITHUB_TOKEN", "")

        if timeout_seconds is not None:
            self.timeout_seconds = timeout_seconds
        else:
            try:
                from app.config import get_settings
                self.timeout_seconds = getattr(get_settings(), "GITHUB_MCP_TIMEOUT", 60.0)
            except Exception:
                self.timeout_seconds = float(os.getenv("GITHUB_MCP_TIMEOUT", "60.0"))

        self.max_retries = max(1, min(max_retries, 5))
        self._custom_session = session
        self._server_params = server_params
        self._command = command
        if args is not None:
            self._args = args
        else:
            try:
                from app.config import get_settings
                pkg = get_settings().GITHUB_MCP_PACKAGE
            except Exception:
                pkg = os.getenv("GITHUB_MCP_PACKAGE", "@modelcontextprotocol/server-github@2025.4.8")
            self._args = ["-y", pkg]

        # Lifecycle state
        self._session: Optional[ClientSession] = session
        self._stdio_ctx: Any = None
        self._is_connected: bool = False
        self._discovered_tools: Dict[str, Tool] = {}
        self.server_name: Optional[str] = None
        self.server_version: Optional[str] = None

    async def connect(self) -> None:
        """Establish session with the MCP server and discover available tools."""
        if self._is_connected and self._session is not None:
            return

        if self._custom_session is not None:
            # Injected mock or in-process session
            self._session = self._custom_session
            self._is_connected = True
            await self._discover_and_validate_tools()
            return

        # Prepare stdio server parameters
        npx_cmd = self._command or shutil.which("npx") or "npx"
        env = dict(os.environ)
        if self._token:
            env["GITHUB_PERSONAL_ACCESS_TOKEN"] = self._token
            env["GITHUB_TOKEN"] = self._token

        params = self._server_params or StdioServerParameters(
            command=npx_cmd,
            args=self._args,
            env=env,
        )

        try:
            self._stdio_ctx = stdio_client(params)
            read_stream, write_stream = await asyncio.wait_for(
                self._stdio_ctx.__aenter__(),
                timeout=self.timeout_seconds,
            )
            session = ClientSession(read_stream, write_stream)
            await asyncio.wait_for(
                session.__aenter__(),
                timeout=self.timeout_seconds,
            )
            init_res = await asyncio.wait_for(
                session.initialize(),
                timeout=self.timeout_seconds,
            )
            self._session = session
            self._is_connected = True
            self.server_name = getattr(init_res.serverInfo, "name", "github-mcp-server")
            self.server_version = getattr(init_res.serverInfo, "version", "unknown")
            logger.info("Connected to GitHub MCP server '%s' (v%s)", self.server_name, self.server_version)

            await self._discover_and_validate_tools()

        except asyncio.TimeoutError as exc:
            await self.close()
            raise MCPTimeoutError(f"Timed out after {self.timeout_seconds}s connecting to GitHub MCP server") from exc
        except Exception as exc:
            await self.close()
            safe_msg = redact_token(str(exc), self._token)
            raise MCPConnectionError(f"Failed to connect to GitHub MCP server: {safe_msg}") from exc

    async def _discover_and_validate_tools(self) -> None:
        """Query server for tools and catalog them."""
        if self._session is None:
            raise MCPConnectionError("Cannot discover tools: session is not initialized")

        try:
            tools_result = await asyncio.wait_for(
                self._session.list_tools(),
                timeout=self.timeout_seconds,
            )
            self._discovered_tools = {t.name: t for t in tools_result.tools}
            logger.info("Discovered %d MCP tools from server", len(self._discovered_tools))

            # Audit against allowlist / denylist
            for tool_name in self._discovered_tools:
                if tool_name in WRITE_CAPABLE_TOOL_DENYLIST:
                    logger.debug("Write tool '%s' recognized and marked BLOCKED", tool_name)
                elif tool_name not in READ_ONLY_TOOL_ALLOWLIST:
                    logger.warning("Unallowlisted tool '%s' discovered; will be blocked by default", tool_name)

        except Exception as exc:
            safe_msg = redact_token(str(exc), self._token)
            raise MCPConnectionError(f"Tool discovery failed: {safe_msg}") from exc

    @classmethod
    def is_tool_allowed(cls, tool_name: str) -> bool:
        """Return True if tool is in read-only allowlist and not in write denylist."""
        return (tool_name in READ_ONLY_TOOL_ALLOWLIST) and (tool_name not in WRITE_CAPABLE_TOOL_DENYLIST)

    async def list_tools(self) -> List[Tool]:
        """Return the list of discovered tools."""
        if not self._is_connected:
            await self.connect()
        return list(self._discovered_tools.values())

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """
        Execute an MCP tool under strict read-only policy and bounded retries.
        
        Raises:
            MCPToolBlockedError: If the tool is write-capable or not in the allowlist.
            MCPRateLimitError: If GitHub rate limits are triggered.
            MCPResourceNotFoundError: If the target repository or issue is not found (404).
            MCPTimeoutError: If execution exceeds timeout after bounded retries.
            MCPClientError: For general tool execution errors.
        """
        # 1. Enforce strict allowlist and denylist in code
        if tool_name in WRITE_CAPABLE_TOOL_DENYLIST:
            raise MCPToolBlockedError(
                f"Tool '{tool_name}' is blocked by security policy: write operations are forbidden."
            )
        if tool_name not in READ_ONLY_TOOL_ALLOWLIST:
            raise MCPToolBlockedError(
                f"Tool '{tool_name}' is not in the read-only allowlist. Unknown tools are blocked by default."
            )

        if not self._is_connected:
            await self.connect()

        last_error: Optional[Exception] = None
        for attempt in range(1, self.max_retries + 1):
            try:
                res = await asyncio.wait_for(
                    self._session.call_tool(tool_name, arguments),
                    timeout=self.timeout_seconds,
                )
                
                # Check for errors returned in response payload
                if getattr(res, "isError", False):
                    err_msg = ""
                    if res.content:
                        err_msg = getattr(res.content[0], "text", "")
                    safe_msg = redact_token(err_msg, self._token)
                    self._classify_and_raise_error(safe_msg)

                # Parse and return content
                if not res.content:
                    return None
                text_content = getattr(res.content[0], "text", "")
                try:
                    return json.loads(text_content)
                except (json.JSONDecodeError, TypeError):
                    return text_content

            except (MCPToolBlockedError, MCPResourceNotFoundError, MCPRateLimitError):
                # Never retry client permission or not-found errors
                raise
            except asyncio.TimeoutError as exc:
                last_error = exc
                logger.warning(
                    "MCP call_tool('%s') attempt %d/%d timed out after %ss",
                    tool_name, attempt, self.max_retries, self.timeout_seconds,
                )
                if attempt < self.max_retries:
                    await asyncio.sleep(0.5 * (2 ** (attempt - 1)))
            except Exception as exc:
                safe_msg = redact_token(str(exc), self._token)
                self._classify_and_raise_error(safe_msg)
                last_error = exc
                logger.warning(
                    "MCP call_tool('%s') attempt %d/%d failed: %s",
                    tool_name, attempt, self.max_retries, safe_msg,
                )
                if attempt < self.max_retries:
                    await asyncio.sleep(0.5 * (2 ** (attempt - 1)))

        if isinstance(last_error, asyncio.TimeoutError):
            raise MCPTimeoutError(
                f"MCP call_tool('{tool_name}') timed out after {self.max_retries} attempts"
            )
        safe_msg = redact_token(str(last_error), self._token)
        raise MCPClientError(f"MCP call_tool('{tool_name}') failed after {self.max_retries} attempts: {safe_msg}")

    def _classify_and_raise_error(self, message: str) -> None:
        """Map error messages to typed exceptions."""
        lower = message.lower()
        if "not found" in lower or "404" in lower:
            raise MCPResourceNotFoundError(f"Requested resource not found: {message}")
        if "rate limit" in lower or "403" in lower:
            raise MCPRateLimitError(f"GitHub API rate limit exceeded: {message}")
        if "unauthorized" in lower or "401" in lower or "bad credentials" in lower:
            raise MCPClientError(f"GitHub authentication error (401): {message}")
        if "mcp" in lower and "error" in lower:
            raise MCPClientError(f"MCP server error: {message}")

    # ── High-level Domain Methods ─────────────────────────────────────────

    async def get_issue(self, owner: str, repo: str, issue_number: int) -> Dict[str, Any]:
        """Fetch real issue details (title, body, labels, state, url) via MCP."""
        if not owner or not repo or issue_number <= 0:
            raise MCPClientError(f"Invalid issue arguments: {owner}/{repo}#{issue_number}")

        result = await self.call_tool(
            "get_issue",
            {"owner": owner, "repo": repo, "issue_number": issue_number},
        )
        if isinstance(result, str):
            try:
                result = json.loads(result)
            except Exception:
                raise MCPClientError(f"Malformed JSON response for issue #{issue_number}")

        if not isinstance(result, dict) or not result.get("title"):
            raise MCPClientError(f"Malformed issue payload received for #{issue_number}")

        return result

    async def get_file_contents(
        self,
        owner: str,
        repo: str,
        path: str,
        branch: Optional[str] = None,
    ) -> Any:
        """Fetch contents of a file or directory listing from a repository."""
        args: Dict[str, Any] = {"owner": owner, "repo": repo, "path": path}
        if branch:
            args["branch"] = branch

        result = await self.call_tool("get_file_contents", args)
        if isinstance(result, str):
            try:
                return json.loads(result)
            except Exception:
                return result
        return result

    async def list_commits(
        self,
        owner: str,
        repo: str,
        sha: Optional[str] = None,
        page: int = 1,
        per_page: int = 10,
    ) -> List[Dict[str, Any]]:
        """List commits of a repository branch or ref."""
        args: Dict[str, Any] = {"owner": owner, "repo": repo, "page": page, "perPage": per_page}
        if sha:
            args["sha"] = sha

        result = await self.call_tool("list_commits", args)
        if isinstance(result, list):
            return result
        elif isinstance(result, dict) and "commits" in result:
            return result["commits"]
        return []

    async def search_code(
        self,
        query: str,
        page: int = 1,
        per_page: int = 20,
    ) -> Dict[str, Any]:
        """Search code in GitHub repositories."""
        result = await self.call_tool("search_code", {"q": query, "page": page, "per_page": per_page})
        if isinstance(result, dict):
            return result
        return {}

    async def close(self) -> None:
        """Cleanly terminate the MCP session and stdio streams."""
        if self._session is not None and self._custom_session is None:
            try:
                await self._session.__aexit__(None, None, None)
            except Exception:
                pass
            self._session = None

        if self._stdio_ctx is not None:
            try:
                await self._stdio_ctx.__aexit__(None, None, None)
            except Exception:
                pass
            self._stdio_ctx = None

        self._is_connected = False

    async def __aenter__(self) -> "GitHubMCPClient":
        await self.connect()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self.close()


def get_github_mcp_client(token: Optional[str] = None) -> GitHubMCPClient:
    """Create a configured GitHubMCPClient instance."""
    return GitHubMCPClient(token=token)
