"""Tests for the app lifespan — HTTP client, lifespan modules, fail-soft startup."""

from __future__ import annotations

import contextlib
import importlib.machinery
import importlib.util
import sys
import types
from collections.abc import AsyncGenerator

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import _module_exists, create_app


# ── Helpers ──────────────────────────────────────────────────────────

def _settings(**overrides: object) -> Settings:
    return Settings(_env_file=None, **overrides)


def _fake_module(
    name: str,
    lifespan_resource: object | None = None,
) -> types.ModuleType:
    """Create a minimal fake module with a ``__spec__`` attribute."""
    mod = types.ModuleType(name)
    mod.__spec__ = importlib.machinery.ModuleSpec(name, None)
    if lifespan_resource is not None:
        mod.lifespan_resource = lifespan_resource  # type: ignore[attr-defined]
    return mod


def _tracking_resource(
    log: list[str],
    tag: str,
    *,
    fail: bool = False,
):
    """Return a lifespan_resource factory that records startup/shutdown."""

    @contextlib.asynccontextmanager
    async def lifespan_resource(app: object) -> AsyncGenerator[None]:
        if fail:
            raise RuntimeError(f"{tag} startup failure")
        log.append(f"{tag}:start")
        try:
            yield
        finally:
            log.append(f"{tag}:stop")

    return lifespan_resource


# ── Tests ────────────────────────────────────────────────────────────

class TestHTTPClient:
    """The shared httpx.AsyncClient must be created at startup and closed at shutdown."""

    def test_http_client_exists_during_lifetime(self) -> None:
        application = create_app(settings=_settings())
        with TestClient(application) as client:
            # During the app's lifetime the HTTP client should exist and be open.
            http_client = application.state.http_client
            assert http_client is not None
            assert not http_client.is_closed

        # After shutdown, the client should be closed.
        assert application.state.http_client.is_closed


class TestLifespanResource:
    """Individual lifespan_resource hooks are entered and cleaned up."""

    def test_startup_and_cleanup_run(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        log: list[str] = []
        mod = _fake_module("fake_res_a", _tracking_resource(log, "A"))
        monkeypatch.setitem(sys.modules, "fake_res_a", mod)
        monkeypatch.setattr("app.main.LIFESPAN_MODULES", ("fake_res_a",))

        application = create_app(settings=_settings())
        with TestClient(application):
            assert "A:start" in log
            assert "A:stop" not in log

        assert "A:stop" in log


class TestReverseCleanupOrder:
    """With two resources, cleanup must run in reverse order of startup."""

    def test_reverse_order(self, monkeypatch: pytest.MonkeyPatch) -> None:
        log: list[str] = []
        mod_x = _fake_module("fake_res_x", _tracking_resource(log, "X"))
        mod_y = _fake_module("fake_res_y", _tracking_resource(log, "Y"))
        monkeypatch.setitem(sys.modules, "fake_res_x", mod_x)
        monkeypatch.setitem(sys.modules, "fake_res_y", mod_y)
        monkeypatch.setattr(
            "app.main.LIFESPAN_MODULES", ("fake_res_x", "fake_res_y"),
        )

        application = create_app(settings=_settings())
        with TestClient(application):
            assert log == ["X:start", "Y:start"]

        # Cleanup must be Y then X (reverse order).
        assert log == ["X:start", "Y:start", "Y:stop", "X:stop"]


class TestFailSoftStartup:
    """A resource that raises at startup must not crash the app."""

    def test_failing_resource_does_not_crash(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        log: list[str] = []
        mod_ok = _fake_module("fake_res_ok", _tracking_resource(log, "OK"))
        mod_bad = _fake_module("fake_res_bad", _tracking_resource(log, "BAD", fail=True))
        monkeypatch.setitem(sys.modules, "fake_res_ok", mod_ok)
        monkeypatch.setitem(sys.modules, "fake_res_bad", mod_bad)
        monkeypatch.setattr(
            "app.main.LIFESPAN_MODULES", ("fake_res_ok", "fake_res_bad"),
        )

        application = create_app(settings=_settings())
        with TestClient(application) as client:
            # /health should still work.
            resp = client.get("/health")
            assert resp.status_code == 200
            assert resp.json() == {"status": "ok"}

            # The failing module's name appears in failed_hooks.
            assert "fake_res_bad" in application.state.failed_hooks
            # The OK module started fine.
            assert "OK:start" in log

        # The OK module was still cleaned up.
        assert "OK:stop" in log


class TestMissingModulesSkipped:
    """Missing modules (including dotted names with missing parents) are skipped."""

    def test_missing_module_skipped(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(
            "app.main.LIFESPAN_MODULES", ("nonexistent_module_xyz",),
        )
        application = create_app(settings=_settings())
        with TestClient(application) as client:
            resp = client.get("/health")
            assert resp.status_code == 200
            assert application.state.failed_hooks == []

    def test_dotted_missing_parent_skipped(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A dotted name whose parent package doesn't exist should be skipped."""
        monkeypatch.setattr(
            "app.main.LIFESPAN_MODULES", ("no_pkg_xyz.sub.mod",),
        )
        application = create_app(settings=_settings())
        with TestClient(application) as client:
            resp = client.get("/health")
            assert resp.status_code == 200
            assert application.state.failed_hooks == []


class TestModuleExistsHardening:
    """_module_exists must re-raise genuine import bugs."""

    def test_genuine_import_bug_reraises(self, tmp_path) -> None:
        """A package whose __init__.py imports a missing dep must raise
        when we check for a submodule (find_spec executes the parent)."""
        pkg = tmp_path / "buggy_pkg_xyz"
        pkg.mkdir()
        (pkg / "__init__.py").write_text(
            "import totally_nonexistent_dep_xyz\n"
        )
        # Add tmp_path to sys.path so the package is findable.
        sys.path.insert(0, str(tmp_path))
        try:
            # find_spec("buggy_pkg_xyz") only finds the spec without running
            # __init__.py, but find_spec("buggy_pkg_xyz.sub") must import the
            # parent, which triggers the genuine import error.
            with pytest.raises(ModuleNotFoundError):
                _module_exists("buggy_pkg_xyz.sub")
        finally:
            sys.path.remove(str(tmp_path))
            sys.modules.pop("buggy_pkg_xyz", None)

    def test_find_spec_raising_with_name_none_reraises(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """If find_spec raises ModuleNotFoundError with name=None, re-raise."""
        exc = ModuleNotFoundError("weird error")
        exc.name = None  # type: ignore[assignment]
        monkeypatch.setattr(
            importlib.util, "find_spec", lambda _: (_ for _ in ()).throw(exc),
        )
        # Must NOT be silently swallowed; should re-raise.
        with pytest.raises(ModuleNotFoundError, match="weird error"):
            _module_exists("some_module")
