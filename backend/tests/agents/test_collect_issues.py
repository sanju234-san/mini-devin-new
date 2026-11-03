"""Unit tests for GitHub issue collection script."""

import pytest

from app.ml_models.training.collect_issues import (
    dedupe,
    is_usable_issue,
    issue_record,
    main,
    map_labels,
    summarize,
)


def test_map_labels():
    """Verify single class mapping, no-match, ambiguous conflict, and case-insensitivity."""
    # Single class
    assert map_labels(["bug"]) == "bug_fix"
    assert map_labels(["enhancement"]) == "small_feature"
    assert map_labels(["testing"]) == "test_writing"
    assert map_labels(["docs"]) == "out_of_scope"

    # Case-insensitivity
    assert map_labels(["BUG"]) == "bug_fix"
    assert map_labels(["Type: Bug"]) == "bug_fix"
    assert map_labels(["FeAtUrE"]) == "small_feature"

    # No match
    assert map_labels(["unknown_label", "wontfix"]) is None
    assert map_labels([]) is None

    # Ambiguous (bug + enhancement) returns None
    assert map_labels(["bug", "enhancement"]) is None
    assert map_labels(["Defect", "documentation"]) is None


def test_is_usable_issue():
    """Verify PR rejection, bot rejection, missing/short body rejection, and valid issue acceptance."""
    # Pull request rejected
    assert not is_usable_issue({
        "pull_request": {},
        "body": "Valid body text with more than thirty characters.",
        "user": {"type": "User"},
    })

    # Bot rejected
    assert not is_usable_issue({
        "body": "Valid body text with more than thirty characters.",
        "user": {"type": "Bot"},
    })

    # Missing body rejected
    assert not is_usable_issue({
        "body": None,
        "user": {"type": "User"},
    })
    assert not is_usable_issue({"user": {"type": "User"}})

    # Short body (< 30 characters) rejected
    assert not is_usable_issue({
        "body": "Short text",
        "user": {"type": "User"},
    })

    # Normal item accepted
    assert is_usable_issue({
        "body": "This is a detailed issue description that is longer than thirty characters.",
        "user": {"type": "User"},
    })


def test_issue_record_truncation_and_keys():
    """Verify issue_record truncates body to 6000 and contains all required keys."""
    long_body = "x" * 7000
    item = {
        "number": 123,
        "html_url": "https://github.com/org/repo/issues/123",
        "title": "Bug in parser",
        "body": long_body,
        "labels": [{"name": "bug"}, {"name": "urgent"}],
        "created_at": "2026-01-01T12:00:00Z",
    }
    rec = issue_record("org/repo", item, "bug_fix")

    required_keys = {
        "repo",
        "number",
        "url",
        "title",
        "body",
        "labels",
        "label",
        "source",
        "created_at",
    }
    assert set(rec.keys()) == required_keys
    assert rec["repo"] == "org/repo"
    assert rec["number"] == 123
    assert rec["url"] == "https://github.com/org/repo/issues/123"
    assert rec["title"] == "Bug in parser"
    assert len(rec["body"]) == 6000
    assert rec["labels"] == ["bug", "urgent"]
    assert rec["label"] == "bug_fix"
    assert rec["source"] == "github"
    assert rec["created_at"] == "2026-01-01T12:00:00Z"


def test_dedupe():
    """Verify dedupe removes repeated url and repeated title+body hash, and keeps distinct records."""
    rec1 = {
        "url": "https://github.com/org/repo/issues/1",
        "title": "Issue 1",
        "body": "First issue body description.",
    }
    rec2_dup_url = {
        "url": "https://github.com/org/repo/issues/1",
        "title": "Different title",
        "body": "Different body text.",
    }
    rec3_dup_content = {
        "url": "https://github.com/org/repo/issues/2",
        "title": "  ISSUE   1  ",
        "body": "first   issue body description.  ",
    }
    rec4_distinct = {
        "url": "https://github.com/org/repo/issues/3",
        "title": "Unique issue",
        "body": "Completely different content here.",
    }

    records = [rec1, rec2_dup_url, rec3_dup_content, rec4_distinct]
    deduped = dedupe(records)

    assert len(deduped) == 2
    assert deduped[0]["url"] == "https://github.com/org/repo/issues/1"
    assert deduped[1]["url"] == "https://github.com/org/repo/issues/3"


def test_summarize():
    """Verify summarize contains each repo name and each class in output string."""
    records = [
        {"repo": "pallets/flask", "label": "bug_fix"},
        {"repo": "pallets/flask", "label": "small_feature"},
        {"repo": "psf/requests", "label": "bug_fix"},
        {"repo": "tiangolo/fastapi", "label": "out_of_scope"},
    ]
    summary = summarize(records)

    assert "pallets/flask" in summary
    assert "psf/requests" in summary
    assert "tiangolo/fastapi" in summary
    assert "bug_fix" in summary
    assert "small_feature" in summary
    assert "out_of_scope" in summary


def test_main_refuses_to_run_without_token(monkeypatch):
    """Verify main exits if GITHUB_TOKEN environment variable is not set."""
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    with pytest.raises(SystemExit):
        main([])
