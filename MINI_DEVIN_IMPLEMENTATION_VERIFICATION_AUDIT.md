# Mini-Devin Implementation & Verification Audit

**Audit date:** 2026-10-24  
**Branch inspected:** `sanjeevni`  
**HEAD:** `ea02182` (`fix: add template stripping to issue cleaning`)  
**Scope:** Read-only source inspection of the existing repository.  
**Prior reports found:** None (no `*AUDIT*`, `*REPORT*`, or similarly named implementation-verification documents in the tree). Design docs and API contract drafts were used as the intended architecture, not as proof of implementation.

**Precedence rule used:** Source code and this audit’s executed checks take precedence over README, design docs, comments, and tests that *define* behaviour without being run here.

---

## How this audit was performed

- Inspected README, `docs/design/agent-state-and-graph.md`, `docs/design/schemas.md`, `docs/api-contract.md`, agent packages, `graph.py`, FastAPI, Chainlit, tests, and teammate-owned stubs.
- Compared the **live** graph (`create_graph` / `create_workflow_graph`) used by Chainlit against the **legacy** supervisor (`build_graph` + `fake_nodes.py` + `routing.py`).
- Classified each claim with the status vocabulary in the audit brief.
- **Did not** modify project files other than creating this report.
- **Did not** install packages, call external APIs, open GitHub PRs, train models, or run pytest / unittest / playground scripts.

---

## Section 1 — Executive Summary

Mini-Devin’s **live** orchestration is a LangGraph `StateGraph` that registers all eight named agents and pauses at a human-approval interrupt. The **planning half** of the pipeline (triage → retrieval → planner → interrupt) is substantially implemented in code. The **execution half** (coder → real tests → repair → independent review → GitHub PR) is mostly gating logic around teammate stubs, with several default routes that can look successful without generating a diff, executing tests, or opening a pull request.

**Maturity:** Early integration skeleton with a real planning path and unsafe default verification semantics. Not a complete issue-to-PR system.

### Agent counts (classified after inspection)

| Bucket | Count | Agents |
|---|---|---|
| IMPLEMENTED + VERIFIED (this audit) | **0** | — |
| IMPLEMENTED — NOT RUNTIME-VERIFIED | **0** | — |
| PARTIALLY IMPLEMENTED | **5** | Triage, Retrieval, Planner, Debugger, Reviewer |
| STUB / PLACEHOLDER | **3** | Coder, Test Runner, PR Agent |
| MISSING (no node/module) | **0** | All eight names exist |

Supporting design nodes from the spec (`intake`, `input_guardrail` as a graph node, `plan_validation`, `diff_gate`, `escalate`, `finish`) exist only on the **legacy** `build_graph` path, mostly as fakes.

### End-to-end issue-to-PR

**Not verified.** Source inspection shows it **cannot** currently complete a real GitHub issue-to-PR workflow: LLM `complete()` raises `NotImplementedError`; Docker/E2B/GitHub clients are docstring-only modules; the PR node always returns `pull_request_url: None` and never calls a GitHub write API; the live graph does not default to `strict_verification`.

### Five most important blockers

1. **False-success routing:** `route_test_runner` treats missing `test_results` as **pass** unless `strict_verification` is set (`graph.py` 381–413). Chainlit never sets that flag.
2. **Coder does not produce patches.** It checks approval/hash/paths, pings an unimplemented LLM, and returns without writing a diff (`coder/agent.py`).
3. **Sandbox and GitHub integrations are stubs.** `docker_manager.py`, `e2b_manager.py`, `github_client.py`, `mcp_client.py`, `mlflow_tracing.py` are module docstrings only. Test runner and PR agent only `hasattr`-check them and never execute tests or create PRs.
4. **Injected / stale artifacts can bypass gates.** `test_runner_node` copies existing `test_results` through; `reviewer_node` returns existing `review_findings` unchanged. Graph tests inject `approved=True` to reach the PR node.
5. **REST backend is not wired to the live graph.** `NoOpAgentGateway.start_run` leaves runs queued (`agent_gateway.py` 42–54). There is **no** plan-approval HTTP endpoint despite the API contract.

---

## Section 2 — Eight-Agent Status Matrix

