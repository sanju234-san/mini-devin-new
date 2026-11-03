from pathlib import Path
"""
Tests for Sandbox Abstraction, GitHub Codespaces Adapter, and Host Execution Guard.
"""

from unittest.mock import patch
import pytest

from app.sandbox.codespaces_manager import (
    CodespacesSandboxManager,
    DiffApplyRequest,
    HostExecutionBlockedError,
    InvalidRequestError,
    SandboxCreateRequest,
    SandboxUnavailableError,
    TestRunRequest,
)


@pytest.fixture
def default_manager():
    """Manager with default security settings (host execution disabled)."""
    return CodespacesSandboxManager(use_cloud_codespaces=False, allow_unsafe_host_execution=False)


@pytest.fixture
def opt_in_manager():
    """Manager with explicit opt-in for host execution in isolated local scratch space."""
    return CodespacesSandboxManager(use_cloud_codespaces=False, allow_unsafe_host_execution=True)


# Alias for backward compatibility in existing tests
@pytest.fixture
def manager(opt_in_manager):
    return opt_in_manager


def test_create_and_destroy_sandbox(default_manager):
    req = SandboxCreateRequest(repo_ref="pallets/flask@main", timeout_seconds=60)
    resp = default_manager.create_sandbox(req)
    assert resp.status == "ready"
    assert resp.sandbox_id.startswith("cs_")
    assert resp.workspace_ref.startswith("workspace_ref://")
    assert "C:" not in resp.workspace_ref

    # Destroy
    destroyed = default_manager.destroy_sandbox(resp.sandbox_id)
    assert destroyed is True

    # Idempotent second destroy
    assert default_manager.destroy_sandbox(resp.sandbox_id) is True


def test_apply_diff_valid(default_manager):
    sb = default_manager.create_sandbox(SandboxCreateRequest(repo_ref="pallets/flask"))
    diff = (
        "--- a/src/app.py\n"
        "+++ b/src/app.py\n"
        "@@ -1,3 +1,4 @@\n"
        " def hello():\n"
        "+    return 'world'\n"
    )
    apply_resp = default_manager.apply_diff(DiffApplyRequest(sandbox_id=sb.sandbox_id, diff_text=diff))
    assert apply_resp.success is True
    assert "src/app.py" in apply_resp.applied_files
    default_manager.destroy_sandbox(sb.sandbox_id)


def test_apply_diff_path_traversal_rejected(default_manager):
    sb = default_manager.create_sandbox(SandboxCreateRequest(repo_ref="pallets/flask"))
    malicious_diff = (
        "--- a/../../etc/passwd\n"
        "+++ b/../../etc/passwd\n"
        "+malicious\n"
    )
    with pytest.raises(InvalidRequestError):
        default_manager.apply_diff(DiffApplyRequest(sandbox_id=sb.sandbox_id, diff_text=malicious_diff))
    default_manager.destroy_sandbox(sb.sandbox_id)


def test_run_tests_success(opt_in_manager):
    sb = opt_in_manager.create_sandbox(SandboxCreateRequest(repo_ref="pallets/flask"))
    run_req = TestRunRequest(
        sandbox_id=sb.sandbox_id,
        argv=["python", "-c", "print('hello from sandbox')"],
        timeout_seconds=10,
    )
    res = opt_in_manager.run_tests(run_req)
    assert res.exit_code == 0
    assert "hello from sandbox" in res.stdout
    assert res.timed_out is False
    assert res.duration_ms >= 0
    assert "label://UNSAFE_HOST_EXECUTION" in res.artifacts
    opt_in_manager.destroy_sandbox(sb.sandbox_id)


def test_run_tests_shell_injection_rejected(opt_in_manager):
    sb = opt_in_manager.create_sandbox(SandboxCreateRequest(repo_ref="pallets/flask"))
    with pytest.raises(InvalidRequestError):
        opt_in_manager.run_tests(TestRunRequest(
            sandbox_id=sb.sandbox_id,
            argv=["python", "-c", "test; rm -rf /"],
        ))
    opt_in_manager.destroy_sandbox(sb.sandbox_id)


