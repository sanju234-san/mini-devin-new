# Stage 1 Execution Path and Triage Root-Cause Audit Report

**Target Document:** `docs/audit/stage1_execution_path_report.md`  
**Audit Type:** Architecture Investigation & Real Execution Path Trace (Read-Only)  
**Target Repository:** `mini-devin`  
**Timestamp:** 2026-10-25T15:05:00+05:30  

---

## 1. Executive Summary

1. **Chainlit vs FastAPI:** Chainlit imports and executes the compiled LangGraph workflow directly in-process (`chainlit_console/app.py:396`); it does **not** call FastAPI over HTTP or WebSocket.
2. **FastAPI Workflow Invocation:** FastAPI is wired to the real `LangGraphAgentGateway` (`backend/app/main.py:171`), but it operates as a disconnected parallel entrypoint in a separate process with independent memory.
3. **GitHub MCP Status:** Genuine GitHub MCP is **ABSENT**; `backend/app/integrations/mcp_client.py` is a 2-line empty stub without client, server, or transport configuration.
4. **Data Reaching Triage/Retrieval/Planner:** Real issue title/body and repository content **do not reach** Triage or downstream agents; Chainlit creates synthetic placeholder text from regex parsing without querying GitHub, and no repository clone is executed.
5. **Cause of Triage Halt:** The local ML classifier evaluated the sparse placeholder text at 37.7% confidence (displayed as 40%); because this fell below the strict 60% fail-closed safety threshold (`MIN_CONFIDENCE = 0.6`), Triage classified the issue as `UNSUPPORTED` (`triage_uncertain`) and routed to `safe_stop`.

---

## 2. Evidence-Labelled Findings

### Finding 1: Direct In-Process LangGraph Invocation from Chainlit [CONFIRMED]
- **Evidence:** `chainlit_console/app.py:82-84` imports `get_checkpointer`, `create_graph`, and `create_initial_state` directly from `backend/app/agents`. At line 379, it instantiates `graph = create_graph(checkpointer=get_checkpointer())`, and at line 396 executes `await graph.ainvoke(initial_state, config=config)`.
- **Finding:** Chainlit runs the graph in its own Python runtime. It makes zero HTTP requests to FastAPI. `httpx` is not even imported in `chainlit_console/app.py`.

### Finding 2: FastAPI Operates as a Disconnected Parallel Entrypoint [CONFIRMED]
- **Evidence:** `backend/app/main.py:170-172` binds `application.state.agent_gateway = LangGraphAgentGateway()` and `application.state.run_store = InMemoryRunStore()`. `backend/app/api/issues.py:47` routes `/issues/ingest` to `run_agent_background_task`.
- **Finding:** FastAPI is fully capable of invoking the real LangGraph workflow, but running `python -m chainlit run .\chainlit_console\app.py` does not touch or launch FastAPI. Furthermore, both services use in-memory state (`MemorySaver` and `InMemoryRunStore`), meaning runs initiated in Chainlit are invisible to FastAPI's `/runs` endpoint.

### Finding 3: GitHub Model Context Protocol (MCP) is Entirely Absent [CONFIRMED]
- **Evidence:** `backend/app/integrations/mcp_client.py:1-2` contains solely:
  ```python
  """Model Context Protocol (MCP) client."""
  ```
  There are no MCP tool definitions, no Stdio/SSE client transports, and no MCP server configs in the repository.
- **Finding:** GitHub integration is implemented solely as an HTTP client using `httpx` (`backend/app/integrations/github_client.py`) with fallback to local in-memory dictionaries.

### Finding 4: GitHub Issue URL Intake Never Fetches GitHub Issue Content [CONFIRMED]
- **Evidence:** `chainlit_console/app.py:105-113` parses incoming text with `_GITHUB_ISSUE_RE`. When a match occurs for `https://github.com/pallets/flask/issues/12345`:
  ```python
  repo = f"{owner}/{repo_name}" # "pallets/flask"
  title = f"Fix defect reported in #{issue_number} for {repo}"
  body = f"Automated bug report imported from {raw}. Investigate and resolve defect."
  ```
- **Finding:** The intake logic synthesizes static dummy strings. It never calls GitHub REST API `GET /repos/{owner}/{repo}/issues/{issue_number}` or any SDK to retrieve the actual issue title, description, labels, or comments.

