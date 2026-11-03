"""
Verification Tests: Coder SWE-Agent ACI & PR Content Parity.
Ensures pushed file content equals the sandbox file content and never falls back to placeholder text.
"""

from pathlib import Path
import pytest

from app.agents.pr_agent.agent import pr_node
from app.agents.schemas import create_initial_state
from app.agents.tools.repo_tools import (
    edit_file,
    goto,
    open_file,
    scroll,
)
from app.integrations.github_client import FileChange


def test_swe_agent_aci_viewer_and_linter_edit(tmp_path: Path):
    """Verify windowed viewer, capped search, denylist, and linter-gated rollback."""
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    py_file = repo_dir / "calc.py"
    py_file.write_text("def add(a, b):\n    return a + b\n\ndef sub(a, b):\n    return a - b\n", encoding="utf-8")

    # 1. Windowed viewer: open_file, goto, scroll
    v_open = open_file(repo_dir, "calc.py", line_number=1, window_size=2)
    assert v_open["success"] is True
    assert v_open["start_line"] == 1
    assert v_open["end_line"] == 2

    v_goto = goto(repo_dir, "calc.py", line_number=4, window_size=2)
    assert v_goto["success"] is True
    assert v_goto["start_line"] == 4

    v_scroll = scroll(repo_dir, "calc.py", current_line=1, direction="down", window_size=2)
    assert v_scroll["success"] is True
    assert v_scroll["start_line"] == 3

    # 2. Denylist enforcement in edit_file (.github/, .env, etc.)
    env_file = repo_dir / ".env"
    env_file.write_text("SECRET=123", encoding="utf-8")
    denied = edit_file(repo_dir, ".env", start_line=1, end_line=1, new_text="SECRET=456")
    assert denied["success"] is False
    assert "denied" in denied["error"].lower() or "violation" in denied["error"].lower()

    # 3. Linter rollback on syntax error
    bad_edit = edit_file(repo_dir, "calc.py", start_line=2, end_line=2, new_text="    return a +++\n")
    assert bad_edit["success"] is False
    assert bad_edit.get("rolled_back") is True
    # Verify file on disk was preserved
    assert "return a + b" in py_file.read_text(encoding="utf-8")

    # 4. Valid linter edit succeeds and updates file on disk
    good_edit = edit_file(repo_dir, "calc.py", start_line=2, end_line=2, new_text="    return (a + b) * 2\n")
    assert good_edit["success"] is True
    assert "(a + b) * 2" in py_file.read_text(encoding="utf-8")


def test_pushed_content_equals_sandbox_content(tmp_path: Path, monkeypatch):
    """Verify pushed PR content equals real sandbox working tree content."""
    workspace = tmp_path / "sandbox_workspace"
    workspace.mkdir()
    target_file = workspace / "patient_import.py"
    target_file.write_text("def parse_row(row):\n    return {}\n", encoding="utf-8")

    # Coder ACI edits the sandbox working tree
    edit_res = edit_file(
        workspace,
        "patient_import.py",
        start_line=2,
        end_line=2,
        new_text="    return {'validated': True, 'row': row}\n",
    )
    assert edit_res["success"] is True
    sandbox_content = target_file.read_text(encoding="utf-8")
    assert "{'validated': True, 'row': row}" in sandbox_content

    state = {
        "status": "approved",
        "repo": "owner/puducan-jipmer",
        "issue_title": "Add patient import validation",
        "human_approval": {"decision": "approved"},
        "review_findings": {"approved": True, "verdict": "approve", "score": 1.0},
        "test_results": {"passed": True, "total_tests": 1},
        "workspace_path": str(workspace),
        "code_changes": [
            {
                "path": "patient_import.py",
                "diff_text": edit_res["diff"],
                "content": sandbox_content,
                "requirement_ids": ["R1"],
            }
        ],
    }

    pushed_files = []

    class MockGitRef:
        owner = "owner"
        repo = "puducan-jipmer"
        full_name = "owner/puducan-jipmer"
        branch = "main"

    class MockPRResponse:
        pr_url = "https://github.com/owner/puducan-jipmer/pull/100"

    class MockGitHubClient:
        def get_authenticated_user(self):
            return "owner"

        def create_branch(self, ref, branch):
            return True

        def push_changes(self, ref, branch_name, changes):
            pushed_files.extend(changes)
            return True

        def open_pull_request(self, req):
            return MockPRResponse()

    monkeypatch.setattr("app.integrations.github_client.get_github_client", lambda: MockGitHubClient())

    out = pr_node(state)
    assert out.get("pull_request_url") == "https://github.com/owner/puducan-jipmer/pull/100"

    # Core assertion: pushed file MUST match sandbox content and never contain fallback string
    assert len(pushed_files) == 1
    pushed = pushed_files[0]
    assert pushed.path == "patient_import.py"
    assert pushed.content != "# mini-devin update\n", "PR must NOT contain fallback text"
    assert pushed.content == sandbox_content, "Pushed content MUST equal sandbox content"


def test_missing_content_fails_closed_without_fallback(monkeypatch):
    """Verify that missing content raises an error rather than falling back to placeholder."""
    state = {
        "status": "approved",
        "repo": "owner/test-repo",
        "issue_title": "Fix bug",
        "human_approval": {"decision": "approved"},
        "review_findings": {"approved": True, "verdict": "approve", "score": 1.0},
        "test_results": {"passed": True},
        "code_changes": [
            {
                "path": "nonexistent.py",
                "diff_text": "+ some diff",
                "content": None,
                "requirement_ids": ["R1"],
            }
        ],
    }

    class MockGitHubClient:
        def get_authenticated_user(self):
            return "owner"

        def create_branch(self, ref, branch):
            return True

    monkeypatch.setattr("app.integrations.github_client.get_github_client", lambda: MockGitHubClient())

    with pytest.raises(ValueError, match="empty or missing content"):
        pr_node(state)
