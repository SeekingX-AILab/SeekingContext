r"""Facade coordinating vector, metadata, and markdown stores.

``MemoryStore`` is the single entry point used by MCP
tools for all storage operations.  It routes writes to
MarkdownStore (source of truth), ChromaDB (embeddings),
and SQLite (metadata + FTS).

When ``markdown_enabled`` is True (default), every write
goes to a ``.md`` file **first**, then to the derived
indexes.  Reads prefer the markdown file, falling back
to SQLite.

Attributes:
    MemoryStore: High-level facade unifying markdown,
        vector, and metadata storage with scope-aware
        queries.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from seeking_context.config import SeekingContextConfig
from seeking_context.models.memory import MemoryItem
from seeking_context.models.scope import Scope
from seeking_context.storage.chromadb_store import (
    ChromaDBStore,
)
from seeking_context.storage.markdown_store import (
    MarkdownStore,
)
from seeking_context.storage.sqlite_store import SQLiteStore

logger = logging.getLogger(__name__)


class MemoryStore:
    r"""Unified facade over markdown + vector + metadata.

    Attributes:
        vector (ChromaDBStore): Vector similarity backend.
        meta (SQLiteStore): Metadata + FTS backend.
        markdown (MarkdownStore | None): Markdown source
            of truth.  None when markdown_enabled=False.
        config (SeekingContextConfig): Server config.
    """

    def __init__(
        self, config: SeekingContextConfig | None = None
    ) -> None:
        """Initialise all sub-stores from config.

        Args:
            config: Server configuration. Uses default
                if None.
        """
        from seeking_context.config import get_config

        self.config = config or get_config()
        data = self.config.ensure_data_dir()

        self.vector = ChromaDBStore(
            persist_dir=str(data / "chroma"),
            embedding_model=self.config.embedding_model,
        )
        self.meta = SQLiteStore(
            db_path=str(data / "metadata.db"),
        )

        # Markdown source of truth (opt-in via config).
        if self.config.markdown_enabled:
            self.markdown: MarkdownStore | None = (
                MarkdownStore(
                    str(data / "memories")
                )
            )
        else:
            self.markdown = None

    # -- write operations --------------------------------------

    async def add(self, item: MemoryItem) -> MemoryItem:
        """Store a new memory item.

        Writes to markdown (source of truth) first, then
        to vector + metadata stores (derived indexes).

        Args:
            item: The memory to store.

        Returns:
            The stored MemoryItem (unchanged).
        """
        dump = item.model_dump(mode="json")

        # 1. Write .md file first (source of truth).
        if self.markdown:
            await self.markdown.save(item.id, dump)

        # 2. Index into ChromaDB + SQLite (derived).
        vector_meta = self._scope_meta(item)
        vector_meta["category"] = item.category.value

        await self.vector.insert(
            doc_id=item.id,
            text=item.content,
            metadata=vector_meta,
        )
        await self.meta.save(
            doc_id=item.id,
            data=dump,
        )

        # 3. Update directory summaries.
        if self.markdown:
            ns = self.markdown._extract_ns(dump)
            await self.markdown.update_dir_summaries(
                ns, item.category.value
            )

        logger.info("Stored memory %s", item.id)
        return item

    async def update(
        self, item: MemoryItem
    ) -> MemoryItem:
        """Update an existing memory item.

        Writes to markdown first, then syncs to derived
        indexes.

        Args:
            item: Updated memory item (must have the
                same ``id`` as the original).

        Returns:
            The updated MemoryItem.
        """
        dump = item.model_dump(mode="json")

        # 1. Update .md file (source of truth).
        if self.markdown:
            await self.markdown.save(item.id, dump)

        # 2. Update derived indexes.
        vector_meta = self._scope_meta(item)
        vector_meta["category"] = item.category.value

        await self.vector.insert(
            doc_id=item.id,
            text=item.content,
            metadata=vector_meta,
        )
        await self.meta.save(
            doc_id=item.id,
            data=dump,
        )

        # 3. Update directory summaries.
        if self.markdown:
            ns = self.markdown._extract_ns(dump)
            await self.markdown.update_dir_summaries(
                ns, item.category.value
            )

        logger.info("Updated memory %s", item.id)
        return item

    async def delete(self, memory_id: str) -> bool:
        """Delete a memory by id.

        Removes the .md file (source of truth), then
        removes from derived indexes.

        Args:
            memory_id: Identifier of the memory to remove.

        Returns:
            True if something was deleted, False otherwise.
        """
        existing = await self.meta.get(memory_id)
        if not existing:
            return False

        # 1. Delete .md file.
        ns = ""
        category = ""
        if self.markdown:
            ns = self.markdown._extract_ns(existing)
            category = existing.get(
                "category", "entities"
            )
            await self.markdown.delete(memory_id)

        # 2. Remove from derived indexes.
        await self.vector.delete(memory_id)
        await self.meta.delete(memory_id)

        # 3. Update directory summaries.
        if self.markdown and ns:
            await self.markdown.update_dir_summaries(
                ns, category
            )

        logger.info("Deleted memory %s", memory_id)
        return True

    # -- read operations ---------------------------------------

    async def get(
        self, memory_id: str
    ) -> MemoryItem | None:
        """Retrieve a memory by id.

        Tries the markdown file first (canonical), then
        falls back to SQLite (derived index).

        Args:
            memory_id: Identifier.

        Returns:
            MemoryItem or None if not found.
        """
        # Try markdown source of truth first.
        if self.markdown:
            data = await self.markdown.get(memory_id)
            if data:
                return MemoryItem.model_validate(data)

        # Fall back to SQLite.
        data = await self.meta.get(memory_id)
        if not data:
            return None
        return MemoryItem.model_validate(data)

    async def list(
        self,
        scope: Scope | None = None,
        category: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[MemoryItem]:
        """List memories with optional scope/category.

        Args:
            scope: Optional scope filter.
            category: Optional category filter.
            limit: Max items.
            offset: Items to skip.

        Returns:
            List of MemoryItem objects.
        """
        where: dict[str, Any] = {}
        if scope:
            where.update(scope.to_filter_dict())
        if category:
            where["category"] = category
        rows = await self.meta.list(
            where=where or None,
            limit=limit,
            offset=offset,
        )
        return [MemoryItem.model_validate(r) for r in rows]

    async def count(
        self,
        scope: Scope | None = None,
        category: str | None = None,
    ) -> int:
        """Count memories matching filters.

        Args:
            scope: Optional scope filter.
            category: Optional category filter.

        Returns:
            Number of matching memories.
        """
        where: dict[str, Any] = {}
        if scope:
            where.update(scope.to_filter_dict())
        if category:
            where["category"] = category
        return await self.meta.count(
            where=where or None
        )

    # -- search operations -------------------------------------

    async def vector_search(
        self,
        query: str,
        top_k: int = 10,
        scope: Scope | None = None,
        category: str | None = None,
    ) -> list[tuple[str, float]]:
        """Vector similarity search.

        Args:
            query: Query text.
            top_k: Max results.
            scope: Optional scope filter.
            category: Optional category filter.

        Returns:
            List of ``(memory_id, score)`` tuples.
        """
        where: dict[str, Any] = {}
        if scope:
            where.update(scope.to_filter_dict())
        if category:
            where["category"] = category
        return await self.vector.search(
            query=query,
            top_k=top_k,
            where=where or None,
        )

    async def fts_search(
        self,
        query: str,
        top_k: int = 10,
        scope: Scope | None = None,
        category: str | None = None,
    ) -> list[tuple[str, float]]:
        """BM25 full-text search.

        Args:
            query: Keyword query.
            top_k: Max results.
            scope: Optional scope filter.
            category: Optional category filter.

        Returns:
            List of ``(memory_id, score)`` tuples.
        """
        where: dict[str, Any] = {}
        if scope:
            where.update(scope.to_filter_dict())
        if category:
            where["category"] = category
        return await self.meta.fts_search(
            query=query,
            top_k=top_k,
            where=where or None,
        )

    async def get_embeddings(
        self, doc_ids: list[str]
    ) -> dict[str, list[float]]:
        """Fetch embeddings for MMR re-ranking.

        Args:
            doc_ids: Memory identifiers.

        Returns:
            Mapping of id to embedding vector.
        """
        return await self.vector.get_embeddings(doc_ids)

    # -- helpers -----------------------------------------------

    @staticmethod
    def _scope_meta(item: MemoryItem) -> dict[str, Any]:
        """Extract scope fields for vector metadata.

        Args:
            item: Source memory item.

        Returns:
            Dict with non-None scope fields.
        """
        meta: dict[str, Any] = {}
        if item.user_id:
            meta["user_id"] = item.user_id
        if item.agent_id:
            meta["agent_id"] = item.agent_id
        if item.session_id:
            meta["session_id"] = item.session_id
        return meta
