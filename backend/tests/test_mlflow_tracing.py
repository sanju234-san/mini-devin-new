"""
Tests for MLflow tracing and telemetry module.
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

from app.observability.mlflow_tracing import (
    clear_audit_trail,
    get_audit_trail,
    is_mlflow_available,
    log_plan_metadata,
    log_pr_outcome,
    log_review_outcome,
    log_test_evidence,
    log_tool_invocation,
    trace_agent_step,
)


@pytest.fixture(autouse=True)
def clean_audit():
    clear_audit_trail()
    yield
    clear_audit_trail()


def test_audit_trail_recorded_without_mlflow():
    with patch.dict(os.environ, {"MLFLOW_TRACKING_URI": "", "MINI_DEVIN_ENABLE_LOCAL_MLFLOW": "false"}):
        assert not is_mlflow_available()

        with trace_agent_step(agent_name="triage", run_id="run-123") as rec:
            rec["status"] = "success"

        trail = get_audit_trail()
        assert len(trail) == 1
        assert trail[0]["agent_name"] == "triage"
        assert trail[0]["run_id"] == "run-123"
        assert trail[0]["status"] == "success"
        assert "duration_seconds" in trail[0]


def test_audit_trail_records_failure_on_exception():
    with patch.dict(os.environ, {"MLFLOW_TRACKING_URI": "", "MINI_DEVIN_ENABLE_LOCAL_MLFLOW": "false"}):
        with pytest.raises(ValueError, match="test error"):
            with trace_agent_step(agent_name="coder", run_id="run-456"):
                raise ValueError("test error")

        trail = get_audit_trail()
        assert len(trail) == 1
        assert trail[0]["agent_name"] == "coder"
        assert trail[0]["status"] == "failed"
        assert "test error" in trail[0]["error"]


def test_metrics_recording_with_mocked_mlflow():
    mock_mlflow = MagicMock()
    with patch.dict(os.environ, {"MLFLOW_TRACKING_URI": "http://localhost:5000"}):
        with patch("app.observability.mlflow_tracing.is_mlflow_available", return_value=True):
            with patch.dict("sys.modules", {"mlflow": mock_mlflow}):
                log_plan_metadata("run-1", "v1", "hash123", ["req1", "req2"])
                mock_mlflow.log_param.assert_any_call("plan_run-1_version", "v1")
                mock_mlflow.log_param.assert_any_call("plan_run-1_hash", "hash123")
                mock_mlflow.log_metric.assert_any_call("plan_run-1_reqs_count", 2)

                log_test_evidence("run-1", True, 5, 0, 1.25)
                mock_mlflow.log_metric.assert_any_call("tests_run-1_passed", 1)
                mock_mlflow.log_metric.assert_any_call("tests_run-1_total", 5)

                log_review_outcome("run-1", "approve", 0.95, {"syntax": True})
                mock_mlflow.log_param.assert_any_call("review_run-1_verdict", "approve")
                mock_mlflow.log_metric.assert_any_call("review_run-1_score", 0.95)

                log_pr_outcome("run-1", "submitted", "https://github.com/org/repo/pull/1")
                mock_mlflow.set_tag.assert_any_call("pr_run-1_status", "submitted")
                mock_mlflow.set_tag.assert_any_call("pr_run-1_url", "https://github.com/org/repo/pull/1")