| Agent | Implementation status | Connected to graph? | Real dependencies working? | Runtime verified? | Evidence | Missing work |
|---|---|---|---|---|---|---|
| **Triage** | PARTIALLY IMPLEMENTED | Yes — live `create_graph` START → `triage`; unsupported → `safe_stop` | Trained `triage_pipeline.joblib` **not present** in tree (gitignored `backend/app/ml_models/artifacts/`). Loader implemented. LLM not used. | **NOT RUN** this audit. Graph tests **monkeypatch** `classify_with_confidence`. | `backend/app/agents/triage/agent.py`; `backend/app/ml_models/triage_classifier.py`; tests mock classifier | Check in trained artifacts; run unmocked classification; DistilBERT path unused by live node |
| **Retrieval** | PARTIALLY IMPLEMENTED | Yes — after supported triage | Local path + BM25 indexer implemented. No clone. Embeddings `embed()` raises `NotImplementedError`; `is_embedding_available()` returns `False`. GitHub file API unused. | **NOT RUN.** Tests exist (`backend/tests/retrieval/test_retrieval.py`) using tmp repos. | `retrieval/agent.py`, `indexer.py`, `vector_store.py` | Repo acquisition; FAISS+embeddings actually wired into `HybridIndex()`; halt on `missing_checkout` instead of planning inventively |
| **Planner** | PARTIALLY IMPLEMENTED | Yes — retrieval → planner → `human_approval` | LLM plan path calls `complete()` which raises; deterministic synthesizer always used in practice | **NOT RUN.** Graph tests assert missing-checkout plans | `planner/agent.py`; `compute_plan_hash` in `schemas.py` | Plan versioning beyond hardcoded `v1`; edit/reapprove; bind approval to append-only `plan_versions`; block inadequate plans |
| **Coder** | STUB / PLACEHOLDER | Yes — only if approval == `approved` | LLM client stub. No file tools, no checkout writes | Tests assert `code_generation_started` without a diff | `coder/agent.py` 119–174 | Generate/apply scoped diffs; fail the graph on empty patches; call LLM for real |
| **Test Runner** | STUB / PLACEHOLDER (browser shim partial) | Yes — unconditional edge from coder | Docker/E2B unimplemented. Browser path exists if `browser_test_url` set | **NOT RUN.** Browser tests exist; sandbox never invoked | `test_runner/agent.py`; `browser_runner.py`; `playground/browser_testing/` | Implement `run_in_sandbox`; capture stdout/stderr/exit; never copy injected results; default fail-closed routing |
| **Debugger** | PARTIALLY IMPLEMENTED | Yes — fail + retries remaining → debugger → coder | No LLM repair; keyword diagnosis only | Retry-loop **tests inject** failing `test_results` | `debugger/agent.py` | Produce/apply patches; infra errors must not consume repair budget; return to tests with a new diff |
| **Reviewer** | PARTIALLY IMPLEMENTED | Yes — after tests “pass”; PR only if `review_findings.approved` | Rule-based; no linter/LLM; 6-dimension `ReviewResult` unused on live path | Tests inject findings to reach PR | `reviewer/agent.py`; unused `ReviewResult` in `schemas.py` 740–765 | Independent review of real diff+tests; Revise→coder; reject missing evidence by default; ignore injected findings |
| **PR Agent** | STUB / PLACEHOLDER | Yes — if `approved` findings | `github_client` has no `create_pull_request` | Tests assert `submitting_pr` with `pull_request_url is None` | `pr_agent/agent.py` 71–119 | Real GitHub PR create; refuse without executed tests; never fabricate URLs |

---

## Section 3 — Backend and Graph Status

### 3.1 Two graphs (critical architectural split)

| Graph | Entry | State type | Used by live UI? | Agents |
|---|---|---|---|---|
| **`create_graph` / `create_workflow_graph`** | `START` → `triage` | `AgentState` | **Yes** — `chainlit_console/app.py` 83, 378 | Real node functions |
| **`build_graph`** | `START` → `intake` | `RunState` | **No** | `default_nodes()` = **fake nodes** except legacy `triage_agent.py` |

Chainlit and the eight-agent product path use `create_graph`. The design document’s supervisor (`intake` → guardrail → … → `diff_gate` → escalate/finish) is implemented as `build_graph` + `routing.decide` and is **not** the Chainlit runtime.

`graph.py` module docstring (lines 1–10) still describes a “Day 1” halt after planner; the compiled live graph **does** continue after approval. `completion_node` (284–309) is **defined but never registered**.

### 3.2 Intended vs implemented live flow

**Design (`docs/design/agent-state-and-graph.md` §4):**  
Issue → intake → input_guardrail → triage → retrieval → planner → plan_validation → human_approval (approve / edit / reject) → coder → diff_gate → test_runner → debugger (on real fail) → reviewer (Approve / Revise / Block) → pr_agent → finish.

**Implemented live graph (`create_workflow_graph`, 443–517):**

```
START → triage
  ├─ unsupported/out_of_scope → safe_stop → END
  └─ supported → retrieval → planner → human_approval
        ├─ approved → coder → test_runner
        │     ├─ passed (or missing results, default) → reviewer
        │     │     ├─ review_findings.approved → pr_agent → END
        │     │     ├─ strict_verification and not approved → review_rejected_terminal → END
        │     │     └─ default not approved → END
        │     ├─ failed and retries left → debugger → coder → test_runner …
        │     ├─ failed and retries exhausted → retry_limit_terminal → END
        │     └─ missing results + strict_verification → test_unverified_terminal → END
        └─ rejected / hash mismatch treated as reject → rejection_terminal → END
```

**Missing from live graph vs spec:** `intake`, `input_guardrail` node, `plan_validation`, `diff_gate`, `escalate`, `finish`, human **edit** loop, reviewer **Revise** → coder, LLM budget check, separate sandbox_error vs test fail.

