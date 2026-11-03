
"""
Unit tests for the Coder Agent.
Verifies LLM-based patch generation, safety guardrails, and approval enforcement.
"""

from __future__ import annotations

import json
from unittest.mock import patch
import pytest

from app.agents.coder.agent import coder_node
from app.agents.schemas import create_event

@pytest.fixture(autouse=True)
def mock_llm_router():
    """Prevent any test from reaching the real LLM provider."""
    with patch("app.agents.model_router.complete") as mock:
        yield mock

@pytest.fixture(autouse=True)
def block_network():
    """Fail any test that attempts to call the real provider client or network."""
    with patch("app.integrations.llm_provider_client.complete", side_effect=RuntimeError("Network call detected in test!")):
        yield

@pytest.fixture
def approved_state() -> dict:
    """Fixture providing authentic repository retrieval evidence."""
    plan = {
        "summary": "Fix division by zero",
        "explanation": "Detailed reasoning",
        "steps": [{"step_number": 1, "description": "Fix", "target_file": "src/calc.py", "action": "modify"}],
        "affected_files": ["src/calc.py"],
        "plan_version": "v1",
    }
    from app.agents.schemas import compute_plan_hash
    plan_hash = compute_plan_hash(plan)

    return {
        "human_approval": {"decision": "approved", "plan_hash": plan_hash},
        "plan": plan,
        "retrieved_context": {"files": ["src/calc.py"], "snippets": []},
        "events": [],
    }

def test_coder_blocks_unapproved_plan(approved_state: dict):
    """Coder must halt if human_approval is not 'approved'."""
    state = approved_state.copy()
    state["human_approval"] = {"decision": "rejected"}

    result = coder_node(state)
    assert result["status"] == "failed"
    assert "approval is missing" in result["error"]

def test_coder_blocks_hash_mismatch(approved_state: dict):
    """Coder must halt if the current plan hash differs from the approved hash."""
    state = approved_state.copy()
    state["plan"] = state["plan"].copy()
    state["plan"]["summary"] = "Tampered summary"

    result = coder_node(state)
    assert result["status"] == "failed"
    assert "hash mismatch" in result["error"]

def test_coder_blocks_unsafe_path(approved_state: dict):
    """Coder must halt if it attempts to modify a denied path."""
    state = approved_state.copy()
    state["code_changes"] = [{"file_path": ".env", "diff": "secret=123"}]

def test_coder_blocks_unsafe_path(approved_state: dict):
    """Coder must halt if it attempts to modify a denied path."""
    state = approved_state.copy()
    # Pre-stage an unsafe change
    state["code_changes"] = [{"file_path": ".env", "diff": "secret=123"}]

    # The agent checks pre-staged changes BEFORE calling the LLM
    result = coder_node(state)
    assert result["status"] == "failed"
    assert "denied" in result["error"] or "safety violation" in result["error"]

def test_coder_generates_valid_patch_via_llm(approved_state: dict):
    """Coder produces a valid patch when LLM provider succeeds."""
    import copy
    from app.agents.schemas import compute_plan_hash

    state = copy.deepcopy(approved_state)
    state["plan"]["requirements"] = [{"id": "REQ-1", "description": "desc", "acceptance_criterion": "crit"}]

    # Recompute hash and update approval to match new plan content
    new_hash = compute_plan_hash(state["plan"])
    state["human_approval"]["plan_hash"] = new_hash

    fake_patch = {
        "plan_version_id": "v1",
        "file_changes": [
            {
                "path": "src/calc.py",
                "change_type": "modify",
                "diff_text": "--- src/calc.py\n+++ src/calc.py\n@@ -10,1 +10,1 @@\n-return a / b\n+return a / b if b != 0 else 0",
                "requirement_ids": ["REQ-1"]
            }
        ],
        "tests_added": [],
        "deviation_log": [],
        "change_summary": "Fixed division by zero in src/calc.py"
    }

    with patch("app.agents.model_router.complete", return_value=json.dumps(fake_patch)):
        result = coder_node(state)
        assert result["status"] == "coding"
        assert result["code_changes"][0]["path"] == "src/calc.py"

def test_coder_handles_malformed_llm_json(approved_state: dict):
    """Coder handles cases where LLM returns unparseable JSON."""
    state = approved_state.copy()

    with patch("app.agents.model_router.complete", return_value="NOT JSON"):
        result = coder_node(state)
        assert result["status"] == "failed"
        assert "error" in result

def test_coder_handles_provider_failure(approved_state: dict):
    """Coder handles LLM provider exceptions gracefully."""
    state = approved_state.copy()
    state["strict_verification"] = True

    with patch("app.agents.model_router.complete", side_effect=Exception("API Down")):
        result = coder_node(state)
        assert result["status"] == "failed"
        assert "API Down" in result["error"]
