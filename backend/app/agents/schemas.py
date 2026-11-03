"""
Shared LangGraph state, schemas, and event models for Mini-Devin.

Defines the multi-agent workflow state, agent payload schemas,
and event logging structures across all stages from Triage to PR Agent.
"""

from __future__ import annotations

import datetime
from enum import Enum
import operator
from typing import Annotated, Any, ClassVar, Literal, Optional
from typing_extensions import TypedDict
import uuid

from pydantic import BaseModel, ConfigDict, Field, model_validator


class BaseSchema(BaseModel):
    """Base schema that forbids extra fields across all models."""
    model_config = ConfigDict(extra="forbid")



# ΓöÇΓöÇ Triage Schemas ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇ

class TriageClassification(str, Enum):
    """Categorization of incoming GitHub issues."""
    BUG = "bug"
    FEATURE = "feature"
    TEST = "test"
    DOCUMENTATION = "documentation"
    QUESTION = "question"
    OUT_OF_SCOPE = "out_of_scope"
    UNSUPPORTED = "unsupported"


class TriageCategory(str, Enum):
    """Classification of an incoming GitHub issue (legacy)."""
    BUG_FIX = "bug_fix"
    SMALL_FEATURE = "small_feature"
    TEST_WRITING = "test_writing"
    OUT_OF_SCOPE = "out_of_scope"


class TriageResult(BaseModel):
    """Triage evaluation result and routing determination."""
    classification: Optional[TriageClassification] = None
    is_supported: bool = True
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    reason: str = ""
    warnings: list[str] = Field(default_factory=list)
    # Legacy fields
    category: Optional[TriageCategory] = None
    cleaned_query: Optional[str] = None



# ΓöÇΓöÇ Retrieval Schemas ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇ

class RetrievedSnippet(BaseModel):
    """A retrieved code snippet from the repository."""
    file_path: str
    start_line: int = 1
    end_line: int = 1
    content: str = ""
    score: Optional[float] = None
    score_type: Optional[str] = None  # e.g., "lexical_bm25", "cosine_similarity"


class RetrievedContext(BaseModel):
    """Repository context retrieved for planning."""
    files: list[str] = Field(default_factory=list)
    snippets: list[RetrievedSnippet] = Field(default_factory=list)
    summary: str = ""
    is_mock: bool = False
    retrieval_status: str = "success"  # "success", "no_results", "missing_checkout", "indexing_failed"
    retrieval_method: str = "none"  # "faiss_embedding", "lexical_bm25", "none"
    error_message: Optional[str] = None
    # Context Budgeting Metadata
    char_budget: Optional[int] = None
    chars_used: int = 0
    is_truncated: bool = False
    is_omitted: bool = False


# ΓöÇΓöÇ Planner Schemas ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇ

class PlanEvidence(BaseModel):
    """Specific code evidence item referenced by the plan."""
    file_path: str
    start_line: int
    end_line: int
    symbol: Optional[str] = None
    observation: str


class RootCauseAnalysis(BaseModel):
    """Root-cause analysis separating evidence-supported facts from hypotheses."""
    evidence_backed_findings: list[str] = Field(default_factory=list)
    hypotheses: list[str] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def coerce_strings_to_lists(cls, data: Any) -> Any:
        if isinstance(data, dict):
            data = dict(data)
            for field in ("evidence_backed_findings", "hypotheses"):
                val = data.get(field)
                if isinstance(val, str):
                    data[field] = [val] if val.strip() else []
        return data


class PlanStep(BaseModel):
    """An individual atomic step in an implementation plan."""
    description: str
    step_number: int = 1
    target_file: str = ""
    action: Literal["create", "modify", "delete", "inspect"] = "modify"
    # Legacy fields
    requirement_ids: list[str] = Field(default_factory=list)
    files: list[str] = Field(default_factory=list)


class PlanAdequacyReport(BaseModel):
    """Deterministic verification of plan adequacy before human review."""
    is_adequate: bool = True
    score: float = Field(default=1.0, ge=0.0, le=1.0)
    findings: list[str] = Field(default_factory=list)
    missing_elements: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)


