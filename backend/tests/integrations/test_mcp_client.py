"""
Tests for Genuine GitHub MCP Client, Tool Allowlist/Denylist Enforcement, and Error Mapping.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from mcp.types import Tool

from app.integrations.mcp_client import (
    GitHubMCPClient,
    MCPClientError,
    MCPConnectionError,
    MCPRateLimitError,
    MCPResourceNotFoundError,
    MCPTimeoutError,
    MCPToolBlockedError,
    READ_ONLY_TOOL_ALLOWLIST,
    WRITE_CAPABLE_TOOL_DENYLIST,
    redact_token,
)

# Canonical list of 26 tools discovered from official github-mcp-server v0.6.2
DISCOVERED_GITHUB_MCP_TOOLS: list[str] = [
    "create_or_update_file",
    "search_repositories",
    "create_repository",
    "get_file_contents",
    "push_files",
    "create_issue",
    "create_pull_request",
    "fork_repository",
    "create_branch",
    "list_commits",
    "list_issues",
    "update_issue",
    "add_issue_comment",
    "search_code",
    "search_issues",
    "search_users",
    "get_issue",
    "get_pull_request",
    "list_pull_requests",
    "create_pull_request_review",
    "merge_pull_request",
    "get_pull_request_files",
    "get_pull_request_status",
    "update_pull_request_branch",
    "get_pull_request_comments",
    "get_pull_request_reviews",
]


@pytest.fixture
def fake_session():
    """Create a mock ClientSession that returns the 26 discovered GitHub MCP tools."""
    session = MagicMock()
    tool_objs = [
        Tool(name=name, description=f"Tool {name}", inputSchema={"type": "object"})
        for name in DISCOVERED_GITHUB_MCP_TOOLS
    ]
    session.list_tools = AsyncMock(return_value=MagicMock(tools=tool_objs))
    session.call_tool = AsyncMock()
    return session


@pytest.fixture
def mcp_client(fake_session):
    return GitHubMCPClient(token="ghp_testtoken1234567890", session=fake_session)


@pytest.mark.asyncio
async def test_tool_discovery_and_classification(mcp_client):
    """Assert all 26 tools discovered from GitHub MCP server are accounted for."""
    tools = await mcp_client.list_tools()
    tool_names = {t.name for t in tools}
    assert tool_names == set(DISCOVERED_GITHUB_MCP_TOOLS)

    # Every discovered tool must be either allowlisted read-only or in write denylist or unallowlisted
    for name in tool_names:
        if name in WRITE_CAPABLE_TOOL_DENYLIST:
            assert name not in READ_ONLY_TOOL_ALLOWLIST
        elif name in READ_ONLY_TOOL_ALLOWLIST:
            assert name not in WRITE_CAPABLE_TOOL_DENYLIST


@pytest.mark.asyncio
async def test_every_write_tool_is_strictly_blocked(mcp_client):
    """Iterate over every write-capable tool and assert invocation raises MCPToolBlockedError."""
    for tool_name in WRITE_CAPABLE_TOOL_DENYLIST:
        with pytest.raises(MCPToolBlockedError) as exc_info:
            await mcp_client.call_tool(tool_name, {"dummy": "arg"})
        assert "blocked by security policy" in str(exc_info.value)
        assert "write operations are forbidden" in str(exc_info.value)

    # Assert that session.call_tool was never invoked for any write tool
    mcp_client._session.call_tool.assert_not_called()


@pytest.mark.asyncio
async def test_unknown_tools_blocked_by_default(mcp_client):
    """Unknown or newly added tools not in the allowlist must be blocked by default."""
    unknown_tools = ["execute_arbitrary_command", "drop_database", "nuclear_wipe", "get_super_secret"]
    for tool_name in unknown_tools:
        with pytest.raises(MCPToolBlockedError) as exc_info:
            await mcp_client.call_tool(tool_name, {})
        assert "not in the read-only allowlist" in str(exc_info.value)

    mcp_client._session.call_tool.assert_not_called()


@pytest.mark.asyncio
async def test_allowlisted_read_tool_execution(mcp_client):
    """Allowlisted read tools successfully pass arguments and parse return payloads."""
    content_mock = MagicMock()
    content_mock.text = '{"title": "Bug in safe_divide", "body": "Division by zero", "number": 42}'
    mcp_client._session.call_tool.return_value = MagicMock(isError=False, content=[content_mock])

    result = await mcp_client.call_tool("get_issue", {"owner": "pallets", "repo": "flask", "issue_number": 42})
    assert isinstance(result, dict)
    assert result["title"] == "Bug in safe_divide"
    assert result["number"] == 42
    mcp_client._session.call_tool.assert_called_once_with(
        "get_issue", {"owner": "pallets", "repo": "flask", "issue_number": 42}
    )


@pytest.mark.asyncio
async def test_error_mapping_not_found(mcp_client):
    """Assert 404 / Resource Not Found is mapped to MCPResourceNotFoundError."""
    content_mock = MagicMock()
    content_mock.text = "Not Found: Resource not found: 404"
    mcp_client._session.call_tool.return_value = MagicMock(isError=True, content=[content_mock])

    with pytest.raises(MCPResourceNotFoundError):
        await mcp_client.call_tool("get_issue", {"owner": "pallets", "repo": "flask", "issue_number": 999999})


@pytest.mark.asyncio
async def test_error_mapping_rate_limit(mcp_client):
    """Assert 403 / API rate limit exceeded is mapped to MCPRateLimitError."""
    content_mock = MagicMock()
    content_mock.text = "API rate limit exceeded for user ID 123 (403)"
    mcp_client._session.call_tool.return_value = MagicMock(isError=True, content=[content_mock])

    with pytest.raises(MCPRateLimitError):
        await mcp_client.call_tool("list_commits", {"owner": "pallets", "repo": "flask"})


@pytest.mark.asyncio
async def test_bounded_retries_on_timeout(mcp_client):
    """Assert client performs bounded retries on timeout before raising MCPTimeoutError."""
    mcp_client.max_retries = 3
    mcp_client.timeout_seconds = 0.05
    mcp_client._session.call_tool.side_effect = asyncio.TimeoutError()

    with pytest.raises(MCPTimeoutError) as exc_info:
        await mcp_client.call_tool("get_file_contents", {"owner": "pallets", "repo": "flask", "path": "src"})
    assert "timed out after 3 attempts" in str(exc_info.value)
    assert mcp_client._session.call_tool.call_count == 3


def test_token_redaction_in_messages():
    """Verify secrets and tokens are redacted from messages and error strings."""
    secret = "ghp_1234567890abcdefABCDEF"
    raw_error = f"Error connecting to https://api.github.com with token {secret}: 401 Unauthorized"
    cleaned = redact_token(raw_error, secret)
    assert secret not in cleaned
    assert "[REDACTED_GITHUB_TOKEN]" in cleaned

    bearer_error = "Authorization failed: Bearer ya29.a0AfH6SMB_secret_key_12345"
    cleaned_bearer = redact_token(bearer_error)
    assert "ya29" not in cleaned_bearer
    assert "Bearer [REDACTED_TOKEN]" in cleaned_bearer


def test_all_discovered_tools_classified_and_allowlist_length():
    """Assert every discovered tool is either allowlisted-read or denied, and counts match exactly."""
    assert len(READ_ONLY_TOOL_ALLOWLIST) == 14, f"Expected 14 read-only tools, got {len(READ_ONLY_TOOL_ALLOWLIST)}"
    assert len(WRITE_CAPABLE_TOOL_DENYLIST) == 12, f"Expected 12 write tools, got {len(WRITE_CAPABLE_TOOL_DENYLIST)}"
    assert READ_ONLY_TOOL_ALLOWLIST.isdisjoint(WRITE_CAPABLE_TOOL_DENYLIST), "Allowlist and denylist must not overlap"

    all_classified = READ_ONLY_TOOL_ALLOWLIST.union(WRITE_CAPABLE_TOOL_DENYLIST)
    assert len(all_classified) == 26
    assert set(DISCOVERED_GITHUB_MCP_TOOLS) == all_classified

    client = GitHubMCPClient(session=MagicMock())
    for tool_name in DISCOVERED_GITHUB_MCP_TOOLS:
        if tool_name in READ_ONLY_TOOL_ALLOWLIST:
            assert client.is_tool_allowed(tool_name) is True
        elif tool_name in WRITE_CAPABLE_TOOL_DENYLIST:
            assert client.is_tool_allowed(tool_name) is False
        else:
            pytest.fail(f"Unclassified tool: {tool_name}")
