"""
Unit tests for Chainlit console implementation plan document preview rendering.
"""

import json
import pytest
from chainlit_console.app import build_plan_document
from app.agents.schemas import ImplementationPlan, PlanStep, RootCauseAnalysis, PlanEvidence


def test_build_plan_document_with_dict():
    """Verify build_plan_document generates complete hierarchical Markdown from a dictionary."""
    plan_dict = {
        "summary": "Fix ZeroDivisionError in calculation endpoint",
        "explanation": "When denominator is zero, the service crashes. Guard against zero values.",
        "plan_version": "v1",
        "plan_hash": "a1b2c3d4e5f678901234567890abcdef1234567890abcdef1234567890abcdef",
        "estimated_complexity": "low",
        "provenance": "evidence_grounded_synthesis",
        "root_cause": {
            "evidence_backed_findings": ["Division by zero occurs in `calc.py:42`."],
            "hypotheses": ["Input validator lacks check for 0."],
        },
        "evidence_items": [
            {
                "file_path": "src/calc.py",
                "start_line": 40,
                "end_line": 45,
                "symbol": "divide",
                "observation": "return a / b without zero check",
            }
        ],
        "file_changes": [
            {
                "file_path": "src/calc.py",
                "module_or_function": "divide",
                "change_description": "Raise ValueError if b == 0.",
            }
        ],
        "steps": [
            {
                "step_number": 1,
                "action": "modify",
                "target_file": "src/calc.py",
                "description": "Add zero divisor guard check.",
            },
            {
                "step_number": 2,
                "action": "modify",
                "target_file": "tests/test_calc.py",
                "description": "Add test case asserting ValueError when denominator is 0.",
            },
        ],
        "acceptance_criteria": [
            "Endpoint returns 400 when denominator is zero.",
            "test_zero_division passes deterministically.",
        ],
        "test_strategy": {
            "existing_tests_to_inspect": ["tests/test_calc.py"],
            "new_tests_to_add": ["test_divide_by_zero_raises"],
        },
        "security_considerations": ["Prevent unhandled 500 server errors that leak stack traces."],
        "risks_and_assumptions": ["Assumption: Callers handle 400 response."],
        "suggested_verification_commands": ["pytest tests/test_calc.py -v"],
    }

    doc = build_plan_document(plan_dict)

    # 1. Main header and secondary metadata (plan hash is secondary metadata, not body)
    assert "# 📋 Implementation Plan: Fix ZeroDivisionError in calculation endpoint" in doc
    assert "> **Plan Version:** `v1` | **Frozen Hash:** `a1b2c3d4`" in doc
    assert doc.strip() != "a1b2c3d4e5f678901234567890abcdef1234567890abcdef1234567890abcdef"

    # 2. Section headings
    assert "## 1. Summary & Intended Behavior" in doc
    assert "When denominator is zero, the service crashes." in doc

    assert "## 2. Root Cause Analysis" in doc
    assert "Division by zero occurs in `calc.py:42`." in doc

    assert "## 3. Grounded Code Evidence" in doc
    assert "`src/calc.py:40-45` (`divide`): return a / b without zero check" in doc

    assert "## 4. Proposed Changes by File" in doc
    assert "### `src/calc.py`" in doc
    assert "**Target Symbol:** `divide`" in doc

    # 3. Numbered steps with action and target file
    assert "## 5. Implementation Steps" in doc
    assert "1. **[MODIFY]** `src/calc.py`: Add zero divisor guard check." in doc
    assert "2. **[MODIFY]** `tests/test_calc.py`: Add test case asserting ValueError when denominator is 0." in doc

    # 4. Acceptance criteria and test strategy
    assert "## 6. Acceptance Criteria" in doc
    assert "- [ ] Endpoint returns 400 when denominator is zero." in doc
    assert "## 7. Test Strategy" in doc
    assert "`tests/test_calc.py`" in doc

    # 5. Security & Verification
    assert "## 8. Security & Guardrail Considerations" in doc
    assert "## 9. Risks & Assumptions" in doc
    assert "## 10. Suggested Verification Commands" in doc
    assert "pytest tests/test_calc.py -v" in doc


def test_build_plan_document_with_json_string():
    """Verify build_plan_document parses serialized JSON string plans instead of displaying raw JSON."""
    raw_json = json.dumps({
        "summary": "Fix auth leak",
        "explanation": "Token exposed in logs",
        "steps": [
            {"step_number": 1, "action": "modify", "target_file": "auth.py", "description": "Redact token"}
        ],
    })

    doc = build_plan_document(raw_json, title="Fallback Title", plan_hash="1234567890abcdef")
    assert "# 📋 Implementation Plan: Fix auth leak" in doc
    assert "Token exposed in logs" in doc
    assert "1. **[MODIFY]** `auth.py`: Redact token" in doc
    assert not doc.startswith("{\"summary\"")


def test_build_plan_document_with_legacy_plan_schema():
    """Verify build_plan_document supports legacy Plan schema with intent and scope."""
    legacy_dict = {
        "intent": "Migrate database schema",
        "scope": "Apply migration v3 across users table",
        "version_id": "v2",
        "steps": [
            {"action": "create", "target_file": "migrations/0003.sql", "description": "Add index"}
        ],
        "requirements": [
            {"description": "Index added without lock contention"}
        ],
    }

    doc = build_plan_document(legacy_dict)
    assert "# 📋 Implementation Plan: Migrate database schema" in doc
    assert "> **Plan Version:** `v2`" in doc
    assert "Apply migration v3 across users table" in doc
    assert "1. **[CREATE]** `migrations/0003.sql`: Add index" in doc
    assert "- [ ] Index added without lock contention" in doc


def test_build_plan_document_with_empty_or_minimal_input():
    """Verify build_plan_document never returns bare hash or crashes on empty plan."""
    doc = build_plan_document(None, title="Sample Issue Title", plan_hash="deadbeef1234")
    assert "# 📋 Implementation Plan: Sample Issue Title" in doc
    assert "Frozen Hash:** `deadbeef`" in doc
    assert doc.strip() != "deadbeef1234"
