"""GitHub issue collection script for triage classifier dataset.

Fetches public issues across defined repositories and maps issue labels
to target classes. Untrusted text is collected without evaluation.
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

CLASS_LABELS: dict[str, set[str]] = {
    "bug_fix": {"bug", "defect", "type: bug", "kind/bug"},
    "small_feature": {
        "enhancement",
        "feature",
        "feature request",
        "type: enhancement",
        "kind/feature",
    },
    "test_writing": {"tests", "testing", "test", "type: tests"},
    "out_of_scope": {
        "question",
        "documentation",
        "docs",
        "refactor",
        "refactoring",
        "epic",
        "breaking change",
        "support",
    },
}

# Label names differ per repository and the user will edit this list.
DEFAULT_REPOS: list[str] = [
    "pallets/flask",
    "psf/requests",
    "tiangolo/fastapi",
    "pandas-dev/pandas",
    "expressjs/express",
    "encode/httpx",
    "django/django",
    "scikit-learn/scikit-learn",
    "tornadoweb/tornado",
    "psf/black",
    "pydantic/pydantic",
    "pytest-dev/pytest",
]

API_CALLS_COUNT = 0


def _get_token() -> str:
    """Retrieve GitHub token from environment, exiting if missing."""
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        sys.exit("GITHUB_TOKEN environment variable is required")
    return token


def map_labels(label_names: list[str]) -> str | None:
    """Return mapped class if labels map to exactly one class, else None."""
    matched_classes: set[str] = set()
    for name in label_names:
        norm = name.strip().lower()
        for cls_name, label_set in CLASS_LABELS.items():
            if norm in label_set:
                matched_classes.add(cls_name)
    if len(matched_classes) == 1:
        return next(iter(matched_classes))
    return None


def is_usable_issue(item: dict) -> bool:
    """Check if issue is usable (not a PR, not a bot, body >= 30 chars)."""
    if "pull_request" in item:
        return False
    user = item.get("user")
    if isinstance(user, dict) and user.get("type") == "Bot":
        return False
    body = item.get("body")
    if not body or not isinstance(body, str) or len(body) < 30:
        return False
    return True


def issue_record(repo: str, item: dict, label: str) -> dict:
    """Construct an issue record dict with truncated body and standard keys."""
    raw_labels = item.get("labels", [])
    label_names = [
        lbl["name"] if isinstance(lbl, dict) else str(lbl) for lbl in raw_labels
    ]
    raw_body = item.get("body") or ""
    return {
        "repo": repo,
        "number": item.get("number"),
        "url": item.get("html_url") or item.get("url") or "",
        "title": item.get("title", ""),
        "body": raw_body[:6000],
        "labels": label_names,
        "label": label,
        "source": "github",
        "created_at": item.get("created_at", ""),
    }


def dedupe(records: list[dict]) -> list[dict]:
    """Drop records with repeated url or repeated normalized title+body hash."""
    seen_urls: set[str] = set()
    seen_hashes: set[str] = set()
    unique_records: list[dict] = []

    for rec in records:
        url = rec.get("url", "")
        if url and url in seen_urls:
            continue

        title = rec.get("title", "")
        body = rec.get("body", "")
        combined = f"{title} {body}".lower()
        norm = re.sub(r"\s+", " ", combined).strip()
        h = hashlib.sha256(norm.encode("utf-8")).hexdigest()
        if h in seen_hashes:
            continue

        if url:
            seen_urls.add(url)
        seen_hashes.add(h)
        unique_records.append(rec)

    return unique_records


def summarize(records: list[dict]) -> str:
    """Generate counts per repo and per class as a printable table."""
    repo_counts = collections.Counter(r.get("repo", "unknown") for r in records)
    class_counts = collections.Counter(r.get("label", "unknown") for r in records)

    lines = [
        "Repository Counts:",
        f"{'Repository':<35} {'Count':>6}",
        "-" * 42,
    ]
    for repo, count in sorted(repo_counts.items()):
        lines.append(f"{repo:<35} {count:>6}")

    lines.append("")
    lines.append("Class Counts:")
    lines.append(f"{'Class':<20} {'Count':>6}")
    lines.append("-" * 27)
    for cls_name, count in sorted(class_counts.items()):
        lines.append(f"{cls_name:<20} {count:>6}")

    lines.append("")
    lines.append(f"Total Issues: {len(records)}")
    return "\n".join(lines)


def _request_json(url: str, token: str) -> tuple[any, dict[str, str]]:
    """Execute GET request with retry and headers."""
    global API_CALLS_COUNT
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "mini-devin-dataset-collector/1.0",
    }
    req = urllib.request.Request(url, headers=headers)

    last_error: Exception | None = None
    for attempt in range(3):
        try:
            API_CALLS_COUNT += 1
            with urllib.request.urlopen(req, timeout=30) as resp:
                resp_headers = {k.lower(): v for k, v in resp.headers.items()}
                data = json.loads(resp.read().decode("utf-8"))
                return data, resp_headers
        except urllib.error.HTTPError as e:
            last_error = e
            resp_headers = {k.lower(): v for k, v in e.headers.items()}
            remaining = resp_headers.get("x-ratelimit-remaining")
            if remaining == "0":
                return [], resp_headers
            if attempt < 2:
                time.sleep(1.0)
        except Exception as e:
            last_error = e
            if attempt < 2:
                time.sleep(1.0)

    raise RuntimeError(f"Request failed after retries: {url}") from last_error


def fetch_labels(repo: str) -> list[str]:
    """Fetch label names for a repository."""
    token = _get_token()
    labels: list[str] = []
    page = 1
    max_pages = 5

    while page <= max_pages:
        url = f"https://api.github.com/repos/{repo}/labels?per_page=100&page={page}"
        try:
            data, headers = _request_json(url, token)
        except Exception:
            break

        if not isinstance(data, list) or not data:
            break

        for item in data:
            if isinstance(item, dict) and "name" in item:
                labels.append(item["name"])

        if len(data) < 100:
            break

        remaining = headers.get("x-ratelimit-remaining")
        if remaining == "0":
            reset_ts = headers.get("x-ratelimit-reset", "0")
            print(f"Rate limit reached for {repo}. Resets at {reset_ts}.")
            break

        page += 1
        time.sleep(0.5)

    return labels


def fetch_issues(repo: str, label_name: str, max_items: int = 40) -> list[dict]:
    """Fetch issues matching label_name up to max_items."""
    token = _get_token()
    issues: list[dict] = []
    page = 1
    max_pages = max(1, (max_items + 99) // 100) + 1
    encoded_label = urllib.parse.quote(label_name)

    while len(issues) < max_items and page <= max_pages:
        url = (
            f"https://api.github.com/repos/{repo}/issues?"
            f"labels={encoded_label}&state=all&per_page=100&page={page}"
        )
        try:
            data, headers = _request_json(url, token)
        except Exception:
            break

        if not isinstance(data, list) or not data:
            break

        for item in data:
            issues.append(item)
            if len(issues) >= max_items:
                break

        if len(data) < 100:
            break

        remaining = headers.get("x-ratelimit-remaining")
        if remaining == "0":
            reset_ts = headers.get("x-ratelimit-reset", "0")
            print(f"Rate limit reached for {repo}. Resets at {reset_ts}.")
            break

        page += 1
        time.sleep(0.5)

    return issues


def main(argv: list[str] | None = None) -> None:
    """CLI entry point for collecting issues."""
    parser = argparse.ArgumentParser(
        description="Collect GitHub issues for triage classifier."
    )
    parser.add_argument(
        "--repos",
        type=str,
        default=None,
        help="Comma-separated list of owner/repo",
    )
    parser.add_argument(
        "--max-per-class-per-repo",
        type=int,
        default=40,
        help="Max issues per class per repo",
    )
    parser.add_argument(
        "--out",
        type=str,
        default="backend/app/ml_models/training/data/raw_issues.jsonl",
        help="Output JSONL path",
    )
    args = parser.parse_args(argv)

    token = _get_token()

    repos = (
        [r.strip() for r in args.repos.split(",") if r.strip()]
        if args.repos
        else DEFAULT_REPOS
    )
    all_records: list[dict] = []

    for repo in repos:
        repo_labels = fetch_labels(repo)
        label_to_class: dict[str, str] = {}
        for lbl in repo_labels:
            cls_name = map_labels([lbl])
            if cls_name:
                label_to_class[lbl] = cls_name

        print(f"\nRepo: {repo}")
        for lbl, cls_name in sorted(label_to_class.items()):
            print(f"  Label '{lbl}' -> {cls_name}")

        class_counts: dict[str, int] = collections.defaultdict(int)
        for lbl, target_cls in label_to_class.items():
            if class_counts[target_cls] >= args.max_per_class_per_repo:
                continue
            needed = args.max_per_class_per_repo - class_counts[target_cls]
            raw_issues = fetch_issues(repo, lbl, max_items=needed)
            for item in raw_issues:
                if not is_usable_issue(item):
                    continue
                item_labels = [
                    l["name"] if isinstance(l, dict) else str(l)
                    for l in item.get("labels", [])
                ]
                item_class = map_labels(item_labels)
                if not item_class:
                    continue
                rec = issue_record(repo, item, item_class)
                all_records.append(rec)
                class_counts[item_class] += 1
                if class_counts[target_cls] >= args.max_per_class_per_repo:
                    break

    final_records = dedupe(all_records)

    out_path = args.out
    out_dir = os.path.dirname(out_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        for rec in final_records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    print("\n" + summarize(final_records))
    print(f"API calls made: {API_CALLS_COUNT}")


if __name__ == "__main__":
    main()
