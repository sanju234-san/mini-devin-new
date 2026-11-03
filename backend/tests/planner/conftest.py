import pytest


@pytest.fixture(autouse=True)
def mock_triage_classifier(monkeypatch: pytest.MonkeyPatch):
    """Monkeypatch triage classifier used by the live Triage node during planner tests."""
    monkeypatch.setattr(
        "app.agents.triage.agent.classify_with_confidence",
        lambda _: ("bug_fix", 0.95),
    )