**Input guardrail** is inlined inside `classify_issue` (`triage/agent.py` 64–78), not a graph node.

### 3.3 State schema

Live state: `AgentState` (`schemas.py` 222–272).  
Legacy state: `RunState` (`schemas.py` 845–875) with `plan_versions`, `approved_version`, `current_diff`, `test_evidence`, `review_result`.

**Live graph does not populate** `plan_versions`, `approved_version`, `current_diff`, or `test_evidence`. Planner writes a single `plan` dict + `plan_hash`. Coder does not write `code_changes` unless they were already in state.

`strict_verification` and `force_reindex` are **read** at runtime but **not declared** on `AgentState`. `create_initial_state` (449–505) never sets `strict_verification` (defaults to false).

`plan_version` is always `"v1"` in the deterministic planner (`planner/agent.py` 167, 216, 384). Hashing is real SHA-256 of canonical JSON (`schemas.py` 275–298). Adequacy scoring does **not** block the human_approval edge.

### 3.4 Human approval, checkpoints, resume

- Interrupt: `human_approval_node` uses LangGraph `interrupt()` (`graph.py` 106–252).
- Frozen hash: resume `plan_hash` must match checkpoint hash; mutated plan hash forces reject (183–201).
- Decisions on the live path: **approved** or **rejected** only. Design **edit** is not implemented in `human_approval_node`.
- Idempotency (114–129): if `human_approval` already has `approved`/`rejected`, the node **skips interrupt**. A caller who seeds `human_approval` in the initial state can skip the pause. Confirmed by source; not runtime-tested here.
- Checkpointer: process-local `MemorySaver` (`checkpointer.py` 29–48). Documented as non-durable across restarts. Not Postgres/SQLite.
- Chainlit resume: `Command(resume={decision, feedback, plan_hash, plan_version})` (`chainlit_console/app.py` 559–571).
- REST: **no** `/runs/{id}/approve` (or equivalent). `api/runs.py` is GET list/detail only. Contract §5 unmet.

### 3.5 Retry loops and false terminals

- Debugger increments `retry_count` on every visit (`debugger/agent.py` 91).
- `route_test_runner` compares `retry_count >= max_retries` (`graph.py` 407–411).
- Unconditional `coder` → `test_runner` edge (`graph.py` 491): coder **failure** (unapproved, hash mismatch, unsafe path) still continues if that node ran. Approval router usually prevents unapproved coder, but coder “failed” after approval still proceeds.
- Default missing tests → reviewer (`graph.py` 399–404, 413) **without** setting `test_results`. Reviewer then often writes no `review_findings`. `route_reviewer` without approval and without strict mode returns `END` (`425–438`). Final status remains `"reviewing"`. Graph tests **require** this (`test_graph.py` 148–174, 440–476, 671–695).

That is a **confirmed source defect** (false-success / false-completion), not merely unverified runtime.

### 3.6 Backend APIs

| Surface | Status | Notes |
|---|---|---|
| FastAPI `create_app` | Implemented | CORS, `/health`, routers registered (`main.py`) |
| `POST /issues/ingest` | Implemented | Creates queued run; background `NoOpAgentGateway` |
| `GET /runs`, `GET /runs/{id}` | Implemented | In-memory `InMemoryRunStore` |
| Webhooks | Implemented (signature/size limits) | Also uses NoOp gateway |
| Artifacts | Implemented against run store | Binary types 501 |
| Metrics | Implemented | `EmptyMetricsProvider` returns `available=False` |
| Agent gateway | **STUB** | Does not invoke `create_graph` |
| Live WebSocket | **STUB** | `websocket/live_stream.py` is a one-line docstring |
| Plan approval API | **MISSING** | |

Lifespan tries `app.sandbox.docker_manager.lifespan_resource`; that module has **no** such function, so the hook is skipped (`main.py` 127–132).

### 3.7 Chainlit vs tests vs playground

| Path | Graph | `strict_verification` | Repo path | After approval |
|---|---|---|---|---|
| Chainlit | `create_graph` | unset (false) | GitHub slug or `demo-org/demo-repo` — almost never a local dir | Coder stub → test_runner (no results) → reviewer → END `reviewing`. UI may say “Plan Approved & Workflow Advanced” (`app.py` 578–587) |
| `backend/tests/agents/test_graph.py` | `create_graph` | unset | fake slugs → `missing_checkout` | Same topology; asserts `status == "reviewing"` |
| Playground `verify_all_eight_agents.py` | Direct node calls, **not** full graph | set True **after** coder | `pallets/flask` missing locally | Injects a fabricated `PatchMetadata` (165–173) then tests sandbox fail-closed |
| Legacy `build_graph` tests | fakes | N/A | N/A | Simulated PASS/PR_OPENED |

GitHub issue URLs in Chainlit (`parse_issue_input`, 95–113) **do not fetch** issue text; they synthesize a generic title/body.

---

## Section 4 — Supporting Components

