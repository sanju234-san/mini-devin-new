"""
Retrieval Agent Implementation for Mini-Devin.

Performs genuine repository indexing and snippet retrieval.
Preserves strict provenance, never fabricates file paths, code, or line ranges,
and accurately reports whether retrieval succeeded, yielded no results,
encountered an unindexed/missing checkout, or ran via lexical vs. vector search.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional

from app.agents.model_router import route
from app.agents.schemas import (
    AgentState,
    RetrievedContext,
    RetrievedSnippet,
    create_event,
)
from app.retrieval.indexer import RepositoryIndexer, resolve_permitted_repo_path
from app.retrieval.query_transform import transform_query

logger = logging.getLogger(__name__)

# Process-level cache for repository indexers to enable fast incremental indexing
_INDEXER_CACHE: dict[str, RepositoryIndexer] = {}


def get_or_create_indexer(repo_path: Path) -> RepositoryIndexer:
    """Retrieve or initialize a RepositoryIndexer for the given directory."""
    path_key = str(repo_path.resolve())
    if path_key not in _INDEXER_CACHE:
        _INDEXER_CACHE[path_key] = RepositoryIndexer(repo_path=repo_path)
    return _INDEXER_CACHE[path_key]


def retrieval_node(state: AgentState) -> dict[str, Any]:
    """
    Retrieval Agent Node: Locates real repository code context.

    Validates repository location, scans and chunks authentic repository files,
    extracts query keywords/identifiers, and returns genuine evidence.
    If repository checkout is not available, reports a truthful structured
    missing_checkout result without inventing synthetic code or filenames.
    """
    tier = route("retrieval")
    title = state.get("issue_title", "")
    body = state.get("issue_body", "")
    repo_raw = state.get("repo", "")

    # Context budgeting config
    char_budget = 30000

    logger.info("Executing Retrieval node [tier=%s] for repo='%s'", tier, repo_raw)

    # 1. Resolve local repository or snapshot directory safely
    snapshot_path = state.get("snapshot_path")
    repo_dir = resolve_permitted_repo_path(snapshot_path) if snapshot_path else None
    if repo_dir is None:
        repo_dir = resolve_permitted_repo_path(repo_raw)

    if repo_dir is None:
        # Truthful handling when repository checkout is not available locally
        logger.info(
            "Target repository checkout for '%s' is not available locally. "
            "Reporting truthful missing_checkout status.",
            repo_raw,
        )
        retrieved = RetrievedContext(
            files=[],
            snippets=[],
            summary=(
                f"Target repository '{repo_raw}' is not available as a local directory. "
                "Backend repository checkout service contract required."
            ),
            is_mock=False,
            retrieval_status="missing_checkout",
            retrieval_method="none",
            error_message=f"Local repository checkout not found for '{repo_raw}'.",
            char_budget=char_budget,
            chars_used=0,
        )
        event = create_event(
            agent_name="retrieval",
            event_type="retrieval_completed",
            status="success",
            message=f"Retrieval evaluated for '{repo_raw}' (checkout not found locally)",
            metadata={
                "tier": tier.value,
                "is_mock": False,
                "retrieval_status": "missing_checkout",
                "retrieval_method": "none",
                "files": [],
            },
        )
        return {
            "retrieved_context": retrieved.model_dump(mode="json"),
            "status": "retrieved",
            "current_agent": "retrieval",
            "events": [event],
        }

    # 2. Authentically index the repository
    indexer = get_or_create_indexer(repo_dir)
    force_reindex = bool(state.get("force_reindex", False))

    try:
        index_summary = indexer.index_repository(force=force_reindex)
    except Exception as exc:
        logger.exception("Failed to index repository at %s: %s", repo_dir, exc)
        retrieved = RetrievedContext(
            files=[],
            snippets=[],
            summary=f"Indexing failed for repository '{repo_raw}': {exc}",
            is_mock=False,
            retrieval_status="indexing_failed",
            retrieval_method=indexer.index.method_name,
            error_message=str(exc),
            char_budget=char_budget,
            chars_used=0,
        )
        event = create_event(
            agent_name="retrieval",
            event_type="retrieval_completed",
            status="failed",
            message=f"Repository indexing failed for '{repo_raw}': {exc}",
            metadata={
                "tier": tier.value,
                "is_mock": False,
                "retrieval_status": "indexing_failed",
                "retrieval_method": indexer.index.method_name,
                "files": [],
            },
        )
        return {
            "retrieved_context": retrieved.model_dump(mode="json"),
            "status": "retrieved",
            "current_agent": "retrieval",
            "events": [event],
        }

    if index_summary.get("indexed_files", 0) == 0:
        retrieved = RetrievedContext(
            files=[],
            snippets=[],
            summary=f"Repository '{repo_raw}' is empty or contains no indexable files.",
            is_mock=False,
            retrieval_status="no_results",
            retrieval_method=indexer.index.method_name,
            char_budget=char_budget,
            chars_used=0,
        )
        event = create_event(
            agent_name="retrieval",
            event_type="retrieval_completed",
            status="success",
            message=f"Repository '{repo_raw}' contains no indexable files",
            metadata={
                "tier": tier.value,
                "is_mock": False,
                "retrieval_status": "no_results",
                "retrieval_method": indexer.index.method_name,
                "files": [],
            },
        )
        return {
            "retrieved_context": retrieved.model_dump(mode="json"),
            "status": "retrieved",
            "current_agent": "retrieval",
            "events": [event],
        }

    # 3. Transform query into search terms
    cleaned_query = state.get("cleaned_query", "")
    query_info = transform_query(title=cleaned_query, body="")

    # 4. Search index for genuine snippets (dense HyDE vector if available, plus BM25 keywords)
    search_results = indexer.search(
        query=query_info.expanded_query,
        query_terms=query_info.search_terms,
        top_k=5,
        query_vector=query_info.query_vector,
    )

    if not search_results:
        retrieved = RetrievedContext(
            files=[],
            snippets=[],
            summary=f"No matching code snippets found in repository '{repo_raw}'.",
            is_mock=False,
            retrieval_status="no_results",
            retrieval_method=indexer.index.method_name,
            char_budget=char_budget,
            chars_used=0,
        )
        event = create_event(
            agent_name="retrieval",
            event_type="retrieval_completed",
            status="success",
            message=f"Retrieved 0 files (no matches found for query) via {indexer.index.method_name}",
            metadata={
                "tier": tier.value,
                "is_mock": False,
                "retrieval_status": "no_results",
                "retrieval_method": indexer.index.method_name,
                "files": [],
            },
        )
        return {
            "retrieved_context": retrieved.model_dump(mode="json"),
            "status": "retrieved",
            "current_agent": "retrieval",
            "events": [event],
        }

    # 5. Build authentic retrieved evidence with context budgeting
    final_snippets: list[RetrievedSnippet] = []
    current_chars = 0
    is_truncated = False
    is_omitted = False

    for i, r in enumerate(search_results):
        content = r.content
        content_len = len(content)

        if current_chars + content_len <= char_budget:
            # Fits perfectly
            final_snippets.append(
                RetrievedSnippet(
                    file_path=r.file_path,
                    start_line=r.start_line,
                    end_line=r.end_line,
                    content=content,
                    score=r.score,
                    score_type=r.score_type,
                )
            )
            current_chars += content_len
        else:
            # Does not fit
            is_omitted = True
            if i == 0:
                # First snippet is oversized: truncate it to fill the budget
                truncated_content = content[:char_budget]
                final_snippets.append(
                    RetrievedSnippet(
                        file_path=r.file_path,
                        start_line=r.start_line,
                        end_line=r.end_line,
                        content=truncated_content,
                        score=r.score,
                        score_type=r.score_type,
                    )
                )
                current_chars = len(truncated_content)
                is_truncated = True
            else:
                # Later snippet: skip it
                continue

    # Deduplicate candidate files from the final (budgeted) list while preserving rank order
    candidate_files = list(dict.fromkeys(s.file_path for s in final_snippets))

    summary_text = (
        f"Retrieved {len(final_snippets)} snippets across {len(candidate_files)} files "
        f"via {indexer.index.method_name}. "
        f"Budget: {char_budget}, Used: {current_chars}."
    )
    if state.get("snapshot_truncated"):
        reason = state.get("snapshot_truncation_reason", "limit_exceeded")
        summary_text += f" [WARNING: Repository snapshot was truncated ({reason}); search executed on partial codebase.]"

    retrieved = RetrievedContext(
        files=candidate_files,
        snippets=final_snippets,
        summary=summary_text,
        is_mock=False,
        retrieval_status="success",
        retrieval_method=indexer.index.method_name,
        char_budget=char_budget,
        chars_used=current_chars,
        is_truncated=is_truncated,
        is_omitted=is_omitted,
    )

    event = create_event(
        agent_name="retrieval",
        event_type="retrieval_completed",
        status="success",
        message=f"Retrieved {len(candidate_files)} files via {indexer.index.method_name}",
        metadata={
            "tier": tier.value,
            "is_mock": False,
            "retrieval_status": "success",
            "retrieval_method": indexer.index.method_name,
            "files": candidate_files,
            "snippet_count": len(final_snippets),
            "chars_used": current_chars,
            "is_truncated": is_truncated,
            "is_omitted": is_omitted,
        },
    )

    return {
        "retrieved_context": retrieved.model_dump(mode="json"),
        "status": "retrieved",
        "current_agent": "retrieval",
        "events": [event],
    }
