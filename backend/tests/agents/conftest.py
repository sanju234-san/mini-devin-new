import pytest
import socket
import os
import inspect
from unittest.mock import patch

@pytest.fixture(autouse=True)
def block_llm_calls(monkeypatch):
    """
    Global guard to prevent any test from making real LLM provider calls.
    Patches the entry point in the shared provider client.
    """
    def guarded_complete(*args, **kwargs):
        # Use a loop to find the first frame outside of the guard logic
        frame = inspect.currentframe()
        while frame:
            if frame.f_code.co_name not in ("guarded_complete", "complete"):
                break
            frame = frame.f_back

        caller_file = frame.f_code.co_filename if frame else "unknown"
        caller_line = frame.f_lineno if frame else 0
        raise RuntimeError(
            f"Unexpected LLM provider call detected in {caller_file}:{caller_line}. "
            "All provider calls in tests must be explicitly mocked."
        )

    # Patch the core implementation used by model_router and other agents
    monkeypatch.setattr(
        "app.integrations.llm_provider_client.complete",
        guarded_complete
    )
    monkeypatch.setattr(
        "app.agents.model_router.provider_complete",
        guarded_complete
    )
