"""
Vector Store and Retrieval Index implementations for Mini-Devin.

Supports:
1. FAISSVectorStore: Dense vector index using FAISS (when installed).
2. LexicalIndex: Honest pure-Python BM25 lexical ranking index (when embedding
   dependencies are unavailable).
"""

from __future__ import annotations

import json
import logging
import math
import os
from pathlib import Path
import re
from typing import Any, Callable, NamedTuple, Optional, Sequence

logger = logging.getLogger(__name__)


class SearchResult(NamedTuple):
    """Ranked search result snippet from retrieval."""
    file_path: str
    start_line: int
    end_line: int
    content: str
    score: float
    score_type: str  # e.g. "faiss_cosine", "lexical_bm25"


class ChunkMetadata:
    """Metadata representing a chunked section of code."""

    def __init__(
        self,
        chunk_id: str,
        file_path: str,
        start_line: int,
        end_line: int,
        content: str,
        file_hash: str = "",
    ):
        self.chunk_id = chunk_id
        self.file_path = file_path
        self.start_line = start_line
        self.end_line = end_line
        self.content = content
        self.file_hash = file_hash

    def to_dict(self) -> dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "file_path": self.file_path,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "content": self.content,
            "file_hash": self.file_hash,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ChunkMetadata":
        return cls(
            chunk_id=data["chunk_id"],
            file_path=data["file_path"],
            start_line=data["start_line"],
            end_line=data["end_line"],
            content=data["content"],
            file_hash=data.get("file_hash", ""),
        )


# ── Honest Lexical BM25 Index (Pure Python Fallback) ─────────────────

_TOKEN_RE = re.compile(r"[A-Za-z0-9_]{2,}")


def tokenize(text: str) -> list[str]:
    """Tokenize code and text into lowercase words/identifiers."""
    return [t.lower() for t in _TOKEN_RE.findall(text)]


class LexicalIndex:
    """
    Pure-Python BM25 Lexical Index.
    
    Clearly and honestly labeled as lexical retrieval (NOT vector embeddings).
    Calculates Okapi BM25 scores over chunk text and identifiers.
    """

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.chunks: dict[str, ChunkMetadata] = {}  # chunk_id -> metadata
        self.doc_lengths: dict[str, int] = {}       # chunk_id -> token count
        self.avg_doc_length: float = 0.0
        self.inverted_index: dict[str, dict[str, int]] = {}  # term -> {chunk_id: count}
        self.file_to_chunks: dict[str, set[str]] = {}        # file_path -> {chunk_id}

    @property
    def method_name(self) -> str:
        return "lexical_bm25"

    def clear(self) -> None:
        self.chunks.clear()
        self.doc_lengths.clear()
        self.avg_doc_length = 0.0
        self.inverted_index.clear()
        self.file_to_chunks.clear()

    def remove_file(self, file_path: str) -> None:
        """Remove all chunks associated with a specific file."""
        chunk_ids = self.file_to_chunks.pop(file_path, set())
        for cid in chunk_ids:
            self.chunks.pop(cid, None)
            self.doc_lengths.pop(cid, None)
            # Remove from inverted index
            for term_dict in self.inverted_index.values():
                term_dict.pop(cid, None)
        self._recompute_avg_doc_len()

    def add_chunks(self, chunks: Sequence[ChunkMetadata]) -> None:
        """Add new code chunks to the index."""
        for chunk in chunks:
            # Overwrite if exists
            if chunk.chunk_id in self.chunks:
                self._remove_chunk_internal(chunk.chunk_id)

            tokens = tokenize(chunk.content) + tokenize(chunk.file_path) * 2
            self.chunks[chunk.chunk_id] = chunk
            self.doc_lengths[chunk.chunk_id] = len(tokens)
            self.file_to_chunks.setdefault(chunk.file_path, set()).add(chunk.chunk_id)

            counts: dict[str, int] = {}
            for t in tokens:
                counts[t] = counts.get(t, 0) + 1

            for term, count in counts.items():
                if term not in self.inverted_index:
                    self.inverted_index[term] = {}
                self.inverted_index[term][chunk.chunk_id] = count

        self._recompute_avg_doc_len()

    def _remove_chunk_internal(self, chunk_id: str) -> None:
        old_chunk = self.chunks.pop(chunk_id, None)
        self.doc_lengths.pop(chunk_id, None)
        if old_chunk and old_chunk.file_path in self.file_to_chunks:
            self.file_to_chunks[old_chunk.file_path].discard(chunk_id)
        for term_dict in self.inverted_index.values():
            term_dict.pop(chunk_id, None)

    def _recompute_avg_doc_len(self) -> None:
        total_len = sum(self.doc_lengths.values())
        total_docs = len(self.doc_lengths)
        self.avg_doc_length = (total_len / total_docs) if total_docs > 0 else 0.0

    def search(self, query: str, top_k: int = 5, query_terms: Optional[list[str]] = None) -> list[SearchResult]:
        """
        Search the lexical index using BM25 scoring.
        
        Returns SearchResult objects with score_type="lexical_bm25".
        """
        terms = query_terms if query_terms is not None else tokenize(query)
        if not terms or not self.chunks:
            return []

        num_docs = len(self.chunks)
        scores: dict[str, float] = {}

        for term in terms:
            term_lower = term.lower()
            postings = self.inverted_index.get(term_lower)
            if not postings:
                continue

            # IDF calculation with smoothing
            df = len(postings)
            idf = math.log(1.0 + (num_docs - df + 0.5) / (df + 0.5))
            if idf <= 0.0:
                idf = 0.01

            for chunk_id, tf in postings.items():
                doc_len = self.doc_lengths.get(chunk_id, 1)
                avg_dl = self.avg_doc_length or 1.0
                denom = tf + self.k1 * (1.0 - self.b + self.b * (doc_len / avg_dl))
                term_score = idf * ((tf * (self.k1 + 1.0)) / denom)
                scores[chunk_id] = scores.get(chunk_id, 0.0) + term_score

        if not scores:
            return []

        ranked_ids = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_k]
        results: list[SearchResult] = []
        for cid, score in ranked_ids:
            chunk = self.chunks[cid]
            results.append(
                SearchResult(
                    file_path=chunk.file_path,
                    start_line=chunk.start_line,
                    end_line=chunk.end_line,
                    content=chunk.content,
                    score=round(score, 4),
                    score_type="lexical_bm25",
                )
            )
        return results

    def save(self, filepath: str | Path) -> None:
        """Persist index state to JSON."""
        data = {
            "version": 1,
            "k1": self.k1,
            "b": self.b,
            "chunks": {cid: c.to_dict() for cid, c in self.chunks.items()},
        }
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    @classmethod
    def load(cls, filepath: str | Path) -> "LexicalIndex":
        """Load index state from JSON."""
        path = Path(filepath)
        if not path.is_file():
            raise FileNotFoundError(f"Index file not found: {path}")
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        index = cls(k1=data.get("k1", 1.5), b=data.get("b", 0.75))
        chunks = [ChunkMetadata.from_dict(cd) for cd in data.get("chunks", {}).values()]
        index.add_chunks(chunks)
        return index


