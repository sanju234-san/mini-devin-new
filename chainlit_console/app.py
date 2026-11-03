"""
Chainlit Live Agent Console for Mini-Devin.

Connects directly to Mini-Devin's LangGraph supervisor workflow, enabling
interactive issue submission, real-time step inspection, and human-in-the-loop
plan approval/rejection with persistent checkpoints.
"""

from __future__ import annotations

import json
import logging
import os
import re
import sys
import uuid
from pathlib import Path
from typing import Any, Optional

# Ensure the backend directory is strictly prioritized in sys.path and console_dir doesn't shadow 'app'
backend_dir = str(Path(__file__).resolve().parent.parent / "backend")
console_dir = str(Path(__file__).resolve().parent)
while backend_dir in sys.path:
    sys.path.remove(backend_dir)
while console_dir in sys.path:
    sys.path.remove(console_dir)
sys.path.insert(0, backend_dir)

# Ensure 'app' refers to backend/app package, not this file:
if "app" in sys.modules and not hasattr(sys.modules["app"], "__path__"):
    del sys.modules["app"]

# Python 3.14 compatibility patch for anyio / sniffio async loop and task detection
if sys.version_info >= (3, 14):
    try:
        import asyncio
        import sniffio

        _orig_asyncio_current_task = asyncio.current_task
        def _safe_asyncio_current_task(loop=None):
            t = _orig_asyncio_current_task(loop)
            if t is not None:
                return t
            try:
                if loop is None:
                    loop = asyncio.get_running_loop()
                tasks = [task for task in asyncio.all_tasks(loop) if not task.done()]
                if tasks:
                    return tasks[-1]
            except Exception:
                pass
            return None
        asyncio.current_task = _safe_asyncio_current_task

        _orig_sniffio = sniffio.current_async_library
        def _patched_sniffio():
            try:
                asyncio.get_running_loop()
                return "asyncio"
            except RuntimeError:
                pass
            return _orig_sniffio()
        sniffio.current_async_library = _patched_sniffio

        import anyio._core._eventloop as _anyio_el
        _orig_anyio = _anyio_el.current_async_library
        def _patched_anyio():
            try:
                asyncio.get_running_loop()
                return "asyncio"
            except RuntimeError:
                pass
            return _orig_anyio()
        _anyio_el.current_async_library = _patched_anyio

        import anyio._backends._asyncio as _anyio_aio
        _anyio_aio.current_task = _safe_asyncio_current_task
    except Exception as _patch_err:
        pass

import chainlit as cl
from langgraph.types import Command

from app.agents.checkpointer import get_checkpointer
from app.agents.graph import create_graph
from app.agents.schemas import create_initial_state, format_plan_as_markdown
from app.integrations.issue_intake import process_issue_intake

logger = logging.getLogger(__name__)

# Pattern to recognize GitHub issue URLs
_GITHUB_ISSUE_RE = re.compile(
    r"^https?://github\.com/(?P<owner>[^/]+)/(?P<repo>[^/]+)/issues/(?P<number>\d+)/?$",
    re.IGNORECASE,
)


def parse_issue_input(text: str) -> tuple[str, str, str, Optional[str], Optional[int]]:
    """
    Parse user message into (repo, title, body, issue_url, issue_number).
    
    Supports:
    1. Full GitHub Issue URL: https://github.com/owner/repo/issues/123
    2. Format "owner/repo: Issue Title\nOptional Body"
    3. Plain text: defaults to local demo repository
    """
    raw = text.strip()
    match = _GITHUB_ISSUE_RE.match(raw)
    if match:
        owner = match.group("owner")
        repo_name = match.group("repo")
        issue_number = int(match.group("number"))
        repo = f"{owner}/{repo_name}"
        title = f"Fix defect reported in #{issue_number} for {repo}"
        body = f"Automated bug report imported from {raw}. Investigate and resolve defect."
        return repo, title, body, raw, issue_number

    lines = raw.split("\n", 1)
    first_line = lines[0].strip()
    body = lines[1].strip() if len(lines) > 1 else ""

    if ":" in first_line:
        parts = first_line.split(":", 1)
        repo_candidate = parts[0].strip()
        title_candidate = parts[1].strip()
        if "/" in repo_candidate and title_candidate:
            return repo_candidate, title_candidate, body, None, None

    repo = "demo-org/demo-repo"
    title = first_line
    return repo, title, body, None, None


