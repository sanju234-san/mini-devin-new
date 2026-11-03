"""Agent gateway and metrics provider protocols and default stubs.

This module defines the boundaries between the REST API layer (owned by
Tamanna) and the multi-agent orchestration layer (owned by Sanjeevni).

By depending on these protocols rather than importing `app.agents` directly:
1. The REST API runs independently without waiting for agent implementation.
2. Unit and integration tests can easily substitute mock gateways.
3. Merge conflicts between backend routes and agent logic are prevented.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
import tempfile
from typing import Protocol, runtime_checkable
from uuid import UUID

from app.models.metrics import MetricsOut
from app.models.plan import PlanDecision
from app.models.run import IssueIn, RunStatus

logger = logging.getLogger(__name__)


@runtime_checkable
class AgentGateway(Protocol):
    """Protocol for initiating autonomous agent workflow runs."""

    async def start_run(self, run_id: UUID, issue: IssueIn) -> None:
        """Start the multi-agent graph execution for a given issue."""
        ...


@runtime_checkable
class MetricsProvider(Protocol):
    """Protocol for fetching evaluation and benchmark statistics."""

    async def get_metrics(self) -> MetricsOut:
        """Retrieve aggregated evaluation metrics."""
        ...


class NoOpAgentGateway:
    """Default no-op agent gateway stub.

    Logs that no agent layer is currently wired and leaves the run in
    its initial 'queued' status.
    """

    async def start_run(self, run_id: UUID, issue: IssueIn) -> None:
        logger.info(
            "NoOpAgentGateway: No agent layer wired. Run %s remains queued.",
            run_id,
        )


class LangGraphAgentGateway:
    """Active Agent Gateway that executes the Mini-Devin LangGraph multi-agent workflow."""

    def __init__(self, checkpointer=None, run_store: object | None = None):
        self._checkpointer = checkpointer
        self._run_store = run_store

    async def start_run(self, run_id: UUID, issue: IssueIn) -> None:
        import json
        from app.agents.checkpointer import get_checkpointer
        from app.agents.graph import create_graph
        from app.agents.schemas import create_initial_state, format_plan_as_markdown
        from app.models.artifact import ArtifactType

        run_id_str = str(run_id)
        thread_id = run_id_str
        checkpointer = self._checkpointer or get_checkpointer()

        if isinstance(issue.repo, str) and "/" in issue.repo:
            repo = issue.repo.strip()
        else:
            owner = getattr(issue.repo, "owner", "unknown")
            name = getattr(issue.repo, "name", "repo")
            repo = f"{owner}/{name}"

        if self._run_store is not None and hasattr(self._run_store, "update_run"):
            await self._run_store.update_run(
                run_id,
                status=RunStatus.running,
                current_step="intake",
            )

        try:
            from app.api.ws import broadcaster
            await broadcaster.publish_event(
                run_id_str,
                {
                    "agent": "triage",
                    "type": "step_started",
                    "message": f"Ingested {repo}#{issue.issue_number}: {issue.title}. Preparing repository snapshot...",
                    "level": "info",
                },
            )
        except Exception:
            pass

        snapshot_path = None
        commit_sha = None
        try:
            from app.integrations.repo_snapshot import RepositorySnapshotService
            owner_slug, repo_slug = repo.split("/", 1)
            default_ref = "main"
            try:
                from app.integrations.github_client import GitRef, get_github_client
                fetched_ref = await asyncio.to_thread(
                    get_github_client().fetch_repo,
                    GitRef(owner=owner_slug, repo=repo_slug),
                )
                default_ref = fetched_ref.rsplit("@", 1)[-1]
            except Exception:
                pass
            snapshots_root = Path(tempfile.gettempdir()) / "mini_devin_snapshots"
            snapshot_dir = await RepositorySnapshotService(snapshots_root=snapshots_root).create_snapshot(
                owner=owner_slug,
                repo=repo_slug,
                ref=default_ref,
            )
            snapshot_path = str(snapshot_dir)
            meta_file = snapshot_dir / "snapshot_metadata.json"
            if meta_file.is_file():
                meta = json.loads(meta_file.read_text(encoding="utf-8"))
                commit_sha = meta.get("commit_sha")
        except Exception as intake_exc:
            logger.warning("LangGraphAgentGateway: Snapshot intake warning for %s: %s", repo, intake_exc)

        initial_state = create_initial_state(
            repo=repo,
            issue_number=issue.issue_number,
            issue_title=issue.title,
            issue_body=issue.body,
            snapshot_path=snapshot_path,
            workspace_path=snapshot_path,
            commit_sha=commit_sha,
            run_id=run_id_str,
            thread_id=thread_id,
        )

        graph = create_graph(checkpointer=checkpointer)
        config = {"configurable": {"thread_id": thread_id}}

        logger.info("LangGraphAgentGateway: Launching workflow for run %s (%s)", run_id_str, repo)
        loop = asyncio.get_running_loop()

        def _stream_graph() -> None:
            for update in graph.stream(initial_state, config=config, stream_mode="updates"):
                if isinstance(update, dict):
                    for node_name, node_out in update.items():
                        if node_name == "planner":
                            # Wait to broadcast planner event until artifact & status are committed below
                            continue
                        if isinstance(node_out, dict) and node_out.get("events"):
                            try:
                                from app.api.ws import broadcaster
                                asyncio.run_coroutine_threadsafe(
                                    broadcaster.publish_events(run_id_str, node_out["events"]),
                                    loop,
                                )
                            except Exception:
                                pass

        await asyncio.to_thread(_stream_graph)

        saved_state = graph.get_state(config)
        values = saved_state.values if saved_state and hasattr(saved_state, "values") else {}
        wf_status = values.get("status", "")
        plan_data = values.get("plan")

        if self._run_store is not None:
            if plan_data and hasattr(self._run_store, "add_artifact"):
                plan_dict = plan_data.model_dump(mode="json") if hasattr(plan_data, "model_dump") else plan_data
                plan_json = json.dumps(plan_dict, indent=2) if isinstance(plan_dict, dict) else str(plan_dict)
                await self._run_store.add_artifact(
                    run_id=run_id,
                    artifact_type=ArtifactType.implementation_plan,
                    name="implementation_plan.json",
                    content=plan_json,
                    content_type="application/json",
                    agent="planner",
                )

            if hasattr(self._run_store, "update_run"):
                if plan_data or wf_status == "awaiting_approval" or (saved_state and saved_state.next):
                    await self._run_store.update_run(
                        run_id,
                        status=RunStatus.awaiting_plan_approval,
                        current_step="awaiting_plan_approval",
                    )
                elif wf_status in ("out_of_scope", "unsupported"):
                    await self._run_store.update_run(
                        run_id,
                        status=RunStatus.escalated,
                        current_step="out_of_scope",
                        error=values.get("error") or "Issue classified as out of scope.",
                    )
                elif wf_status == "failed":
                    await self._run_store.update_run(
                        run_id,
                        status=RunStatus.failed,
                        current_step=values.get("current_agent") or "failed",
                        error=values.get("error") or "Workflow failed during planning.",
                    )

        try:
            from app.api.ws import broadcaster
            await broadcaster.publish_events(run_id_str, values.get("events") or [])
        except Exception:
            pass

        logger.info("LangGraphAgentGateway: Run %s execution paused at approval interrupt or completed", run_id_str)


class EmptyMetricsProvider:
    """Default empty metrics provider stub.

    Returns an unavailable MetricsOut instance with all metric values unset.
    """

    async def get_metrics(self) -> MetricsOut:
        return MetricsOut(
            available=False,
            fix_accuracy=None,
            test_pass_rate=None,
            avg_self_correction_iterations=None,
            swe_bench_lite=None,
            updated_at=None,
        )


async def run_agent_background_task(
    run_id: UUID,
    issue: IssueIn,
    gateway: AgentGateway,
    store: object,
) -> None:
    """Safely execute the agent workflow in the background.

    WHY THIS WRAPPER IS NEEDED:
    Background tasks execute outside the HTTP request/response cycle. If an unhandled
    exception bubbles up from the agent layer, it would crash or corrupt worker task loops.
    This wrapper catches every Exception, logs only the run_id (never secrets or issue text),
    and updates the run status in the store with a clean generic error message so the
    server process remains stable and the client can see the run failed.
    """
    try:
        await gateway.start_run(run_id, issue)
    except Exception:
        # Log only the run_id without leaking issue text or stack trace to users
        logger.error("Agent run %s failed to start", run_id)
        # store is RunStore; call update_run safely
        if hasattr(store, "update_run"):
            await store.update_run(
                run_id,
                status=RunStatus.failed,
                error="Failed to start agent run",
            )


# ── Plan Resume Interface ──────────────────────────────────────────────────────


@runtime_checkable
class PlanResumer(Protocol):
    """Protocol for resuming a paused agent run after a human plan decision.

    When the Planner pauses the graph for human review, Sanjeevni's agent
    layer provides a concrete implementation of this protocol that calls
    the LangGraph compiled graph with the resume Command.

    The REST API layer depends on this Protocol (not on any concrete agent
    class) so the API can run without the agent layer and tests can inject
    a fake resumer via dependency_overrides.
    """

    async def resume(self, run_id: UUID, decision: PlanDecision) -> None:
        """Resume a graph that is paused at the human_approval interrupt.

        Args:
            run_id:   The UUID of the run to resume. The agent layer converts
                      this to the LangGraph thread_id (thread_id == str(run_id)).
            decision: The human decision (approve / edit / reject).
        """
        ...


class NoOpPlanResumer:
    """Default no-op plan resumer stub.

    Logs that no resume implementation is wired and leaves the run in
    whatever status claim_plan_decision set. Used until Sanjeevni's agent
    layer wires a real resumer via application.state.plan_resumer.
    """

    async def resume(self, run_id: UUID, decision: PlanDecision) -> None:
        # Log only the run_id and decision name; never log plan content or reason
        logger.info(
            "NoOpPlanResumer: No agent layer wired. Run %s decision '%s' not forwarded.",
            run_id,
            decision.value,
        )


class LangGraphPlanResumer:
    """Concrete PlanResumer that resumes the paused LangGraph workflow on human plan decision."""

    def __init__(self, checkpointer=None, run_store: object | None = None):
        self._checkpointer = checkpointer
        self._run_store = run_store

    async def resume(self, run_id: UUID, decision: PlanDecision) -> None:
        from langgraph.types import Command
        from app.agents.checkpointer import get_checkpointer
        from app.agents.graph import create_graph
        from app.models.artifact import ArtifactType

        thread_id = str(run_id)
        checkpointer = self._checkpointer or get_checkpointer()
        graph = create_graph(checkpointer=checkpointer)
        config = {"configurable": {"thread_id": thread_id}}

        mapped_decision = "rejected" if decision == PlanDecision.reject else "approved"
        loop = asyncio.get_running_loop()

        def _stream_resume() -> None:
            for update in graph.stream(
                Command(resume={"decision": mapped_decision}),
                config=config,
                stream_mode="updates",
            ):
                if isinstance(update, dict):
                    for node_name, node_out in update.items():
                        if isinstance(node_out, dict) and node_out.get("events"):
                            try:
                                from app.api.ws import broadcaster
                                asyncio.run_coroutine_threadsafe(
                                    broadcaster.publish_events(thread_id, node_out["events"]),
                                    loop,
                                )
                            except Exception:
                                pass

        await asyncio.to_thread(_stream_resume)

        saved = graph.get_state(config)
        values = saved.values if saved and hasattr(saved, "values") else {}

        try:
            from app.api.ws import broadcaster
            await broadcaster.publish_events(thread_id, values.get("events") or [])
        except Exception:
            pass

        if self._run_store is not None:
            if hasattr(self._run_store, "add_artifact"):
                code_changes = values.get("code_changes") or []
                if code_changes:
                    diff_parts = [
                        c.get("diff_text") or c.get("diff") or ""
                        for c in code_changes
                        if isinstance(c, dict)
                    ]
                    combined_diff = "\n".join(p for p in diff_parts if p)
                    if combined_diff:
                        await self._run_store.add_artifact(
                            run_id=run_id,
                            artifact_type=ArtifactType.code_diff,
                            name="patch.diff",
                            content=combined_diff,
                            content_type="text/plain",
                            agent="coder",
                        )

                test_results = values.get("test_results")
                if isinstance(test_results, dict) and test_results.get("details"):
                    await self._run_store.add_artifact(
                        run_id=run_id,
                        artifact_type=ArtifactType.test_log,
                        name="test_results.log",
                        content=str(test_results.get("details", "")),
                        content_type="text/plain",
                        agent="test_runner",
                    )

                review_md = values.get("review_report_markdown")
                if review_md:
                    await self._run_store.add_artifact(
                        run_id=run_id,
                        artifact_type=ArtifactType.walkthrough,
                        name="code_review_report.md",
                        content=str(review_md),
                        content_type="text/markdown",
                        agent="reviewer",
                    )

                pr_result = values.get("pr_result")
                if isinstance(pr_result, dict) and (pr_result.get("pr_url") or pr_result.get("body")):
                    pr_md = f"# Pull Request: {pr_result.get('title', '')}\n\n"
                    if pr_result.get("pr_url"):
                        pr_md += f"**URL**: {pr_result.get('pr_url')}\n"
                    if pr_result.get("branch_name"):
                        pr_md += f"**Branch**: `{pr_result.get('branch_name')}`\n\n"
                    pr_md += str(pr_result.get("body", ""))
                    await self._run_store.add_artifact(
                        run_id=run_id,
                        artifact_type=ArtifactType.walkthrough,
                        name="pull_request.md",
                        content=pr_md,
                        content_type="text/markdown",
                        agent="pr_agent",
                    )

            if hasattr(self._run_store, "update_run"):
                wf_status = values.get("status", "")
                if wf_status == "rejected" or decision == PlanDecision.reject:
                    await self._run_store.update_run(
                        run_id,
                        status=RunStatus.rejected,
                        current_step="rejected",
                    )
                elif wf_status == "escalated":
                    await self._run_store.update_run(
                        run_id,
                        status=RunStatus.escalated,
                        current_step=values.get("current_agent") or "escalated",
                        error=values.get("error"),
                    )
                elif wf_status == "failed":
                    await self._run_store.update_run(
                        run_id,
                        status=RunStatus.failed,
                        current_step=values.get("current_agent") or "failed",
                        error=values.get("error") or "Agent workflow failed.",
                    )
                else:
                    await self._run_store.update_run(
                        run_id,
                        status=RunStatus.completed,
                        current_step="completed",
                    )


async def resume_plan_background_task(
    run_id: UUID,
    decision: PlanDecision,
    resumer: PlanResumer,
    store: object,
) -> None:
    """Safely call the plan resumer in the background.

    WHY THIS WRAPPER IS NEEDED:
    Same reason as run_agent_background_task — background tasks run outside
    the HTTP cycle. If the resumer raises, we catch it, log only the run_id
    (never the decision reason or plan content), and mark the run failed so
    the frontend can show a meaningful error. The server process is never
    crashed by agent-layer exceptions.
    """
    try:
        await resumer.resume(run_id, decision)
    except Exception:
        # Log only the run_id; never log decision reason, plan content, or traces
        logger.error("Plan resume for run %s failed", run_id)
        if hasattr(store, "update_run"):
            await store.update_run(
                run_id,
                status=RunStatus.failed,
                error="Failed to resume agent run",
            )
