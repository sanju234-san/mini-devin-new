import pytest
from unittest.mock import patch
import inspect

def test_provider_guard_blocks_direct_client_call():
    """Verify direct call to llm_provider_client.complete is blocked."""
    from app.integrations import llm_provider_client
    with pytest.raises(RuntimeError) as excinfo:
        llm_provider_client.complete("Direct call")
    assert "Unexpected LLM provider call" in str(excinfo.value)
    assert "test_llm_guard.py" in str(excinfo.value)

def test_provider_guard_blocks_router_call():
    """Verify call through model_router.complete is blocked."""
    from app.agents import model_router
    with pytest.raises(RuntimeError) as excinfo:
        model_router.complete("Router call")
    assert "Unexpected LLM provider call" in str(excinfo.value)
    assert "test_llm_guard.py" in str(excinfo.value)

def test_explicit_mock_still_works():
    """Verify that explicit mocks bypass the guard."""
    from app.integrations import llm_provider_client
    with patch("app.integrations.llm_provider_client.complete", return_value="Mocked Response"):
        res = llm_provider_client.complete("Hello")
        assert res == "Mocked Response"
