"""
Live Chainlit Browser Automation - Supported Issue -> Approval Stage Test.
"""

from __future__ import annotations

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


def test_supported_issue_flow(target_url: str = "http://localhost:8000"):
    art_dir = run_artifact_dir("chainlit_supported_issue_verification")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 800})

        logger.info("Opening %s", target_url)
        page.goto(target_url, wait_until="networkidle", timeout=15000)

        # Chat input
        input_selector = "textarea#chat-input, textarea, input[type='text']"
        page.wait_for_selector(input_selector, timeout=10000)
        textarea = page.query_selector(input_selector)

        # Clear and fill with high confidence bug_fix issue
        textarea.click()
        issue_text = "pallets/flask: flask.abort() behavioral change in debug mode\n\nIn flask 1.0, calling flask.abort(400) returns a 500 error in debug mode\n\n```python\nimport flask\nimport pytest\n"
        textarea.fill(issue_text)

        send_btn = page.query_selector("button#chat-send-button, button[type='submit'], button:has-text('Send')")
        if send_btn and send_btn.is_enabled():
            send_btn.click()
        else:
            page.keyboard.press("Enter")

        logger.info("Issue submitted. Polling for approval buttons or plan document...")
        time.sleep(2.0)

        # Wait for workflow execution
        for _ in range(25):
            body = page.inner_text("body") or ""
            if "Implementation Plan" in body or "Approve" in body or "Triage Agent Report" in body:
                logger.info("Found milestone text in body!")
                break
            time.sleep(1.0)

        # Take screenshot of the real executed state
        screen_path = art_dir / "01_chainlit_approval_state.png"
        page.screenshot(path=str(screen_path), full_page=True)
        logger.info("Saved screenshot to %s", screen_path)

        body_final = page.inner_text("body") or ""
        logger.info("Final body content snippet:\n%s", body_final[-800:])

        report = {
            "target_url": target_url,
            "issue_text": issue_text,
            "artifact_dir": str(art_dir),
            "screenshot": str(screen_path),
            "body_snippet": body_final[-1000:],
            "passed": ("Started Workflow Execution" in body_final),
        }
        with open(art_dir / "report.json", "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)

        browser.close()
        return report


if __name__ == "__main__":
    rep = test_supported_issue_flow()
    print(json.dumps(rep, indent=2))
