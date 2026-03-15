r"""Hybrid search combining vector + BM25 keyword results.

Ported from less-agent's hybrid search module.  Merges
vector similarity scores and BM25 keyword scores using
a weighted average (default 70% vector, 30% keyword).

Attributes:
    HybridResult: Dataclass holding per-result scores.
    merge_hybrid_results: Merges two ranked lists into a
        single hybrid-scored list.
    hybrid_search: Convenience function running the full
        hybrid pipeline against a MemoryStore.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class HybridResult:
    r"""Result from the hybrid merge step.

    Attributes:
        id (str): Memory identifier.
        vector_score (float): Score from vector search.
        text_score (float): Score from BM25 search.
        combined_score (float): Weighted combined score.
        content (str): Memory content text.
        metadata (dict[str, Any]): Attached metadata.
        timestamp (str | None): ISO timestamp for decay.
    """

    id: str
    vector_score: float = 0.0
    text_score: float = 0.0
    combined_score: float = 0.0
    content: str = ""
    metadata: dict[str, Any] = field(
        default_factory=dict
    )
    timestamp: str | None = None


def merge_hybrid_results(
    vector_results: list[tuple[str, float]],
    keyword_results: list[tuple[str, float]],
    vector_weight: float = 0.7,
    text_weight: float = 0.3,
    contents: dict[str, str] | None = None,
    metadatas: dict[str, dict[str, Any]] | None = None,
    timestamps: dict[str, str] | None = None,
) -> list[HybridResult]:
    r"""Merge vector and keyword search results.

    Combines scores using a weighted average::

        combined = w_v * vector_score + w_t * text_score

    where weights are normalised to sum to 1.

    Args:
        vector_results: ``(id, score)`` pairs from vector
            search.
        keyword_results: ``(id, score)`` pairs from BM25.
        vector_weight: Weight for vector scores.
        text_weight: Weight for keyword scores.
        contents: Optional id-to-content mapping.
        metadatas: Optional id-to-metadata mapping.
        timestamps: Optional id-to-timestamp mapping.

    Returns:
        List of ``HybridResult`` sorted by combined score
        in descending order.
    """
    total = vector_weight + text_weight
    if total == 0:
        return []
    vector_weight /= total
    text_weight /= total

    all_ids: set[str] = set()
    for id_, _ in vector_results:
        all_ids.add(id_)
    for id_, _ in keyword_results:
        all_ids.add(id_)

    v_map = dict(vector_results)
    k_map = dict(keyword_results)

    results: list[HybridResult] = []
    for id_ in all_ids:
        vs = v_map.get(id_, 0.0)
        ks = k_map.get(id_, 0.0)
        combined = vector_weight * vs + text_weight * ks

        results.append(
            HybridResult(
                id=id_,
                vector_score=vs,
                text_score=ks,
                combined_score=combined,
                content=(
                    contents.get(id_, "")
                    if contents
                    else ""
                ),
                metadata=(
                    metadatas.get(id_, {})
                    if metadatas
                    else {}
                ),
                timestamp=(
                    timestamps.get(id_)
                    if timestamps
                    else None
                ),
            )
        )

    results.sort(
        key=lambda x: x.combined_score, reverse=True
    )
    return results


async def hybrid_search(
    store: Any,  # MemoryStore
    query: str,
    top_k: int = 10,
    vector_weight: float = 0.7,
    text_weight: float = 0.3,
    scope: Any | None = None,
    category: str | None = None,
) -> list[HybridResult]:
    r"""Run the full hybrid search pipeline.

    Queries both vector and BM25 backends, then merges.

    Args:
        store: A ``MemoryStore`` instance.
        query: Natural-language search text.
        top_k: Maximum results to return.
        vector_weight: Vector score weight.
        text_weight: BM25 score weight.
        scope: Optional ``Scope`` filter.
        category: Optional category filter.

    Returns:
        Merged ``HybridResult`` list.
    """
    fetch_k = top_k * 2

    vector_results = await store.vector_search(
        query=query,
        top_k=fetch_k,
        scope=scope,
        category=category,
    )
    fts_results = await store.fts_search(
        query=query,
        top_k=fetch_k,
        scope=scope,
        category=category,
    )

    # Normalise BM25 scores to 0-1
    fts_results = _normalise_scores(fts_results)

    # Gather content + metadata for results
    all_ids = {id_ for id_, _ in vector_results}
    all_ids |= {id_ for id_, _ in fts_results}

    contents: dict[str, str] = {}
    metadatas: dict[str, dict[str, Any]] = {}
    timestamps: dict[str, str] = {}
    for id_ in all_ids:
        item = await store.get(id_)
        if item:
            contents[id_] = item.content
            metadatas[id_] = item.metadata
            timestamps[id_] = item.updated_at

    return merge_hybrid_results(
        vector_results=vector_results,
        keyword_results=fts_results,
        vector_weight=vector_weight,
        text_weight=text_weight,
        contents=contents,
        metadatas=metadatas,
        timestamps=timestamps,
    )


def _normalise_scores(
    results: list[tuple[str, float]],
) -> list[tuple[str, float]]:
    """Normalise scores to 0-1 range.

    Args:
        results: List of ``(id, raw_score)`` tuples.

    Returns:
        Normalised tuples where the max score maps to 1.
    """
    if not results:
        return results
    max_score = max(s for _, s in results)
    if max_score <= 0:
        return results
    return [(id_, s / max_score) for id_, s in results]
