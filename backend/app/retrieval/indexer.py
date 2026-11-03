"""
Repository Indexer for Mini-Devin.

Handles safe repository path validation, file enumeration, gitignore parsing,
sensitive file filtering, binary detection, chunking with accurate line ranges,
and incremental re-indexing.
"""

from __future__ import annotations

import fnmatch
import hashlib
import logging
import os
from pathlib import Path
import re
from typing import Any, Optional, Sequence

from app.retrieval.vector_store import (
    ChunkMetadata,
    HybridIndex,
    LexicalIndex,
    SearchResult,
    is_faiss_available,
)

logger = logging.getLogger(__name__)

# Standard directory exclusions
EXCLUDED_DIRS = frozenset({
    ".git",
    ".github",
    ".hg",
    ".svn",
    ".venv",
    "venv",
    "env",
    ".env",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".idea",
    ".vscode",
    "dist",
    "build",
    "target",
    "bin",
    "obj",
    ".tox",
    "coverage",
    ".coverage",
    "htmlcov",
    ".eggs",
})

# Standard binary file extensions
BINARY_EXTENSIONS = frozenset({
    ".pyc", ".pyo", ".pyd", ".so", ".dll", ".dylib", ".exe", ".bin",
    ".zip", ".tar", ".gz", ".tgz", ".bz2", ".xz", ".7z", ".whl",
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".bmp", ".tiff", ".webp",
    ".pdf", ".svg", ".wasm", ".db", ".sqlite", ".sqlite3", ".parquet",
    ".arrow", ".pkl", ".pickle", ".npy", ".npz", ".pt", ".pth", ".onnx",
    ".woff", ".woff2", ".ttf", ".eot", ".mp3", ".mp4", ".wav", ".avi",
    ".mov",
})

# Control and VCS files to skip indexing as source code
EXCLUDED_FILENAMES = frozenset({
    ".gitignore",
    ".gitattributes",
    ".gitmodules",
    ".gitkeep",
    ".dockerignore",
})

# Patterns for files that typically contain secrets or private keys
SECRET_FILE_PATTERNS = (
    ".env*",
    "*.pem",
    "*.key",
    "*.pkcs12",
    "*.pfx",
    "id_rsa*",
    "id_ed25519*",
    "id_ecdsa*",
    "*.token",
    "*secret*",
    "*credential*",
    "credentials.json",
    "service-account*.json",
)


def is_path_safe_and_permitted(target_path: Path, permitted_root: Optional[Path] = None) -> bool:
    """
    Ensure the path exists, is a directory, resolves without symlink escape,
    and is within permitted_root if provided.
    """
    try:
        resolved = target_path.resolve()
        if not resolved.is_dir():
            return False

        if permitted_root is not None:
            resolved_root = permitted_root.resolve()
            # Must be equal to or sub-path of resolved_root
            if resolved != resolved_root and resolved_root not in resolved.parents:
                return False

        return True
    except (OSError, ValueError, RuntimeError):
        return False


DEFAULT_PERMITTED_SNAPSHOT_ROOT = Path("workspaces/snapshots").resolve()


def resolve_permitted_repo_path(
    repo_input: str,
    permitted_root: Optional[Path] = None,
) -> Optional[Path]:
    """
    Validate and resolve a repository identifier or path.
    
    Rejects remote slugs (e.g. 'owner/repo') unless they correspond to an
    actual local directory within the permitted snapshot/checkout root.
    Arbitrary paths outside permitted bounds are strictly rejected.
    """
    if not repo_input or not repo_input.strip():
        return None

    raw_path = repo_input.strip()

    # Reject classic owner/repo pattern if it has no local path presence
    # e.g., 'acme/calculator' is a remote GitHub slug
    candidate = Path(raw_path)
    if not candidate.exists():
        # Check if candidate exists within explicitly provided permitted_root
        if permitted_root is not None:
            relative_candidate = permitted_root / candidate
            if relative_candidate.exists() and is_path_safe_and_permitted(relative_candidate, permitted_root):
                return relative_candidate.resolve()
        # Also check within default snapshots root
        if DEFAULT_PERMITTED_SNAPSHOT_ROOT.exists():
            snapshot_candidate = DEFAULT_PERMITTED_SNAPSHOT_ROOT / candidate
            if snapshot_candidate.exists() and is_path_safe_and_permitted(snapshot_candidate, DEFAULT_PERMITTED_SNAPSHOT_ROOT):
                return snapshot_candidate.resolve()
        return None

    # If permitted_root is specified, path MUST be within permitted_root
    if permitted_root is not None:
        if is_path_safe_and_permitted(candidate, permitted_root):
            return candidate.resolve()
        return None

    # If candidate is a safe local directory, verify it does not escape to arbitrary sensitive roots
    if is_path_safe_and_permitted(candidate):
        resolved = candidate.resolve()
        # Reject root directories
        if resolved == resolved.parent:
            return None
        return resolved

    return None


