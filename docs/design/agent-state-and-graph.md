# 1. Purpose
Design of the LangGraph StateGraph for Mini-Devin. The Supervisor is deterministic code (no LLM): fixed rules read the run state and choose the next node. It supervises output validity, retry/budget bounds, failures, route integrity and step events. It does not judge code quality; the Test-Runner and the Reviewer do.

# 2. Run state
| Group | Holds | Written by | Read by |
|---|---|---|---|
| Identity | run_id, repo, issue number | intake | all |
| Issue | raw issue text | intake | input guardrail, Triage only |
| Guardrail result | pass/flagged, reason | input guardrail | Supervisor |
| Triage result | category, classifier confidence, cleaned query | Triage | Supervisor, Retrieval |
| Retrieval result | code chunks (references + short snippets) | Retrieval | Planner |
| Plan versions | append-only list; each has version id, author (Planner or human) | Planner, human | Coder, Reviewer, PR Agent |
| Approved version | pointer to the human-approved plan version | approval step | Coder, Reviewer |
| Approval feedback | reject reason text for the Planner | human_approval | Planner |
| Current diff | latest diff, deviation log, change summary | Coder, Debugger | diff gate, Test-Runner, Reviewer |
| Test evidence | result (pass, fail or error), short summary, reference to full log | Test-Runner | Debugger, Reviewer |
| Review result | Approve/Revise/Block, findings, six rubric scores, plan version checked | Reviewer | Supervisor, Coder, PR Agent |
| Counters | plan_schema_retries, diff_schema_retries, plan_revisions (counts reject decisions only; human edits do not count), debug_attempts, review_revisions, run_llm_calls | Supervisor | Supervisor |
| Stop reason | where and why a run ended early | Supervisor | API, dashboard |
| Artifact references | pointers to plan, diff, logs, screenshots, walkthrough | various | PR Agent |
| Status | current step, final outcome | Supervisor | API |

State rules:
1. The Coder's reasoning never enters state; it goes only to the MLflow trace (writer-blind Reviewer by construction).
2. Plan versions are append-only and immutable. A human edit creates a new version. The Reviewer always gets the approved version, never just the latest.
3. Large items (full logs, screenshots) are stored as artifact references, not inline.
4. Each node receives only the state slice it needs.
5. Step events are not kept in state. Each node emits them; Tamanna's stream carries them. Only the latest event is kept in state.
6. Each loop has its own counter.

# 3. Nodes
| Node | Kind | Reads | Writes | LLM? |
|---|---|---|---|---|
| intake | step | none | identity, issue | no |
| input_guardrail | check | issue | guardrail result | no |
| triage | agent | issue, guardrail result | triage result (cleaned by simple rules) | no (classifier) |
| retrieval | agent | cleaned query | retrieval result | HyDE only (small call) |
| planner | agent | retrieval result, cleaned query, feedback on earlier versions | new plan version | yes |
| plan_validation | check | latest plan version | validity; plan_schema_retries | no |
| human_approval | interrupt | latest valid plan version | approved version, or new plan version; plan_revisions (reject only) | no |
| coder | agent | approved plan version, retrieval result, review findings if revising | current diff, deviation log, change summary | yes |
| diff_gate | check | current diff | gate result | no |
| test_runner | agent (runs in Docker/E2B sandbox) | current diff | test evidence | no |
| debugger | agent | test evidence, diff (delta only) | revised diff; debug_attempts | cheap pre-classifier first, LLM only if ambiguous |
| reviewer | agent | approved plan version, current diff, test evidence, retrieval snippets, deviation log, change summary (NOT Coder reasoning) | review result; review_revisions on Revise | linter first, LLM for semantic review |
| pr_agent | agent | approved plan version, diff, test evidence, review result, artifact references | artifact references, PR link | yes |

