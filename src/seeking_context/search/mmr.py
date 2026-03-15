r"""Maximal Marginal Relevance (MMR) re-ranking.

Ported from less-agent's MMR module.  Selects results
that balance relevance with diversity by penalising
candidates too similar to already-selected items.

MMR formula::

    score = lambda * relevance - (1-lambda) * max_sim

Attributes:
    MMRConfig: Configuration dataclass.
    apply_mmr: Core MMR algorithm on tuples.
    apply_mmr_to_hybrid: Wrapper for HybridResult objects.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from seeking_context.search.hybrid import HybridResult


@dataclass
class MMRConfig:
    r"""Configuration for MMR re-ranking.

    Attributes:
        lambda_param (float): Balance between relevance
            (1.0) and diversity (0.0).  Default 0.7
            favours relevance.
        top_k (int): Max results after re-ranking.
    """

    lambda_param: float = 0.7
    top_k: int = 10


def apply_mmr(
    results: list[tuple[str, float, dict[str, Any]]],
    embeddings: dict[str, list[float]],
    config: MMRConfig | None = None,
) -> list[tuple[str, float, dict[str, Any]]]:
    r"""Apply MMR re-ranking to increase diversity.

    Iteratively selects the candidate that maximises
    the MMR score relative to already-selected items.

    Args:
        results: ``(id, score, metadata)`` tuples sorted
            by relevance.
        embeddings: Mapping of id to embedding vector.
        config: MMR configuration.

    Returns:
        Re-ranked list with increased diversity.
    """
    if config is None:
        config = MMRConfig()
    if len(results) <= 1:
        return results

    selected: list[tuple[str, float, dict[str, Any]]] = []
    remaining = list(results)

    # Seed with the top result
    selected.append(remaining.pop(0))

    while remaining and len(selected) < config.top_k:
        best_score = float("-inf")
        best_idx = 0

        for i, (id_, score, _meta) in enumerate(remaining):
            if id_ not in embeddings:
                continue

            relevance = score

            # Max similarity to any already-selected item
            max_sim = 0.0
            for sel_id, _, _ in selected:
                if sel_id in embeddings:
                    sim = _cosine_similarity(
                        embeddings[id_],
                        embeddings[sel_id],
                    )
                    max_sim = max(max_sim, sim)

            mmr = (
                config.lambda_param * relevance
                - (1 - config.lambda_param) * max_sim
            )
            if mmr > best_score:
                best_score = mmr
                best_idx = i

        if best_idx < len(remaining):
            selected.append(remaining.pop(best_idx))
        else:
            break

    return selected


def apply_mmr_to_hybrid(
    results: list[HybridResult],
    embeddings: dict[str, list[float]],
    config: MMRConfig | None = None,
) -> list[HybridResult]:
    r"""Apply MMR to HybridResult objects.

    Converts to tuples, runs MMR, then maps back.

    Args:
        results: HybridResult list from hybrid search.
        embeddings: id-to-embedding mapping.
        config: MMR config.

    Returns:
        Re-ranked HybridResult list.
    """
    if config is None:
        config = MMRConfig()

    tuples = [
        (r.id, r.combined_score, r.metadata)
        for r in results
    ]
    reranked = apply_mmr(tuples, embeddings, config)

    result_map = {r.id: r for r in results}
    return [
        result_map[id_]
        for id_, _, _ in reranked
        if id_ in result_map
    ]


def _cosine_similarity(
    vec1: list[float], vec2: list[float]
) -> float:
    """Calculate cosine similarity between two vectors.

    Args:
        vec1: First vector.
        vec2: Second vector.

    Returns:
        Cosine similarity in range [0, 1].
    """
    if not vec1 or not vec2:
        return 0.0
    if len(vec1) != len(vec2):
        return 0.0

    dot = sum(a * b for a, b in zip(vec1, vec2))
    n1 = sum(a * a for a in vec1) ** 0.5
    n2 = sum(b * b for b in vec2) ** 0.5

    if n1 == 0 or n2 == 0:
        return 0.0
    return dot / (n1 * n2)
