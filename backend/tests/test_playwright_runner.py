"""Unit tests for app.sandbox.playwright_runner — parsing, artifact handling, and URL security."""

from __future__ import annotations

import io
import json
import tarfile
import pytest
from pydantic import ValidationError

from app.sandbox.models import BrowserCheck, BrowserCheckResult
from app.sandbox.playwright_runner import (
    PNG_MAGIC,
    parse_browser_check_output,
    run_browser_check,
)
from tests.fake_docker import FakeContainer, FakeDockerClient


class TestBrowserCheckModelSecurity:
    """Verifies BrowserCheck model validation rules."""

    def test_valid_localhost_url_accepted(self) -> None:
        check = BrowserCheck(
            start_command=["python", "-m", "http.server", "8000"],
            url="http://127.0.0.1:8000",
            paths=["/"],
        )
        assert check.url == "http://127.0.0.1:8000"

    def test_external_host_rejected(self) -> None:
        with pytest.raises(ValidationError, match="127.0.0.1 or localhost"):
            BrowserCheck(
                start_command=["python", "app.py"],
                url="http://example.com:8080",
            )

    def test_userinfo_ssrf_bypass_rejected(self) -> None:
        with pytest.raises(ValidationError, match="userinfo"):
            BrowserCheck(
                start_command=["python", "app.py"],
                url="http://127.0.0.1@evil.com:8080",
            )

    def test_missing_port_rejected(self) -> None:
        with pytest.raises(ValidationError, match="explicit port number"):
            BrowserCheck(
                start_command=["python", "app.py"],
                url="http://localhost",
            )

    def test_bad_port_out_of_range_rejected(self) -> None:
        with pytest.raises(ValidationError, match="port must be between 1024 and 65535"):
            BrowserCheck(
                start_command=["python", "app.py"],
                url="http://127.0.0.1:80",  # privileged port < 1024
            )

    def test_too_many_paths_rejected(self) -> None:
        with pytest.raises(ValidationError, match="between 1 and 5"):
            BrowserCheck(
                start_command=["python", "app.py"],
                url="http://127.0.0.1:3000",
                paths=["/1", "/2", "/3", "/4", "/5", "/6"],
            )

    def test_path_must_start_with_slash(self) -> None:
        with pytest.raises(ValidationError, match="starting with '/'"):
            BrowserCheck(
                start_command=["python", "app.py"],
                url="http://127.0.0.1:3000",
                paths=["about"],
            )


class TestParseBrowserCheckOutput:
    """Verifies output parsing from the container script."""

    def test_valid_result_parsed(self) -> None:
        payload = {
            "ok": True,
            "error": None,
            "http_status": {"/": 200},
            "page_title": "Mini-Devin Test",
            "console_errors": [],
            "page_errors": [],
            "failed_requests": [],
            "server_log_tail": "Started server",
            "video_supported": False,
            "duration_seconds": 1.25,
        }
        stdout = f"Log line 1\nLog line 2\nMINI_DEVIN_RESULT:{json.dumps(payload)}\n"
        res = parse_browser_check_output(stdout)

        assert res.ok is True
        assert res.page_title == "Mini-Devin Test"
        assert res.http_status == {"/": 200}

    def test_missing_result_line_handled(self) -> None:
        stdout = "Some random crash occurred\nTraceback...\n"
        res = parse_browser_check_output(stdout)

        assert res.ok is False
        assert "did not produce a MINI_DEVIN_RESULT line" in (res.error or "")

    def test_oversized_payload_rejected(self) -> None:
        huge = "x" * 70000
        stdout = f"MINI_DEVIN_RESULT:{huge}\n"
        res = parse_browser_check_output(stdout)

        assert res.ok is False
        assert "exceeded 64 KiB limit" in (res.error or "")

    def test_garbage_json_handled(self) -> None:
        stdout = "MINI_DEVIN_RESULT:{not valid json\n"
        res = parse_browser_check_output(stdout)

        assert res.ok is False
        assert "Failed to validate browser check result" in (res.error or "")


class TestRunBrowserCheckArtifacts:
    """Verifies artifact retrieval, magic byte checks, and backend naming."""

    def test_png_artifacts_retrieved_and_named(self) -> None:
        async def _run():
            fake_client = FakeDockerClient(ping_ok=True)
            container = FakeContainer("test_c", {})

            # Setup valid script result
            valid_result = {
                "ok": True,
                "error": None,
                "http_status": {"/": 200},
                "page_title": "Demo",
                "console_errors": [],
                "page_errors": [],
                "failed_requests": [],
                "server_log_tail": None,
                "video_supported": False,
                "duration_seconds": 0.5,
            }
            output_line = f"MINI_DEVIN_RESULT:{json.dumps(valid_result)}\n".encode("utf-8")
            container.custom_exec_responses["python /tmp/browser_check_script.py"] = (
                0,
                output_line,
            )

            # Setup mock screenshot archive in container
            valid_png = PNG_MAGIC + b"\x00\x00\x00\rIHDR" + b"dummy-png-data"
            buf = io.BytesIO()
            with tarfile.open(fileobj=buf, mode="w") as tar:
                info = tarfile.TarInfo(name="container_unsafe_name.png")
                info.size = len(valid_png)
                tar.addfile(info, fileobj=io.BytesIO(valid_png))
            container.archive_responses["/tmp/browser_artifacts"] = buf.getvalue()

            check = BrowserCheck(
                start_command=["python", "server.py"],
                url="http://127.0.0.1:8080",
                screenshot=True,
            )

            res, artifacts = await run_browser_check(container, check, fake_client)

            assert res.ok is True
            assert len(artifacts) == 1
            art = artifacts[0]
            # Assert backend-generated name, NOT container_unsafe_name.png
            assert art.name == "screenshot_1.png"
            assert art.type == "screenshot"
            assert art.content_type == "image/png"
            assert art.data.startswith(PNG_MAGIC)

        import asyncio
        asyncio.run(_run())
