"""Build training and test datasets for Triage classifier.

Joins raw GitHub issues with curated test labels, applies issue text cleaning,
enforces leakage guards, and outputs train.jsonl and test.jsonl.
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import os
import re
import sys

from app.retrieval.query_transform import clean_issue_text

CLASSES = ["bug_fix", "small_feature", "test_writing", "out_of_scope"]

DEFAULT_RAW = "backend/app/ml_models/training/data/raw_issues.jsonl"
DEFAULT_HANDWRITTEN = "backend/app/ml_models/training/curated/handwritten.jsonl"
DEFAULT_TEST_LABELS = "backend/app/ml_models/training/curated/test_labels.jsonl"
DEFAULT_TRAIN_OUT = "backend/app/ml_models/training/data/train.jsonl"
DEFAULT_TEST_OUT = "backend/app/ml_models/training/data/test.jsonl"


def _norm_hash(text: str) -> str:
    """Return sha256 hash of lowercased, whitespace-collapsed text."""
    norm = re.sub(r"\s+", " ", text.lower()).strip()
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()


def _load_jsonl(path: str) -> list[dict]:
    """Load JSON lines from file if exists, else return empty list."""
    if not os.path.exists(path):
        return []
    records: list[dict] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def _write_jsonl(path: str, records: list[dict]) -> None:
    """Write records to JSON lines file, creating directories if needed."""
    out_dir = os.path.dirname(path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def build_datasets(
    raw_path: str = DEFAULT_RAW,
    handwritten_path: str = DEFAULT_HANDWRITTEN,
    test_labels_path: str = DEFAULT_TEST_LABELS,
    train_out: str = DEFAULT_TRAIN_OUT,
    test_out: str = DEFAULT_TEST_OUT,
) -> tuple[list[dict], list[dict]]:
    """Build train and test datasets, enforcing deduplication and leakage guard."""
    if not os.path.exists(raw_path):
        sys.exit(f"Raw issues file not found: {raw_path}")

    raw_items = _load_jsonl(raw_path)
    handwritten_items = _load_jsonl(handwritten_path)
    test_label_items = _load_jsonl(test_labels_path)

    # 1. Process and clean raw issues
    cleaned_raw_by_url: dict[str, dict] = {}
    cleaned_raw_list: list[dict] = []

    for item in raw_items:
        raw_text = item.get("text")
        if raw_text is None:
            raw_text = f"{item.get('title', '')}\n{item.get('body', '')}"
        cleaned = clean_issue_text(raw_text)
        if not cleaned:
            continue
        rec = {
            "text": cleaned,
            "label": item.get("label", ""),
            "source": item.get("source", "github"),
            "url": item.get("url", ""),
            "raw_title": item.get("title", ""),
            "raw_body": item.get("body", ""),
        }
        cleaned_raw_list.append(rec)
        if rec["url"]:
            cleaned_raw_by_url[rec["url"]] = rec

    # 2. Build test set if test_labels exists and non-empty
    test_records: list[dict] = []
    test_urls: set[str] = set()
    test_hashes: set[str] = set()

    if not test_label_items:
        print("Warning: test_labels.jsonl is empty or missing. Building training set only.")
    else:
        for t_item in test_label_items:
            url = t_item.get("url", "")
            verdict = t_item.get("verdict", "")
            if url:
                test_urls.add(url)
            if url and url in cleaned_raw_by_url:
                raw_match = cleaned_raw_by_url[url]
                t_rec = {
                    "text": raw_match["text"],
                    "label": verdict,
                    "source": "github",
                    "url": url,
                }
                test_records.append(t_rec)
                test_hashes.add(_norm_hash(raw_match["text"]))

    # 3. Clean handwritten items
    cleaned_handwritten: list[dict] = []
    for h_item in handwritten_items:
        raw_text = h_item.get("text")
        if raw_text is None:
            raw_text = f"{h_item.get('title', '')}\n{h_item.get('body', '')}"
        cleaned = clean_issue_text(raw_text)
        if not cleaned:
            continue
        cleaned_handwritten.append({
            "text": cleaned,
            "label": h_item.get("label", ""),
            "source": h_item.get("source", "handwritten"),
            "url": h_item.get("url", ""),
            "raw_title": h_item.get("title", ""),
            "raw_body": h_item.get("body", ""),
        })

    # 4. Leakage guard & deduplication for training set
    candidates = cleaned_raw_list + cleaned_handwritten
    train_records: list[dict] = []
    seen_urls: set[str] = set()
    seen_hashes: set[str] = set()

    for cand in candidates:
        url = cand.get("url", "")
        # Leakage guard: remove every url in test_labels and text hash matching test
        if url and url in test_urls:
            continue
        h = _norm_hash(cand["text"])
        if h in test_hashes:
            continue

        # Dedupe by url and by normalised title+body hash
        if url and url in seen_urls:
            continue
        # Dedupe hash using title+body if available, else text
        if cand.get("raw_title") or cand.get("raw_body"):
            raw_title_body = f"{cand.get('raw_title', '')} {cand.get('raw_body', '')}"
            cand_hash = _norm_hash(raw_title_body)
        else:
            cand_hash = h

        if cand_hash in seen_hashes:
            continue

        if url:
            seen_urls.add(url)
        seen_hashes.add(cand_hash)

        train_records.append({
            "text": cand["text"],
            "label": cand["label"],
            "source": cand["source"],
            "url": cand["url"],
        })

    # 5. Write outputs
    _write_jsonl(train_out, train_records)
    _write_jsonl(test_out, test_records)

    # 6. Print per-class counts and warnings
    train_counts = collections.Counter(r.get("label", "unknown") for r in train_records)
    test_counts = collections.Counter(r.get("label", "unknown") for r in test_records)

    print("Training set class counts:")
    for cls_name in CLASSES:
        count = train_counts.get(cls_name, 0)
        print(f"  {cls_name}: {count}")

    print("\nTest set class counts:")
    for cls_name in CLASSES:
        count = test_counts.get(cls_name, 0)
        print(f"  {cls_name}: {count}")

    for cls_name in CLASSES:
        if train_counts.get(cls_name, 0) < 30:
            print(
                f"Warning: class '{cls_name}' has fewer than 30 training examples "
                f"({train_counts.get(cls_name, 0)})."
            )

    return train_records, test_records


def main(argv: list[str] | None = None) -> None:
    """CLI interface for building datasets."""
    parser = argparse.ArgumentParser(description="Build triage classifier datasets.")
    parser.add_argument("--raw", default=DEFAULT_RAW, help="Path to raw_issues.jsonl")
    parser.add_argument("--handwritten", default=DEFAULT_HANDWRITTEN, help="Path to handwritten.jsonl")
    parser.add_argument("--test-labels", default=DEFAULT_TEST_LABELS, help="Path to test_labels.jsonl")
    parser.add_argument("--train-out", default=DEFAULT_TRAIN_OUT, help="Path to train.jsonl output")
    parser.add_argument("--test-out", default=DEFAULT_TEST_OUT, help="Path to test.jsonl output")
    args = parser.parse_args(argv)

    build_datasets(
        raw_path=args.raw,
        handwritten_path=args.handwritten,
        test_labels_path=args.test_labels,
        train_out=args.train_out,
        test_out=args.test_out,
    )


if __name__ == "__main__":
    main()
