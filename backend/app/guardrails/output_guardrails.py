"""
Output Guardrails for Mini-Devin.

Validates and sanitizes agent and model outputs:
1. Redacts sensitive credentials (API tokens, private keys, secrets).
2. Validates structured responses against expected Pydantic schemas.
3. Guards against malformed, hallucinated, or unparseable model payloads.
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING, Any

# Deferred to avoid circular import:
#   guardrails.output_guardrails → agents.schemas → agents.__init__
#   → agents.graph → agents.triage → guardrails (partially initialized)
if TYPE_CHECKING:
    from app.agents.schemas import TriageClassification, TriageResult

logger = logging.getLogger(__name__)

# Secret patterns to redact from operational messages and logs
_SECRET_PATTERNS = (
    r"(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9_]{36,}",           # GitHub Personal Access Tokens
    r"gsk_[A-Za-z0-9]{32,}",                                 # Groq API Keys
    r"AIza[0-9A-Za-z-_]{35}",                               # Google AI Studio / Firebase Keys
    r"hf_[A-Za-z0-9]{34,}",                                 # Hugging Face Tokens
    r"sk-[A-Za-z0-9_-]{20,}",                               # OpenAI / General API Keys
    r"bearer\s+[A-Za-z0-9\-\._~\+\/]+=*",                   # Bearer Tokens
    r"-----BEGIN\s+[A-Z\s]+PRIVATE\s+KEY-----",             # Private Key blocks
)

_SECRET_REGEXES = [re.compile(p, re.IGNORECASE) for p in _SECRET_PATTERNS]


def redact_secrets(text: str) -> str:
    """Scan and redact any accidental API keys or secrets from text."""
    if not text:
        return ""
    sanitized = text
    for rx in _SECRET_REGEXES:
        sanitized = rx.sub("[REDACTED_SECRET]", sanitized)
    return sanitized


def validate_triage_output(
    data: dict[str, Any],
    fallback_reason: str = "Triage validation failed; safely routed to out_of_scope.",
) -> "TriageResult":
    # Local import prevents the circular dependency at module load time.
    from app.agents.schemas import TriageClassification, TriageResult  # noqa: PLC0415
    """
    Validate a raw dictionary against TriageResult requirements.
    
    If invalid or malformed, returns a safe fallback out_of_scope classification.
    """
    try:
        raw_classification = str(data.get("classification", "")).strip().lower()
        
        # Map or validate classification enum
        if raw_classification in ("bug", "defect", "error", "fix"):
            cls_enum = TriageClassification.BUG
            is_supported = True
        elif raw_classification in ("feature", "enhancement", "feat", "addition"):
            cls_enum = TriageClassification.FEATURE
            is_supported = True
        elif raw_classification in ("test", "tests", "testing", "unit_test"):
            cls_enum = TriageClassification.TEST
            is_supported = True
        elif raw_classification in ("out_of_scope", "question", "documentation", "unsupported", "invalid"):
            cls_enum = TriageClassification.OUT_OF_SCOPE
            is_supported = False
        else:
            raise ValueError(f"Unrecognized triage classification: {raw_classification!r}")

        # Override is_supported if explicitly provided as False
        if "is_supported" in data and not bool(data["is_supported"]):
            is_supported = False

        confidence_val = float(data.get("confidence", 0.9))
        confidence = max(0.0, min(1.0, confidence_val))

        raw_reason = str(data.get("reason", "")).strip() or "Classified based on issue analysis."
        reason = redact_secrets(raw_reason)

        raw_warnings = data.get("warnings", [])
        warnings = [redact_secrets(str(w)) for w in raw_warnings] if isinstance(raw_warnings, list) else []

        return TriageResult(
            classification=cls_enum,
            is_supported=is_supported,
            confidence=confidence,
            reason=reason,
            warnings=warnings,
        )
    except Exception as exc:
        logger.warning("Output guardrail validation failed on raw data: %s (error: %s)", data, exc)
        return TriageResult(
            classification=TriageClassification.OUT_OF_SCOPE,
            is_supported=False,
            confidence=0.5,
            reason=f"{fallback_reason} (Validation error: {exc})",
            warnings=[f"Malformed output guarded: {exc}"],
        )


# ── Dangerous Path & Diff Safety Guardrails ──────────────────────────

_WORKFLOW_DENY_PATTERN = r"^\.github/(?:workflows|actions)/.*"
_CANONICAL_WORKFLOW_RE = re.compile(r"^\.github/workflows/[A-Za-z0-9_.-]+\.ya?ml$", re.IGNORECASE)

DENIED_PATH_PATTERNS = (
    r"(?:^|/)\.env(?:\..+)?$",
    r".*\.pem$",
    r".*\.key$",
    r".*\.pfx$",
    r".*\.pkcs12$",
    r"(?:^|/)id_rsa.*",
    r"(?:^|/)id_ed25519.*",
    r"^\.git(?:/.*|$)",
    _WORKFLOW_DENY_PATTERN,
    r"(?:^|/)\.?secrets?(?:\.(?:json|ya?ml|toml|ini|cfg|conf|txt|env))?$",
    r".*\.secret$",
    r"(?:^|/)\.?credentials?(?:\.(?:json|ya?ml|toml|ini|cfg|conf|txt|env))?$",
    r"(?:^|/)service-account.*\.json$",
    r"(?:^|/)\.?tokens?(?:\.(?:json|ya?ml|toml|ini|cfg|conf|txt|env))?$",
    r".*\.token$",
)
_DENIED_REGEXES = [re.compile(p, re.IGNORECASE) for p in DENIED_PATH_PATTERNS]

_DANGEROUS_WORKFLOW_CONTENT_RES = (
    re.compile(r"^\+.*\bpull_request_target\b", re.IGNORECASE | re.MULTILINE),
    re.compile(r"^\+.*\bpermissions\s*:\s*write-all\b", re.IGNORECASE | re.MULTILINE),
    re.compile(r"^\+.*(?:curl|wget|nc|netcat)\b.*\$\{\{\s*secrets\.", re.IGNORECASE | re.MULTILINE),
)


def validate_workflow_diff_content(diff_text: str) -> tuple[bool, str]:
    """
    Validate that an explicitly human-approved workflow diff does not introduce
    privilege escalation (pull_request_target, write-all) or secret exfiltration.
    """
    if not diff_text:
        return True, ""
    for rx in _DANGEROUS_WORKFLOW_CONTENT_RES:
        if rx.search(diff_text):
            return (
                False,
                f"Workflow diff rejected: contains forbidden pattern '{rx.pattern}'.",
            )
    return True, ""


def get_human_approved_workflow_paths(
    human_approval: Any,
    approved_plan: Any,
) -> set[str]:
    """
    Derive the exact set of GitHub Actions workflow paths explicitly authorized
    by a human operator for a hash-verified frozen plan.

    Security Invariants:
    - Never trusts LLM or Coder output to self-authorize workflow changes.
    - Requires human_approval['decision'] == 'approved' AND
      human_approval['allow_workflow_changes'] is True.
    - Requires cryptographic plan hash match between approved_plan and human_approval['plan_hash'].
    - Only permits canonical '.github/workflows/<file>.yml|.yaml' paths listed in
      approved_plan['affected_files'] (and human_approval['allowed_workflow_paths'] if provided).
    """
    if not isinstance(human_approval, dict):
        return set()
    if human_approval.get("decision") != "approved":
        return set()
    if human_approval.get("allow_workflow_changes") is not True:
        return set()
    if not approved_plan:
        return set()

    plan_dict = (
        approved_plan.model_dump(mode="json")
        if hasattr(approved_plan, "model_dump")
        else (dict(approved_plan) if isinstance(approved_plan, dict) else None)
    )
    if not isinstance(plan_dict, dict):
        return set()

    approved_hash = human_approval.get("plan_hash")
    if not approved_hash or not isinstance(approved_hash, str):
        return set()

    from app.agents.schemas import compute_plan_hash  # noqa: PLC0415

    if compute_plan_hash(plan_dict) != approved_hash:
        return set()

    affected = plan_dict.get("affected_files") or []
    if not isinstance(affected, list):
        return set()

    candidates: set[str] = set()
    for path in affected:
        if not isinstance(path, str):
            continue
        norm = path.strip().replace("\\", "/")
        if ".." not in norm.split("/") and _CANONICAL_WORKFLOW_RE.match(norm):
            candidates.add(norm)

    explicit_list = human_approval.get("allowed_workflow_paths")
    if explicit_list is not None:
        if not isinstance(explicit_list, (list, tuple, set)):
            return set()
        explicit_norm = {
            p.strip().replace("\\", "/")
            for p in explicit_list
            if isinstance(p, str)
        }
        candidates &= explicit_norm

    return candidates


def validate_path_safety(
    file_path: str,
    allowed_workflow_paths: Sequence[str] | set[str] | None = None,
) -> tuple[bool, str]:
    """
    Check if a file path is safe from path traversal and sensitive denylists.

    By default, all '.github/workflows/*' and '.github/actions/*' paths are strictly denied.
    A workflow path is permitted only if it is present in 'allowed_workflow_paths'
    (verified from explicit human approval and frozen plan hash) and matches
    canonical '.github/workflows/<name>.yml|.yaml'.

    Returns (is_safe, violation_reason).
    """
    if not file_path or not file_path.strip():
        return False, "File path is empty."

    if any(c in file_path for c in ("\x00", "\r", "\n")):
        return False, "File path contains forbidden control characters."

    raw_stripped = file_path.strip()
    norm = raw_stripped.replace("\\", "/")

    # Check directory traversal
    if ".." in norm.split("/"):
        return False, f"Path traversal ('..') detected in '{file_path}'."

    # Check absolute, UNC, or Windows drive path escapes
    if (
        raw_stripped.startswith("\\\\")
        or norm.startswith("/")
        or re.match(r"^/?[A-Za-z]:", norm)
    ):
        return False, f"Absolute path '{file_path}' is forbidden; paths must be repository-relative."

    allowed_wf_set = {
        p.strip().replace("\\", "/")
        for p in (allowed_workflow_paths or ())
        if isinstance(p, str)
    }

    # Check sensitive denylist
    for rx in _DENIED_REGEXES:
        if rx.search(norm):
            if (
                rx.pattern == _WORKFLOW_DENY_PATTERN
                and norm in allowed_wf_set
                and _CANONICAL_WORKFLOW_RE.match(norm)
            ):
                continue
            return False, f"Access to sensitive file pattern '{rx.pattern}' in '{file_path}' is denied."

    return True, ""


def validate_diff_safety(
    file_changes: Sequence[dict[str, Any] | Any],
    allowed_workflow_paths: Sequence[str] | set[str] | None = None,
) -> tuple[bool, list[str]]:
    """
    Validate proposed file changes against sensitive file denylists.

    Returns (is_clean, violations).
    """
    violations: list[str] = []
    if not file_changes:
        return True, []

    for change in file_changes:
        path = change.get("path") if isinstance(change, dict) else getattr(change, "path", "")
        if not path:
            path = change.get("file_path") if isinstance(change, dict) else getattr(change, "file_path", "")
        is_safe, reason = validate_path_safety(path, allowed_workflow_paths=allowed_workflow_paths)
        if not is_safe:
            violations.append(reason)
            logger.warning("Diff gate guardrail triggered: %s", reason)
            continue

        norm_path = str(path).strip().replace("\\", "/")
        if _CANONICAL_WORKFLOW_RE.match(norm_path):
            diff_text = (
                (change.get("diff_text") or change.get("diff") or "")
                if isinstance(change, dict)
                else (getattr(change, "diff_text", None) or getattr(change, "diff", "") or "")
            )
            wf_ok, wf_reason = validate_workflow_diff_content(str(diff_text))
            if not wf_ok:
                violations.append(wf_reason)
                logger.warning("Workflow diff content guardrail triggered: %s", wf_reason)

    return len(violations) == 0, violations


def validate_plan_output(data: dict[str, Any]) -> tuple[bool, dict[str, Any], list[str]]:
    """
    Validate and sanitize structured implementation plan output from LLM.
    
    Guarantees:
    - Secrets are redacted from explanation, summary, and step descriptions.
    - Affected files satisfy path safety.
    - Required fields (summary, steps) are present.
    """
    violations: list[str] = []
    sanitized: dict[str, Any] = dict(data)

    # Redact sensitive values from text fields
    if "summary" in sanitized:
        sanitized["summary"] = redact_secrets(str(sanitized["summary"]))
    if "explanation" in sanitized:
        sanitized["explanation"] = redact_secrets(str(sanitized["explanation"]))

    steps = sanitized.get("steps", [])
    if not steps:
        violations.append("Plan contains no implementation steps.")
    else:
        for idx, s in enumerate(steps):
            if isinstance(s, dict):
                s["description"] = redact_secrets(str(s.get("description", "")))
                target = s.get("target_file", "")
                if target:
                    is_safe, reason = validate_path_safety(target)
                    if not is_safe:
                        violations.append(f"Step {idx+1}: {reason}")

    affected = sanitized.get("affected_files", [])
    if not affected:
        violations.append("Plan affected_files list is empty.")
    else:
        for af in affected:
            is_safe, reason = validate_path_safety(af)
            if not is_safe:
                violations.append(f"Affected file: {reason}")

    is_valid = len(violations) == 0
    return is_valid, sanitized, violations