class ImplementationPlan(BaseModel):
    """Structured implementation plan proposed by the Planner Agent."""
    summary: str
    explanation: str
    steps: list[PlanStep] = Field(default_factory=list)
    affected_files: list[str] = Field(default_factory=list)
    estimated_complexity: Literal["low", "medium", "high"] = "medium"

    # Detailed engineering plan fields
    plan_version: str = "v1"
    plan_hash: str = ""
    evidence_items: list[PlanEvidence] = Field(default_factory=list)
    root_cause: Optional[RootCauseAnalysis] = None
    file_changes: list[dict[str, Any]] = Field(default_factory=list)
    dependencies_and_interfaces: list[str] = Field(default_factory=list)
    acceptance_criteria: list[str] = Field(default_factory=list)
    non_goals: list[str] = Field(default_factory=list)
    requirements: list[dict[str, Any]] = Field(default_factory=list)
    test_strategy: dict[str, Any] = Field(default_factory=dict)
    security_considerations: list[str] = Field(default_factory=list)
    risks_and_assumptions: list[str] = Field(default_factory=list)
    suggested_verification_commands: list[str] = Field(default_factory=list)
    provenance: str = "deterministic_evidence_synthesis"
    adequacy_report: Optional[PlanAdequacyReport] = None


# ── Human Approval Schemas ──────────────────────────────────────

class ApprovalDecision(BaseModel):
    """Human review decision on the proposed implementation plan."""
    decision: str = "pending"
    feedback: Optional[str] = None
    timestamp: Optional[str] = None
    plan_version: Optional[str] = None
    plan_hash: Optional[str] = None

    APPROVE: ClassVar[str] = "approve"
    EDIT: ClassVar[str] = "edit"
    REJECT: ClassVar[str] = "reject"
    APPROVED: ClassVar[str] = "approved"
    REJECTED: ClassVar[str] = "rejected"
    PENDING: ClassVar[str] = "pending"



# ΓöÇΓöÇ Event / Observability Schemas ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇ

class WorkflowEvent(BaseModel):
    """Structured workflow progress event emitted during graph execution."""
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str  # e.g., "workflow_started", "agent_step", "approval_required", "completed", "error"
    agent_name: str
    status: str      # e.g., "in_progress", "awaiting_approval", "success", "failed", "rejected"
    message: str
    timestamp: str = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())
    metadata: dict[str, Any] = Field(default_factory=dict)


