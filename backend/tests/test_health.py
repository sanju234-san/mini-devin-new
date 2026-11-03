"""Smoke test for the /health endpoint."""

from fastapi.testclient import TestClient

from app.main import app


def test_health_via_module_level_app() -> None:
    """The ``uvicorn app.main:app`` target returns 200 on GET /health."""
    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
