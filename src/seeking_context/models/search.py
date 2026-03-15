r"""Search-related data models.

Defines ``SearchQuery`` (input) and ``SearchResult``
(output) for the hybrid search pipeline.

Attributes:
    SearchQuery: Pydantic model encapsulating query text,
        top-k, scope filters and desired context level.
    SearchResult: Pydantic model wrapping a MemoryItem
        together with relevance scores and the returned
        context level.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from seeking_context.models.memory import (
    ContextLevel,
    MemoryCategory,
    MemoryItem,
)


class SearchQuery(BaseModel):
    r"""Input parameters for a memory search operation.

    Attributes:
        query (str): Natural-language search text.
        top_k (int): Maximum number of results.
        category (MemoryCategory | None): Optional filter.
        user_id (str | None): Scope by user.
        agent_id (str | None): Scope by agent.
        session_id (str | None): Scope by session.
        level (ContextLevel): Desired detail level.
    """

    query: str
    top_k: int = 10
    category: MemoryCategory | None = None
    user_id: str | None = None
    agent_id: str | None = None
    session_id: str | None = None
    level: ContextLevel = ContextLevel.DETAIL


class SearchResult(BaseModel):
    r"""A single result from the search pipeline.

    Wraps a ``MemoryItem`` with scoring information so
    callers can understand both the content and why it
    was ranked where it is.

    Attributes:
        memory (MemoryItem): The matched memory.
        score (float): Final combined score after all
            pipeline stages.
        vector_score (float): Raw vector similarity score.
        text_score (float): Raw BM25 keyword score.
        level (ContextLevel): The detail level returned.
        content_at_level (str): Pre-resolved content text
            at the requested level.
    """

    memory: MemoryItem
    score: float = 0.0
    vector_score: float = 0.0
    text_score: float = 0.0
    level: ContextLevel = ContextLevel.DETAIL
    content_at_level: str = Field(default="")
