"""
Controlled ACI-Style Repository Tools for Mini-Devin Coder Agent.

Provides safe, sandboxed read, inspection, and patch preparation tools:
1. read_file: inspect file contents with line-range bounding.
2. list_directory: inspect repository directory structure safely.
3. search_code: search text/identifiers across permitted repository files.
4. generate_unified_patch: compute standard unified diff from original to modified code.
5. parse_diff_header_paths: extract genuine file paths directly from diff headers.

Safety Invariants:
- Strict path traversal prevention ('..' and absolute escapes blocked).
- Action denylist enforcement (.env, .git/, .github/, private keys, tokens).
- Secret redaction on all returned observations.
- All operations are bounded within the resolved repository workspace.
"""

from __future__ import annotations

import difflib
import fnmatch
import logging
import os
from pathlib import Path
import re
from typing import Any, Optional

from app.guardrails.output_guardrails import (
    redact_secrets,
    validate_path_safety,
)

logger = logging.getLogger(__name__)

_TOOL_INVOCATION_LOG: list[dict[str, Any]] = []


def get_tool_log() -> list[dict[str, Any]]:
    """Return an audit copy of logged tool invocations."""
    return list(_TOOL_INVOCATION_LOG)


def clear_tool_log() -> None:
    """Clear the in-memory tool invocation log (for testing)."""
    _TOOL_INVOCATION_LOG.clear()


def _log_tool_invocation(tool_name: str, arguments: dict[str, Any], success: bool, reason: str = "") -> None:
    """Audit log tool invocations with secret redaction."""
    safe_args = {k: redact_secrets(str(v)) for k, v in arguments.items()}
    entry = {
        "tool": tool_name,
        "arguments": safe_args,
        "success": success,
        "reason": redact_secrets(reason),
    }
    _TOOL_INVOCATION_LOG.append(entry)
    logger.info("ACI Tool [%s] success=%s reason=%s", tool_name, success, entry["reason"])


def resolve_safe_path(base_dir: str | Path, rel_path: str) -> tuple[bool, Optional[Path], str]:
    """
    Resolve and validate that a relative file path is safe and strictly inside base_dir.
    
    Returns (is_safe, resolved_path, violation_reason).
    """
    safe_path, reason = validate_path_safety(rel_path)
    if not safe_path:
        return False, None, reason

    base = Path(base_dir).resolve()
    try:
        target = (base / rel_path).resolve()
    except Exception as exc:
        return False, None, f"Path resolution failed: {exc}"

    # Verify target path is strictly within base directory (no escape)
    if base != target and base not in target.parents:
        return False, None, f"Path escape detected: '{rel_path}' is outside repository workspace."

    return True, target, ""


def read_file(
    repo_path: str | Path,
    file_path: str,
    start_line: int = 1,
    end_line: int = 300,
    max_lines: int = 500,
) -> dict[str, Any]:
    """
    Read bounded line range from a repository file.
    """
    is_safe, resolved, reason = resolve_safe_path(repo_path, file_path)
    if not is_safe or resolved is None:
        _log_tool_invocation("read_file", {"file_path": file_path}, False, reason)
        return {"success": False, "error": reason, "content": ""}

    if not resolved.is_file():
        err = f"File not found: {file_path}"
        _log_tool_invocation("read_file", {"file_path": file_path}, False, err)
        return {"success": False, "error": err, "content": ""}

    try:
        with open(resolved, "r", encoding="utf-8", errors="replace") as f:
            all_lines = f.readlines()

        total_lines = len(all_lines)
        s = max(1, start_line)
        e = min(total_lines, max(s, end_line))
        if (e - s + 1) > max_lines:
            e = s + max_lines - 1

        selected = all_lines[s - 1 : e]
        numbered_content = "".join(f"{s + idx}: {line}" for idx, line in enumerate(selected))
        safe_content = redact_secrets(numbered_content)

        _log_tool_invocation("read_file", {"file_path": file_path, "lines": f"{s}-{e}"}, True, "OK")
        return {
            "success": True,
            "file_path": file_path,
            "start_line": s,
            "end_line": e,
            "total_lines": total_lines,
            "content": safe_content,
        }
    except Exception as exc:
        err = f"Failed to read file '{file_path}': {exc}"
        _log_tool_invocation("read_file", {"file_path": file_path}, False, err)
        return {"success": False, "error": err, "content": ""}


