"""Tests for search pipeline."""

from __future__ import annotations

import pytest
from datetime import datetime, timedelta

from seeking_context.search.hybrid import (
    HybridResult,
    merge_hybrid_results,
)
from seeking_context.search.mmr import (
    MMRConfig,
    apply_mmr,
    _cosine_similarity,
)
from seeking_context.search.temporal_decay import (
    TemporalDecayConfig,
    compute_decay_factor,
    apply_temporal_decay_to_hybrid,
    get_age_bucket,
)


class TestHybridMerge:
    """Tests for hybrid search merge."""

    def test_merge_basic(self) -> None:
        """Test basic merge of vector + keyword results."""
        vector = [("a", 0.9), ("b", 0.7)]
        keyword = [("a", 0.5), ("c", 0.8)]
        results = merge_hybrid_results(vector, keyword)
        assert len(results) == 3
        # 'a' appears in both, should rank high
        assert results[0].id == "a"

    def test_merge_weights(self) -> None:
        """Test that weights are respected."""
        vector = [("a", 1.0)]
        keyword = [("a", 0.0)]
        results = merge_hybrid_results(
            vector, keyword,
            vector_weight=0.7, text_weight=0.3,
        )
        assert abs(results[0].combined_score - 0.7) < 0.01

    def test_merge_empty(self) -> None:
        """Test merge with empty inputs."""
        results = merge_hybrid_results([], [])
        assert results == []

    def test_merge_zero_weights(self) -> None:
        """Test merge with zero weights returns empty."""
        results = merge_hybrid_results(
            [("a", 1.0)], [],
            vector_weight=0.0, text_weight=0.0,
        )
        assert results == []


class TestMMR:
    """Tests for MMR re-ranking."""

    def test_cosine_identical(self) -> None:
        """Test cosine similarity of identical vectors."""
        v = [1.0, 0.0, 0.0]
        assert abs(_cosine_similarity(v, v) - 1.0) < 0.01

    def test_cosine_orthogonal(self) -> None:
        """Test cosine similarity of orthogonal vectors."""
        a = [1.0, 0.0]
        b = [0.0, 1.0]
        assert abs(_cosine_similarity(a, b)) < 0.01

    def test_mmr_promotes_diversity(self) -> None:
        """Test that MMR promotes diverse results."""
        results = [
            ("a", 0.9, {}),
            ("b", 0.85, {}),
            ("c", 0.7, {}),
        ]
        embeddings = {
            "a": [1.0, 0.0],
            "b": [0.99, 0.1],  # Very similar to a
            "c": [0.0, 1.0],   # Very different
        }
        config = MMRConfig(lambda_param=0.5, top_k=3)
        reranked = apply_mmr(results, embeddings, config)
        # c should be promoted over b due to diversity
        ids = [r[0] for r in reranked]
        assert ids[0] == "a"
        # c should appear before b
        assert ids.index("c") < ids.index("b")


class TestTemporalDecay:
    """Tests for temporal decay scoring."""

    def test_recent_boost(self) -> None:
        """Test that recent items get boosted."""
        now = datetime.now()
        ts = (now - timedelta(hours=1)).isoformat()
        config = TemporalDecayConfig(
            boost_recent_days=7.0,
            boost_factor=1.2,
        )
        factor = compute_decay_factor(ts, config, now)
        assert factor == 1.2

    def test_old_decays(self) -> None:
        """Test that old items decay."""
        now = datetime.now()
        ts = (now - timedelta(days=60)).isoformat()
        config = TemporalDecayConfig(
            half_life_days=30.0,
        )
        factor = compute_decay_factor(ts, config, now)
        assert 0.2 < factor < 0.3  # ~0.25 at 60 days

    def test_disabled(self) -> None:
        """Test decay disabled returns 1.0."""
        config = TemporalDecayConfig(enabled=False)
        factor = compute_decay_factor(
            "2020-01-01", config
        )
        assert factor == 1.0

    def test_apply_to_hybrid_reorders(self) -> None:
        """Test that decay re-orders hybrid results."""
        now = datetime.now()
        old = HybridResult(
            id="old",
            combined_score=1.0,
            timestamp=(
                now - timedelta(days=90)
            ).isoformat(),
        )
        new = HybridResult(
            id="new",
            combined_score=0.8,
            timestamp=(
                now - timedelta(hours=1)
            ).isoformat(),
        )
        config = TemporalDecayConfig()
        results = apply_temporal_decay_to_hybrid(
            [old, new], config, now
        )
        # New should now rank first (boosted)
        assert results[0].id == "new"

    def test_age_bucket(self) -> None:
        """Test age bucket categorisation."""
        now = datetime.now()
        assert get_age_bucket(
            (now - timedelta(hours=1)).isoformat(), now
        ) == "today"
        assert get_age_bucket(
            (now - timedelta(days=3)).isoformat(), now
        ) == "this_week"
        assert get_age_bucket(
            (now - timedelta(days=15)).isoformat(), now
        ) == "this_month"
