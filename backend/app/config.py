from __future__ import annotations

from dotenv import load_dotenv
load_dotenv()

import functools
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed, validated application settings.

    Every field maps to an environment variable of the same name.
    Optional secrets default to ``None`` so the app starts without them.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        # Extra env vars (e.g. MLFLOW_TRACKING_URI) must not crash startup.
        extra="ignore",
    )

    # ── Environment ──────────────────────────────────────────────────
    ENVIRONMENT: Literal["development", "production", "test"] = "development"

    # ── CORS ─────────────────────────────────────────────────────────
    # Stored as a raw comma-separated string so pydantic-settings does not
    # attempt JSON-decoding the env var.  Use the ``cors_origins`` property
    # to get the parsed list.
    CORS_ALLOWED_ORIGINS: str = "http://localhost:3000"

    @field_validator("CORS_ALLOWED_ORIGINS", mode="before")
    @classmethod
    def _validate_cors_origins(cls, v: object) -> str:
        """Normalise and validate the comma-separated origins string.

        - Strips whitespace and trailing ``/`` from each entry.
        - Drops empty entries.
        - De-duplicates while preserving order.
        - Rejects ``"*"`` (wildcard origins are never allowed).
        - Rejects entries that do not start with ``http://`` or ``https://``.
        """
        if not isinstance(v, str):
            return v  # type: ignore[return-value]

        seen: set[str] = set()
        cleaned: list[str] = []
        for raw in v.split(","):
            entry = raw.strip().rstrip("/")
            if not entry:
                continue
            if entry == "*":
                raise ValueError(
                    "Wildcard origin '*' is not allowed in CORS_ALLOWED_ORIGINS"
                )
            if not (entry.startswith("http://") or entry.startswith("https://")):
                raise ValueError(
                    f"CORS origin must start with http:// or https://, got: {entry!r}"
                )
            if entry not in seen:
                seen.add(entry)
                cleaned.append(entry)
        return ",".join(cleaned)

    @property
    def cors_origins(self) -> list[str]:
        """Parse ``CORS_ALLOWED_ORIGINS`` into a deduplicated list."""
        return [
            origin.strip()
            for origin in self.CORS_ALLOWED_ORIGINS.split(",")
            if origin.strip()
        ]

    # ── API docs exposure ────────────────────────────────────────────
    ENABLE_DOCS: bool | None = None  # resolved in property below

    @property
    def docs_enabled(self) -> bool:
        """Docs are on by default except in production."""
        if self.ENABLE_DOCS is not None:
            return self.ENABLE_DOCS
        return self.ENVIRONMENT != "production"

    # ── Application Info & Version ───────────────────────────────────
    APP_NAME: str = "Mini-Devin"
    APP_VERSION: str = "0.1.0"
    APP_DESCRIPTION: str = "Autonomous GitHub Issue-to-Pull-Request Multi-Agent System"

    # ── LLM API Keys & Secrets ───────────────────────────────────────
    GROQ_API_KEY: SecretStr | None = None
    GOOGLE_AI_STUDIO_API_KEY: SecretStr | None = None
    HUGGINGFACE_API_TOKEN: SecretStr | None = None
    ANTHROPIC_API_KEY: SecretStr | None = None
    OPENAI_API_KEY: SecretStr | None = None
    TAVILY_API_KEY: SecretStr | None = None
    GITHUB_TOKEN: SecretStr | None = None
    GITHUB_WEBHOOK_SECRET: SecretStr | None = None

    # ── Model Configurations ─────────────────────────────────────────
    OLLAMA_MODEL: str = "qwen2.5-coder:7b"
    GROQ_MODEL: str = "openai/gpt-oss-120b"
    GROQ_DEFAULT_MODEL: str = "openai/gpt-oss-120b"
    GROQ_FALLBACK_MODEL: str = "openai/gpt-oss-20b"
    GEMINI_MODEL: str = "gemini-1.5-pro"
    HF_MODEL: str = "mistralai/Mistral-7B-Instruct-v0.3"
    ANTHROPIC_MODEL: str | None = None
    OPENAI_MODEL: str | None = None
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"

    # ── External Services, Endpoints & Databases ─────────────────────
    LM_STUDIO_BASE_URL: str | None = None
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    QDRANT_URL: str | None = "http://localhost:6333"
    QDRANT_API_KEY: SecretStr | None = None
    MONGO_URI: str = "mongodb://localhost:27017"
    MONGO_PASS: SecretStr | None = None
    MONGO_DB_NAME: str = "mini_devin"

    # ── Chunking & Retrieval ─────────────────────────────────────────
    CHUNK_SIZE: int = 50
    CHUNK_OVERLAP: int = 10
    RETRIEVAL_CHAR_BUDGET: int = 30000

    # ── Agent Behaviour & Fallbacks ──────────────────────────────────
    MAX_RETRY_ATTEMPTS: int = Field(default=3, ge=1, le=10)
    SANDBOX_BACKEND: Literal["docker", "e2b", "codespaces"] = "docker"
    ALLOW_UNSAFE_HOST_EXECUTION: bool = False
    ALLOW_DETERMINISTIC_FALLBACK: bool = False
    MINI_DEVIN_USE_CLOUD_CODESPACES: bool = False

    # ── GitHub MCP Server Configuration ──────────────────────────────
    GITHUB_MCP_PACKAGE: str = "@modelcontextprotocol/server-github@2025.4.8"
    GITHUB_MCP_TIMEOUT: float = 60.0

    # ── MLflow & Observability ───────────────────────────────────────
    MLFLOW_TRACKING_URI: str = "http://localhost:5000"
    MINI_DEVIN_MLFLOW_EXPERIMENT: str = "mini-devin-runs"
    MINI_DEVIN_ENABLE_LOCAL_MLFLOW: bool = False

    # ── Triage ML Classifier Thresholds ──────────────────────────────
    MINI_DEVIN_MIN_CONFIDENCE: float = 0.55
    MINI_DEVIN_MIN_MARGIN: float = 0.12
    MINI_DEVIN_TITLE_WEIGHT: int = 3
    MINI_DEVIN_TRIAGE_MAX_BODY_CHARS: int = 800

    # ── Sandbox execution settings (ephemeral containers) ────────────
    SANDBOX_IMAGE: str = "mini-devin-sandbox:py"
    SANDBOX_BROWSER_IMAGE: str = "mini-devin-sandbox:browser"
    SANDBOX_MEMORY_MB: int = Field(default=512, ge=128, le=4096)
    SANDBOX_CPUS: float = Field(default=1.0, gt=0.0, le=4.0)
    SANDBOX_PIDS_LIMIT: int = Field(default=128, ge=16, le=1024)
    SANDBOX_TIMEOUT_SECONDS: int = Field(default=300, ge=10, le=1800)
    SANDBOX_MAX_CONCURRENT: int = Field(default=2, ge=1, le=8)
    SANDBOX_MAX_LOG_BYTES: int = Field(default=1048576, ge=1024)
    SANDBOX_MAX_ARCHIVE_MB: int = Field(default=50, ge=1, le=500)


