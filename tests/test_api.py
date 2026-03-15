"""Tests for the FastAPI REST layer."""

from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from seeking_context.api import create_app
from seeking_context.config import SeekingContextConfig
from seeking_context.storage.memory_store import (
    MemoryStore,
)
from seeking_context.tools import memory_tools
from seeking_context.tools import session_tools


@pytest_asyncio.fixture()
async def client(
    store: MemoryStore,
) -> AsyncClient:
    """Provide an httpx async test client.

    Patches the global store so the API uses temp storage,
    then yields an ``AsyncClient`` bound to the app.

    Args:
        store: Test MemoryStore from conftest.

    Yields:
        AsyncClient for making requests.
    """
    memory_tools._store = store
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as ac:
        yield ac
    # Clean up session registry
    session_tools._sessions.clear()


@pytest.mark.asyncio
class TestStatusEndpoint:
    """Tests for GET /v1/status."""

    async def test_returns_ok(
        self, client: AsyncClient,
    ) -> None:
        """Status endpoint returns ok."""
        resp = await client.get("/v1/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "version" in data


@pytest.mark.asyncio
class TestMemoryCRUD:
    """Tests for memory CRUD endpoints."""

    async def test_add_and_get(
        self, client: AsyncClient,
    ) -> None:
        """POST then GET a memory."""
        resp = await client.post(
            "/v1/memories",
            json={
                "content": "REST test content",
                "category": "entities",
            },
        )
        assert resp.status_code == 200
        mid = resp.json()["id"]

        resp = await client.get(
            f"/v1/memories/{mid}",
        )
        assert resp.status_code == 200
        assert resp.json()["content"] == (
            "REST test content"
        )

    async def test_update(
        self, client: AsyncClient,
    ) -> None:
        """PATCH updates memory content."""
        resp = await client.post(
            "/v1/memories",
            json={"content": "original"},
        )
        mid = resp.json()["id"]

        resp = await client.patch(
            f"/v1/memories/{mid}",
            json={"content": "updated"},
        )
        assert resp.status_code == 200

        resp = await client.get(
            f"/v1/memories/{mid}",
        )
        assert resp.json()["content"] == "updated"

    async def test_delete(
        self, client: AsyncClient,
    ) -> None:
        """DELETE removes a memory."""
        resp = await client.post(
            "/v1/memories",
            json={"content": "to delete"},
        )
        mid = resp.json()["id"]

        resp = await client.delete(
            f"/v1/memories/{mid}",
        )
        assert resp.status_code == 200

        resp = await client.get(
            f"/v1/memories/{mid}",
        )
        assert resp.status_code == 404

    async def test_list(
        self, client: AsyncClient,
    ) -> None:
        """GET /v1/memories lists stored items."""
        for i in range(3):
            await client.post(
                "/v1/memories",
                json={
                    "content": f"item {i}",
                    "user_id": "rest-u1",
                },
            )
        resp = await client.get(
            "/v1/memories",
            params={"user_id": "rest-u1"},
        )
        assert resp.status_code == 200
        assert len(resp.json()) == 3

    async def test_not_found(
        self, client: AsyncClient,
    ) -> None:
        """GET non-existent memory returns 404."""
        resp = await client.get(
            "/v1/memories/nonexistent-id",
        )
        assert resp.status_code == 404


@pytest.mark.asyncio
class TestNamespaceHeader:
    """Tests for X-Namespace header support."""

    async def test_namespace_via_header(
        self, client: AsyncClient,
    ) -> None:
        """X-Namespace header applies namespace."""
        resp = await client.post(
            "/v1/memories",
            json={
                "content": "namespaced content",
                "user_id": "alice",
            },
            headers={"X-Namespace": "test-ns"},
        )
        assert resp.status_code == 200
        mid = resp.json()["id"]

        resp = await client.get(
            f"/v1/memories/{mid}",
        )
        data = resp.json()
        # user_id should be prefixed
        assert data["user_id"] == "test-ns:alice"


@pytest.mark.asyncio
class TestSearchEndpoint:
    """Tests for POST /v1/memories/search."""

    async def test_search_returns_results(
        self, client: AsyncClient,
    ) -> None:
        """Search finds stored memories."""
        await client.post(
            "/v1/memories",
            json={
                "content": "Python programming language",
            },
        )
        await client.post(
            "/v1/memories",
            json={
                "content": "Cooking pasta recipe",
            },
        )

        resp = await client.post(
            "/v1/memories/search",
            json={
                "query": "programming",
                "top_k": 2,
            },
        )
        assert resp.status_code == 200
        results = resp.json()
        assert len(results) > 0


@pytest.mark.asyncio
class TestSessionEndpoints:
    """Tests for session lifecycle endpoints."""

    async def test_session_lifecycle(
        self, client: AsyncClient,
    ) -> None:
        """Start, list, and end a session."""
        resp = await client.post(
            "/v1/sessions",
            json={"user_id": "sess-user"},
        )
        assert resp.status_code == 200
        sid = resp.json()["session_id"]

        resp = await client.get("/v1/sessions")
        assert resp.status_code == 200
        sessions = resp.json()
        assert any(
            s["session_id"] == sid for s in sessions
        )

        resp = await client.delete(
            f"/v1/sessions/{sid}",
        )
        assert resp.status_code == 200

    async def test_end_nonexistent_session(
        self, client: AsyncClient,
    ) -> None:
        """Ending a bad session returns 404."""
        resp = await client.delete(
            "/v1/sessions/fake-session-id",
        )
        assert resp.status_code == 404
