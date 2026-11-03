"""Pure, unit-testable security validation helpers for the Mini-Devin sandbox.

Plain-Language Guide for Beginners:
-----------------------------------
When code arrives from external sources (such as an AI model generating a patch or a
user uploading a repository zip), we must NEVER blindly trust the file paths or
archive contents.

Malicious attacks include:
1. Path Traversal: A patch trying to write to `../../etc/passwd` or `/root/.ssh/id_rsa`.
2. Zip-Bombs: A tiny 1 MB archive that expands into 50 GB to crash the machine.
3. Git directory poisoning: Trying to overwrite `.git/hooks` so host scripts execute evil code.
4. Setuid / Special devices: Creating device nodes or setuid binaries to escalate privileges.
5. Command Injection: Passing unescaped shell strings instead of discrete argv argument lists.

This module validates and sanitizes all inputs BEFORE any container is created.
"""

from __future__ import annotations

import io
import os
import posixpath
import re
import tarfile

# Maximum allowed patch diff size: 1 MiB
MAX_DIFF_BYTES = 1024 * 1024

# Regex patterns for diff inspection
_GIT_DIFF_HEADER_RE = re.compile(r"^diff\s+--git\s+(?:a/(.*?))\s+(?:b/(.*?))$")
_TRIPLE_MINUS_RE = re.compile(r"^---\s+(?:a/)?(\S+)")
_TRIPLE_PLUS_RE = re.compile(r"^\+\+\+\s+(?:b/)?(\S+)")
_RENAME_FROM_RE = re.compile(r"^rename\s+from\s+(\S+)")
_RENAME_TO_RE = re.compile(r"^rename\s+to\s+(\S+)")
_COPY_FROM_RE = re.compile(r"^copy\s+from\s+(\S+)")
_COPY_TO_RE = re.compile(r"^copy\s+to\s+(\S+)")
_NEW_FILE_MODE_RE = re.compile(r"^new\s+file\s+mode\s+(\d+)")
_OLD_MODE_RE = re.compile(r"^old\s+mode\s+(\d+)")
_NEW_MODE_RE = re.compile(r"^new\s+mode\s+(\d+)")


def _check_safe_relative_path(path: str, context: str) -> None:
    """Ensure a path is relative, normalized, and cannot escape the working directory."""
    if not path or path == "/dev/null":
        return

    # Reject Windows drive letters (e.g. C:)
    if len(path) > 1 and path[1] == ":":
        raise ValueError(f"Absolute path with drive letter rejected in {context}: {path!r}")

    # Reject absolute Unix paths
    if path.startswith("/"):
        raise ValueError(f"Absolute path rejected in {context}: {path!r}")

    # Reject backslashes (Windows path separator tricks)
    if "\\" in path:
        raise ValueError(f"Path with backslashes rejected in {context}: {path!r}")

    # Reject NUL bytes
    if "\0" in path:
        raise ValueError(f"Path containing NUL byte rejected in {context}")

    # Normalize POSIX path and check for traversal
    norm = posixpath.normpath(path)
    parts = norm.split("/")

    if norm == ".." or norm.startswith("../") or ".." in parts:
        raise ValueError(f"Path traversal '..' rejected in {context}: {path!r}")

    # Reject references into .git
    for part in parts:
        if part.lower() == ".git":
            raise ValueError(f"Reference to .git directory rejected in {context}: {path!r}")


