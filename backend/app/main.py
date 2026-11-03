"""
FastAPI application entrypoint.

Creates the FastAPI app via ``create_app()``, applies CORS middleware,
runs the async lifespan (shared HTTP client + pluggable resource hooks),
and registers any routers that already exist in ``backend/app/api/``.

Lifecycle Convention
--------------------
Modules listed in ``LIFESPAN_MODULES`` may expose an **async context manager
factory** called ``lifespan_resource(app)``::

    @contextlib.asynccontextmanager
    async def lifespan_resource(app: FastAPI):
        # startup: acquire / create resources
        yield
        # shutdown: destroy / release resources (runs in finally)

At app startup each module is imported (if it exists) and its
``lifespan_resource`` is entered on an ``AsyncExitStack``.  At shutdown the
stack unwinds in **reverse** order, guaranteeing that resources created later
are cleaned up first — even if a subsequent resource fails during startup.

If a resource raises during startup it is logged and recorded in
``app.state.failed_hooks``; the app continues serving so that ``/health``
remains reachable (e.g. Docker may be unavailable on Render).
"""

from __future__ import annotations

import contextlib
import importlib
import importlib.util
import logging
import sys
from collections.abc import AsyncIterator

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.agent_gateway import EmptyMetricsProvider, LangGraphAgentGateway, NoOpAgentGateway, NoOpPlanResumer
from app.api.run_store import InMemoryRunStore
from app.config import Settings, get_settings

logger = logging.getLogger(__name__)

# ── Lifespan modules ────────────────────────────────────────────────
# Each entry is a dotted module path. At startup, for each module that
# exists and exposes ``lifespan_resource(app)``, we enter the context
# manager on the shared AsyncExitStack.
# Add "app.sandbox.e2b_manager" here when the E2B backend is ready.
LIFESPAN_MODULES: tuple[str, ...] = (
    "app.sandbox.docker_manager",
)

# ── Router modules to register ──────────────────────────────────────
# (module_path, attribute_name) pairs.  Each router module will declare
# its own APIRouter(prefix=..., tags=...) in Task 2.
# API prefix pending agreement with the frontend lead; see docs/api-contract.md
_ROUTER_MODULES: tuple[tuple[str, str], ...] = (
    ("app.api.runs", "router"),
    ("app.api.issues", "router"),
    ("app.api.webhooks", "router"),
    ("app.api.artifacts", "router"),
    ("app.api.metrics", "router"),
)


# ── Helpers ──────────────────────────────────────────────────────────

def _module_exists(name: str) -> bool:
    """Return True if *name* can be found as an importable module.

    ``importlib.util.find_spec("a.b.c")`` raises ``ModuleNotFoundError``
    when a **parent** package (``a`` or ``a.b``) does not exist.  We catch
    that error only when the missing name is the module we asked about or
    one of its parent packages.  Any other ``ModuleNotFoundError`` (i.e. a
    genuine import bug inside an existing module) is re-raised.
    """
    # Fast path: already imported.
    if name in sys.modules:
        return True
    try:
        return importlib.util.find_spec(name) is not None
    except ModuleNotFoundError as exc:
        # exc.name is the package that was actually not found.
        # Guard against exc.name being None (should not happen, but
        # avoids a TypeError on the startswith check).
        if exc.name is None:
            raise
        if exc.name == name or name.startswith(exc.name + "."):
            return False
        raise


# ── Lifespan ─────────────────────────────────────────────────────────

@contextlib.asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    """App-level lifespan: startup before ``yield``, shutdown after."""
    # Read settings from app.state (set by create_app) — never call
    # get_settings() here, so the settings passed to create_app are used.
    app.state.failed_hooks = []

    async with contextlib.AsyncExitStack() as stack:
        # Step 1: shared HTTP client ──────────────────────────────────
        http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(60.0, connect=10.0),
        )
        app.state.http_client = http_client
        stack.push_async_callback(http_client.aclose)

        # Step 2: lifespan resources from LIFESPAN_MODULES ────────────
        for module_name in LIFESPAN_MODULES:
            if not _module_exists(module_name):
                logger.info("Lifespan module %s not found; skipping.", module_name)
                continue

            try:
                mod = importlib.import_module(module_name)
            except Exception:
                logger.exception("Failed to import lifespan module %s", module_name)
                app.state.failed_hooks.append(module_name)
                continue

            resource_factory = getattr(mod, "lifespan_resource", None)
            if resource_factory is None:
                logger.info(
                    "Module %s has no lifespan_resource; skipping.", module_name,
                )
                continue

            try:
                await stack.enter_async_context(resource_factory(app))
                logger.info("Lifespan resource %s started.", module_name)
            except Exception:
                logger.exception(
                    "Lifespan resource %s failed during startup.", module_name,
                )
                app.state.failed_hooks.append(module_name)

        logger.info("Startup complete.")
        yield
    # AsyncExitStack.__aexit__ runs here — cleanup in reverse order.
    logger.info("Shutdown complete.")


# ── App factory ──────────────────────────────────────────────────────

def create_app(settings: Settings | None = None) -> FastAPI:
    """Build and return the configured :class:`FastAPI` application."""
    if settings is None:
        settings = get_settings()

    docs_kwargs: dict[str, str | None] = {}
    if not settings.docs_enabled:
        docs_kwargs.update(docs_url=None, redoc_url=None, openapi_url=None)

    application = FastAPI(
        title="Mini-Devin Backend",
        lifespan=_lifespan,
        **docs_kwargs,
    )

    # Store settings and initialise state used by the lifespan.
    application.state.settings = settings
    application.state.failed_hooks: list[str] = []
    application.state.http_client = None
    application.state.run_store = InMemoryRunStore()
    application.state.agent_gateway = LangGraphAgentGateway()
    application.state.metrics_provider = EmptyMetricsProvider()
    application.state.plan_resumer = NoOpPlanResumer()

    # ── CORS ─────────────────────────────────────────────────────────
    # NOTE: CORSMiddleware does NOT protect WebSocket routes.
    # The WebSocket layer (a later task) must check the Origin header itself.
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        # Enable only if cookie auth is introduced, and never with a wildcard origin.
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization"],
    )

    # ── Health endpoint ──────────────────────────────────────────────
    @application.get("/health")
    async def health() -> dict:
        return {"status": "ok"}

    # ── Router registration ──────────────────────────────────────────
    _registered: list[str] = []
    _skipped: list[str] = []

    for mod_path, attr in _ROUTER_MODULES:
        if not _module_exists(mod_path):
            _skipped.append(mod_path)
            continue

        # Do NOT catch import errors for routers — a broken router module
        # must fail startup loudly so the bug is caught immediately.
        mod = importlib.import_module(mod_path)

        router_obj = getattr(mod, attr, None)
        if router_obj is None:
            _skipped.append(mod_path)
            continue

        application.include_router(router_obj)
        _registered.append(mod_path)

    if _registered:
        logger.info("Registered routers: %s", ", ".join(_registered))
    if _skipped:
        # TODO: Register these routers once they define a `router` object:
        #   - app.api.runs
        #   - app.api.issues
        #   - app.api.webhooks
        #   - app.api.artifacts
        #   - app.api.metrics
        logger.info("Skipped routers (no router object yet): %s", ", ".join(_skipped))

    return application


# Module-level app for ``uvicorn app.main:app``
app = create_app()
