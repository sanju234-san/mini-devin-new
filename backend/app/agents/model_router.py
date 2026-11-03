"""
Per-agent, task-difficulty-based model routing.

Not every agent needs an LLM call. This module decides, for a given
agent/task, whether to use a lightweight classifier, a static-analysis
pass, or escalate to an LLM -- and if an LLM is needed, which provider
in the hybrid routing chain (Groq -> Google AI Studio/Gemini ->
Hugging Face Inference API) to use.

See llm_provider_client.py (integrations/) for the actual multi-provider
HTTP client and 429 retry/fallback handling this module routes into.
"""

from enum import Enum

from app.integrations.llm_provider_client import complete as provider_complete


class ModelTier(str, Enum):
    CLASSIFIER = "classifier"       # e.g. Triage Agent's DistilBERT model
    EMBEDDING = "embedding"         # e.g. Retrieval Agent's sentence-transformer
    STATIC_ANALYSIS = "static"      # e.g. Reviewer Agent's first-pass linter
    LLM = "llm"                     # Planner / Coder / escalated Debugger & Reviewer / PR


AGENT_MODEL_TIER = {
    "triage": ModelTier.CLASSIFIER,
    "retrieval": ModelTier.EMBEDDING,
    "planner": ModelTier.LLM,
    "coder": ModelTier.LLM,
    "debugger_first_pass": ModelTier.CLASSIFIER,
    "debugger_escalated": ModelTier.LLM,
    "reviewer_first_pass": ModelTier.STATIC_ANALYSIS,
    "reviewer_escalated": ModelTier.LLM,
    "pr": ModelTier.LLM,
}


def route(agent_name: str):
    """Return the ModelTier a given agent/stage should use."""
    return AGENT_MODEL_TIER.get(agent_name, ModelTier.LLM)


def complete(prompt: str, agent_name: str = ""):
    """Route LLM completion requests through the provider chain."""
    return provider_complete(prompt, agent_name=agent_name)


AGENT_MODEL_TIER = {
    "triage": ModelTier.CLASSIFIER,
    "retrieval": ModelTier.EMBEDDING,
    "planner": ModelTier.LLM,
    "coder": ModelTier.LLM,
    "debugger_first_pass": ModelTier.CLASSIFIER,
    "debugger_escalated": ModelTier.LLM,
    "reviewer_first_pass": ModelTier.STATIC_ANALYSIS,
    "reviewer_escalated": ModelTier.LLM,
    "pr": ModelTier.LLM,
}


def route(agent_name: str):
    """Return the ModelTier a given agent/stage should use."""
    return AGENT_MODEL_TIER.get(agent_name, ModelTier.LLM)
