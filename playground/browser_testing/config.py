"""
Browser Testing Configuration for Mini-Devin.

Explicit, declarative configuration for all browser-test runs.
No URLs are invented here; all targets must be set by the caller or via
the environment variables listed below.

Environment variables:
  MINI_DEVIN_TEST_URL   – target web application URL (required for live run)
  BROWSER_HEADLESS      – "1" (default) or "0" for headed mode
  BROWSER_SLOW_MO_MS    – Playwright slow-motion delay in ms (default 0)
  BROWSER_TIMEOUT_MS    – default navigation/action timeout (default 10000)
  SCREENSHOT_DIR        – override artifact output directory
"""

from __future__ import annotations

import datetime
import os
import pathlib
import uuid

# ── Target URL ──────────────────────────────────────────────────────────────
# Explicitly configured.  Never fabricated or guessed.
TARGET_URL: str | None = os.environ.get("MINI_DEVIN_TEST_URL")

# ── Browser options ─────────────────────────────────────────────────────────
HEADLESS: bool = os.environ.get("BROWSER_HEADLESS", "1") == "1"
SLOW_MO_MS: int = int(os.environ.get("BROWSER_SLOW_MO_MS", "0"))
TIMEOUT_MS: int = int(os.environ.get("BROWSER_TIMEOUT_MS", "10000"))

# ── Artifact directory ───────────────────────────────────────────────────────
_DEFAULT_ARTIFACT_ROOT = pathlib.Path(__file__).parent / "artifacts"
ARTIFACT_ROOT: pathlib.Path = pathlib.Path(
    os.environ.get("SCREENSHOT_DIR", str(_DEFAULT_ARTIFACT_ROOT))
)


def run_artifact_dir(run_id: str | None = None) -> pathlib.Path:
    """Return a run-specific subdirectory, creating it on first call."""
    rid = run_id or datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%S") + "_" + uuid.uuid4().hex[:6]
    d = ARTIFACT_ROOT / rid
    d.mkdir(parents=True, exist_ok=True)
    return d


# ── Permitted URL prefix allowlist ───────────────────────────────────────────
# Browser tests may only run against URLs that start with one of these prefixes.
# Extend this list for other approved test environments.
PERMITTED_URL_PREFIXES: list[str] = [
    "http://localhost",
    "http://127.0.0.1",
    "https://localhost",
    "https://127.0.0.1",
    # Add approved staging/test domains here, e.g.:
    # "https://staging.mini-devin.example.com",
]


def is_permitted(url: str) -> bool:
    """Return True only when *url* starts with an approved prefix."""
    return any(url.startswith(prefix) for prefix in PERMITTED_URL_PREFIXES)
