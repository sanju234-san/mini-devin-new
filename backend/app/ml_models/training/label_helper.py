"""Labelling helper for triage classifier test set.

Provides commands to export unlabelled candidates from raw_issues.jsonl
and import validated human verdicts into curated/test_labels.jsonl.
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import random
import sys

from app.retrieval.query_transform import clean_issue_text

VALID_CLASSES = {"bug_fix", "small_feature", "test_writing", "out_of_scope"}

DEFAULT_RAW = "backend/app/ml_models/training/data/raw_issues.jsonl"
DEFAULT_TEST_LABELS = "backend/app/ml_models/training/curated/test_labels.jsonl"
DEFAULT_TO_LABEL = "backend/app/ml_models/training/data/to_label.jsonl"


def _load_jsonl(path: str) -> list[dict]:
    """Load JSON lines from path if file exists, else return empty list."""
    if not os.path.exists(path):
        return []
    records: list[dict] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def export_issues(
    raw_path: str = DEFAULT_RAW,
    test_labels_path: str = DEFAULT_TEST_LABELS,
    out_path: str = DEFAULT_TO_LABEL,
    n: int = 100,
    seed: int = 42,
) -> list[dict]:
    """Sample N issues from raw_issues stratified across GitHub labels."""
    raw_issues = _load_jsonl(raw_path)
    test_labels = _load_jsonl(test_labels_path)
    test_urls = {r.get("url") for r in test_labels if r.get("url")}

    # Exclude already-labelled URLs and handwritten examples (raw_issues only)
    eligible = [r for r in raw_issues if r.get("url") not in test_urls]

    # Stratify by GitHub label
    groups: dict[str, list[dict]] = collections.defaultdict(list)
    for item in eligible:
        label = item.get("label", "unknown")
        groups[label].append(item)

    rng = random.Random(seed)
    for group_items in groups.values():
        rng.shuffle(group_items)

    group_keys = sorted(groups.keys())
    sampled: list[dict] = []
    group_ptrs = {k: 0 for k in group_keys}

    while len(sampled) < n and any(group_ptrs[k] < len(groups[k]) for k in group_keys):
        for k in group_keys:
            if len(sampled) >= n:
                break
            if group_ptrs[k] < len(groups[k]):
                sampled.append(groups[k][group_ptrs[k]])
                group_ptrs[k] += 1

    # Format output rows (no GitHub label, empty verdict, cleaned body truncated to 800 chars)
    to_label_rows: list[dict] = []
    for item in sampled:
        cleaned_body = clean_issue_text(item.get("body", ""))[:800]
        to_label_rows.append({
            "url": item.get("url", ""),
            "repo": item.get("repo", ""),
            "number": item.get("number"),
            "title": item.get("title", ""),
            "body": cleaned_body,
            "verdict": "",
        })

    out_dir = os.path.dirname(out_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        for row in to_label_rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    print(f"Exported {len(to_label_rows)} issues to {out_path}")
    return to_label_rows


def import_labels(
    in_path: str = DEFAULT_TO_LABEL,
    test_labels_path: str = DEFAULT_TEST_LABELS,
) -> tuple[int, int, dict[str, int]]:
    """Import filled verdicts into test_labels.jsonl without duplicates."""
    rows = _load_jsonl(in_path)
    existing_items = _load_jsonl(test_labels_path)
    existing_urls = {r.get("url") for r in existing_items if r.get("url")}

    added_rows: list[dict] = []
    seen_urls: set[str] = set(existing_urls)
    rejected_count = 0

    for idx, row in enumerate(rows, 1):
        url = row.get("url", "")
        verdict = (row.get("verdict") or "").strip()

        if not verdict:
            print(f"Rejected row #{idx} ({url}): empty verdict")
            rejected_count += 1
            continue

        if verdict not in VALID_CLASSES:
            print(f"Rejected row #{idx} ({url}): invalid verdict '{verdict}'")
            rejected_count += 1
            continue

        if url in seen_urls:
            # Duplicate, do not append again
            continue

        seen_urls.add(url)
        added_rows.append({
            "repo": row.get("repo", ""),
            "number": row.get("number"),
            "url": url,
            "verdict": verdict,
        })

    # Append valid rows to test_labels_path
    out_dir = os.path.dirname(test_labels_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    with open(test_labels_path, "a", encoding="utf-8") as f:
        for r in added_rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    # Re-read total records to calculate total per class
    all_test_items = _load_jsonl(test_labels_path)
    class_totals = collections.Counter(r.get("verdict", "unknown") for r in all_test_items)

    print(f"\nImport Summary:")
    print(f"  Added: {len(added_rows)}")
    print(f"  Rejected: {rejected_count}")
    print("  Total per class in test labels:")
    for cls_name in sorted(VALID_CLASSES):
        print(f"    {cls_name}: {class_totals.get(cls_name, 0)}")

    return len(added_rows), rejected_count, dict(class_totals)


def main(argv: list[str] | None = None) -> None:
    """CLI for export and import commands."""
    parser = argparse.ArgumentParser(description="Triage labelling helper.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Export parser
    p_export = subparsers.add_parser("export", help="Export issues to label")
    p_export.add_argument("--raw", default=DEFAULT_RAW, help="Path to raw_issues.jsonl")
    p_export.add_argument("--test-labels", default=DEFAULT_TEST_LABELS, help="Path to test_labels.jsonl")
    p_export.add_argument("--out", default=DEFAULT_TO_LABEL, help="Path to to_label.jsonl output")
    p_export.add_argument("--n", type=int, default=100, help="Number of issues to export")
    p_export.add_argument("--seed", type=int, default=42, help="Random seed for stratification")

    # Import parser
    p_import = subparsers.add_parser("import", help="Import labelled issues")
    p_import.add_argument("--in", dest="in_file", default=DEFAULT_TO_LABEL, help="Path to filled to_label.jsonl")
    p_import.add_argument("--test-labels", default=DEFAULT_TEST_LABELS, help="Path to test_labels.jsonl")

    args = parser.parse_args(argv)

    if args.command == "export":
        export_issues(
            raw_path=args.raw,
            test_labels_path=args.test_labels,
            out_path=args.out,
            n=args.n,
            seed=args.seed,
        )
    elif args.command == "import":
        import_labels(
            in_path=args.in_file,
            test_labels_path=args.test_labels,
        )


if __name__ == "__main__":
    main()
