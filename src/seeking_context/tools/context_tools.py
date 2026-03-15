r"""Context-oriented MCP tools.

Provides ``context_search`` (semantic search) and
``context_mark_important`` (flag content as a memory).
"""

from __future__ import annotations

import logging
from typing import Any

from seeking_context.identity import resolve_scope
from seeking_context.models.memory import (
    MemoryCategory,
    MemoryItem,
)
from seeking_context.models.scope import Scope
from seeking_context.server import mcp
from seeking_context.tools.memory_tools import (
    _get_store,
    memory_search,
)

logger = logging.getLogger(__name__)


@mcp.tool()
async def context_search(
    query: str,
    top_k: int = 5,
    user_id: str | None = None,
    agent_id: str | None = None,
    namespace: str | None = None,
) -> list[dict[str, Any]]:
    """Semantic search over memories (convenience wrapper).

    Identical to ``memory_search`` but with lower default
    ``top_k`` and returns only L1 (overview) content for
    compact context injection.

    Args:
        query: Natural-language search text.
        top_k: Maximum results (default 5).
        user_id: Optional user scope.
        agent_id: Optional agent scope.
        namespace: Optional framework namespace.

    Returns:
        List of result dicts with overview-level content.
    """
    return await memory_search(
        query=query,
        top_k=top_k,
        user_id=user_id,
        agent_id=agent_id,
        level=1,
        namespace=namespace,
    )


@mcp.tool()
async def context_mark_important(
    content: str,
    category: str = "entities",
    user_id: str | None = None,
    agent_id: str | None = None,
    metadata: dict[str, Any] | None = None,
    namespace: str | None = None,
) -> dict[str, Any]:
    """Flag content as an important memory.

    Creates a new memory with the ``important`` metadata
    flag set to ``true``.

    Args:
        content: The text to remember.
        category: Memory category.
        user_id: Optional user scope.
        agent_id: Optional agent scope.
        metadata: Extra metadata.
        namespace: Optional framework namespace.

    Returns:
        Dict with ``id`` and ``status``.
    """
    store = _get_store()
    cat = MemoryCategory(category)
    meta = metadata or {}
    meta["important"] = True

    # Apply namespace if provided
    if namespace is not None:
        scope = resolve_scope(
            namespace=namespace,
            user_id=user_id,
            agent_id=agent_id,
        )
        uid = scope.user_id
        aid = scope.agent_id
    else:
        uid = user_id
        aid = agent_id

    item = MemoryItem(
        content=content,
        abstract=content[:200],
        category=cat,
        user_id=uid,
        agent_id=aid,
        metadata=meta,
    )
    await store.add(item)
    logger.info("Marked important: %s", item.id)
    return {"id": item.id, "status": "stored"}
