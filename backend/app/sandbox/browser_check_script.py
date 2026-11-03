"""Trusted browser verification script that executes INSIDE the sandbox container.

Plain-Language Guide for Beginners:
-----------------------------------
What does this script do?
When a developer or AI builds a web application (like a React or FastAPI app), unit tests
only check functions in isolation. To verify that the website actually runs and displays
properly, this script:
1. Launches the web server in the background (using `start_command`).
2. Waits until the server is ready by polling the local URL (e.g. http://127.0.0.1:3000).
3. Launches a headless Chromium browser with Chrome DevTools Protocol (CDP) enabled.
4. Visits up to 5 web pages, checks HTTP status codes, captures console errors,
   and takes full-page screenshots.
5. Cleanly terminates the web server and browser processes.
6. Emits the final diagnostics as a single machine-readable JSON line: `MINI_DEVIN_RESULT:{...}`.

Why CDP?
The Chrome DevTools Protocol allows Playwright to connect to an existing Chromium process
over a local debugging port (127.0.0.1:9222). By keeping CDP bound strictly to localhost
inside the container, it is never exposed to the outside world.

Why --no-sandbox for Chromium?
Chromium normally uses Linux SUID and user namespaces to sandbox its renderers. Inside a
Docker container that already drops all capabilities (`cap_drop=['ALL']`) and has a read-only
filesystem, Chromium's internal sandbox cannot initialize. Passing `--no-sandbox` allows
Chromium to run because the container itself is the hardened sandbox boundary.
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from typing import Any

RESULT_PREFIX = "MINI_DEVIN_RESULT:"


def _poll_url_ready(url: str, timeout_seconds: float) -> bool:
    """Poll the target URL until it returns a response or the timeout expires."""
    start = time.monotonic()
    req = urllib.request.Request(url, headers={"User-Agent": "Mini-Devin-HealthCheck/1.0"})

    while time.monotonic() - start < timeout_seconds:
        try:
            with urllib.request.urlopen(req, timeout=1.0) as resp:
                # Any HTTP response indicates the server is up
                if resp.status < 500:
                    return True
        except urllib.error.HTTPError as http_err:
            # 404 or other 4xx still means the server is running and answering
            if http_err.code < 500:
                return True
        except Exception:
            pass
        time.sleep(0.5)

    return False


def _read_tail(stream, max_bytes: int = 4096) -> str:
    """Read the tail of a stream up to max_bytes."""
    try:
        stream.seek(0, os.SEEK_END)
        size = stream.tell()
        stream.seek(max(0, size - max_bytes), os.SEEK_SET)
        data = stream.read()
        if isinstance(data, bytes):
            return data.decode("utf-8", errors="replace")
        return str(data)
    except Exception:
        return ""


def run_browser_verification(config_path: str) -> dict[str, Any]:
    """Execute browser verification according to the JSON config file.

    Imports Playwright lazily so importing this file outside the container does
    not fail if Playwright is not installed.
    """
    start_time = time.monotonic()

    # Load configuration JSON
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
    except Exception as exc:
        return {
            "ok": False,
            "error": f"Failed to load browser check config: {exc}",
            "duration_seconds": round(time.monotonic() - start_time, 3),
        }

    start_command = cfg.get("start_command", [])
    base_url = cfg.get("url", "http://127.0.0.1:8000")
    paths = cfg.get("paths", ["/"])
    readiness_timeout = float(cfg.get("readiness_timeout_seconds", 30))
    take_screenshot = bool(cfg.get("screenshot", True))
    record_video = bool(cfg.get("record_video", False))
    artifacts_dir = cfg.get("artifacts_dir", "/tmp/browser_artifacts")

    os.makedirs(artifacts_dir, exist_ok=True)

    http_status: dict[str, int | None] = {}
    console_errors: list[str] = []
    page_errors: list[str] = []
    failed_requests: list[str] = []
    page_title: str | None = None
    server_proc = None
    chromium_proc = None
    server_log_file = None

    try:
        # Step 1: Start the application server in its own process group
        # This ensures all spawned child processes can be terminated together
        server_log_path = "/tmp/server_output.log"
        server_log_file = open(server_log_path, "w+", encoding="utf-8", errors="replace")

        # Use preexec_fn=os.setsid on Unix to create a separate process group
        preexec = getattr(os, "setsid", None)
        server_proc = subprocess.Popen(
            start_command,
            cwd="/workspace",
            stdout=server_log_file,
            stderr=subprocess.STDOUT,
            preexec_fn=preexec,
        )

        # Step 2: Poll until base URL responds
        server_ready = _poll_url_ready(base_url, timeout_seconds=readiness_timeout)
        if not server_ready:
            server_tail = _read_tail(server_log_file, max_bytes=4096)
            return {
                "ok": False,
                "error": f"Web server failed to become ready at {base_url} within {readiness_timeout}s",
                "server_log_tail": server_tail,
                "duration_seconds": round(time.monotonic() - start_time, 3),
            }

        # Step 3: Lazy-import Playwright and launch Chromium with CDP
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            # Locate Playwright's bundled Chromium binary
            chromium_executable = p.chromium.executable_path

            # Launch Chromium with remote debugging port 9222 bound strictly to 127.0.0.1
            # Note: --no-sandbox is necessary inside containers where user namespaces and SUID are dropped
            cdp_port = 9222
            chrome_args = [
                chromium_executable,
                f"--remote-debugging-port={cdp_port}",
                "--no-sandbox",
                "--disable-gpu",
                "--disable-dev-shm-usage",
                "--headless=new",
            ]

            chromium_proc = subprocess.Popen(
                chrome_args,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                preexec_fn=preexec,
            )

            # Wait for CDP endpoint to respond
            cdp_url = f"http://127.0.0.1:{cdp_port}"
            cdp_ready = _poll_url_ready(f"{cdp_url}/json/version", timeout_seconds=15.0)
            if not cdp_ready:
                return {
                    "ok": False,
                    "error": "Chromium CDP endpoint failed to respond",
                    "duration_seconds": round(time.monotonic() - start_time, 3),
                }

            # Connect via CDP
            browser = p.chromium.connect_over_cdp(cdp_url)
            context = browser.contexts[0] if browser.contexts else browser.new_context()

            # Fixed 1280x720 standard viewport
            page = context.new_page()
            page.set_viewport_size({"width": 1280, "height": 720})

            # Event listeners to collect client-side diagnostic issues
            def on_console(msg):
                if msg.type == "error":
                    if len(console_errors) < 50:
                        console_errors.append(msg.text[:500])

            def on_page_error(exc):
                if len(page_errors) < 50:
                    page_errors.append(str(exc)[:500])

            def on_request_failed(req):
                if len(failed_requests) < 50:
                    failure = req.failure
                    failed_requests.append(f"{req.url}: {failure}"[:500])

            page.on("console", on_console)
            page.on("pageerror", on_page_error)
            page.on("requestfailed", on_request_failed)

            # Step 4: Visit routes and capture artifacts
            for idx, path in enumerate(paths, start=1):
                full_url = f"{base_url.rstrip('/')}{path}"
                try:
                    response = page.goto(full_url, wait_until="networkidle", timeout=15000)
                    http_status[path] = response.status if response else None
                    if page_title is None:
                        page_title = page.title()

                    if take_screenshot:
                        screenshot_path = os.path.join(artifacts_dir, f"screenshot_{idx}.png")
                        page.screenshot(path=screenshot_path, full_page=True)
                except Exception as nav_exc:
                    http_status[path] = None
                    if len(page_errors) < 50:
                        page_errors.append(f"Navigation error for {path}: {nav_exc}"[:500])

            browser.close()

        server_tail = _read_tail(server_log_file, max_bytes=4096)
        all_ok = all(
            status is not None and 200 <= status < 400 for status in http_status.values()
        ) and len(page_errors) == 0

        return {
            "ok": all_ok,
            "error": None if all_ok else "One or more pages returned an error or failed navigation",
            "http_status": http_status,
            "page_title": page_title,
            "console_errors": console_errors,
            "page_errors": page_errors,
            "failed_requests": failed_requests,
            "server_log_tail": server_tail,
            "video_supported": False,  # Playwright cannot record video over CDP connection
            "duration_seconds": round(time.monotonic() - start_time, 3),
        }

    except Exception as exc:
        server_tail = _read_tail(server_log_file, max_bytes=4096) if server_log_file else None
        return {
            "ok": False,
            "error": f"Browser verification encountered exception: {exc}",
            "http_status": http_status,
            "console_errors": console_errors,
            "page_errors": page_errors,
            "failed_requests": failed_requests,
            "server_log_tail": server_tail,
            "video_supported": False,
            "duration_seconds": round(time.monotonic() - start_time, 3),
        }

    finally:
        # Step 5: Always terminate server and Chromium process groups
        if chromium_proc and chromium_proc.poll() is None:
            try:
                if hasattr(os, "killpg"):
                    os.killpg(os.getpgid(chromium_proc.pid), signal.SIGTERM)
                else:
                    chromium_proc.terminate()
            except Exception:
                pass

        if server_proc and server_proc.poll() is None:
            try:
                if hasattr(os, "killpg"):
                    os.killpg(os.getpgid(server_proc.pid), signal.SIGTERM)
                else:
                    server_proc.terminate()
            except Exception:
                pass

        if server_log_file and not server_log_file.closed:
            try:
                server_log_file.close()
            except Exception:
                pass


def main() -> None:
    """Entry point when executed inside container."""
    config_path = sys.argv[1] if len(sys.argv) > 1 else "/tmp/browser_check_config.json"
    result = run_browser_verification(config_path)
    # Output the result JSON on a single prefixed line for host parsing
    print(f"{RESULT_PREFIX}{json.dumps(result)}")


if __name__ == "__main__":
    main()
