"""
Fine-tune DistilBERT Sequence Classifier for Mini-Devin Issue Triage.

Fine-tunes 'distilbert-base-uncased' on train.jsonl (with 45 curated additions)
and rigorously evaluates on held-out test.jsonl against established promotion gates.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from typing import Any

import numpy as np
import torch
from torch.utils.data import DataLoader, Dataset
from transformers import (
    AutoModelForSequenceClassification,
    AutoTokenizer,
    get_linear_schedule_with_warmup,
)
import os
import sys

# Ensure backend and root are on sys.path
sys.path.extend([os.path.abspath("backend"), os.path.abspath(".")])

from evaluation.metrics import (
    HISTORICAL_BASELINE,
    TRIAGE_CLASSES,
    compute_classification_metrics,
    evaluate_model_promotion,
)

logger = logging.getLogger(__name__)

DEFAULT_TRAIN = "backend/app/ml_models/training/data/train.jsonl"
DEFAULT_TEST = "backend/app/ml_models/training/data/test.jsonl"
DEFAULT_ARTIFACTS_DIR = "backend/app/ml_models/artifacts"
MODEL_NAME = "distilbert-base-uncased"

LABEL2ID = {cls: idx for idx, cls in enumerate(TRIAGE_CLASSES)}
ID2LABEL = {idx: cls for idx, cls in enumerate(TRIAGE_CLASSES)}


class IssueDataset(Dataset):
    """PyTorch Dataset for GitHub Issue texts and labels."""

    def __init__(self, records: list[dict], tokenizer, max_length: int = 256):
        self.texts = [r.get("text", "") for r in records]
        self.labels = [LABEL2ID[r["label"]] for r in records if r.get("label") in LABEL2ID]
        self.tokenizer = tokenizer
        self.max_length = max_length

    def __len__(self) -> int:
        return len(self.texts)

    def __getitem__(self, idx: int) -> dict[str, torch.Tensor]:
        encoding = self.tokenizer(
            self.texts[idx],
            truncation=True,
            padding="max_length",
            max_length=self.max_length,
            return_tensors="pt",
        )
        item = {key: val.squeeze(0) for key, val in encoding.items()}
        item["labels"] = torch.tensor(self.labels[idx], dtype=torch.long)
        return item


def load_jsonl(path: str) -> list[dict]:
    records: list[dict] = []
    if not os.path.exists(path):
        return records
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def train_distilbert(
    train_path: str = DEFAULT_TRAIN,
    test_path: str = DEFAULT_TEST,
    artifacts_dir: str = DEFAULT_ARTIFACTS_DIR,
    epochs: int = 4,
    batch_size: int = 16,
    lr: float = 3e-5,
    seed: int = 42,
) -> dict[str, Any]:
    """Train and evaluate DistilBERT on held-out test split."""
    torch.manual_seed(seed)
    np.random.seed(seed)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Using device: {device}")

    train_records = load_jsonl(train_path)
    test_records = load_jsonl(test_path)

    if not train_records:
        sys.exit(f"Training data not found or empty: {train_path}")
    if not test_records:
        sys.exit(f"Test data not found or empty: {test_path}")

    print(f"Training set: {len(train_records)} issues")
    print(f"Held-out test set: {len(test_records)} issues")

    # Training-only minority class augmentation (strictly never touches held-out test split)
    from evaluation.metrics import verify_evaluation_split_integrity
    split_info = verify_evaluation_split_integrity(train_records, test_records)
    print("Split integrity check (raw):", split_info)
    if not split_info["is_clean"]:
        sys.exit(f"Split contamination detected! URL overlap: {split_info['url_overlap_count']}")

    tw_train = [r for r in train_records if r.get("label") == "test_writing"]
    augmented_train = list(train_records)
    if tw_train:
        for r in tw_train:
            augmented_train.append({"text": r["text"], "label": "test_writing"})
            augmented_train.append({"text": f"Test writing / coverage request: {r['text']}", "label": "test_writing"})
    train_records = augmented_train
    print(f"Training set after training-only minority augmentation: {len(train_records)} issues")

    print(f"Loading tokenizer & pretrained weights for '{MODEL_NAME}'...")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    model = AutoModelForSequenceClassification.from_pretrained(
        MODEL_NAME,
        num_labels=len(TRIAGE_CLASSES),
        id2label=ID2LABEL,
        label2id=LABEL2ID,
    )
    model.to(device)

    train_dataset = IssueDataset(train_records, tokenizer)
    test_dataset = IssueDataset(test_records, tokenizer)

    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)
    test_loader = DataLoader(test_dataset, batch_size=batch_size, shuffle=False)

    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=0.01)
    total_steps = len(train_loader) * epochs
    scheduler = get_linear_schedule_with_warmup(
        optimizer,
        num_warmup_steps=int(total_steps * 0.1),
        num_training_steps=total_steps,
    )

    # Class-weighted loss to address imbalance
    class_counts = [0] * len(TRIAGE_CLASSES)
    for r in train_records:
        if r.get("label") in LABEL2ID:
            class_counts[LABEL2ID[r["label"]]] += 1
    total_samples = sum(class_counts)
    class_weights = [total_samples / (len(TRIAGE_CLASSES) * max(1, c)) for c in class_counts]
    tw_idx = LABEL2ID.get("test_writing", 2)
    class_weights[tw_idx] *= 1.3
    weight_tensor = torch.tensor(class_weights, dtype=torch.float32).to(device)
    loss_fn = torch.nn.CrossEntropyLoss(weight=weight_tensor)

    print("\n--- Starting DistilBERT Fine-Tuning ---")
    start_time = time.time()
    for epoch in range(1, epochs + 1):
        model.train()
        running_loss = 0.0
        for batch in train_loader:
            optimizer.zero_grad()
            input_ids = batch["input_ids"].to(device)
            attention_mask = batch["attention_mask"].to(device)
            labels = batch["labels"].to(device)

            outputs = model(input_ids=input_ids, attention_mask=attention_mask)
            logits = outputs.logits
            loss = loss_fn(logits, labels)
            loss.backward()

            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            scheduler.step()
            running_loss += loss.item()

        avg_loss = running_loss / len(train_loader)
        print(f"Epoch {epoch}/{epochs} | Training Loss: {avg_loss:.4f}")

    train_duration = time.time() - start_time
    print(f"Training completed in {train_duration:.1f}s")

    # Evaluation on held-out test set
    print("\n--- Evaluating on Held-Out Test Set (92 samples) ---")
    model.eval()
    all_preds: list[int] = []
    all_labels: list[int] = []

    with torch.no_grad():
        for batch in test_loader:
            input_ids = batch["input_ids"].to(device)
            attention_mask = batch["attention_mask"].to(device)
            labels = batch["labels"].to(device)

            outputs = model(input_ids=input_ids, attention_mask=attention_mask)
            preds = torch.argmax(outputs.logits, dim=1)
            all_preds.extend(preds.cpu().tolist())
            all_labels.extend(labels.cpu().tolist())

    y_true_str = [ID2LABEL[idx] for idx in all_labels]
    y_pred_str = [ID2LABEL[idx] for idx in all_preds]

    candidate_metrics = compute_classification_metrics(y_true_str, y_pred_str, classes=TRIAGE_CLASSES)
    candidate_metrics["model_name"] = "DistilBERT Fine-Tuned"
    candidate_metrics["train_set_size"] = len(train_records)
    candidate_metrics["epochs"] = epochs
    candidate_metrics["batch_size"] = batch_size

    print("\n=== DistilBERT Held-Out Test Results ===")
    print(f"Accuracy:        {candidate_metrics['accuracy']:.4f}")
    print(f"Macro-Precision: {candidate_metrics['macro_precision']:.4f}")
    print(f"Macro-Recall:    {candidate_metrics['macro_recall']:.4f}")
    print(f"Macro-F1:        {candidate_metrics['macro_f1']:.4f}")
    print("\nPer-Class Breakdown:")
    for cls_name, m in candidate_metrics["per_class"].items():
        print(f"  {cls_name:<15} Precision: {m['precision']:.4f} | Recall: {m['recall']:.4f} | F1: {m['f1']:.4f} (Support: {m['support']})")

    # Compare against Baseline & Evaluate Promotion Gates
    promotion = evaluate_model_promotion(
        candidate_metrics=candidate_metrics,
        baseline_metrics=HISTORICAL_BASELINE,
    )

    print("\n=== Model Promotion Gate Assessment ===")
    print(f"Promote Candidate: {promotion['promote']}")
    print(f"Macro-F1 Delta:    {promotion['f1_delta']:+.4f} (Required: >= +0.05)")
    print(f"test_writing Recall: {promotion['candidate_test_writing_recall']:.2%} (Required: >= 40.0%)")
    for gate, passed in promotion["gates"].items():
        print(f"  - Gate '{gate}': {'PASSED' if passed else 'FAILED'}")

    if promotion["rejection_reasons"]:
        print("\nRejection Reasons:")
        for r in promotion["rejection_reasons"]:
            print(f"  * {r}")

    # Determine artifact save path based on promotion
    if promotion["promote"]:
        out_model_dir = os.path.join(artifacts_dir, "distilbert_promoted")
        decision_label = "PROMOTED"
    else:
        out_model_dir = os.path.join(artifacts_dir, "distilbert_candidate")
        decision_label = "RETAIN_BASELINE"

    os.makedirs(out_model_dir, exist_ok=True)
    model.save_pretrained(out_model_dir)
    tokenizer.save_pretrained(out_model_dir)

    results_file = os.path.join(out_model_dir, "evaluation_comparison.json")
    save_payload = {
        "decision": decision_label,
        "candidate_metrics": candidate_metrics,
        "baseline_metrics": HISTORICAL_BASELINE,
        "promotion_evaluation": promotion,
        "date": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    with open(results_file, "w", encoding="utf-8") as f:
        json.dump(save_payload, f, indent=2)

    print(f"\nModel artifacts and evaluation comparison saved to: {out_model_dir}")
    return save_payload


if __name__ == "__main__":
    train_distilbert()
