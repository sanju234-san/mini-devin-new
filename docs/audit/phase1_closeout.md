# Mini-Devin Phase 1 Close-Out Report: Evidence, Hygiene & Final Accounting

**Date:** 2026-10-25  
**Auditor / Principal Engineer:** Antigravity  
**Specification:** Phase 1 Close-Out Directives  
**Target File:** `docs/audit/phase1_closeout.md`  
**Status:** **PHASE 1 CLOSE-OUT COMPLETE — STOPPING AT GATE**

---

## 1. Tool Accounting: Discovered Tools & Missing Tool Analysis

A clean re-discovery was executed against the GitHub Model Context Protocol server over `stdio`. The server returns **26 total tools**.

### Discrepancy Reconciliation
In the initial `phase1_report.md` draft, the text stated 14 read-only tools and 12 write tools (26 total), but the markdown table listed only 13 read tools + 12 write tools (25 total).
- **Missing Tool Identified:** `search_users` ("Search for users on GitHub").
- **Policy Classification:** **READ-ONLY ALLOWLIST**. `search_users` is a read-only query tool with no repository or state mutation capabilities.
- **Remediation:**
  1. `search_users` was added to `READ_ONLY_TOOL_ALLOWLIST` in `backend/app/integrations/mcp_client.py`.
  2. `search_users` was added to the summary table in `docs/audit/phase1_report.md`.
  3. Added `test_all_discovered_tools_classified_and_allowlist_length` in `backend/tests/integrations/test_mcp_client.py` asserting that all 26 discovered tools are disjointly partitioned (14 read, 12 write) with zero unclassified tools.

### Complete Table of All 26 Discovered Tools

| # | Tool Name | Classification | In-Code Policy Action | Description |
|---|---|---|---|---|
| 1 | `get_issue` | Read | **ALLOWLISTED** | Get details of a specific issue in a GitHub repository |
| 2 | `get_file_contents` | Read | **ALLOWLISTED** | Get the contents of a file or directory from a GitHub repository |
| 3 | `list_commits` | Read | **ALLOWLISTED** | Get list of commits of a branch in a GitHub repository |
| 4 | `search_code` | Read | **ALLOWLISTED** | Search for code across GitHub repositories |
| 5 | `search_issues` | Read | **ALLOWLISTED** | Search for issues and pull requests across GitHub repositories |
| 6 | `search_repositories` | Read | **ALLOWLISTED** | Search for GitHub repositories |
| 7 | `search_users` | Read | **ALLOWLISTED** | Search for users on GitHub |
| 8 | `list_issues` | Read | **ALLOWLISTED** | List issues in a GitHub repository with filtering options |
| 9 | `list_pull_requests` | Read | **ALLOWLISTED** | List and filter repository pull requests |
| 10 | `get_pull_request` | Read | **ALLOWLISTED** | Get details of a specific pull request |
| 11 | `get_pull_request_files` | Read | **ALLOWLISTED** | Get the list of files changed in a pull request |
| 12 | `get_pull_request_status` | Read | **ALLOWLISTED** | Get the combined status of all status checks for a pull request |
| 13 | `get_pull_request_comments` | Read | **ALLOWLISTED** | Get the review comments on a pull request |
| 14 | `get_pull_request_reviews` | Read | **ALLOWLISTED** | Get the reviews on a pull request |
| 15 | `create_or_update_file` | Write | **DENIED / BLOCKED** | Create or update a single file in a GitHub repository |
| 16 | `create_repository` | Write | **DENIED / BLOCKED** | Create a new GitHub repository in your account |
| 17 | `push_files` | Write | **DENIED / BLOCKED** | Push multiple files to a GitHub repository in a single commit |
| 18 | `create_issue` | Write | **DENIED / BLOCKED** | Create a new issue in a GitHub repository |
| 19 | `create_pull_request` | Write | **DENIED / BLOCKED** | Create a new pull request in a GitHub repository |
| 20 | `fork_repository` | Write | **DENIED / BLOCKED** | Fork a GitHub repository to your account or specified organization |
| 21 | `create_branch` | Write | **DENIED / BLOCKED** | Create a new branch in a GitHub repository |
| 22 | `update_issue` | Write | **DENIED / BLOCKED** | Update an existing issue in a GitHub repository |
| 23 | `add_issue_comment` | Write | **DENIED / BLOCKED** | Add a comment to an existing issue |
| 24 | `create_pull_request_review`| Write | **DENIED / BLOCKED** | Create a review on a pull request |
| 25 | `merge_pull_request` | Write | **DENIED / BLOCKED** | Merge a pull request |
| 26 | `update_pull_request_branch`| Write | **DENIED / BLOCKED** | Update a pull request branch with latest changes from base |
| * | *Any Unlisted Tool* | Unknown | **DENIED / BLOCKED** | Raises `MCPToolBlockedError` by default |