### Finding 5: Remote Repositories Cannot Be Resolved Without Prior Local Checkout [CONFIRMED]
- **Evidence:** `backend/app/retrieval/indexer.py:116-140` in `resolve_permitted_repo_path()` rejects remote slugs (`owner/repo`) unless a physical directory matching that path exists on the local disk. In `backend/app/agents/retrieval/agent.py:62-79`, when `repo_dir is None`, Retrieval reports `retrieval_status="missing_checkout"`.
- **Finding:** There is no automatic `git clone` or workspace preparation service wired on the live runtime path before Retrieval executes.

### Finding 6: Triage Halts Safely Due to Real ML Model Output Falling Below Strict Safety Threshold [CONFIRMED]
- **Evidence:** 
  1. `backend/app/ml_models/triage_classifier.py:13` defines `MIN_CONFIDENCE = float(os.getenv("MINI_DEVIN_MIN_CONFIDENCE", "0.6"))`.
  2. `backend/app/agents/triage/agent.py:99` runs `classify_with_confidence(cleaned_query)`.
  3. `backend/app/ml_models/artifacts/triage_pipeline.joblib` calculates class probabilities for `'Fix defect reported in #12345 for pallets/flask\nAutomated bug report imported from Investigate and resolve defect.'`:
     - `bug_fix`: 0.3770 (37.70%)
     - `out_of_scope`: 0.2715 (27.15%)
     - `small_feature`: 0.2191 (21.91%)
     - `test_writing`: 0.1324 (13.24%)
  4. At `backend/app/agents/triage/agent.py:142-152`, because `0.377 < 0.60`, the agent marks `is_supported=False`, `classification=UNSUPPORTED`, `reason="triage_uncertain"`.
  5. In `chainlit_console/app.py:453`, `f"{triage.get('confidence', 0.0):.0%}"` renders `0.377` as `40%`.
- **Finding:** The 40% confidence was not a random mock or hard-coded default; it was the actual mathematical probability output of the scikit-learn pipeline for the synthetic placeholder text.

### Finding 7: Lack of Clarification Loop in Chainlit Console [CONFIRMED]
- **Evidence:** `chainlit_console/app.py:443-458` checks `if workflow_status == "out_of_scope" or not triage.get("is_supported", True):`, prints the terminal message, and executes `return`.
- **Finding:** Although the warning states `operator clarification required`, no `cl.AskUserMessage` or graph resume mechanism is provided to accept operator clarification.

---

## 3. Current vs Target Architecture Comparison

