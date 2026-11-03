#!/usr/bin/env python3
"""
Mini-Devin Browser Test CLI Entry Point.

Usage
-----
  # Run all standard scenarios against the Chainlit console (if running):
  python playground/run_browser_tests.py --url http://localhost:8000

  # Run specific scenarios only:
  python playground/run_browser_tests.py --url http://localhost:8000 \\
      --scenarios availability workflow_status

  # Run failure scenario only (no live URL required):
  python playground/run_browser_tests.py --scenarios unavailable_url

  # Headed browser (visible window):
  BROWSER_HEADLESS=0 python playground/run_browser_tests.py --url http://localhost:8000

Environment Variables
---------------------
  MINI_DEVIN_TEST_URL   – target URL (overridden by --url flag)
  BROWSER_HEADLESS      – "1" headless (default), "0" headed
  BROWSER_SLOW_MO_MS    – slow-motion delay in milliseconds
  BROWSER_TIMEOUT_MS    – action/navigation timeout in milliseconds

Output
------
  All screenshots and report.json are written to:
    playground/browser_testing/artifacts/<run_id>/

  Exit code 0 = all executed steps passed (or only BLOCKED/NOT_RUN).
  Exit code 1 = one or more steps failed or an unexpected error occurred.

Important
---------
  This CLI exercises Mini-Devin's OWN browser automation capability,
  implemented in playground/browser_testing/ and wired into the Test Runner
  agent via backend/app/agents/test_runner/browser_runner.py.
  It is NOT a demo of an external tool — it IS the Mini-Devin capability.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import pathlib

# Ensure repo root is on sys.path
_REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT))
# Add backend/ so that `from app.agents...` resolves
_BACKEND = _REPO_ROOT / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s – %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("mini_devin.browser_cli")


VALID_SCENARIOS = ["availability", "issue_intake", "workflow_status", "unavailable_url"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Mini-Devin browser test runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--url",
        metavar="URL",
        default=os.environ.get("MINI_DEVIN_TEST_URL"),
        help="Target URL (must be localhost/127.0.0.1). Overrides MINI_DEVIN_TEST_URL.",
    )
    parser.add_argument(
        "--scenarios",
        nargs="+",
        metavar="SCENARIO",
        choices=VALID_SCENARIOS,
        default=None,
        help=f"Scenarios to run (default: all). Choices: {VALID_SCENARIOS}",
    )
    parser.add_argument(
        "--run-id",
        metavar="ID",
        default=None,
        help="Optional run identifier for artifact directory naming.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Print the full JSON report to stdout in addition to logging.",
    )
    args = parser.parse_args(argv)

    from playground.browser_testing.config import is_permitted
    from app.agents.test_runner.browser_runner import run_browser_tests_for_agent

    url: str | None = args.url
    scenarios: list[str] | None = args.scenarios

    # If no URL provided AND scenarios include live ones → will produce BLOCKED
    if not url and scenarios and set(scenarios) - {"unavailable_url"}:
        logger.warning(
            "No target URL provided. Live scenarios will produce BLOCKED reports. "
            "Set --url or MINI_DEVIN_TEST_URL to run against a real server."
        )

    report = run_browser_tests_for_agent(
        target_url=url,
        run_id=args.run_id,
        scenarios=scenarios,
    )

    # ── Pretty-print summary ──────────────────────────────────────────────────
    status = report.get("status", "unknown")
    total = report.get("total_steps", 0)
    passed = report.get("passed_steps", 0)
    failed = report.get("failed_steps", 0)
    artifact_dir = report.get("artifact_dir", "")
    report_path = report.get("report_path", "")
    blocking = report.get("blocking_reason", "")

    print("\n" + "=" * 70)
    print("  Mini-Devin Browser Test Report")
    print("=" * 70)
    print(f"  Status       : {status.upper()}")
    print(f"  Target URL   : {report.get('target_url', 'N/A')}")
    print(f"  Run ID       : {report.get('run_id', 'N/A')}")
    print(f"  Total steps  : {total}")
    print(f"  Passed       : {passed}")
    print(f"  Failed       : {failed}")
    if blocking:
        print(f"  Blocked (why): {blocking}")
    if artifact_dir:
        print(f"  Artifacts    : {artifact_dir}")
    if report_path:
        print(f"  Report JSON  : {report_path}")

    steps: list[dict] = report.get("steps", [])
    if steps:
        print("\n  Steps:")
        for s in steps:
            sym = "[PASS]" if s.get("passed") else "[FAIL]"
            print(f"    [{s.get('step_index', '?')}] {sym} {s.get('step_name', '')} -- {s.get('observed', '')[:80]}")
            if s.get("screenshot_path"):
                print(f"         [IMG] {s['screenshot_path']}")
    print("=" * 70 + "\n")

    if args.json_output:
        print(json.dumps(report, indent=2, default=str))

    # Exit code
    if status in ("passed",):
        return 0
    if status in ("blocked", "not_run"):
        # Not a test failure — prerequisites missing but nothing ran incorrectly
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
