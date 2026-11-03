"""
Multi-provider LLM client with graceful fallback.

Routing chain: Groq (free tier, low-latency) primary for Planner/Coder/
Debugger -> Google AI Studio (Gemini) on rate-limit -> Hugging Face
Inference API as an open-source-model fallback.
"""

from __future__ import annotations

import logging
import os
import re
import time
from typing import Any

from groq import Groq
from google import genai
from huggingface_hub import InferenceClient

from app.config import GROQ_API_KEY, GOOGLE_AI_STUDIO_API_KEY, HUGGINGFACE_API_TOKEN

logger = logging.getLogger(__name__)

def _redact_keys(text: str) -> str:
    s = str(text)
    for env_var in ("GROQ_API_KEY", "GOOGLE_AI_STUDIO_API_KEY", "HUGGINGFACE_API_TOKEN"):
        val = os.getenv(env_var)
        if val and len(val.strip()) > 4:
            s = s.replace(val, "[REDACTED]").replace(val.strip(), "[REDACTED]")
    for val in (GROQ_API_KEY, GOOGLE_AI_STUDIO_API_KEY, HUGGINGFACE_API_TOKEN):
        if val and len(str(val).strip()) > 4:
            s = s.replace(str(val), "[REDACTED]").replace(str(val).strip(), "[REDACTED]")
    s = re.sub(r'(gsk_|AIzaSy|hf_)[A-Za-z0-9_-]+', '[REDACTED]', s)
    return s

PROVIDER_CHAIN = ["groq", "gemini", "huggingface"]

class AllProvidersExhaustedError(Exception):
    """Raised when all configured LLM providers fail or are rate-limited."""
    def __init__(self, message: str, provider_errors: dict[str, str] | None = None):
        super().__init__(message)
        self.provider_errors = provider_errors or {}

def _call_groq(prompt: str) -> str:
    groq_key = os.getenv("GROQ_API_KEY") or GROQ_API_KEY
    if not groq_key:
        raise RuntimeError("GROQ_API_KEY not configured")
    client = Groq(api_key=groq_key)
    model_name = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
    try:
        chat_completion = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model=model_name,
        )
        return chat_completion.choices[0].message.content
    except Exception as exc:
        exc_str = str(exc).lower()
        if any(term in exc_str for term in ("decommissioned", "not found", "404", "model_not_found", "does not exist")):
            # Fallback to next accessible model
            fallback_model = os.getenv("GROQ_FALLBACK_MODEL", "openai/gpt-oss-20b")
            chat_completion = client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model=fallback_model,
            )
            return chat_completion.choices[0].message.content
        raise

def _call_gemini(prompt: str) -> str:
    gemini_key = os.getenv("GOOGLE_AI_STUDIO_API_KEY") or GOOGLE_AI_STUDIO_API_KEY
    if not gemini_key:
        raise RuntimeError("GOOGLE_AI_STUDIO_API_KEY not configured")
    # genai.configure(api_key=gemini_key)
    model_name = os.getenv("GEMINI_MODEL", "gemini-flash-latest")
    # model = genai.GenerativeModel(model_name)
    client = genai.Client(api_key=gemini_key)

    response = client.models.generate_content(
        model = model_name,
        contents=prompt,
    )
    return response.text

def _call_huggingface(prompt: str) -> str:
    hf_token = os.getenv("HUGGINGFACE_API_TOKEN") or HUGGINGFACE_API_TOKEN
    if not hf_token:
        raise RuntimeError("HUGGINGFACE_API_TOKEN not configured")
    client = InferenceClient(token=hf_token)
    model_name = os.getenv("HF_MODEL", "mistralai/Mistral-7B-Instruct-v0.3")
    try:
        chat_resp = client.chat_completion(
            messages=[{"role": "user", "content": prompt}],
            model=model_name,
            max_tokens=2048,
        )
        return chat_resp.choices[0].message.content
    except Exception:
        return client.text_generation(prompt, model=model_name, max_new_tokens=2048)

def _call_ollama(prompt: str) -> str:
    import httpx
    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
    model_name = os.getenv("OLLAMA_MODEL", "qwen2.5-coder:7b")
    timeout_sec = float(os.getenv("OLLAMA_TIMEOUT", "300.0"))
    num_ctx = int(os.getenv("OLLAMA_NUM_CTX", "8192"))
    # Call Ollama native generate endpoint
    resp = httpx.post(
        f"{base_url}/api/generate",
        json={
            "model": model_name,
            "prompt": prompt,
            "stream": False,
            "options": {
                "num_ctx": num_ctx,
                "temperature": 0.1,
            },
        },
        timeout=timeout_sec,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"Ollama returned HTTP {resp.status_code}: {resp.text}")
    data = resp.json()
    return data.get("response", "")

def complete(prompt: str, agent_name: str = ""):
    """
    Try each provider in PROVIDER_CHAIN in order, falling back on 429s or server errors.
    """
    provider_map = {
        "ollama": _call_ollama,
        "groq": _call_groq,
        "gemini": _call_gemini,
        "huggingface": _call_huggingface,
    }

    provider_errors: dict[str, str] = {}
    last_exc = None
    chain = [p.strip() for p in os.getenv("LLM_PROVIDER_CHAIN", ",".join(PROVIDER_CHAIN)).split(",") if p.strip()]
    for provider in chain:
        if provider not in provider_map:
            continue
        try:
            logger.info("Attempting LLM completion via %s [agent=%s]", provider, agent_name)
            return provider_map[provider](prompt)
        except Exception as e:
            # We catch all exceptions to ensure fallback happens.
            # In a production system, we'd specifically check for 429s/5xxs.
            clean_err = _redact_keys(str(e))
            logger.warning("Provider %s failed: %s. Trying next fallback...", provider, clean_err)
            provider_errors[provider] = clean_err
            last_exc = e
            continue

    msg = f"All available LLM providers failed or are misconfigured. Details: {provider_errors}"
    if last_exc:
        raise AllProvidersExhaustedError(msg, provider_errors=provider_errors) from last_exc
    raise AllProvidersExhaustedError(msg, provider_errors=provider_errors)
