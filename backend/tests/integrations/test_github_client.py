"""
Tests for GitHub Client Integration and Security Invariants.
"""

import pytest

from app.integrations.github_client import (
    BranchExistsError,
    FileChange,
    GitHubClient,
    GitRef,
    PathTraversalError,
    PermissionError,
    PRRequest,
    sanitize_relative_path,
)


@pytest.fixture
def client():
    # In-memory mock client without external network calls
    return GitHubClient(token="")


def test_sanitize_relative_path_valid():
    assert sanitize_relative_path("src/app/main.py") == "src/app/main.py"
    assert sanitize_relative_path("tests/test_app.py") == "tests/test_app.py"


def test_sanitize_relative_path_traversal_rejected():
    with pytest.raises(PathTraversalError):
        sanitize_relative_path("../secret.env")

    with pytest.raises(PathTraversalError):
        sanitize_relative_path("src/../../etc/passwd")

    with pytest.raises(PathTraversalError):
        sanitize_relative_path("/etc/passwd")

    with pytest.raises(PathTraversalError):
        sanitize_relative_path("C:\\Windows\\System32")


def test_fetch_repo(client):
    ref = GitRef(owner="pallets", repo="flask")
    ws_ref = client.fetch_repo(ref)
    assert ws_ref.startswith("workspace_ref://pallets/flask")
    assert "C:" not in ws_ref
    assert "/" in ws_ref


def test_create_branch_custom(client):
    ref = GitRef(owner="pallets", repo="flask")
    success = client.create_branch(ref, "mini-devin/fix-issue-100")
    assert success is True


def test_create_branch_protected_rejected(client):
    ref = GitRef(owner="pallets", repo="flask")
    with pytest.raises(PermissionError):
        client.create_branch(ref, "main")

    with pytest.raises(PermissionError):
        client.create_branch(ref, "master")


def test_push_changes_protected_rejected(client):
    ref = GitRef(owner="pallets", repo="flask")
    changes = [FileChange(path="src/app.py", content="# modified", action="modify")]
    with pytest.raises(PermissionError):
        client.push_changes(ref, "main", changes)


def test_push_and_read_changes(client):
    ref = GitRef(owner="pallets", repo="flask")
    branch = "mini-devin/fix-bug"
    changes = [
        FileChange(path="flask/app.py", content="# fix content\n", action="create")
    ]
    client.push_changes(ref, branch, changes)

    # Read back file
    content = client.read_file(ref, "flask/app.py")
    assert content == "# fix content\n"


def test_open_pull_request(client):
    ref = GitRef(owner="pallets", repo="flask")
    pr_req = PRRequest(
        ref=ref,
        title="fix(app): resolve flask abort regression",
        body="## Changes\nFixes issue #100",
        head_branch="mini-devin/fix-bug",
        base_branch="main",
    )
    resp = client.open_pull_request(pr_req)
    assert resp.created is True
    assert "https://github.com/pallets/flask/pull/" in resp.pr_url
    assert resp.pr_number > 0
    assert resp.head_branch == "mini-devin/fix-bug"
    assert resp.base_branch == "main"
