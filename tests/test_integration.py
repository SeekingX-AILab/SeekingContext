"""End-to-end integration tests."""

from __future__ import annotations

import pytest

from seeking_context.config import SeekingContextConfig
from seeking_context.models.memory import (
    MemoryCategory,
    MemoryItem,
)
from seeking_context.models.scope import Scope
from seeking_context.search.hybrid import hybrid_search
from seeking_context.search.mmr import (
    MMRConfig,
    apply_mmr_to_hybrid,
)
from seeking_context.search.temporal_decay import (
    TemporalDecayConfig,
    apply_temporal_decay_to_hybrid,
)
from seeking_context.storage.memory_store import MemoryStore


@pytest.mark.asyncio
class TestIntegration:
    """End-to-end tests for the full pipeline."""

    async def test_full_search_pipeline(
        self,
        store: MemoryStore,
        sample_items: list[MemoryItem],
    ) -> None:
        """Test add -> hybrid search -> decay -> MMR."""
        for item in sample_items:
            await store.add(item)

        config = store.config

        # Hybrid search
        results = await hybrid_search(
            store=store,
            query="python data",
            top_k=5,
            vector_weight=config.vector_weight,
            text_weight=config.text_weight,
        )
        assert len(results) > 0

        # Temporal decay
        decay_cfg = TemporalDecayConfig(
            half_life_days=30.0,
        )
        results = apply_temporal_decay_to_hybrid(
            results, decay_cfg
        )

        # MMR
        ids = [r.id for r in results]
        embeddings = await store.get_embeddings(ids)
        mmr_cfg = MMRConfig(lambda_param=0.7, top_k=3)
        results = apply_mmr_to_hybrid(
            results, embeddings, mmr_cfg
        )

        assert len(results) > 0
        # Top result should be python-related
        top = await store.get(results[0].id)
        assert top is not None
        assert "python" in top.content.lower()

    async def test_scope_filtering(
        self,
        store: MemoryStore,
    ) -> None:
        """Test that scope filters isolate memories."""
        a = MemoryItem(
            content="User A's memory",
            user_id="userA",
            category=MemoryCategory.PROFILE,
        )
        b = MemoryItem(
            content="User B's memory",
            user_id="userB",
            category=MemoryCategory.PROFILE,
        )
        await store.add(a)
        await store.add(b)

        scope_a = Scope(user_id="userA")
        items_a = await store.list(scope=scope_a)
        assert len(items_a) == 1
        assert items_a[0].user_id == "userA"

    async def test_category_filtering(
        self,
        store: MemoryStore,
        sample_items: list[MemoryItem],
    ) -> None:
        """Test filtering by category."""
        for item in sample_items:
            await store.add(item)

        items = await store.list(
            category="cases",
        )
        assert all(
            i.category == MemoryCategory.CASES
            for i in items
        )

    async def test_persistence_roundtrip(
        self,
        config: SeekingContextConfig,
    ) -> None:
        """Test that data persists across store instances."""
        store1 = MemoryStore(config=config)
        item = MemoryItem(
            content="Persistent memory",
            category=MemoryCategory.ENTITIES,
        )
        await store1.add(item)

        # Create new store instance (simulates restart)
        store2 = MemoryStore(config=config)
        got = await store2.get(item.id)
        assert got is not None
        assert got.content == "Persistent memory"

    async def test_search_quality_diverse_corpus(
        self,
        store: MemoryStore,
    ) -> None:
        """Test search quality with diverse memories."""
        memories = [
            "Python list comprehensions improve code readability.",
            "Docker containers isolate applications.",
            "React hooks manage component state.",
            "PostgreSQL supports JSON columns.",
            "Git branching enables parallel development.",
            "FastAPI uses type hints for validation.",
            "Redis caches frequently accessed data.",
            "Kubernetes orchestrates container deployments.",
            "GraphQL provides flexible API queries.",
            "Pytest fixtures simplify test setup.",
        ]
        for m in memories:
            item = MemoryItem(
                content=m,
                abstract=m[:50],
                category=MemoryCategory.ENTITIES,
            )
            await store.add(item)

        results = await hybrid_search(
            store=store,
            query="testing Python code",
            top_k=3,
        )
        assert len(results) > 0
        # Expect pytest or Python related results first
        top_item = await store.get(results[0].id)
        assert top_item is not None
        content_lower = top_item.content.lower()
        assert (
            "python" in content_lower
            or "pytest" in content_lower
            or "test" in content_lower
        )
