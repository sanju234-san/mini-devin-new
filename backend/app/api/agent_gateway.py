"""Agent gateway and metrics provider protocols and default stubs.

This module defines the boundaries between the REST API layer (owned by
Tamanna) and the multi-agent orchestration layer (owned by Sanjeevni).

By depending on these protocols rather than importing `app.agents` directly:
1. The REST API runs independently without waiting for agent implementation.
2. Unit and integration tests can easily substitute mock gateways.
3. Merge conflicts between backend routes and agent logic are prevented.
"""

from __future__ import annotations

import logging
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

    def __init__(self, checkpointer=None):
        self._checkpointer = checkpointer

    async def start_run(self, run_id: UUID, issue: IssueIn) -> None:
        from app.agents.checkpointer import get_checkpointer
        from app.agents.graph import create_graph
        from app.agents.schemas import create_initial_state

        run_id_str = str(run_id)
        thread_id = run_id_str
        checkpointer = self._checkpointer or get_checkpointer()

        owner = issue.repo.owner if hasattr(issue.repo, "owner") else "unknown"
        name = issue.repo.name if hasattr(issue.repo, "name") else "repo"
        repo = f"{owner}/{name}"

        initial_state = create_initial_state(
            repo=repo,
            issue_title=issue.title,
            issue_body=issue.body,
            run_id=run_id_str,
            thread_id=thread_id,
        )

        graph = create_graph(checkpointer=checkpointer)
        config = {"configurable": {"thread_id": thread_id}}

        logger.info("LangGraphAgentGateway: Launching workflow for run %s (%s)", run_id_str, repo)
        # Execute workflow up to human approval interrupt
        await graph.ainvoke(initial_state, config=config)
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
