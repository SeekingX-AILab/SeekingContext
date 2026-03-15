"""Tests for MCP tools."""

from __future__ import annotations

import pytest

from seeking_context.config import SeekingContextConfig
from seeking_context.models.memory import MemoryItem
from seeking_context.storage.memory_store import MemoryStore
from seeking_context.tools import memory_tools
from seeking_context.tools import session_tools


@pytest.mark.asyncio
class TestMemoryTools:
    """Tests for memory_tools MCP functions."""

    async def test_add_and_get(
        self, store: MemoryStore
    ) -> None:
        """Test memory_add then memory_get roundtrip."""
        # Patch the global store
        memory_tools._store = store

        result = await memory_tools.memory_add(
            content="Test content",
            category="entities",
            user_id="u1",
        )
        assert result["status"] == "stored"
        mid = result["id"]

        got = await memory_tools.memory_get(
            memory_id=mid
        )
        assert got["content"] == "Test content"

    async def test_update(
        self, store: MemoryStore
    ) -> None:
        """Test memory_update modifies content."""
        memory_tools._store = store

        result = await memory_tools.memory_add(
            content="Original",
        )
        mid = result["id"]

        await memory_tools.memory_update(
            memory_id=mid, content="Modified"
        )
        got = await memory_tools.memory_get(
            memory_id=mid
        )
        assert got["content"] == "Modified"

    async def test_delete(
        self, store: MemoryStore
    ) -> None:
        """Test memory_delete removes the item."""
        memory_tools._store = store

        result = await memory_tools.memory_add(
            content="To delete",
        )
        mid = result["id"]

        d = await memory_tools.memory_delete(
            memory_id=mid
        )
        assert d["status"] == "deleted"

        got = await memory_tools.memory_get(
            memory_id=mid
        )
        assert got.get("error") == "not_found"

    async def test_list(
        self, store: MemoryStore
    ) -> None:
        """Test memory_list returns stored items."""
        memory_tools._store = store

        for i in range(3):
            await memory_tools.memory_add(
                content=f"Item {i}",
                user_id="u1",
            )

        items = await memory_tools.memory_list(
            user_id="u1"
        )
        assert len(items) == 3

    async def test_search(
        self, store: MemoryStore
    ) -> None:
        """Test memory_search returns relevant results."""
        memory_tools._store = store

        await memory_tools.memory_add(
            content="Python is a programming language.",
        )
        await memory_tools.memory_add(
            content="Cooking pasta takes 10 minutes.",
        )

        results = await memory_tools.memory_search(
            query="programming language", top_k=2
        )
        assert len(results) > 0
        assert "python" in results[0]["content"].lower()


@pytest.mark.asyncio
class TestSessionTools:
    """Tests for session_tools MCP functions."""

    async def test_session_lifecycle(
        self, store: MemoryStore
    ) -> None:
        """Test session start, list, and end."""
        memory_tools._store = store

        r = await session_tools.session_start(
            user_id="u1"
        )
        sid = r["session_id"]
        assert r["status"] == "started"

        sessions = await session_tools.session_list(
            user_id="u1"
        )
        assert len(sessions) == 1

        end = await session_tools.session_end(
            session_id=sid
        )
        assert end["status"] == "ended"

    async def test_session_compress(
        self, store: MemoryStore
    ) -> None:
        """Test session_compress stores a summary."""
        memory_tools._store = store

        r = await session_tools.session_start()
        sid = r["session_id"]

        cr = await session_tools.session_compress(
            session_id=sid,
            messages=["Hello", "How are you?", "Bye"],
        )
        assert cr["status"] == "compressed"
        assert cr["id"]
