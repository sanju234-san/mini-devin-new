"""
Input Guardrails for Mini-Devin.

Treats incoming GitHub issue titles, descriptions, and user inputs as untrusted data:
1. Detects prompt injection and system override attempts.
2. Cleanses harmful control characters while preserving valid code and markdown.
3. Flags suspicious or ambiguous input patterns with clear diagnostic warnings.
"""

from __future__ import annotations

import logging
import re
from typing import Tuple

logger = logging.getLogger(__name__)

# Patterns that indicate an adversarial attempt to hijack LLM system prompts
_INJECTION_PATTERNS = (
    r"ignore\s+(all\s+)?(previous|prior|above)\s+(instructions|prompts|rules)",
    r"disregard\s+(all\s+)?(previous|prior|above)\s+(instructions|prompts|rules)",
    r"forget\s+(all\s+)?(previous|prior|above)\s+(instructions|rules)",
    r"you\s+are\s+now\s+(in\s+developer\s+mode|dan|an\s+unrestricted|a\s+different)",
    r"override\s+system\s+(prompt|instructions)",
    r"(reveal|print|expose|leak|exfiltrate)\s+(all\s+)?(system\s+prompts?|api\s*keys?|secrets?)",
    r"system\s*:\s*you\s+must",
    r"###\s*system\s*instruction",
)

_INJECTION_REGEXES = [re.compile(p, re.IGNORECASE) for p in _INJECTION_PATTERNS]


def sanitize_text(text: str) -> str:
    """Strip dangerous non-printable ASCII/Unicode control codes except normal whitespace."""
    if not text:
        return ""
    # Allow standard printable characters, newlines, carriage returns, tabs, and unicode
    cleaned = "".join(ch for ch in text if ch in "\n\r\t" or (ord(ch) >= 32 and ord(ch) != 127))
    return cleaned.strip()


def validate_and_sanitize_issue(
    title: str,
    body: str = "",
) -> Tuple[str, str, list[str], bool]:
    """
    Validate and sanitize GitHub issue input.
    
    Returns:
        tuple of (clean_title, clean_body, warnings, is_suspicious)
    """
    warnings: list[str] = []
    is_suspicious = False

    raw_title = title or ""
    raw_body = body or ""

    clean_title = sanitize_text(raw_title)
    clean_body = sanitize_text(raw_body)

    # Check for empty or missing inputs
    if not clean_title:
        warnings.append("Issue title is missing or empty.")
    elif len(clean_title) < 5:
        warnings.append("Issue title is unusually short (< 5 characters) and may be ambiguous.")

    if not clean_body:
        warnings.append("Issue description/body is empty; triage will rely solely on title.")

    # Check for prompt injection patterns — collect ALL matches, not just the first.
    combined = f"{clean_title}\n{clean_body}"
    for rx in _INJECTION_REGEXES:
        if rx.search(combined):
            is_suspicious = True
            warning_msg = f"Potential prompt injection pattern detected: '{rx.pattern}'."
            warnings.append(warning_msg)
            logger.warning("Input guardrail triggered: %s", warning_msg)

    return clean_title, clean_body, warnings, is_suspicious