---

## 2. MCP Server Pinning & Official Upstream Analysis

### Pinned Server Details
- **Configuration Parameter:** `Settings.GITHUB_MCP_PACKAGE` in `backend/app/config.py`
- **Pinned Package Specifier:** `@modelcontextprotocol/server-github@2025.4.8`
- **Reported Server Name (`initialize()`):** `github-mcp-server`
- **Reported Server Internal Version:** `0.6.2`
- **Protocol Version:** `2024-11-05`
- **Config Alias:** Added `GITHUB_MCP_PACKAGE` to `_PLAIN_ALIASES` in `backend/app/config.py` so downstream code and tests can configure it without hardcoding.

### Server Provenance & Maintenance Status
- **Observed NPM Package Metadata (`npm view @modelcontextprotocol/server-github`):**
  - **Maintainers:** `jspahrsummers`, `pcarleton`, `fweinberger`, `thedsp`, `ochafik-ant`, `cliffhall` (Anthropic / Model Context Protocol reference team).
  - **Notice:** `DEPRECATED!! - Package no longer supported. Contact Support at https://www.npmjs.com/support for more info.`
  - **Status:** This package is the initial reference implementation created by the Model Context Protocol core team. It is stable and functional over `stdio` in this environment (providing all 26 tools), but is no longer actively receiving new features from Anthropic.
