import pytest
from unittest.mock import MagicMock, patch
from app.integrations.llm_provider_client import complete, AllProvidersExhaustedError

def test_complete_groq_success():
    """Verify primary provider (Groq) success."""
    with patch("app.integrations.llm_provider_client.Groq") as mock_groq:
        mock_instance = mock_groq.return_value
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="Groq Success"))]
        mock_instance.chat.completions.create.return_value = mock_response

        # Ensure we have a key for the check
        with patch("app.integrations.llm_provider_client.GROQ_API_KEY", "fake_key"):
            assert complete("Hello") == "Groq Success"

def test_complete_fallback_to_gemini():
    """Verify fallback from Groq to Gemini."""
    with patch("app.integrations.llm_provider_client.Groq") as mock_groq, \
         patch("app.integrations.llm_provider_client.genai") as mock_genai:

        # Groq fails
        mock_groq.return_value.chat.completions.create.side_effect = Exception("Groq Error")

        # Gemini succeeds
        mock_model = MagicMock()
        mock_model.generate_content.return_value = MagicMock(text="Gemini Success")
        mock_genai.GenerativeModel.return_value = mock_model

        with patch("app.integrations.llm_provider_client.GROQ_API_KEY", "key1"), \
             patch("app.integrations.llm_provider_client.GOOGLE_AI_STUDIO_API_KEY", "key2"):
            assert complete("Hello") == "Gemini Success"

def test_complete_all_exhausted():
    """Verify exception when all providers fail."""
    with patch("app.integrations.llm_provider_client._call_groq") as m1, \
         patch("app.integrations.llm_provider_client._call_gemini") as m2, \
         patch("app.integrations.llm_provider_client._call_huggingface") as m3:

        m1.side_effect = Exception("Error 1")
        m2.side_effect = Exception("Error 2")
        m3.side_effect = Exception("Error 3")

        with pytest.raises(AllProvidersExhaustedError):
            complete("Hello")

def test_complete_missing_keys():
    """Verify that missing keys trigger fallback."""
    with patch("app.integrations.llm_provider_client.GROQ_API_KEY", None), \
         patch("app.integrations.llm_provider_client.GOOGLE_AI_STUDIO_API_KEY", None), \
         patch("app.integrations.llm_provider_client.HUGGINGFACE_API_TOKEN", None):

        with pytest.raises(AllProvidersExhaustedError):
            complete("Hello")

def test_complete_huggingface_success():
    """Verify final fallback (HuggingFace) success."""
    with patch("app.integrations.llm_provider_client.Groq") as mock_groq, \
         patch("app.integrations.llm_provider_client.genai") as mock_genai, \
         patch("app.integrations.llm_provider_client.InferenceClient") as mock_hf:

        mock_groq.return_value.chat.completions.create.side_effect = Exception("Fail")
        mock_genai.GenerativeModel.return_value.generate_content.side_effect = Exception("Fail")

        mock_hf.return_value.text_generation.return_value = "HF Success"

        with patch("app.integrations.llm_provider_client.GROQ_API_KEY", "k1"), \
             patch("app.integrations.llm_provider_client.GOOGLE_AI_STUDIO_API_KEY", "k2"), \
             patch("app.integrations.llm_provider_client.HUGGINGFACE_API_TOKEN", "k3"):
            assert complete("Hello") == "HF Success"