| Component | Status | Connected? | Notes |
|---|---|---|---|
| **LLM provider** `integrations/llm_provider_client.py` | STUB | Planner/coder/query-transform import `complete` | `complete()` raises `NotImplementedError` (19–25). `PROVIDER_CHAIN` declared only. Owner: Tamanna (API contract). |
| **Model router** `agents/model_router.py` | PARTIAL | Agents call `route(name)` for logging/metadata | Returns a `ModelTier` enum only; does not call providers. |
| **Docker sandbox** | STUB | Test runner `hasattr(run_in_sandbox)` | Function **does not exist**. `sandbox_ready` stays False. Never executes. |
| **E2B** | STUB | Not in live agent path | Docstring module; commented in `LIFESPAN_MODULES`. |
| **Playwright sandbox module** `sandbox/playwright_runner.py` | STUB | Unused by test_runner_node | One-line docstring. Real Playwright lives under `playground/browser_testing/`. |
| **GitHub client** | STUB | PR `hasattr(create_pull_request)` is False | No methods. No clone/read-issue. |
| **MCP client** | STUB | Unreferenced by agents | Docstring only. |
| **Memory** `agents/memory.py` | PARTIALLY IMPLEMENTED | **Not** called from retrieval/planner/reviewer | In-memory LangGraph `InMemoryStore`; isolation helpers exist; playground unit tests exist. Advisory-only by comment; not wired. |
| **DSPy** | MISSING | — | No matches in `*.py`/`*.md`/`requirements`. |
| **Query transformer** | PARTIALLY IMPLEMENTED | Retrieval calls `transform_query` | Deterministic identifiers/keywords. HyDE/LLM expand calls stub `complete()`. Cleaning is not a security control (module docstring). |
| **Indexing / BM25** | PARTIALLY IMPLEMENTED | Retrieval | Real file walk, gitignore, secret/binary skip, chunk line ranges, incremental reindex. `HybridIndex()` constructed **without** `embed_fn`/`dimension` → always `lexical_bm25` (`vector_store.py` 369–386, `indexer.py` 288). |
| **FAISS** | PARTIALLY IMPLEMENTED | Only if HybridIndex given embed_fn | Class exists; default retrieval path does not enable it. `faiss-cpu` listed in requirements ≠ runtime proof. |
| **Embeddings** | STUB | `is_embedding_available()` → False | `embed()` raises `NotImplementedError`. |
| **Triage classifier** | PARTIALLY IMPLEMENTED | Live triage | joblib load + `predict_proba`. Artifacts directory gitignored and **absent** in this checkout. Fail-closed to unsupported. Training scripts exist; `train.jsonl` directory gitignored/empty. DistilBERT trainer is a separate unused path. |
| **Input guardrails** | PARTIALLY IMPLEMENTED | Inside triage | Regex injection scan. Not a graph-level escalate with `injection_suspected` stop reason on the live graph (uses `out_of_scope` / `is_supported=False`). |
| **Output guardrails** | PARTIALLY IMPLEMENTED | Coder/reviewer path checks | Path denylist + secret redact + plan validator. **Not** a graph `diff_gate` node. `validate_plan_output` not invoked by `planner_node`. |
| **MLflow tracing** | STUB | Not wrapping graph nodes | Docstring file. Design required node wrappers in `graph.py` — absent. |
| **Evaluation reporting** | PARTIALLY IMPLEMENTED | Not served live | `observability/evaluation.py` categorizes outcomes; `EmptyMetricsProvider` on API. `HISTORICAL_BASELINE` in `evaluation/metrics.py` is **historical recorded numbers**, not this audit. |
| **Chainlit UI** | PARTIALLY IMPLEMENTED | Direct graph invoke | Plan markdown, approve/reject actions, event dump. Does not show real diffs/PRs. Python 3.14 sniffio patches (fragile). |
| **Frontend React** | STUB / PLACEHOLDER | Not wired to live graph | Component files are single comment lines (`PlanApproval`, `LiveConsole`, `api.ts`, etc.). |
| **Config / env** | IMPLEMENTED — NOT RUNTIME-VERIFIED | `Settings` via pydantic-settings | `.env.example` lists key **names** only. This report does not print `.env` contents. App starts without secrets. |
| **Logging** | PARTIAL | stdlib loggers | Tracing failure isolation for MLflow N/A because MLflow unused. |

---

## Section 5 — Verification Evidence

### 5.1 Commands actually run during this audit

