"""Create, list, fetch agent runs, and handle human plan decisions.

This module provides the core run lifecycle endpoints:
- GET  /runs:                      Paginated list of recent runs (summaries, newest first).
- GET  /runs/{run_id}:             Full details of a single run, including issue body.
- POST /runs/{run_id}/plan/decision: Submit a human plan decision (approve / edit / reject).

Plan Approval Walkthrough (beginner-friendly)
----------------------------------------------
1. The Planner agent finishes and the run pauses at status 'awaiting_plan_approval'.
2. The frontend fetches the plan via the existing artifact routes (GET /runs/{id}/artifacts).
3. The developer reads the plan and clicks Approve / Edit / Reject in the UI.
4. The UI POSTs to /runs/{run_id}/plan/decision with a JSON body like:
       {"decision": "approve"}
5. This endpoint atomically claims the decision (only one request wins even if
   two arrive simultaneously) and returns 202 with the updated RunSummary.
6. A background task then calls the PlanResumer (Sanjeevni's agent layer) to
   resume the paused LangGraph graph. If that call fails, the run is marked
   failed; the 202 response is already on its way to the client.
7. The developer can poll GET /runs/{run_id} or watch the WebSocket stream to
   see the run progress to 'running' and eventually to 'completed'.

Error codes:
- 404: Unknown run ID.
- 409: Run is not awaiting plan approval (wrong status or decision already made).
- 422: Invalid request body (bad decision value, missing edited_plan, etc.).
"""

from __future__ import annotations

import json
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status

from app.api.agent_gateway import PlanResumer, resume_plan_background_task
from app.api.deps import get_plan_resumer, get_run_store
from app.api.run_store import PlanDecisionOutcome, RunStore
from app.models.plan import PlanDecision, PlanDecisionIn
from app.models.run import RunDetail, RunList, RunSummary

router = APIRouter(prefix="/runs", tags=["runs"])


@router.get(
    "",
    response_model=RunList,
    summary="List agent runs with pagination",
)
async def list_runs(
    limit: int = Query(
        default=20,
        ge=1,
        le=100,
        description="Maximum number of runs to return (1-100)",
    ),
    offset: int = Query(
        default=0,
        ge=0,
        description="Number of runs to skip",
    ),
    store: RunStore = Depends(get_run_store),
) -> RunList:
    """Retrieve a paginated list of agent runs ordered newest first."""
    return await store.list_runs(limit=limit, offset=offset)


@router.get(
    "/{run_id}",
    response_model=RunDetail,
    summary="Get details of a specific agent run",
)
async def get_run(
    run_id: UUID,
    store: RunStore = Depends(get_run_store),
) -> RunDetail:
    """Fetch complete details for a run, including the original issue body."""
    run = await store.get_run(run_id)
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Run not found",
        )
    return run


@router.post(
    "/{run_id}/plan/decision",
    response_model=RunSummary,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Submit a human plan decision (approve / edit / reject)",
)
async def submit_plan_decision(
    run_id: UUID,
    body: PlanDecisionIn,
    background_tasks: BackgroundTasks,
    store: RunStore = Depends(get_run_store),
    resumer: PlanResumer = Depends(get_plan_resumer),
) -> RunSummary:
    """Record the human's plan decision and schedule the agent resume.

    Request body fields
    -------------------
    decision     : "approve" | "edit" | "reject"
    edited_plan  : dict (required only for "edit"; <= 64 KiB JSON)
    reason       : str | None  (max 2 000 chars; stored internally, never echoed)

    Response
    --------
    202 RunSummary on success. The body contains the *updated* run (new status
    and current_step). The response never echoes back the edited_plan or reason.

    Concurrency guarantee
    ---------------------
    The status check and transition are one atomic operation inside the store
    lock. Two simultaneous requests for the same run will result in one 202
    and one 409.
    """
    # Serialise edited_plan to a JSON string BEFORE entering the store.
    # The store receives a plain string (not a dict) so it can write it
    # directly as artifact content without any agent-owned schema dependency.
    edited_plan_content: str | None = None
    if body.edited_plan is not None:
        # json.dumps is safe here: PlanDecisionIn already validated the dict
        # is JSON-serialisable and <= 64 KiB.
        edited_plan_content = json.dumps(body.edited_plan)

    # Atomically claim the decision. This is the single point of truth for
    # whether this request wins the race; all logic (status change, artifact
    # creation) happens inside one lock acquisition inside the store.
    outcome, run_summary = await store.claim_plan_decision(
        run_id=run_id,
        decision=PlanDecision(body.decision),
        reason=body.reason,
        edited_plan_content=edited_plan_content,
    )

    if outcome == PlanDecisionOutcome.NOT_FOUND:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Run not found",
        )
    if outcome == PlanDecisionOutcome.CONFLICT:
        # Covers: wrong current status (queued, running, completed, failed,
        # rejected, escalated) AND a previous decision already claimed.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Run is not awaiting plan approval",
        )

    # run_summary is guaranteed to be non-None when outcome is OK
    assert run_summary is not None  # for type checkers

    # Schedule the background resume call. We do this AFTER the 202 response
    # is built so the HTTP client doesn't wait for the (potentially slow)
    # agent layer. If the resumer raises, resume_plan_background_task catches
    # it, marks the run failed, and never crashes the server.
    background_tasks.add_task(
        resume_plan_background_task,
        run_id=run_id,
        decision=PlanDecision(body.decision),
        resumer=resumer,
        store=store,
    )

    return run_summary