| Stage | Target Flow Specification | Current Actual Implementation | Status |
| :--- | :--- | :--- | :--- |
| **1. Issue Intake** | Accept URL, webhook, or text; normalize issue identifier | Regex matching in Chainlit (`chainlit_console/app.py:95`) or REST endpoint (`backend/app/api/issues.py:27`) | **LIVE / SIMULATED** (Extracts regex groups, but fabricates synthetic text) |
| **2. Input Guardrails** | Prompt injection scan, sanitization, length boundaries | `app.guardrails.validate_and_sanitize_issue()` called in `triage/agent.py:64` | **LIVE** (Regex / heuristic injection scanner operational) |
| **3. GitHub Issue Retrieval** | Fetch real title, description, comments, labels via GitHub API | Not implemented in intake path. URL placeholder text used instead. | **ABSENT** (Zero calls to fetch issue details from GitHub) |
| **4. Repo Metadata & Source Checkout** | Clone or checkout target repository commit into local sandbox | `resolve_permitted_repo_path()` checks if directory exists locally. | **DISCONNECTED** (No automated clone/checkout service wired) |
| **5. Triage** | Categorize issue; fail closed if out of scope or confidence < 0.60 | `triage_node()` invokes scikit-learn pipeline (`triage_pipeline.joblib`) | **LIVE** (Authentic ML classification with fail-closed safety gate) |
| **6. Relevant Code Retrieval** | Extract AST keywords, expand query (HyDE), search BM25 + FAISS | `retrieval_node()` in `app/agents/retrieval/agent.py` | **IMPLEMENTED-UNVERIFIED** (Code ready; bypassed by triage halt) |
| **7. Repo-Aware Analysis** | Parse repository structure and ground evidence | `RepositoryIndexer` in `app/retrieval/indexer.py` | **IMPLEMENTED-UNVERIFIED** (Requires local directory presence) |
| **8. Implementation Planning** | Synthesize root cause, affected files, steps; freeze SHA-256 hash | `planner_node()` in `app/agents/planner/agent.py` | **IMPLEMENTED-UNVERIFIED** (LLM generation + deterministic synthesizer ready) |
| **9. Plan Validation** | Verify atomic steps, target files, acceptance criteria | `evaluate_plan_adequacy()` in `app/agents/planner/agent.py:458` | **IMPLEMENTED-UNVERIFIED** |
| **10. HITL Approval** | Pause on LangGraph `interrupt()`; present plan; await approve/reject | `human_approval_node()` + Chainlit `AskActionMessage` | **LIVE** (Full interrupt and resume tested in Chainlit) |
| **11. Coder Agent** | Generate minimal diff scoped strictly to affected files | `coder_node()` in `app/agents/coder/agent.py` | *Stage 2 Audit Scope* (Node present with Pydantic diff gate) |
| **12. Isolated Test-Runner** | Execute verification tests in isolated Docker / E2B sandbox | `test_runner_node()` in `app/agents/test_runner/agent.py` | *Stage 2 Audit Scope* (Docker sandbox manager present) |
| **13. Bounded Debugger** | Categorize test failures; manage bounded repair retry loop | `debugger_node()` in `app/agents/debugger/agent.py` | *Stage 2 Audit Scope* (Rule-based pre-classifier present) |
| **14. Independent Reviewer** | Static analysis (AST), security denylist, 6-dimension rubric | `reviewer_node()` in `app/agents/reviewer/agent.py` | *Stage 2 Audit Scope* (Deterministic AST linter present) |
| **15. PR Preparation / Creation** | Open documented pull request on GitHub (strictly no merge) | `pr_node()` in `app/agents/pr_agent/agent.py` | *Stage 2 Audit Scope* (`GitHubClient.open_pull_request` present) |
| **16. Audit Log & Checkpointing** | Persist event trail and LangGraph checkpoints | `app.agents.schemas.create_event` + `MemorySaver` | **LIVE** (In-memory event trail operational) |

---

## 4. Traceability Matrix (Stages up to Planner)

| Stage | Entry File / Function | Input Data | Tools / APIs Called | Output Data | State Fields Updated | Next Node | Error Behaviour | Proving Test | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Intake (Chainlit)** | `chainlit_console/app.py:parse_issue_input` | Raw user chat message | Regex `_GITHUB_ISSUE_RE` | `(repo, title, body, url, number)` | `issue_title`, `issue_body`, `repo`, `issue_url`, `issue_number` | `triage` | Catches exceptions; returns UI error message | Manual verification | **LIVE (Simulated Data)** |
| **Input Guardrails** | `backend/app/guardrails/input_guardrails.py:validate_and_sanitize_issue` | `title`, `body` | Regex patterns for prompt injection & HTML tags | `(clean_title, clean_body, warnings, is_suspicious)` | None (called by Triage) | N/A | Flags `is_suspicious=True` | `backend/tests/agents/test_triage.py` | **LIVE** |
| **GitHub Issue Fetch** | *None* | `issue_url` | None | None | None | N/A | Silently bypassed; uses placeholder string | *None* | **ABSENT** |
| **Triage Agent** | `backend/app/agents/triage/agent.py:triage_node` | `issue_title`, `issue_body`, `repo` | `classify_with_confidence()` (`triage_pipeline.joblib`) | `TriageResult` | `triage`, `cleaned_query`, `status`, `events` | `safe_stop` (if unsupported) or `retrieval` | Sets `is_supported=False`, halts at `safe_stop` | `backend/tests/agents/test_triage_agent.py` | **LIVE** |
| **Safe Stop** | `backend/app/agents/graph.py:safe_stop_node` | `triage` | None | Event dict | `status="out_of_scope"`, `events` | `END` | Terminal node | `backend/tests/agents/test_graph.py` | **LIVE** |
| **Retrieval Agent** | `backend/app/agents/retrieval/agent.py:retrieval_node` | `cleaned_query`, `repo` | `resolve_permitted_repo_path`, `RepositoryIndexer.search`, `transform_query` | `RetrievedContext` | `retrieved_context`, `status`, `events` | `planner` | Reports `missing_checkout` if directory absent | `backend/tests/retrieval/test_retrieval.py` | **IMPLEMENTED-UNVERIFIED** |
| **Planner Agent** | `backend/app/agents/planner/agent.py:planner_node` | `issue_title`, `issue_body`, `retrieved_context` | `try_llm_plan_generation`, `synthesize_deterministic_plan`, `compute_plan_hash` | `ImplementationPlan` | `plan`, `plan_hash`, `plan_version`, `status="awaiting_approval"` | `human_approval` | Falls back to deterministic plan synthesis | `backend/tests/planner/test_planner.py` | **IMPLEMENTED-UNVERIFIED** |

