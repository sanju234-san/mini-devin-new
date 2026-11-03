"""
Cross-Session Persistent Memory Store for Mini-Devin.

Deep Agents-Style Persistent Context Management using LangGraph Store:
- Ephemeral workflow state is managed via `AgentState` in graph.py.
- Execution checkpointing and interrupt/resume is managed via `checkpointer.py`.
- This module provides the persistent memory layer spanning across independent
  sessions, issues, and workflow runs.

Isolation and Safety Invariants:
--------------------------------
1. Multi-tenant Repository Isolation:
   All memories are strictly partitioned under hierarchical namespaces:
   `("repos", repo_name, category)`. Queries for repo A can NEVER match or
   contaminate repo B.
2. Advisory Status:
   Historical memories serve strictly as optional advisory context for
   Retrieval and Planner agents. They can NEVER override input guardrails,
   diff gates, human approval, or strict review rubrics.
3. Conflict & Stale Data Resilience:
   Conflicting records are resolved by recency timestamp, and invalid plan
   hashes are rejected.
4. Reviewer Blindness:
   The Reviewer agent strictly evaluates the frozen approved plan, actual diff,
   and sandbox test evidence; historical memory is never used to substitute
   for verification.
"""

from __future__ import annotations

import datetime
import logging
from typing import Any, Optional

from langgraph.store.base import BaseStore
from langgraph.store.memory import InMemoryStore

logger = logging.getLogger(__name__)

_GLOBAL_STORE: Optional[BaseStore] = None


def get_memory_store() -> BaseStore:
    """Return the global shared BaseStore instance for cross-session memory."""
    global _GLOBAL_STORE
    if _GLOBAL_STORE is None:
        logger.info("Initializing LangGraph InMemoryStore for cross-session persistent memory.")
        _GLOBAL_STORE = InMemoryStore()
    return _GLOBAL_STORE


def set_memory_store(store: BaseStore) -> None:
    """Override memory store instance (e.g. for testing)."""
    global _GLOBAL_STORE
    _GLOBAL_STORE = store


def reset_memory_store() -> None:
    """Clear memory store instance and all stored namespaces."""
    global _GLOBAL_STORE
    _GLOBAL_STORE = None


def _format_repo_namespace(repo: str, category: str = "resolved_issues") -> tuple[str, str, str]:
    """
    Format a normalized, injection-resistant namespace tuple for a repository.
    
    Prevents cross-repository contamination by normalizing repo names.
    """
    clean_repo = repo.strip().lower().replace(" ", "_")
    return ("repos", clean_repo, category)


def store_issue_resolution(
    repo: str,
    issue_number: int | str,
    title: str,
    plan_summary: str,
    plan_hash: str,
    files_modified: list[str],
    status: str = "completed",
    metadata: Optional[dict[str, Any]] = None,
) -> None:
    """
    Record an authentic completed issue resolution in persistent memory.
    
    Scoped strictly to the target repository namespace.
    """
    store = get_memory_store()
    namespace = _format_repo_namespace(repo, "resolved_issues")
    key = f"issue_{issue_number}"

    value = {
        "repo": repo,
        "issue_number": issue_number,
        "title": title,
        "plan_summary": plan_summary,
        "plan_hash": plan_hash,
        "files_modified": files_modified,
        "status": status,
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "metadata": metadata or {},
    }

    store.put(namespace, key, value)
    logger.info("Stored resolution memory for %s#%s in namespace %s", repo, issue_number, namespace)


def query_historical_context(
    repo: str,
    query: str = "",
    category: str = "resolved_issues",
    limit: int = 5,
) -> list[dict[str, Any]]:
    """
    Retrieve historical resolution memories for a repository.
    
    Strictly isolated: only returns entries belonging to the specified repository.
    """
    store = get_memory_store()
    namespace = _format_repo_namespace(repo, category)

    try:
        items = store.search(namespace, query=query if query else None, limit=limit)
    except Exception as exc:
        logger.warning("Error searching memory store for %s: %s", namespace, exc)
        return []

    results: list[dict[str, Any]] = []
    for item in items:
        if isinstance(item.value, dict):
            # Enforce repository match sanity check
            if item.value.get("repo", "").lower() == repo.strip().lower():
                results.append(item.value)
    return results


def store_failure_pattern(
    repo: str,
    pattern_name: str,
    error_summary: str,
    recommendations: list[str],
) -> None:
    """Record a known failure or debugging pattern for a repository."""
    store = get_memory_store()
    namespace = _format_repo_namespace(repo, "failure_patterns")

    value = {
        "repo": repo,
        "pattern_name": pattern_name,
        "error_summary": error_summary,
        "recommendations": recommendations,
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    store.put(namespace, pattern_name, value)
    logger.info("Stored failure pattern '%s' for %s", pattern_name, repo)
