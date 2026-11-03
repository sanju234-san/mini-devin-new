"""Tests for app.config — settings loading, validation, and secrets."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.config import Settings, get_settings


class TestSettingsDefaults:
    """Settings should load with sensible defaults and no env vars set."""

    def test_defaults_without_env(self) -> None:
        """The app must start with an empty environment."""
        s = Settings(_env_file=None)
        assert s.ENVIRONMENT == "development"
        assert s.cors_origins == ["http://localhost:3000"]
        assert s.GROQ_API_KEY is None
        assert s.GOOGLE_AI_STUDIO_API_KEY is None
        assert s.HUGGINGFACE_API_TOKEN is None
        assert s.GITHUB_TOKEN is None
        assert s.GITHUB_WEBHOOK_SECRET is None
        assert s.LM_STUDIO_BASE_URL is None
        assert s.MAX_RETRY_ATTEMPTS == 3
        assert s.SANDBOX_BACKEND == "docker"
        assert s.ALLOW_UNSAFE_HOST_EXECUTION is False

    def test_docs_enabled_in_development(self) -> None:
        s = Settings(ENVIRONMENT="development", _env_file=None)
        assert s.docs_enabled is True

    def test_docs_disabled_in_production(self) -> None:
        s = Settings(ENVIRONMENT="production", _env_file=None)
        assert s.docs_enabled is False

    def test_docs_enabled_in_test(self) -> None:
        s = Settings(ENVIRONMENT="test", _env_file=None)
        assert s.docs_enabled is True

    def test_docs_explicit_override(self) -> None:
        s = Settings(ENVIRONMENT="production", ENABLE_DOCS=True, _env_file=None)
        assert s.docs_enabled is True


class TestCORSParsing:
    """CORS_ALLOWED_ORIGINS should handle comma-separated strings."""

    def test_single_origin(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "https://app.vercel.app")
        s = Settings(_env_file=None)
        assert s.cors_origins == ["https://app.vercel.app"]

    def test_multiple_origins(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(
            "CORS_ALLOWED_ORIGINS",
            "https://a.com, https://b.com , https://c.com",
        )
        s = Settings(_env_file=None)
        assert s.cors_origins == [
            "https://a.com",
            "https://b.com",
            "https://c.com",
        ]

    def test_stray_spaces_and_trailing_comma(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("CORS_ALLOWED_ORIGINS", " https://x.com , , ")
        s = Settings(_env_file=None)
        assert s.cors_origins == ["https://x.com"]

    def test_trailing_slash_stripped(self) -> None:
        s = Settings(
            CORS_ALLOWED_ORIGINS="https://a.com/, https://b.com/",
            _env_file=None,
        )
        assert s.cors_origins == ["https://a.com", "https://b.com"]

    def test_duplicates_removed_order_preserved(self) -> None:
        s = Settings(
            CORS_ALLOWED_ORIGINS="https://a.com, https://b.com, https://a.com",
            _env_file=None,
        )
        assert s.cors_origins == ["https://a.com", "https://b.com"]

    def test_wildcard_origin_raises(self) -> None:
        with pytest.raises(ValidationError, match="Wildcard"):
            Settings(CORS_ALLOWED_ORIGINS="*", _env_file=None)

    def test_schemeless_origin_raises(self) -> None:
        with pytest.raises(ValidationError, match="http://"):
            Settings(CORS_ALLOWED_ORIGINS="example.com", _env_file=None)


class TestInvalidEnvironment:
    """An invalid ENVIRONMENT value must fail fast with a validation error."""

    def test_invalid_environment_raises(self) -> None:
        with pytest.raises(ValidationError):
            Settings(ENVIRONMENT="staging", _env_file=None)


class TestMaxRetryAttempts:
    """MAX_RETRY_ATTEMPTS is bounded [1, 10]."""

    def test_zero_raises(self) -> None:
        with pytest.raises(ValidationError):
            Settings(MAX_RETRY_ATTEMPTS=0, _env_file=None)

    def test_eleven_raises(self) -> None:
        with pytest.raises(ValidationError):
            Settings(MAX_RETRY_ATTEMPTS=11, _env_file=None)

    def test_one_accepted(self) -> None:
        s = Settings(MAX_RETRY_ATTEMPTS=1, _env_file=None)
        assert s.MAX_RETRY_ATTEMPTS == 1

    def test_ten_accepted(self) -> None:
        s = Settings(MAX_RETRY_ATTEMPTS=10, _env_file=None)
        assert s.MAX_RETRY_ATTEMPTS == 10


class TestSandboxBackend:
    """SANDBOX_BACKEND must be 'docker' or 'e2b'."""

    def test_invalid_sandbox_backend_raises(self) -> None:
        with pytest.raises(ValidationError):
            Settings(SANDBOX_BACKEND="podman", _env_file=None)


class TestSecretsNotLeaked:
    """SecretStr fields must not appear in repr() or str()."""

    def test_secrets_masked_in_repr(self) -> None:
        s = Settings(
            GROQ_API_KEY="supersecret",
            GITHUB_TOKEN="ghp_abc123",
            _env_file=None,
        )
        text = repr(s)
        assert "supersecret" not in text
        assert "ghp_abc123" not in text

    def test_secrets_masked_in_str(self) -> None:
        s = Settings(
            GROQ_API_KEY="supersecret",
            GITHUB_TOKEN="ghp_abc123",
            _env_file=None,
        )
        text = str(s)
        assert "supersecret" not in text
        assert "ghp_abc123" not in text


class TestGetSettings:
    """The cached get_settings() function."""

    def test_returns_settings_instance(self) -> None:
        s = get_settings()
        assert isinstance(s, Settings)

    def test_cached(self) -> None:
        s1 = get_settings()
        s2 = get_settings()
        assert s1 is s2

    def test_cache_clear(self) -> None:
        s1 = get_settings()
        get_settings.cache_clear()
        s2 = get_settings()
        # New instance after cache clear.
        assert s1 is not s2


class TestLazyModuleAliases:
    """Module-level aliases served via __getattr__."""

    def test_github_token_empty_when_unset(self) -> None:
        import app.config as cfg
        get_settings.cache_clear()
        assert cfg.GITHUB_TOKEN == ""

    def test_github_token_returns_secret_value(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("GITHUB_TOKEN", "ghp_test123")
        get_settings.cache_clear()
        import app.config as cfg
        assert cfg.GITHUB_TOKEN == "ghp_test123"

    def test_from_import_works(self) -> None:
        from app.config import GITHUB_TOKEN  # noqa: F811
        assert isinstance(GITHUB_TOKEN, str)

    def test_max_retry_attempts_alias(self) -> None:
        import app.config as cfg
        get_settings.cache_clear()
        assert cfg.MAX_RETRY_ATTEMPTS == 3

    def test_sandbox_backend_alias(self) -> None:
        import app.config as cfg
        get_settings.cache_clear()
        assert cfg.SANDBOX_BACKEND == "docker"

    def test_unknown_attribute_raises(self) -> None:
        import app.config as cfg
        with pytest.raises(AttributeError):
            _ = cfg.NO_SUCH_ATTRIBUTE_XYZ


class TestSandboxSettings:
    """Verifies defaults, bounds, and aliases for sandbox settings."""

    def test_sandbox_defaults(self) -> None:
        s = Settings(_env_file=None)
        assert s.SANDBOX_IMAGE == "mini-devin-sandbox:py"
        assert s.SANDBOX_BROWSER_IMAGE == "mini-devin-sandbox:browser"
        assert s.SANDBOX_MEMORY_MB == 512
        assert s.SANDBOX_CPUS == 1.0
        assert s.SANDBOX_PIDS_LIMIT == 128
        assert s.SANDBOX_TIMEOUT_SECONDS == 300
        assert s.SANDBOX_MAX_CONCURRENT == 2
        assert s.SANDBOX_MAX_LOG_BYTES == 1048576
        assert s.SANDBOX_MAX_ARCHIVE_MB == 50

    def test_sandbox_memory_bounds(self) -> None:
        with pytest.raises(ValidationError):
            Settings(SANDBOX_MEMORY_MB=127, _env_file=None)
        with pytest.raises(ValidationError):
            Settings(SANDBOX_MEMORY_MB=4097, _env_file=None)
        s = Settings(SANDBOX_MEMORY_MB=1024, _env_file=None)
        assert s.SANDBOX_MEMORY_MB == 1024

    def test_sandbox_cpus_bounds(self) -> None:
        with pytest.raises(ValidationError):
            Settings(SANDBOX_CPUS=0.0, _env_file=None)
        with pytest.raises(ValidationError):
            Settings(SANDBOX_CPUS=4.1, _env_file=None)
        s = Settings(SANDBOX_CPUS=2.0, _env_file=None)
        assert s.SANDBOX_CPUS == 2.0

    def test_sandbox_pids_bounds(self) -> None:
        with pytest.raises(ValidationError):
            Settings(SANDBOX_PIDS_LIMIT=15, _env_file=None)
        with pytest.raises(ValidationError):
            Settings(SANDBOX_PIDS_LIMIT=1025, _env_file=None)
        s = Settings(SANDBOX_PIDS_LIMIT=256, _env_file=None)
        assert s.SANDBOX_PIDS_LIMIT == 256

    def test_sandbox_timeout_bounds(self) -> None:
        with pytest.raises(ValidationError):
            Settings(SANDBOX_TIMEOUT_SECONDS=9, _env_file=None)
        with pytest.raises(ValidationError):
            Settings(SANDBOX_TIMEOUT_SECONDS=1801, _env_file=None)
        s = Settings(SANDBOX_TIMEOUT_SECONDS=60, _env_file=None)
        assert s.SANDBOX_TIMEOUT_SECONDS == 60

    def test_sandbox_concurrent_bounds(self) -> None:
        with pytest.raises(ValidationError):
            Settings(SANDBOX_MAX_CONCURRENT=0, _env_file=None)
        with pytest.raises(ValidationError):
            Settings(SANDBOX_MAX_CONCURRENT=9, _env_file=None)
        s = Settings(SANDBOX_MAX_CONCURRENT=4, _env_file=None)
        assert s.SANDBOX_MAX_CONCURRENT == 4

    def test_sandbox_log_bytes_bounds(self) -> None:
        with pytest.raises(ValidationError):
            Settings(SANDBOX_MAX_LOG_BYTES=1023, _env_file=None)
        s = Settings(SANDBOX_MAX_LOG_BYTES=2048, _env_file=None)
        assert s.SANDBOX_MAX_LOG_BYTES == 2048

    def test_sandbox_archive_mb_bounds(self) -> None:
        with pytest.raises(ValidationError):
            Settings(SANDBOX_MAX_ARCHIVE_MB=0, _env_file=None)
        with pytest.raises(ValidationError):
            Settings(SANDBOX_MAX_ARCHIVE_MB=501, _env_file=None)
        s = Settings(SANDBOX_MAX_ARCHIVE_MB=100, _env_file=None)
        assert s.SANDBOX_MAX_ARCHIVE_MB == 100

    def test_sandbox_aliases(self) -> None:
        import app.config as cfg
        get_settings.cache_clear()
        assert cfg.SANDBOX_IMAGE == "mini-devin-sandbox:py"
        assert cfg.SANDBOX_MEMORY_MB == 512

