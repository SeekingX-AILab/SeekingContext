r"""Python SDK client for SeekingContext.

Provides a high-level ``SeekingContextClient`` that wraps
the underlying ``MemoryStore`` with namespace-aware scoping.
Every method has both sync (``client.add``) and async
(``client.async_add``) variants.

Usage::

    from seeking_context import SeekingContextClient

    client = SeekingContextClient(namespace="my-app")

    # Sync
    mem = client.add("some content", category="events")
    results = client.search("find something")

    # Async
    mem = await client.async_add("content")
    results = await client.async_search("query")

The client creates or reuses a ``MemoryStore`` singleton
internally, meaning all clients in the same process share
one data backend.

Design note:
    Inspired by less-agent's markdown-first persistence
    model.  The SDK auto-applies namespace prefixes to
    ``user_id`` and ``agent_id`` so callers never need
    to worry about cross-framework collisions.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from seeking_context.config import (
    SeekingContextConfig,
    get_config,
)
from seeking_context.context.levels import (
    resolve_content_at_level,
)
from seeking_context.identity import resolve_scope
from seeking_context.models.memory import (
    ContextLevel,
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
from seeking_context.storage.memory_store import (
    MemoryStore,
)

logger = logging.getLogger(__name__)

# Module-level singleton for shared MemoryStore
_shared_store: MemoryStore | None = None


def _get_shared_store(
    config: SeekingContextConfig | None = None,
) -> MemoryStore:
    """Return or create the process-wide MemoryStore.

    Args:
        config: Optional config override.

    Returns:
        The shared MemoryStore instance.
    """
    global _shared_store
    if _shared_store is None:
        _shared_store = MemoryStore(config=config)
    return _shared_store


def _run_sync(coro: Any) -> Any:
    """Run an async coroutine synchronously.

    Uses the running event loop if one exists,
    otherwise creates a new one.

    Args:
        coro: The coroutine to execute.

    Returns:
        The coroutine's return value.
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        # We're inside an async context — use a new
        # thread to avoid deadlock.
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=1,
        ) as pool:
            return pool.submit(
                asyncio.run, coro,
            ).result()
    return asyncio.run(coro)


