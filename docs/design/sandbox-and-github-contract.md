# Sandbox and GitHub Interface Contract

This document defines the required interface for the Sandbox and GitHub integrations to support the Mini-Devin agent pipeline.

## 1. Sandbox Interface
**Purpose:** Provide an isolated, ephemeral environment to apply patches and run verification tests without risking the host system.

### Proposed API
```python
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Literal

class SandboxCreateRequest(BaseModel):
    repo_ref: str  # e.g., "owner/repo@sha"
    timeout_seconds: int = 300
    # Only a whitelist of non-secret, non-privileged env vars allowed
    env_vars: Dict[str, str] = Field(default_factory=dict)

class SandboxCreateResponse(BaseModel):
    sandbox_id: str
    status: str
    # A stable reference to the workspace; internal host paths MUST NOT be exposed
    workspace_ref: str

class DiffApplyRequest(BaseModel):
    sandbox_id: str
    diff_text: str

class DiffApplyResponse(BaseModel):
    success: bool
    error: Optional[str] = None

class TestRunRequest(BaseModel):
    sandbox_id: str
    argv: List[str]  # Argument list to prevent shell injection
    cwd: str = "/workspace"
    timeout_seconds: int = 60

class TestRunResponse(BaseModel):
    exit_code: int
    stdout: str  # Size-capped (e.g., 1MB)
    stderr: str  # Size-capped (e.g., 1MB)
    duration_ms: int
    timed_out: bool
    artifacts: List[str] # Reference IDs for logs/coverage; no host paths

class SandboxError(Exception):
    """Base for: TimeoutError, SandboxUnavailableError, DiffApplyFailedError, InvalidRequestError"""
```

### Operation Details
| Operation | Consumer | Owner | Input | Output | Validation | Errors | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Create** | Planner/Svc | SandboxMngr | `SandboxCreateRequest` | `SandboxCreateResponse` | Valid `repo_ref` | `SandboxUnavailableError` | Proposed |
| **Apply Diff**| Coder/Svc | SandboxMngr | `DiffApplyRequest` | `DiffApplyResponse` | Valid `sandbox_id` | `DiffApplyFailedError` | Proposed |
| **Run Test** | TestRunner | SandboxMngr | `TestRunRequest` | `TestRunResponse` | Path $\neq$ host root | `TimeoutError`, `InvalidRequestError` | Proposed |
| **Destroy** | Svc/Cleanup | SandboxMngr | `sandbox_id: str` | `bool` (success) | Idempotent check | `SandboxUnavailableError` | Proposed |

**Lifecycle & Timeout Logic:**
- **Timeout:** If `timed_out: True`, the system must send a `SIGKILL` to the process group, capture whatever `stdout`/`stderr` was buffered, and mark the sandbox for immediate cleanup.
- **Cleanup:** Destruction of a sandbox is idempotent; destroying a missing or already destroyed sandbox returns `success: True`.
- **Failure:** If termination or cleanup fails, the system must log a critical infrastructure error and alert the orchestrator.
- **Host Boundary:** No host paths allowed in requests or responses. All access is via `sandbox_id` or `workspace_ref`.

---

## 2. GitHub Interface
**Purpose:** Manage repository state and facilitate the transition from local verification to a formal pull request.

### Proposed API
```python
from pydantic import BaseModel, Field
from typing import List, Optional, Literal

class GitRef(BaseModel):
    owner: str
    repo: str
    sha: Optional[str] = None
    branch: Optional[str] = None

class FileChange(BaseModel):
    path: str
    # Required for 'create' and 'modify', must be None for 'delete'
    content: Optional[str] = None 
    action: Literal["create", "modify", "delete"]

class PRRequest(BaseModel):
    ref: GitRef
    title: str
    body: str
    head_branch: str
    base_branch: str = "main"

class PRResponse(BaseModel):
    pr_url: str
    pr_number: int

# Interface Methods
def fetch_repo(ref: GitRef) -> str: 
    """Read-only clone/fetch. Returns a stable workspace reference (not a path)."""
    ...

def read_file(ref: GitRef, path: str) -> str:
    """Read specific file content. Validates path to prevent traversal."""
    ...

def create_branch(ref: GitRef, branch_name: str) -> bool:
    """Creates a new branch on remote from ref. Validates branch name."""
    ...

def push_changes(ref: GitRef, branch_name: str, changes: List[FileChange]) -> bool:
    """Pushes modified files. MUST NOT push to main/default."""
    ...

def open_pull_request(request: PRRequest, auth_token: str) -> PRResponse:
    """
    Opens PR. Validates auth_token against a trusted internal secret.
    """
    ...
```

