r"""FastAPI REST layer for SeekingContext.

Provides a full REST API that mirrors the MCP tools,
so any HTTP client can interact with the memory store.

Usage::

    # Start the API server
    uv run seeking-context-api

    # Or programmatically
    from seeking_context.api import create_app
    app = create_app()

Endpoints::

    POST   /v1/memories              - Store a memory
    GET    /v1/memories              - List memories
    GET    /v1/memories/{id}         - Get a memory
    PATCH  /v1/memories/{id}         - Update a memory
    DELETE /v1/memories/{id}         - Delete a memory
    POST   /v1/memories/search       - Hybrid search
    POST   /v1/memories/search/cross - Cross-ns search
    POST   /v1/sessions              - Start session
    DELETE /v1/sessions/{id}         - End session
    POST   /v1/sessions/{id}/compress - Compress
    GET    /v1/sessions              - List sessions
    GET    /v1/status                - Health + stats
"""

from __future__ import annotations

import logging
import os
from typing import Any

from fastapi import (
    Depends,
    FastAPI,
    Header,
    HTTPException,
    Query,
)
from fastapi.responses import JSONResponse

from seeking_context import __version__
from seeking_context.api_models import (
    ErrorResponse,
    IdStatusResponse,
    MemoryAddRequest,
    MemoryCrossSearchRequest,
    MemorySearchRequest,
    MemoryUpdateRequest,
    SessionCompressRequest,
    SessionStartRequest,
    StatusResponse,
)
from seeking_context.config import get_config
from seeking_context.identity import resolve_scope
from seeking_context.models.memory import (
    ContextLevel,
    MemoryCategory,
    MemoryItem,
)
from seeking_context.models.scope import Scope
from seeking_context.storage.memory_store import (
    MemoryStore,
)
from seeking_context.tools.memory_tools import (
    _get_store,
    _make_scope,
    memory_search as _mcp_memory_search,
    memory_search_cross as _mcp_cross_search,
)
from seeking_context.tools.session_tools import (
    _sessions,
    session_compress as _mcp_session_compress,
    session_end as _mcp_session_end,
    session_list as _mcp_session_list,
    session_start as _mcp_session_start,
)

logger = logging.getLogger(__name__)


def _check_api_key(
    x_api_key: str | None = Header(
        None, alias="X-Api-Key",
    ),
) -> None:
    """Validate optional API key from header.

    If ``SEEKING_CONTEXT_API_KEY`` is set, requests must
    include a matching ``X-Api-Key`` header.

    Args:
        x_api_key: Value from the X-Api-Key header.

    Raises:
        HTTPException: 401 if key is required but missing
            or incorrect.
    """
    expected = os.environ.get("SEEKING_CONTEXT_API_KEY")
    if expected and x_api_key != expected:
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing API key",
        )