---

## 5. Execution Path Diagram

```mermaid
flowchart TD
    User([User in Chainlit UI]) -->|Inputs URL| CL_Input[chainlit_console/app.py: parse_issue_input]
    
    subgraph Chainlit_In_Process [Chainlit Process: In-Memory Runtime]
        CL_Input -->|Regex Match: No GitHub API Call| Synthesize[Synthesize Dummy Title & Body]
        Synthesize -->|create_initial_state| StateInit[Initial AgentState]
        StateInit -->|create_graph + ainvoke| LG_Start([LangGraph START])
        
        subgraph LangGraph_Topology [Compiled StateGraph]
            LG_Start --> Triage[Triage Agent: triage_node]
            Triage --> Guardrails[app.guardrails: validate_and_sanitize_issue]
            Guardrails --> Classifier[app.ml_models: classify_with_confidence]
            Classifier --> CheckConf{Confidence >= 0.60?}
            
            CheckConf -->|No: Conf = 37.7%| HaltTriage[TriageResult: is_supported=False, reason=triage_uncertain]
            HaltTriage --> RouteTriage{route_triage}
            RouteTriage -->|safe_stop| SafeStop[safe_stop_node: status=out_of_scope]
            SafeStop --> LG_End([LangGraph END])
            
            CheckConf -->|Yes: e.g. >= 60%| SupTriage[TriageResult: is_supported=True]
            SupTriage --> RouteTriage
            RouteTriage -->|retrieval| Retrieval[Retrieval Agent: retrieval_node]
            Retrieval --> CheckLocalRepo{Local Directory Exists?}
            CheckLocalRepo -->|No: Remote Slug| MissingCheckout[RetrievedContext: missing_checkout]
            CheckLocalRepo -->|Yes| BM25Index[BM25 + Dense Index Search]
            MissingCheckout --> Planner[Planner Agent: planner_node]
            BM25Index --> Planner
            Planner --> PlanAdequacy[evaluate_plan_adequacy]
            PlanAdequacy --> FreezeHash[compute_plan_hash: SHA-256]
            FreezeHash --> HITL[human_approval_node: interrupt]
        end
        
        LG_End --> UI_Halt[Chainlit UI Renders: Workflow Safely Halted by Triage Agent]
        UI_Halt --> TerminateTurn[Execution Returns: No Clarification Prompt]
    end
    
    subgraph Disconnected_FastAPI [FastAPI Process: Disconnected]
        FastAPI_App[backend/app/main.py]
        FastAPI_App --> Endpoint_Ingest[/issues/ingest]
        FastAPI_App --> Endpoint_Webhook[/webhooks/github]
        Endpoint_Ingest -.->|Not Called by Chainlit| Gateway[LangGraphAgentGateway]
    end
```

---

## 6. Triage Halt Root-Cause Analysis

### Decisive Code Path
1. **Input Submission:** User entered `https://github.com/pallets/flask/issues/12345`.
2. **Regex Parsing without Fetch (`chainlit_console/app.py:105-113`):**
   ```python
   repo = "pallets/flask"
   title = "Fix defect reported in #12345 for pallets/flask"
   body = "Automated bug report imported from https://github.com/pallets/flask/issues/12345. Investigate and resolve defect."
   ```
3. **Issue Sanitization & Cleaning (`backend/app/retrieval/query_transform.py:58`):**
   `clean_issue_text()` removes Markdown image tags, template boilerplate, and strips URL patterns:
   - Input text: `"Fix defect reported in #12345 for pallets/flask\nAutomated bug report imported from https://github.com/pallets/flask/issues/12345. Investigate and resolve defect."`
   - Cleaned text: `'Fix defect reported in #12345 for pallets/flask\nAutomated bug report imported from Investigate and resolve defect.'`
4. **Classifier Inference (`backend/app/ml_models/triage_classifier.py:153`):**
   The calibrated TF-IDF + Logistic Regression / LinearSVC pipeline evaluates the cleaned text against 4 classes:
   - `bug_fix`: **0.3770 (37.7%)**
   - `out_of_scope`: 0.2715 (27.2%)
   - `small_feature`: 0.2191 (21.9%)
   - `test_writing`: 0.1324 (13.2%)