- **Actively Maintained Alternative (Official GitHub Server):**
  - GitHub maintains their own official server: [`github/github-mcp-server`](https://github.com/github/github-mcp-server).
  - It is written in Go, distributed as a container (`ghcr.io/github/github-mcp-server`) and prebuilt multi-platform binaries.
  - **Recommendation:** We recommend evaluating `github/github-mcp-server` as part of Phase 2 once Docker infrastructure is in place. Per strict instructions, **we have NOT switched to it** and will await explicit user gate approval before changing the server implementation.

---

## 3. Live Snapshot Evidence

### Live Verification Run
A live read-only MCP snapshot was executed against a verified public repository with shallow-clone fallback explicitly disabled (`allow_shallow_clone_fallback=False`):
- **Target Repository:** [`octocat/Hello-World`](https://github.com/octocat/Hello-World)
- **Ref / Branch:** `master`
- **Transport:** Node.js `stdio` (`github-mcp-server` v0.6.2)
- **Result:** **SUCCESS**
  - **Resolved Commit SHA:** `7fd1a60b01f91b314f59955a4e4d4e80d8edf11d`
  - **Files Downloaded:** 1 (`README`, 13 bytes, containing `"Hello World!\n"`)
  - **Total Snapshot Bytes:** 13 bytes
  - **Excluded Files:** 0 (clean repository; `.git` not pulled)
  - **Duration:** 647 ms
  - **Truncation:** `is_truncated: false`, `truncation_reason: null`
  - **Cache Verification:** A subsequent call for `octocat/Hello-World` resolved the commit SHA and returned the cached directory instantly without issuing redundant MCP fetch calls.

### Truncation Handling & State Visibility
- **Limit Configuration:**
  - `MAX_SNAPSHOT_FILES`: 250 files
  - `MAX_FILE_BYTES`: 512 KB per file
  - `MAX_TOTAL_SNAPSHOT_BYTES`: 20 MB
  - `MAX_TREE_DEPTH`: 8 levels
- **Handling When Limits Exceeded:**
  - Previously, truncation halted directory traversal silently.
  - **Updated Implementation:**
    1. `RepositorySnapshotService` now sets `is_truncated = True` and records `truncation_reason` (`"max_files_exceeded"`, `"max_total_bytes_exceeded"`, or `"max_files_or_depth_reached"`).
    2. Written to `snapshot_metadata.json` alongside commit SHA.
    3. `AgentState` now contains explicit tracking fields:
       - `snapshot_truncated: bool` (default `False`)
       - `snapshot_truncation_reason: Optional[str]` (default `None`)
    4. `issue_intake.py` populates these state fields and logs a warning.
    5. `retrieval_node` detects `snapshot_truncated` and appends a visible warning to `retrieved_context["summary"]`:
       `[WARNING: Repository snapshot was truncated ({reason}); search executed on partial codebase.]`
    6. Verified with automated test: `backend/tests/integrations/test_repo_snapshot.py::test_snapshot_truncation_is_flagged_in_metadata_and_state`.

---

## 4. Corrected Integration Status Table

| Component | Status | Verification Evidence |
|---|---|---|
| **Host-Execution Guard** | **LIVE-VERIFIED** | Default `ALLOW_UNSAFE_HOST_EXECUTION=False` blocks execution in `CodespacesSandboxManager`; raises `HostExecutionBlockedError`; `test_runner_node` returns `sandbox_unavailable=True`; routes to `test_unverified_terminal` (10/10 passed in `test_codespaces_manager.py`). |
| **GitHub MCP Client** | **LIVE-VERIFIED** | Connected over `stdio` to `github-mcp-server` (pinned package `@modelcontextprotocol/server-github@2025.4.8`). Live calls executed against `pallets/flask#5000` (issue details) and `octocat/Hello-World` (file contents & tree). 14 read tools allowlisted; 12 write tools denied; unclassified tools blocked (9/9 passed in `test_mcp_client.py`). |
| **Issue Intake Service** | **LIVE-VERIFIED** | Validates issue URLs; rejects PR URLs before MCP; fetches real issue body/title via MCP; halts before Triage on error; runs input guardrails; preserves free-text intake (8/8 passed in `test_issue_intake.py`). |
| **Repository Snapshot Service** | **LIVE-VERIFIED** | Live fetch of `octocat/Hello-World` created real snapshot (`commit_sha: 7fd1a60b01f91b314f59955a4e4d4e80d8edf11d`, 1 file, 13 bytes). Metadata records SHA and truncation flag. Path traversal and symlinks rejected (4/4 passed in `test_repo_snapshot.py`). |
| **Triage Fail-Closed Confidence**| **LIVE-VERIFIED** | Sparse input (`"Fix defect reported in #12345 for pallets/flask"`) triggers `confidence=0.377 < 0.60`; returns `triage_uncertain` and halts workflow at Triage. |
| **Docker Sandbox Container** | **ABSENT** (Scoped Phase 2) | Intentionally not implemented in Phase 1 per prompt instructions. Host execution remains fail-closed. |
| **PR Agent (Write Operations)** | **MOCKED** | Write operations remain stubbed/mocked in compliance with global read-only rules. |

---

## 5. Test Accounting & Reconciliation

### Baseline & Final Counts
- **Phase 0 Baseline (Ground Truth):** **452 passed, 0 failed, 0 skipped** (collected 452 items in `backend/tests`).
  *(Note: The "2 skipped" mentioned in previous notes was an erroneous recollection; `backend/tests` has always run 0 skipped).*
- **Phase 1 Final Count (`backend/tests`):** **477 passed, 0 failed, 0 skipped** (collected 477 items).
- **Net Increase:** Exactly **+25 passed tests**.

### Per-File Breakdown of New Tests (Collected via `pytest --collect-only`)
| Test File | New Tests Added | Total Collected in File | Description |
|---|---|---|---|
| `backend/tests/sandbox/test_codespaces_manager.py` | **+4** | 10 | 6 tests existed in Phase 0; 4 added in Phase 1A (fail-closed default, payload injection guard, structured escalation, routing) |
| `backend/tests/integrations/test_mcp_client.py` | **+9** | 9 | Stdio launch, 14 read tools allowlisted, 12 write tools denied, unknown blocked, token redaction, 404/403 mapping, retries, exhaustive 26-tool classification test |
| `backend/tests/integrations/test_repo_snapshot.py` | **+4** | 4 | Bounds enforcement, path traversal rejection, SHA caching, and snapshot truncation metadata test |
| `backend/tests/integrations/test_issue_intake.py` | **+8** | 8 | Issue URL regex validation, PR URL rejection, 404 error mapping, free-text intake, prompt injection guardrail, triage uncertainty regression |
| **Total New Tests** | **+25** | **31** | **452 baseline + 25 new tests = 477 passed** |

### Actual Test Suite Execution Output
```powershell
$ python -m pytest backend/tests -q
........................................................................ [ 15%]
........................................................................ [ 30%]
........................................................................ [ 45%]
........................................................................ [ 60%]
........................................................................ [ 75%]
........................................................................ [ 90%]
.............................................                            [100%]
477 passed, 7 warnings in 68.89s (0:01:08)
```

---

## 6. Fixture Scope & Isolation Evidence

The autouse opt-in fixture for `ALLOW_UNSAFE_HOST_EXECUTION` was inspected to ensure strict isolation:
1. **Locations:**
   - `backend/tests/agents/test_graph.py:56-63` (`enable_opt_in_sandbox_for_graph_tests`)
   - `backend/tests/planner/test_planner.py:43-50` (`enable_opt_in_sandbox_for_planner_tests`)
   - `backend/tests/system/test_st_scenarios.py:52-59` (`enable_opt_in_sandbox_for_st`)
2. **Scope:** Default pytest fixture scope: **`function`**.
3. **Implementation:**
   ```python
   @pytest.fixture(autouse=True)
   def enable_opt_in_sandbox_for_graph_tests(monkeypatch: pytest.MonkeyPatch):
       """Enable explicit opt-in host execution for graph pipeline unit tests."""
       from app.config import get_settings
       monkeypatch.setenv("ALLOW_UNSAFE_HOST_EXECUTION", "true")
       get_settings.cache_clear()
       yield
       get_settings.cache_clear()
   ```
4. **Isolation Verification:**
   - Defined solely inside the three specific test modules; **NOT defined in any shared `conftest.py`**.
   - `monkeypatch.setenv()` restores the environment variable immediately upon test completion.
   - `get_settings.cache_clear()` ensures settings cache does not leak across tests.
   - All tests in these modules execute exclusively against local temporary directories (`tmp_path`) or fake fixtures; **zero network clones or remote fetches are executed**.

---

## 7. Configuration Safety Check

- **`.env`:** `ALLOW_UNSAFE_HOST_EXECUTION` is **UNSET** (empty / absent).
- **`.env.example`:** `ALLOW_UNSAFE_HOST_EXECUTION` is **UNSET** (absent).
- **`backend/app/config.py`:** Shipped default is hardcoded to **`False`** (`ALLOW_UNSAFE_HOST_EXECUTION: bool = False`).
- **Assertion:** Verified by `backend/tests/test_config.py:27` (`assert s.ALLOW_UNSAFE_HOST_EXECUTION is False`).

---

## 8. Remaining Items & Phase 2 Gate Scope

The following items are intentionally scoped for Phase 2 and remain in their declared states:
1. **Docker Sandbox Execution (Phase 2):** Test execution remains fail-closed by default. Isolated Docker container management (`backend/app/sandbox/docker_manager.py`) is scheduled for Phase 2.
2. **PR Agent Write Operations:** In accordance with the global read-only rule, pull request writes remain simulated/mocked.
3. **MCP Server Recommendation:** Transition to GitHub's native Go-based server (`github/github-mcp-server`) recommended for Phase 2 evaluation.

---
**END OF PHASE 1 CLOSE-OUT — STOPPING AT GATE AWAITING USER CONFIRMATION**
