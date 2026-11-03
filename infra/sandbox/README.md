# Mini-Devin Sandbox Container Images

This directory defines the Docker images used by Mini-Devin to safely run untrusted code and perform automated browser verifications.

## Images Overview

1. `mini-devin-sandbox:py` (`Dockerfile`):
   - Ephemeral, hardened execution environment for standard Python unit testing.
   - Pinned to `python:3.12-slim`.
   - Includes `git` and `pytest`.
   - Runs strictly as the non-root `sandbox` user (uid 1000).

2. `mini-devin-sandbox:browser` (`Dockerfile.browser`):
   - Extends `mini-devin-sandbox:py` with headless Chromium and Playwright.
   - Drives live website verifications over Chrome DevTools Protocol (CDP).
   - Keeps browser assets isolated in `/ms-playwright`.

---

## Building the Images (Windows PowerShell)

Run these commands from the repository root:

```powershell
# 1. Build the base Python sandbox image
docker build -t mini-devin-sandbox:py infra/sandbox

# 2. Build the browser verification sandbox image
docker build -f infra/sandbox/Dockerfile.browser -t mini-devin-sandbox:browser infra/sandbox
```

---

## Running Integration Tests

Default pytest test suites run completely offline without needing a Docker daemon (using fast in-memory fakes).

To run real end-to-end container integration tests:

```powershell
# Ensure Docker Desktop / daemon is running, then:
$env:RUN_DOCKER_TESTS = "1"
python -m pytest backend/tests/test_sandbox_integration.py -v

# To also run real browser integration tests (requires mini-devin-sandbox:browser):
$env:RUN_BROWSER_TESTS = "1"
python -m pytest backend/tests/test_sandbox_integration.py -v
```
