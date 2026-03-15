r"""Core memory CRUD + search MCP tools.

Registers the six primary memory tools with the FastMCP
server: ``memory_add``, ``memory_search``, ``memory_get``,
``memory_update``, ``memory_delete``, ``memory_list``,
plus ``memory_search_cross`` for cross-namespace queries.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from seeking_context.config import get_config
from seeking_context.context.levels import (
    resolve_content_at_level,
)
from seeking_context.identity import (
    build_cross_scopes,
    resolve_scope,
)
from seeking_context.models.memory import (
    ContextLevel,
    MemoryCategory,
    MemoryItem,
)
from seeking_context.models.scope import Scope
from seeking_context.models.search import SearchResult
from seeking_context.search.hybrid import hybrid_search
from seeking_context.search.mmr import (
    MMRConfig,
    apply_mmr_to_hybrid,
)
from seeking_context.search.temporal_decay import (
    TemporalDecayConfig,
    apply_temporal_decay_to_hybrid,
)
from seeking_context.server import mcp
from seeking_context.storage.memory_store import MemoryStore

logger = logging.getLogger(__name__)

_store: MemoryStore | None = None


def _get_store() -> MemoryStore:
    """Return the global MemoryStore singleton.

    Returns:
        Initialised MemoryStore instance.
    """
    global _store
    if _store is None:
        _store = MemoryStore()
    return _store


def _make_scope(
    namespace: str | None,
    user_id: str | None,
    agent_id: str | None,
    session_id: str | None = None,
) -> Scope:
    """Build a Scope with optional namespace prefixing.

    When ``namespace`` is provided, user_id and agent_id
    are prefixed to prevent cross-framework collisions.
    When ``namespace`` is None **and** user_id/agent_id
    are both None, returns an empty Scope (no filtering)
    to preserve full backward compatibility.

    Args:
        namespace: Optional framework identifier.
        user_id: Optional user scope.
        agent_id: Optional agent scope.
        session_id: Optional session UUID.

    Returns:
        A Scope object for storage/query filtering.
    """
    if namespace is not None:
        return resolve_scope(
            namespace=namespace,
            user_id=user_id,
            agent_id=agent_id,
            session_id=session_id,
        )
    # Backward compat: raw scope (no prefixing)
    return Scope(
        user_id=user_id,
        agent_id=agent_id,
        session_id=session_id,
    )


# -- memory_add ------------------------------------------------


@mcp.tool()
async def memory_add(
    content: str,
    category: str = "entities",
    abstract: str = "",
    overview: str = "",
    user_id: str | None = None,
    agent_id: str | None = None,
    session_id: str | None = None,
    metadata: dict[str, Any] | None = None,
    namespace: str | None = None,
) -> dict[str, Any]:
    """Store a new memory.

    Args:
        content: Full text content (L2 detail).
        category: Memory category (profile, preferences,
            entities, events, cases, patterns).
        abstract: One-line summary (L0, ~100 tokens).
        overview: Structured summary (L1, ~2K tokens).
        user_id: Optional user scope.
        agent_id: Optional agent scope.
        session_id: Optional session scope.
        metadata: Arbitrary key-value metadata.
        namespace: Optional framework namespace for
            cross-framework isolation.

    Returns:
        Dict with ``id`` and ``status`` keys.
    """
    store = _get_store()
    scope = _make_scope(
        namespace, user_id, agent_id, session_id,
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
    await store.add(item)
    return {"id": item.id, "status": "stored"}


# -- memory_search ---------------------------------------------


@mcp.tool()
async def memory_search(
    query: str,
    top_k: int = 10,
    category: str | None = None,
    user_id: str | None = None,
    agent_id: str | None = None,
    session_id: str | None = None,
    level: int = 2,
    namespace: str | None = None,
) -> list[dict[str, Any]]:
    """Hybrid search over stored memories.

    Combines vector similarity (70%) with BM25 keyword
    matching (30%), applies temporal decay and MMR
    diversity re-ranking.

    Args:
        query: Natural-language search text.
        top_k: Maximum results to return.
        category: Optional category filter.
        user_id: Optional user scope.
        agent_id: Optional agent scope.
        session_id: Optional session scope.
        level: Context level (0=abstract, 1=overview,
            2=detail).
        namespace: Optional framework namespace.

    Returns:
        List of result dicts with ``id``, ``score``,
        ``content``, ``category``, ``vector_score``,
        ``text_score``.
    """
    store = _get_store()
    config = get_config()
    scope = _make_scope(
        namespace, user_id, agent_id, session_id,
    )
    ctx_level = ContextLevel(level)

    # 1. Hybrid search
    results = await hybrid_search(
        store=store,
        query=query,
        top_k=top_k * 2,
        vector_weight=config.vector_weight,
        text_weight=config.text_weight,
        scope=scope,
        category=category,
    )

    # 2. Temporal decay
    decay_cfg = TemporalDecayConfig(
        half_life_days=(
            config.temporal_decay_half_life_days
        ),
        boost_recent_days=config.boost_recent_days,
        boost_factor=config.boost_factor,
        min_decay=config.min_decay,
    )
    results = apply_temporal_decay_to_hybrid(
        results, decay_cfg
    )

    # 3. MMR re-ranking
    if len(results) > 1:
        ids = [r.id for r in results]
        embeddings = await store.get_embeddings(ids)
        mmr_cfg = MMRConfig(
            lambda_param=config.mmr_lambda,
            top_k=top_k,
        )
        results = apply_mmr_to_hybrid(
            results, embeddings, mmr_cfg
        )

    # 4. Build response
    output: list[dict[str, Any]] = []
    for r in results[:top_k]:
        item = await store.get(r.id)
        if not item:
            continue
        item.touch()
        await store.update(item)

        text = resolve_content_at_level(
            item, ctx_level,
        )
        output.append(
            {
                "id": item.id,
                "score": round(r.combined_score, 4),
                "vector_score": round(
                    r.vector_score, 4,
                ),
                "text_score": round(
                    r.text_score, 4,
                ),
                "content": text,
                "category": item.category.value,
            }
        )

    return output


# -- memory_search_cross ---------------------------------------


@mcp.tool()
async def memory_search_cross(
    query: str,
    namespaces: list[str],
    top_k: int = 10,
    category: str | None = None,
    user_id: str | None = None,
    agent_id: str | None = None,
    level: int = 2,
) -> list[dict[str, Any]]:
    """Search across multiple namespaces.

    Runs a hybrid search in each namespace and merges
    results by combined score.  Useful when an agent
    needs to access memories stored by other frameworks.

    Args:
        query: Natural-language search text.
        namespaces: List of namespace strings to search.
        top_k: Maximum total results to return.
        category: Optional category filter.
        user_id: Optional user scope within each ns.
        agent_id: Optional agent scope within each ns.
        level: Context level (0/1/2).

    Returns:
        Merged result list sorted by score.
    """
    all_results: list[dict[str, Any]] = []
    for ns in namespaces:
        partial = await memory_search(
            query=query,
            top_k=top_k,
            category=category,
            user_id=user_id,
            agent_id=agent_id,
            level=level,
            namespace=ns,
        )
        for item in partial:
            item["namespace"] = ns
        all_results.extend(partial)

    # Sort by score descending, take top_k
    all_results.sort(
        key=lambda x: x.get("score", 0),
        reverse=True,
    )
    return all_results[:top_k]


# -- memory_get ------------------------------------------------


@mcp.tool()
async def memory_get(
    memory_id: str,
) -> dict[str, Any]:
    """Retrieve a memory by its ID.

    Args:
        memory_id: The UUID of the memory.

    Returns:
        Full memory dict, or error dict if not found.
    """
    store = _get_store()
    item = await store.get(memory_id)
    if not item:
        return {"error": "not_found"}
    item.touch()
    await store.update(item)
    return item.model_dump(mode="json")


# -- memory_update ---------------------------------------------


@mcp.tool()
async def memory_update(
    memory_id: str,
    content: str | None = None,
    abstract: str | None = None,
    overview: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Update an existing memory.

    Only provided fields are changed; others remain
    untouched.

    Args:
        memory_id: UUID of the memory to update.
        content: New full content (L2).
        abstract: New abstract (L0).
        overview: New overview (L1).
        metadata: Metadata dict to merge into existing.

    Returns:
        Updated memory dict, or error.
    """
    store = _get_store()
    item = await store.get(memory_id)
    if not item:
        return {"error": "not_found"}

    if content is not None:
        item.content = content
    if abstract is not None:
        item.abstract = abstract
    if overview is not None:
        item.overview = overview
    if metadata is not None:
        item.metadata.update(metadata)
    item.updated_at = datetime.now(
        timezone.utc
    ).isoformat()

    await store.update(item)
    return {"id": item.id, "status": "updated"}