def list_directory(
    repo_path: str | Path,
    dir_path: str = ".",
    max_entries: int = 100,
) -> dict[str, Any]:
    """
    Safely list directories and files within the permitted repository tree.
    """
    is_safe, resolved, reason = resolve_safe_path(repo_path, dir_path)
    if not is_safe or resolved is None:
        _log_tool_invocation("list_directory", {"dir_path": dir_path}, False, reason)
        return {"success": False, "error": reason, "entries": []}

    if not resolved.is_dir():
        err = f"Directory not found: {dir_path}"
        _log_tool_invocation("list_directory", {"dir_path": dir_path}, False, err)
        return {"success": False, "error": err, "entries": []}

    entries = []
    try:
        for item in sorted(os.listdir(resolved)):
            rel_entry = os.path.join(dir_path, item) if dir_path not in (".", "") else item
            safe_item, _ = validate_path_safety(rel_entry)
            if not safe_item:
                continue

            full = resolved / item
            entries.append({
                "name": item,
                "is_dir": full.is_dir(),
                "size_bytes": full.stat().st_size if full.is_file() else None,
            })
            if len(entries) >= max_entries:
                break

        _log_tool_invocation("list_directory", {"dir_path": dir_path, "count": len(entries)}, True, "OK")
        return {"success": True, "dir_path": dir_path, "entries": entries}
    except Exception as exc:
        err = f"Failed to list directory '{dir_path}': {exc}"
        _log_tool_invocation("list_directory", {"dir_path": dir_path}, False, err)
        return {"success": False, "error": err, "entries": []}


def search_code(
    repo_path: str | Path,
    query: str,
    file_pattern: str = "*.py",
    max_matches: int = 20,
) -> dict[str, Any]:
    """
    Search permitted repository source files for specific symbols, keywords, or patterns.
    """
    base = Path(repo_path).resolve()
    if not base.is_dir():
        return {"success": False, "error": "Invalid repository directory", "matches": []}

    matches: list[dict[str, Any]] = []
    regex = re.compile(re.escape(query), re.IGNORECASE)

    try:
        for root, dirs, files in os.walk(base):
            # Prune protected directories from traversal
            dirs[:] = [d for d in dirs if not d.startswith(".") and d not in ("node_modules", "dist", "build", "venv")]
            for f in files:
                if not fnmatch.fnmatch(f, file_pattern):
                    continue

                full_path = Path(root) / f
                rel_path = str(full_path.relative_to(base)).replace("\\", "/")
                is_safe, reason = validate_path_safety(rel_path)
                if not is_safe:
                    continue

                try:
                    with open(full_path, "r", encoding="utf-8", errors="replace") as fh:
                        for line_num, line in enumerate(fh, 1):
                            if regex.search(line):
                                matches.append({
                                    "file_path": rel_path,
                                    "line_number": line_num,
                                    "line_content": redact_secrets(line.strip()),
                                })
                                if len(matches) >= max_matches:
                                    break
                except Exception:
                    continue
                if len(matches) >= max_matches:
                    break
            if len(matches) >= max_matches:
                break

        _log_tool_invocation("search_code", {"query": query, "matches": len(matches)}, True, "OK")
        return {"success": True, "query": query, "matches": matches}
    except Exception as exc:
        err = f"Search failed: {exc}"
        _log_tool_invocation("search_code", {"query": query}, False, err)
        return {"success": False, "error": err, "matches": []}


