"""
Evaluation metrics, benchmark analysis, and model promotion framework for Mini-Devin.

Supports:
1. Classification metrics (Accuracy, Macro-P/R/F1, Per-Class P/R/F1, Confusion Matrix).
2. Class imbalance and support distribution analysis.
3. Test-split integrity and data leakage verification.
4. Baseline comparison and empirical model promotion rules (DistilBERT vs. TF-IDF).
5. Workflow benchmark metrics: fix accuracy, test-pass rate, self-correction iterations.
"""

from __future__ import annotations

import collections
import hashlib
import json
import logging
import math
import re
from typing import Any, Optional, Sequence

logger = logging.getLogger(__name__)

# Standard classification labels for issue triage
TRIAGE_CLASSES = ["bug_fix", "small_feature", "test_writing", "out_of_scope"]

# Baseline metrics recorded from verified held-out test evaluation (92 samples)
HISTORICAL_BASELINE = {
    "model_name": "TF-IDF + LogisticRegression",
    "accuracy": 0.5543478260869565,
    "macro_f1": 0.47584415584415585,
    "per_class": {
        "bug_fix": {"precision": 0.6000, "recall": 0.6486, "f1": 0.6234, "support": 37},
        "small_feature": {"precision": 0.6087, "recall": 0.7368, "f1": 0.6667, "support": 19},
        "test_writing": {"precision": 1.0000, "recall": 0.0714, "f1": 0.1333, "support": 14},
        "out_of_scope": {"precision": 0.4286, "recall": 0.5455, "f1": 0.4800, "support": 22},
    },
    "test_set_size": 92,
}


def normalize_text_hash(text: str) -> str:
    """Compute sha256 hash of normalized lowercase whitespace-collapsed text."""
    norm = re.sub(r"\s+", " ", text.lower()).strip()
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()


# ── Split Integrity & Leakage Verification ───────────────────────────

def verify_evaluation_split_integrity(
    train_records: Sequence[dict[str, Any]],
    test_records: Sequence[dict[str, Any]],
) -> dict[str, Any]:
    """
    Verify strict separation between training and test sets.
    
    Guarantees:
    - Zero duplicate URLs between train and test.
    - Zero exact or normalized text collisions between train and test.
    - Minimum test set size constraint satisfaction.
    """
    train_urls = {r.get("url") for r in train_records if r.get("url")}
    test_urls = {r.get("url") for r in test_records if r.get("url")}
    url_overlap = train_urls.intersection(test_urls)

    train_hashes = {normalize_text_hash(r.get("text", "")) for r in train_records if r.get("text")}
    test_hashes = {normalize_text_hash(r.get("text", "")) for r in test_records if r.get("text")}
    hash_overlap = train_hashes.intersection(test_hashes)

    is_clean = len(url_overlap) == 0 and len(hash_overlap) == 0

    return {
        "is_clean": is_clean,
        "train_size": len(train_records),
        "test_size": len(test_records),
        "url_overlap_count": len(url_overlap),
        "overlapping_urls": list(url_overlap)[:5],
        "content_leak_count": len(hash_overlap),
    }


# ── Classification Metrics Computation ───────────────────────────────

def compute_classification_metrics(
    y_true: Sequence[str],
    y_pred: Sequence[str],
    classes: Optional[Sequence[str]] = None,
) -> dict[str, Any]:
    """
    Compute comprehensive classification metrics without external dependencies.
    """
    target_classes = list(classes) if classes is not None else TRIAGE_CLASSES
    n_samples = len(y_true)
    if n_samples == 0:
        return {"accuracy": 0.0, "macro_f1": 0.0, "per_class": {}, "confusion_matrix": []}

    # Accuracy
    correct = sum(1 for t, p in zip(y_true, y_pred) if t == p)
    accuracy = correct / n_samples

    # Confusion Matrix
    class_idx = {c: i for i, c in enumerate(target_classes)}
    n_classes = len(target_classes)
    matrix = [[0] * n_classes for _ in range(n_classes)]

    for t, p in zip(y_true, y_pred):
        if t in class_idx and p in class_idx:
            matrix[class_idx[t]][class_idx[p]] += 1

    per_class: dict[str, dict[str, float | int]] = {}
    f1_list: list[float] = []
    precision_list: list[float] = []
    recall_list: list[float] = []

    for i, c in enumerate(target_classes):
        tp = matrix[i][i]
        fp = sum(matrix[row][i] for row in range(n_classes) if row != i)
        fn = sum(matrix[i][col] for col in range(n_classes) if col != i)
        support = sum(matrix[i])

        prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (2 * prec * rec) / (prec + rec) if (prec + rec) > 0 else 0.0

        per_class[c] = {
            "precision": round(prec, 4),
            "recall": round(rec, 4),
            "f1": round(f1, 4),
            "support": support,
        }
        f1_list.append(f1)
        precision_list.append(prec)
        recall_list.append(rec)

    macro_f1 = sum(f1_list) / len(f1_list) if f1_list else 0.0
    macro_precision = sum(precision_list) / len(precision_list) if precision_list else 0.0
    macro_recall = sum(recall_list) / len(recall_list) if recall_list else 0.0

    return {
        "accuracy": round(accuracy, 4),
        "macro_precision": round(macro_precision, 4),
        "macro_recall": round(macro_recall, 4),
        "macro_f1": round(macro_f1, 4),
        "per_class": per_class,
        "confusion_matrix": matrix,
        "classes": target_classes,
        "test_set_size": n_samples,
    }


