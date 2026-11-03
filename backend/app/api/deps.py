"""FastAPI dependency providers for API routes.

Injects the run store, agent gateway, metrics provider, and application
settings from application state. In tests, these dependencies can be
overridden via `app.dependency_overrides`.

Note: Types used here are kept available at runtime (not inside
`if TYPE_CHECKING:`) so FastAPI's dependency injection and OpenAPI
reflection function properly.
"""

from __future__ import annotations

from fastapi import Request

from app.api.agent_gateway import AgentGateway, MetricsProvider, PlanResumer
from app.api.run_store import RunStore
from app.config import Settings, get_settings


def get_run_store(request: Request) -> RunStore:
    """Provide the RunStore instance stored on application state."""
    return request.app.state.run_store


def get_agent_gateway(request: Request) -> AgentGateway:
    """Provide the AgentGateway instance stored on application state."""
    return request.app.state.agent_gateway


def get_metrics_provider(request: Request) -> MetricsProvider:
    """Provide the MetricsProvider instance stored on application state."""
    return request.app.state.metrics_provider


def get_settings_dep(request: Request) -> Settings:
    """Provide the application Settings instance from application state.

    Allows tests to easily override application settings (such as webhook secret)
    per-test using `app.dependency_overrides[get_settings_dep] = lambda: ...`.
    """
    settings = getattr(request.app.state, "settings", None)
    if settings is None:
        settings = get_settings()
    return settings


def get_plan_resumer(request: Request) -> PlanResumer:
    """Provide the PlanResumer instance stored on application state.

    The default is NoOpPlanResumer (logs only). Sanjeevni's agent layer
    replaces this with a real implementation once the LangGraph graph
    is wired up. Tests inject a fake via app.dependency_overrides.
    """
    return request.app.state.plan_resumer