def validate_diff(diff: str | None) -> None:
    """Validate a unified diff string for security before passing it to git apply.

    Rejects:
    - None or empty diffs (no-op, but if provided must be safe)
    - Diffs larger than 1 MiB
    - Diffs containing NUL bytes
    - Binary patches ('GIT binary patch')
    - Symlink mode changes ('120000')
    - Any path with '..', leading '/', backslashes, or '.git/'
    - Rename / copy targets pointing outside the repository tree

    Raises:
        ValueError: if the diff fails any safety check.
    """
    if diff is None or not diff.strip():
        return

    diff_bytes = diff.encode("utf-8", errors="ignore")
    if len(diff_bytes) > MAX_DIFF_BYTES:
        raise ValueError(
            f"Diff exceeds maximum size of 1 MiB ({len(diff_bytes)} bytes > {MAX_DIFF_BYTES})"
        )

    if "\0" in diff:
        raise ValueError("Diff contains forbidden NUL (\\0) byte")

    lines = diff.splitlines()

    for line in lines:
        stripped = line.strip()

        # Reject binary patches
        if stripped.startswith("GIT binary patch"):
            raise ValueError("Binary diff patches are forbidden")

        # Check for symlink file modes
        # In Git, mode 120000 represents a symbolic link
        m_new_mode = _NEW_FILE_MODE_RE.match(stripped)
        if m_new_mode and m_new_mode.group(1) == "120000":
            raise ValueError("Creation of symbolic links (mode 120000) is forbidden in diff")

        m_nm = _NEW_MODE_RE.match(stripped)
        if m_nm and m_nm.group(1) == "120000":
            raise ValueError("Changing mode to symbolic link (120000) is forbidden in diff")

        # Check diff --git header
        m_git = _GIT_DIFF_HEADER_RE.match(stripped)
        if m_git:
            _check_safe_relative_path(m_git.group(1), "diff header")
            _check_safe_relative_path(m_git.group(2), "diff header")
            continue

        # Check --- header
        m_minus = _TRIPLE_MINUS_RE.match(stripped)
        if m_minus:
            _check_safe_relative_path(m_minus.group(1), "--- header")
            continue

        # Check +++ header
        m_plus = _TRIPLE_PLUS_RE.match(stripped)
        if m_plus:
            _check_safe_relative_path(m_plus.group(1), "+++ header")
            continue

        # Check rename / copy headers
        m_ren_from = _RENAME_FROM_RE.match(stripped)
        if m_ren_from:
            _check_safe_relative_path(m_ren_from.group(1), "rename from")
            continue

        m_ren_to = _RENAME_TO_RE.match(stripped)
        if m_ren_to:
            _check_safe_relative_path(m_ren_to.group(1), "rename to")
            continue

        m_copy_from = _COPY_FROM_RE.match(stripped)
        if m_copy_from:
            _check_safe_relative_path(m_copy_from.group(1), "copy from")
            continue

        m_copy_to = _COPY_TO_RE.match(stripped)
        if m_copy_to:
            _check_safe_relative_path(m_copy_to.group(1), "copy to")
            continue