| # | What was checked | Command / procedure | Executed? | Result | Scope / limitations | Evidence location |
|---|---|---|---|---|---|---|
| 1 | Repository layout, docs, agents, graph, APIs, tests | Read/grep/glob of source | **Yes** | See sections 2–4, 6–7 | Implementation evidence only | This report |
| 2 | Presence of triage model artifacts | Glob `**/*.joblib`, `backend/app/ml_models/artifacts/**` | **Yes** | **0 files.** Training data dir also empty/gitignored | Does not prove a local untracked artifact outside workspace indexing | `.gitignore` 24–32 |
| 3 | Git baseline | `git status --porcelain`; `git log -12 --oneline`; `git branch --show-current` | **Yes** | Branch `sanjeevni`; dirty tree (see 5.3); HEAD `ea02182` | Status snapshot during audit | Terminal |
| 4 | pytest / unittest / playground scripts | — | **NOT RUN** | — | Unsafe/untrusted execution, possible file writes (browser artifacts), network, secrets | Brief §1, §6 |
| 5 | Docker / GitHub / LLM live calls | — | **NOT RUN** | — | Would require secrets and network | — |
| 6 | `py_compile` / import smoke | — | **NOT RUN** | — | Import is not a functional test (brief) | — |
| 7 | Browser / Chainlit live session | — | **NOT RUN** | — | Would start servers and execute repo code | — |

**No test names passed, failed, or skipped in this audit** because the suite was not executed.

### 5.2 Historical vs current

- `evaluation/metrics.py` `HISTORICAL_BASELINE` (accuracy ~0.55, macro-F1 ~0.48 on 92 samples) is **labelled historical** in source. **Not** reproduced here.
- Graph tests that “pass” in CI (`.github/workflows/ci.yml` runs `pytest backend/tests`) would prove topology against **mocks and missing-checkout**, not a real PR. CI status for current dirty tree was **not** fetched (no remote API).
- `playground/tests/verify_all_eight_agents.py` **injects** a fake patch after the coder returns empty changes (165–173). That is not evidence of code generation.

### 5.3 Pre-existing dirty tree (not cleaned)

Modified (among others): `.gitignore`, coder/debugger/graph/planner/pr/reviewer/schemas/test_runner, guardrails, embedding model, retrieval, Chainlit, evaluation metrics.  
Untracked: `memory.py`, `browser_runner.py`, `train_distilbert.py`, `evaluation/validate_system.py`, `playground/`, root `pytest.ini`.

This audit did not stage, commit, or revert any of it.

---

## Section 6 — Defects and False-Success Risks

Priority is “could a UI or test report success without the corresponding real work?”

### P0 — Confirmed by source inspection

1. **Coding path without a patch still looks like progress**  
   After approval, coder emits `code_generation_started` / `in_progress` with no `code_changes` (`coder/agent.py` 158–174). Graph tests treat that as success (`test_graph.py` 445–449). Chainlit on non-failed status shows “Plan Approved & Workflow Advanced” (`app.py` 585–587).

2. **Missing tests treated as pass (default)**  
   `route_test_runner` 399–404, 413. `strict_verification` off in `create_initial_state` and Chainlit. `evaluation/validate_system.py` 148–156 only asserts fail-closed **when the flag is True**.

3. **Stale or injected test results survive the test runner**  
   `test_runner/agent.py` 72–73 copies `state["test_results"]` if present. `test_graph.py` 517–521 injects failures; 590–593 injects `passed=True`. A passing injection never requires sandbox execution.

4. **Injected review approval reaches PR node**  
   `reviewer/agent.py` 33–51: if `review_findings` already set, return it unchanged. `test_graph.py` 625–643 injects `approved: True` and expects `submitting_pr`. Independent review is skippable.

5. **PR “started” with no URL and no GitHub call**  
   `pr_agent/agent.py` 102–119: `pull_request_url: None`, event `pr_creation_started`. `hasattr(create_pull_request)` is false, but without `strict_verification` the node still reports in-progress submission.

6. **Coder failure does not stop the graph**  
   Unconditional edge `coder` → `test_runner` (`graph.py` 491).

7. **Human-approval skip if state pre-seeded**  
   `graph.py` 114–129.

### Additional confirmed gaps (not always false-success, but workflow-breaking)

8. LLM `complete()` unimplemented — planner always deterministic; coder cannot generate.  
9. No sandbox execution even if Docker were installed — no `run_in_sandbox` symbol; test runner never calls a runner.  
10. Infrastructure-flavoured test details still go to debugger and consume `retry_count` (`debugger/agent.py` 34–40, 91). Spec: sandbox **error** should escalate, not retry as a code defect.  
11. Debugger never writes a new diff; retry loops the same empty coder.  
12. Live reviewer has no Revise outcome; legacy `ReviewOutcome` unused.  
13. REST ingest never starts the graph (`NoOpAgentGateway`).  
14. Dual `ApprovalDecision`: live model uses strings `"approved"`/`"rejected"`; legacy `routing.py` compares `ApprovalDecision.APPROVE` (`"approve"`) on `RunState`. Easy to confuse; live path uses `_get_approval_decision` == `"approved"`.  
15. `token` substring denylist (`output_guardrails.py` 123) can block legitimate paths containing “token”.

### Defects that need runtime to confirm

- Whether a local checkout path through Chainlit actually indexes and plans from real files (code path exists; this audit did not run it).  
- Whether interrupt/resume works on the installed LangGraph version in a live Chainlit session (tests exist, **NOT RUN**).  
- Whether `MemorySaver` thread resume is reliable under concurrent Chainlit users (process-global checkpointer).