def build_plan_document(plan: Any, title: str = "", plan_hash: str = "") -> str:
    """
    Render an authentic, readable Markdown implementation plan document
    for preview in Chainlit's right-side panel.
    
    Guarantees:
    - Never displays raw structured JSON/dict text or standalone hashes as body content.
    - Presents formatted hierarchical markdown headings (#, ##, ###).
    - Details numbered implementation steps with action verbs and target file paths.
    - Renders evidence citations, root-cause findings, and file modifications when present.
    - Treats plan hash strictly as secondary provenance metadata in the document header.
    """
    if plan is None:
        p: dict[str, Any] = {}
    elif hasattr(plan, "model_dump"):
        p = plan.model_dump(mode="json")
    elif isinstance(plan, str):
        raw_str = plan.strip()
        if raw_str.startswith("{") and raw_str.endswith("}"):
            try:
                p = json.loads(raw_str)
            except Exception:
                p = {"explanation": raw_str}
        elif raw_str.startswith("#"):
            return raw_str
        else:
            p = {"explanation": raw_str}
    elif isinstance(plan, dict):
        p = dict(plan)
    else:
        p = {"explanation": str(plan)}

    summary = p.get("summary") or p.get("intent") or title or "Engineering Implementation Plan"
    version = p.get("plan_version") or p.get("version_id") or "v1"
    phash = p.get("plan_hash") or plan_hash or ""
    short_hash = phash[:8] if phash else "unfrozen"
    complexity = str(p.get("estimated_complexity", "medium")).upper()
    provenance = p.get("provenance", "evidence_grounded_synthesis")
    explanation = p.get("explanation") or p.get("scope") or ""

    sec_num = 1
    lines: list[str] = [
        f"# 📋 Implementation Plan: {summary}",
        "",
        f"> **Plan Version:** `{version}` | **Frozen Hash:** `{short_hash}` | **Estimated Complexity:** `{complexity}` | **Provenance:** `{provenance}`",
        "",
        f"## {sec_num}. Summary & Intended Behavior",
        explanation if explanation else f"Evidence-grounded engineering plan for issue: {summary}.",
        "",
    ]
    sec_num += 1

    # Root Cause Analysis
    rc = p.get("root_cause")
    if rc and isinstance(rc, dict):
        lines.append(f"## {sec_num}. Root Cause Analysis")
        sec_num += 1
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

    # Grounded Code Evidence
    evidence = p.get("evidence_items", [])
    if evidence:
        lines.append(f"## {sec_num}. Grounded Code Evidence")
        sec_num += 1
        for ev in evidence:
            if isinstance(ev, dict):
                fpath = ev.get("file_path", "")
                sline = ev.get("start_line", 1)
                eline = ev.get("end_line", 1)
                sym = ev.get("symbol")
                sym_str = f" (`{sym}`)" if sym else ""
                obs = ev.get("observation", "")
                lines.append(f"- `{fpath}:{sline}-{eline}`{sym_str}: {obs}")
            else:
                lines.append(f"- {ev}")
        lines.append("")

    # Proposed Changes by File
    file_changes = p.get("file_changes", [])
    if file_changes:
        lines.append(f"## {sec_num}. Proposed Changes by File")
        sec_num += 1
        for fc in file_changes:
            if isinstance(fc, dict):
                fpath = fc.get("file_path", "unknown")
                lines.append(f"### `{fpath}`")
                if fc.get("module_or_function"):
                    lines.append(f"- **Target Symbol:** `{fc.get('module_or_function')}`")
                if fc.get("change_description"):
                    lines.append(f"- **Change Description:** {fc.get('change_description')}")
            else:
                lines.append(f"- {fc}")
        lines.append("")

    # Implementation Steps
    steps = p.get("steps", [])
    if steps:
        lines.append(f"## {sec_num}. Implementation Steps")
        sec_num += 1
        for idx, s in enumerate(steps, 1):
            if isinstance(s, dict):
                num = s.get("step_number", idx)
                action = str(s.get("action", "modify")).upper()
                target = s.get("target_file") or (s.get("files")[0] if s.get("files") else "repository")
                desc = s.get("description", "")
                lines.append(f"{num}. **[{action}]** `{target}`: {desc}")
            else:
                lines.append(f"{idx}. {s}")
        lines.append("")

    # Acceptance Criteria / Requirements
    ac = p.get("acceptance_criteria") or []
    reqs = p.get("requirements") or []
    if ac or reqs:
        lines.append(f"## {sec_num}. Acceptance Criteria")
        sec_num += 1
        for criterion in ac:
            lines.append(f"- [ ] {criterion}")
        for r in reqs:
            if isinstance(r, dict):
                r_desc = r.get("description") or r.get("acceptance_criterion", "")
            else:
                r_desc = getattr(r, "description", str(r))
            lines.append(f"- [ ] {r_desc}")
        lines.append("")

    # Test Strategy
    ts = p.get("test_strategy")
    exp_tests = p.get("expected_tests") or []
    if ts or exp_tests:
        lines.append(f"## {sec_num}. Test Strategy")
        sec_num += 1
        if isinstance(ts, dict):
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
        for t in exp_tests:
            lines.append(f"- Regression test: `{t}`")
        lines.append("")

    # Dependencies & Interfaces
    deps = p.get("dependencies_and_interfaces", [])
    if deps:
        lines.append(f"## {sec_num}. Dependencies & Interfaces")
        sec_num += 1
        for d in deps:
            lines.append(f"- {d}")
        lines.append("")

    # Security Considerations
    sec = p.get("security_considerations", [])
    if sec:
        lines.append(f"## {sec_num}. Security & Guardrail Considerations")
        sec_num += 1
        for s in sec:
            lines.append(f"- {s}")
        lines.append("")

    # Risks & Assumptions
    risks = p.get("risks_and_assumptions", [])
    if risks:
        lines.append(f"## {sec_num}. Risks & Assumptions")
        sec_num += 1
        for r in risks:
            lines.append(f"- {r}")
        lines.append("")

    # Verification Commands
    cmds = p.get("suggested_verification_commands", [])
    if cmds:
        lines.append(f"## {sec_num}. Suggested Verification Commands")
        sec_num += 1
        lines.append("```bash")
        for c in cmds:
            lines.append(c)
        lines.append("```")
        lines.append("")

    return "\n".join(lines).strip()


