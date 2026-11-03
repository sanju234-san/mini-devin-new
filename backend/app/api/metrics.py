"""Evaluation metrics endpoints for Mini-Devin.

This module provides the /metrics route that serves system evaluation data,
including fix accuracy, test pass rate, average self-correction iterations,
and SWE-bench Lite benchmark results.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.agent_gateway import MetricsProvider
from app.api.deps import get_metrics_provider
from app.models.metrics import MetricsOut

router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get(
    "",
    response_model=MetricsOut,
    summary="Get system evaluation and benchmark metrics",
)
async def get_metrics(
    provider: MetricsProvider = Depends(get_metrics_provider),
) -> MetricsOut:
    """Return aggregated benchmark and evaluation statistics."""
    return await provider.get_metrics()
