# Mini-Devin Baseline Audit Report
**Timestamp:** 2026-10-25 14:00 UTC
**Branch:** `wip/agents-checkpoint`
**Working Tree Status:** Modified: `backend/app/agents/planner/agent.py`, `backend/app/agents/retrieval/agent.py`, `backend/tests/agents/test_triage_gaps.py`, `backend/tests/retrieval/conftest.py`. Untracked: `backend/app/agents/issue_utils.py`, `backend/tests/agents/conftest.py`, `backend/tests/coder/conftest.py`, `docs/audit/agents-status.md`, `docs/design/sandbox-and-github-contract.md`.

## 1. Executive Summary
The project is in a **transitional state**. The core orchestrator (LangGraph) is wired, and several agents (Triage, Retrieval, Coder) have real logic. However, the pipeline is functionally blocked at the **Test-Runner** and **PR Agent** stages due to completely unimplemented sandbox and GitHub integrations. Safety guardrails for input/output and plan integrity are implemented and verified via unit tests.

## 2. Architecture and Graph Workflow
The system uses a LangGraph `StateGraph` defined in `backend/app/agents/graph.py:443`.
**Workflow:** `START` $\rightarrow$ `triage` $\rightarrow$ `retrieval` $\rightarrow$ `planner` $\rightarrow$ `human_approval` (Interrupt) $\rightarrow$ `coder` $\rightarrow$ `test_runner` $\rightarrow$ `reviewer` $\rightarrow$ `pr_agent` $\rightarrow$ `END`.
**Routing:** Conditional edges are used for safe stops (Triage), rejections (Approval), and debug loops (Test-Runner $\rightarrow$ Debugger $\rightarrow$ Coder).

## 3. Eight-Agent Evidence Table

| Agent | Implemented Behavior | Safety Checks | Tests | Gaps | Real LLM/SB/GH |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Triage** | Classifier-based cat. | Input guardrails | `test_triage_agent.py` | None | No |
| **Retrieval** | FAISS/Lexical search | Path safety | `test_retrieval.py` | None | No |
| **Planner** | LLM $\rightarrow$ Deterministic | Plan adequacy check | `test_graph.py` | Bounded retry | No |
| **Coder** | Pydantic Diff gen | Hash check, Scope | `test_coder_hardened.py` | None | No |
| **Test-Runner**| Pass-through state |- | None | **No Sandbox** | **Blocked** |
| **Debugger** | Rule-based diagnosis | Bounded retries | `test_graph.py` | LLM escalation | No |
| **Reviewer** | State-based check | Diff safety | `test_graph.py` | Linter pass | No |
| **PR Agent** | PR meta-generation | Review approval | `test_graph.py` | **No GH Client** | **Blocked** |

## 4. Safety and Approval Controls Audit
- **Approval/Hash/Version:** `coder_node` enforces `approved_hash` match (`backend/app/agents/coder/agent.py:115-122`). Verified by `test_coder_hardened.py:test_coder_hash_mismatch_on_approved_version`.
- **Diff Gates:** `validate_diff_safety` used in Coder and Reviewer (`backend/app/agents/coder/agent.py:225`).
- **Writer-Blind Reviewer:** `build_reviewer_input` explicitly excludes coder reasoning (`backend/app/agents/schemas.py:566-569`).
- **Provider Routing:** `ModelTier` system in `backend/app/agents/model_router.py:19-24`.
- **Retrieval Constraint:** `cleaned_query` is generated in Triage and used in Retrieval (`backend/app/agents/triage/agent.py:194`, `backend/app/agents/retrieval/agent.py:165`).
- **PR Authorization:** `pr_node` checks `review_approved` (`backend/app/agents/pr_agent/agent.py:31-38`).

## 5. Test Results Table

| Command | Exit Code | Passed | Failed | Skipped | Result |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `pytest backend/tests/agents/test_routing.py` | 0 | 54 | 0 | 0 | PASS |
| `pytest backend/tests/agents/test_schemas.py` | 0 | 27 | 0 | 0 | PASS |
| `pytest backend/tests/agents/test_guardrails.py` | 0 | 48 | 0 | 0 | PASS |
| `pytest backend/tests/agents/test_query_transform.py` | 0 | 29 | 0 | 0 | PASS |
| **Total (Safe Subset)** | **0** | **158** | **0** | **0** | **PASS** |

## 6. Network and Provider Activity
- **Findings:** All executed tests use mocks or pure logic. No network calls were detected.
- **Limitations:** Real LLM provider integration is not tested in this audit to avoid cost/side-effects.

## 7. Ownership and Uncommitted Work
- **Modified Files:** `planner/agent.py`, `retrieval/agent.py`, `test_triage_gaps.py`, `retrieval/conftest.py`.
- **Untracked:** `issue_utils.py`, `conftest.py` (agents/coder).
- **Conflicts:** No modifications made to files in `origin/tamanna` (all `backend/app/sandbox` and `github_client.py` were read-only).

## 8. Prior Claims Verification
- **Claim:** "Full workflow works" $\rightarrow$ **UNVERIFIED**. Blocked by Sandbox/GitHub stubs.
- **Claim:** "Linter first in Reviewer" $\rightarrow$ **FALSE**. Only basic state checks in `backend/app/agents/reviewer/agent.py`.

## 9. Prioritized Next Steps
1. **Confirmed Defect:** Implement `app.sandbox.docker_manager` to unblock Test-Runner.
2. **Confirmed Defect:** Implement `app.integrations.github_client` to unblock PR Agent.
3. **Suspected Defect:** Verify if `planner_node` correctly handles bounded retries for LLM failures.

## 10. Source Reference Index
- **Graph Topology:** `backend/app/agents/graph.py:443-518`
- **Coder Safety:** `backend/app/agents/coder/agent.py:56-122`
- **Triage Logic:** `backend/app/agents/triage/agent.py:50-165`
- **Reviewer Isolation:** `backend/app/agents/schemas.py:524-575`
- **Routing Tiers:** `backend/app/agents/model_router.py:26-36`