# ── FAISS Vector Store Adapter ───────────────────────────────────────

class FAISSVectorStore:
    """
    FAISS-backed Dense Vector Store.
    
    Used when FAISS and an embedding model are available in the environment.
    """

    def __init__(
        self,
        dimension: int,
        embed_fn: Optional[Callable[[list[str]], list[list[float]]]] = None,
    ):
        try:
            import faiss
            self._faiss = faiss
        except ImportError as exc:
            raise ImportError(
                "faiss is not installed. Use LexicalIndex or install faiss-cpu."
            ) from exc

        self.dimension = dimension
        self.embed_fn = embed_fn
        self.index = self._faiss.IndexFlatIP(dimension)
        self.chunks: list[ChunkMetadata] = []
        self.chunk_ids: list[str] = []

    @property
    def method_name(self) -> str:
        return "faiss_embedding"

    def add_chunks(
        self,
        chunks: Sequence[ChunkMetadata],
        embeddings: Optional[Sequence[Sequence[float]]] = None,
    ) -> None:
        """Add chunks and their vectors to the FAISS index."""
        if not chunks:
            return

        import numpy as np

        if embeddings is None:
            if not self.embed_fn:
                raise ValueError("embed_fn must be provided when embeddings are not supplied.")
            embeddings = self.embed_fn([c.content for c in chunks])

        vectors = np.array(embeddings, dtype=np.float32)
        # Normalize for inner product / cosine similarity
        self._faiss.normalize_L2(vectors)
        self.index.add(vectors)
        for c in chunks:
            self.chunks.append(c)
            self.chunk_ids.append(c.chunk_id)

    def search(
        self,
        query: str,
        top_k: int = 5,
        query_vector: Optional[Sequence[float]] = None,
    ) -> list[SearchResult]:
        """Search nearest neighbors using FAISS."""
        if self.index.ntotal == 0:
            return []

        import numpy as np

        if query_vector is None:
            if not self.embed_fn:
                raise ValueError("embed_fn or query_vector required for search.")
            vectors = self.embed_fn([query])
            query_vector = vectors[0]

        q_vec = np.array([query_vector], dtype=np.float32)
        self._faiss.normalize_L2(q_vec)
        distances, indices = self.index.search(q_vec, min(top_k, self.index.ntotal))

        results: list[SearchResult] = []
        for dist, idx in zip(distances[0], indices[0]):
            if idx < 0 or idx >= len(self.chunks):
                continue
            chunk = self.chunks[idx]
            results.append(
                SearchResult(
                    file_path=chunk.file_path,
                    start_line=chunk.start_line,
                    end_line=chunk.end_line,
                    content=chunk.content,
                    score=round(float(dist), 4),
                    score_type="faiss_cosine",
                )
            )
        return results


