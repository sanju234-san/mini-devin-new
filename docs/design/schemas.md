# Mini-Devin schemas (design draft)
Status: draft, not yet confirmed with the project supervisor. These are designs for agents/schemas.py and docs/api-contract.md. Plan, diff and review result are validated by output_guardrails (schema check with bounded retry). Dangerous-path checks are done separately by the diff gate.

# 1. Plan (written by Planner or by a human editor)
| Field | Meaning |
|---|---|
| version_id | v1, v2, ... ; append-only, never edited in place |
| author | planner or human |
| intent | what the issue wants, one or two sentences |
| scope | what is included |
| non_goals | what is explicitly excluded |
| affected_files | files expected to change |
| requirements | list; each has id (R1, R2, ...), description, acceptance_criterion |
| steps | ordered list; each has description, requirement_ids it serves, files it touches |
| expected_tests | tests to add or run to show the requirements are met |

Approval state is not stored on the plan. The approved plan is identified by the approved_version pointer in run state; a plan version is superseded when a newer version exists.

Validation rules: at least one requirement; every step references existing requirement ids; every requirement is covered by at least one step; affected_files is not empty.

# 2. Diff (written by Coder; revised by Debugger)
| Field | Meaning |
|---|---|
| plan_version_id | the approved plan version this implements |
| file_changes | list; each has path, change_type (add, modify, delete), diff_text, requirement_ids it serves |
| tests_added | paths of new or changed test files |
| deviation_log | list; each has file_path, description, reason, affected requirement_id |
| change_summary | short factual note of what changed; NOT the Coder's reasoning |

Validation rules: plan_version_id must equal the approved version; every file change has at least one requirement id that exists in that plan version; a deviation entry whose file_path equals the changed file is required whenever a changed file is not in the plan's affected_files. The Coder's reasoning is never part of this schema or of run state.

Reviewer note: requirement_ids on file changes are Coder-supplied labels. The Reviewer must verify them independently and raise a finding for any tag that does not fit the change.

# 3. Review result (written by Reviewer)
| Field | Meaning |
|---|---|
| outcome | Approve, Revise or Block |
| plan_version_checked | the approved plan version used |
| dimensions | six entries: plan_coverage, correctness_and_verification, regression_risk, scope_control, security, documentation; each has result (pass, concern, fail) and evidence |
| findings | list; each has severity, location, related requirement_id, description |
| revision_instructions | required only when outcome is Revise |
| block_reason | required only when outcome is Block |

Validation rules: plan_version_checked must equal the approved version; Revise requires revision_instructions; Block requires block_reason.
Proposed outcome rule (not from the source documents; mark it as proposed): Approve when no dimension fails; Revise when a failure can be fixed by the Coder; Block when it cannot (for example a security problem or a violation of the approved plan). The rubric is a proposed design artifact, not an empirically validated metric.

# 4. Step event (emitted by every node; streamed by the backend)
| Field | Meaning |
|---|---|
| run_id, event_id, timestamp | identity and ordering |
| agent, step | which node and what it is doing |
| event_type | started, tool_call, completed, failed, retry, paused, escalated |
| tool_name | only for tool_call |
| model_info | kind (classifier, llm, static_analysis, none), name, provider, tier |
| tokens | input and output counts, only if an LLM was used |
| plan_version_id | when relevant |
| message | one short plain line describing the action, for example "Editing auth.py for R2". It must not contain agent reasoning. |

Full agent reasoning goes only to the MLflow trace, never into events.

# 5. Open items (do not decide)
Maximum sizes and length limits for fields; exact enum spellings; how large diffs are stored by reference; where events are stored for replay; whether a separate clearly-labelled agent-notes field is ever added.
