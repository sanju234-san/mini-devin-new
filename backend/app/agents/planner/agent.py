"""
Planner Agent Implementation for Mini-Devin.

Synthesizes issue specifications and authentic repository code evidence into a
detailed, structured engineering plan. Grounds all findings in RetrievedContext,
separates evidence from hypotheses, and freezes the plan with a deterministic
cryptographic hash before submitting for human approval.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
import re
from typing import Any, Optional

from langchain_core.runnables.config import RunnableConfig, var_child_runnable_config

from app.agents.model_router import route
from app.agents.schemas import (
    AgentState,
    ImplementationPlan,
    PlanAdequacyReport,
    PlanEvidence,
    PlanStep,
    RetrievedContext,
    RetrievedSnippet,
    RootCauseAnalysis,
    compute_plan_hash,
    create_event,
)

logger = logging.getLogger(__name__)

# Patterns to extract function and class declarations from snippets
_DEF_RE = re.compile(r"^\s*def\s+([A-Za-z0-9_]+)\s*\(", re.MULTILINE)
_CLASS_RE = re.compile(r"^\s*class\s+([A-Za-z0-9_]+)\s*[:\(]", re.MULTILINE)
_RAISE_RE = re.compile(r"^\s*raise\s+([A-Za-z0-9_]+)\b", re.MULTILINE)


def extract_symbols_from_code(code: str) -> list[str]:
    """Extract declared functions, classes, or exceptions from code snippet text."""
    symbols: list[str] = []
    seen: set[str] = set()

    for m in _CLASS_RE.finditer(code):
        sym = f"class {m.group(1)}"
        if sym not in seen:
            seen.add(sym)
            symbols.append(sym)

    for m in _DEF_RE.finditer(code):
        sym = f"def {m.group(1)}()"
        if sym not in seen:
            seen.add(sym)
            symbols.append(sym)

    for m in _RAISE_RE.finditer(code):
        sym = f"raise {m.group(1)}"
        if sym not in seen:
            seen.add(sym)
            symbols.append(sym)

    return symbols


def try_llm_plan_generation(
    title: str,
    body: str,
    retrieved: dict[str, Any],
) -> Optional[ImplementationPlan]:
    """
    Attempt to use the shared LLM client to produce a detailed engineering plan.

    Returns None if the shared LLM client raises NotImplementedError, is
    unimplemented, or fails, enabling clean deterministic synthesis fallback.

    After parsing the LLM response, any file path in the plan's affected_files
    or steps that is NOT in the retrieved file list is flagged: the plan's
    provenance is set to 'llm_generated_unverified_paths' and a risk note is
    appended. Verified paths retain provenance 'llm_generated'.
    """
    try:
        from app.integrations.llm_provider_client import complete
        from app.agents.issue_utils import format_issue_for_prompt

        snippets_text = "\n".join(
            f"--- {s.get('file_path')} (lines {s.get('start_line')}-{s.get('end_line')}) ---\n{s.get('content')}"
            for s in retrieved.get("snippets", [])
        )
        verified_files = retrieved.get("files", [])
        files_list_str = ", ".join(verified_files) if verified_files else "None"
        formatted_issue = format_issue_for_prompt(title, body)
        prompt = (
            f"You are the Planner Agent for Mini-Devin.\n"
            f"{formatted_issue}\n\n"
            f"Verified Repository Files:\n{files_list_str}\n\n"
            f"Code Evidence:\n{snippets_text}\n\n"
            f"Generate a detailed implementation plan. Your response must be a valid JSON object "
            f"matching the ImplementationPlan schema. Ensure all file paths, steps, and root cause "
            f"findings are grounded in the Verified Repository Files and Code Evidence above (do NOT invent non-existent file paths when modifying existing components).\n"
            f"CRITICAL: Do NOT include '.github/workflows/*', '.github/actions/*', '.env*', or secret/key files "
            f"in 'affected_files' or 'steps' unless the issue explicitly asks to modify GitHub Actions workflows.\n"
            f"Schema requirements:\n"
            f"- summary: Concise goal\n"
            f"- explanation: Detailed engineering reasoning\n"
            f"- steps: List of PlanStep objects (description, step_number, target_file, action)\n"
            f"- affected_files: List of file paths to be modified\n"
            f"- root_cause: RootCauseAnalysis object (evidence_backed_findings, hypotheses)\n"
            f"- acceptance_criteria: List of measurable criteria\n"
            f"- test_strategy: Dict with existing_tests_to_inspect and new_tests_to_add\n"
            f"- suggested_verification_commands: List of bash commands (e.g. pytest)\n"
            f"- provenance: Set to 'llm_generated'\n"
        )
        response = complete(prompt, agent_name="planner")
        if response and isinstance(response, str):
            s, e = response.find("{"), response.rfind("}")
            data = json.loads(response[s:e+1]) if (s != -1 and e != -1) else json.loads(response)
            for step in data.get("steps", []):
                if isinstance(step, dict) and step.get("action") not in ("create", "modify", "delete", "inspect"):
                    step["action"] = "create" if "add" in str(step.get("action", "")) else "modify"
            data["provenance"] = "llm_generated"
            plan = ImplementationPlan.model_validate(data)

            # Strip unsolicited protected/workflow paths from LLM plan unless issue explicitly targets workflows
            from app.guardrails.output_guardrails import validate_path_safety

            issue_text_lower = f"{title} {body}".lower()
            explicitly_requests_workflow = any(
                kw in issue_text_lower
                for kw in (".github/workflows", ".github/actions", "github action", "workflow file", "ci.yml", "ci.yaml")
            )
            allowed_wf_for_plan = (
                [p for p in plan.affected_files if p.strip().replace("\\", "/").startswith(".github/workflows/")]
                if explicitly_requests_workflow
                else []
            )
            safe_affected = [
                f for f in plan.affected_files
                if validate_path_safety(f, allowed_workflow_paths=allowed_wf_for_plan)[0]
            ]
            if safe_affected and len(safe_affected) != len(plan.affected_files):
                plan.affected_files = safe_affected
                filtered_steps: list[PlanStep] = []
                for step in plan.steps:
                    tf = (step.target_file or "").strip()
                    if tf and tf not in ("repository_root", "tests/", "repo_checkout") and not validate_path_safety(
                        tf, allowed_workflow_paths=allowed_wf_for_plan
                    )[0]:
                        continue
                    filtered_steps.append(step)
                if filtered_steps:
                    for idx, st in enumerate(filtered_steps, start=1):
                        st.step_number = idx
                    plan.steps = filtered_steps

            # Validate LLM-proposed file paths against retrieved evidence.
            retrieved_files: set[str] = set(retrieved.get("files", []))
            if retrieved_files:
                llm_paths: set[str] = set(plan.affected_files)
                for step in plan.steps:
                    if step.target_file:
                        llm_paths.add(step.target_file)
                unverified = llm_paths - retrieved_files - {"repository_root", "tests/", "repo_checkout", ""}
                if unverified:
                    plan.provenance = "llm_generated_unverified_paths"
                    plan.risks_and_assumptions = list(plan.risks_and_assumptions) + [
                        f"LLM proposed file path(s) not found in retrieved evidence "
                        f"(unverified hypotheses): {sorted(unverified)}"
                    ]

            return plan
    except (NotImplementedError, ImportError, Exception) as exc:
        logger.error("LLM plan generation failed: %s", exc)
        raise


def synthesize_deterministic_plan(
    title: str,
    body: str,
    retrieved: dict[str, Any],
    repo: str,
) -> ImplementationPlan:
    """
    Synthesize an evidence-grounded, detailed engineering plan deterministically
    from authentic repository snippets and issue specifications.
    
    Strictly preserves provenance: never fabricates non-existent lines or files.
    """
    retrieval_status = retrieved.get("retrieval_status", "success")
    snippets_data = retrieved.get("snippets", [])
    files = retrieved.get("files", [])

    # Case 1: Target repository checkout is missing.
    # Do NOT invent file paths; return an investigation/blocked plan with
    # empty affected_files and a single inspect step only.
    if retrieval_status == "missing_checkout":
        return ImplementationPlan(
            summary=f"Blocked — Repository Checkout Required: {title}",
            explanation=(
                f"Repository '{repo}' is not available as an approved local checkout. "
                "Mini-Devin cannot propose file-specific changes without authentic source access. "
                "Repository inspection and checkout are required before any file paths or "
                "root-cause findings can be verified."
            ),
            steps=[
                PlanStep(
                    step_number=1,
                    description=(
                        f"Request repository checkout for '{repo}' into an approved workspace "
                        "directory so that source files and tests can be inspected."
                    ),
                    target_file="repository_root",
                    action="inspect",
                ),
            ],
            # No invented paths — checkout is required first.
            affected_files=[],
            estimated_complexity="high",
            plan_version="v1",
            root_cause=RootCauseAnalysis(
                evidence_backed_findings=[],
                hypotheses=[
                    f"Issue '{title}' refers to repository '{repo}', which requires local checkout "
                    "before file paths and defect locations can be confirmed.",
                ],
            ),
            acceptance_criteria=[
                f"Repository '{repo}' is checked out into an approved workspace directory.",
                f"Root-cause analysis is performed on verified repository files for '{title}'.",
            ],
            test_strategy={
                "existing_tests_to_inspect": [],
                "new_tests_to_add": [
                    f"Add regression test for '{title}' once checkout provides verified file paths."
                ],
            },
            security_considerations=[
                "Do not execute remote repository code until repository checkout is validated.",
            ],
            risks_and_assumptions=[
                "Risk: No authentic repository evidence is currently available.",
                "Assumption: A repository checkout service will provide verified source access.",
            ],
            suggested_verification_commands=[
                "echo 'Awaiting repository checkout before test execution'",
            ],
            provenance="deterministic_unverified_missing_checkout",
        )

    # Case 2: Repository exists but yielded no matching code results
    if retrieval_status == "no_results" or not snippets_data:
        return ImplementationPlan(
            summary=f"Investigate: No Matching Snippets Found for '{title}'",
            explanation=(
                f"Retrieval scanned repository '{repo}', but no source snippets matched the "
                f"query terms for issue '{title}'. Additional issue details or manual inspection required."
            ),
            steps=[
                PlanStep(
                    step_number=1,
                    description=f"Inspect repository structure to identify files relevant to '{title}'.",
                    target_file="repository_root",
                    action="inspect",
                )
            ],
            affected_files=[],
            estimated_complexity="medium",
            plan_version="v1",
            root_cause=RootCauseAnalysis(
                evidence_backed_findings=[],
                hypotheses=[
                    f"Issue '{title}' may relate to an unindexed file or require creating new modules."
                ],
            ),
            acceptance_criteria=[
                f"Relevant source file for '{title}' identified.",
            ],
            test_strategy={
                "existing_tests_to_inspect": [],
                "new_tests_to_add": [f"Add test reproducing '{title}' once target file is located."],
            },
            security_considerations=[
                "Verify file paths and permissions before creating new files.",
            ],
            risks_and_assumptions=[
                "Risk: Retrieval query did not match existing identifier tokens in indexed files.",
            ],
            suggested_verification_commands=[
                "git status",
            ],
            provenance="deterministic_no_results",
        )

    # Case 3: Genuine repository evidence is available
    evidence_items: list[PlanEvidence] = []
    file_changes: list[dict[str, Any]] = []
    evidence_findings: list[str] = []
    existing_tests_to_inspect: list[str] = []

    for snip in snippets_data:
        fpath = snip.get("file_path", "")
        sline = snip.get("start_line", 1)
        eline = snip.get("end_line", 1)
        content = snip.get("content", "")

        symbols = extract_symbols_from_code(content)
        sym_label = ", ".join(symbols) if symbols else None

        obs = f"Indexed lines {sline}-{eline} containing: {symbols[0]}" if symbols else f"Indexed lines {sline}-{eline}"
        evidence_items.append(
            PlanEvidence(
                file_path=fpath,
                start_line=sline,
                end_line=eline,
                symbol=sym_label,
                observation=obs,
            )
        )
        evidence_findings.append(f"In `{fpath}` (lines {sline}-{eline}): {obs}")

        if "test" in fpath.lower() and fpath not in existing_tests_to_inspect:
            existing_tests_to_inspect.append(fpath)

    # Separate code files from test files — only use paths that are in the
    # retrieved file list (i.e. actually retrieved from the repository).
    code_files = [f for f in files if "test" not in f.lower()]
    target_code_file = code_files[0] if code_files else (files[0] if files else None)
    # Only include a test file if retrieval actually returned one; never invent a path.
    retrieved_test_file: Optional[str] = next(
        (f for f in files if "test" in f.lower()), None
    )

    primary_symbol = (
        evidence_items[0].symbol if evidence_items and evidence_items[0].symbol
        else "target logic"
    )

    # Build file_changes only for files confirmed by retrieved evidence.
    if target_code_file:
        file_changes.append({
            "file_path": target_code_file,
            "module_or_function": primary_symbol,
            "change_description": f"Refactor and add defensive error handling to address: {title}",
        })
    if retrieved_test_file:
        file_changes.append({
            "file_path": retrieved_test_file,
            "module_or_function": (
                f"test_{Path(retrieved_test_file).stem}_regression"
            ),
            "change_description": f"Add regression assertion verifying behavior reported in '{title}'",
        })

    # Build steps — Step 2/3 for test file only when a retrieved test file exists.
    steps: list[PlanStep] = []
    if target_code_file:
        steps.append(
            PlanStep(
                step_number=1,
                description=(
                    f"Inspect and modify `{target_code_file}` ({primary_symbol}) "
                    f"to satisfy intended behavior."
                ),
                target_file=target_code_file,
                action="modify",
                requirement_ids=["R1"],
            )
        )
    else:
        steps.append(
            PlanStep(
                step_number=1,
                description=(
                    f"Inspect repository structure for files relevant to '{title}'; "
                    "no source file was confirmed by retrieval evidence."
                ),
                target_file="repository_root",
                action="inspect",
                requirement_ids=["R1"],
            )
        )
    if retrieved_test_file:
        steps.append(
            PlanStep(
                step_number=2,
                description=(
                    f"Add regression test in `{retrieved_test_file}` asserting "
                    f"expected outcome for '{title}'."
                ),
                target_file=retrieved_test_file,
                action="modify",
                requirement_ids=["R2"],
            )
        )
        steps.append(
            PlanStep(
                step_number=3,
                description=(
                    f"Execute verification test suite against `{retrieved_test_file}` "
                    "to confirm resolution."
                ),
                target_file=retrieved_test_file,
                action="inspect",
                requirement_ids=["R2"],
            )
        )
    else:
        # Suggest adding a test but do not claim a path that was not retrieved.
        steps.append(
            PlanStep(
                step_number=2,
                description=(
                    f"Create a regression test for '{title}' in an appropriate test "
                    "file once the target source file is confirmed."
                ),
                target_file="tests/",
                action="inspect",
            )
        )

    # affected_files: only files actually confirmed by retrieved evidence.
    confirmed_files: list[str] = []
    if target_code_file:
        confirmed_files.append(target_code_file)
    if retrieved_test_file:
        confirmed_files.append(retrieved_test_file)
    affected_files = list(dict.fromkeys(confirmed_files))

    # Phrase the explanation using only confirmed file paths.
    confirmed_code_label = f"`{target_code_file}`" if target_code_file else "(source file TBD)"
    return ImplementationPlan(
        summary=f"Fix: {title}",
        explanation=(
            f"Evidence-grounded analysis of issue '{title}' against repository '{repo}'. "
            f"Grounded in {len(evidence_items)} retrieved snippet(s) from {confirmed_code_label}."
        ),
        steps=steps,
        affected_files=affected_files,
        estimated_complexity="medium" if len(evidence_items) <= 3 else "high",
        plan_version="v1",
        evidence_items=evidence_items,
        root_cause=RootCauseAnalysis(
            evidence_backed_findings=evidence_findings,
            hypotheses=[
                f"Defect reported in '{title}' occurs when `{primary_symbol}` receives "
                "unexpected input or state.",
            ],
        ),
        file_changes=file_changes,
        dependencies_and_interfaces=[
            f"Preserve public API and function signature compatibility in {confirmed_code_label}.",
        ],
        acceptance_criteria=[
            f"Issue '{title}' is resolved without regressions.",
            "All existing unit tests in repository continue to pass.",
        ] + (
            [f"Regression test in `{retrieved_test_file}` passes deterministically."]
            if retrieved_test_file else []
        ),
        non_goals=[
            "No large architectural refactors across multiple subsystems.",
            "Do not modify CI/CD workflows, deployment scripts, or .env files.",
            "Do not modify files outside of the approved affected_files scope.",
        ],
        requirements=[
            {"id": "R1", "description": f"Implement code fix for '{title}'."},
            {"id": "R2", "description": "Ensure zero regressions and verify test passing."},
        ],
        test_strategy={
            "existing_tests_to_inspect": existing_tests_to_inspect,
            "new_tests_to_add": (
                [f"`{retrieved_test_file}` regression test for '{title}'"]
                if retrieved_test_file
                else [f"Add a regression test for '{title}' once the target file is confirmed."]
            ),
        },
        security_considerations=[
            "Validate all inputs against unexpected boundary values and type mutations.",
            "Ensure no secrets, tokens, or credential strings are logged or exposed.",
        ],
        risks_and_assumptions=[
            f"Assumption: Retrieved snippet(s) in {confirmed_code_label} contain the entrypoint for the reported defect.",
            "Risk: Secondary side effects in consumers of this module if return signatures change.",
        ] + (
            [] if retrieved_test_file else
            ["Note: No test file was found in retrieved evidence; a test path must be confirmed after checkout."]
        ),
        suggested_verification_commands=(
            [f"pytest {retrieved_test_file} -v", "pytest tests/ -v"]
            if retrieved_test_file
            else ["pytest tests/ -v"]
        ),
        provenance="deterministic_evidence_synthesis",
    )


def evaluate_plan_adequacy(
    plan: ImplementationPlan,
    retrieved: Optional[dict[str, Any]] = None,
) -> PlanAdequacyReport:
    """
    Deterministic verification of plan adequacy before human review.

    Evaluates:
    1. Actionable implementation steps with target files.
    2. Explicit affected files list.
    3. Grounded code evidence or root cause analysis.
    4. Measurable acceptance criteria.
    5. Test verification strategy and commands.
    """
    findings: list[str] = []
    missing: list[str] = []
    recommendations: list[str] = []
    penalties = 0.0

    # 1. Implementation Steps
    if not plan.steps:
        missing.append("No atomic implementation steps defined.")
        recommendations.append("Define at least one structured step with a target file and action.")
        penalties += 0.35
    else:
        findings.append(f"Plan defines {len(plan.steps)} structured step(s).")
        unspecified_targets = [s for s in plan.steps if not s.target_file]
        if unspecified_targets:
            missing.append(f"{len(unspecified_targets)} step(s) lack an explicit target file.")
            penalties += 0.1

    # 2. Affected Files
    if not plan.affected_files:
        missing.append("Affected files list is empty.")
        recommendations.append("Specify the exact repository file paths expected to be modified.")
        penalties += 0.25
    else:
        findings.append(f"Affects {len(plan.affected_files)} file(s): {', '.join(plan.affected_files[:3])}")

    # 3. Grounded Code Evidence & Root Cause
    evidence_count = len(plan.evidence_items) if plan.evidence_items else 0
    rc_findings = (
        len(plan.root_cause.evidence_backed_findings)
        if plan.root_cause and plan.root_cause.evidence_backed_findings
        else 0
    )
    if evidence_count == 0 and rc_findings == 0:
        missing.append("No grounded code evidence citations or root cause findings.")
        recommendations.append("Ground plan in authentic repository snippets or root-cause findings.")
        penalties += 0.2
    else:
        findings.append(
            f"Supported by {evidence_count} grounded code citation(s) and {rc_findings} root-cause finding(s)."
        )

    # 4. Acceptance Criteria
    if not plan.acceptance_criteria:
        missing.append("Acceptance criteria are missing.")
        recommendations.append("Provide explicit checklist criteria to verify issue resolution.")
        penalties += 0.15
    else:
        findings.append(f"Specifies {len(plan.acceptance_criteria)} acceptance criteria.")

    # 5. Test Strategy & Verification Commands
    has_test_strat = bool(
        plan.test_strategy
        and (plan.test_strategy.get("existing_tests_to_inspect") or plan.test_strategy.get("new_tests_to_add"))
    )
    has_cmds = bool(plan.suggested_verification_commands)
    if not has_test_strat and not has_cmds:
        missing.append("Missing test strategy and verification commands.")
        recommendations.append("Include verification commands (e.g., pytest) to run in the sandbox.")
        penalties += 0.15
    else:
        findings.append("Verification commands and test strategy are documented.")

    score = max(0.0, round(1.0 - penalties, 2))
    is_adequate = score >= 0.65 and bool(plan.steps) and bool(plan.affected_files)

    return PlanAdequacyReport(
        is_adequate=is_adequate,
        score=score,
        findings=findings,
        missing_elements=missing,
        recommendations=recommendations,
    )


def planner_node(state: AgentState, config: Optional[RunnableConfig] = None) -> dict[str, Any]:
    """
    Planner Agent Node: Synthesizes issue details and code evidence into a concrete,
    frozen implementation plan.
    
    Evaluates plan adequacy, freezes with deterministic cryptographic hash,
    and pauses for human operator approval.
    """
    tier = route("planner")
    title = state.get("issue_title", "")
    body = state.get("issue_body", "")
    repo = state.get("repo", "local/repo")
    retrieved_raw = state.get("retrieved_context") or {}

    retrieved_dict: dict[str, Any] = (
        retrieved_raw.model_dump(mode="json")
        if hasattr(retrieved_raw, "model_dump")
        else dict(retrieved_raw)
    )

    workspace_path = state.get("workspace_path") or state.get("snapshot_path")
    ws_files: list[str] = []
    if workspace_path and Path(workspace_path).is_dir():
        ws_root = Path(workspace_path)
        skip_dirs = {".git", "node_modules", "dist", "build", ".next", "__pycache__", ".venv", "venv"}
        for p in ws_root.rglob("*"):
            if p.is_file() and not any(part in skip_dirs for part in p.parts):
                if p.suffix.lower() in {".js", ".jsx", ".ts", ".tsx", ".py", ".css", ".html"}:
                    ws_files.append(p.relative_to(ws_root).as_posix())
        if ws_files:
            q_words = {w.lower() for w in re.findall(r"[A-Za-z]{3,}", f"{title} {body}")}
            ranked_ws = sorted(
                ws_files,
                key=lambda fp: sum(2 for w in q_words if w in fp.lower()),
                reverse=True,
            )
            existing_ret_files = list(retrieved_dict.get("files") or [])
            merged_files = list(dict.fromkeys(existing_ret_files + ranked_ws[:35]))
            retrieved_dict["files"] = merged_files

    logger.info("Executing Planner node [tier=%s] for repo='%s'", tier, repo)

    # 1. Attempt LLM generation first via shared interface with active runnable config context
    config_token = None
    if config is not None:
        config_token = var_child_runnable_config.set(config)
    llm_error = None
    try:
        plan = try_llm_plan_generation(title=title, body=body, retrieved=retrieved_dict)
    except Exception as exc:
        llm_error = str(exc)
        plan = None
    finally:
        if config_token is not None:
            var_child_runnable_config.reset(config_token)

    if plan is not None and ws_files:
        ws_set = set(ws_files)
        q_words = {w.lower() for w in re.findall(r"[A-Za-z]{3,}", f"{title} {body}")}
        resolved_af: list[str] = []
        path_remap: dict[str, str] = {}
        for af in plan.affected_files:
            norm_af = af.strip().replace("\\", "/")
            if norm_af in ws_set:
                if norm_af not in resolved_af:
                    resolved_af.append(norm_af)
                continue
            # Skip invented non-existent test files if the repo doesn't have them
            if any(t_tok in norm_af.lower() for t_tok in (".test.", ".spec.", "/tests/", "__tests__")):
                continue
            af_tokens = {w.lower() for w in re.findall(r"[A-Za-z]{3,}", Path(norm_af).stem)} | q_words
            best_cand = max(
                ws_files,
                key=lambda fp: (
                    sum(3 for w in af_tokens if w in Path(fp).stem.lower())
                    + sum(1 for w in af_tokens if w in fp.lower())
                    + (2 if fp in (retrieved_dict.get("files") or [])[:5] else 0)
                ),
                default=None,
            )
            if best_cand:
                path_remap[af] = best_cand
                if best_cand not in resolved_af:
                    resolved_af.append(best_cand)
        if resolved_af:
            plan.affected_files = resolved_af
            plan.provenance = "llm_generated"
            for st in plan.steps:
                if st.target_file in path_remap:
                    st.target_file = path_remap[st.target_file]
                elif st.target_file and st.target_file.strip().replace("\\", "/") not in ws_set:
                    st.target_file = resolved_af[0]

    # 2. If LLM provider is unimplemented or fails, use evidence-grounded synthesizer
    if plan is None:
        allow_fallback = state.get("allow_deterministic_fallback", False) or os.getenv("ALLOW_DETERMINISTIC_FALLBACK", "false").lower() in ("true", "1")
        if not allow_fallback:
            err_msg = f"Planner failed: {llm_error or 'LLM plan generation failed'}"
            event = create_event(
                agent_name="planner",
                event_type="plan_generation_failed",
                status="failed",
                message=err_msg,
            )
            return {
                "status": "failed",
                "current_agent": "planner",
                "error": err_msg,
                "events": [event],
            }
        plan = synthesize_deterministic_plan(
            title=title,
            body=body,
            retrieved=retrieved_dict,
            repo=repo,
        )

    # 3. Deterministically evaluate plan adequacy
    adequacy = evaluate_plan_adequacy(plan=plan, retrieved=retrieved_dict)
    plan.adequacy_report = adequacy
    adequacy_dict = adequacy.model_dump(mode="json")

    # 4. Freeze the plan with a deterministic SHA-256 hash
    plan_dict = plan.model_dump(mode="json")
    plan_hash = compute_plan_hash(plan_dict)
    plan.plan_hash = plan_hash
    plan_dict["plan_hash"] = plan_hash

    event = create_event(
        agent_name="planner",
        event_type="plan_generated",
        status="awaiting_approval",
        message=(
            f"Implementation plan generated and frozen (v1:{plan_hash[:8]}). "
            f"Adequacy: {'PASS' if adequacy.is_adequate else 'NEEDS_REVISION'} ({int(adequacy.score * 100)}%). "
            "Awaiting human approval."
        ),
        metadata={
            "tier": tier.value,
            "plan_version": plan.plan_version,
            "plan_hash": plan_hash,
            "affected_files": plan.affected_files,
            "step_count": len(plan.steps),
            "evidence_count": len(plan.evidence_items),
            "provenance": plan.provenance,
            "adequacy_score": adequacy.score,
            "is_adequate": adequacy.is_adequate,
            "missing_elements": adequacy.missing_elements,
        },
    )

    return {
        "plan": plan_dict,
        "plan_version": plan.plan_version,
        "plan_hash": plan_hash,
        "plan_adequacy": adequacy_dict,
        "status": "awaiting_approval",
        "current_agent": "planner",
        "events": [event],
    }
