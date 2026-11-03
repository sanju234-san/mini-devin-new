# `playground/` — Browser Testing for Mini-Devin

This directory adds **autonomous live-website testing** to Mini-Devin, implemented through Mini-Devin's own agent workflow — not as an external demo.

---

## Architecture

```
playground/
├── browser_testing/
│   ├── config.py            # URL allowlist, artifact dirs, Playwright knobs
│   ├── engine.py            # BrowserTestRunner — core Playwright engine
│   └── scenarios/
│       └── web_scenarios.py # Concrete test scenarios (4 scenarios)
├── tests/
│   └── test_browser_testing.py  # Pytest suite (offline + live)
├── run_browser_tests.py     # CLI entry point
└── README.md

backend/app/agents/test_runner/
├── agent.py                 # Updated: calls browser_runner when browser_test_url set
└── browser_runner.py        # Agent-facing integration shim
```

## How Mini-Devin Uses This

1. A workflow run's `AgentState` includes `browser_test_url` (e.g. `"http://localhost:8000"`).
2. `test_runner_node` detects this field and calls `browser_runner.run_browser_tests_for_agent()`.
3. The Playwright engine opens a real Chromium browser, navigates pages, interacts with UI, and saves screenshots.
4. The result (a `BrowserTestReport`) is stored as `browser_test_results` in `AgentState` and emitted as a `browser_tests_completed` event for Chainlit rendering.

This is **not** a disconnected demo — it is wired directly into the LangGraph Test Runner node.

---

## Scenarios

| Scenario | Description |
|---|---|
| `availability` | Navigate to root, verify page loads, check body content and console |
| `issue_intake` | Locate textarea, type an issue, submit, verify acknowledgement |
| `workflow_status` | Check workflow stage keywords are visible |
| `unavailable_url` | Deliberate failure: confirms non-listening port is honestly reported as FAIL |

---

## Running

### Prerequisites

```bash
# Playwright + Chromium (already installed in this project)
python -m playwright install chromium
```

### CLI (recommended)

```bash
# Against a running Chainlit console (start it first):
#   cd chainlit_console && chainlit run app.py -w
python playground/run_browser_tests.py --url http://localhost:8000

# Specific scenarios only:
python playground/run_browser_tests.py --url http://localhost:8000 \
    --scenarios availability workflow_status

# Failure scenario (no live server required):
python playground/run_browser_tests.py --scenarios unavailable_url

# Headed browser (visible window):
BROWSER_HEADLESS=0 python playground/run_browser_tests.py --url http://localhost:8000

# Full JSON report to stdout:
python playground/run_browser_tests.py --url http://localhost:8000 --json
```

### Pytest suite

```bash
# All tests (offline + real browser):
python -m pytest playground/tests/test_browser_testing.py -v

# Skip real-browser tests (CI without Chromium):
PLAYWRIGHT_SKIP_BROWSER_TESTS=1 python -m pytest playground/tests/test_browser_testing.py -v
```

---

## Artifacts

Each run writes evidence to:
```
playground/browser_testing/artifacts/<run_id>/
  00_PASS_Navigate_to_root_page.png
  02_PASS_Body_has_visible_text.png
  03_FAIL_Submit_issue.png          ← if submission step fails
  report.json                       ← full structured report
```

`report.json` format:
```json
{
  "run_id": "20261024T185000_a1b2c3",
  "target_url": "http://localhost:8000",
  "status": "passed",
  "total_steps": 4,
  "passed_steps": 4,
  "failed_steps": 0,
  "steps": [
    {
      "step_index": 0,
      "step_name": "Navigate to root page",
      "url": "http://localhost:8000/",
      "timestamp": "...",
      "expected": "Page loads without navigation error",
      "observed": "Assertion passed.",
      "passed": true,
      "screenshot_path": ".../00_PASS_Navigate_to_root_page.png"
    }
  ]
}
```

---

## Security Constraints

| Constraint | How enforced |
|---|---|
| URL allowlist | `config.py::is_permitted()` — only `localhost` / `127.0.0.1` by default |
| Secret scrubbing | `engine.py::_scrub()` — regex patterns remove tokens/keys before storage |
| No production data | Tests navigate and observe only; form submission targets local test server |
| No credential storage | Browser context created fresh each run with no stored cookies/auth |
| No auto-merge | Browser tests are evidence only; PR creation remains in `pr_node` |

---

## Status

| Capability | Status |
|---|---|
| Playwright Chromium launch | ✅ IMPLEMENTED |
| URL allowlist enforcement | ✅ IMPLEMENTED |
| Screenshot capture per step | ✅ IMPLEMENTED |
| Console error recording | ✅ IMPLEMENTED |
| Failed network request recording | ✅ IMPLEMENTED |
| Secret scrubbing | ✅ IMPLEMENTED |
| Structured JSON report | ✅ IMPLEMENTED |
| AgentState `browser_test_url` field | ✅ IMPLEMENTED |
| test_runner_node browser branch | ✅ IMPLEMENTED |
| Offline pytest suite (no live server) | ✅ IMPLEMENTED |
| Live browser pytest (inline HTTP server) | ✅ IMPLEMENTED |
| Chainlit issue intake scenario | ✅ IMPLEMENTED (requires running server) |
| Live Chainlit verification | ⚠️ NOT RUN — no running server at test time |
| Docker sandbox integration | 🔴 BLOCKED — teammate-owned stub |
| GitHub PR creation | 🔴 BLOCKED — teammate-owned stub |
