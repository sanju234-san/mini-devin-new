"""GitHub issue ingestion endpoints — the entry point for a new agent run.

This module provides the REST API route for directly submitting GitHub issues
to Mini-Devin. Ingesting an issue creates a new agent run in 'queued' status
and schedules execution via FastAPI BackgroundTasks.

Security & Resilience:
- Request body is validated against IssueIn (strict length limits, repo regex,
  and no extra fields).
- Issue content is stored as plain data; it is never executed or logged.
- Background execution catches any unhandled exceptions, marks the run failed,
  and logs only the run_id, preventing unhandled crashes in background tasks.
"""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, status

from app.api.agent_gateway import AgentGateway, run_agent_background_task
from app.api.deps import get_agent_gateway, get_run_store
from app.api.run_store import RunStore
from app.models.run import IssueIn, RunSummary

router = APIRouter(prefix="/issues", tags=["issues"])


@router.post(
    "/ingest",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=RunSummary,
    summary="Ingest a GitHub issue and queue an autonomous run",
)
async def ingest_issue(
    issue: IssueIn,
    background_tasks: BackgroundTasks,
    store: RunStore = Depends(get_run_store),
    gateway: AgentGateway = Depends(get_agent_gateway),
) -> RunSummary:
    """Accept an issue description, create a queued run, and start background processing.

    Returns HTTP 202 Accepted with the initial RunSummary representation.
    """
    # Create the run in the store with initial status 'queued'
    run = await store.create_run(issue)

    # Schedule the shared background task to start execution without blocking the response
    background_tasks.add_task(run_agent_background_task, run.id, issue, gateway, store)

    return RunSummary(
        id=run.id,
        status=run.status,
        current_step=run.current_step,
        issue=run.issue,
        created_at=run.created_at,
        updated_at=run.updated_at,
        error=run.error,
    )