def _resolve_ns(
    namespace: str | None,
    header_ns: str | None,
) -> str | None:
    """Pick namespace from body or header.

    Body ``namespace`` takes priority over the
    ``X-Namespace`` header.

    Args:
        namespace: Namespace from request body.
        header_ns: Namespace from X-Namespace header.

    Returns:
        The resolved namespace or None.
    """
    return namespace or header_ns


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    Returns:
        Configured FastAPI app with all routes registered.
    """
    app = FastAPI(
        title="SeekingContext API",
        version=__version__,
        description=(
            "REST API for SeekingContext universal "
            "agent memory."
        ),
    )

    # -- status -----------------------------------------------

    @app.get(
        "/v1/status",
        response_model=StatusResponse,
    )
    async def status(
        _: None = Depends(_check_api_key),
    ) -> StatusResponse:
        """Health check and basic stats."""
        store = _get_store()
        count = await store.count()
        return StatusResponse(
            status="ok",
            version=__version__,
            memory_count=count,
            active_sessions=len(_sessions),
        )

    # -- memories CRUD ----------------------------------------

    @app.post("/v1/memories")
    async def add_memory(
        body: MemoryAddRequest,
        x_namespace: str | None = Header(
            None, alias="X-Namespace",
        ),
        _auth: None = Depends(_check_api_key),
    ) -> dict[str, Any]:
        """Store a new memory."""
        ns = _resolve_ns(body.namespace, x_namespace)
        scope = _make_scope(
            ns, body.user_id,
            body.agent_id, body.session_id,
        )
        store = _get_store()
        cat = MemoryCategory(body.category)
        item = MemoryItem(
            content=body.content,
            abstract=body.abstract or body.content[:200],
            overview=body.overview,
            category=cat,
            user_id=scope.user_id,
            agent_id=scope.agent_id,
            session_id=scope.session_id,
            metadata=body.metadata or {},
        )
        await store.add(item)
        return {"id": item.id, "status": "stored"}

    @app.get("/v1/memories")
    async def list_memories(
        category: str | None = Query(None),
        user_id: str | None = Query(None),
        agent_id: str | None = Query(None),
        session_id: str | None = Query(None),
        namespace: str | None = Query(None),
        limit: int = Query(20, ge=1, le=100),
        offset: int = Query(0, ge=0),
        x_namespace: str | None = Header(
            None, alias="X-Namespace",
        ),
        _auth: None = Depends(_check_api_key),
    ) -> list[dict[str, Any]]:
        """List memories with optional filters."""
        ns = _resolve_ns(namespace, x_namespace)
        scope = _make_scope(
            ns, user_id, agent_id, session_id,
        )
        store = _get_store()
        items = await store.list(
            scope=scope,
            category=category,
            limit=limit,
            offset=offset,
        )
        return [
            i.model_dump(mode="json") for i in items
        ]

    @app.get("/v1/memories/{memory_id}")
    async def get_memory(
        memory_id: str,
        _auth: None = Depends(_check_api_key),
    ) -> dict[str, Any]:
        """Retrieve a memory by ID."""
        store = _get_store()
        item = await store.get(memory_id)
        if not item:
            raise HTTPException(
                status_code=404,
                detail="Memory not found",
            )
        item.touch()
        await store.update(item)
        return item.model_dump(mode="json")

    @app.patch("/v1/memories/{memory_id}")
    async def update_memory(
        memory_id: str,
        body: MemoryUpdateRequest,
        _auth: None = Depends(_check_api_key),
    ) -> dict[str, Any]:
        """Update an existing memory."""
        store = _get_store()
        item = await store.get(memory_id)
        if not item:
            raise HTTPException(
                status_code=404,
                detail="Memory not found",
            )
        if body.content is not None:
            item.content = body.content
        if body.abstract is not None:
            item.abstract = body.abstract
        if body.overview is not None:
            item.overview = body.overview
        if body.metadata is not None:
            item.metadata.update(body.metadata)
        from datetime import datetime, timezone
        item.updated_at = datetime.now(
            timezone.utc,
        ).isoformat()
        await store.update(item)
        return {"id": item.id, "status": "updated"}

    @app.delete("/v1/memories/{memory_id}")
    async def delete_memory(
        memory_id: str,
        _auth: None = Depends(_check_api_key),
    ) -> dict[str, Any]:
        """Delete a memory."""
        store = _get_store()
        ok = await store.delete(memory_id)
        if not ok:
            raise HTTPException(
                status_code=404,
                detail="Memory not found",
            )
        return {
            "id": memory_id, "status": "deleted",
        }

    # -- search -----------------------------------------------

    @app.post("/v1/memories/search")
    async def search_memories(
        body: MemorySearchRequest,
        x_namespace: str | None = Header(
            None, alias="X-Namespace",
        ),
        _auth: None = Depends(_check_api_key),
    ) -> list[dict[str, Any]]:
        """Hybrid search over memories."""
        ns = _resolve_ns(body.namespace, x_namespace)
        return await _mcp_memory_search(
            query=body.query,
            top_k=body.top_k,
            category=body.category,
            user_id=body.user_id,
            agent_id=body.agent_id,
            session_id=body.session_id,
            level=body.level,
            namespace=ns,
        )

    @app.post("/v1/memories/search/cross")
    async def cross_search(
        body: MemoryCrossSearchRequest,
        _auth: None = Depends(_check_api_key),
    ) -> list[dict[str, Any]]:
        """Search across multiple namespaces."""
        return await _mcp_cross_search(
            query=body.query,
            namespaces=body.namespaces,
            top_k=body.top_k,
            category=body.category,
            user_id=body.user_id,
            agent_id=body.agent_id,
            level=body.level,
        )

    # -- sessions ---------------------------------------------

    @app.post("/v1/sessions")
    async def start_session(
        body: SessionStartRequest,
        x_namespace: str | None = Header(
            None, alias="X-Namespace",
        ),
        _auth: None = Depends(_check_api_key),
    ) -> dict[str, Any]:
        """Start a new session."""
        ns = _resolve_ns(body.namespace, x_namespace)
        return await _mcp_session_start(
            session_id=body.session_id,
            user_id=body.user_id,
            agent_id=body.agent_id,
            namespace=ns,
        )

    @app.delete("/v1/sessions/{session_id}")
    async def end_session(
        session_id: str,
        _auth: None = Depends(_check_api_key),
    ) -> dict[str, Any]:
        """End a session."""
        result = await _mcp_session_end(
            session_id=session_id,
        )
        if "error" in result:
            raise HTTPException(
                status_code=404,
                detail="Session not found",
            )
        return result

    @app.post(
        "/v1/sessions/{session_id}/compress",
    )
    async def compress_session(
        session_id: str,
        body: SessionCompressRequest,
        _auth: None = Depends(_check_api_key),
    ) -> dict[str, Any]:
        """Compress session messages."""
        result = await _mcp_session_compress(
            session_id=session_id,
            messages=body.messages,
        )
        if "error" in result:
            raise HTTPException(
                status_code=400,
                detail=result["error"],
            )
        return result

    @app.get("/v1/sessions")
    async def list_sessions(
        user_id: str | None = Query(None),
        agent_id: str | None = Query(None),
        namespace: str | None = Query(None),
        x_namespace: str | None = Header(
            None, alias="X-Namespace",
        ),
        _auth: None = Depends(_check_api_key),
    ) -> list[dict[str, Any]]:
        """List active sessions."""
        ns = _resolve_ns(namespace, x_namespace)
        return await _mcp_session_list(
            user_id=user_id,
            agent_id=agent_id,
            namespace=ns,
        )

    return app


def main() -> None:
    """CLI entry point for the REST API server."""
    import uvicorn

    config = get_config()
    config.ensure_data_dir()

    logging.basicConfig(
        level=logging.INFO,
        format=(
            "%(asctime)s %(name)s "
            "%(levelname)s %(message)s"
        ),
    )

    logger.info(
        "Starting SeekingContext REST API on %s:%d",
        config.rest_host,
        config.rest_port,
    )

    app = create_app()
    uvicorn.run(
        app,
        host=config.rest_host,
        port=config.rest_port,
        log_level="info",
    )


if __name__ == "__main__":
    main()
