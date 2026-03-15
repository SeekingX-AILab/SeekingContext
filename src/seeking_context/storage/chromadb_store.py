r"""ChromaDB vector store backend.

Wraps ChromaDB as the default vector similarity backend
for SeekingContext.  Uses the built-in sentence-transformer
``all-MiniLM-L6-v2`` (384-dim) for embedding generation.

Storage location defaults to ``~/.seeking_context/chroma/``.

Attributes:
    ChromaDBStore: Async wrapper around ChromaDB's
        persistent client with metadata filtering.
"""

from __future__ import annotations

import asyncio
import logging
from functools import partial
from typing import Any

import chromadb

logger = logging.getLogger(__name__)


class ChromaDBStore:
    r"""ChromaDB-backed vector store.

    Attributes:
        persist_dir (str): Directory for ChromaDB storage.
        collection_name (str): Name of the ChromaDB
            collection.
        embedding_model (str): Sentence-transformer model
            name used for embeddings.
    """

    def __init__(
        self,
        persist_dir: str,
        collection_name: str = "seeking_context",
        embedding_model: str = "all-MiniLM-L6-v2",
    ) -> None:
        """Initialise the ChromaDB store.

        Args:
            persist_dir: Path to ChromaDB persistence dir.
            collection_name: Collection name.
            embedding_model: Embedding model identifier.
        """
        self._persist_dir = persist_dir
        self._collection_name = collection_name
        self._embedding_model = embedding_model
        self._client: chromadb.ClientAPI | None = None
        self._collection: chromadb.Collection | None = None

    def _ensure_client(self) -> chromadb.Collection:
        """Lazily create the ChromaDB client + collection.

        Returns:
            The active ChromaDB collection.
        """
        if self._collection is not None:
            return self._collection

        self._client = chromadb.PersistentClient(
            path=self._persist_dir,
        )
        self._collection = (
            self._client.get_or_create_collection(
                name=self._collection_name,
                metadata={
                    "hnsw:space": "cosine",
                },
            )
        )
        return self._collection

    async def insert(
        self,
        doc_id: str,
        text: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Insert or upsert a document into ChromaDB.

        Args:
            doc_id: Unique document identifier.
            text: Text to embed and store.
            metadata: Optional metadata dict. Non-string
                values are coerced to strings for ChromaDB
                compatibility.
        """
        col = self._ensure_client()
        clean_meta = _clean_metadata(metadata or {})

        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            None,
            partial(
                col.upsert,
                ids=[doc_id],
                documents=[text],
                metadatas=[clean_meta],
            ),
        )

    async def search(
        self,
        query: str,
        top_k: int = 10,
        where: dict[str, Any] | None = None,
    ) -> list[tuple[str, float]]:
        """Search by vector similarity in ChromaDB.

        Args:
            query: Natural-language query.
            top_k: Maximum results.
            where: Optional metadata filter (ChromaDB
                ``where`` clause).

        Returns:
            List of ``(doc_id, score)`` tuples with
            scores normalised to 0-1 (higher is better).
        """
        col = self._ensure_client()
        kwargs: dict[str, Any] = {
            "query_texts": [query],
            "n_results": top_k,
        }
        if where:
            clean_where = _build_chroma_where(where)
            if clean_where:
                kwargs["where"] = clean_where

        loop = asyncio.get_running_loop()
        results = await loop.run_in_executor(
            None, partial(col.query, **kwargs)
        )

        pairs: list[tuple[str, float]] = []
        if results and results["ids"]:
            ids = results["ids"][0]
            distances = results["distances"][0]
            for doc_id, dist in zip(ids, distances):
                # ChromaDB cosine distance -> similarity
                score = max(0.0, 1.0 - dist)
                pairs.append((doc_id, score))
        return pairs

    async def delete(self, doc_id: str) -> None:
        """Delete a document from ChromaDB.

        Args:
            doc_id: Document identifier to remove.
        """
        col = self._ensure_client()
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            None, partial(col.delete, ids=[doc_id])
        )

    async def get(
        self, doc_id: str
    ) -> dict[str, Any] | None:
        """Get a document by id from ChromaDB.

        Args:
            doc_id: Document identifier.

        Returns:
            Dict with ``id``, ``text``, ``metadata`` keys
            or None if not found.
        """
        col = self._ensure_client()
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(
            None, partial(col.get, ids=[doc_id])
        )
        if not result or not result["ids"]:
            return None
        return {
            "id": result["ids"][0],
            "text": (result["documents"] or [""])[0],
            "metadata": (result["metadatas"] or [{}])[0],
        }

    async def get_embeddings(
        self, doc_ids: list[str]
    ) -> dict[str, list[float]]:
        """Fetch stored embeddings for given ids.

        Args:
            doc_ids: List of document identifiers.

        Returns:
            Mapping from doc_id to embedding vector.
        """
        if not doc_ids:
            return {}
        col = self._ensure_client()
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(
            None,
            partial(
                col.get,
                ids=doc_ids,
                include=["embeddings"],
            ),
        )
        out: dict[str, list[float]] = {}
        if result and result["ids"]:
            embeddings = result.get("embeddings")
            if embeddings is None:
                embeddings = []
            for did, emb in zip(result["ids"], embeddings):
                if emb is not None:
                    out[did] = list(emb)
        return out


def _clean_metadata(
    meta: dict[str, Any],
) -> dict[str, str | int | float | bool]:
    """Coerce metadata values to ChromaDB-safe types.

    Args:
        meta: Raw metadata dict.

    Returns:
        Dict with values coerced to str/int/float/bool.
    """
    clean: dict[str, str | int | float | bool] = {}
    for k, v in meta.items():
        if v is None:
            continue
        if isinstance(v, (str, int, float, bool)):
            clean[k] = v
        else:
            clean[k] = str(v)
    return clean


def _build_chroma_where(
    where: dict[str, Any],
) -> dict[str, Any] | None:
    """Build a ChromaDB ``where`` filter.

    If multiple fields are present, wraps them in an
    ``$and`` clause.

    Args:
        where: Simple key-value filter dict.

    Returns:
        ChromaDB-compatible where dict, or None if empty.
    """
    conditions = []
    for k, v in where.items():
        if v is not None:
            conditions.append({k: {"$eq": v}})
    if not conditions:
        return None
    if len(conditions) == 1:
        return conditions[0]
    return {"$and": conditions}
