"""
Mini-Devin — Chainlit Live Agent Console.

Root-level entrypoint for launching the interactive multi-agent console:
    chainlit run chainlit_app.py --port 8001
"""

from __future__ import annotations

import logging
import re
import sys
import uuid
from pathlib import Path
from typing import Any, Optional

# Ensure the backend directory is first in sys.path
root_dir = Path(__file__).resolve().parent
backend_dir = root_dir / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

import chainlit as cl
from langgraph.types import Command

from app.agents.checkpointer import get_checkpointer
from app.agents.graph import create_graph
from app.agents.schemas import create_initial_state

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
        title = f"Issue #{issue_number} in {repo}"
        body = f"Imported from {raw}"
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


@cl.on_chat_start
async def on_chat_start():
    """Display welcome screen and instructions when a new session begins."""
    await cl.Message(
        content=(
            "## 🤖 Welcome to Mini-Devin\n"
            "**Autonomous GitHub Issue-to-Pull-Request Multi-Agent System**\n\n"
            "### How to submit an issue:\n"
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

    # Parse and validate issue details
    try:
        repo, title, body, issue_url, issue_number = parse_issue_input(user_input)
        run_id = f"run_{uuid.uuid4().hex[:10]}"
        thread_id = f"thread_{uuid.uuid4().hex[:10]}"

        initial_state = create_initial_state(
            repo=repo,
            issue_title=title,
            issue_body=body,
            issue_url=issue_url,
            issue_number=issue_number,
            run_id=run_id,
            thread_id=thread_id,
        )
    except Exception as exc:
        logger.exception("Input validation error")
        await cl.Message(content=f"❌ **Validation Error:** {exc}").send()
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
        async with cl.Step(name="Triage & Retrieval", type="run") as prep_step:
            prep_step.output = "Executing Triage and Retrieval agents..."
            # ainvoke executes until it hits interrupt() inside human_approval_node
            await graph.ainvoke(initial_state, config=config)

        # Inspect paused state from checkpointer
        current_state = await cl.make_async(graph.get_state)(config)
        state_values = current_state.values
        triage = state_values.get("triage") or {}
        retrieved = state_values.get("retrieved_context") or {}
        plan = state_values.get("plan") or {}
        workflow_status = state_values.get("status", "")

        # Handle Out-of-Scope or safe-stop termination
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
                f"**Downstream Retrieval Status:** Issue passed triage; retrieval running in labeled mock mode (`{len(files_found)} candidate files`)."
            )
        ).send()

        # Display the Proposed Implementation Plan
        steps_markdown = ""
        for s in plan.get("steps", []):
            steps_markdown += f"{s.get('step_number')}. **[{s.get('action').upper()}]** `{s.get('target_file')}`: {s.get('description')}\n"

        plan_display = (
            f"### 📝 Proposed Implementation Plan\n\n"
            f"**Summary:** {plan.get('summary', title)}\n\n"
            f"**Analysis:** {plan.get('explanation', '')}\n\n"
            f"**Estimated Complexity:** `{plan.get('estimated_complexity', 'medium').upper()}`\n\n"
            f"**Planned Steps:**\n{steps_markdown}\n"
            f"**Affected Files:** `{', '.join(plan.get('affected_files', []))}`"
        )
        await cl.Message(content=plan_display).send()

    except Exception as exc:
        logger.exception("Error executing initial workflow phase")
        await cl.Message(content=f"❌ **Error during planning phase:** {exc}").send()
        return

    # Phase 2: Human Approval Interrupt & User Choice
    decision = "rejected"
    user_feedback = ""
    try:
        actions = [
            cl.Action(name="approve", payload={"decision": "approved"}, label="✅ Approve Plan"),
            cl.Action(name="reject", payload={"decision": "rejected"}, label="❌ Reject Plan"),
        ]

        approval_prompt = (
            "### 🛡️ Human Approval Required\n"
            "Review the implementation plan above. "
            "Please confirm whether to approve code modification or reject the plan."
        )

        res = await cl.AskActionMessage(
            content=approval_prompt,
            actions=actions,
            timeout=300,
        ).send()

        if res and res.get("name") == "approve":
            decision = "approved"
            user_feedback = "Approved by operator via Chainlit console."
        else:
            decision = "rejected"
            user_feedback = "Rejected by operator via Chainlit console."

    except Exception as exc:
        logger.warning("Action prompt timed out or failed: %s; defaulting to rejection", exc)
        decision = "rejected"
        user_feedback = "Action prompt timed out; safely defaulting to rejection."

    # Phase 3: Resume the graph from saved checkpoint
    try:
        async with cl.Step(name="Workflow Resume", type="run") as resume_step:
            resume_step.output = f"Resuming execution with decision: {decision.upper()}..."
            resume_cmd = Command(
                resume={
                    "decision": decision,
                    "feedback": user_feedback,
                }
            )
            final_result = await graph.ainvoke(resume_cmd, config=config)

        final_status = final_result.get("status", "unknown")
        events = final_result.get("events", [])

        if decision == "approved":
            await cl.Message(
                content=(
                    f"🎉 **Plan Approved & Workflow Completed**\n\n"
                    f"- **Status:** `{final_status}`\n"
                    f"- **Checkpoint Thread:** `{thread_id}`\n"
                    f"- **Handoff:** Ready for Coder Agent\n"
                    f"- **Total Events Logged:** {len(events)}"
                )
            ).send()
        else:
            await cl.Message(
                content=(
                    f"🛑 **Plan Rejected & Workflow Terminated Safely**\n\n"
                    f"- **Status:** `{final_status}`\n"
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