def generate_unified_patch(
    file_path: str,
    original_content: str,
    modified_content: str,
) -> str:
    """
    Generate unified diff format string for a single file modification.
    Produces canonical '--- a/file +++ b/file' headers.
    """
    norm_path = file_path.replace("\\", "/")
    orig_lines = original_content.splitlines(keepends=True)
    mod_lines = modified_content.splitlines(keepends=True)
    diff_lines = list(
        difflib.unified_diff(
            orig_lines,
            mod_lines,
            fromfile=f"a/{norm_path}",
            tofile=f"b/{norm_path}",
        )
    )
    return "".join(diff_lines)


def parse_diff_header_paths(diff_text: str) -> list[str]:
    """
    Parse actual affected file paths from unified diff headers.
    Never trusts metadata alone; verifies real '--- a/...' and '+++ b/...' headers.
    """
    paths: list[str] = []
    lines = diff_text.splitlines()
    in_hunk = False
    for idx, line in enumerate(lines):
        if line.startswith("diff --git "):
            in_hunk = False
            continue
        if line.startswith("@@"):
            in_hunk = True
            continue
        is_minus = line.startswith("--- ") and (
            not in_hunk
            or (idx + 1 < len(lines) and lines[idx + 1].startswith("+++ "))
            or line[4:].lstrip().startswith(("a/", "a\\", "/", "\\", '"a/', '"/', ".."))
            or bool(re.match(r'^---\s+"?[A-Za-z]:', line))
        )
        is_plus = line.startswith("+++ ") and (
            not in_hunk
            or line[4:].lstrip().startswith(("b/", "b\\", "/", "\\", '"b/', '"/', ".."))
            or bool(re.match(r'^\+\+\+\s+"?[A-Za-z]:', line))
        )
        if is_minus or is_plus:
            in_hunk = False
            target = line[4:].split("\t", 1)[0].strip()
            if len(target) >= 2 and target.startswith('"') and target.endswith('"'):
                target = target[1:-1]
            if target in ("/dev/null", "dev/null", ""):
                continue
            if len(target) >= 2 and target[:2] in ("a/", "b/", "a\\", "b\\"):
                target = target[2:]
            norm = target.replace("\\", "/")
            if norm and norm not in paths:
                paths.append(norm)
    return paths



# ── Minimal SWE-Agent Style ACI Tools ──────────────────────────────────────────

def open_file(
    repo_path: str | Path,
    file_path: str,
    line_number: int = 1,
    window_size: int = 100,
) -> dict[str, Any]:
    """Windowed file viewer: opens file at specified line with bounded window."""
    s = max(1, line_number)
    e = s + max(1, window_size) - 1
    res = read_file(repo_path, file_path, start_line=s, end_line=e, max_lines=window_size)
    if res.get("success"):
        res["current_line"] = s
        res["window_size"] = window_size
    return res


def goto(
    repo_path: str | Path,
    file_path: str,
    line_number: int,
    window_size: int = 100,
) -> dict[str, Any]:
    """Jump viewer window to specific line number."""
    return open_file(repo_path, file_path, line_number=line_number, window_size=window_size)


def scroll(
    repo_path: str | Path,
    file_path: str,
    current_line: int = 1,
    direction: str = "down",
    window_size: int = 100,
) -> dict[str, Any]:
    """Scroll viewer window up or down by window_size lines."""
    step = window_size if direction.lower() == "down" else -window_size
    target_line = max(1, current_line + step)
    return open_file(repo_path, file_path, line_number=target_line, window_size=window_size)


