# Mini-Devin API contract (draft)
Status: PROPOSED by Sanjeevni for review by Tamanna (backend) and Nikunj (frontend). Not agreed until each owner confirms. Schemas referenced here are defined in docs/design/schemas.md; the graph is in docs/design/agent-state-and-graph.md. Each owner builds against a stub of the other side until the contract is agreed.

# 0. Ownership summary
| Interface | Provided by | Used by |
|---|---|---|
| 1. LLM completion | Tamanna (integrations/llm_provider_client.py) | Sanjeevni (agents/model_router.py) |
| 2. Sandbox run | Tamanna (sandbox/) | Sanjeevni (Test-Runner) |
| 3. GitHub read and write | Tamanna (integrations/github_client.py) | Sanjeevni (Retrieval, PR Agent) |
| 4. Live step events | Sanjeevni emits; Tamanna streams | Nikunj (dashboard, Chainlit) |
| 5. Plan approval | Tamanna (api/runs.py); Sanjeevni provides resume | Nikunj (PlanApproval screen) |
| 6. Evaluation metrics | Sanjeevni produces; Tamanna serves | Nikunj (EvalResults screen) |

# 1. LLM completion
Purpose: one function behind which provider fallback (Groq, then Gemini, then Hugging Face, then LM Studio) and 429 retry/backoff are hidden. No provider code in agents. The router chooses the tier; Tamanna's client chooses the provider.
Current stub: complete(prompt, agent_name) with PROVIDER_CHAIN of three providers. It needs extending.
| Request field | Meaning |
|---|---|
| run_id, agent_name | for logging and tracing |
| tier | strong or cheap (chosen by model_router) |
| messages | system and user messages |
| max_output_tokens | output limit |
| Response field | Meaning |
|---|---|
| text | the model output |
| model_name, provider, tier | what actually answered |
| fallback_used | true if a provider other than the first choice answered |
| input_tokens, output_tokens | usage |

Errors: AllProvidersExhaustedError when every provider fails.
OPEN: actual model names per tier; whether LM Studio is added to PROVIDER_CHAIN and config.py; structured-output support; run-wide LLM call budget enforcement (Supervisor counts calls).

# 2. Sandbox run
Purpose: apply a diff and run tests in an isolated Docker/E2B sandbox; never on the host or the real repository.
| Request field | Meaning |
|---|---|
| run_id | identifies the run |
| file_changes | the diff, per the Diff schema |
| test_command | OPEN (project default or specified) |
| timeout, resource limits | enforced by Tamanna |
| Response field | Meaning |
|---|---|
| result | pass, fail (real failing tests) or error (timeout, crash, infrastructure failure) |
| summary | short text |
| log_reference | pointer to the full log |
| artifact_references | screenshots, recordings |
| duration | run time |

Lifecycle: sandbox destroyed after each run.
OPEN: sandbox creation time and reuse across Debugger retries; where the Coder's file tools operate (local checkout or sandbox); where the Reviewer's linter or static analysis runs.

# 3. GitHub read and write
| Operation | Used by | Notes |
|---|---|---|
| read issue | intake, Retrieval | text is untrusted |
| read repo files, search code, list related commits | Retrieval | |
| open pull request (branch, title, body, linked artifacts) | PR Agent | agent opens PR; a human reviews and merges |

Rules: the agent never commits directly to main. Proposed: least-privilege token with read and write permissions separated.
OPEN: exact function names and the branch naming scheme.

# 4. Live step events
Schema: Step event in docs/design/schemas.md section 4. Each node emits one per step. Events carry a short action-level status line, never agent reasoning. Tamanna streams them per run_id over the WebSocket layer to the dashboard and the Chainlit console. Nikunj displays agent, step, event type, model used and the message.
OPEN: transport details (message framing, reconnect); where events are stored for replay.

# 5. Plan approval
| Step | Who | What |
|---|---|---|
| Pause | Sanjeevni | Run pauses at the human approval interrupt; a paused event with plan_version_id is emitted |
| Fetch plan | Tamanna endpoint | returns the plan to display, per the Plan schema |
| Decide | Nikunj UI to Tamanna endpoint | decision: approve, edit or reject; edited plan (for edit) or feedback text (for reject) |
| Resume | Sanjeevni provides a resume function by run_id; Tamanna's endpoint calls it using the shared checkpointer | run continues |

Rules: every new plan version needs fresh approval; only reject decisions count toward the plan revision limit.
OPEN: endpoint paths and HTTP methods (Tamanna); checkpointer backend.

# 6. Evaluation metrics
Produced by Sanjeevni (evaluation/, observability/); served by Tamanna's metrics route; shown by Nikunj's EvalResults screen.
| Metric | Notes |
|---|---|
| fix accuracy | |
| test-pass rate | |
| average self-correction iterations | |
| SWE-bench Lite mini-evaluation results | Week 15 |
| tokens per agent and model used | proposed addition |

OPEN: exact response format; per-run versus aggregate views.

# 7. Run status and stop reasons (for API and dashboard)
Final outcomes: pr_opened, out_of_scope, escalated. Stop reasons for escalated: injection_suspected, plan_schema_retries_exhausted, plan_revisions_exhausted, diff_blocked, diff_schema_retries_exhausted, debugger_limit, reviewer_limit, reviewer_block, run_budget, sandbox_error, error, triage_uncertain.

# 8. Open items summary
Model names per tier; retry limit values (config.py currently has one MAX_RETRY_ATTEMPTS; separate limits needed); checkpointer backend; sandbox timing and reuse; Coder tool location; Reviewer linter location; endpoint paths; metrics format; event storage; prompt caching ownership; who tests the Chainlit console.
