"""Tests for evaluate_triage evaluator."""

import json
import joblib
import pytest
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

from app.ml_models.training.evaluate_triage import evaluate_triage, CLASSES


def _write_jsonl(path, records):
    with open(path, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")


def _create_dummy_pipeline(model_path):
    # Train simple pipeline on small data
    train_texts = [
        "bug bug bug fix defect",
        "feature enhancement add capability",
        "test tests test_writing testing coverage",
        "question docs documentation out_of_scope support",
    ]
    train_labels = ["bug_fix", "small_feature", "test_writing", "out_of_scope"]
    pipe = Pipeline([
        ("tfidf", TfidfVectorizer(min_df=1)),
        ("clf", LogisticRegression(random_state=42)),
    ])
    pipe.fit(train_texts, train_labels)
    joblib.dump(pipe, str(model_path))
    return pipe


def test_evaluate_refuses_below_40_rows(tmp_path):
    """Verify evaluation refuses if test set has fewer than 40 rows."""
    model_path = tmp_path / "model.joblib"
    _create_dummy_pipeline(model_path)

    test_file = tmp_path / "test.jsonl"
    records = [{"text": "Sample text", "label": "bug_fix"} for _ in range(39)]
    _write_jsonl(test_file, records)

    with pytest.raises(SystemExit):
        evaluate_triage(
            model_path=str(model_path),
            test_path=str(test_file),
            metrics_out=str(tmp_path / "metrics.json"),
            min_test_rows=40,
        )


def test_evaluate_metrics_correct_and_json_written(tmp_path):
    """Verify metrics calculation and metrics.json serialization."""
    model_path = tmp_path / "model.joblib"
    _create_dummy_pipeline(model_path)

    test_file = tmp_path / "test.jsonl"
    metrics_out = tmp_path / "metrics.json"

    # Exactly 40 records: 10 per class with matching text
    records = []
    text_map = {
        "bug_fix": "bug bug fix defect",
        "small_feature": "feature enhancement add capability",
        "test_writing": "test tests testing coverage",
        "out_of_scope": "question docs documentation support",
    }
    for cls_name in CLASSES:
        for i in range(10):
            records.append({
                "text": text_map[cls_name],
                "label": cls_name,
                "url": f"https://gh.com/{cls_name}/{i}",
            })
    _write_jsonl(test_file, records)

    metrics = evaluate_triage(
        model_path=str(model_path),
        test_path=str(test_file),
        metrics_out=str(metrics_out),
        min_test_rows=40,
    )

    assert metrics_out.exists()
    assert metrics["test_set_size"] == 40
    assert "accuracy" in metrics
    assert "macro_f1" in metrics
    assert "confusion_matrix" in metrics
    assert set(metrics["per_class"].keys()) == set(CLASSES)

    # Every class has support 10
    for cls_name in CLASSES:
        assert metrics["per_class"][cls_name]["support"] == 10


def test_evaluate_low_support_warning(tmp_path, capsys):
    """Verify one-line warning printed if any class has fewer than 5 test examples."""
    model_path = tmp_path / "model.joblib"
    _create_dummy_pipeline(model_path)

    test_file = tmp_path / "test.jsonl"
    metrics_out = tmp_path / "metrics.json"

    # 40 rows: out_of_scope has only 2 rows (< 5), others have 12, 13, 13
    records = []
    for i in range(13):
        records.append({"text": "bug bug fix", "label": "bug_fix"})
    for i in range(13):
        records.append({"text": "feature add", "label": "small_feature"})
    for i in range(12):
        records.append({"text": "test testing", "label": "test_writing"})
    for i in range(2):
        records.append({"text": "docs question", "label": "out_of_scope"})

    _write_jsonl(test_file, records)

    evaluate_triage(
        model_path=str(model_path),
        test_path=str(test_file),
        metrics_out=str(metrics_out),
        min_test_rows=40,
    )

    captured = capsys.readouterr().out
    assert "Warning: class 'out_of_scope' has fewer than 5 test examples (2)." in captured