def test_run_tests_timeout(opt_in_manager):
    sb = opt_in_manager.create_sandbox(SandboxCreateRequest(repo_ref="pallets/flask"))
    run_req = TestRunRequest(
        sandbox_id=sb.sandbox_id,
        argv=["python", "-c", "import time; time.sleep(5)"],
        timeout_seconds=1,
    )
    res = opt_in_manager.run_tests(run_req)
    assert res.timed_out is True
    assert res.exit_code == -1
    opt_in_manager.destroy_sandbox(sb.sandbox_id)


# ── New Fail-Closed Security & Escalation Tests ──────────────────────────────

def test_default_config_blocks_host_execution():
    """Assert default manager blocks command execution and never invokes subprocess.run."""
    manager = CodespacesSandboxManager(use_cloud_codespaces=False)
    assert manager.allow_unsafe_host_execution is False

    sb = manager.create_sandbox(SandboxCreateRequest(repo_ref="test/repo"))
    run_req = TestRunRequest(
        sandbox_id=sb.sandbox_id,
        argv=["python", "-c", "print('should not run')"],
    )

    with patch("subprocess.run") as mock_subproc:
        with pytest.raises(HostExecutionBlockedError) as exc_info:
            manager.run_tests(run_req)
        assert "Untrusted host execution blocked" in str(exc_info.value)
        mock_subproc.assert_not_called()

    manager.destroy_sandbox(sb.sandbox_id)


def test_request_payload_cannot_override_host_execution():
    """Verify extra payload fields in request schemas cannot enable host execution."""
    manager = CodespacesSandboxManager(use_cloud_codespaces=False, allow_unsafe_host_execution=False)
    sb = manager.create_sandbox(SandboxCreateRequest(
        repo_ref="test/repo",
        env_vars={"ALLOW_UNSAFE_HOST_EXECUTION": "true"},  # Attempt injection via env_vars
    ))
    run_req = TestRunRequest(
        sandbox_id=sb.sandbox_id,
        argv=["python", "-c", "print('should not run')"],
    )
    with pytest.raises(HostExecutionBlockedError):
        manager.run_tests(run_req)
    manager.destroy_sandbox(sb.sandbox_id)


def test_test_runner_node_returns_sandbox_unavailable():
    """Assert test_runner_node returns structured sandbox_unavailable under default config."""
    from app.agents.test_runner.agent import test_runner_node
    from app.agents.schemas import create_initial_state

    # Ensure default settings are used (ALLOW_UNSAFE_HOST_EXECUTION is False)
    with patch("app.sandbox.codespaces_manager.get_sandbox_manager") as mock_get_sb:
        mock_get_sb.return_value = CodespacesSandboxManager(allow_unsafe_host_execution=False)
        state = create_initial_state(issue_title="Test Issue", repo="owner/repo")
        result = test_runner_node(state)

    test_results = result.get("test_results")
    assert test_results["passed"] is False
    assert test_results["total_tests"] == 0
    assert test_results["failed_tests"] == 0
    assert test_results["infrastructure_failure"] is True
    assert test_results["sandbox_unavailable"] is True
    assert "sandbox_unavailable" in test_results["details"]
    assert result["status"] == "escalated"


def test_route_test_runner_escalates_on_sandbox_unavailable():
    """Assert route_test_runner routes to test_unverified_terminal, NEVER to debugger."""
    from app.agents.graph import route_test_runner, test_unverified_terminal_node
    from app.agents.schemas import TestResults

    state = {
        "test_results": TestResults(
            passed=False,
            total_tests=0,
            passed_tests=0,
            failed_tests=0,
            infrastructure_failure=True,
            sandbox_unavailable=True,
            details="sandbox_unavailable: Untrusted host execution blocked",
        ).model_dump(mode="json"),
        "retry_count": 0,
        "max_retries": 3,
        "events": [],
    }

    next_node = route_test_runner(state)
    assert next_node == "test_unverified_terminal"
    assert next_node != "debugger"

    terminal_output = test_unverified_terminal_node(state)
    assert terminal_output["status"] == "escalated"
    assert "Sandbox unavailable" in terminal_output["error"]