@functools.lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached :class:`Settings` instance.

    In tests, either override via ``app.dependency_overrides[get_settings]``
    or clear the cache with ``get_settings.cache_clear()`` after setting
    environment variables.
    """
    return Settings()


# ── Lazy backward-compatible module-level aliases ────────────────────
# Existing agent / retrieval code may import names directly from app.config.
# These are served lazily via __getattr__ so that:
# (a) importing app.config does not read the environment eagerly and
# (b) cache_clear() is respected on subsequent access.

_SECRET_ALIASES = frozenset({
    "GITHUB_TOKEN",
    "GITHUB_WEBHOOK_SECRET",
    "GROQ_API_KEY",
    "GOOGLE_AI_STUDIO_API_KEY",
    "HUGGINGFACE_API_TOKEN",
    "ANTHROPIC_API_KEY",
    "OPENAI_API_KEY",
    "TAVILY_API_KEY",
    "QDRANT_API_KEY",
    "MONGO_PASS",
})

_PLAIN_ALIASES = frozenset({
    "APP_NAME",
    "APP_VERSION",
    "APP_DESCRIPTION",
    "ENVIRONMENT",
    "CORS_ALLOWED_ORIGINS",
    "ENABLE_DOCS",
    "OLLAMA_MODEL",
    "GROQ_MODEL",
    "GROQ_DEFAULT_MODEL",
    "GROQ_FALLBACK_MODEL",
    "GEMINI_MODEL",
    "HF_MODEL",
    "ANTHROPIC_MODEL",
    "OPENAI_MODEL",
    "EMBEDDING_MODEL",
    "LM_STUDIO_BASE_URL",
    "OLLAMA_BASE_URL",
    "QDRANT_URL",
    "MONGO_URI",
    "MONGO_DB_NAME",
    "CHUNK_SIZE",
    "CHUNK_OVERLAP",
    "RETRIEVAL_CHAR_BUDGET",
    "MAX_RETRY_ATTEMPTS",
    "SANDBOX_BACKEND",
    "ALLOW_UNSAFE_HOST_EXECUTION",
    "ALLOW_DETERMINISTIC_FALLBACK",
    "MINI_DEVIN_USE_CLOUD_CODESPACES",
    "GITHUB_MCP_PACKAGE",
    "GITHUB_MCP_TIMEOUT",
    "MLFLOW_TRACKING_URI",
    "MINI_DEVIN_MLFLOW_EXPERIMENT",
    "MINI_DEVIN_ENABLE_LOCAL_MLFLOW",
    "MINI_DEVIN_MIN_CONFIDENCE",
    "MINI_DEVIN_MIN_MARGIN",
    "MINI_DEVIN_TITLE_WEIGHT",
    "MINI_DEVIN_TRIAGE_MAX_BODY_CHARS",
    "SANDBOX_IMAGE",
    "SANDBOX_BROWSER_IMAGE",
    "SANDBOX_MEMORY_MB",
    "SANDBOX_CPUS",
    "SANDBOX_PIDS_LIMIT",
    "SANDBOX_TIMEOUT_SECONDS",
    "SANDBOX_MAX_CONCURRENT",
    "SANDBOX_MAX_LOG_BYTES",
    "SANDBOX_MAX_ARCHIVE_MB",
})


def __getattr__(name: str) -> object:
    if name in _SECRET_ALIASES:
        s = get_settings()
        secret = getattr(s, name)
        return secret.get_secret_value() if secret else ""
    if name in _PLAIN_ALIASES:
        return getattr(get_settings(), name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
