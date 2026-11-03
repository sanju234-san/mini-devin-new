# Agents Implementation Status Audit

| Agent | Status | Real-verified | Missing requirements | Evidence |
| :--- | :--- | :--- | :--- | :--- |
| **Triage** | FULL | No | None | `backend/app/agents/triage/agent.py`, `test_triage_agent.py` |
| **Retrieval** | FULL | No | None | `backend/app/agents/retrieval/agent.py`, `test_retrieval.py` |
| **Planner** | PARTIAL | No | Pydantic-validated bounded retry (fallback logic exists, but LLM retry is implicit/missing) | `backend/app/agents/planner/agent.py`, `test_graph.py` |
| **Coder** | FULL | No | None | `backend/app/agents/coder/agent.py`, `test_coder_hardened.py` |
| **Test-Runner** | STUB | No | Isolated sandbox execution (explicitly unimplemented in code) | `backend/app/agents/test_runner/agent.py` |
| **Debugger** | PARTIAL | No | LLM fallback for ambiguous errors (only rule-based logic implemented) | `backend/app/agents/debugger/agent.py` |
| **Reviewer** | PARTIAL | No | Linter first (only manual checks and guardrails implemented) | `backend/app/agents/reviewer/agent.py` |
| **PR Agent** | STUB | No | Real PR creation (explicitly unimplemented in code) | `backend/app/agents/pr_agent/agent.py` |