# ── Regression Tests: Legitimate Next.js/TS Syntax vs. Malicious Target Paths ──

def test_apply_diff_accepts_nextjs_catchall_spread_and_relative_imports(default_manager):
    """
    Legitimate TypeScript/Next.js diffs containing spread syntax (...err.rowData),
    relative imports (../schema/patientImportSchema), and catch-all route filenames
    (app/import/[...slug].tsx, app/api/import/[...].ts) must be accepted.
    """
    sb = default_manager.create_sandbox(SandboxCreateRequest(repo_ref="PUDUCAN-JIPMER/puducan-jipmer"))
    workspace = Path(default_manager._sandboxes[sb.sandbox_id]["workspace_path"])
    try:
        valid_ts_diff = (
            "--- a/lib/import/importUtils.ts\n"
            "+++ b/lib/import/importUtils.ts\n"
            "@@ -1,4 +1,12 @@\n"
            "+import { patientImportSchema } from '../schema/patientImportSchema'\n"
            "+export function formatErrors(errors: any[]) {\n"
            "+  return errors.map((err) => ({\n"
            "+    Row: err.row,\n"
            "+    ...err.rowData,\n"
            "+  }))\n"
            "+}\n"
            "--- /dev/null\n"
            "+++ b/app/import/[...slug].tsx\n"
            "@@ -0,0 +1,4 @@\n"
            "+export default function CatchAllImportPage() {\n"
            "+  return <div>Loading...</div>\n"
            "+}\n"
            "--- /dev/null\n"
            "+++ b/app/api/import/[...].ts\n"
            "@@ -0,0 +1,3 @@\n"
            "+export async function POST(req: Request) {\n"
            "+  return new Response('ok')\n"
            "+}\n"
        )
        resp = default_manager.apply_diff(DiffApplyRequest(sandbox_id=sb.sandbox_id, diff_text=valid_ts_diff))
        assert resp.success is True
        assert resp.applied_files == [
            "lib/import/importUtils.ts",
            "app/import/[...slug].tsx",
            "app/api/import/[...].ts",
        ]
        assert "...err.rowData" in (workspace / "lib/import/importUtils.ts").read_text(encoding="utf-8")
        assert "../schema/patientImportSchema" in (workspace / "lib/import/importUtils.ts").read_text(encoding="utf-8")
        assert (workspace / "app/import/[...slug].tsx").is_file()
        assert (workspace / "app/api/import/[...].ts").is_file()
    finally:
        default_manager.destroy_sandbox(sb.sandbox_id)


@pytest.mark.parametrize(
    "malicious_header_path",
    [
        "b/../../etc/passwd",
        "b/src/../../outside.py",
        "b/src\\..\\outside.py",
        "/etc/passwd",
        "b//etc/passwd",
        "C:\\Windows\\System32\\drivers\\etc\\hosts",
        "b/C:/Windows/win.ini",
        "D:evil.py",
        "\\\\evil-server\\share\\payload.py",
        "b/\\\\evil-server\\share\\payload.py",
        "//evil-server/share/payload.py",
        "b/.env",
        "b/.env.production",
        "b/.github/workflows/ci.yml",
        "b/.git/config",
        "b/certs/private.key",
    ],
)
def test_apply_diff_rejects_malicious_target_paths(default_manager, malicious_header_path):
    """
    Reject path traversal, Unix absolute paths, Windows drive/UNC paths,
    and protected denylisted files in diff headers.
    """
    sb = default_manager.create_sandbox(SandboxCreateRequest(repo_ref="pallets/flask"))
    try:
        bad_diff = (
            f"--- a/src/app.py\n"
            f"+++ {malicious_header_path}\n"
            f"@@ -1,1 +1,2 @@\n"
            f"+malicious_payload = True\n"
        )
        with pytest.raises(InvalidRequestError):
            default_manager.apply_diff(DiffApplyRequest(sandbox_id=sb.sandbox_id, diff_text=bad_diff))

        # Also test malicious source path in '---' header (e.g. file deletion)
        bad_source_diff = (
            f"--- {malicious_header_path}\n"
            f"+++ /dev/null\n"
            f"@@ -1,1 +0,0 @@\n"
            f"-deleted\n"
        )
        with pytest.raises(InvalidRequestError):
            default_manager.apply_diff(DiffApplyRequest(sandbox_id=sb.sandbox_id, diff_text=bad_source_diff))
    finally:
        default_manager.destroy_sandbox(sb.sandbox_id)