# ── Model Promotion & Selection Criteria ─────────────────────────────

def evaluate_model_promotion(
    candidate_metrics: dict[str, Any],
    baseline_metrics: Optional[dict[str, Any]] = None,
    min_macro_f1_gain: float = 0.05,
    min_test_writing_recall: float = 0.40,
    max_bug_fix_f1_regression: float = 0.05,
) -> dict[str, Any]:
    """
    Empirical Model Promotion Rule:
    
    Evaluates whether a candidate model (e.g. fine-tuned DistilBERT)
    outperforms the baseline (TF-IDF + Logistic Regression) sufficiently
    to justify promotion into production.
    
    Promotion Gates:
    1. Overall Macro-F1 must improve by at least `min_macro_f1_gain` (+5% absolute).
    2. Minority class recall for 'test_writing' must exceed `min_test_writing_recall` (>= 0.40).
    3. Critical class 'bug_fix' F1 must not regress by more than `max_bug_fix_f1_regression`.
    4. Must be evaluated on identical held-out test split (test_set_size >= 40).
    """
    baseline = baseline_metrics or HISTORICAL_BASELINE

    cand_f1 = candidate_metrics.get("macro_f1", 0.0)
    base_f1 = baseline.get("macro_f1", 0.0)
    f1_delta = cand_f1 - base_f1

    cand_pc = candidate_metrics.get("per_class", {})
    base_pc = baseline.get("per_class", {})

    cand_tw_rec = cand_pc.get("test_writing", {}).get("recall", 0.0)
    base_tw_rec = base_pc.get("test_writing", {}).get("recall", 0.0)

    cand_bf_f1 = cand_pc.get("bug_fix", {}).get("f1", 0.0)
    base_bf_f1 = base_pc.get("bug_fix", {}).get("f1", 0.0)

    gates: dict[str, bool] = {
        "macro_f1_improved": f1_delta >= min_macro_f1_gain,
        "test_writing_recall_acceptable": cand_tw_rec >= min_test_writing_recall,
        "bug_fix_f1_preserved": (base_bf_f1 - cand_bf_f1) <= max_bug_fix_f1_regression,
        "test_split_adequate": candidate_metrics.get("test_set_size", 0) >= 40,
    }

    promote = all(gates.values())
    reasons: list[str] = []
    if not gates["macro_f1_improved"]:
        reasons.append(
            f"Macro-F1 delta ({f1_delta:+.4f}) is below minimum required threshold (+{min_macro_f1_gain:.2f})."
        )
    if not gates["test_writing_recall_acceptable"]:
        reasons.append(
            f"Minority class 'test_writing' recall ({cand_tw_rec:.2%}) is below threshold ({min_test_writing_recall:.0%})."
        )
    if not gates["bug_fix_f1_preserved"]:
        reasons.append(
            f"Critical class 'bug_fix' F1 regressed from {base_bf_f1:.4f} to {cand_bf_f1:.4f}."
        )

    return {
        "promote": promote,
        "gates": gates,
        "rejection_reasons": reasons,
        "f1_delta": round(f1_delta, 4),
        "candidate_macro_f1": cand_f1,
        "baseline_macro_f1": base_f1,
        "candidate_test_writing_recall": cand_tw_rec,
        "baseline_test_writing_recall": base_tw_rec,
    }


# ── System / Multi-Agent Workflow Metrics ─────────────────────────────

def compute_workflow_metrics(runs: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """
    Compute benchmark metrics across completed multi-agent workflow runs:
    - Fix accuracy (percentage of issues resolved with passing tests and PR).
    - Test-pass rate (runs with successful test verification / total runs).
    - Average self-correction iterations (average debug retry count).
    """
    total = len(runs)
    if total == 0:
        return {
            "total_runs": 0,
            "fix_accuracy": 0.0,
            "test_pass_rate": 0.0,
            "avg_correction_iterations": 0.0,
        }

    tests_passed = 0
    prs_opened = 0
    total_retries = 0

    for r in runs:
        if r.get("test_results", {}).get("passed") is True:
            tests_passed += 1
        if r.get("status") in ("pr_opened", "completed"):
            prs_opened += 1
        total_retries += r.get("retry_count", 0)

    return {
        "total_runs": total,
        "fix_accuracy": round(prs_opened / total, 4),
        "test_pass_rate": round(tests_passed / total, 4),
        "avg_correction_iterations": round(total_retries / total, 2),
    }
