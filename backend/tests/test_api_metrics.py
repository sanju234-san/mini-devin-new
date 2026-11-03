"""Tests for GET /metrics route."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.api.agent_gateway import MetricsProvider
from app.api.deps import get_metrics_provider
from app.main import create_app
from app.models.metrics import MetricsOut, SWEBenchLiteMetrics


def test_metrics_default_empty_provider():
    app = create_app()
    with TestClient(app) as client:
        response = client.get("/metrics")
        assert response.status_code == 200
        data = response.json()
        assert data["available"] is False
        assert data["fix_accuracy"] is None
        assert data["test_pass_rate"] is None
        assert data["avg_self_correction_iterations"] is None
        assert data["swe_bench_lite"] is None
        assert data["updated_at"] is None


def test_metrics_overridden_provider():
    now = datetime.now(timezone.utc)

    class CustomMetricsProvider:
        async def get_metrics(self) -> MetricsOut:
            return MetricsOut(
                available=True,
                fix_accuracy=0.78,
                test_pass_rate=0.85,
                avg_self_correction_iterations=1.4,
                swe_bench_lite=SWEBenchLiteMetrics(
                    resolved=39,
                    total=50,
                    resolve_rate=0.78,
                ),
                updated_at=now,
            )

    app = create_app()
    app.dependency_overrides[get_metrics_provider] = lambda: CustomMetricsProvider()

    with TestClient(app) as client:
        response = client.get("/metrics")
        assert response.status_code == 200
        data = response.json()
        assert data["available"] is True
        assert data["fix_accuracy"] == 0.78
        assert data["test_pass_rate"] == 0.85
        assert data["avg_self_correction_iterations"] == 1.4
        assert data["swe_bench_lite"]["resolved"] == 39
        assert data["swe_bench_lite"]["total"] == 50
        assert data["swe_bench_lite"]["resolve_rate"] == 0.78
        assert data["updated_at"] is not None
