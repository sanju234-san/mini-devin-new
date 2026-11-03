"""Unit tests for app.sandbox.safety — diff, tar archive, and command validation."""

from __future__ import annotations

import io
import tarfile
import pytest

from app.sandbox.safety import (
    MAX_DIFF_BYTES,
    normalize_repo_archive,
    truncate_text,
    validate_command,
    validate_diff,
)


def _make_tar(members: dict[str, bytes | str]) -> bytes:
    """Helper to generate an in-memory tarball for testing."""
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tar:
        for name, content in members.items():
            data = content.encode("utf-8") if isinstance(content, str) else content
            info = tarfile.TarInfo(name=name)
            info.size = len(data)
            tar.addfile(info, fileobj=io.BytesIO(data))
    buf.seek(0)
    return buf.getvalue()


class TestValidateDiff:
    """Tests for validate_diff helper."""

    def test_safe_diff_passes(self) -> None:
        safe_diff = (
            "diff --git a/app/main.py b/app/main.py\n"
            "--- a/app/main.py\n"
            "+++ b/app/main.py\n"
            "@@ -1,3 +1,3 @@\n"
            "-print('old')\n"
            "+print('new')\n"
        )
        # Should not raise
        validate_diff(safe_diff)

    def test_none_or_empty_diff_passes(self) -> None:
        validate_diff(None)
        validate_diff("")
        validate_diff("   \n  ")

    def test_oversized_diff_rejected(self) -> None:
        oversized = "a" * (MAX_DIFF_BYTES + 10)
        with pytest.raises(ValueError, match="exceeds maximum size"):
            validate_diff(oversized)

    def test_nul_byte_in_diff_rejected(self) -> None:
        with pytest.raises(ValueError, match="NUL"):
            validate_diff("diff --git a/file.py b/file.py\n\0")

    def test_binary_patch_rejected(self) -> None:
        diff = "diff --git a/img.png b/img.png\nGIT binary patch\nliteral 500\n..."
        with pytest.raises(ValueError, match="Binary diff patches are forbidden"):
            validate_diff(diff)

    def test_symlink_mode_rejected(self) -> None:
        diff = (
            "diff --git a/link b/link\n"
            "new file mode 120000\n"
            "--- /dev/null\n"
            "+++ b/link\n"
            "@@ -0,0 +1 @@\n"
            "+/etc/passwd\n"
        )
        with pytest.raises(ValueError, match="symbolic link"):
            validate_diff(diff)

    def test_path_traversal_dot_dot_rejected(self) -> None:
        diff = (
            "diff --git a/../secret.txt b/../secret.txt\n"
            "--- a/../secret.txt\n"
            "+++ b/../secret.txt\n"
        )
        with pytest.raises(ValueError, match="Path traversal '..'"):
            validate_diff(diff)

    def test_absolute_path_rejected(self) -> None:
        diff = "diff --git a//etc/passwd b//etc/passwd\n--- //etc/passwd\n+++ //etc/passwd\n"
        with pytest.raises(ValueError, match="Absolute path"):
            validate_diff(diff)

    def test_git_directory_target_rejected(self) -> None:
        diff = (
            "diff --git a/.git/hooks/pre-commit b/.git/hooks/pre-commit\n"
            "--- a/.git/hooks/pre-commit\n"
            "+++ b/.git/hooks/pre-commit\n"
        )
        with pytest.raises(ValueError, match="Reference to .git directory"):
            validate_diff(diff)

    def test_backslash_rejected(self) -> None:
        diff = "diff --git a\\foo\\bar b\\foo\\bar\n--- a\\foo\\bar\n+++ b\\foo\\bar\n"
        with pytest.raises(ValueError, match="backslashes"):
            validate_diff(diff)