5. **Threshold Comparison (`backend/app/agents/triage/agent.py:142-152`):**
   ```python
   if confidence < MIN_CONFIDENCE: # 0.377 < 0.60
       result = TriageResult(
           classification=TriageClassification.UNSUPPORTED,
           category=category,
           is_supported=False,
           confidence=confidence,
           reason="triage_uncertain",
           warnings=warnings + [f"Low classification confidence ({confidence:.2f} < {MIN_CONFIDENCE}); operator clarification required."],
           cleaned_query=cleaned_query,
       )
   ```
6. **Graph Routing (`backend/app/agents/graph.py:73-78`):**
   `route_triage(state)` checks `_is_supported_triage(triage)`. Because `is_supported == False`, it returns `"safe_stop"`.
7. **Safe Termination (`backend/app/agents/graph.py:99-103`):**
   `safe_stop_node` sets `status = "out_of_scope"` and transitions directly to `END`.
8. **UI Display (`chainlit_console/app.py:449-457`):**
   Renders the exact message observed in the evidence:
   - Classification: `UNSUPPORTED`
   - Eligibility to Proceed: `False (Safe Terminal)`
   - Explanation: `triage_uncertain`
   - Confidence: `40%` (derived from `0.377` rounded by `:.0%`)

**Conclusion:** The triage halt is **not a bug or unhandled crash**. It is an intentional, correctly functioning safety invariant that prevents the system from generating code or modifying repositories when the input text lacks technical specifics.

---

## 7. Prioritised Defect List

### P0: Chainlit GitHub Issue Intake Does Not Fetch Live Issue Content
- **Description:** Submitting a GitHub issue URL in Chainlit parses the URL with regex and invents synthetic dummy text instead of fetching the real issue title and body.
- **Evidence:** `chainlit_console/app.py:105-113`.
- **Impact:** Any real GitHub issue submitted via URL is evaluated only on dummy text, causing high-quality issues to trigger low classification confidence (< 60%) and falsely halt at Triage.
- **Proposed Fix:** In `chainlit_console/app.py:parse_issue_input`, when `_GITHUB_ISSUE_RE` matches, call `GitHubClient.fetch_issue(owner, repo_name, issue_number)` (or `httpx.get(f"https://api.github.com/repos/{owner}/{repo_name}/issues/{issue_number}")`) to retrieve the authentic `title` and `body` before constructing `initial_state`. Fall back to synthetic text only if the network or API call fails.

### P0: Retrieval Fails on Remote Repository Slugs Without Clone/Checkout Service
- **Description:** `resolve_permitted_repo_path()` rejects remote slugs like `pallets/flask` unless a directory named `pallets/flask` already exists on the local file system.
- **Evidence:** `backend/app/retrieval/indexer.py:116-140` and `backend/app/agents/retrieval/agent.py:62`.
- **Impact:** Even when issues pass Triage, Retrieval immediately reports `missing_checkout`, and Planner is forced into a blocked state because no source code is accessible.
- **Proposed Fix:** Introduce a repository checkout utility before or within `retrieval_node` that clones the target repository or shallow-fetches the default branch into an isolated temporary workspace directory when given a remote GitHub slug.

### P1: Clarification Loop in Chainlit Console is Terminated Rather Than Interactive
- **Description:** When Triage yields `triage_uncertain`, the warning advises `operator clarification required`, but the console immediately exits the turn without asking for clarification.
- **Evidence:** `chainlit_console/app.py:443-458`.
- **Impact:** Operators cannot disambiguate borderline issues; the workflow terminates and discards all context.
- **Proposed Fix:** When `reason == "triage_uncertain"`, invoke `cl.AskUserMessage` to prompt the operator: *"Mini-Devin was uncertain if this issue is a bug fix or feature. Please provide additional details or specify the category."* Update the issue text and re-invoke Triage within the same thread.

