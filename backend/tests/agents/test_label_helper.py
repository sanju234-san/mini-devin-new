"""Tests for label_helper export and import commands."""

import json
import pytest

from app.ml_models.training.label_helper import export_issues, import_labels


def _write_jsonl(path, records):
    with open(path, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")


def _read_jsonl(path):
    with open(path, "r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def test_export_stratified_and_reproducible(tmp_path):
    """Verify export is stratified across labels and reproducible with same seed."""
    raw_path = tmp_path / "raw.jsonl"
    test_labels_path = tmp_path / "test_labels.jsonl"
    out_path_1 = tmp_path / "to_label_1.jsonl"
    out_path_2 = tmp_path / "to_label_2.jsonl"

    raw_items = []
    classes = ["bug_fix", "small_feature", "test_writing", "out_of_scope"]
    for cls_name in classes:
        for i in range(10):
            raw_items.append({
                "url": f"https://gh.com/{cls_name}/{i}",
                "repo": "org/repo",
                "number": i,
                "title": f"Title {cls_name} {i}",
                "body": f"Description content for {cls_name} issue {i}.",
                "label": cls_name,
            })
    _write_jsonl(raw_path, raw_items)
    _write_jsonl(test_labels_path, [])

    # Export twice with same seed
    res1 = export_issues(
        raw_path=str(raw_path),
        test_labels_path=str(test_labels_path),
        out_path=str(out_path_1),
        n=12,
        seed=123,
    )
    res2 = export_issues(
        raw_path=str(raw_path),
        test_labels_path=str(test_labels_path),
        out_path=str(out_path_2),
        n=12,
        seed=123,
    )

    assert len(res1) == 12
    # Exact reproducibility
    assert res1 == res2

    # Check stratification: 12 sampled across 4 classes means 3 from each
    urls_by_cls = {c: 0 for c in classes}
    for r in res1:
        for c in classes:
            if c in r["url"]:
                urls_by_cls[c] += 1
    assert all(count == 3 for count in urls_by_cls.values())


def test_export_excludes_already_labelled_urls(tmp_path):
    """Verify export excludes URLs already in test_labels.jsonl."""
    raw_path = tmp_path / "raw.jsonl"
    test_labels_path = tmp_path / "test_labels.jsonl"
    out_path = tmp_path / "to_label.jsonl"

    raw_items = [
        {"url": "https://gh.com/already-labelled", "repo": "r", "number": 1, "title": "T1", "body": "B1", "label": "bug_fix"},
        {"url": "https://gh.com/unlabelled", "repo": "r", "number": 2, "title": "T2", "body": "B2", "label": "bug_fix"},
    ]
    test_labels_data = [
        {"repo": "r", "number": 1, "url": "https://gh.com/already-labelled", "verdict": "bug_fix"}
    ]
    _write_jsonl(raw_path, raw_items)
    _write_jsonl(test_labels_path, test_labels_data)

    res = export_issues(
        raw_path=str(raw_path),
        test_labels_path=str(test_labels_path),
        out_path=str(out_path),
        n=10,
    )

    assert len(res) == 1
    assert res[0]["url"] == "https://gh.com/unlabelled"


def test_export_has_no_github_label_and_empty_verdict(tmp_path):
    """Verify exported records omit the GitHub label and have an empty verdict."""
    raw_path = tmp_path / "raw.jsonl"
    test_labels_path = tmp_path / "test_labels.jsonl"
    out_path = tmp_path / "to_label.jsonl"

    raw_items = [
        {"url": "https://gh.com/item-1", "repo": "org/repo", "number": 1, "title": "Title 1", "body": "Body 1", "label": "bug_fix"},
    ]
    _write_jsonl(raw_path, raw_items)
    _write_jsonl(test_labels_path, [])

    res = export_issues(
        raw_path=str(raw_path),
        test_labels_path=str(test_labels_path),
        out_path=str(out_path),
        n=5,
    )

    assert len(res) == 1
    row = res[0]
    # No GitHub label key to prevent anchoring
    assert "label" not in row
    # Empty verdict, never pre-filled
    assert row["verdict"] == ""
    # Standard fields present
    assert set(row.keys()) == {"url", "repo", "number", "title", "body", "verdict"}


def test_import_rejects_invalid_and_empty_verdicts(tmp_path):
    """Verify import rejects rows with invalid or missing verdicts."""
    in_path = tmp_path / "to_label.jsonl"
    test_labels_path = tmp_path / "test_labels.jsonl"

    to_label_data = [
        {"url": "https://gh.com/valid", "repo": "r", "number": 1, "verdict": "bug_fix"},
        {"url": "https://gh.com/invalid-class", "repo": "r", "number": 2, "verdict": "not_a_valid_class"},
        {"url": "https://gh.com/empty-verdict", "repo": "r", "number": 3, "verdict": ""},
        {"url": "https://gh.com/none-verdict", "repo": "r", "number": 4, "verdict": None},
    ]
    _write_jsonl(in_path, to_label_data)
    _write_jsonl(test_labels_path, [])

    added, rejected, _ = import_labels(
        in_path=str(in_path),
        test_labels_path=str(test_labels_path),
    )

    assert added == 1
    assert rejected == 3

    saved = _read_jsonl(test_labels_path)
    assert len(saved) == 1
    assert saved[0]["url"] == "https://gh.com/valid"
    assert saved[0]["verdict"] == "bug_fix"


def test_import_does_not_append_duplicates(tmp_path):
    """Verify import skips duplicate URLs and does not append them again."""
    in_path = tmp_path / "to_label.jsonl"
    test_labels_path = tmp_path / "test_labels.jsonl"

    to_label_data = [
        {"url": "https://gh.com/dup", "repo": "r", "number": 1, "verdict": "small_feature"},
    ]
    _write_jsonl(in_path, to_label_data)
    _write_jsonl(test_labels_path, [])

    added1, _, _ = import_labels(in_path=str(in_path), test_labels_path=str(test_labels_path))
    assert added1 == 1

    # Second import with the same URL
    added2, _, _ = import_labels(in_path=str(in_path), test_labels_path=str(test_labels_path))
    assert added2 == 0

    saved = _read_jsonl(test_labels_path)
    assert len(saved) == 1


def test_no_verdict_ever_filled_automatically(tmp_path):
    """Verify that no verdict is ever automatically filled during export."""
    raw_path = tmp_path / "raw.jsonl"
    test_labels_path = tmp_path / "test_labels.jsonl"
    out_path = tmp_path / "to_label.jsonl"

    raw_items = [
        {"url": f"https://gh.com/{i}", "repo": "r", "number": i, "title": f"T{i}", "body": f"B{i}", "label": "bug_fix"}
        for i in range(20)
    ]
    _write_jsonl(raw_path, raw_items)
    _write_jsonl(test_labels_path, [])

    exported = export_issues(
        raw_path=str(raw_path),
        test_labels_path=str(test_labels_path),
        out_path=str(out_path),
        n=15,
    )

    for item in exported:
        assert item["verdict"] == "", "Verdict was automatically filled!"