class TestNormalizeRepoArchive:
    """Tests for normalize_repo_archive helper."""

    def test_safe_archive_normalized(self) -> None:
        raw_tar = _make_tar({"README.md": "# Hello", "src/code.py": "x = 1"})
        norm_tar = normalize_repo_archive(raw_tar, max_archive_mb=10)

        assert isinstance(norm_tar, bytes)
        with tarfile.open(fileobj=io.BytesIO(norm_tar), mode="r") as tar:
            members = tar.getmembers()
            assert len(members) == 2
            for m in members:
                # Assert uid/gid forced to 1000
                assert m.uid == 1000
                assert m.gid == 1000
                assert m.uname == "sandbox"
                assert m.gname == "sandbox"
                # Assert SUID/SGID stripped
                assert m.mode & 0o7000 == 0

    def test_setuid_bits_stripped(self) -> None:
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w") as tar:
            info = tarfile.TarInfo(name="bin/evil")
            info.size = 4
            info.mode = 0o4755  # setuid bit set
            tar.addfile(info, fileobj=io.BytesIO(b"evil"))
        raw_tar = buf.getvalue()

        norm = normalize_repo_archive(raw_tar, max_archive_mb=10)
        with tarfile.open(fileobj=io.BytesIO(norm), mode="r") as tar:
            m = tar.getmember("bin/evil")
            assert m.mode == 0o755  # 0o4000 stripped!

    def test_traversal_name_rejected(self) -> None:
        raw_tar = _make_tar({"../evil.txt": "data"})
        with pytest.raises(ValueError, match="Path traversal"):
            normalize_repo_archive(raw_tar)

    def test_absolute_name_rejected(self) -> None:
        raw_tar = _make_tar({"/etc/passwd": "root:x:0:0"})
        with pytest.raises(ValueError, match="Absolute path"):
            normalize_repo_archive(raw_tar)

    def test_device_node_rejected(self) -> None:
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w") as tar:
            info = tarfile.TarInfo(name="dev/null")
            info.type = tarfile.CHRTYPE
            tar.addfile(info)
        with pytest.raises(ValueError, match="Forbidden special device"):
            normalize_repo_archive(buf.getvalue())

    def test_outside_symlink_rejected(self) -> None:
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w") as tar:
            info = tarfile.TarInfo(name="link_to_root")
            info.type = tarfile.SYMTYPE
            info.linkname = "../../etc/passwd"
            tar.addfile(info)
        with pytest.raises(ValueError, match="Forbidden link escaping"):
            normalize_repo_archive(buf.getvalue())

    def test_zip_bomb_uncompressed_ceiling_rejected(self) -> None:
        # Create a compressed archive (small compressed size, huge uncompressed size)
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w:gz") as tar:
            info = tarfile.TarInfo(name="huge.dat")
            # 1 MB max_archive_mb -> 4 MB uncompressed ceiling
            info.size = 5 * 1024 * 1024
            tar.addfile(info, fileobj=io.BytesIO(b"\0" * (5 * 1024 * 1024)))
        compressed = buf.getvalue()
        # Compressed size is tiny (< 10 KB), but uncompressed is 5 MB (> 4 MB)
        assert len(compressed) < 50000
        with pytest.raises(ValueError, match="zip-bomb guard"):
            normalize_repo_archive(compressed, max_archive_mb=1)


class TestValidateCommand:
    """Tests for validate_command helper."""

    def test_valid_argv_passes(self) -> None:
        cmd = ["python", "-m", "pytest", "-q"]
        assert validate_command(cmd) == cmd

    def test_none_returns_none(self) -> None:
        assert validate_command(None) is None

    def test_shell_string_rejected(self) -> None:
        with pytest.raises(ValueError, match="must be a non-empty list"):
            validate_command("python -m pytest")  # type: ignore

    def test_empty_list_rejected(self) -> None:
        with pytest.raises(ValueError, match="must be a non-empty list"):
            validate_command([])

    def test_too_many_args_rejected(self) -> None:
        with pytest.raises(ValueError, match="too many arguments"):
            validate_command(["arg"] * 33)

    def test_arg_too_long_rejected(self) -> None:
        with pytest.raises(ValueError, match="length must be between 1 and 1000"):
            validate_command(["a" * 1001])

    def test_nul_byte_in_arg_rejected(self) -> None:
        with pytest.raises(ValueError, match="NUL"):
            validate_command(["echo", "hello\0world"])


class TestTruncateText:
    """Tests for truncate_text helper."""

    def test_short_text_not_truncated(self) -> None:
        text, is_trunc = truncate_text("hello world", 100)
        assert text == "hello world"
        assert is_trunc is False

    def test_long_text_truncated(self) -> None:
        text, is_trunc = truncate_text("abcdefghij", 5)
        assert text == "abcde"
        assert is_trunc is True