### Operation Details
| Operation | Consumer | Owner | Input | Output | Validation | Errors | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Fetch** | Retrieval | GHClient | `GitRef` | `workspace_ref: str` | Valid `repo` | `RepoNotFoundError` | Proposed |
| **Read File**| Retrieval/Coder| GHClient | `GitRef`, `path` | `content: str` | Path traversal check | `FileNotFoundError` | Proposed |
| **Branch** | PR Agent | GHClient | `GitRef`, `name` | `bool` | Name regex | `BranchExistsError` | Proposed |
| **Push** | PR Agent | GHClient | `GitRef`, `name`, `List[FileChange]` | `bool` | Branch $\neq$ main | `PermissionError` | Proposed |
| **Open PR** | PR Agent | GHClient | `PRRequest`, `auth_token` | `PRResponse` | Auth check, Ref check | `PermissionError` | Proposed |

**Constraints:**
- **Permissions:** Strictly separate Read (fetch/read) and Write (push/PR) scopes.
- **Auth Contract:** Authorization must not depend on a caller-supplied Boolean. It requires a token bound to (repo, branch, operation, expiry). Fail closed if absent, invalid, expired, or mismatched.
- **Integrity:** Mini-Devin must never commit directly to the default branch (`main`). Human review and merge remain mandatory.
- **Sanitization:** All repository names, branch names, and paths must be validated to prevent path traversal and injection.

---

## 3. Open Decisions
- **D5 (Coder Tooling):** Whether the Coder's file-view/edit tools operate on the host's cloned repo or inside the sandbox.
- **D6 (Sandbox Lifecycle):** Whether a sandbox is created per-run or per-agent, and if it is reused across Debugger $\rightarrow$ Coder $\rightarrow$ Test-Runner retry loops.
- **D7 (Reviewer Linter):** Whether the static analysis/linter pass runs on the host (via local tools) or inside the sandbox.
- **D8 (Dependency Policy):** How dependencies (pip/npm) are installed in the sandbox.
- **D9 (Auth Mechanism):** The specific trusted mechanism for generating and validating the `auth_token` for PR creation.
- **D10 (Secret Injection):** How required build-time secrets are safely injected into the sandbox.

---

## 4. Scenario Matrix

| Scenario | Input | Expected Outcome | Error/Response |
| :--- | :--- | :--- | :--- |
| **Success Run** | Valid Diff $\rightarrow$ Valid Cmd | `exit_code: 0` | `stdout` captured |
| **Test Failure** | Valid Diff $\rightarrow$ Failing Test | `exit_code: != 0` | `stderr` captured |
| **Timeout** | Long running command | `timed_out: True` | `SandboxError(Timeout)` |
| **Path Traversal** | `cwd: "/etc/passwd"` | `Failure` | `InvalidRequestError` |
| **Destructive Cmd**| `argv: ["rm", "-rf", "/"]` | `success: False` | `InvalidRequestError` or restricted |
| **Output Overflow** | Command producing 10GB log | `stdout` truncated | `stdout` capped at 1MB |
| **Cleanup Failure** | `destroy()` on missing ID | `success: True` | Idempotent |
| **Unauthorized PR**| PRRequest without token | `Failure` | `PermissionError` |
| **Direct Push** | `push_changes` to `main` | `Failure` | `PermissionError` |
| **Invalid Ref** | `GitRef(repo="nonexistent")`| `Failure` | `GitHubClientError` |

---

## 5. Stubbing for Tests
- **Sandbox:** Use a `MockSandboxManager` that records `apply_diff` calls and returns pre-defined `TestRunResponse` objects based on the command string.
- **GitHub:** Use a `MockGitHubClient` that simulates API responses and tracks created branches/PRs in an in-memory dictionary.

---

## 6. What to tell Tamanna
1. **Sandbox:** Update `run_tests` to accept `argv: List[str]` and return `duration_ms`, `timed_out`, and artifact refs.
2. **GitHub:** Implement `read_file` and `push_changes` (with `FileChange` model).
3. **PR Auth:** Update `open_pull_request` to require a trusted `auth_token` rather than a boolean.
4. **Types:** Align return types with the Pydantic schemas in this contract.
