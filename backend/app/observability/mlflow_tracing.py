"""
Mini-Devin Observability: MLflow Tracing and Structured Telemetry.

Provides self-hosted MLflow tracing for every agent step, tool invocation,
plan hash verification, review verdict, test evidence, and PR submission.
Degrades gracefully to standard logging when MLflow tracking server is unconfigured.
"""

from __future__ import annotations

import functools
import logging
import os
import time
from contextlib import contextmanager
from typing import Any, Callable, Generator, Optional

logger = logging.getLogger("mini_devin.observability")

_MLFLOW_ENABLED = False
_EXPERIMENT_NAME = os.getenv("MINI_DEVIN_MLFLOW_EXPERIMENT", "mini-devin-runs")
_AUDIT_LOGS: list[dict[str, Any]] = []


def is_mlflow_available() -> bool:
    """Check if MLflow is installed and configured."""
    global _MLFLOW_ENABLED
    try:
        import mlflow  # noqa: F401
        tracking_uri = os.getenv("MLFLOW_TRACKING_URI", "")
        _MLFLOW_ENABLED = bool(tracking_uri) or os.getenv("MINI_DEVIN_ENABLE_LOCAL_MLFLOW", "false").lower() == "true"
        return _MLFLOW_ENABLED
    except ImportError:
        _MLFLOW_ENABLED = False
        return False


def get_audit_trail() -> list[dict[str, Any]]:
    """Return in-memory copy of telemetry events for test assertions and diagnostics."""
    return list(_AUDIT_LOGS)


def clear_audit_trail() -> None:
    """Clear in-memory audit logs."""
    _AUDIT_LOGS.clear()


@contextmanager
def trace_agent_step(agent_name: str, run_id: Optional[str] = None) -> Generator[dict[str, Any], None, None]:
    """
    Context manager to trace execution duration, parameters, and outcome of an agent step.
    
    Logs to MLflow if available, and always records to structured audit trail.
    """
    start_time = time.perf_counter()
    record: dict[str, Any] = {
        "agent_name": agent_name,
        "run_id": run_id or "local",
        "start_time": start_time,
        "status": "in_progress",
    }
    logger.info("Trace started for agent '%s' [run_id=%s]", agent_name, record["run_id"])
    try:
        yield record
        record["status"] = "success"
    except Exception as exc:
        record["status"] = "failed"
        record["error"] = str(exc)
        raise
    finally:
        elapsed = time.perf_counter() - start_time
        record["duration_seconds"] = round(elapsed, 4)
        _AUDIT_LOGS.append(record)
        logger.info(
            "Trace completed for agent '%s' in %.4fs (status=%s)",
            agent_name,
            elapsed,
            record["status"],
        )
        if is_mlflow_available():
            try:
                import mlflow
                with mlflow.start_run(run_name=f"{agent_name}-step", nested=True):
                    mlflow.log_param("agent_name", agent_name)
                    mlflow.log_metric("duration_seconds", elapsed)
                    mlflow.set_tag("status", record["status"])
                    if "error" in record:
                        mlflow.set_tag("error", record["error"])
            except Exception as e:
                logger.debug("Non-blocking MLflow trace emission error: %s", e)


def trace_agent(agent_name: str) -> Callable:
    """Decorator to trace synchronous agent functions."""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            state = args[0] if args and isinstance(args[0], dict) else {}
            run_id = state.get("run_id") if isinstance(state, dict) else None
            with trace_agent_step(agent_name, run_id=run_id):
                return func(*args, **kwargs)
        return wrapper
    return decorator


def log_plan_metadata(run_id: str, version: str, plan_hash: str, requirements: list[Any]) -> None:
    """Log plan version, SHA-256 hash, and requirements count."""
    event = {
        "event": "plan_metadata",
        "run_id": run_id,
        "plan_version": version,
        "plan_hash": plan_hash,
        "requirements_count": len(requirements),
        "timestamp": time.time(),
    }
    _AUDIT_LOGS.append(event)
    logger.info("Plan logged: version=%s, hash=%s, reqs=%d", version, plan_hash[:8], len(requirements))
    if is_mlflow_available():
        try:
            import mlflow
            mlflow.log_param(f"plan_{run_id}_version", version)
            mlflow.log_param(f"plan_{run_id}_hash", plan_hash)
            mlflow.log_metric(f"plan_{run_id}_reqs_count", len(requirements))
        except Exception:
            pass


def log_tool_invocation(tool_name: str, arguments: dict[str, Any], duration_seconds: float, success: bool) -> None:
    """Log controlled tool execution telemetry."""
    event = {
        "event": "tool_invocation",
        "tool_name": tool_name,
        "duration_seconds": duration_seconds,
        "success": success,
        "arguments_keys": list(arguments.keys()),
        "timestamp": time.time(),
    }
    _AUDIT_LOGS.append(event)
    logger.info("Tool logged: tool=%s, success=%s, duration=%.4fs", tool_name, success, duration_seconds)


def log_test_evidence(run_id: str, passed: bool, total_tests: int, failed_tests: int, duration_seconds: float) -> None:
    """Log test verification results."""
    event = {
        "event": "test_evidence",
        "run_id": run_id,
        "passed": passed,
        "total_tests": total_tests,
        "failed_tests": failed_tests,
        "duration_seconds": duration_seconds,
        "timestamp": time.time(),
    }
    _AUDIT_LOGS.append(event)
    logger.info("Test results logged: passed=%s, total=%d, failed=%d", passed, total_tests, failed_tests)
    if is_mlflow_available():
        try:
            import mlflow
            mlflow.log_metric(f"tests_{run_id}_passed", 1 if passed else 0)
            mlflow.log_metric(f"tests_{run_id}_total", total_tests)
            mlflow.log_metric(f"tests_{run_id}_failed", failed_tests)
            mlflow.log_metric(f"tests_{run_id}_duration", duration_seconds)
        except Exception:
            pass


def log_review_outcome(run_id: str, verdict: str, score: float, dimensions: dict[str, Any]) -> None:
    """Log 6-dimensional review findings and verdict."""
    event = {
        "event": "review_outcome",
        "run_id": run_id,
        "verdict": verdict,
        "score": score,
        "dimensions": dimensions,
        "timestamp": time.time(),
    }
    _AUDIT_LOGS.append(event)
    logger.info("Review logged: verdict=%s, score=%.2f, dimensions=%s", verdict, score, list(dimensions.keys()))
    if is_mlflow_available():
        try:
            import mlflow
            mlflow.log_param(f"review_{run_id}_verdict", verdict)
            mlflow.log_metric(f"review_{run_id}_score", score)
        except Exception:
            pass


def log_pr_outcome(run_id: str, status: str, pull_request_url: Optional[str]) -> None:
    """Log PR generation and submission outcome."""
    event = {
        "event": "pr_outcome",
        "run_id": run_id,
        "status": status,
        "pull_request_url": pull_request_url,
        "timestamp": time.time(),
    }
    _AUDIT_LOGS.append(event)
    logger.info("PR logged: status=%s, url=%s", status, pull_request_url)
    if is_mlflow_available():
        try:
            import mlflow
            mlflow.set_tag(f"pr_{run_id}_status", status)
            if pull_request_url:
                mlflow.set_tag(f"pr_{run_id}_url", pull_request_url)
        except Exception:
            pass