@cl.on_chat_start
async def on_chat_start():
    """Display welcome screen and instructions when a new session begins."""
    await cl.Message(
        content=(
            "## 🤖 Welcome to Mini-Devin\n"
            "**Autonomous GitHub Issue-to-Pull-Request Multi-Agent System**\n\n"
            "### How to run an issue:\n"
            "- **GitHub Issue URL:** `https://github.com/owner/repo/issues/42`\n"
            "- **Manual format:** `owner/repo: Fix null pointer in auth service`\n"
            "- **Free text:** Just type any issue description (runs against demo repo)\n\n"
            "Mini-Devin will triage the issue, retrieve relevant context, formulate a "
            "concrete implementation plan, and **pause for your approval** before any code is modified."
        )
    ).send()


@cl.on_message
async def on_message(message: cl.Message):
    """
    Process incoming issue submissions, invoke the LangGraph workflow,
    handle human approval/rejection, and render results.
    """
    user_input = message.content.strip()
    if not user_input:
        await cl.Message(content="⚠️ Please provide a GitHub issue URL or issue title.").send()
        return

    # Parse and validate issue details via genuine MCP intake service
    try:
        async with cl.Step(name="Issue Intake & Validation", type="tool") as intake_step:
            intake_step.output = "Validating input and fetching issue details via GitHub MCP..."
            intake_res = await process_issue_intake(user_input)
            intake_step.output = (
                f"Successfully ingested issue #{intake_res.issue_number or 'free-text'} "
                f"for `{intake_res.repo}`: {intake_res.issue_title}"
            )

        repo = intake_res.repo
        title = intake_res.issue_title
        body = intake_res.issue_body
        issue_url = intake_res.issue_url
        issue_number = intake_res.issue_number

        run_id = f"run_{uuid.uuid4().hex[:10]}"
        thread_id = f"thread_{uuid.uuid4().hex[:10]}"

        initial_state = create_initial_state(
            repo=repo,
            issue_title=title,
            issue_body=body,
            issue_url=issue_url,
            issue_number=issue_number,
            repo_ref=intake_res.repo_ref,
            commit_sha=intake_res.commit_sha,
            snapshot_path=intake_res.snapshot_path,
            issue_metadata=intake_res.issue_metadata,
            run_id=run_id,
            thread_id=thread_id,
        )
    except Exception as exc:
        logger.warning("Issue intake halted before triage: %s", exc)
        await cl.Message(content=f"❌ **Intake Error:** {exc}").send()
        return

    config = {"configurable": {"thread_id": thread_id}}
    graph = create_graph(checkpointer=get_checkpointer())

    # Notification of start
    await cl.Message(
        content=(
            f"🚀 **Started Workflow Execution**\n\n"
            f"- **Repository:** `{repo}`\n"
            f"- **Issue Title:** {title}\n"
            f"- **Run ID:** `{run_id}`\n"
            f"- **Thread ID:** `{thread_id}`"
        )
    ).send()

    # Phase 1: Invoke workflow up to the Human Approval Interrupt
    try:
        async with cl.Step(name="Triage and Retrieval", type="run") as prep_step:
            prep_step.output = "Executing Triage and Retrieval agents..."
            # ainvoke executes until it hits interrupt() inside human_approval_node
            await graph.ainvoke(initial_state, config=config)

        # Inspect paused state from checkpointer
        current_state = await cl.make_async(graph.get_state)(config)
        state_values = current_state.values
        triage = state_values.get("triage") or {}
        retrieved = state_values.get("retrieved_context") or {}
        workflow_status = state_values.get("status", "")

        # Extract authentic plan content (inspecting state values, then interrupt payload fallback)
        plan_raw = state_values.get("plan")
        if not plan_raw or (isinstance(plan_raw, str) and not plan_raw.strip().startswith("{")):
            tasks = getattr(current_state, "tasks", [])
            for t in tasks:
                for intr in getattr(t, "interrupts", []):
                    intr_val = getattr(intr, "value", None)
                    if isinstance(intr_val, dict) and "plan" in intr_val:
                        candidate_plan = intr_val["plan"]
                        if candidate_plan and not isinstance(candidate_plan, str):
                            plan_raw = candidate_plan
                            break

        # Normalize plan dictionary
        plan_dict: dict[str, Any] = {}
        if hasattr(plan_raw, "model_dump"):
            plan_dict = plan_raw.model_dump(mode="json")
        elif isinstance(plan_raw, dict):
            plan_dict = dict(plan_raw)
        elif isinstance(plan_raw, str) and plan_raw.strip().startswith("{"):
            try:
                plan_dict = json.loads(plan_raw)
            except Exception:
                plan_dict = {"explanation": plan_raw}

        plan_version = (
            plan_dict.get("plan_version")
            or state_values.get("plan_version")
            or "v1"
        )
        plan_hash = (
            plan_dict.get("plan_hash")
            or state_values.get("plan_hash")
            or ""
        )
        short_hash = plan_hash[:8] if plan_hash else "unfrozen"

        # Handle Out-of-Scope, safe-stop termination, or workflow failure
        if workflow_status == "failed":
            err_msg = state_values.get("error") or "An error occurred during workflow execution."
            await cl.Message(
                content=(
                    f"🛑 **Workflow Safely Halted: Execution Failed**\n\n"
                    f"- **Status:** `FAILED`\n"
                    f"- **Error:** {err_msg}\n\n"
                    f"Execution halted safely. No plan was created and no code modifications were attempted."
                )
            ).send()
            return

        if workflow_status == "out_of_scope" or not triage.get("is_supported", True):
            reason = triage.get("reason", "Out-of-scope issue.")
            warnings_list = triage.get("warnings", [])
            warnings_str = f"\n- **Warnings:** {', '.join(warnings_list)}" if warnings_list else ""
            await cl.Message(
                content=(
                    f"🛑 **Workflow Safely Halted by Triage Agent**\n\n"
                    f"- **Classification:** `{triage.get('classification', 'out_of_scope').upper()}`\n"
                    f"- **Eligibility to Proceed:** `False (Safe Terminal)`\n"
                    f"- **Explanation:** {reason}\n"
                    f"- **Confidence:** {triage.get('confidence', 0.0):.0%}"
                    f"{warnings_str}\n\n"
                    f"No code or repository modifications were attempted."
                )
            ).send()
            return

        # Display Triage Report & Downstream Status
        triage_cls = triage.get("classification", "unknown")
        triage_reason = triage.get("reason", "")
        triage_warnings = triage.get("warnings", [])
        warnings_md = f"\n- **Warnings:** {', '.join(triage_warnings)}" if triage_warnings else ""
        files_found = retrieved.get("files", [])
        await cl.Message(
            content=(
                f"### 📋 Triage Agent Report\n\n"
                f"- **Classification:** `{triage_cls.upper()}`\n"
                f"- **Eligibility to Proceed:** `True (Proceeding to Retrieval)`\n"
                f"- **Explanation:** {triage_reason}\n"
                f"- **Confidence:** {triage.get('confidence', 1.0):.0%}"
                f"{warnings_md}\n\n"
                f"**Downstream Retrieval Status:** `{retrieved.get('retrieval_status', 'success')}` via `{retrieved.get('retrieval_method', 'none')}` (`{len(files_found)} candidate files`)."
            )
        ).send()

        # Build readable document preview — rendered as markdown in a Message
        plan_markdown = build_plan_document(
            plan=plan_dict if plan_dict else plan_raw,
            title=title,
            plan_hash=plan_hash,
        )

        # ── Right-side panel: plain-text sidebar for quick scrolling ────────────
        # NOTE: cl.Text with language="markdown" renders as a code editor
        # (syntax-highlighted source), NOT as formatted HTML. Omitting `language`
        # gives a plain-text viewer. Fully rendered markdown is only possible
        # via cl.Message content, which Chainlit always processes as markdown.
        try:
            plan_element = cl.Text(
                name="implementation_plan",
                content=plan_markdown,
                display="side",
                # language intentionally omitted — avoids code-editor rendering
            )
            await cl.ElementSidebar.set_title("📋 Implementation Plan")
            await cl.ElementSidebar.set_elements([plan_element])
        except Exception as elem_err:
            logger.warning("Side panel element preview setup skipped: %s", elem_err)

        # ── Main chat: full rendered markdown preview ────────────────────────────
        # cl.Message content is always rendered as formatted markdown by Chainlit,
        # giving proper headings, bullet points, checklists, and code blocks.
        await cl.Message(
            author="📋 Implementation Plan",
            content=plan_markdown,
        ).send()

    except Exception as exc:
        logger.exception("Error executing initial workflow phase")
        await cl.Message(content=f"❌ **Error during planning phase:** {exc}").send()
        return

    # Phase 2: Human Approval Interrupt & User Choice
    decision = "rejected"
    user_feedback = ""
    frozen_hash = plan_hash
    frozen_version = plan_version

    try:
        actions = [
            cl.Action(
                name="approve",
                payload={"decision": "approved", "plan_hash": frozen_hash, "plan_version": frozen_version},
                label=f"✅ Approve Plan ({frozen_hash[:8]})",
            ),
            cl.Action(
                name="reject",
                payload={"decision": "rejected", "plan_hash": frozen_hash, "plan_version": frozen_version},
                label="❌ Reject Plan",
            ),
        ]

        approval_prompt = (
            f"### 🛡️ Human Approval Required (Plan `{frozen_version}:{frozen_hash[:8]}`)\n"
            "Review the implementation plan above or in the side panel. "
            "Please confirm whether to approve code modification or reject the plan."
        )

        res = await cl.AskActionMessage(
            content=approval_prompt,
            actions=actions,
            timeout=300,
        ).send()

        if res and res.get("name") == "approve":
            decision = "approved"
            user_feedback = f"Approved by operator via Chainlit console (Hash: {frozen_hash[:8]})."
        else:
            decision = "rejected"
            user_feedback = f"Rejected by operator via Chainlit console (Hash: {frozen_hash[:8]})."

    except Exception as exc:
        logger.warning("Action prompt timed out or failed: %s; defaulting to rejection", exc)
        decision = "rejected"
        user_feedback = "Action prompt timed out; safely defaulting to rejection."

    # Phase 3: Resume the graph from saved checkpoint
    try:
        async with cl.Step(name="Workflow Resume", type="run") as resume_step:
            resume_step.output = f"Resuming execution with decision: {decision.upper()} (Plan: {frozen_hash[:8]})..."
            resume_cmd = Command(
                resume={
                    "decision": decision,
                    "feedback": user_feedback,
                    "plan_hash": frozen_hash,
                    "plan_version": frozen_version,
                }
            )
            final_result = await graph.ainvoke(resume_cmd, config=config)

        final_status = final_result.get("status", "unknown")
        events = final_result.get("events", [])

        error_detail = final_result.get("error")

        if decision == "approved":
            # 1. Test Runner verification report
            test_res = final_result.get("test_results") or {}
            if test_res:
                t_passed = (
                    test_res.get("passed", False)
                    if isinstance(test_res, dict)
                    else getattr(test_res, "passed", False)
                )
                t_total = (
                    test_res.get("total_tests", 0)
                    if isinstance(test_res, dict)
                    else getattr(test_res, "total_tests", 0)
                )
                t_passed_count = (
                    test_res.get("passed_tests", 0)
                    if isinstance(test_res, dict)
                    else getattr(test_res, "passed_tests", 0)
                )
                t_details = (
                    test_res.get("details", "")
                    if isinstance(test_res, dict)
                    else getattr(test_res, "details", "")
                )
                status_badge = "PASSED ✅" if t_passed else "FAILED ❌"
                await cl.Message(
                    content=(
                        f"### 🧪 Test Runner Sandbox Execution Report\n\n"
                        f"- **Overall Status:** `{status_badge}`\n"
                        f"- **Tests Passed:** `{t_passed_count}/{t_total}`\n"
                        f"```text\n{t_details.strip()}\n```"
                    )
                ).send()

            # 2. Reviewer Report (preview on right side panel and attachment)
            review_file = final_result.get("review_report_path")
            review_md = final_result.get("review_report_markdown")
            if not review_md and review_file and os.path.exists(review_file):
                try:
                    with open(review_file, "r", encoding="utf-8") as rf:
                        review_md = rf.read()
                except Exception:
                    pass

            if not review_md:
                import glob
                run_id_clean = (final_result.get("run_id") or run_id or "")[:10]
                candidates = [
                    os.path.join(os.getcwd(), "scratch", "reviews", f"review_{run_id_clean}.md"),
                    os.path.join(os.getcwd(), "scratch", "reviews", f"review_{run_id_clean[:6]}.md"),
                ]
                found_files = glob.glob(os.path.join(os.getcwd(), "scratch", "reviews", "*.md"))
                if found_files:
                    candidates.extend(sorted(found_files, key=os.path.getmtime, reverse=True))
                for cp in candidates:
                    if os.path.exists(cp):
                        try:
                            with open(cp, "r", encoding="utf-8") as rf:
                                review_md = rf.read()
                            review_file = cp
                            break
                        except Exception:
                            pass

            if review_md:
                try:
                    review_element = cl.Text(
                        name="review_report",
                        content=review_md,
                        display="side",
                    )
                    await cl.ElementSidebar.set_title("📝 Review & Verification Report")
                    await cl.ElementSidebar.set_elements([review_element])
                except Exception as side_err:
                    logger.warning("Side panel review preview update skipped: %s", side_err)

                review_elements = []
                if review_file and os.path.exists(review_file):
                    review_elements.append(cl.File(name=os.path.basename(review_file), path=review_file, display="inline"))

                await cl.Message(
                    author="📝 Reviewer Agent",
                    content=review_md,
                    elements=review_elements,
                ).send()

            # 3. Pull Request Submission Card
            pr_url = final_result.get("pull_request_url")
            if final_status in ("pr_opened", "submitting_pr"):
                msg_title = "🎉 **Pull Request Created / Prepared Successfully**"
                if pr_url and str(pr_url).startswith("http"):
                    handoff_text = f"### 🚀 [Click here to View Pull Request on GitHub]({pr_url})\n\n- **PR URL:** [{pr_url}]({pr_url})"
                else:
                    handoff_text = f"- **PR Link / Artifacts:** `{pr_url or 'ready'}`"
            elif final_status == "failed":
                msg_title = "⚠️ **Plan Approved, but Downstream Execution Halted**"
                handoff_text = f"- **Halt Reason:** {error_detail or 'Downstream sandbox or review verification incomplete.'}"
            else:
                msg_title = "✅ **Plan Approved & Workflow Advanced**"
                handoff_text = "- **Stage Result:** Checkpoint saved; ready for subsequent verification."

            await cl.Message(
                content=(
                    f"{msg_title}\n\n"
                    f"- **Workflow Status:** `{final_status}`\n"
                    f"- **Checkpoint Thread:** `{thread_id}`\n"
                    f"{handoff_text}\n"
                    f"- **Total Events Logged:** {len(events)}"
                )
            ).send()
        else:
            await cl.Message(
                content=(
                    f"🛑 **Plan Rejected & Workflow Terminated Safely**\n\n"
                    f"- **Workflow Status:** `{final_status}`\n"
                    f"- **Checkpoint Thread:** `{thread_id}`\n"
                    f"- **Safety Guarantee:** Zero code changes or pull requests attempted.\n"
                    f"- **Total Events Logged:** {len(events)}"
                )
            ).send()

        # Render workflow event log summary
        event_summary_lines = []
        for ev in events:
            ev_agent = ev.get("agent_name", "unknown")
            ev_status = ev.get("status", "")
            ev_msg = ev.get("message", "")
            event_summary_lines.append(f"- **[{ev_agent}]** ({ev_status}): {ev_msg}")

        await cl.Message(
            content="### 📜 Workflow Event Log\n" + "\n".join(event_summary_lines)
        ).send()

    except Exception as exc:
        logger.exception("Error resuming workflow execution")
        await cl.Message(content=f"❌ **Error resuming workflow:** {exc}").send()
