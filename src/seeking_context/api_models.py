r"""Pydantic request/response models for the REST API.

All models use camelCase aliases so the JSON wire format
follows REST conventions while Python code uses snake_case.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


# -- Request models -------------------------------------------


class MemoryAddRequest(BaseModel):
    r"""Request body for POST /v1/memories.

    Attributes:
        content (str): Full text content (L2).
        category (str): Memory category name.
        abstract (str): One-line summary (L0).
        overview (str): Structured summary (L1).
        user_id (str | None): Optional user scope.
        agent_id (str | None): Optional agent scope.
        session_id (str | None): Optional session scope.
        metadata (dict | None): Arbitrary metadata.
        namespace (str | None): Framework namespace.
    """

    content: str
    category: str = "entities"
    abstract: str = ""
    overview: str = ""
    user_id: str | None = None
    agent_id: str | None = None
    session_id: str | None = None
    metadata: dict[str, Any] | None = None
    namespace: str | None = None


class MemoryUpdateRequest(BaseModel):
    r"""Request body for PATCH /v1/memories/{id}.

    Attributes:
        content (str | None): New content.
        abstract (str | None): New abstract.
        overview (str | None): New overview.
        metadata (dict | None): Metadata to merge.
    """

    content: str | None = None
    abstract: str | None = None
    overview: str | None = None
    metadata: dict[str, Any] | None = None


class MemorySearchRequest(BaseModel):
    r"""Request body for POST /v1/memories/search.

    Attributes:
        query (str): Natural-language search text.
        top_k (int): Maximum results.
        category (str | None): Category filter.
        user_id (str | None): User scope.
        agent_id (str | None): Agent scope.
        session_id (str | None): Session scope.
        level (int): Context level (0/1/2).
        namespace (str | None): Framework namespace.
    """

    query: str
    top_k: int = 10
    category: str | None = None
    user_id: str | None = None
    agent_id: str | None = None
    session_id: str | None = None
    level: int = 2
    namespace: str | None = None


class MemoryCrossSearchRequest(BaseModel):
    r"""Request body for POST /v1/memories/search/cross.

    Attributes:
        query (str): Natural-language search text.
        namespaces (list[str]): Namespaces to search.
        top_k (int): Maximum total results.
        category (str | None): Category filter.
        user_id (str | None): User scope within each ns.
        agent_id (str | None): Agent scope within each ns.
        level (int): Context level (0/1/2).
    """

    query: str
    namespaces: list[str]
    top_k: int = 10
    category: str | None = None
    user_id: str | None = None
    agent_id: str | None = None
    level: int = 2


class MemoryListParams(BaseModel):
    r"""Query params for GET /v1/memories.

    Attributes:
        category (str | None): Category filter.
        user_id (str | None): User scope.
        agent_id (str | None): Agent scope.
        session_id (str | None): Session scope.
        limit (int): Max items.
        offset (int): Items to skip.
        namespace (str | None): Framework namespace.
    """

    category: str | None = None
    user_id: str | None = None
    agent_id: str | None = None
    session_id: str | None = None
    limit: int = 20
    offset: int = 0
    namespace: str | None = None


class SessionStartRequest(BaseModel):
    r"""Request body for POST /v1/sessions.

    Attributes:
        session_id (str | None): Explicit session ID.
        user_id (str | None): User scope.
        agent_id (str | None): Agent scope.
        namespace (str | None): Framework namespace.
    """

    session_id: str | None = None
    user_id: str | None = None
    agent_id: str | None = None
    namespace: str | None = None


class SessionCompressRequest(BaseModel):
    r"""Request body for POST /v1/sessions/{id}/compress.

    Attributes:
        messages (list[str]): Raw message strings.
    """

    messages: list[str]


# -- Response models ------------------------------------------


class StatusResponse(BaseModel):
    r"""Response for GET /v1/status.

    Attributes:
        status (str): Health status string.
        version (str): Server version.
        memory_count (int): Total stored memories.
        active_sessions (int): Active session count.
    """

    status: str = "ok"
    version: str = ""
    memory_count: int = 0
    active_sessions: int = 0


class IdStatusResponse(BaseModel):
    r"""Generic response with id + status.

    Attributes:
        id (str): Resource identifier.
        status (str): Operation result.
    """

    id: str = ""
    status: str = ""


class ErrorResponse(BaseModel):
    r"""Error response.

    Attributes:
        error (str): Error description.
    """

    error: str
