"""
Hardened Error Routing and Exception Redaction Tests.

Validates:
1. Planner LLM failure returns status 'failed' and routes cleanly to 'safe_stop' terminal node.
2. Coder LLM failure returns status 'failed' without falling back to synthetic diff.
3. AllProvidersExhaustedError attaches sanitized provider_errors containing zero raw API keys.
"""

from __future__ import annotations

import os
from unittest.mock import patch
import pytest

from app.agents.coder.agent import coder_node
from app.agents.graph import create_graph
from app.agents.schemas import compute_plan_hash, create_initial_state
from app.integrations.llm_provider_client import complete, AllProvidersExhaustedError


def test_planner_llm_failure_routes_to_terminal_node():
    """When planner LLM call fails and fallback is disabled, status is failed and workflow halts at safe_stop."""
    graph = create_graph()
    initial_state = create_initial_state(
        issue_title="Test failure propagation",
        issue_body="Planner should fail when LLM provider fails.",
        repo="org/repo",
    )
    config = {"configurable": {"thread_id": initial_state["thread_id"]}}

    # Global guard in conftest blocks complete() with RuntimeError; ensure deterministic fallback is OFF
    with patch.dict(os.environ, {"ALLOW_DETERMINISTIC_FALLBACK": "false"}):
        final_state = graph.invoke(initial_state, config=config)

    assert final_state["status"] == "failed"
    assert "Planner failed" in final_state.get("error", "")
    # Verify it routed to terminal node and did NOT pause at human_approval
    saved_state = graph.get_state(config)
    assert saved_state.next == () or "human_approval" not in saved_state.next


def test_coder_llm_failure_returns_failed():
    """When coder LLM fails and fallback is disabled, coder returns status failed with error."""
    fake_plan = {
        "summary": "Fix connection issue",
        "affected_files": ["src/app.py"],
        "requirements": [{"id": "R1", "description": "Add timeout"}],
        "steps": [{"step_number": 1, "action": "modify", "target_file": "src/app.py", "description": "Add timeout"}],
    }
    plan_hash = compute_plan_hash(fake_plan)
    fake_plan["plan_hash"] = plan_hash
    state = {
        "plan": fake_plan,
        "human_approval": {"decision": "approved", "plan_hash": plan_hash},
        "repo": "org/repo",
        "events": [],
        "retrieved_context": {"snippets": []},
        "diff_schema_retries": 1,
    }

    # Simulate provider failure in coder
    with patch("app.agents.model_router.complete", side_effect=RuntimeError("Provider failure")), \
         patch.dict(os.environ, {"ALLOW_DETERMINISTIC_FALLBACK": "false"}):
        result = coder_node(state)

    assert result["status"] == "failed"
    assert "Coder failed" in result["error"]
    assert "Provider failure" in result["error"]
    assert result["current_agent"] == "coder"


def test_all_providers_exhausted_error_contains_no_keys():
    """AllProvidersExhaustedError must redact real keys and key-like patterns from error dict."""
    dummy_groq_key = "gsk_testSECRETkey1234567890abcdef"
    dummy_gemini_key = "AIzaSyTestSECRETkey9876543210zyxw"
    dummy_hf_key = "hf_testSECRETkey55555555555555555"

    def fail_groq(prompt: str):
        raise ValueError(f"Groq auth failed for key {dummy_groq_key}")

    def fail_gemini(prompt: str):
        raise ValueError(f"Gemini rejected {dummy_gemini_key}")

    def fail_hf(prompt: str):
        raise ValueError(f"HuggingFace invalid token {dummy_hf_key}")

    with patch.dict(os.environ, {
        "LLM_PROVIDER_CHAIN": "groq,gemini,huggingface",
        "GROQ_API_KEY": dummy_groq_key,
        "GOOGLE_AI_STUDIO_API_KEY": dummy_gemini_key,
        "HUGGINGFACE_API_TOKEN": dummy_hf_key,
    }), patch("app.integrations.llm_provider_client._call_groq", side_effect=fail_groq), \
       patch("app.integrations.llm_provider_client._call_gemini", side_effect=fail_gemini), \
       patch("app.integrations.llm_provider_client._call_huggingface", side_effect=fail_hf):

        with pytest.raises(AllProvidersExhaustedError) as exc_info:
            complete("test prompt", agent_name="test")

        err = exc_info.value
        err_str = str(err)
        details = str(err.provider_errors)

        # None of the raw secret keys should appear anywhere in the error or dictionary
        assert dummy_groq_key not in err_str and dummy_groq_key not in details
        assert dummy_gemini_key not in err_str and dummy_gemini_key not in details
        assert dummy_hf_key not in err_str and dummy_hf_key not in details

        # Sanitized token should be present
        assert "[REDACTED]" in details
        assert len(err.provider_errors) == 3
