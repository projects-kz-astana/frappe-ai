import numpy as np

# Constant used by Reciprocal Rank Fusion. The standard value of 60 dampens the
# influence of any single ranker so neither vector nor keyword results dominate.
RRF_K = 60


def _tokenize(text: str) -> list[str]:
    return text.lower().split()


def hybrid_search(
    question: str,
    q_vec: np.ndarray,
    index,
    metadata: list[dict],
    top_k: int,
    candidate_multiplier: int = 3,
) -> list[int]:
    """Combine FAISS vector search with BM25 keyword scoring.

    Both rankers produce an ordered list of chunk indices over the active
    metadata; the two lists are merged with Reciprocal Rank Fusion (RRF), which
    avoids having to normalise FAISS L2 distances against BM25 relevance scores.

    Returns the fused list of metadata indices, truncated to ``top_k``.
    """
    from rank_bm25 import BM25Okapi

    active_indices = [i for i, m in enumerate(metadata) if m.get("active", True)]
    if not active_indices:
        return []

    k_fetch = min(top_k * candidate_multiplier, index.ntotal)

    _distances, faiss_indices = index.search(q_vec, k=k_fetch)
    vector_ranking = [
        int(i)
        for i in faiss_indices[0]
        if 0 <= i < len(metadata) and metadata[i].get("active", True)
    ]

    corpus = [_tokenize(metadata[i].get("content", "")) for i in active_indices]
    bm25 = BM25Okapi(corpus)
    bm25_scores = bm25.get_scores(_tokenize(question))
    top_local = np.argsort(bm25_scores)[::-1][:k_fetch]
    keyword_ranking = [active_indices[i] for i in top_local]

    scores: dict[int, float] = {}
    for ranking in (vector_ranking, keyword_ranking):
        for rank, idx in enumerate(ranking):
            scores[idx] = scores.get(idx, 0.0) + 1.0 / (RRF_K + rank)

    fused = sorted(scores, key=lambda i: scores[i], reverse=True)
    return fused[:top_k]
