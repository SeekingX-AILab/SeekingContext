r"""MCP resources exposing memory:// URIs.

Provides read-only resources for server status, available
categories, user overviews, and session abstracts.
"""

from __future__ import annotations

import logging
from typing import Any

from seeking_context.context.levels import (
    summarise_items_at_level,
)
from seeking_context.models.memory import (
    ContextLevel,
    MemoryCategory,
)
from seeking_context.models.scope import Scope
from seeking_context.server import mcp
from seeking_context.tools.memory_tools import _get_store

logger = logging.getLogger(__name__)


@mcp.resource("memory://status")
async def memory_status() -> str:
    """Server status and total memory count.

    Returns:
        Human-readable status string.
    """
    store = _get_store()
    total = await store.count()
    return (
        f"SeekingContext status: OK\n"
        f"Total memories: {total}"
    )


@mcp.resource("memory://categories")
async def memory_categories() -> str:
    """Available categories with counts.

    Returns:
        Formatted list of categories and their counts.
    """
    store = _get_store()
    lines: list[str] = []
    for cat in MemoryCategory:
        cnt = await store.count(category=cat.value)
        lines.append(f"- {cat.value}: {cnt}")
    return "Memory categories:\n" + "\n".join(lines)


@mcp.resource("memory://user/{user_id}/overview")
async def user_overview(user_id: str) -> str:
    """L1 overview of a user's memory space.

    Args:
        user_id: The user identifier.

    Returns:
        Concatenated overview-level summaries.
    """
    store = _get_store()
    scope = Scope(user_id=user_id)
    items = await store.list(scope=scope, limit=50)
    if not items:
        return f"No memories found for user {user_id}."
    return summarise_items_at_level(
        items, ContextLevel.OVERVIEW
    )


@mcp.resource("memory://session/{session_id}/abstract")
async def session_abstract(session_id: str) -> str:
    """L0 abstract for a session.

    Args:
        session_id: The session identifier.

    Returns:
        Concatenated abstract-level summaries.
    """
    store = _get_store()
    scope = Scope(session_id=session_id)
    items = await store.list(scope=scope, limit=50)
    if not items:
        return f"No memories for session {session_id}."
    return summarise_items_at_level(
        items, ContextLevel.ABSTRACT
    )
