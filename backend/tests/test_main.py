"""Tests for app.main — health endpoint, CORS, docs, routers, and app startup."""

from __future__ import annotations

import sys
import types

import pytest
from fastapi import APIRouter
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


# ── Helpers ──────────────────────────────────────────────────────────

def _make_client(
    settings: Settings | None = None,
    **overrides: object,
) -> TestClient:
    """Build a TestClient with custom settings.

    Keyword arguments are passed to ``Settings(...)`` when *settings* is
    not supplied.
    """
    if settings is None:
        settings = Settings(_env_file=None, **overrides)
    application = create_app(settings=settings)
    return TestClient(application)


# ── Health endpoint ──────────────────────────────────────────────────

class TestHealth:
    def test_health_returns_200(self) -> None:
        client = _make_client()
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}

    def test_health_does_not_expose_config(self) -> None:
        client = _make_client(GROQ_API_KEY="secret123")
        resp = client.get("/health")
        body = resp.text
        assert "secret123" not in body


# ── CORS ─────────────────────────────────────────────────────────────

class TestCORS:
    def test_preflight_allowed_origin(self) -> None:
        client = _make_client(
            CORS_ALLOWED_ORIGINS="https://my-app.vercel.app",
        )
        resp = client.options(
            "/health",
            headers={
                "Origin": "https://my-app.vercel.app",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert resp.headers.get("access-control-allow-origin") == "https://my-app.vercel.app"

    def test_preflight_disallowed_origin(self) -> None:
        client = _make_client(
            CORS_ALLOWED_ORIGINS="https://my-app.vercel.app",
        )
        resp = client.options(
            "/health",
            headers={
                "Origin": "https://evil.com",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert "access-control-allow-origin" not in resp.headers

    def test_simple_request_allowed_origin(self) -> None:
        client = _make_client(
            CORS_ALLOWED_ORIGINS="http://localhost:3000",
        )
        resp = client.get("/health", headers={"Origin": "http://localhost:3000"})
        assert resp.headers.get("access-control-allow-origin") == "http://localhost:3000"

    def test_simple_request_disallowed_origin(self) -> None:
        client = _make_client(
            CORS_ALLOWED_ORIGINS="http://localhost:3000",
        )
        resp = client.get("/health", headers={"Origin": "https://evil.com"})
        assert "access-control-allow-origin" not in resp.headers

    def test_credentials_not_allowed(self) -> None:
        """allow_credentials is False — no cookie auth."""
        client = _make_client(
            CORS_ALLOWED_ORIGINS="https://my-app.vercel.app",
        )
        resp = client.options(
            "/health",
            headers={
                "Origin": "https://my-app.vercel.app",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert resp.headers.get("access-control-allow-credentials") != "true"


# ── Docs endpoints ──────────────────────────────────────────────────

class TestDocsEndpoints:
    def test_docs_available_in_development(self) -> None:
        client = _make_client(ENVIRONMENT="development")
        assert client.get("/docs").status_code == 200
        assert client.get("/redoc").status_code == 200
        assert client.get("/openapi.json").status_code == 200

    def test_docs_disabled_in_production(self) -> None:
        client = _make_client(ENVIRONMENT="production")
        assert client.get("/docs").status_code == 404
        assert client.get("/redoc").status_code == 404
        assert client.get("/openapi.json").status_code == 404

    def test_docs_re_enabled_in_production_via_flag(self) -> None:
        client = _make_client(ENVIRONMENT="production", ENABLE_DOCS=True)
        assert client.get("/docs").status_code == 200


# ── App state ────────────────────────────────────────────────────────

class TestAppState:
    def test_state_settings_is_the_one_passed_to_create_app(self) -> None:
        """create_app(settings=custom) must store that exact instance."""
        custom = Settings(_env_file=None)
        application = create_app(settings=custom)
        with TestClient(application):
            assert application.state.settings is custom


# ── Router registration ─────────────────────────────────────────────

class TestRouterRegistration:
    def test_fake_router_mounted_without_extra_prefix(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A router with GET /ping is reachable at exactly /ping (no /api prefix)."""
        router = APIRouter()

        @router.get("/ping")
        async def ping():
            return {"pong": True}

        fake_mod = types.ModuleType("fake_router_mod")
        fake_mod.router = router  # type: ignore[attr-defined]
        monkeypatch.setitem(sys.modules, "fake_router_mod", fake_mod)
        monkeypatch.setattr(
            "app.main._ROUTER_MODULES",
            (("fake_router_mod", "router"),),
        )

        application = create_app(settings=Settings(_env_file=None))
        with TestClient(application) as client:
            resp = client.get("/ping")
            assert resp.status_code == 200
            assert resp.json() == {"pong": True}

    def test_broken_router_module_crashes_startup(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path,
    ) -> None:
        """A router module that exists but raises on import must stop startup."""
        pkg = tmp_path / "broken_router_pkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text(
            "raise RuntimeError('intentional import error')\n"
        )
        monkeypatch.syspath_prepend(str(tmp_path))
        monkeypatch.setattr(
            "app.main._ROUTER_MODULES",
            (("broken_router_pkg", "router"),),
        )

        with pytest.raises(RuntimeError, match="intentional import error"):
            create_app(settings=Settings(_env_file=None))


# ── App startup ──────────────────────────────────────────────────────

class TestAppStartup:
    def test_app_imports_and_starts_with_empty_env(self) -> None:
        """The app must import and serve /health with no env vars set."""
        client = _make_client()
        resp = client.get("/health")
        assert resp.status_code == 200
