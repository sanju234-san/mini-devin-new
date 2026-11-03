"""Host-side runner for Playwright live browser verification inside the sandbox container.

Plain-Language Guide for Beginners:
-----------------------------------
This module coordinates the browser verification workflow from the host server:
1. Prepares the browser verification configuration as a JSON file.
2. Injects the trusted `browser_check_script.py` and the JSON config into the container.
3. Executes the script inside the container using the non-root 'sandbox' user (uid 1000).
4. Captures and parses the machine-readable result line (`MINI_DEVIN_RESULT:...`).
5. Extracts generated screenshot files using Docker's `get_archive` API.
6. Validates the PNG binary headers (magic bytes) and enforces strict size limits.
7. Wraps each screenshot in a `SandboxArtifact` using safe, backend-generated names
   (e.g. `screenshot_1.png`). Container paths are NEVER trusted directly.
"""

from __future__ import annotations

import asyncio
import io
import json
import logging
import os
import tarfile
import time
from typing import Any

from app.sandbox.models import (
    BrowserCheck,
    BrowserCheckResult,
    SandboxArtifact,
)

logger = logging.getLogger(__name__)

RESULT_PREFIX = "MINI_DEVIN_RESULT:"
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
MAX_FILE_BYTES = 5 * 1024 * 1024  # 5 MiB per screenshot
MAX_TOTAL_BYTES = 15 * 1024 * 1024  # 15 MiB total for all screenshots
MAX_FILES = 5


def _create_tar_with_files(files: dict[str, tuple[bytes, int]]) -> bytes:
    """Pack in-memory files into an uncompressed tar stream.

    Args:
        files: Mapping of filename -> (bytes_content, file_mode)
    """
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tar:
        for fname, (content, mode) in files.items():
            info = tarfile.TarInfo(name=fname)
            info.size = len(content)
            info.mtime = int(time.time())
            info.mode = mode
            info.uid = 1000
            info.gid = 1000
            info.uname = "sandbox"
            info.gname = "sandbox"
            tar.addfile(info, fileobj=io.BytesIO(content))
    buf.seek(0)
    return buf.getvalue()


def _get_script_content() -> bytes:
    """Read the local browser_check_script.py content."""
    script_path = os.path.join(os.path.dirname(__file__), "browser_check_script.py")
    with open(script_path, "rb") as f:
        return f.read()


def parse_browser_check_output(stdout_text: str) -> BrowserCheckResult:
    """Parse and validate the MINI_DEVIN_RESULT line from script stdout."""
    result_line: str | None = None

    for line in stdout_text.splitlines():
        trimmed = line.strip()
        if trimmed.startswith(RESULT_PREFIX):
            result_line = trimmed[len(RESULT_PREFIX) :].strip()
            break

    if result_line is None:
        return BrowserCheckResult(
            ok=False,
            error="Browser check did not produce a MINI_DEVIN_RESULT line",
            server_log_tail=stdout_text[-4096:] if stdout_text else None,
        )

    # Protect against memory exhaustion: cap parsed line at 64 KiB
    if len(result_line) > 65536:
        return BrowserCheckResult(
            ok=False,
            error="Browser check result payload exceeded 64 KiB limit",
        )

    try:
        raw_dict = json.loads(result_line)
        return BrowserCheckResult.model_validate(raw_dict)
    except Exception as exc:
        return BrowserCheckResult(
            ok=False,
            error=f"Failed to validate browser check result schema: {exc}",
        )


async def run_browser_check(
    container: Any,
    check: BrowserCheck,
    client: Any,
) -> tuple[BrowserCheckResult, list[SandboxArtifact]]:
    """Execute live browser verification inside container and retrieve screenshot artifacts."""
    config_data = {
        "start_command": check.start_command,
        "url": check.url,
        "paths": check.paths,
        "readiness_timeout_seconds": check.readiness_timeout_seconds,
        "screenshot": check.screenshot,
        "record_video": check.record_video,
        "artifacts_dir": "/tmp/browser_artifacts",
    }
    config_bytes = json.dumps(config_data).encode("utf-8")
    script_bytes = _get_script_content()

    # Step 1: Upload script (mode 0o555 read-only/executable) and config to /tmp
    upload_tar = _create_tar_with_files(
        {
            "browser_check_script.py": (script_bytes, 0o555),
            "browser_check_config.json": (config_bytes, 0o644),
        }
    )
    await asyncio.to_thread(container.put_archive, "/tmp", upload_tar)

    # Step 2: Execute script as non-root sandbox user
    cmd = ["python", "/tmp/browser_check_script.py", "/tmp/browser_check_config.json"]

    def _run_exec():
        res = container.exec_run(
            cmd,
            workdir="/workspace",
            user="1000:1000",
            environment={"HOME": "/tmp", "PATH": "/usr/local/bin:/usr/bin:/bin"},
        )
        out = res.output
        if isinstance(out, bytes):
            return res.exit_code, out.decode("utf-8", errors="replace")
        return res.exit_code, str(out)

    try:
        exit_code, output_text = await asyncio.to_thread(_run_exec)
    except Exception as exec_err:
        logger.warning("Browser check exec failed: %s", exec_err)
        return (
            BrowserCheckResult(ok=False, error=f"Container execution error: {exec_err}"),
            [],
        )

    # Step 3: Parse result
    result = parse_browser_check_output(output_text)

    # Step 4: Retrieve screenshot artifacts from container
    artifacts: list[SandboxArtifact] = []
    if check.screenshot:
        try:

            def _get_archive():
                try:
                    bits, _ = container.get_archive("/tmp/browser_artifacts")
                    stream = io.BytesIO()
                    for chunk in bits:
                        stream.write(chunk)
                    stream.seek(0)
                    return stream
                except Exception:
                    return None

            archive_stream = await asyncio.to_thread(_get_archive)
            if archive_stream is not None:
                total_bytes = 0
                file_count = 0

                with tarfile.open(fileobj=archive_stream, mode="r") as tar:
                    for member in tar.getmembers():
                        if not member.isreg():
                            continue
                        if file_count >= MAX_FILES:
                            break

                        f = tar.extractfile(member)
                        if f is None:
                            continue
                        data = f.read()

                        # Validate PNG magic bytes and limits
                        if len(data) <= MAX_FILE_BYTES and data.startswith(PNG_MAGIC):
                            if total_bytes + len(data) <= MAX_TOTAL_BYTES:
                                file_count += 1
                                total_bytes += len(data)
                                # Backend-generated safe name: NEVER use container paths or member.name
                                artifact_name = f"screenshot_{file_count}.png"
                                artifacts.append(
                                    SandboxArtifact(
                                        name=artifact_name,
                                        type="screenshot",
                                        content_type="image/png",
                                        size_bytes=len(data),
                                        data=data,
                                    )
                                )
        except Exception as art_err:
            logger.warning("Failed to collect screenshot artifacts: %s", art_err)

    return result, artifacts
