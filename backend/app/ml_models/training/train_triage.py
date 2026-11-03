"""Train baseline TF-IDF + LogisticRegression triage classifier.

Trains solely on train.jsonl (never reads test set), computes cross-validation
macro-F1, and serializes model pipeline and metadata to artifacts folder.
"""

from __future__ import annotations

import argparse
import collections
from datetime import datetime, timezone
import json
import os
import sys

import joblib
import numpy as np
import sklearn
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.pipeline import Pipeline

CLASSES = ["bug_fix", "small_feature", "test_writing", "out_of_scope"]

DEFAULT_TRAIN = "backend/app/ml_models/training/data/train.jsonl"
DEFAULT_ARTIFACTS_DIR = "backend/app/ml_models/artifacts"


def _load_jsonl(path: str) -> list[dict]:
    """Load JSON lines from path."""
    if not os.path.exists(path):
        return []
    records: list[dict] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def train_triage(
    train_path: str = DEFAULT_TRAIN,
    artifacts_dir: str = DEFAULT_ARTIFACTS_DIR,
    random_state: int = 42,
) -> tuple[Pipeline, dict]:
    """Train triage classifier pipeline and write model artifacts and metadata."""
    if not os.path.exists(train_path):
        sys.exit(f"Training data not found: {train_path}")

    records = _load_jsonl(train_path)
    if not records:
        sys.exit(f"Training data is empty: {train_path}")

    counts = collections.Counter(r.get("label", "") for r in records)
    for cls_name in CLASSES:
        if counts.get(cls_name, 0) < 2:
            sys.exit(
                f"Class '{cls_name}' has fewer than 2 examples ({counts.get(cls_name, 0)}). "
                f"Cannot train classifier."
            )

    texts = [r.get("text", "") for r in records]
    labels = [r.get("label", "") for r in records]

    # Pipeline: TF-IDF (1-2 grams, sublinear_tf, min_df=2, max_features=20000) + LogisticRegression
    # Adjust min_df to 1 if dataset is too small for min_df=2
    min_df = 2 if len(texts) >= 10 else 1

    pipeline = Pipeline([
        (
            "tfidf",
            TfidfVectorizer(
                ngram_range=(1, 2),
                sublinear_tf=True,
                min_df=min_df,
                max_features=20000,
            ),
        ),
        (
            "clf",
            LogisticRegression(
                class_weight="balanced",
                max_iter=1000,
                random_state=random_state,
            ),
        ),
    ])

    # 5-fold stratified CV (reduce if any class has fewer than 5 examples)
    min_class_count = min(counts[c] for c in CLASSES)
    n_splits = min(5, min_class_count)
    if n_splits < 5:
        print(
            f"Reducing cross-validation folds to {n_splits} because "
            f"smallest class has {min_class_count} examples."
        )

    skf = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=random_state)
    scores = cross_val_score(pipeline, texts, labels, cv=skf, scoring="f1_macro")
    cv_macro_f1 = float(np.mean(scores))
    print(
        f"Cross-validation macro-F1 (measured on weak labels, not the test set): "
        f"{cv_macro_f1:.4f}"
    )

    # Fit on all training data
    pipeline.fit(texts, labels)

    # Save artifacts
    os.makedirs(artifacts_dir, exist_ok=True)
    model_path = os.path.join(artifacts_dir, "triage_pipeline.joblib")
    joblib.dump(pipeline, model_path)

    metadata = {
        "classes": CLASSES,
        "training_size": len(records),
        "per_class_counts": dict(counts),
        "sklearn_version": sklearn.__version__,
        "seed": random_state,
        "date": datetime.now(timezone.utc).isoformat(),
        "cv_macro_f1": cv_macro_f1,
    }
    metadata_path = os.path.join(artifacts_dir, "triage_metadata.json")
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    print(f"Model and metadata saved to {artifacts_dir}")
    return pipeline, metadata


def main(argv: list[str] | None = None) -> None:
    """CLI entry point for training."""
    parser = argparse.ArgumentParser(description="Train triage classifier.")
    parser.add_argument("--train", default=DEFAULT_TRAIN, help="Path to train.jsonl")
    parser.add_argument("--artifacts", default=DEFAULT_ARTIFACTS_DIR, help="Artifacts directory")
    args = parser.parse_args(argv)

    train_triage(
        train_path=args.train,
        artifacts_dir=args.artifacts,
    )


if __name__ == "__main__":
    main()