def test_apply_diff_rejects_symlink_mode_and_symlink_escapes(default_manager, tmp_path):
    """
    Reject diffs that attempt git symlink mode (120000) or traverse a symlinked
    directory/file pointing outside the sandbox workspace.
    """
    sb = default_manager.create_sandbox(SandboxCreateRequest(repo_ref="pallets/flask"))
    workspace = Path(default_manager._sandboxes[sb.sandbox_id]["workspace_path"])
    outside_dir = tmp_path / "outside_secret"
    outside_dir.mkdir(parents=True, exist_ok=True)
    outside_target = outside_dir / "escaped.py"
    try:
        # 1. Git symlink mode 120000 must be rejected
        symlink_mode_diff = (
            "diff --git a/src/link b/src/link\n"
            "new file mode 120000\n"
            "--- /dev/null\n"
            "+++ b/src/link\n"
            "@@ -0,0 +1 @@\n"
            "+/etc/passwd\n"
        )
        with pytest.raises(InvalidRequestError, match="symlink"):
            default_manager.apply_diff(DiffApplyRequest(sandbox_id=sb.sandbox_id, diff_text=symlink_mode_diff))

        # 2. Symlinked path component inside workspace must be rejected
        escape_diff = (
            "--- a/src/linked_dir/escaped.py\n"
            "+++ b/src/linked_dir/escaped.py\n"
            "@@ -0,0 +1 @@\n"
            "+pwned = True\n"
        )
        with patch("os.path.islink", side_effect=lambda p: Path(p).name == "linked_dir"):
            with pytest.raises(InvalidRequestError, match="symbolic link"):
                default_manager.apply_diff(DiffApplyRequest(sandbox_id=sb.sandbox_id, diff_text=escape_diff))

        assert not outside_target.exists()
    finally:
        default_manager.destroy_sandbox(sb.sandbox_id)


def test_rejected_multifile_patch_leaves_no_partial_changes_or_outside_writes(default_manager, tmp_path):
    """
    When a multi-file diff contains one valid file and one invalid/traversal file,
    the entire patch must be rejected upfront without modifying the valid file
    or writing anything outside the workspace.
    """
    sb = default_manager.create_sandbox(SandboxCreateRequest(repo_ref="pallets/flask"))
    workspace = Path(default_manager._sandboxes[sb.sandbox_id]["workspace_path"])
    valid_file = workspace / "src" / "safe.py"
    valid_file.write_text("original = True\n", encoding="utf-8")
    outside_file = workspace.parent / "escaped_outside.py"
    if outside_file.exists():
        outside_file.unlink()

    try:
        mixed_diff = (
            "--- a/src/safe.py\n"
            "+++ b/src/safe.py\n"
            "@@ -1,1 +1,2 @@\n"
            " original = True\n"
            "+modified = True\n"
            "--- /dev/null\n"
            "+++ b/../escaped_outside.py\n"
            "@@ -0,0 +1,1 @@\n"
            "+escaped = True\n"
        )
        with pytest.raises(InvalidRequestError):
            default_manager.apply_diff(DiffApplyRequest(sandbox_id=sb.sandbox_id, diff_text=mixed_diff))

        # Valid file inside workspace must remain untouched (no partial changes)
        assert valid_file.read_text(encoding="utf-8") == "original = True\n"
        # File outside workspace must not be created
        assert not outside_file.exists()
        # Temporary change.patch must not exist
        assert not (workspace / "change.patch").exists()
    finally:
        default_manager.destroy_sandbox(sb.sandbox_id)