def create_event(
    agent_name: str,
    event_type: str,
    status: str,
    message: str,
    metadata: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Helper to construct a validated event dictionary for the state reducer."""
    event = WorkflowEvent(
        agent_name=agent_name,
        event_type=event_type,
        status=status,
        message=message,
        metadata=metadata or {},
    )
    return event.model_dump()


# ΓöÇΓöÇ Execution, Verification & Review Schemas ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇ

class PatchMetadata(BaseModel):
    """Metadata describing a generated patch or file change."""
    file_path: str
    diff: str
    lines_added: int = 0
    lines_removed: int = 0


class TestResults(BaseModel):
    """Sandbox verification test run results."""
    __test__ = False
    passed: bool
    total_tests: int = 0
    passed_tests: int = 0
    failed_tests: int = 0
    skipped_tests: int = 0
    details: str = ""
    exit_code: Optional[int] = 0
    stdout: str = ""
    stderr: str = ""
    duration_seconds: float = 0.0
    command: str = ""
    infrastructure_failure: bool = False
    timed_out: bool = False
    sandbox_unavailable: bool = False


class ReviewFindings(BaseModel):
    """Automated reviewer findings comparing diff to the approved plan."""
    approved: bool = True
    score: float = Field(default=1.0, ge=0.0, le=1.0)
    comments: list[str] = Field(default_factory=list)
    verdict: str = "approve"  # "approve", "revise", "block"
    dimensions: dict[str, Any] = Field(default_factory=dict)
    revision_instructions: list[str] = Field(default_factory=list)
    linter_output: Optional[dict[str, Any]] = None


# ΓöÇΓöÇ LangGraph Workflow State ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇ

class AgentState(TypedDict, total=False):
    """
    Shared LangGraph workflow state across all Mini-Devin agents.
    
    Annotated fields use custom reducers (e.g. `events` accumulates entries).
    All other fields are replaced when updated by returning dicts from nodes.
    """
    # Execution & Tracking Identifiers
    run_id: str
    thread_id: str
    
    # Target Repository & Issue Information
    repo: str
    issue_url: Optional[str]
    issue_number: Optional[int]
    issue_title: str
    issue_body: str
    cleaned_query: Optional[str]
    repo_ref: Optional[str]
    commit_sha: Optional[str]
    snapshot_path: Optional[str]
    workspace_path: Optional[str]
    snapshot_truncated: bool
    snapshot_truncation_reason: Optional[str]
    issue_metadata: Optional[dict[str, Any]]
    
    # Workflow Stage Artifacts
    triage: Optional[TriageResult | dict[str, Any]]
    retrieved_context: Optional[RetrievedContext | dict[str, Any]]
    plan: Optional[ImplementationPlan | dict[str, Any]]
    plan_version: Optional[str]
    plan_hash: Optional[str]
    plan_adequacy: Optional[PlanAdequacyReport | dict[str, Any]]
    human_approval: Optional[ApprovalDecision | dict[str, Any]]
    
    # Retry & Loop Limits
    retry_count: int
    max_retries: int
    review_revisions: int
    max_review_revisions: int
    
    # Downstream Stage Metadata (populated in subsequent stages)
    code_changes: Optional[list[PatchMetadata | dict[str, Any]]]
    deviation_log: Optional[list[dict[str, Any]]]
    test_results: Optional[TestResults | dict[str, Any]]
    linter_results: Optional[dict[str, Any]]
    review_findings: Optional[ReviewFindings | dict[str, Any]]
    review_report_path: Optional[str]
    review_report_markdown: Optional[str]
    pull_request_package: Optional[dict[str, Any]]

    # Browser Testing Extension (optional; set by caller to enable Playwright runs)
    # browser_test_url  – explicit permitted URL to run browser scenarios against.
    #                     Must start with an allowlisted prefix (localhost/127.0.0.1).
    #                     Leave None to skip browser testing entirely.
    # browser_test_results – BrowserTestReport dict written by test_runner_node.
    browser_test_url: Optional[str]
    browser_test_results: Optional[dict[str, Any]]

    # Overall Workflow Status & Observability
    status: str  # "pending", "triaging", "retrieving", "planning", "awaiting_approval", "approved", "rejected", "out_of_scope", "completed", "failed"
    current_agent: Optional[str]
    error: Optional[str]
    events: Annotated[list[dict[str, Any]], operator.add]
    pull_request_url: Optional[str]


def serialize_plan_canonical(plan: Any) -> str:
    """
    Serialize an ImplementationPlan into deterministic canonical JSON.
    Excludes dynamic plan_hash so the hash computation is strictly idempotent.
    """
    import json
    if hasattr(plan, "model_dump"):
        data = plan.model_dump(mode="json")
    elif isinstance(plan, dict):
        data = dict(plan)
    else:
        data = {"summary": str(plan)}

    # Exclude plan_hash itself to prevent circular hashing
    data.pop("plan_hash", None)

    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def compute_plan_hash(plan: Any) -> str:
    """Compute deterministic SHA-256 hash of a plan's canonical serialization."""
    import hashlib
    canonical_str = serialize_plan_canonical(plan)
    return hashlib.sha256(canonical_str.encode("utf-8")).hexdigest()


def format_plan_as_markdown(plan: Any) -> str:
    """Format an ImplementationPlan as readable GitHub-flavored Markdown for side panel preview."""
    if hasattr(plan, "model_dump"):
        p = plan.model_dump(mode="json")
    elif isinstance(plan, dict):
        p = plan
    else:
        return f"# Implementation Plan\n\n{plan}"

    summary = p.get("summary", "Implementation Plan")
    version = p.get("plan_version", "v1")
    phash = p.get("plan_hash", "")
    short_hash = phash[:8] if phash else "unfrozen"
    complexity = p.get("estimated_complexity", "medium").upper()
    provenance = p.get("provenance", "deterministic_evidence_synthesis")
    explanation = p.get("explanation", "")

    lines = [
        f"# 📋 Implementation Plan: {summary}",
        f"**Plan Version:** `{version}` | **Plan Hash:** `{short_hash}` | **Complexity:** `{complexity}` | **Provenance:** `{provenance}`",
        "",
    ]

    adeq = p.get("adequacy_report")
    if adeq and isinstance(adeq, dict):
        status_label = "PASS — Adequate for Implementation" if adeq.get("is_adequate", True) else "NEEDS REVISION"
        score_pct = int(adeq.get("score", 1.0) * 100)
        lines.append("## 🔍 Plan Adequacy Assessment")
        lines.append(f"- **Verification Verdict:** `{status_label}` (Score: `{score_pct}%`)")
        for f in adeq.get("findings", []):
            lines.append(f"- ℹ️ {f}")
        for m in adeq.get("missing_elements", []):
            lines.append(f"- ⚠️ Missing: {m}")
        for r in adeq.get("recommendations", []):
            lines.append(f"- 💡 Recommendation: {r}")
        lines.append("")

    lines.extend([
        "## 1. Summary & Intended Behavior",
        explanation or summary,
        "",
    ])

    rc = p.get("root_cause")
    if rc:
        lines.append("## 2. Root Cause Analysis")
        findings = rc.get("evidence_backed_findings", [])
        if findings:
            lines.append("### 🔍 Evidence-Supported Findings")
            for f in findings:
                lines.append(f"- {f}")
        hypotheses = rc.get("hypotheses", [])
        if hypotheses:
            lines.append("### 💡 Hypotheses (Awaiting Further Evidence)")
            for h in hypotheses:
                lines.append(f"- {h}")
        lines.append("")

    evidence = p.get("evidence_items", [])
    if evidence:
        lines.append("## 3. Grounded Code Evidence")
        for ev in evidence:
            fpath = ev.get("file_path", "")
            sline = ev.get("start_line", 1)
            eline = ev.get("end_line", 1)
            sym = ev.get("symbol")
            sym_str = f" (`{sym}`)" if sym else ""
            obs = ev.get("observation", "")
            lines.append(f"- `{fpath}:{sline}-{eline}`{sym_str}: {obs}")
        lines.append("")

    file_changes = p.get("file_changes", [])
    if file_changes:
        lines.append("## 4. Proposed Changes by File")
        for fc in file_changes:
            lines.append(f"### `{fc.get('file_path', 'unknown')}`")
            if fc.get("module_or_function"):
                lines.append(f"- **Target Symbol:** `{fc.get('module_or_function')}`")
            lines.append(f"- **Change Description:** {fc.get('change_description', '')}")
        lines.append("")

    steps = p.get("steps", [])
    if steps:
        lines.append("## 5. Implementation Steps")
        for s in steps:
            num = s.get("step_number", 1)
            action = str(s.get("action", "modify")).upper()
            target = s.get("target_file", "")
            desc = s.get("description", "")
            lines.append(f"{num}. **[{action}]** `{target}`: {desc}")
        lines.append("")

    ac = p.get("acceptance_criteria", [])
    if ac:
        lines.append("## 6. Acceptance Criteria")
        for criterion in ac:
            lines.append(f"- [ ] {criterion}")
        lines.append("")

    ts = p.get("test_strategy", {})
    if ts:
        lines.append("## 7. Test Strategy")
        inspect_tests = ts.get("existing_tests_to_inspect", [])
        if inspect_tests:
            lines.append("### Existing Tests to Inspect")
            for t in inspect_tests:
                lines.append(f"- `{t}`")
        new_tests = ts.get("new_tests_to_add", [])
        if new_tests:
            lines.append("### New Tests to Add")
            for t in new_tests:
                lines.append(f"- {t}")
        lines.append("")

    deps = p.get("dependencies_and_interfaces", [])
    if deps:
        lines.append("## 8. Dependencies & Interfaces")
        for d in deps:
            lines.append(f"- {d}")
        lines.append("")

    sec = p.get("security_considerations", [])
    if sec:
        lines.append("## 9. Security & Guardrail Considerations")
        for s in sec:
            lines.append(f"- {s}")
        lines.append("")

    risks = p.get("risks_and_assumptions", [])
    if risks:
        lines.append("## 10. Risks & Assumptions")
        for r in risks:
            lines.append(f"- {r}")
        lines.append("")

    cmds = p.get("suggested_verification_commands", [])
    if cmds:
        lines.append("## 11. Suggested Verification Commands")
        lines.append("> *Note: These commands are suggested for execution in the test sandbox; they have not been run.*")
        lines.append("```bash")
        for c in cmds:
            lines.append(c)
        lines.append("```")
        lines.append("")

    return "\n".join(lines)


def create_initial_state(
    issue_title: str,
    issue_body: str = "",
    repo: str = "local/repo",
    issue_url: Optional[str] = None,
    issue_number: Optional[int] = None,
    repo_ref: Optional[str] = None,
    commit_sha: Optional[str] = None,
    snapshot_path: Optional[str] = None,
    workspace_path: Optional[str] = None,
    issue_metadata: Optional[dict[str, Any]] = None,
    run_id: Optional[str] = None,
    thread_id: Optional[str] = None,
    max_retries: int = 3,
) -> AgentState:
    """
    Construct a validated initial AgentState for workflow execution.
    
    Raises:
        ValueError: If required inputs (repo or issue_title) are missing or blank.
    """
    if not repo or not repo.strip():
        raise ValueError("Repository identifier ('repo') cannot be empty.")
    if not issue_title or not issue_title.strip():
        raise ValueError("Issue title cannot be empty.")

    active_run_id = run_id or f"run_{uuid.uuid4().hex[:12]}"
    active_thread_id = thread_id or active_run_id

    initial_event = create_event(
        agent_name="orchestrator",
        event_type="workflow_started",
        status="pending",
        message=f"Initialized workflow for {repo} (run_id: {active_run_id})",
        metadata={
            "repo": repo,
            "issue_title": issue_title,
            "issue_number": issue_number,
            "commit_sha": commit_sha,
            "snapshot_path": snapshot_path,
        "workspace_path": workspace_path,
        },
    )

    return {
        "run_id": active_run_id,
        "thread_id": active_thread_id,
        "repo": repo.strip(),
        "issue_url": issue_url.strip() if issue_url else None,
        "issue_number": issue_number,
        "issue_title": issue_title.strip(),
        "issue_body": issue_body.strip() if issue_body else "",
        "repo_ref": repo_ref,
        "commit_sha": commit_sha,
        "snapshot_path": snapshot_path,
        "workspace_path": workspace_path,
        "snapshot_truncated": False,
        "snapshot_truncation_reason": None,
        "issue_metadata": issue_metadata,
        "triage": None,
        "retrieved_context": None,
        "plan": None,
        "plan_version": None,
        "plan_hash": None,
        "human_approval": None,
        "retry_count": 0,
        "max_retries": max_retries,
        "review_revisions": 0,
        "max_review_revisions": 2,
        "code_changes": None,
        "deviation_log": [],
        "test_results": None,
        "linter_results": None,
        "review_findings": None,
        "pull_request_package": None,
        "status": "pending",
        "current_agent": None,
        "error": None,
        "events": [initial_event],
        "pull_request_url": None,
    }


# ── Legacy Architecture Schemas & Enums (Backward Compatibility) ──

class PlanAuthor(str, Enum):
    """Author identity for a plan version."""
    PLANNER = "planner"
    HUMAN = "human"


class ChangeType(str, Enum):
    """Type of file modification."""
    ADD = "add"
    MODIFY = "modify"
    DELETE = "delete"


class ReviewOutcome(str, Enum):
    """Overall outcome of a code review."""
    APPROVE = "approve"
    REVISE = "revise"
    BLOCK = "block"


class DimensionName(str, Enum):
    """The six evaluation dimensions for review."""
    PLAN_COVERAGE = "plan_coverage"
    CORRECTNESS_AND_VERIFICATION = "correctness_and_verification"
    REGRESSION_RISK = "regression_risk"
    SCOPE_CONTROL = "scope_control"
    SECURITY = "security"
    DOCUMENTATION = "documentation"


class DimensionResult(str, Enum):
    """Assessment result for a review dimension."""
    PASS = "pass"
    CONCERN = "concern"
    FAIL = "fail"


class EventType(str, Enum):
    """Type of streaming step event."""
    STARTED = "started"
    TOOL_CALL = "tool_call"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRY = "retry"
    PAUSED = "paused"
    ESCALATED = "escalated"


class ModelKind(str, Enum):
    """Category of model or execution tier."""
    CLASSIFIER = "classifier"
    LLM = "llm"
    STATIC_ANALYSIS = "static_analysis"
    NONE = "none"


class TestResult(str, Enum):
    """Execution result of the test runner."""
    PASS = "pass"
    FAIL = "fail"
    ERROR = "error"


class RunStatus(str, Enum):
    """High-level run execution status."""
    RUNNING = "running"
    PR_OPENED = "pr_opened"
    OUT_OF_SCOPE = "out_of_scope"
    ESCALATED = "escalated"


class StopReason(str, Enum):
    """Terminal stop reason for escalated runs."""
    INJECTION_SUSPECTED = "injection_suspected"
    PLAN_SCHEMA_RETRIES_EXHAUSTED = "plan_schema_retries_exhausted"
    PLAN_REVISIONS_EXHAUSTED = "plan_revisions_exhausted"
    DIFF_BLOCKED = "diff_blocked"
    DIFF_SCHEMA_RETRIES_EXHAUSTED = "diff_schema_retries_exhausted"
    DEBUGGER_LIMIT = "debugger_limit"
    REVIEWER_LIMIT = "reviewer_limit"
    REVIEWER_BLOCK = "reviewer_block"
    RUN_BUDGET = "run_budget"
    SANDBOX_ERROR = "sandbox_error"
    TRIAGE_UNCERTAIN = "triage_uncertain"
    ERROR = "error"


class DiffGateResult(str, Enum):
    """Outcome of the diff gate check."""
    CLEAN = "clean"
    SCHEMA_INVALID = "schema_invalid"
    DENYLIST_HIT = "denylist_hit"


class Requirement(BaseSchema):
    """Individual requirement extracted from an issue."""
    id: str
    description: str
    acceptance_criterion: str


class Plan(BaseSchema):
    """Implementation plan proposed by Planner or human editor."""
    version_id: str
    author: PlanAuthor
    intent: str
    scope: str
    non_goals: str
    affected_files: list[str]
    requirements: list[Requirement]
    steps: list[PlanStep]
    expected_tests: list[str]

    @model_validator(mode="after")
    def validate_plan(self) -> "Plan":
        """Validate requirement coverage, step references, and non-empty files."""
        if not self.requirements:
            raise ValueError("Plan must contain at least one requirement")
        if not self.affected_files:
            raise ValueError("Plan affected_files cannot be empty")
        req_ids = {r.id for r in self.requirements}
        covered_ids: set[str] = set()
        for idx, step in enumerate(self.steps):
            for rid in step.requirement_ids:
                if rid not in req_ids:
                    raise ValueError(f"Step {idx} references unknown requirement_id '{rid}'")
                covered_ids.add(rid)
        uncovered = req_ids - covered_ids
        if uncovered:
            raise ValueError(f"Requirements not covered by any step: {sorted(uncovered)}")
        return self


class ApprovalResponse(BaseSchema):
    """Payload provided when resuming from human approval interrupt."""
    decision: str
    edited_plan: Plan | None = None
    feedback: str | None = None

    @model_validator(mode="after")
    def validate_decision_payload(self) -> "ApprovalResponse":
        """Ensure payload matches decision type."""
        if self.decision == ApprovalDecision.EDIT:
            if self.edited_plan is None:
                raise ValueError("Decision 'edit' requires edited_plan")
        elif self.decision == ApprovalDecision.REJECT:
            if not self.feedback or not self.feedback.strip():
                raise ValueError("Decision 'reject' requires non-empty feedback")
        elif self.decision == ApprovalDecision.APPROVE:
            if self.edited_plan is not None or self.feedback is not None:
                raise ValueError("Decision 'approve' requires neither edited_plan nor feedback")
        return self


class FileChange(BaseSchema):
    """Individual file modification within a diff."""
    path: str
    change_type: ChangeType = ChangeType.MODIFY
    diff_text: str = ""
    content: Optional[str] = None
    requirement_ids: list[str] = Field(default_factory=list)

    @property
    def diff(self) -> str:
        return self.diff_text

    @model_validator(mode="before")
    @classmethod
    def populate_diff_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            # Tolerant alias: file_path -> path
            if "path" not in data and "file_path" in data:
                data["path"] = data.pop("file_path")
            elif "file_path" in data:
                data.pop("file_path")

            # Tolerant alias: requirement_id -> requirement_ids
            if "requirement_ids" not in data and "requirement_id" in data:
                req_val = data.pop("requirement_id")
                data["requirement_ids"] = [str(req_val)] if req_val else ["R1"]
            elif "requirement_id" in data:
                data.pop("requirement_id")

            if "diff" in data and "diff_text" not in data:
                data["diff_text"] = data.pop("diff")
            elif "diff" in data:
                data.pop("diff")
            if "change_type" not in data:
                data["change_type"] = ChangeType.MODIFY
        return data

    @model_validator(mode="after")
    def validate_requirements(self) -> "FileChange":
        """Ensure file change is associated with at least one requirement."""
        if not self.requirement_ids:
            self.requirement_ids = ["R1"]
        return self


class Deviation(BaseSchema):
    """Deviation from plan requirements or affected files."""
    file_path: str
    description: str
    reason: str
    requirement_id: str


class Diff(BaseSchema):
    """Diff produced by Coder or Debugger."""
    plan_version_id: str = "v1"
    file_changes: list[FileChange]
    tests_added: list[str] = Field(default_factory=list)
    deviation_log: list[Deviation] = Field(default_factory=list)
    change_summary: str = "Implementation changes"

    @model_validator(mode="before")
    @classmethod
    def populate_diff_defaults(cls, data: Any) -> Any:
        if isinstance(data, dict):
            # Tolerant alias: map 'diffs' -> 'file_changes' if model emitted 'diffs'
            if "file_changes" not in data and "diffs" in data:
                data["file_changes"] = data.pop("diffs")
            elif "diffs" in data:
                data.pop("diffs")

            if "plan_version_id" not in data:
                data["plan_version_id"] = "v1"
            if "tests_added" not in data:
                data["tests_added"] = []
            if "deviation_log" not in data:
                data["deviation_log"] = []
            if "change_summary" not in data:
                data["change_summary"] = "Implementation changes"
        return data

    @model_validator(mode="after")
    def validate_file_changes(self) -> "Diff":
        """Ensure diff contains file changes."""
        if not self.file_changes:
            raise ValueError("Diff must contain at least one file change")
        return self


def validate_diff_against_plan(diff: Diff, plan: Plan) -> list[str]:
    """Validate diff consistency against the approved plan."""
    errors: list[str] = []
    if diff.plan_version_id != plan.version_id:
        errors.append(f"Diff plan_version_id '{diff.plan_version_id}' != plan version_id '{plan.version_id}'")
    plan_req_ids = {r.id for r in plan.requirements}
    for fc in diff.file_changes:
        for rid in fc.requirement_ids:
            if rid not in plan_req_ids:
                errors.append(f"FileChange '{fc.path}' references unknown requirement '{rid}'")
    for dev in diff.deviation_log:
        if dev.requirement_id not in plan_req_ids:
            errors.append(f"Deviation references unknown requirement '{dev.requirement_id}'")
    plan_files = set(plan.affected_files)
    deviation_files = {d.file_path for d in diff.deviation_log}
    for fc in diff.file_changes:
        if fc.path not in plan_files:
            if fc.path not in deviation_files:
                errors.append(f"Changed file '{fc.path}' not in plan affected_files and lacks a deviation entry")
    return errors


class DimensionAssessment(BaseSchema):
    """Assessment of one of the six review rubric dimensions."""
    name: DimensionName
    result: DimensionResult
    evidence: str


class Finding(BaseSchema):
    """Specific finding or concern raised during review."""
    severity: str
    location: str
    requirement_id: str | None = None
    description: str


class ReviewResult(BaseSchema):
    """Output of the Reviewer Agent evaluation."""
    outcome: ReviewOutcome
    plan_version_checked: str
    dimensions: list[DimensionAssessment]
    findings: list[Finding]
    revision_instructions: str | None = None
    block_reason: str | None = None

    @model_validator(mode="after")
    def validate_review(self) -> "ReviewResult":
        """Validate dimension completeness, instructions/block reason, and proposed outcome rules."""
        dim_names = [d.name for d in self.dimensions]
        expected_dims = set(DimensionName)
        if len(dim_names) != len(expected_dims) or set(dim_names) != expected_dims:
            raise ValueError("Review must assess all 6 dimensions exactly once")
        if self.outcome == ReviewOutcome.REVISE:
            if not self.revision_instructions or not self.revision_instructions.strip():
                raise ValueError("Outcome 'revise' requires non-empty revision_instructions")
        elif self.outcome == ReviewOutcome.BLOCK:
            if not self.block_reason or not self.block_reason.strip():
                raise ValueError("Outcome 'block' requires non-empty block_reason")
        elif self.outcome == ReviewOutcome.APPROVE:
            if any(d.result == DimensionResult.FAIL for d in self.dimensions):
                raise ValueError("Cannot approve when any review dimension failed")
        return self


def validate_review_against_plan(review: ReviewResult, approved_version_id: str) -> list[str]:
    """Validate review result against approved plan version."""
    errors: list[str] = []
    if review.plan_version_checked != approved_version_id:
        errors.append(
            f"Plan version checked '{review.plan_version_checked}' does not match approved plan version '{approved_version_id}'"
        )
    return errors


class ModelInfo(BaseSchema):
    """Metadata regarding model and tier used by an agent step."""
    kind: ModelKind
    name: str | None = None
    provider: str | None = None
    tier: str | None = None


class TokenUsage(BaseSchema):
    """Token usage counts for LLM calls."""
    input_tokens: int
    output_tokens: int


class StepEvent(BaseSchema):
    """Live streaming event emitted during step execution."""
    run_id: str
    event_id: str
    timestamp: str
    agent: str
    step: str
    event_type: EventType
    tool_name: str | None = None
    model_info: ModelInfo
    tokens: TokenUsage | None = None
    plan_version_id: str | None = None
    message: str

    @model_validator(mode="after")
    def validate_event(self) -> "StepEvent":
        """Validate tool_name requirement and token presence only for LLM calls."""
        if self.event_type == EventType.TOOL_CALL:
            if not self.tool_name or not self.tool_name.strip():
                raise ValueError("Event type 'tool_call' requires tool_name")
        else:
            if self.tool_name is not None:
                raise ValueError("tool_name must be None when event_type is not 'tool_call'")
        if self.model_info.kind != ModelKind.LLM and self.tokens is not None:
            raise ValueError("tokens is allowed only when model_info.kind is 'llm'")
        return self


class GuardrailResult(BaseSchema):
    """Result of input guardrail check."""
    flagged: bool
    reason: str | None = None


class RetrievedChunk(BaseSchema):
    """Code snippet and reference retrieved from repository."""
    file_path: str
    snippet: str
    reference: str


class RetrievalResult(BaseSchema):
    """Collection of chunks retrieved by Retrieval agent."""
    chunks: list[RetrievedChunk]


class TestEvidence(BaseSchema):
    """Summary and pointer to test run results."""
    result: TestResult
    summary: str
    log_reference: str | None = None


class RunState(TypedDict, total=False):
    """Shared typed state dictionary managed across StateGraph nodes."""
    run_id: str
    repo: str
    issue_number: int
    issue_text: str
    guardrail_result: GuardrailResult
    triage_result: TriageResult
    retrieval_result: RetrievalResult
    plan_versions: Annotated[list[Plan], operator.add]
    approved_version: str | None
    approval_feedback: str | None
    current_diff: Diff | None
    test_evidence: TestEvidence
    review_result: ReviewResult | None
    plan_schema_retries: int
    diff_schema_retries: int
    plan_revisions: int
    debug_attempts: int
    review_revisions: int
    run_llm_calls: int
    stop_reason: StopReason | None
    status: RunStatus
    current_step: str
    artifact_references: dict[str, str]
    latest_event: StepEvent | None
    plan_validation_ok: bool | None
    diff_gate_result: DiffGateResult | None
    diff_producer: str | None
    last_approval: ApprovalResponse | None
    node_error: StopReason | None


class ReviewerInput(BaseSchema):
    """Writer-blind view of state provided to Reviewer Agent."""
    approved_plan: Plan
    diff: Diff
    test_evidence: TestEvidence | None
    retrieval_chunks: list[RetrievedChunk]
    deviation_log: list[Deviation]
    change_summary: str


def get_approved_plan(state: RunState) -> Plan:
    """Extract approved plan version from run state."""
    approved_id = state.get("approved_version")
    if not approved_id:
        raise ValueError("Missing 'approved_version' in state")
    for plan in state.get("plan_versions", []):
        if plan.version_id == approved_id:
            return plan
    raise ValueError(f"Approved plan version '{approved_id}' not found in state plan_versions")


def build_reviewer_input(state: RunState) -> ReviewerInput:
    """Build writer-blind input view for the Reviewer without coder reasoning."""
    approved_plan = get_approved_plan(state)
    diff = state.get("current_diff")
    if diff is None:
        raise ValueError("Missing 'current_diff' in state")
    test_evidence = state.get("test_evidence")
    retrieval = state.get("retrieval_result")
    retrieval_chunks = retrieval.chunks if retrieval is not None else []
    return ReviewerInput(
        approved_plan=approved_plan,
        diff=diff,
        test_evidence=test_evidence,
        retrieval_chunks=retrieval_chunks,
        deviation_log=diff.deviation_log,
        change_summary=diff.change_summary,
    )


def next_plan_version_id(state: RunState) -> str:
    """Return next version id 'v' followed by number of plans plus 1."""
    plans = state.get("plan_versions", [])
    return f"v{len(plans) + 1}"


def find_duplicate_plan_versions(state: RunState) -> list[str]:
    """Return any duplicated version_id values in state['plan_versions']."""
    plans = state.get("plan_versions", [])
    seen: set[str] = set()
    duplicates: list[str] = []
    for plan in plans:
        vid = plan.version_id
        if vid in seen:
            if vid not in duplicates:
                duplicates.append(vid)
        else:
            seen.add(vid)
    return duplicates


def plan_state(state: RunState, version_id: str) -> str:
    """Compute plan lifecycle state: approved, superseded, or pending."""
    plans = state.get("plan_versions", [])
    version_ids = [p.version_id for p in plans]
    if version_id not in version_ids:
        raise ValueError(f"Version ID '{version_id}' not found in state plan_versions")
    if version_id == state.get("approved_version"):
        return "approved"
    idx = version_ids.index(version_id)
    if idx < len(plans) - 1:
        return "superseded"
    return "pending"
