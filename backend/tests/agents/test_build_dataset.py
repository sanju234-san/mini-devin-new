"""Tests for build_dataset pipeline."""

import json
import pytest

from app.ml_models.training.build_dataset import build_datasets


def _write_jsonl(path, records):
    with open(path, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")


def _read_jsonl(path):
    with open(path, "r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def test_dedupe_by_url_and_hash(tmp_path):
    """Verify train set dedupes by url and by normalized title+body hash."""
    raw_path = tmp_path / "raw.jsonl"
    handwritten_path = tmp_path / "handwritten.jsonl"
    test_labels_path = tmp_path / "test_labels.jsonl"
    train_out = tmp_path / "train.jsonl"
    test_out = tmp_path / "test.jsonl"

    raw_data = [
        {"url": "https://gh.com/1", "title": "Crash on start", "body": "App crashes immediately.", "label": "bug_fix"},
        {"url": "https://gh.com/1", "title": "Different title", "body": "Different body", "label": "bug_fix"},  # Duplicate URL
        {"url": "https://gh.com/2", "title": "  CRASH   ON   START  ", "body": "app   crashes immediately.  ", "label": "bug_fix"},  # Duplicate hash
        {"url": "https://gh.com/3", "title": "Feature request", "body": "Please add dark mode.", "label": "small_feature"},
    ]
    _write_jsonl(raw_path, raw_data)
    _write_jsonl(handwritten_path, [])
    _write_jsonl(test_labels_path, [])

    train, _ = build_datasets(
        raw_path=str(raw_path),
        handwritten_path=str(handwritten_path),
        test_labels_path=str(test_labels_path),
        train_out=str(train_out),
        test_out=str(test_out),
    )

    # 1 and 3 are unique; duplicates 2nd (url) and 3rd (hash) are dropped
    assert len(train) == 2
    urls = {r["url"] for r in train}
    assert urls == {"https://gh.com/1", "https://gh.com/3"}


def test_leakage_guard(tmp_path):
    """Verify leakage guard removes test urls and hash matches from training."""
    raw_path = tmp_path / "raw.jsonl"
    handwritten_path = tmp_path / "handwritten.jsonl"
    test_labels_path = tmp_path / "test_labels.jsonl"
    train_out = tmp_path / "train.jsonl"
    test_out = tmp_path / "test.jsonl"

    raw_data = [
        {"url": "https://gh.com/test-1", "title": "Test issue", "body": "Exact text of test issue.", "label": "bug_fix"},
        {"url": "https://gh.com/train-leak", "title": "  TEST ISSUE  ", "body": "exact text of test issue.  ", "label": "bug_fix"},  # Same text hash
        {"url": "https://gh.com/train-clean", "title": "Clean train issue", "body": "Completely separate text.", "label": "bug_fix"},
    ]
    test_labels_data = [
        {"repo": "org/repo", "number": 1, "url": "https://gh.com/test-1", "verdict": "bug_fix"}
    ]

    _write_jsonl(raw_path, raw_data)
    _write_jsonl(handwritten_path, [])
    _write_jsonl(test_labels_path, test_labels_data)

    train, test = build_datasets(
        raw_path=str(raw_path),
        handwritten_path=str(handwritten_path),
        test_labels_path=str(test_labels_path),
        train_out=str(train_out),
        test_out=str(test_out),
    )

    assert len(test) == 1
    assert test[0]["url"] == "https://gh.com/test-1"

    # Both https://gh.com/test-1 and https://gh.com/train-leak must be removed from train
    assert len(train) == 1
    assert train[0]["url"] == "https://gh.com/train-clean"


def test_verdict_overrides_github_label_in_test(tmp_path):
    """Verify test set uses human verdict, never the GitHub label."""
    raw_path = tmp_path / "raw.jsonl"
    handwritten_path = tmp_path / "handwritten.jsonl"
    test_labels_path = tmp_path / "test_labels.jsonl"
    train_out = tmp_path / "train.jsonl"
    test_out = tmp_path / "test.jsonl"

    raw_data = [
        {"url": "https://gh.com/10", "title": "Documentation fix", "body": "Fix typo in docs.", "label": "bug_fix"},  # GitHub says bug_fix
    ]
    test_labels_data = [
        {"repo": "org/repo", "number": 10, "url": "https://gh.com/10", "verdict": "out_of_scope"}  # Human says out_of_scope
    ]

    _write_jsonl(raw_path, raw_data)
    _write_jsonl(handwritten_path, [])
    _write_jsonl(test_labels_path, test_labels_data)

    _, test = build_datasets(
        raw_path=str(raw_path),
        handwritten_path=str(handwritten_path),
        test_labels_path=str(test_labels_path),
        train_out=str(train_out),
        test_out=str(test_out),
    )

    assert len(test) == 1
    assert test[0]["label"] == "out_of_scope"
    assert test[0]["label"] != "bug_fix"


def test_warning_when_class_fewer_than_30_and_missing_test_file(tmp_path, capsys):
    """Verify warnings for missing test file and classes with fewer than 30 examples."""
    raw_path = tmp_path / "raw.jsonl"
    handwritten_path = tmp_path / "handwritten.jsonl"
    missing_test_labels = tmp_path / "nonexistent_test_labels.jsonl"
    train_out = tmp_path / "train.jsonl"
    test_out = tmp_path / "test.jsonl"

    raw_data = [
        {"url": f"https://gh.com/{i}", "title": f"Title {i}", "body": f"Description {i} content.", "label": "bug_fix"}
        for i in range(5)
    ]
    _write_jsonl(raw_path, raw_data)
    _write_jsonl(handwritten_path, [])

    train, test = build_datasets(
        raw_path=str(raw_path),
        handwritten_path=str(handwritten_path),
        test_labels_path=str(missing_test_labels),
        train_out=str(train_out),
        test_out=str(test_out),
    )

    captured = capsys.readouterr().out
    assert "Warning: test_labels.jsonl is empty or missing" in captured
    assert "fewer than 30 training examples" in captured
    assert len(train) == 5
    assert len(test) == 0


def test_empty_cleaned_text_dropped(tmp_path):
    """Verify issues whose text becomes empty after cleaning are dropped."""
    raw_path = tmp_path / "raw.jsonl"
    handwritten_path = tmp_path / "handwritten.jsonl"
    test_labels_path = tmp_path / "test_labels.jsonl"
    train_out = tmp_path / "train.jsonl"
    test_out = tmp_path / "test.jsonl"

    raw_data = [
        {"url": "https://gh.com/empty-1", "title": "   ", "body": "<!-- only a comment -->", "label": "bug_fix"},
        {"url": "https://gh.com/valid-1", "title": "Real title", "body": "Real issue body content.", "label": "bug_fix"},
    ]
    _write_jsonl(raw_path, raw_data)
    _write_jsonl(handwritten_path, [])
    _write_jsonl(test_labels_path, [])

    train, _ = build_datasets(
        raw_path=str(raw_path),
        handwritten_path=str(handwritten_path),
        test_labels_path=str(test_labels_path),
        train_out=str(train_out),
        test_out=str(test_out),
    )

    assert len(train) == 1
    assert train[0]["url"] == "https://gh.com/valid-1"


def test_missing_raw_file_exits(tmp_path):
    """Verify missing raw issues file causes exit with clear message."""
    missing_raw = tmp_path / "no_such_raw.jsonl"
    with pytest.raises(SystemExit):
        build_datasets(raw_path=str(missing_raw))
