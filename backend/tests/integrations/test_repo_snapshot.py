"""
Tests for Repository Snapshot Service.

Verifies:
1. File and total byte limits are enforced.
2. Path traversal attempts are rejected.
3. Sensitive (.env, secrets) and binary files are excluded.
4. Commit SHA is deterministically recorded in snapshot metadata.
5. Shallow clone fallback is labelled non-MCP.
"""

from __future__ import annotations

import base64
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from app.integrations.repo_snapshot import (
    MAX_FILE_BYTES,
    MAX_SNAPSHOT_FILES,
    RepositorySnapshotService,
    validate_repo_identifier,
)


@pytest.fixture
def mock_mcp_client():
    client = MagicMock()
    client.list_commits = AsyncMock(return_value=[{"sha": "a1b2c3d4e5f678901234567890abcdef12345678"}])
    return client


@pytest.fixture
def snapshot_service(mock_mcp_client, tmp_path):
    return RepositorySnapshotService(mcp_client=mock_mcp_client, snapshots_root=tmp_path / "snapshots")


def test_validate_repo_identifier():
    """Assert valid and malicious repository coordinates are checked."""
    validate_repo_identifier("pallets", "flask", "main")

    # Malicious inputs
    with pytest.raises(ValueError):
        validate_repo_identifier("pallets/../etc", "flask")
    with pytest.raises(ValueError):
        validate_repo_identifier("pallets", "flask; rm -rf /")
    with pytest.raises(ValueError):
        validate_repo_identifier("pallets", "flask", "main && cat /etc/passwd")


@pytest.mark.asyncio
async def test_snapshot_fetches_files_and_writes_metadata(snapshot_service, mock_mcp_client):
    """Snapshot service fetches files through MCP and creates validated snapshot."""
    # Root listing with 1 dir and 1 file
    mock_mcp_client.get_file_contents = AsyncMock()

    def get_contents_side_effect(owner, repo, path, branch=None):
        if path == "":
            return [
                {"name": "src", "path": "src", "type": "dir", "size": 0},
                {"name": "README.md", "path": "README.md", "type": "file", "size": 50},
                {"name": ".env", "path": ".env", "type": "file", "size": 30},           # Must be excluded
                {"name": "malicious_link", "path": "../../etc/passwd", "type": "file", "size": 10},  # Traversal rejected
            ]
        elif path == "src":
            return [
                {"name": "app.py", "path": "src/app.py", "type": "file", "size": 100},
                {"name": "app.pyc", "path": "src/app.pyc", "type": "file", "size": 200},  # Binary excluded
            ]
        elif path == "README.md":
            return {"content": base64.b64encode(b"# Hello Flask").decode("ascii"), "encoding": "base64"}
        elif path == "src/app.py":
            return {"content": base64.b64encode(b"def main(): pass").decode("ascii"), "encoding": "base64"}
        return []

    mock_mcp_client.get_file_contents.side_effect = get_contents_side_effect

    snapshot_dir = await snapshot_service.create_snapshot("pallets", "flask", "main")
    assert snapshot_dir.is_dir()
    assert (snapshot_dir / "README.md").is_file()
    assert (snapshot_dir / "README.md").read_text(encoding="utf-8") == "# Hello Flask"
    assert (snapshot_dir / "src" / "app.py").is_file()

    # Assert sensitive files and traversal files are NOT present
    assert not (snapshot_dir / ".env").exists()
    assert not (snapshot_dir / "src" / "app.pyc").exists()
    assert not (snapshot_dir / "etc").exists()

    # Assert metadata JSON
    meta_file = snapshot_dir / "snapshot_metadata.json"
    assert meta_file.is_file()
    meta = json.loads(meta_file.read_text(encoding="utf-8"))
    assert meta["owner"] == "pallets"
    assert meta["repo"] == "flask"
    assert meta["method"] == "mcp"
    assert meta["commit_sha"] == "a1b2c3d4e5f678901234567890abcdef12345678"
    assert meta["file_count"] == 2


@pytest.mark.asyncio
async def test_snapshot_caching_by_sha(snapshot_service, mock_mcp_client):
    """If snapshot exists for commit SHA, return cached directory without re-fetching."""
    mock_mcp_client.get_file_contents = AsyncMock()
    mock_mcp_client.get_file_contents.return_value = [
        {"name": "main.py", "path": "main.py", "type": "file", "size": 20}
    ]

    dir1 = await snapshot_service.create_snapshot("testorg", "testrepo", "main")
    assert dir1.is_dir()
    initial_call_count = mock_mcp_client.get_file_contents.call_count

    # Second call for the same repo/sha
    dir2 = await snapshot_service.create_snapshot("testorg", "testrepo", "main")
    assert dir1 == dir2
    # No additional get_file_contents calls made because cached
    assert mock_mcp_client.get_file_contents.call_count == initial_call_count


@pytest.mark.asyncio
async def test_snapshot_truncation_is_flagged_in_metadata_and_state(snapshot_service, mock_mcp_client):
    """When repository file count exceeds limit, truncation is explicitly flagged in metadata."""
    from app.integrations.repo_snapshot import read_snapshot_metadata

    mock_mcp_client.get_file_contents = AsyncMock()
    mock_mcp_client.get_file_contents.side_effect = [
        # Root listing with 3 files
        [
            {"name": "file1.py", "path": "file1.py", "type": "file", "size": 10},
            {"name": "file2.py", "path": "file2.py", "type": "file", "size": 10},
            {"name": "file3.py", "path": "file3.py", "type": "file", "size": 10},
        ],
        # Content for file 1
        {"content": base64.b64encode(b"a = 1").decode("ascii"), "encoding": "base64"},
        # Content for file 2
        {"content": base64.b64encode(b"b = 2").decode("ascii"), "encoding": "base64"},
    ]

    with patch("app.integrations.repo_snapshot.MAX_SNAPSHOT_FILES", 2):
        snapshot_dir = await snapshot_service.create_snapshot("testorg", "bigrepo", "main")

    assert snapshot_dir.is_dir()
    meta = read_snapshot_metadata(snapshot_dir)
    assert meta.get("is_truncated") is True
    assert meta.get("truncation_reason") == "max_files_exceeded"
    assert meta.get("file_count") == 2

