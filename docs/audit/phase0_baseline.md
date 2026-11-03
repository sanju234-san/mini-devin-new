# Phase 0: Baseline Architecture and Verification Audit

**Document Path:** `docs/audit/phase0_baseline.md`  
**Phase:** Phase 0 (Baseline Audit)  
**Status:** COMPLETE — Gate Awaiting User Confirmation  
**Execution Context:** Windows · Python 3.10.11 · Read-Only Verification  
**Repository State:** Preserved uncommitted changes from branch `wip/agents-checkpoint` (see Section 6)  

---

## 1. Executive Summary & Ground Truth

| Component | Intended Architecture (Synopsis) | Actual Implementation in Repository | Ground Truth Status |
| :--- | :--- | :--- | :--- |
| **Chainlit Frontend** | Interactive agent console driving autonomous runs via FastAPI or workflow engine | Directly imports and executes compiled LangGraph workflow in-process via `graph.ainvoke()` ([`chainlit_console/app.py:396`](file:///c:/Users/sanje/OneDrive/Desktop/Minor%20Project/mini-devin/chainlit_console/app.py#L396)). Does **not** call FastAPI over HTTP. | **LIVE (In-Process LangGraph)** |
| **FastAPI Backend** | REST API for issue ingestion, webhook handling, and run management | Fully created via `create_app()` ([`backend/app/main.py:151`](file:///c:/Users/sanje/OneDrive/Desktop/Minor%20Project/mini-devin/backend/app/main.py#L151)). Binds `LangGraphAgentGateway` as active gateway ([`main.py:171`](file:///c:/Users/sanje/OneDrive/Desktop/Minor%20Project/mini-devin/backend/app/main.py#L171)). Disconnected from Chainlit. | **DISCONNECTED ENTRYPOINT** |
| **Graph Topology** | Single unified 8-agent workflow with intake, triage, and human approval | Two divergent graphs exist: production `create_workflow_graph` (`AgentState`, `START -> triage`) and legacy `build_graph` (`RunState`, `START -> intake -> guardrails`). | **DUAL DIVERGENT GRAPHS** |
| **GitHub Integration** | Model Context Protocol (MCP) server/client for issue & repo context | `backend/app/integrations/mcp_client.py` is a 2-line empty stub. GitHub access uses REST via `httpx` in [`github_client.py`](file:///c:/Users/sanje/OneDrive/Desktop/Minor%20Project/mini-devin/backend/app/integrations/github_client.py) or in-memory dict mocks. | **MCP ABSENT / REST IMPLEMENTED** |
| **Issue Intake Data** | Live issue title, body, comments, and labels fetched via GitHub API | Chainlit URL intake parses regex and fabricates static placeholder strings without calling GitHub API ([`chainlit_console/app.py:105-113`](file:///c:/Users/sanje/OneDrive/Desktop/Minor%20Project/mini-devin/chainlit_console/app.py#L105-L113)). | **SIMULATED / SYNTHETIC** |
| **Repo Source Retrieval** | Clones/checks out repository commit into sandbox workspace | `resolve_permitted_repo_path()` rejects remote slugs unless directory exists locally. Reports `missing_checkout` ([`retrieval/agent.py:62`](file:///c:/Users/sanje/OneDrive/Desktop/Minor%20Project/mini-devin/backend/app/agents/retrieval/agent.py#L62)). | **DISCONNECTED CHECKOUT** |
| **Sandbox Environment** | Ephemeral, isolated Docker sandbox container (or E2B microVM) | `docker_manager.py` and `e2b_manager.py` are 2-line empty stubs. `get_sandbox_manager()` returns `CodespacesSandboxManager`, which defaults to creating a local temp directory and running `subprocess.run()` on the host ([`codespaces_manager.py:111-170`](file:///c:/Users/sanje/OneDrive/Desktop/Minor%20Project/mini-devin/backend/app/sandbox/codespaces_manager.py#L111-L170)). | **STUB (Host Subprocess Fallback)** |
| **Checkpointer & State** | Stateful persistence surviving restarts | In-memory `MemorySaver` ([`checkpointer.py:35`](file:///c:/Users/sanje/OneDrive/Desktop/Minor%20Project/mini-devin/backend/app/agents/checkpointer.py#L35)) and `InMemoryRunStore` ([`run_store.py:23`](file:///c:/Users/sanje/OneDrive/Desktop/Minor%20Project/mini-devin/backend/app/api/run_store.py#L23)). Zero persistence across process restarts. | **IN-MEMORY ONLY** |
| **Provider Fallback** | Groq primary -> Gemini on 429 -> Hugging Face fallback | Implemented in [`llm_provider_client.py`](file:///c:/Users/sanje/OneDrive/Desktop/Minor%20Project/mini-devin/backend/app/integrations/llm_provider_client.py). Catches all `Exception` blindly; no delay/backoff; live cloud endpoints currently fail due to model ID / task mismatches, falling back to deterministic synthesis. | **IMPLEMENTED-UNVERIFIED (Cloud 404s)** |
| **Observability / Tracing** | Self-hosted MLflow tracing per agent step and tool invocation | `mlflow_tracing.py` implements `@trace_agent_step`. Falls back gracefully to in-memory audit log `_AUDIT_LOGS` when MLflow server is offline. | **LIVE (Fallback In-Memory Trail)** |

---

## 2. Stage-by-Stage Traceability Matrix

| Stage | Entry File / Function | Input | Tools / APIs Called | Output | State Fields Updated | Next Node | Error Behaviour | Proving Test | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **1. Intake (Chainlit)** | [`chainlit_console/app.py:parse_issue_input`](file:///c:/Users/sanje/OneDrive/Desktop/Minor%20Project/mini-devin/chainlit_console/app.py#L95) | User chat message | Regex `_GITHUB_ISSUE_RE` | `(repo, title, body, url, number)` | `issue_title`, `issue_body`, `repo`, `issue_url`, `issue_number` | `triage` | Catches exceptions, returns UI error message | Manual verification | **LIVE (Simulated Data)** |
| **2. Intake (FastAPI)** | [`backend/app/api/issues.py:ingest_issue`](file:///c:/Users/sanje/OneDrive/Desktop/Minor%20Project/mini-devin/backend/app/api/issues.py#L27) | `IssueIn` JSON payload | `RunStore.create_run`, `BackgroundTasks` | `RunSummary` (202 Accepted) | Creates run in `RunStore` | `LangGraphAgentGateway.start_run` | Logs error, updates status to `failed` | `backend/tests/test_api_runs.py` | **LIVE-VERIFIED (REST)** |
| **3. Input Guardrails** | [`backend/app/guardrails/input_guardrails.py:validate_and_sanitize_issue`](file:///c:/Users/sanje/OneDrive/Desktop/Minor%20Project/mini-devin/backend/app/guardrails/input_guardrails.py#L1) | `title`, `body` | Regex injection scanners, HTML tag sanitizers | Clean strings + `is_suspicious` boolean | Evaluated inside `triage_node` | N/A | Flags `is_suspicious=True`, halts at triage | `backend/tests/agents/test_triage.py` | **LIVE-VERIFIED** |
| **4. GitHub Issue Fetch** | *None* | `issue_url` | None | None | None | N/A | Bypassed; invents placeholder strings | *None* | **ABSENT** |
| **5. Repo Checkout** | *None* | `repo` slug | None | None | None | N/A | Bypassed; requires existing local directory | *None* | **ABSENT / DISCONNECTED** |
| **6. Triage Agent** | [`backend/app/agents/triage/agent.py:triage_node`](file:///c:/Users/sanje/OneDrive/Desktop/Minor%20Project/mini-devin/backend/app/agents/triage/agent.py#L167) | `issue_title`, `issue_body`, `repo` | `classify_with_confidence()` (`triage_pipeline.joblib`) | `TriageResult` | `triage`, `cleaned_query`, `status`, `events` | `safe_stop` (if unsupported) or `retrieval` | Sets `is_supported=False`, halts at `safe_stop` | `backend/tests/agents/test_triage_agent.py` | **LIVE-VERIFIED (ML Pipeline)** |
| **7. Safe Stop** | [`backend/app/agents/graph.py:safe_stop_node`](file:///c:/Users/sanje/OneDrive/Desktop/Minor%20Project/mini-devin/backend/app/agents/graph.py#L81) | `triage` | None | Event record | `status="out_of_scope"`, `events` | `END` | Clean terminal node | `backend/tests/agents/test_graph.py` | **LIVE-VERIFIED** |
| **8. Retrieval Agent** | [`backend/app/agents/retrieval/agent.py:retrieval_node`](file:///c:/Users/sanje/OneDrive/Desktop/Minor%20Project/mini-devin/backend/app/agents/retrieval/agent.py#L40) | `cleaned_query`, `repo` | `resolve_permitted_repo_path`, `RepositoryIndexer.search`, `transform_query` | `RetrievedContext` | `retrieved_context`, `status`, `events` | `planner` | Reports `missing_checkout` if directory absent | `backend/tests/retrieval/test_retrieval.py` | **IMPLEMENTED-UNVERIFIED** |
| **9. Planner Agent** | [`backend/app/agents/planner/agent.py:planner_node`](file:///c:/Users/sanje/OneDrive/Desktop/Minor%20Project/mini-devin/backend/app/agents/planner/agent.py#L540) | `issue_title`, `retrieved_context` | `try_llm_plan_generation`, `synthesize_deterministic_plan`, `compute_plan_hash` | `ImplementationPlan` | `plan`, `plan_hash`, `plan_version`, `status="awaiting_approval"` | `human_approval` | Falls back to deterministic plan synthesis | `backend/tests/planner/test_planner.py` | **LIVE-VERIFIED (Deterministic Fallback)** |
| **10. HITL Approval** | [`backend/app/agents/graph.py:human_approval_node`](file:///c:/Users/sanje/OneDrive/Desktop/Minor%20Project/mini-devin/backend/app/agents/graph.py#L106) | `plan`, `plan_hash` | LangGraph `interrupt()` | `ApprovalDecision` | `human_approval`, `status="approved"/"rejected"` | `coder` (if approved) or `rejection_terminal` | Rejects plan if hash is tampered or unapproved | `backend/tests/planner/test_planner.py` | **LIVE-VERIFIED (Interrupt/Resume)** |
| **11. Coder Agent** | [`backend/app/agents/coder/agent.py:coder_node`](file:///c:/Users/sanje/OneDrive/Desktop/Minor%20Project/mini-devin/backend/app/agents/coder/agent.py#L121) | `human_approval`, `plan`, `plan_hash` | `model_router.complete()`, `validate_diff_safety`, `synthesize_deterministic_diff` | `Diff` | `code_changes`, `deviation_log`, `status="coding"` | `test_runner` | Fails closed on hash mismatch or safety violations; falls back to deterministic patch | `backend/tests/coder/test_coder.py` | **LIVE-VERIFIED (Deterministic Fallback)** |
| **12. Test-Runner** | [`backend/app/agents/test_runner/agent.py:test_runner_node`](file:///c:/Users/sanje/OneDrive/Desktop/Minor%20Project/mini-devin/backend/app/agents/test_runner/agent.py#L24) | `code_changes`, `repo` | `get_sandbox_manager()` (`CodespacesSandboxManager.run_tests`) | `TestResults` | `test_results`, `status` | `reviewer` (pass) or `debugger` (fail) | Sets `passed=False` on failure; halts at `test_unverified_terminal` in strict mode | `backend/tests/test_st_scenarios.py` | **LIVE-VERIFIED (Host Subprocess)** |
| **13. Debugger Agent** | [`backend/app/agents/debugger/agent.py:debugger_node`](file:///c:/Users/sanje/OneDrive/Desktop/Minor%20Project/mini-devin/backend/app/agents/debugger/agent.py#L81) | `test_results`, `retry_count` | `diagnose_failure_details` (regex/rules) | Diagnostic report | `retry_count`, `status="debugging"`, `error` | `coder` (under limit) or `retry_limit_terminal` | Bounded by `max_retries <= 3`; halts at `retry_limit_terminal` | `backend/tests/agents/test_routing.py` | **LIVE-VERIFIED (Rule-based)** |
| **14. Reviewer Agent** | [`backend/app/agents/reviewer/agent.py:reviewer_node`](file:///c:/Users/sanje/OneDrive/Desktop/Minor%20Project/mini-devin/backend/app/agents/reviewer/agent.py#L46) | `plan`, `test_results`, `code_changes` | `run_static_analysis` (`ast.parse`), `validate_diff_safety` | `ReviewFindings` | `review_findings`, `linter_results`, `status` | `pr_agent` (approve), `coder` (revise), `review_rejected_terminal` (block) | Evaluates 6 dimensions; writer-blind to Coder reasoning; returns approve/revise/block | `backend/tests/agents/test_routing.py` | **LIVE-VERIFIED (Static AST Linter)** |
| **15. PR Agent** | [`backend/app/agents/pr_agent/agent.py:pr_node`](file:///c:/Users/sanje/OneDrive/Desktop/Minor%20Project/mini-devin/backend/app/agents/pr_agent/agent.py#L19) | `review_findings`, `plan_hash`, `test_results` | `GitHubClient.open_pull_request` | PR Package & URL | `pull_request_url`, `pull_request_package`, `status="submitting_pr"` | `END` | Strictly creates PR, never merges; creates simulated mock PR if no token | `backend/tests/integrations/test_github_client.py` | **LIVE-VERIFIED (Mock/REST)** |

---

## 3. Discrepancies Against Project Synopsis

1. **GitHub MCP vs GitHub REST Client:**
   - *Synopsis:* "Repository Metadata and Source-Code Retrieval (via GitHub MCP)".
   - *Actual:* GitHub MCP is absent (`mcp_client.py` is an empty stub). All GitHub operations use a direct `httpx` REST client with in-memory test doubles.
2. **Docker/E2B Sandbox vs Host Subprocess Execution:**
   - *Synopsis:* "isolated sandbox environment (Docker or E2B)".
   - *Actual:* `docker_manager.py` and `e2b_manager.py` are empty stubs. The active sandbox manager is `CodespacesSandboxManager`, which defaults to creating a local temp directory on the host and running `subprocess.run(argv, cwd=temp_dir)`.
3. **Dual Divergent Graph Definitions:**
   - *Synopsis:* Unified multi-agent workflow from issue to pull request.
   - *Actual:* Two independent graph builders exist in [`backend/app/agents/graph.py`](file:///c:/Users/sanje/OneDrive/Desktop/Minor%20Project/mini-devin/backend/app/agents/graph.py):
     - `create_workflow_graph()`: Uses `AgentState`, entry node `triage`, wired to all 8 nodes, used by Chainlit and `LangGraphAgentGateway`.
     - `build_graph()`: Legacy graph using `RunState`, entry node `intake`, routed by `routing.py`, used by legacy unit tests.
4. **Issue Intake Without Issue Retrieval:**
   - *Synopsis:* User submits issue URL -> System fetches issue title, body, comments -> Triage evaluates issue.
   - *Actual:* Chainlit parses the URL with regex and immediately invents synthetic placeholder strings without querying the GitHub API.

---

## 4. Test Suite Baseline Execution

The full credential-free, network-free automated backend test suite was executed:

- **Command:** `python -m pytest backend/tests -q`
- **Output:** `452 passed, 7 warnings in 102.92s (0:01:42)`
- **Failures:** 0
- **Errors:** 0
- **Skipped:** 0
- **Baseline Test Count:** **452 passing tests**.

---

## 5. Security & Isolation Constraints Audit

1. **Secrets & Tokens:** `GITHUB_TOKEN`, `GROQ_API_KEY`, `GOOGLE_AI_STUDIO_API_KEY`, `HUGGINGFACE_API_TOKEN` are loaded as `SecretStr` in [`backend/app/config.py`](file:///c:/Users/sanje/OneDrive/Desktop/Minor%20Project/mini-devin/backend/app/config.py) and masked in `repr` and `str`.
2. **GitHub Writes:** Write protection is active; `GitHubClient` simulates PR creation when unconfigured and prohibits direct pushes or commits to protected branches (`main`, `master`, `develop`, etc.).
3. **Plan Approval:** The `coder_node` strictly refuses execution without valid approval containing a matching SHA-256 plan hash ([`coder/agent.py:144-209`](file:///c:/Users/sanje/OneDrive/Desktop/Minor%20Project/mini-devin/backend/app/agents/coder/agent.py#L144-L209)).
4. **Unsandboxed Host Execution Risk:** Current Test-Runner uses `CodespacesSandboxManager` which executes `subprocess.run` on the host operating system. This is a critical security risk for untrusted repositories until Phase 4 (Docker sandbox) is implemented.

---

## 6. Pre-Change Git Baseline

### `git status --short`
```text
 M backend/app/agents/coder/agent.py
 M backend/app/agents/graph.py
 M backend/app/agents/planner/agent.py
 M backend/app/agents/pr_agent/agent.py
 M backend/app/agents/retrieval/agent.py
 M backend/app/agents/reviewer/agent.py
 M backend/app/agents/schemas.py
 M backend/app/agents/test_runner/agent.py
 M backend/app/agents/tools/__init__.py
 M backend/app/api/agent_gateway.py
 M backend/app/api/runs.py
 M backend/app/config.py
 M backend/app/guardrails/output_guardrails.py
 M backend/app/integrations/github_client.py
 M backend/app/integrations/llm_provider_client.py
 M backend/app/main.py
 M backend/app/ml_models/embedding_model.py
 M backend/app/ml_models/triage_classifier.py
 M backend/app/models/__init__.py
 M backend/app/observability/mlflow_tracing.py
 M backend/app/retrieval/indexer.py
 M backend/app/retrieval/query_transform.py
 M backend/app/sandbox/__init__.py
 M backend/tests/agents/test_triage_gaps.py
 M backend/tests/planner/test_planner.py
 M backend/tests/retrieval/conftest.py
 M backend/tests/retrieval/test_retrieval.py
 M chainlit_console/app.py
 M chainlit_console/run.py
 M evaluation/swebench_lite/run_eval.py
 M evaluation/validate_system.py
?? backend/app/agents/issue_utils.py
?? backend/app/agents/tools/repo_tools.py
?? backend/app/models/events.py
?? backend/app/models/plan.py
?? backend/app/sandbox/base.py
?? backend/app/sandbox/codespaces_manager.py
?? backend/app/sandbox/models.py
?? backend/tests/agents/conftest.py
?? backend/tests/agents/test_llm_guard.py
?? backend/tests/coder/conftest.py
?? backend/tests/integrations/test_github_client.py
?? backend/tests/sandbox/
?? backend/tests/system/
?? backend/tests/test_api_plan_decision.py
?? backend/tests/test_mlflow_tracing.py
?? chainlit_console/.chainlit/
?? docs/audit/agents-status.md
?? docs/audit/mini-devin-baseline-audit.md
?? docs/audit/mini-devin-verification-report.md
?? docs/audit/phase0_baseline.md
?? docs/audit/stage1_execution_path_report.md
?? docs/design/sandbox-and-github-contract.md
?? playground/browser_testing/scenarios/chainlit_full_workflow_test.py
```

### `git diff --stat`
```text
 backend/app/agents/coder/agent.py               | 151 ++++++++++-
 backend/app/agents/graph.py                     |  33 ++-
 backend/app/agents/planner/agent.py             |  18 +-
 backend/app/agents/pr_agent/agent.py            | 146 +++++++++--
 backend/app/agents/retrieval/agent.py           |  95 +++++--
 backend/app/agents/reviewer/agent.py            | 121 +++++++--
 backend/app/agents/schemas.py                   |  76 +++++-
 backend/app/agents/test_runner/agent.py         |  99 +++++--
 backend/app/agents/tools/__init__.py            |  23 ++
 backend/app/api/agent_gateway.py                |  38 ++-
 backend/app/api/runs.py                         | 165 +++++++++++-
 backend/app/config.py                           |   2 +-
 backend/app/guardrails/output_guardrails.py     |   2 +-
 backend/app/integrations/github_client.py       | 326 +++++++++++++++++++++++-
 backend/app/integrations/llm_provider_client.py |  31 ++-
 backend/app/main.py                             |   4 +-
 backend/app/ml_models/embedding_model.py        |  35 ++-
 backend/app/ml_models/triage_classifier.py      |  60 ++++-
 backend/app/models/__init__.py                  |  18 ++
 backend/app/observability/mlflow_tracing.py     | 206 ++++++++++++++-
 backend/app/retrieval/indexer.py                |   8 +
 backend/app/retrieval/query_transform.py        |  99 +++++--
 backend/app/sandbox/__init__.py                 |  30 ++-
 backend/tests/agents/test_triage_gaps.py        |  75 ++++--
 backend/tests/planner/test_planner.py           |  10 +-
 backend/tests/retrieval/conftest.py             |  26 +-
 backend/tests/retrieval/test_retrieval.py       | 179 +++++++++++++
 chainlit_console/app.py                         |   6 +-
 chainlit_console/run.py                         |   1 +
 evaluation/swebench_lite/run_eval.py            | 181 ++++++++++++-
 evaluation/validate_system.py                   |   2 +-
 31 files changed, 2064 insertions(+), 202 deletions(-)
```

---

## 7. Phase 0 Gate Condition

**Status:** STOP AT THE GATE.  
Awaiting user review and confirmation of the traceability matrix, verified baseline findings, and priorities before proceeding to Phase 1 (Genuine GitHub MCP Integration).