def normalize_repo_archive(archive_bytes: bytes, max_archive_mb: int = 50) -> bytes:
    """Inspect, validate, and normalize a tar/tar.gz archive in memory.

    Protection against:
    - Oversized archive uploads (> max_archive_mb)
    - Zip-bomb decompression explosions (> 4x max_archive_mb uncompressed)
    - File count exhaustion (> 20,000 members)
    - Absolute file paths or traversal paths ('..')
    - Device nodes, named pipes (FIFOs), sockets
    - Symlinks / hardlinks pointing outside the extraction tree
    - SUID / SGID permission bits

    Normalization:
    - Re-packs all safe members into a clean uncompressed TAR
    - Forces uid=1000, gid=1000, uname='sandbox', gname='sandbox'
    - Clears SUID/SGID/sticky bits by masking modes to 0o777

    Returns:
        bytes: The sanitized, re-packed uncompressed tar stream.

    Raises:
        ValueError: if the archive violates safety rules or is malformed.
    """
    max_bytes = max_archive_mb * 1024 * 1024
    if len(archive_bytes) > max_bytes:
        raise ValueError(
            f"Repository archive exceeds maximum size of {max_archive_mb} MB ({len(archive_bytes)} bytes)"
        )

    if not archive_bytes:
        raise ValueError("Repository archive is empty")

    in_buffer = io.BytesIO(archive_bytes)
    out_buffer = io.BytesIO()

    try:
        in_tar = tarfile.open(fileobj=in_buffer, mode="r:*")
    except Exception as exc:
        raise ValueError(f"Failed to read repository archive as tar/tar.gz: {exc}") from exc

    total_uncompressed_bytes = 0
    max_uncompressed_bytes = 4 * max_bytes
    max_members = 20000
    member_count = 0

    with in_tar:
        members = in_tar.getmembers()
        if len(members) > max_members:
            raise ValueError(
                f"Archive contains too many members ({len(members)} > {max_members})"
            )

        with tarfile.open(fileobj=out_buffer, mode="w") as out_tar:
            for member in members:
                member_count += 1
                name = member.name.replace("\\", "/")

                # Path traversal check on member name
                _check_safe_relative_path(name, f"archive member '{name}'")

                # Reject special device files, FIFOs, etc.
                if member.ischr() or member.isblk() or member.isfifo() or member.isdev():
                    raise ValueError(f"Forbidden special device / FIFO member in archive: {name!r}")

                # Check link targets for traversal or absolute escapes
                if member.issym() or member.islnk():
                    target = member.linkname.replace("\\", "/")
                    if target.startswith("/"):
                        raise ValueError(f"Forbidden absolute link target in archive: {target!r}")
                    # Normalize target relative to member's parent directory
                    target_dir = posixpath.dirname(name)
                    combined = posixpath.normpath(posixpath.join(target_dir, target))
                    if combined == ".." or combined.startswith("../"):
                        raise ValueError(
                            f"Forbidden link escaping archive tree: {name} -> {target}"
                        )

                # Zip bomb guard: sum uncompressed size
                total_uncompressed_bytes += member.size
                if total_uncompressed_bytes > max_uncompressed_bytes:
                    raise ValueError(
                        f"Archive uncompressed size exceeds safety ceiling of {max_uncompressed_bytes // (1024*1024)} MB (zip-bomb guard)"
                    )

                # Read data for regular files
                file_obj = None
                if member.isreg():
                    file_obj = in_tar.extractfile(member)

                # Sanitize permissions and ownership:
                # Force uid=1000, gid=1000 ("sandbox" non-root user)
                # Mask out setuid (0o4000), setgid (0o2000), and sticky (0o1000) bits
                sanitized_info = tarfile.TarInfo(name=name)
                sanitized_info.type = member.type
                sanitized_info.size = member.size
                sanitized_info.mtime = member.mtime
                sanitized_info.mode = member.mode & 0o777
                sanitized_info.uid = 1000
                sanitized_info.gid = 1000
                sanitized_info.uname = "sandbox"
                sanitized_info.gname = "sandbox"
                sanitized_info.linkname = member.linkname

                if file_obj is not None:
                    out_tar.addfile(sanitized_info, fileobj=file_obj)
                else:
                    out_tar.addfile(sanitized_info)

    out_buffer.seek(0)
    return out_buffer.getvalue()


def validate_command(cmd: list[str] | None, field_name: str = "command") -> list[str] | None:
    """Validate that a command is an argv list meeting strict length and encoding limits.

    Rules:
    - Returns None if cmd is None.
    - Must be a non-empty list of strings.
    - Maximum 32 arguments.
    - Each argument must be 1..1000 characters.
    - No NUL (\\0) bytes.
    """
    if cmd is None:
        return None
    if not isinstance(cmd, list) or len(cmd) == 0:
        raise ValueError(f"{field_name} must be a non-empty list of string arguments")
    if len(cmd) > 32:
        raise ValueError(f"{field_name} has too many arguments ({len(cmd)} > 32)")
    for i, arg in enumerate(cmd):
        if not isinstance(arg, str):
            raise ValueError(f"{field_name}[{i}] must be a string, got {type(arg).__name__}")
        if len(arg) < 1 or len(arg) > 1000:
            raise ValueError(
                f"{field_name}[{i}] length must be between 1 and 1000 characters (got {len(arg)})"
            )
        if "\0" in arg:
            raise ValueError(f"{field_name}[{i}] contains forbidden NUL (\\0) byte")
    return cmd


def truncate_text(text: str, max_bytes: int) -> tuple[str, bool]:
    """Truncate text to at most max_bytes on UTF-8 boundaries.

    Returns:
        tuple[str, bool]: (truncated_text, was_truncated)
    """
    if not text:
        return "", False

    encoded = text.encode("utf-8", errors="ignore")
    if len(encoded) <= max_bytes:
        return text, False

    # Slice at byte boundary and decode ignoring incomplete trailing multibyte character
    sliced = encoded[:max_bytes]
    truncated_str = sliced.decode("utf-8", errors="ignore")
    return truncated_str, True
