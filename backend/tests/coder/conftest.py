import pytest
import socket
import os
from unittest.mock import patch

@pytest.fixture(autouse=True)
def block_network_access(monkeypatch):
    # Block socket connections to non-loopback addresses
    original_connect = socket.socket.connect

    def mocked_connect(self, address):
        host = address[0]
        if host != "127.0.0.1" and host != "localhost":
            test_name = pytest.current_test_name if hasattr(pytest, 'current_test_name') else "unknown test"
            raise RuntimeError(f"Network access blocked in {test_name}: attempt to connect to {host}")
        return original_connect(self, address)

    monkeypatch.setattr(socket.socket, "connect", mocked_connect)

    # Set offline flags
    monkeypatch.setenv("HF_HUB_OFFLINE", "1")
    monkeypatch.setenv("TRANSFORMERS_OFFLINE", "1")

    # Clear API keys
    for key in ["GROQ_API_KEY", "GEMINI_API_KEY", "HF_TOKEN"]:
        monkeypatch.delenv(key, raising=False)