# 4. Routing rules (all checked in code)
| After node | Condition | Next |
|---|---|---|
| input_guardrail | flagged | END escalated (injection_suspected) |
| input_guardrail | pass | triage |
| triage | classifier confidence below the minimum | END escalated (triage_uncertain) |
| triage | out_of_scope | END out_of_scope |
| triage | in scope | retrieval |
| retrieval | always | planner |
| planner | always | plan_validation |
| plan_validation | valid | human_approval |
| plan_validation | invalid, plan_schema_retries below limit | planner |
| plan_validation | invalid, limit reached | END escalated (plan_schema_retries_exhausted) |
| human_approval | approve | coder (approved version set) |
| human_approval | edit | new human-authored version appended, to plan_validation, then back to human_approval |
| human_approval | reject | planner with feedback; plan_revisions +1 |
| human_approval | plan_revisions (rejects) at limit | END escalated (plan_revisions_exhausted) |
| coder | always | diff_gate |
| diff_gate | schema invalid, diff_schema_retries below limit | back to the node that produced the diff |
| diff_gate | denylist hit (CI config deletion, .env/secrets, .github/) | END escalated (diff_blocked) |
| diff_gate | schema invalid, diff_schema_retries limit reached | END escalated (diff_schema_retries_exhausted) |
| diff_gate | clean | test_runner |
| test_runner | tests pass | reviewer |
| test_runner | tests fail (real failing tests), debug_attempts below limit | debugger |
| test_runner | tests fail, limit reached | END escalated (debugger_limit) |
| test_runner | result is error (sandbox timeout, crash or infrastructure failure) | END escalated (sandbox_error) |
| debugger | always | diff_gate |
| reviewer | Approve | pr_agent |
| reviewer | Revise, review_revisions below limit | coder, then diff_gate, test_runner, reviewer again |
| reviewer | Revise, limit reached | END escalated (reviewer_limit) |
| reviewer | Block | END escalated (reviewer_block) |
| pr_agent | always | END pr_opened (human reviews and merges) |
| any LLM call | run_llm_calls at run budget | END escalated (run_budget) |
| any node | tool, provider or sandbox failure | END escalated (error type); retry policy OPEN |

A low-confidence Triage result stops the run and asks a human; the minimum confidence is a placeholder to be tuned on validation data.

# 5. Human approval interrupt
The run pauses at human_approval after plan_validation passes. State is checkpointed. Resume payload: decision (approve, edit or reject), plus the edited plan (for edit) or feedback text (for reject). The resume is triggered by Tamanna's api/runs.py approval endpoint using the run id. The Coder cannot run until an approved version is set. Every new plan version needs a fresh human approval.

# 6. Checkpointing
State is saved after every node, enabling resume, replay and time-travel debugging by run id. Large items are held by reference. Checkpointer backend (SQLite or Postgres): OPEN.

# 7. Counters and end states
Counters: plan_schema_retries, diff_schema_retries, plan_revisions (rejects only), debug_attempts, review_revisions, run_llm_calls. Limit values: OPEN (to agree with Tamanna; config.py currently has a single MAX_RETRY_ATTEMPTS).
End states: pr_opened; out_of_scope; escalated with a stop reason from this list: injection_suspected, plan_schema_retries_exhausted, diff_schema_retries_exhausted, plan_revisions_exhausted, diff_blocked, debugger_limit, reviewer_limit, reviewer_block, run_budget, error, sandbox_error, triage_uncertain.
Run status values: running, pr_opened, out_of_scope, escalated.

# 8. Open items (do not decide)
Where the Coder's file tools run (local checkout or sandbox); sandbox creation time and reuse across Debugger retries; where the Reviewer's linter runs; retry policy for provider and sandbox errors; checkpointer backend; where step events are stored for replay; counter limit values; owner of prompt caching; LangGraph version in use (not pinned in requirements.txt; the interrupt, resume and checkpointer APIs vary between versions); maximum tool steps per looping node; whether the Reviewer may use read-only repo view and search tools; MLflow version and tracing API in use; where the MLflow server runs in development versus docker-compose; trace storage and retention; whether the LLM-as-judge model is the same as the agents' model; whether trace viewing is exposed in the dashboard.

# 9. Mapping to LangGraph
In LangGraph terms the Supervisor is not a node. It is the compiled graph plus small routing functions that only read state and name the next node. Nodes do the work.
| Design piece | LangGraph building block |
|---|---|
| Run state | One shared typed state; each node returns partial updates; append-only fields (plan versions, findings) use a reducer that adds to the list instead of replacing it |
| Nodes | 13 nodes: intake, input_guardrail, triage, retrieval, planner, plan_validation, human_approval, coder, diff_gate, test_runner, debugger, reviewer, pr_agent; plus two end nodes: escalate and finish |
| Fixed arrows | Plain edges: intake to input_guardrail, retrieval to planner, planner to plan_validation, coder to diff_gate, debugger to diff_gate |
| Decision arrows (section 4 routing table) | Conditional edges; one routing function per decision point returns the next node name |
| Human approval pause | An interrupt inside the human_approval node |
| Resume after approve, edit or reject | Invoke the graph again with a resume command carrying the decision; the value becomes what the interrupt call returns |
| Saved state, replay, time-travel | A checkpointer; interrupts require one; use an in-memory checkpointer for development and a durable one (SQLite or Postgres) for real runs |
| One run = one stored state | thread_id in the run config equals run_id |
| Counters and run budget | Fields in state; nodes increment them; routers compare them with the limits |

