r"""Session lifecycle MCP tools.

Provides ``session_start``, ``session_end``,
``session_compress``, and ``session_list`` for managing
conversational sessions and extracting memories from
them.

Inspired by less-agent's ``.context/`` per-session file
isolation and ``digest.md`` compaction patterns.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from seeking_context.identity import resolve_scope
from seeking_context.models.memory import (
    MemoryCategory,
    MemoryItem,
)
from seeking_context.models.scope import Scope
from seeking_context.server import mcp
from seeking_context.tools.memory_tools import (
    _get_store,
    _make_scope,
)

logger = logging.getLogger(__name__)

# In-memory session registry (lightweight)
_sessions: dict[str, dict[str, Any]] = {}


@mcp.tool()
async def session_start(
    session_id: str | None = None,
    user_id: str | None = None,
    agent_id: str | None = None,
    namespace: str | None = None,
) -> dict[str, Any]:
    """Initialise a new session scope.

    Creates a session record so that subsequent memory
    operations can be scoped to this session.

    Args:
        session_id: Optional explicit session ID.  A UUID
            is generated if not provided.
        user_id: Optional user scope.
        agent_id: Optional agent scope.
        namespace: Optional framework namespace.

    Returns:
        Dict with ``session_id`` and ``status``.
    """
    sid = session_id or str(uuid4())
    scope = _make_scope(
        namespace, user_id, agent_id, sid,
    )
    _sessions[sid] = {
        "session_id": sid,
        "user_id": scope.user_id,
        "agent_id": scope.agent_id,
        "namespace": namespace,
        "started_at": datetime.now(
            timezone.utc
        ).isoformat(),
        "messages": [],
    }
    logger.info("Session started: %s", sid)
    return {"session_id": sid, "status": "started"}


@mcp.tool()
async def session_end(
    session_id: str,
) -> dict[str, Any]:
    """Finalise a session.

    Removes the session from the in-memory registry and
    stores a session-end event memory.

    Args:
        session_id: ID of the session to end.

    Returns:
        Dict with ``session_id`` and ``status``.
    """
    session = _sessions.pop(session_id, None)
    if not session:
        return {"error": "session_not_found"}

    store = _get_store()
    item = MemoryItem(
        content=f"Session {session_id} ended.",
        abstract=f"Session {session_id} ended.",
        category=MemoryCategory.EVENTS,
        user_id=session.get("user_id"),
        agent_id=session.get("agent_id"),
        session_id=session_id,
        metadata={"event": "session_end"},
    )
    await store.add(item)
    logger.info("Session ended: %s", session_id)
    return {
        "session_id": session_id,
        "status": "ended",
    }


@mcp.tool()
async def session_compress(
    session_id: str,
    messages: list[str],
) -> dict[str, Any]:
    """Compress session messages into L0/L1 summaries.

    Takes a list of raw messages and produces a compact
    abstract (L0) and an overview (L1) stored as a
    memory under the session scope.

    Follows the same three-tier pattern as less-agent's
    ``.abstract.md`` / ``.overview.md`` / full transcript.

    Args:
        session_id: Session to associate the summary with.
        messages: List of message strings from the session.

    Returns:
        Dict with the created memory ``id`` and summaries.
    """
    if not messages:
        return {"error": "no_messages"}

    # Simple extractive compression
    abstract = messages[0][:200]
    overview = "\n".join(
        m[:500] for m in messages[:10]
    )
    full = "\n\n".join(messages)

    session = _sessions.get(session_id, {})
    store = _get_store()

    item = MemoryItem(
        content=full,
        abstract=abstract,
        overview=overview,
        category=MemoryCategory.EVENTS,
        user_id=session.get("user_id"),
        agent_id=session.get("agent_id"),
        session_id=session_id,
        metadata={"compressed": True},
    )
    await store.add(item)
    logger.info(
        "Compressed %d messages for session %s",
        len(messages),
        session_id,
    )
    return {
        "id": item.id,
        "abstract": abstract,
        "overview": overview[:500],
        "status": "compressed",
    }


@mcp.tool()
async def session_list(
    user_id: str | None = None,
    agent_id: str | None = None,
    namespace: str | None = None,
) -> list[dict[str, Any]]:
    """List active sessions.

    Args:
        user_id: Optional filter by user.
        agent_id: Optional filter by agent.
        namespace: Optional framework namespace filter.

    Returns:
        List of session info dicts.
    """
    # Build expected scope for filtering
    scope = _make_scope(
        namespace, user_id, agent_id,
    )

    results: list[dict[str, Any]] = []
    for sid, info in _sessions.items():
        if scope.user_id and (
            info.get("user_id") != scope.user_id
        ):
            continue
        if scope.agent_id and (
            info.get("agent_id") != scope.agent_id
        ):
            continue
        results.append(
            {
                "session_id": sid,
                "user_id": info.get("user_id"),
                "agent_id": info.get("agent_id"),
                "started_at": info.get("started_at"),
            }
        )
    return results
