"""
Self-learning RAG layer. Every completed review is embedded and stored in
ChromaDB (local, persistent). Future PRs retrieve the top-k most similar
past reviews so agents can reuse prior findings instead of re-deriving them
from scratch (e.g. "we flagged this exact SQL-injection pattern in PR #42").
"""
from __future__ import annotations

import chromadb
from chromadb.utils import embedding_functions

from app.config import get_settings

_client = None
_collection = None


def _get_collection():
    global _client, _collection
    if _collection is not None:
        return _collection

    settings = get_settings()
    _client = chromadb.PersistentClient(path=settings.chroma_persist_dir)

    # Uses Chroma's default sentence-transformer embedding function so the
    # prototype runs fully offline without an extra embeddings API key.
    embed_fn = embedding_functions.DefaultEmbeddingFunction()

    _collection = _client.get_or_create_collection(
        name=settings.chroma_collection,
        embedding_function=embed_fn,
    )
    return _collection


def index_review(pr_id: str, summary_text: str, metadata: dict) -> None:
    """Called after a review is posted, so future PRs can retrieve it."""
    collection = _get_collection()
    collection.upsert(
        ids=[pr_id],
        documents=[summary_text],
        metadatas=[metadata],
    )


def retrieve_similar_reviews(query_text: str, k: int = 3) -> list[dict]:
    """Returns up to k past review summaries most similar to the current PR."""
    collection = _get_collection()
    if collection.count() == 0:
        return []
    k = min(k, collection.count())
    results = collection.query(query_texts=[query_text], n_results=k)

    matches = []
    for doc, meta, dist in zip(
        results.get("documents", [[]])[0],
        results.get("metadatas", [[]])[0],
        results.get("distances", [[]])[0],
    ):
        matches.append({"summary": doc, "metadata": meta, "distance": dist})
    return matches
