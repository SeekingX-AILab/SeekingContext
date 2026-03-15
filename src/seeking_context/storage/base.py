r"""Abstract protocols for storage backends.

Defines ``VectorStore`` and ``MetadataStore`` protocols
that concrete backends must implement.  This allows
swapping ChromaDB for another vector DB or SQLite for
another metadata store without touching upper layers.

Attributes:
    VectorStore: Protocol for vector similarity backends.
    MetadataStore: Protocol for metadata + FTS backends.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class VectorStore(Protocol):
    r"""Protocol for vector similarity search backends.

    Implementors must provide async insert, search, delete
    and get operations over embedded documents.
    """

    async def insert(
        self,
        doc_id: str,
        text: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Insert or upsert a document.

        Args:
            doc_id: Unique document identifier.
            text: Text to embed and store.
            metadata: Optional metadata dict attached
                to the document for filtering.
        """
        ...

    async def search(
        self,
        query: str,
        top_k: int = 10,
        where: dict[str, Any] | None = None,
    ) -> list[tuple[str, float]]:
        """Search by vector similarity.

        Args:
            query: Natural-language query text.
            top_k: Maximum results to return.
            where: Optional metadata filter dict.

        Returns:
            List of ``(doc_id, score)`` tuples ordered
            by descending similarity.
        """
        ...

    async def delete(self, doc_id: str) -> None:
        """Delete a document by id.

        Args:
            doc_id: Document identifier to remove.
        """
        ...

    async def get(
        self, doc_id: str
    ) -> dict[str, Any] | None:
        """Get a document's stored data by id.

        Args:
            doc_id: Document identifier.

        Returns:
            Dict with keys ``id``, ``text``, ``metadata``
            or None if not found.
        """
        ...


@runtime_checkable
class MetadataStore(Protocol):
    r"""Protocol for metadata + full-text search backends.

    Stores the full ``MemoryItem`` JSON alongside an FTS
    index for BM25 keyword search.
    """

    async def save(
        self,
        doc_id: str,
        data: dict[str, Any],
    ) -> None:
        """Persist a memory item's data.

        Args:
            doc_id: Unique document identifier.
            data: Serialised MemoryItem dict.
        """
        ...

    async def get(
        self, doc_id: str
    ) -> dict[str, Any] | None:
        """Retrieve a memory item by id.

        Args:
            doc_id: Document identifier.

        Returns:
            The stored dict or None.
        """
        ...

    async def delete(self, doc_id: str) -> None:
        """Delete a memory item.

        Args:
            doc_id: Document identifier.
        """
        ...

    async def list(
        self,
        where: dict[str, Any] | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """List memory items with optional filtering.

        Args:
            where: Key-value filters applied to stored
                data fields.
            limit: Maximum items to return.
            offset: Number of items to skip.

        Returns:
            List of stored dicts.
        """
        ...

    async def fts_search(
        self,
        query: str,
        top_k: int = 10,
        where: dict[str, Any] | None = None,
    ) -> list[tuple[str, float]]:
        """Full-text (BM25) keyword search.

        Args:
            query: Keyword query string.
            top_k: Maximum results.
            where: Optional metadata filter.

        Returns:
            List of ``(doc_id, score)`` tuples.
        """
        ...

    async def count(
        self,
        where: dict[str, Any] | None = None,
    ) -> int:
        """Count stored items matching filters.

        Args:
            where: Optional filter dict.

        Returns:
            Number of matching items.
        """
        ...