def edit_file(
    repo_path: str | Path,
    file_path: str,
    start_line: int,
    end_line: int,
    new_text: str,
) -> dict[str, Any]:
    """
    Linter-gated file edit tool: modifies file in working tree directly.
    Enforces path denylist (.github/, .env, CI configs) and rolls back on syntax errors.
    """
    is_safe, resolved, reason = resolve_safe_path(repo_path, file_path)
    if not is_safe or resolved is None:
        _log_tool_invocation("edit_file", {"file_path": file_path}, False, reason)
        return {"success": False, "error": f"Denylist/Path safety violation: {reason}"}

    norm = file_path.replace("\\", "/").lower()
    if (
        norm.startswith((".github/workflows/", ".github/actions/"))
        or "/.github/workflows/" in norm
        or "/.github/actions/" in norm
        or norm == ".env"
        or norm.startswith(".env.")
        or "/.env" in norm
        or norm in ("render.yaml", "dockerfile")
        or norm.endswith((".key", ".pem", ".p12"))
    ):
        err = f"Denylist violation: editing protected file '{file_path}' is strictly forbidden."
        _log_tool_invocation("edit_file", {"file_path": file_path}, False, err)
        return {"success": False, "error": err}

    original_content = ""
    orig_lines: list[str] = []
    if resolved.is_file():
        try:
            with open(resolved, "r", encoding="utf-8", errors="replace") as f:
                orig_lines = f.readlines()
            original_content = "".join(orig_lines)
        except Exception as exc:
            return {"success": False, "error": f"Failed to read '{file_path}': {exc}"}
    elif not resolved.exists() and start_line == 1 and end_line == 1:
        original_content = ""
        orig_lines = []
    else:
        return {"success": False, "error": f"File not found: {file_path}"}

    total_lines = len(orig_lines)
    s = max(1, start_line)
    e = min(total_lines, max(s, end_line)) if total_lines > 0 else 0
    repl_lines = [l if l.endswith("\n") else (l + "\n") for l in new_text.splitlines()]

    if total_lines > 0:
        new_lines = orig_lines[: s - 1] + repl_lines + orig_lines[e:]
    else:
        new_lines = repl_lines
    new_full_content = "".join(new_lines)

    # Linter & syntax validation
    norm_ext = os.path.splitext(file_path)[1].lower()
    lint_err = None
    if norm_ext == ".py":
        import ast
        try:
            ast.parse(new_full_content)
        except SyntaxError as syn_err:
            lint_err = f"Python syntax error at line {syn_err.lineno}: {syn_err.msg}"
    elif norm_ext == ".json":
        import json
        try:
            json.loads(new_full_content)
        except Exception as j_err:
            lint_err = f"JSON syntax error: {j_err}"
    elif norm_ext in (".ts", ".tsx", ".js", ".jsx"):
        stack = []
        pairs = {")": "(", "}": "{", "]": "["}
        in_string = False
        str_char = None
        for line_idx, line in enumerate(new_full_content.splitlines(), 1):
            for ch in line:
                if ch in ('"', "'", "`"):
                    if in_string and ch == str_char:
                        in_string = False
                    elif not in_string:
                        in_string = True
                        str_char = ch
                elif not in_string:
                    if ch in ("(", "{", "["):
                        stack.append((ch, line_idx))
                    elif ch in (")", "}", "]"):
                        if not stack or stack[-1][0] != pairs[ch]:
                            lint_err = f"Mismatched bracket '{ch}' at line {line_idx}"
                            break
                        stack.pop()
            if lint_err:
                break
        if not lint_err and stack:
            unclosed = stack[-1]
            lint_err = f"Unclosed bracket '{unclosed[0]}' opened at line {unclosed[1]}"

    if lint_err:
        if resolved.exists():
            resolved.write_text(original_content, encoding="utf-8")
        _log_tool_invocation("edit_file", {"file_path": file_path, "lines": f"{start_line}-{end_line}"}, False, lint_err)
        return {
            "success": False,
            "error": f"Linter/Syntax check failed: {lint_err}. Edit rolled back.",
            "rolled_back": True,
        }

    try:
        resolved.parent.mkdir(parents=True, exist_ok=True)
        resolved.write_text(new_full_content, encoding="utf-8")
        diff = generate_unified_patch(file_path, original_content, new_full_content)
        _log_tool_invocation("edit_file", {"file_path": file_path, "lines": f"{start_line}-{end_line}"}, True, "OK")
        return {
            "success": True,
            "file_path": file_path,
            "diff": diff,
            "content": new_full_content,
        }
    except Exception as exc:
        if resolved.exists():
            resolved.write_text(original_content, encoding="utf-8")
        return {"success": False, "error": f"Failed to write changes: {exc}", "rolled_back": True}