# -- memory_delete ---------------------------------------------


@mcp.tool()
async def memory_delete(
    memory_id: str,
) -> dict[str, Any]:
    """Delete a memory by its ID.

    Args:
        memory_id: UUID of the memory to delete.

    Returns:
        Dict with ``status`` key.
    """
    store = _get_store()
    ok = await store.delete(memory_id)
    if not ok:
        return {"error": "not_found"}
    return {"id": memory_id, "status": "deleted"}


# -- memory_list -----------------------------------------------


@mcp.tool()
async def memory_list(
    category: str | None = None,
    user_id: str | None = None,
    agent_id: str | None = None,
    session_id: str | None = None,
    limit: int = 20,
    offset: int = 0,
    namespace: str | None = None,
) -> list[dict[str, Any]]:
    """List memories with optional scope and category.

    Args:
        category: Filter by category.
        user_id: Scope by user.
        agent_id: Scope by agent.
        session_id: Scope by session.
        limit: Max items to return.
        offset: Items to skip.
        namespace: Optional framework namespace.

    Returns:
        List of memory dicts.
    """
    store = _get_store()
    scope = _make_scope(
        namespace, user_id, agent_id, session_id,
    )
    items = await store.list(
        scope=scope,
        category=category,
        limit=limit,
        offset=offset,
    )
    return [i.model_dump(mode="json") for i in items]


# -- memory_rebuild_index --------------------------------------


@mcp.tool()
async def memory_rebuild_index() -> dict[str, Any]:
    """Rebuild vector + FTS indexes from markdown files.

    Use after manually editing ``.md`` files or if indexes
    become corrupted.  Proves markdown is the canonical
    source of truth.

    Returns:
        Dict with ``count`` of re-indexed memories and
        ``status`` key.
    """
    store = _get_store()
    if not store.markdown:
        return {
            "error": "markdown_disabled",
            "message": (
                "Markdown storage is not enabled. "
                "Set SEEKING_CONTEXT_MARKDOWN_ENABLED=true."
            ),
        }

    count = await store.markdown.rebuild_indexes(
        store.vector, store.meta
    )
    return {
        "count": count,
        "status": "rebuilt",
    }