def is_secret_file(filename: str) -> bool:
    """Check if filename matches sensitive secret or credential patterns."""
    fn_lower = filename.lower()
    for pattern in SECRET_FILE_PATTERNS:
        if fnmatch.fnmatch(fn_lower, pattern.lower()):
            return True
    return False


def is_binary_file(file_path: Path) -> bool:
    """Detect if file is binary by extension or checking for NUL bytes."""
    if file_path.suffix.lower() in BINARY_EXTENSIONS:
        return True
    try:
        with open(file_path, "rb") as f:
            chunk = f.read(4096)
            if b"\x00" in chunk:
                return True
    except (OSError, PermissionError):
        return True
    return False


def parse_gitignore(gitignore_path: Path) -> list[str]:
    """Parse a .gitignore file into glob pattern strings."""
    patterns: list[str] = []
    if not gitignore_path.is_file():
        return patterns

    try:
        with open(gitignore_path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                stripped = line.strip()
                if not stripped or stripped.startswith("#"):
                    continue
                # Normalize trailing slash
                if stripped.endswith("/"):
                    stripped = stripped[:-1]
                patterns.append(stripped)
    except (OSError, PermissionError) as exc:
        logger.debug("Failed to read gitignore %s: %s", gitignore_path, exc)

    return patterns


def matches_gitignore(rel_path_str: str, patterns: list[str]) -> bool:
    """Check if relative path matches any gitignore patterns."""
    normalized = rel_path_str.replace("\\", "/")
    basename = Path(normalized).name

    for pat in patterns:
        pat_norm = pat.replace("\\", "/")
        if fnmatch.fnmatch(normalized, pat_norm):
            return True
        if fnmatch.fnmatch(basename, pat_norm):
            return True
        if fnmatch.fnmatch(normalized, f"*{pat_norm}*"):
            return True

    return False


def compute_file_hash(file_path: Path) -> str:
    """Compute SHA-256 hash of a file for incremental indexing."""
    h = hashlib.sha256()
    try:
        with open(file_path, "rb") as f:
            while chunk := f.read(65536):
                h.update(chunk)
        return h.hexdigest()
    except (OSError, PermissionError):
        return ""


def chunk_file(
    file_path: Path,
    rel_path_str: str,
    file_hash: str,
    chunk_size: int = 50,
    chunk_overlap: int = 10,
) -> list[ChunkMetadata]:
    """
    Chunk a text file into overlapping line segments while preserving
    exact 1-indexed start and end line ranges.
    """
    chunks: list[ChunkMetadata] = []
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
    except (OSError, PermissionError) as exc:
        logger.warning("Could not read file %s: %s", file_path, exc)
        return []

    if not lines:
        return []

    total_lines = len(lines)
    step = max(1, chunk_size - chunk_overlap)

    for i in range(0, total_lines, step):
        start_line = i + 1
        end_line = min(total_lines, i + chunk_size)
        content = "".join(lines[i:end_line])

        # Skip empty or whitespace-only chunks
        if not content.strip():
            continue

        chunk_id = f"{rel_path_str}#{start_line}-{end_line}"
        chunks.append(
            ChunkMetadata(
                chunk_id=chunk_id,
                file_path=rel_path_str,
                start_line=start_line,
                end_line=end_line,
                content=content,
                file_hash=file_hash,
            )
        )

        if end_line >= total_lines:
            break

    return chunks


class RepositoryIndexer:
    """
    Manages scanning, filtering, chunking, and incremental indexing
    of a local repository.
    """

    def __init__(
        self,
        repo_path: Path,
        index: Optional[Any] = None,
        chunk_size: int = 50,
        chunk_overlap: int = 10,
    ):
        self.repo_path = repo_path.resolve()
        self.index = index if index is not None else HybridIndex()
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.file_hashes: dict[str, str] = {}  # rel_path -> sha256

    def enumerate_files(self) -> list[Path]:
        """
        Enumerate all candidate source files in repo_path,
        strictly respecting gitignore and excluding sensitive/binary files.
        """
        gitignore_patterns: list[str] = []
        root_gitignore = self.repo_path / ".gitignore"
        if root_gitignore.is_file():
            gitignore_patterns.extend(parse_gitignore(root_gitignore))

        discovered: list[Path] = []

        for root, dirs, files in os.walk(self.repo_path, topdown=True, followlinks=False):
            # Prune excluded directories
            dirs[:] = [
                d for d in dirs
                if d not in EXCLUDED_DIRS
                and not d.startswith(".git")
                and not is_secret_file(d)
                and not matches_gitignore(
                    str((Path(root) / d).relative_to(self.repo_path)),
                    gitignore_patterns,
                )
            ]

            root_path = Path(root)

            # Check nested .gitignore if present
            nested_gi = root_path / ".gitignore"
            if nested_gi.is_file() and nested_gi != root_gitignore:
                gitignore_patterns.extend(parse_gitignore(nested_gi))

            for f in files:
                if f in EXCLUDED_FILENAMES:
                    continue

                # Check sensitive files
                if is_secret_file(f):
                    continue

                full_path = root_path / f

                # Check symlink escape
                try:
                    resolved_file = full_path.resolve()
                    if self.repo_path not in resolved_file.parents and resolved_file != self.repo_path:
                        continue
                except (OSError, RuntimeError):
                    continue

                try:
                    rel_path = full_path.relative_to(self.repo_path)
                    rel_str = str(rel_path).replace("\\", "/")
                except ValueError:
                    continue

                if matches_gitignore(rel_str, gitignore_patterns):
                    continue

                if is_binary_file(full_path):
                    continue

                discovered.append(full_path)

        return sorted(discovered)

    def index_repository(self, force: bool = False) -> dict[str, Any]:
        """
        Index or incrementally re-index the repository.
        
        Returns summary dictionary with indexed_files, chunk_count, and status.
        """
        files = self.enumerate_files()
        if not files:
            self.index.clear()
            self.file_hashes.clear()
            return {
                "status": "empty_repository",
                "indexed_files": 0,
                "chunk_count": 0,
                "method": self.index.method_name,
            }

        current_file_set: set[str] = set()
        added_or_modified_chunks: list[ChunkMetadata] = []
        reindexed_files = 0

        for f in files:
            rel_str = str(f.relative_to(self.repo_path)).replace("\\", "/")
            current_file_set.add(rel_str)
            curr_hash = compute_file_hash(f)

            if not force and self.file_hashes.get(rel_str) == curr_hash:
                # File unchanged
                continue

            # File is new or changed: remove old chunks first
            self.index.remove_file(rel_str)
            new_chunks = chunk_file(
                f,
                rel_str,
                curr_hash,
                chunk_size=self.chunk_size,
                chunk_overlap=self.chunk_overlap,
            )
            added_or_modified_chunks.extend(new_chunks)
            self.file_hashes[rel_str] = curr_hash
            reindexed_files += 1

        # Handle deleted files
        deleted_files = set(self.file_hashes.keys()) - current_file_set
        for df in deleted_files:
            self.index.remove_file(df)
            self.file_hashes.pop(df, None)

        if added_or_modified_chunks:
            self.index.add_chunks(added_or_modified_chunks)

        return {
            "status": "indexed",
            "indexed_files": len(current_file_set),
            "reindexed_files": reindexed_files,
            "deleted_files": len(deleted_files),
            "chunk_count": len(self.index.chunks),
            "method": self.index.method_name,
        }

    def search(
        self,
        query: str,
        query_terms: Optional[list[str]] = None,
        top_k: int = 5,
        query_vector: Optional[Sequence[float]] = None,
    ) -> list[SearchResult]:
        """Query the repository index."""
        if hasattr(self.index, "search"):
            import inspect
            sig = inspect.signature(self.index.search)
            if "query_vector" in sig.parameters:
                return self.index.search(
                    query=query, top_k=top_k, query_terms=query_terms, query_vector=query_vector
                )
        return self.index.search(query=query, top_k=top_k, query_terms=query_terms)
