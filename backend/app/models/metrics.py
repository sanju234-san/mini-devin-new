"""Pydantic v2 schemas for Mini-Devin evaluation metrics.

This module defines the response model for system-wide benchmarks and
evaluation results, including fix accuracy, test pass rate, average
self-correction iterations, and SWE-bench Lite resolution statistics.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class SWEBenchLiteMetrics(BaseModel):
    """SWE-bench Lite benchmark results."""

    resolved: int = Field(
        ...,
        ge=0,
        description="Number of benchmark instances resolved",
    )
    total: int = Field(
        ...,
        ge=0,
        description="Total number of benchmark instances evaluated",
    )
    resolve_rate: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Fraction of instances resolved (0.0 to 1.0)",
    )


class MetricsOut(BaseModel):
    """Evaluation metrics payload returned by the /metrics endpoint."""

    available: bool = Field(
        ...,
        description="Whether evaluation metrics are currently available",
    )
    fix_accuracy: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Historical or benchmark fix accuracy rate (0.0 to 1.0)",
    )
    test_pass_rate: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Fraction of test suites passing on first or final attempt (0.0 to 1.0)",
    )
    avg_self_correction_iterations: float | None = Field(
        default=None,
        ge=0.0,
        description="Average number of debugger/self-correction loops per issue",
    )
    swe_bench_lite: SWEBenchLiteMetrics | None = Field(
        default=None,
        description="SWE-bench Lite benchmark performance stats, if evaluated",
    )
    updated_at: datetime | None = Field(
        default=None,
        description="Timestamp when metrics were last refreshed (UTC)",
    )
