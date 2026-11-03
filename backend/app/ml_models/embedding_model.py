"""
Sentence-transformer embedding model used by the Retrieval Agent.

Wraps the embedding model that feeds backend/app/retrieval/vector_store.py's
FAISS index -- a discriminative deep-learning task, not a generative one.
"""


_MODEL = None


def is_embedding_available() -> bool:
    """Check if an embedding model is currently configured, loaded, and available."""
    try:
        import sentence_transformers  # noqa: F401
        return True
    except (ImportError, Exception):
        return False


def get_embedding_model():
    """Retrieve or lazily initialize the SentenceTransformer model."""
    global _MODEL
    if _MODEL is None:
        from sentence_transformers import SentenceTransformer
        _MODEL = SentenceTransformer("all-MiniLM-L6-v2")
    return _MODEL


def embed(texts: list[str]) -> list[list[float]]:
    """Return embedding vectors for a list of code/text chunks."""
    model = get_embedding_model()
    embeddings = model.encode(texts, convert_to_numpy=True)
    return [vec.tolist() for vec in embeddings]
