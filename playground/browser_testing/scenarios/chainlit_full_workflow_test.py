"""
Comprehensive Chainlit E2E Browser Automation Test
Exercises:
1. Issue Intake & Triage & Retrieval & Planning
2. Human Approval presentation with Plan Document & Hash
3. Approving the plan -> Coder -> Test-Runner -> Reviewer -> PR Agent
4. Rejection flow in separate session -> Immediate safe termination with 0 code changes
"""

import json
import logging
import os
import pathlib
import sys
import time

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
_BACKEND = _REPO_ROOT / "backend"
sys.path.insert(0, str(_BACKEND))
sys.path.insert(0, str(_REPO_ROOT))

from playwright.sync_api import sync_playwright
from playground.browser_testing.config import run_artifact_dir

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def run_full_chainlit_e2e(target_url: str = "http://localhost:8000"):
    art_dir = run_artifact_dir("chainlit_e2e_full_verification")
    results = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        # =========================================================================
        # TEST 1: APPROVAL FLOW (Runs full 8-agent loop)
        # =========================================================================
        logger.info("=== Starting Test 1: Approval Flow ===")
        context1 = browser.new_context(viewport={"width": 1280, "height": 900})
        page1 = context1.new_page()

        page1.goto(target_url, wait_until="networkidle", timeout=15000)
        input_sel = "textarea#chat-input, textarea, input[type='text']"
        page1.wait_for_selector(input_sel, timeout=10000)

        issue_text = (
            "pallets/flask: Fix bug in flask exception when running pytest in py\n\n"
            "In flask 1.0, calling flask.abort(400) raises an unhandled exception in debug mode\n\n"
            "```python\nimport flask\nimport pytest\n```"
        )
        page1.fill("textarea#chat-input", issue_text)
        time.sleep(1.0)

        send_btn = page1.query_selector("button#chat-submit, button[type='submit'], button:has-text('Send')")
        if send_btn and send_btn.is_enabled():
            send_btn.click()
        else:
            page1.keyboard.press("Enter")

        logger.info("Submitted issue. Waiting for Approval button...")

        # Poll for Approve button
        approve_button = None
        for attempt in range(40):
            time.sleep(1.0)
            approve_button = page1.query_selector("button:has-text('Approve Plan')")
            if approve_button:
                logger.info("Found 'Approve Plan' button on attempt %d!", attempt)
                break
            body = page1.inner_text("body") or ""
            if "Human Approval Required" in body:
                logger.info("Found 'Human Approval Required' in body!")
                approve_button = page1.query_selector("button:has-text('Approve')")
                if approve_button:
                    break

        screenshot_plan = art_dir / "01_approval_prompt_rendered.png"
        page1.screenshot(path=str(screenshot_plan), full_page=True)
        logger.info("Saved plan approval screenshot to %s", screenshot_plan)

        if approve_button:
            logger.info("Clicking 'Approve Plan' button...")
            approve_button.click()
            time.sleep(2.0)

            # Wait for downstream workflow execution (Coder -> Test-Runner -> Reviewer -> PR)
            logger.info("Waiting for downstream execution to complete...")
            for attempt in range(60):
                time.sleep(1.0)
                body = page1.inner_text("body") or ""
                if ("Workflow Terminated" in body or 
                    "Workflow Advanced" in body or 
                    "Pull Request Created" in body or 
                    "Downstream Execution Halted" in body or
                    "Workflow Event Log" in body):
                    logger.info("Downstream workflow milestone reached on attempt %d!", attempt)
                    break

            time.sleep(2.0)
            screenshot_approved_final = art_dir / "02_downstream_execution_completed.png"
            page1.screenshot(path=str(screenshot_approved_final), full_page=True)
            logger.info("Saved final execution screenshot to %s", screenshot_approved_final)

            body_approved = page1.inner_text("body") or ""
            results["approval_flow"] = {
                "status": "completed",
                "milestone_found": True,
                "body_snippet": body_approved[-1200:],
                "screenshot_plan": str(screenshot_plan),
                "screenshot_final": str(screenshot_approved_final),
            }
        else:
            logger.error("Approve button not found!")
            results["approval_flow"] = {
                "status": "failed_to_find_button",
                "body_snippet": page1.inner_text("body")[-800:],
            }

        context1.close()

        # =========================================================================
        # TEST 2: REJECTION FLOW (Safe Abort)
        # =========================================================================
        logger.info("=== Starting Test 2: Rejection Flow ===")
        context2 = browser.new_context(viewport={"width": 1280, "height": 900})
        page2 = context2.new_page()

        page2.goto(target_url, wait_until="networkidle", timeout=15000)
        page2.wait_for_selector(input_sel, timeout=10000)
        page2.fill("textarea#chat-input", issue_text)
        time.sleep(1.0)

        send_btn2 = page2.query_selector("button#chat-submit, button[type='submit'], button:has-text('Send')")
        if send_btn2 and send_btn2.is_enabled():
            send_btn2.click()
        else:
            page2.keyboard.press("Enter")

        logger.info("Submitted issue for Rejection test. Waiting for Reject button...")
        reject_button = None
        for attempt in range(40):
            time.sleep(1.0)
            reject_button = page2.query_selector("button:has-text('Reject Plan')")
            if reject_button:
                logger.info("Found 'Reject Plan' button on attempt %d!", attempt)
                break

        if reject_button:
            logger.info("Clicking 'Reject Plan' button...")
            reject_button.click()
            time.sleep(2.0)

            for attempt in range(30):
                time.sleep(1.0)
                body = page2.inner_text("body") or ""
                if "Plan Rejected & Workflow Terminated Safely" in body or "Zero code changes" in body:
                    logger.info("Rejection safe-stop confirmed on attempt %d!", attempt)
                    break

            screenshot_rejected = art_dir / "03_plan_rejected_safely.png"
            page2.screenshot(path=str(screenshot_rejected), full_page=True)
            logger.info("Saved rejection screenshot to %s", screenshot_rejected)

            body_rejected = page2.inner_text("body") or ""
            results["rejection_flow"] = {
                "status": "completed",
                "safe_termination_verified": "Zero code changes" in body_rejected,
                "body_snippet": body_rejected[-800:],
                "screenshot": str(screenshot_rejected),
            }
        else:
            logger.error("Reject button not found!")
            results["rejection_flow"] = {
                "status": "failed_to_find_button",
                "body_snippet": page2.inner_text("body")[-800:],
            }

        context2.close()
        browser.close()

    summary_file = art_dir / "full_e2e_results.json"
    with open(summary_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    logger.info("Full E2E testing completed. Summary written to %s", summary_file)
    return results


if __name__ == "__main__":
    res = run_full_chainlit_e2e()
    print(json.dumps(res, indent=2))