def is_faiss_available() -> bool:
    """Check if faiss and numpy are available in the current environment."""
    try:
        import faiss  # noqa: F401
        import numpy  # noqa: F401
        return True
    except (ImportError, Exception):
        return False


# ── Hybrid Retrieval Index (Dense FAISS + Sparse BM25 via RRF) ───────

class HybridIndex:
    """
    Hybrid Retrieval Index combining Dense Vector Search (FAISS)
    and Sparse Lexical Search (BM25) using Reciprocal Rank Fusion (RRF).

    Gracefully falls back to pure BM25 LexicalIndex whenever embedding models
    or FAISS dependencies are unavailable, never fabricating vector similarity.
    """

    def __init__(
        self,
        dimension: Optional[int] = None,
        embed_fn: Optional[Callable[[list[str]], list[list[float]]]] = None,
        k1: float = 1.5,
        b: float = 0.75,
        rrf_k: int = 60,
    ):
        self.k1 = k1
        self.b = b
        self.rrf_k = rrf_k
        self.lexical_index = LexicalIndex(k1=k1, b=b)
        self.dense_store: Optional[FAISSVectorStore] = None
        self._dense_enabled = False

        if is_faiss_available() and dimension is not None and embed_fn is not None:
            try:
                self.dense_store = FAISSVectorStore(dimension=dimension, embed_fn=embed_fn)
                self._dense_enabled = True
            except Exception as exc:
                logger.warning("FAISS initialization failed (%s); operating in lexical fallback mode.", exc)
                self.dense_store = None
                self._dense_enabled = False

    @property
    def chunks(self) -> dict[str, ChunkMetadata]:
        return self.lexical_index.chunks

    @property
    def method_name(self) -> str:
        if self._dense_enabled and self.dense_store is not None:
            return "hybrid_rrf"
        return "lexical_bm25"

    def clear(self) -> None:
        self.lexical_index.clear()
        if self.dense_store is not None:
            try:
                self.dense_store.index.reset()
                self.dense_store.chunks.clear()
                self.dense_store.chunk_ids.clear()
            except Exception:
                pass

    def remove_file(self, file_path: str) -> None:
        self.lexical_index.remove_file(file_path)

    def add_chunks(
        self,
        chunks: Sequence[ChunkMetadata],
        embeddings: Optional[Sequence[Sequence[float]]] = None,
    ) -> None:
        """Add chunks to lexical index, and to dense store if available."""
        self.lexical_index.add_chunks(chunks)

        if self._dense_enabled and self.dense_store is not None:
            try:
                self.dense_store.add_chunks(chunks, embeddings=embeddings)
            except (NotImplementedError, Exception) as exc:
                logger.info(
                    "Dense embedding indexing unavailable (%s); maintaining lexical BM25 index.",
                    exc,
                )
                self._dense_enabled = False

    def search(
        self,
        query: str,
        top_k: int = 5,
        query_terms: Optional[list[str]] = None,
        query_vector: Optional[Sequence[float]] = None,
    ) -> list[SearchResult]:
        """
        Execute search. If dense retrieval is active, combines dense and
        lexical results using Reciprocal Rank Fusion (RRF). Otherwise, returns
        lexical BM25 results.
        """
        lexical_results = self.lexical_index.search(
            query=query, top_k=top_k * 2, query_terms=query_terms
        )

        dense_results: list[SearchResult] = []
        if self._dense_enabled and self.dense_store is not None:
            try:
                dense_results = self.dense_store.search(
                    query=query, top_k=top_k * 2, query_vector=query_vector
                )
            except (NotImplementedError, Exception) as exc:
                logger.debug("Dense vector search omitted (%s); using lexical results.", exc)
                dense_results = []

        if not dense_results:
            return lexical_results[:top_k]

        # Reciprocal Rank Fusion (RRF)
        rrf_scores: dict[str, float] = {}
        chunk_map: dict[str, SearchResult] = {}

        for rank, res in enumerate(lexical_results, start=1):
            key = f"{res.file_path}#{res.start_line}-{res.end_line}"
            rrf_scores[key] = rrf_scores.get(key, 0.0) + (1.0 / (self.rrf_k + rank))
            chunk_map[key] = res

        for rank, res in enumerate(dense_results, start=1):
            key = f"{res.file_path}#{res.start_line}-{res.end_line}"
            rrf_scores[key] = rrf_scores.get(key, 0.0) + (1.0 / (self.rrf_k + rank))
            if key not in chunk_map:
                chunk_map[key] = res

        ranked_keys = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)[:top_k]
        combined: list[SearchResult] = []
        for key, rrf_score in ranked_keys:
            base = chunk_map[key]
            combined.append(
                SearchResult(
                    file_path=base.file_path,
                    start_line=base.start_line,
                    end_line=base.end_line,
                    content=base.content,
                    score=round(rrf_score, 6),
                    score_type="hybrid_rrf",
                )
            )
        return combined