---

## Section 7 — Missing Requirements

Mapped to spec (`docs/design/agent-state-and-graph.md`, `docs/design/schemas.md`, `docs/api-contract.md`, README).

| Requirement | Where it should live | Actual |
|---|---|---|
| Intake node writing identity/issue | Graph node | Missing on live graph; Chainlit/`create_initial_state` fills fields |
| Input guardrail as graph check + `injection_suspected` escalate | Graph + `StopReason` | Regex inside triage; live stop is `out_of_scope`/`safe_stop` |
| Trained classifier loaded in production | `ml_models/artifacts/` | Code yes; artifact **missing** in tree |
| DistilBERT as triage model | `train_distilbert.py` | Not used by `triage_node` |
| GitHub issue fetch | GitHub client + Chainlit/intake | Missing; URL parsed only |
| Repository clone / checkout service | GitHub + retrieval | Missing; `missing_checkout` reported, then planner still runs |
| HyDE embedding retrieval | query_transform + FAISS | LLM expand stub; HybridIndex default BM25 |
| Append-only plan versions; Reviewer sees **approved** version not latest | `RunState.plan_versions` | Live single `plan`; always `v1` |
| Plan schema validation node + bounded retry | `plan_validation` | Adequacy report only; not a router |
| Human **edit** + re-validation | `human_approval` | Missing on live path |
| REST resume-by-run-id | `api/runs.py` | Missing |
| Durable checkpointer | `checkpointer.py` | MemorySaver only |
| Coder file tools / real diff | `coder/agent.py` | Missing |
| Diff schema + denylist **graph gate** | `diff_gate` | Function `validate_diff_safety` exists; not a node; coder may not produce a diff |
| Sandbox apply-diff + tests; pass/fail/**error** | `sandbox/` + test_runner | Missing implementation |
| Test evidence linked to diff | `TestEvidence` / artifacts | Live `TestResults` optional and often unset |
| Debugger corrective patch | `debugger/agent.py` | Diagnosis only |
| Writer-blind 6-dimension review | `ReviewResult` + reviewer | Schema exists; live uses `ReviewFindings.approved` bool |
| Reviewer Revise → coder | `route_reviewer` | Missing |
| LLM-as-judge / MLflow spans | `mlflow_tracing.py` | Stub |
| GitHub PR create, never merge, never commit main | `github_client` + PR agent | Client missing; PR node does not call it |
| Live step events WebSocket | `websocket/live_stream.py` | Stub |
| AgentGateway → graph | `agent_gateway.py` | NoOp |
| Frontend dashboard | `frontend/src/components/*` | Comment stubs |
| DSPy | — | Absent |
| Memory consulted by Retrieval/Planner | `memory.py` | Module unused by agents |
| SWE-bench / fix-accuracy production metrics | `evaluation/` + metrics API | Empty provider; harnesses exist, not run here |

---

## Section 8 — Prioritized Completion Roadmap

### P0 — Security, approval bypass, false-success, critical workflow

| Item | Requirement | Evidence | Owner (from docs) | Definition of done |
|---|---|---|---|---|
| Default fail-closed tests | Missing `test_results` must not route to reviewer | `graph.py` 399–404; Chainlit unset flag | Sanjeevni (graph) | Default graph (and Chainlit) routes to `test_unverified_terminal`. Tests that currently expect `reviewing` without results are updated **by implementers later** (not this audit). |
| Do not copy injected test results | Test runner must execute or record unverified | `test_runner/agent.py` 72–73 | Sanjeevni + Tamanna | Node ignores pre-seeded results unless produced by this run’s sandbox with a diff hash. |
| Do not honor injected review_findings | Independent review | `reviewer/agent.py` 49–51; `test_graph.py` 625–643 | Sanjeevni | Reviewer always recomputes; injected approval cannot open PR path. |
| Halt after coder with no diff | Coder must produce `code_changes` | `coder/agent.py` 166–174; unconditional edge 491 | Sanjeevni | Empty/failed coder → terminal, not test_runner. |
| Implement or hard-block GitHub PR | No `submitting_pr` without API response | `pr_agent/agent.py` 102–119; `github_client.py` | Tamanna + Sanjeevni | Either create a real PR and store URL, or status `failed` with `pull_request_url is None` on **all** modes including default. |
| Approval interrupt cannot be skipped by seeding state | HITL | `graph.py` 114–129 | Sanjeevni | Interrupt always runs unless this thread already resumed the same frozen hash. |
| Wire REST ingest to graph **or** document that only Chainlit runs agents | API contract §5 | `NoOpAgentGateway` | Tamanna + Sanjeevni | `start_run` invokes `create_graph` with checkpointer; approval endpoint resumes. |

### P1 — Missing core agent/backend functionality

| Item | Requirement | Evidence | Owner | Definition of done |
|---|---|---|---|---|
| LLM `complete()` | Planner/coder/PR generation | `llm_provider_client.py` 19–25 | Tamanna | Real provider chain; agents consume `text`; failures are errors not silent fallback that looks complete |
| Coder applies scoped diffs | File tools + plan hash | `coder/agent.py` | Sanjeevni | Unified diffs for `affected_files` only; denylist enforced; partial write rollback |
| Docker/E2B `run_in_sandbox` | Isolated tests | `docker_manager.py` docstring | Tamanna | Apply diff, run command, return pass/fail/error + logs; host execution denied |
| GitHub read issue + clone or local checkout contract | Retrieval provenance | retrieval `missing_checkout`; Chainlit URL parser | Tamanna | Issue body from API; repo files on disk inside permitted root |
| Check in or generate triage artifacts | Classifier | No joblib in tree | Sanjeevni | `classify_with_confidence` loads committed or CI-built pipeline; unmocked test on sample issues |
| Plan validation + edit/reapprove | Spec §4–5 | Live graph skips | Sanjeevni | Invalid plan retries; human edit creates new hash; old approval invalid |
| Reviewer rubric + Revise | Spec | `ReviewResult` unused live | Sanjeevni | Approve/Revise/Block routed; Block ≠ PR |

### P2 — Reliability, integration, observability, memory, DSPy

| Item | Requirement | Evidence | Owner | Definition of done |
|---|---|---|---|---|
| Durable checkpointer | Spec §6 | MemorySaver | Tamanna / Sanjeevni | Resume after process restart |
| MLflow node wrappers | Spec §11 | stub file | Sanjeevni | Per-node spans; tracing failure never aborts run |
| Wire memory as advisory only | `memory.py` unused | Sanjeevni | Retrieval/planner may read; reviewer never does |
| Enable HybridIndex embeddings or drop the claim | `embed()` stub; HybridIndex default BM25 | Sanjeevni | method_name `hybrid_rrf` only when both sides ran |
| Metrics provider | EmptyMetricsProvider | Tamanna + Sanjeevni | `/metrics` reflects real runs, including NOT_VERIFIED |
| WebSocket events | stub | Tamanna | Dashboard/Chainlit subscribe to step events |
| Debugger patches + infra vs fail | debugger agent | Sanjeevni | ERROR → escalate; FAIL → bounded patch retry |
| DSPy | missing | unassigned | Only if product still requires it; otherwise mark out of scope in spec |

### P3 — UI polish, docs, nonessential

| Item | Requirement | Evidence | Definition of done |
|---|---|---|---|
| React dashboard components | README frontend | Comment-only TSX | Real Plan approval, diff, tests, artifacts against API |
| Align `graph.py` docstring with compiled graph | Lines 1–10 vs 443–517 | Doc matches live topology |
| Remove or isolate unused `completion_node` | Dead code | No accidental “Day 1 complete” messaging |
| Dual-schema cleanup | `AgentState` vs `RunState` | Single runtime state or a documented legacy-only package |
| Chainlit 3.14 sniffio monkeypatch | `app.py` 32–77 | Supported Python version without patching |

---

## Section 9 — Final Verdict

### 1. What is genuinely implemented?

- Live LangGraph topology for eight agent **names**, HITL interrupt, hash-bound approve/reject, rejection terminal, bounded debugger **counter**, several fail terminals (used only if flags/injections set).
- Triage **code**: sanitise, optional classifier, fail-closed on missing model / low confidence / injection (as out-of-scope).
- Retrieval **code**: permitted local path, file enumeration, BM25 index, honest `missing_checkout` / `no_results` / `indexing_failed`.
- Planner **code**: deterministic evidence-grounded plan, adequacy report, SHA-256 freeze.
- Path denylist helpers; issue text cleaning; FastAPI health/runs/issues/webhooks/artifacts/metrics **shapes**; Chainlit plan preview + approve/reject; in-memory run store; in-memory memory store module; browser-test **library** under `playground/` (optional extension).
- Legacy supervisor **routing unit logic** and fake-node skeleton (not the live product path).

### 2. What is genuinely verified?

**Nothing in this audit was demonstrated by executed tests or a live run.**  
Source inspection **confirms** (does not runtime-verify) the false-success routes and stub integrations above. Existing automated tests, if they pass in CI, primarily verify **graph topology, mocks, and injected results** (`test_graph.py`), plus isolated retrieval against **temporary** repos (not run here).

### 3. What is implemented but unverified?

- Local BM25 retrieval on a real directory.  
- Interrupt/resume with MemorySaver.  
- Classifier inference **if** a joblib artifact were present.  
- Browser runner against an allowlisted localhost URL.  
- Memory store isolation unit behaviour.  
- FastAPI route tests (defined, not run).

### 4. What remains stubbed or mocked?

- `llm_provider_client.complete`  
- `github_client`, `mcp_client`, `docker_manager`, `e2b_manager`, `mlflow_tracing`, `websocket/live_stream`, `sandbox/playwright_runner`  
- Coder generation, test execution, PR creation  
- `NoOpAgentGateway`, `EmptyMetricsProvider`  
- Embedding `embed()`  
- Frontend components  
- Graph tests: monkeypatched triage; injected `test_results` / `review_findings`  
- `verify_all_eight_agents.py` fabricated patch  
- `build_graph` fake agents  

### 5. What is missing?

- Trained triage artifact in the repository  
- Repo clone / GitHub issue fetch  
- Plan edit, plan_validation node, diff_gate node, escalate/finish on live graph  
- Durable checkpoints, approval REST, agent gateway wiring  
- Real diffs, sandbox, GitHub PRs  
- Six-dimension reviewer, Revise loop  
- DSPy, MLflow tracing, live event stream  
- Production metrics and end-to-end eval  

### 6. Can the current project safely complete a real issue-to-PR workflow?

**No.**  
It can triage (or fail closed), optionally index a **pre-existing local** tree, draft a plan, and pause for a human. After approval it does not reliably generate code, execute tests, or open a GitHub pull request. Default routing can present a completed/advanced run **without** those steps.

### 7. Single highest-priority next step

**Close the default false-success path:** treat missing/unexecuted tests as unverified (halt), stop copying injected `test_results`/`review_findings`, and refuse to leave the coder node without a real scoped diff — then implement Tamanna’s `complete()` and `run_in_sandbox` so the remaining pipeline has something real to verify.

---

## Appendix A — Key symbols and line references

| Symbol | File | Lines (approx.) |
|---|---|---|
| `create_workflow_graph` | `backend/app/agents/graph.py` | 443–517 |
| `route_test_runner` | same | 381–413 |
| `route_reviewer` | same | 425–438 |
| `human_approval_node` | same | 106–252 |
| `build_graph` / fakes | `graph.py` 656–714; `fake_nodes.py` | |
| `classify_issue` / `triage_node` | `backend/app/agents/triage/agent.py` | 50–218 |
| `classify_with_confidence` | `backend/app/ml_models/triage_classifier.py` | 97–123 |
| `retrieval_node` | `backend/app/agents/retrieval/agent.py` | 40–251 |
| `planner_node` | `backend/app/agents/planner/agent.py` | 520–603 |
| `coder_node` | `backend/app/agents/coder/agent.py` | 20–174 |
| `test_runner_node` | `backend/app/agents/test_runner/agent.py` | 24–113 |
| `debugger_node` | `backend/app/agents/debugger/agent.py` | 81–131 |
| `reviewer_node` | `backend/app/agents/reviewer/agent.py` | 20–110 |
| `pr_node` | `backend/app/agents/pr_agent/agent.py` | 19–119 |
| `complete` | `backend/app/integrations/llm_provider_client.py` | 19–25 |
| Chainlit flow | `chainlit_console/app.py` | 346–623 |
| `NoOpAgentGateway` | `backend/app/api/agent_gateway.py` | 42–54 |

## Appendix B — Test map (defined, not executed)

| File | Targets | Notes |
|---|---|---|
| `backend/tests/agents/test_graph.py` | Live graph topology, interrupt, hash reject, injected tests/reviews | Encodes missing-tests → `reviewing` as expected |
| `backend/tests/agents/test_triage.py`, `test_triage_classifier.py`, `test_triage_agent.py` | Classifier + live/legacy triage | Artifacts mocked; legacy uses `build_graph` |
| `backend/tests/retrieval/test_retrieval.py` | Real tmp-repo BM25 | Strongest retrieval tests; **NOT RUN** |
| `backend/tests/planner/test_planner.py` | Planner + graph | |
| `backend/tests/agents/test_routing.py` | Legacy `decide()` | Does not protect live `route_test_runner` |
| `backend/tests/agents/test_guardrails.py`, `test_schemas.py`, `test_query_transform.py` | Helpers | |
| `backend/tests/test_api_*.py`, `test_health.py`, `test_lifespan.py`, `test_run_store.py`, `test_config.py` | REST | Gateway still NoOp |
| `backend/tests/agents/test_train_triage.py`, `test_build_dataset.py`, `test_collect_issues.py`, `test_evaluate_triage.py`, `test_label_helper.py` | Training pipeline | No live artifact |
| `playground/tests/test_browser_testing.py` | Browser allowlist; some live Chromium if plugin present | May write artifacts under playground |
| `playground/tests/test_deep_agents_memory.py` | Memory isolation | Not wired to agents |
| `playground/tests/verify_all_eight_agents.py` | Direct node calls + fake patch | Not a pytest graph E2E |
| `evaluation/validate_system.py` | Unittest scenarios | Uses `strict_verification=True` for the critical missing-test case |
| `evaluation/swebench_lite/run_eval.py` | Benchmark harness | **NOT RUN**; would need models/network |

**Missing tests (critical):** default-mode (no strict flag) missing-tests must not reach reviewer; coder empty diff must not proceed; reviewer must ignore injected approval; PR must not start without GitHub response; Chainlit vs API parity; sandbox error vs fail; approval seed bypass.

---

*End of audit. No project files were modified except the creation of this document.*
