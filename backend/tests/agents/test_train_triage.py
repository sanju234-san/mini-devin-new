"""Tests for train_triage baseline trainer."""

import json
import joblib
import pytest

from app.ml_models.training.train_triage import train_triage, CLASSES


def _write_jsonl(path, records):
    with open(path, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")


def test_train_writes_artifacts_and_metadata_without_test_file(tmp_path, capsys):
    """Verify artifacts and metadata are written and test.jsonl is never accessed."""
    train_file = tmp_path / "train.jsonl"
    artifacts_dir = tmp_path / "artifacts"

    # 3 examples per class (total 12)
    records = []
    for cls_name in CLASSES:
        for i in range(3):
            records.append({
                "text": f"Issue text regarding {cls_name} number {i} with some key vocabulary words",
                "label": cls_name,
                "source": "github",
                "url": f"https://gh.com/{cls_name}/{i}",
            })
    _write_jsonl(train_file, records)

    # Note: test.jsonl does not exist in tmp_path and must never be needed
    pipeline, metadata = train_triage(
        train_path=str(train_file),
        artifacts_dir=str(artifacts_dir),
        random_state=42,
    )

    model_file = artifacts_dir / "triage_pipeline.joblib"
    metadata_file = artifacts_dir / "triage_metadata.json"

    assert model_file.exists()
    assert metadata_file.exists()

    loaded_pipeline = joblib.load(str(model_file))
    assert hasattr(loaded_pipeline, "predict")

    with open(metadata_file, "r", encoding="utf-8") as f:
        meta_data = json.load(f)

    assert meta_data["classes"] == CLASSES
    assert meta_data["training_size"] == 12
    assert "cv_macro_f1" in meta_data
    assert meta_data["seed"] == 42


def test_train_refuses_missing_file(tmp_path):
    """Verify training exits if train.jsonl is missing."""
    missing_train = tmp_path / "nonexistent.jsonl"
    with pytest.raises(SystemExit):
        train_triage(train_path=str(missing_train), artifacts_dir=str(tmp_path / "art"))


def test_train_refuses_fewer_than_2_examples(tmp_path):
    """Verify training exits if any class has fewer than 2 examples."""
    train_file = tmp_path / "train.jsonl"
    records = []
    for cls_name in CLASSES:
        # out_of_scope has only 1 example, others have 2
        count = 1 if cls_name == "out_of_scope" else 2
        for i in range(count):
            records.append({
                "text": f"Issue sample text for {cls_name} {i}",
                "label": cls_name,
            })
    _write_jsonl(train_file, records)

    with pytest.raises(SystemExit):
        train_triage(train_path=str(train_file), artifacts_dir=str(tmp_path / "art"))


def test_train_folds_reduced_for_small_classes(tmp_path, capsys):
    """Verify cross-validation folds are reduced when smallest class has < 5 examples."""
    train_file = tmp_path / "train.jsonl"
    artifacts_dir = tmp_path / "artifacts"

    # 2 examples per class
    records = []
    for cls_name in CLASSES:
        for i in range(2):
            records.append({
                "text": f"Sample problem description {cls_name} {i} for classification",
                "label": cls_name,
            })
    _write_jsonl(train_file, records)

    train_triage(train_path=str(train_file), artifacts_dir=str(artifacts_dir))
    captured = capsys.readouterr().out
    assert "Reducing cross-validation folds to 2" in captured
    assert "measured on weak labels, not the test set" in captured
