"""Tests for triage_classifier loader and prediction."""

import json
import joblib
import pytest
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

from app.ml_models import triage_classifier
from app.ml_models.triage_classifier import (
    VALID_CLASSES,
    TriageModelNotFound,
    TriagePredictionError,
    classify,
    load_pipeline,
    reset_cache,
)


@pytest.fixture(autouse=True)
def clean_cache():
    """Ensure cache is reset before and after each test."""
    reset_cache()
    yield
    reset_cache()


class DummyPipeline:
    def __init__(self, pred_class):
        self.pred_class = pred_class

    def predict(self, texts):
        return [self.pred_class] * len(texts)


def _create_mock_artifacts(tmp_path, class_to_predict="bug_fix"):
    pipe = DummyPipeline(class_to_predict)
    classes = ["bug_fix", "small_feature", "test_writing", "out_of_scope"]

    pipeline_path = tmp_path / "triage_pipeline.joblib"
    metadata_path = tmp_path / "triage_metadata.json"

    joblib.dump(pipe, str(pipeline_path))
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump({"classes": classes, "seed": 42}, f)

    return str(pipeline_path), str(metadata_path)


def test_lazy_load():
    """Verify importing the module does not load the pipeline into cache."""
    assert triage_classifier._PIPELINE_CACHE is None
    assert triage_classifier._METADATA_CACHE is None


def test_missing_artifact_raises(tmp_path):
    """Verify missing pipeline artifact or metadata raises TriageModelNotFound."""
    nonexistent = tmp_path / "missing.joblib"
    with pytest.raises(TriageModelNotFound, match="Triage model pipeline not found"):
        load_pipeline(pipeline_path=str(nonexistent), metadata_path=str(tmp_path / "m.json"))

    pipe_path, _ = _create_mock_artifacts(tmp_path)
    with pytest.raises(TriageModelNotFound, match="Triage model metadata not found"):
        load_pipeline(pipeline_path=pipe_path, metadata_path=str(tmp_path / "nonexistent.json"))


def test_classify_returns_valid_class(tmp_path, monkeypatch):
    """Verify classify returns one of the four designated valid classes."""
    pipe_path, meta_path = _create_mock_artifacts(tmp_path, "bug_fix")
    monkeypatch.setattr(triage_classifier, "PIPELINE_PATH", pipe_path)
    monkeypatch.setattr(triage_classifier, "METADATA_PATH", meta_path)

    res = classify("Crash on startup with null pointer")
    assert res in VALID_CLASSES
    assert res == "bug_fix"


def test_unexpected_class_raises(tmp_path, monkeypatch):
    """Verify pipeline returning an unexpected class raises TriagePredictionError."""
    pipe_path, meta_path = _create_mock_artifacts(tmp_path, "unsupported_class")
    monkeypatch.setattr(triage_classifier, "PIPELINE_PATH", pipe_path)
    monkeypatch.setattr(triage_classifier, "METADATA_PATH", meta_path)

    with pytest.raises(TriagePredictionError, match="unexpected class 'unsupported_class'"):
        classify("Sample input text")


def test_cache_reuse_and_reset(tmp_path, monkeypatch):
    """Verify cached pipeline is reused across calls and cleared on reset_cache."""
    pipe_path, meta_path = _create_mock_artifacts(tmp_path, "small_feature")
    monkeypatch.setattr(triage_classifier, "PIPELINE_PATH", pipe_path)
    monkeypatch.setattr(triage_classifier, "METADATA_PATH", meta_path)

    p1 = load_pipeline()
    assert triage_classifier._PIPELINE_CACHE is not None

    p2 = load_pipeline()
    assert p1 is p2

    reset_cache()
    assert triage_classifier._PIPELINE_CACHE is None
