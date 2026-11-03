"""Evaluate triage classifier on hand-curated test dataset.

Computes precision, recall, F1, accuracy, confusion matrix, top-10
confidently wrong predictions, and serializes results to metrics.json.
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import sys

import joblib
import numpy as np
from sklearn.metrics import accuracy_score, confusion_matrix, precision_recall_fscore_support

CLASSES = ["bug_fix", "small_feature", "test_writing", "out_of_scope"]

DEFAULT_MODEL = "backend/app/ml_models/artifacts/triage_pipeline.joblib"
DEFAULT_TEST = "backend/app/ml_models/training/data/test.jsonl"
DEFAULT_METRICS_OUT = "backend/app/ml_models/training/data/metrics.json"


def _load_jsonl(path: str) -> list[dict]:
    """Load JSON lines from file."""
    if not os.path.exists(path):
        return []
    records: list[dict] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def evaluate_triage(
    model_path: str = DEFAULT_MODEL,
    test_path: str = DEFAULT_TEST,
    metrics_out: str = DEFAULT_METRICS_OUT,
    min_test_rows: int = 40,
) -> dict:
    """Evaluate trained triage classifier and write metrics to JSON."""
    if not os.path.exists(model_path):
        sys.exit(f"Model artifact not found: {model_path}")
    if not os.path.exists(test_path):
        sys.exit(f"Test data not found: {test_path}")

    records = _load_jsonl(test_path)
    if len(records) < min_test_rows:
        sys.exit(
            f"Test set has fewer than {min_test_rows} rows ({len(records)}). "
            f"Evaluation requires at least {min_test_rows} rows."
        )

    pipeline = joblib.load(model_path)

    texts = [r.get("text", "") for r in records]
    y_true = [r.get("label", "") for r in records]

    y_pred = pipeline.predict(texts)
    y_prob = pipeline.predict_proba(texts)

    # Class mappings in pipeline
    pipeline_classes = list(pipeline.classes_)

    acc = float(accuracy_score(y_true, y_pred))
    precisions, recalls, f1s, supports = precision_recall_fscore_support(
        y_true, y_pred, labels=CLASSES, zero_division=0
    )
    macro_precision = float(np.mean(precisions))
    macro_recall = float(np.mean(recalls))
    macro_f1 = float(np.mean(f1s))
    cm = confusion_matrix(y_true, y_pred, labels=CLASSES).tolist()

    per_class = {}
    print("\n--- Evaluation Metrics ---")
    print(f"Accuracy: {acc:.4f}")
    print(f"Macro-Precision: {macro_precision:.4f}")
    print(f"Macro-Recall: {macro_recall:.4f}")
    print(f"Macro-F1: {macro_f1:.4f}")
    print(f"Test Set Size: {len(records)}\n")
    print(f"{'Class':<15} {'Precision':>10} {'Recall':>10} {'F1':>10} {'Support':>10}")
    print("-" * 60)

    for i, cls_name in enumerate(CLASSES):
        sup = int(supports[i])
        per_class[cls_name] = {
            "precision": float(precisions[i]),
            "recall": float(recalls[i]),
            "f1": float(f1s[i]),
            "support": sup,
        }
        print(
            f"{cls_name:<15} {precisions[i]:>10.4f} {recalls[i]:>10.4f} "
            f"{f1s[i]:>10.4f} {sup:>10}"
        )
        if sup < 5:
            print(f"Warning: class '{cls_name}' has fewer than 5 test examples ({sup}).")

    # Confidently wrong predictions
    wrong_predictions = []
    for idx, (true_label, pred_label, probs, rec) in enumerate(
        zip(y_true, y_pred, y_prob, records)
    ):
        if true_label != pred_label:
            confidence = float(np.max(probs))
            snippet = (rec.get("title") or rec.get("text") or "")[:80]
            wrong_predictions.append({
                "url": rec.get("url", ""),
                "title_or_snippet": snippet,
                "true_label": true_label,
                "pred_label": pred_label,
                "confidence": confidence,
            })

    wrong_predictions.sort(key=lambda x: x["confidence"], reverse=True)
    top_10_wrong = wrong_predictions[:10]

    if top_10_wrong:
        print("\n--- Top Confidently Wrong Predictions ---")
        for item in top_10_wrong:
            print(
                f"URL: {item['url']} | Conf: {item['confidence']:.3f} | "
                f"True: {item['true_label']} | Pred: {item['pred_label']} | "
                f"Text: {item['title_or_snippet']}"
            )

    metrics = {
        "accuracy": acc,
        "macro_precision": macro_precision,
        "macro_recall": macro_recall,
        "macro_f1": macro_f1,
        "per_class": per_class,
        "confusion_matrix": cm,
        "test_set_size": len(records),
        "classes": CLASSES,
    }

    out_dir = os.path.dirname(metrics_out)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    with open(metrics_out, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)

    print(f"\nMetrics written to {metrics_out}")
    return metrics


def main(argv: list[str] | None = None) -> None:
    """CLI entry point for evaluation."""
    parser = argparse.ArgumentParser(description="Evaluate triage classifier.")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Path to pipeline artifact")
    parser.add_argument("--test", default=DEFAULT_TEST, help="Path to test.jsonl")
    parser.add_argument("--out", default=DEFAULT_METRICS_OUT, help="Path to metrics.json")
    args = parser.parse_args(argv)

    evaluate_triage(
        model_path=args.model,
        test_path=args.test,
        metrics_out=args.out,
    )


if __name__ == "__main__":
    main()