class SeekingContextClient:
    r"""High-level client for SeekingContext memory operations.

    Attributes:
        namespace (str | None): Framework namespace for
            scope isolation.
        default_user_id (str | None): Default user scope.
        default_agent_id (str | None): Default agent scope.
        store (MemoryStore): The underlying memory store.
    """

    def __init__(
        self,
        namespace: str | None = None,
        default_user_id: str | None = None,
        default_agent_id: str | None = None,
        data_dir: str | None = None,
    ) -> None:
        """Initialise the client.

        Args:
            namespace: Framework identifier for scope
                isolation (e.g. ``"openclaw"``).
            default_user_id: Default user_id applied to
                all operations unless overridden.
            default_agent_id: Default agent_id applied to
                all operations unless overridden.
            data_dir: Custom data directory.  Defaults to
                ``~/.seeking_context``.
        """
        self.namespace = namespace
        self.default_user_id = default_user_id
        self.default_agent_id = default_agent_id

        config = None
        if data_dir:
            config = SeekingContextConfig(
                data_dir=data_dir,
            )
        self.store = _get_shared_store(config)

    def _scope(
        self,
        user_id: str | None = None,
        agent_id: str | None = None,
        session_id: str | None = None,
    ) -> Scope:
        """Build a namespaced Scope with defaults.

        Args:
            user_id: Override for user.
            agent_id: Override for agent.
            session_id: Session UUID.

        Returns:
            Scope with namespace applied.
        """
        uid = user_id or self.default_user_id
        aid = agent_id or self.default_agent_id
        if self.namespace is not None:
            return resolve_scope(
                namespace=self.namespace,
                user_id=uid,
                agent_id=aid,
                session_id=session_id,
            )
        return Scope(
            user_id=uid,
            agent_id=aid,
            session_id=session_id,
        )

    # ---- async API ------------------------------------------

    async def async_add(
        self,
        content: str,
        category: str = "entities",
        abstract: str = "",
        overview: str = "",
        user_id: str | None = None,
        agent_id: str | None = None,
        session_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Store a new memory (async).

        Args:
            content: Full text content (L2).
            category: Memory category name.
            abstract: One-line summary (L0).
            overview: Structured summary (L1).
            user_id: Optional user scope override.
            agent_id: Optional agent scope override.
            session_id: Optional session scope.
            metadata: Arbitrary key-value metadata.

        Returns:
            Dict with ``id`` and ``status``.
        """
        scope = self._scope(
            user_id, agent_id, session_id,
        )
        cat = MemoryCategory(category)
        item = MemoryItem(
            content=content,
            abstract=abstract or content[:200],
            overview=overview,
            category=cat,
            user_id=scope.user_id,
            agent_id=scope.agent_id,
            session_id=scope.session_id,
            metadata=metadata or {},
        )
        await self.store.add(item)
        return {"id": item.id, "status": "stored"}

    async def async_search(
        self,
        query: str,
        top_k: int = 10,
        category: str | None = None,
        user_id: str | None = None,
        agent_id: str | None = None,
        session_id: str | None = None,
        level: int = 2,
    ) -> list[dict[str, Any]]:
        """Hybrid search over memories (async).

        Args:
            query: Natural-language search text.
            top_k: Maximum results.
            category: Optional category filter.
            user_id: Optional user scope override.
            agent_id: Optional agent scope override.
            session_id: Optional session scope.
            level: Context level (0/1/2).

        Returns:
            List of result dicts.
        """
        config = get_config()
        scope = self._scope(
            user_id, agent_id, session_id,
        )
        ctx_level = ContextLevel(level)

        results = await hybrid_search(
            store=self.store,
            query=query,
            top_k=top_k * 2,
            vector_weight=config.vector_weight,
            text_weight=config.text_weight,
            scope=scope,
            category=category,
        )

        decay_cfg = TemporalDecayConfig(
            half_life_days=(
                config.temporal_decay_half_life_days
            ),
            boost_recent_days=config.boost_recent_days,
            boost_factor=config.boost_factor,
            min_decay=config.min_decay,
        )
        results = apply_temporal_decay_to_hybrid(
            results, decay_cfg,
        )

        if len(results) > 1:
            ids = [r.id for r in results]
            embeddings = await self.store.get_embeddings(
                ids,
            )
            mmr_cfg = MMRConfig(
                lambda_param=config.mmr_lambda,
                top_k=top_k,
            )
            results = apply_mmr_to_hybrid(
                results, embeddings, mmr_cfg,
            )

        output: list[dict[str, Any]] = []
        for r in results[:top_k]:
            item = await self.store.get(r.id)
            if not item:
                continue
            item.touch()
            await self.store.update(item)
            text = resolve_content_at_level(
                item, ctx_level,
            )
            output.append(
                {
                    "id": item.id,
                    "score": round(
                        r.combined_score, 4,
                    ),
                    "content": text,
                    "category": item.category.value,
                }
            )
        return output

    async def async_get(
        self, memory_id: str,
    ) -> dict[str, Any] | None:
        """Retrieve a memory by ID (async).

        Args:
            memory_id: UUID of the memory.

        Returns:
            Memory dict or None if not found.
        """
        item = await self.store.get(memory_id)
        if not item:
            return None
        item.touch()
        await self.store.update(item)
        return item.model_dump(mode="json")

    async def async_delete(
        self, memory_id: str,
    ) -> bool:
        """Delete a memory by ID (async).

        Args:
            memory_id: UUID of the memory.

        Returns:
            True if deleted, False if not found.
        """
        return await self.store.delete(memory_id)

    async def async_list(
        self,
        category: str | None = None,
        user_id: str | None = None,
        agent_id: str | None = None,
        session_id: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """List memories with optional filters (async).

        Args:
            category: Optional category filter.
            user_id: Optional user scope override.
            agent_id: Optional agent scope override.
            session_id: Optional session scope.
            limit: Max items.
            offset: Items to skip.

        Returns:
            List of memory dicts.
        """
        scope = self._scope(
            user_id, agent_id, session_id,
        )
        items = await self.store.list(
            scope=scope,
            category=category,
            limit=limit,
            offset=offset,
        )
        return [
            i.model_dump(mode="json") for i in items
        ]

    # ---- sync API -------------------------------------------

    def add(
        self, content: str, **kwargs: Any,
    ) -> dict[str, Any]:
        """Store a new memory (sync).

        Args:
            content: Full text content (L2).
            **kwargs: Forwarded to ``async_add``.

        Returns:
            Dict with ``id`` and ``status``.
        """
        return _run_sync(
            self.async_add(content, **kwargs),
        )

    def search(
        self, query: str, **kwargs: Any,
    ) -> list[dict[str, Any]]:
        """Hybrid search over memories (sync).

        Args:
            query: Natural-language search text.
            **kwargs: Forwarded to ``async_search``.

        Returns:
            List of result dicts.
        """
        return _run_sync(
            self.async_search(query, **kwargs),
        )

    def get(
        self, memory_id: str,
    ) -> dict[str, Any] | None:
        """Retrieve a memory by ID (sync).

        Args:
            memory_id: UUID of the memory.

        Returns:
            Memory dict or None.
        """
        return _run_sync(
            self.async_get(memory_id),
        )

    def delete(self, memory_id: str) -> bool:
        """Delete a memory by ID (sync).

        Args:
            memory_id: UUID of the memory.

        Returns:
            True if deleted, False if not found.
        """
        return _run_sync(
            self.async_delete(memory_id),
        )

    def list(self, **kwargs: Any) -> list[dict[str, Any]]:
        """List memories with optional filters (sync).

        Args:
            **kwargs: Forwarded to ``async_list``.

        Returns:
            List of memory dicts.
        """
        return _run_sync(
            self.async_list(**kwargs),
        )
