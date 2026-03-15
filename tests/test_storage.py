"""Tests for storage backends."""

from __future__ import annotations

import pytest

from seeking_context.models.memory import (
    MemoryCategory,
    MemoryItem,
)
from seeking_context.storage.memory_store import MemoryStore


@pytest.mark.asyncio
class TestMemoryStore:
    """Tests for the MemoryStore facade."""

    async def test_add_and_get(
        self, store: MemoryStore, sample_item: MemoryItem
    ) -> None:
        """Test storing and retrieving a memory."""
        await store.add(sample_item)
        got = await store.get(sample_item.id)
        assert got is not None
        assert got.id == sample_item.id
        assert got.content == sample_item.content

    async def test_delete(
        self, store: MemoryStore, sample_item: MemoryItem
    ) -> None:
        """Test deleting a memory."""
        await store.add(sample_item)
        ok = await store.delete(sample_item.id)
        assert ok is True
        got = await store.get(sample_item.id)
        assert got is None

    async def test_delete_nonexistent(
        self, store: MemoryStore
    ) -> None:
        """Test deleting a non-existent memory."""
        ok = await store.delete("nonexistent-id")
        assert ok is False

    async def test_update(
        self, store: MemoryStore, sample_item: MemoryItem
    ) -> None:
        """Test updating a memory's content."""
        await store.add(sample_item)
        sample_item.content = "Updated content"
        await store.update(sample_item)
        got = await store.get(sample_item.id)
        assert got is not None
        assert got.content == "Updated content"

    async def test_list_empty(
        self, store: MemoryStore
    ) -> None:
        """Test listing from empty store."""
        items = await store.list()
        assert items == []

    async def test_list_with_items(
        self,
        store: MemoryStore,
        sample_items: list[MemoryItem],
    ) -> None:
        """Test listing after adding items."""
        for item in sample_items:
            await store.add(item)
        items = await store.list(limit=10)
        assert len(items) == len(sample_items)

    async def test_count(
        self,
        store: MemoryStore,
        sample_items: list[MemoryItem],
    ) -> None:
        """Test count operation."""
        for item in sample_items:
            await store.add(item)
        total = await store.count()
        assert total == len(sample_items)

    async def test_vector_search(
        self,
        store: MemoryStore,
        sample_items: list[MemoryItem],
    ) -> None:
        """Test vector similarity search returns results."""
        for item in sample_items:
            await store.add(item)
        results = await store.vector_search(
            "python programming", top_k=3
        )
        assert len(results) > 0
        # First result should relate to Python
        top_id = results[0][0]
        top_item = await store.get(top_id)
        assert top_item is not None
        assert "python" in top_item.content.lower()

    async def test_fts_search(
        self,
        store: MemoryStore,
        sample_items: list[MemoryItem],
    ) -> None:
        """Test BM25 full-text search."""
        for item in sample_items:
            await store.add(item)
        results = await store.fts_search(
            "python", top_k=3
        )
        assert len(results) > 0