Design rules:
1. Nodes decide and record, routers only read. The guardrail, plan_validation, diff_gate and the test check write their verdict (including the stop reason) into state; routers read it. This puts the reason into traces and events. (Proposed.)
2. Keep the human_approval node tiny and put the interrupt first: a node re-runs from its beginning on every resume, so side effects before the interrupt would run twice. No loop of several interrupts inside one node; the edit and reject loops go back around the graph so each approval is a separate run of the node.
3. Before dispatching any LLM node, the router checks run_llm_calls against the run budget and sends the run to escalate if the cap is reached.
4. Every escalation goes through the single escalate node, which sets the final status and the stop reason, then ends. The finish node ends a successful run (pr_opened) or an out_of_scope run.
Exact API names and syntax depend on the installed LangGraph version (OPEN).

# 10. Reason, Act, Observe per node
The Synopsis says each agent node follows Reason, Act, Observe. This design applies it only where a node uses tools in a loop. This reading is proposed and still to be confirmed with the supervisor.
| Node | Loop? | Notes |
|---|---|---|
| coder | Yes | Reason: choose next step; Act: use a tool (file view, file edit, code search); Observe: read the tool result; stop when the diff is complete or max tool steps is reached |
| retrieval | Yes, small | Search tools after HyDE embedding and FAISS lookup; stops when enough relevant chunks are found or max tool steps is reached |
| debugger | Yes, only when the cheap pre-classifier is ambiguous and the LLM is used | Works on the delta only (diff and new error) |
| reviewer | OPEN | Whether it may use read-only repo view and search tools; if yes, the same loop shape applies |
| planner | No | Single structured LLM call; schema failures are handled by plan_validation and its retry counter |
| pr_agent | No | Single LLM call |
| intake, input_guardrail, triage, plan_validation, human_approval, diff_gate, test_runner | No | Checks, classifier, human pause, or sandbox execution |

Rules for looping nodes:
1. The loop's scratch work (reasoning, tool trace) stays inside the node and goes only to the MLflow trace. It is never written to run state or to step events.
2. Only the final output (for the Coder: the diff, deviation log and change summary) is written to state.
3. Every LLM call inside a loop counts toward run_llm_calls.
4. Each loop has a maximum number of tool steps. Value OPEN. When it is reached the node ends and writes what it has, or fails; the failure handling follows the error rule in section 4.
5. Tools are constrained: the Coder uses only the ACI tools (file view, edit, search); Retrieval and the Reviewer (if allowed) use read-only tools.

# 11. Observability and MLflow
MLflow (self-hosted) provides tracing, evaluation logging and prompt versioning. It is owned by Sanjeevni (observability/mlflow_tracing.py, observability/evaluation.py).

## 11.1 Tracing
| Item | Design |
|---|---|
| Trace per run | One trace per run, using the same run_id as the graph |
| Spans | Each graph node is a span; inside looping nodes (coder, retrieval, debugger) each LLM call and tool call is a child span |
| Coder reasoning | Goes only into the trace, never into run state or step events |
| Access | The trace may contain private agent reasoning. It is not read by any agent (the Reviewer never reads it) and is not served to the UI by default |
| Link to events | Step events and trace spans share run_id and event_id so a status line can be traced to its spans |

## 11.2 Where the hooks live
| Hook | Location | What it logs |
|---|---|---|
| Node wrapper | Applied from outside to each node when the graph is built (graph.py); agent logic contains no MLflow calls | node name, start and end time, outcome, counters |
| LLM call point | Inside model_router.py, around the call to the shared completion interface | model name, provider, tier, input and output tokens, fallback_used |

## 11.3 Logged at the end of each run
Final status and stop reason; approved plan version id; all counter values; models used per step; tokens per agent; whether any step used a fallback provider; total duration.

## 11.4 Prompt versioning
Every agent prompt has a version id. The version id is recorded in the trace for each LLM call so results can be tied to the prompt that produced them.

## 11.5 Evaluation
| Metric | Notes |
|---|---|
| fix accuracy | |
| test-pass rate | |
| average self-correction iterations | |
| tokens per agent and models used | supports the cost-optimisation claim |
| SWE-bench Lite mini-evaluation results | Week 15 |
| LLM-as-judge scores | |

Evaluation runs that used a fallback provider are flagged so results stay comparable; models should be pinned for benchmark runs.

## 11.6 Safety rules
1. A tracing or logging failure must never stop a run: log a warning and continue.
2. Secrets are redacted before anything is logged.
3. The trace is a debugging and evaluation record, not an input to any agent.

## 11.7 Build order
Graph skeleton with fake agents first; then add the node wrapper to prove the trace shape; then add evaluation logging once real agents produce results.