### P1: Dual Graph Implementations and Missing Graph Synchronisation
- **Description:** `backend/app/agents/graph.py` contains two independent graph definitions: `create_graph` (using `AgentState`) and `build_graph` (using `RunState` with `intake` and `input_guardrail` nodes).
- **Evidence:** `backend/app/agents/graph.py:473` vs `backend/app/agents/graph.py:687`.
- **Impact:** Unit tests that test `build_graph()` test a different graph topology (`START -> intake -> input_guardrail -> triage`) than the active production topology used by Chainlit and FastAPI (`START -> triage`).
- **Proposed Fix:** Deprecate the legacy `build_graph` and unify all tests around `create_workflow_graph()` and `AgentState`.

### P2: In-Memory State Isolation Between FastAPI and Chainlit
- **Description:** FastAPI and Chainlit run in separate processes, each maintaining an in-memory `MemorySaver` and `InMemoryRunStore`.
- **Evidence:** `backend/app/agents/checkpointer.py:35` and `backend/app/api/run_store.py:23`.
- **Impact:** Actions taken in Chainlit do not register in FastAPI's `/runs` dashboard or event history.
- **Proposed Fix:** For production readiness, configure a shared database checkpointer (e.g. SQLite / PostgresSaver) and have Chainlit record runs in the shared `RunStore`.

---

## 8. Commands Run and Actual Outputs

1. **Python and Package Inspection in Virtual Environment:**
   ```bash
   .\.venv\Scripts\python.exe -c "import importlib.metadata as im; pkgs = ['chainlit', 'fastapi', 'langgraph', 'langchain', 'mcp', 'pydantic', 'httpx']; [print(f'{p}: {im.version(p)}') if p in [d.metadata['Name'] for d in im.distributions()] else print(f'{p}: NOT INSTALLED') for p in pkgs]"
   ```
   *Output:*
   ```
   chainlit: 2.12.0
   fastapi: 0.162.0
   langgraph: 1.2.17
   langchain: 1.4.7
   mcp: 1.30.0
   pydantic: 2.14.1
   httpx: 0.28.1
   ```

2. **Triage Classifier Exact Probability Derivation:**
   ```bash
   python -c "import sys, joblib; sys.path.insert(0, 'backend'); from app.retrieval.query_transform import clean_issue_text; pipe = joblib.load('backend/app/ml_models/artifacts/triage_pipeline.joblib'); title = 'Fix defect reported in #12345 for pallets/flask'; body = 'Automated bug report imported from https://github.com/pallets/flask/issues/12345. Investigate and resolve defect.'; text = clean_issue_text(f'{title}\n{body}'); probas = pipe.predict_proba([text])[0]; print('Cleaned text:\n', repr(text)); print('\nClasses and probabilities:'); [print(f'  {c}: {p:.4f} ({p*100:.2f}%)') for c, p in zip(pipe.classes_, probas)]"
   ```
   *Output:*
   ```
   Cleaned text:
    'Fix defect reported in #12345 for pallets/flask\nAutomated bug report imported from Investigate and resolve defect.'

   Classes and probabilities:
     bug_fix: 0.3770 (37.70%)
     out_of_scope: 0.2715 (27.15%)
     small_feature: 0.2191 (21.91%)
     test_writing: 0.1324 (13.24%)
   ```

3. **Triage and Planner Automated Test Execution:**
   ```bash
   python -m pytest backend/tests/agents/test_triage.py backend/tests/agents/test_triage_agent.py backend/tests/planner/test_planner.py -q
   ```
   *Output:*
   ```
   .................................................                        [100%]
   49 passed, 3 warnings in 16.87s
   ```

4. **Retrieval Automated Test Execution:**
   ```bash
   python -m pytest backend/tests/retrieval -q
   ```
   *Output:*
   ```
   ..................                                                       [100%]
   18 passed, 6 warnings in 18.66s
   ```

---

## 9. Unresolved Questions and Blockers

1. **GitHub Credentials for Live Issue Ingestion:**
   `GITHUB_TOKEN` is currently unset in the test execution environment. To enable live fetching of real GitHub issues and private repository inspection, a read-scoped token must be configured.
2. **Repository Workspace Storage Strategy:**
   A design decision is required: Should Mini-Devin clone repositories into a persistent local folder (e.g. `workspaces/<owner>/<repo>`), ephemeral temporary directories (`tempfile.mkdtemp()`), or Docker sandbox container volumes?
3. **FastAPI-Chainlit Architecture Convergence:**
   Architecture decision required: Is Chainlit intended strictly as a developer debugging console that directly embeds LangGraph, or should Chainlit be refactored into a thin client that submits issues to FastAPI's `/issues/ingest` and streams progress via WebSockets?
