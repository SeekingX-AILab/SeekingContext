r"""SQLite metadata + FTS5 store backend.

Uses ``aiosqlite`` for async access.  Stores the full
serialised ``MemoryItem`` JSON in a ``memories`` table
and maintains a parallel ``memories_fts`` FTS5 virtual
table for BM25 keyword search.

Storage location defaults to
``~/.seeking_context/metadata.db``.

Attributes:
    SQLiteStore: Async SQLite backend providing metadata
        CRUD and BM25 full-text search via FTS5.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import aiosqlite

logger = logging.getLogger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS memories (
    id   TEXT PRIMARY KEY,
    data TEXT NOT NULL
);

CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts
USING fts5(id, content, tokenize='porter');
"""


class SQLiteStore:
    r"""SQLite-backed metadata + FTS5 store.

    Attributes:
        db_path (str): Path to the SQLite database file.
    """

    def __init__(self, db_path: str) -> None:
        """Initialise the SQLite store.

        Args:
            db_path: Filesystem path for the database.
        """
        self._db_path = db_path
        self._initialised = False

    async def _ensure_db(self) -> aiosqlite.Connection:
        """Open a connection and ensure schema exists.

        Returns:
            An open ``aiosqlite.Connection``.
        """
        db = await aiosqlite.connect(self._db_path)
        if not self._initialised:
            await db.executescript(_SCHEMA)
            await db.commit()
            self._initialised = True
        return db

    # -- CRUD ---------------------------------------------------

    async def save(
        self,
        doc_id: str,
        data: dict[str, Any],
    ) -> None:
        """Persist or update a memory item.

        Args:
            doc_id: Unique document identifier.
            data: Serialised MemoryItem dict.
        """
        db = await self._ensure_db()
        try:
            blob = json.dumps(data, ensure_ascii=False)
            await db.execute(
                "INSERT OR REPLACE INTO memories "
                "(id, data) VALUES (?, ?)",
                (doc_id, blob),
            )
            # Sync FTS index
            content = data.get("content", "")
            abstract = data.get("abstract", "")
            overview = data.get("overview", "")
            fts_text = " ".join(
                filter(None, [content, abstract, overview])
            )
            await db.execute(
                "DELETE FROM memories_fts WHERE id = ?",
                (doc_id,),
            )
            await db.execute(
                "INSERT INTO memories_fts (id, content) "
                "VALUES (?, ?)",
                (doc_id, fts_text),
            )
            await db.commit()
        finally:
            await db.close()

    async def get(
        self, doc_id: str
    ) -> dict[str, Any] | None:
        """Retrieve a memory item by id.

        Args:
            doc_id: Document identifier.

        Returns:
            The stored dict or None.
        """
        db = await self._ensure_db()
        try:
            cursor = await db.execute(
                "SELECT data FROM memories WHERE id = ?",
                (doc_id,),
            )
            row = await cursor.fetchone()
            if row is None:
                return None
            return json.loads(row[0])
        finally:
            await db.close()

    async def delete(self, doc_id: str) -> None:
        """Delete a memory item.

        Args:
            doc_id: Document identifier.
        """
        db = await self._ensure_db()
        try:
            await db.execute(
                "DELETE FROM memories WHERE id = ?",
                (doc_id,),
            )
            await db.execute(
                "DELETE FROM memories_fts WHERE id = ?",
                (doc_id,),
            )
            await db.commit()
        finally:
            await db.close()

    async def list(
        self,
        where: dict[str, Any] | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """List memory items with optional filtering.

        Args:
            where: Key-value filters matched against the
                stored JSON data.
            limit: Maximum items.
            offset: Items to skip.

        Returns:
            List of stored dicts.
        """
        db = await self._ensure_db()
        try:
            cursor = await db.execute(
                "SELECT data FROM memories "
                "ORDER BY rowid DESC LIMIT ? OFFSET ?",
                (limit, offset),
            )
            rows = await cursor.fetchall()
            items = [json.loads(r[0]) for r in rows]
            if where:
                items = _filter_items(items, where)
            return items
        finally:
            await db.close()

    async def fts_search(
        self,
        query: str,
        top_k: int = 10,
        where: dict[str, Any] | None = None,
    ) -> list[tuple[str, float]]:
        """BM25 full-text search via FTS5.

        Args:
            query: Keyword query string.
            top_k: Maximum results.
            where: Optional metadata filter applied
                after the FTS query.

        Returns:
            List of ``(doc_id, bm25_score)`` tuples.
            Scores are negated so higher is better.
        """
        db = await self._ensure_db()
        try:
            safe_query = _sanitise_fts_query(query)
            if not safe_query:
                return []

            cursor = await db.execute(
                "SELECT id, rank "
                "FROM memories_fts "
                "WHERE memories_fts MATCH ? "
                "ORDER BY rank "
                "LIMIT ?",
                (safe_query, top_k * 3),
            )
            rows = await cursor.fetchall()

            results: list[tuple[str, float]] = []
            for doc_id, rank in rows:
                # FTS5 rank is negative; negate for score
                score = -rank if rank else 0.0
                results.append((doc_id, score))

            # Post-filter by metadata if needed
            if where and results:
                results = await self._filter_fts(
                    db, results, where
                )

            return results[:top_k]
        finally:
            await db.close()

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
        db = await self._ensure_db()
        try:
            if not where:
                cursor = await db.execute(
                    "SELECT COUNT(*) FROM memories"
                )
                row = await cursor.fetchone()
                return row[0] if row else 0

            cursor = await db.execute(
                "SELECT data FROM memories"
            )
            rows = await cursor.fetchall()
            items = [json.loads(r[0]) for r in rows]
            return len(_filter_items(items, where))
        finally:
            await db.close()

    # -- helpers -----------------------------------------------

    async def _filter_fts(
        self,
        db: aiosqlite.Connection,
        results: list[tuple[str, float]],
        where: dict[str, Any],
    ) -> list[tuple[str, float]]:
        """Filter FTS results by metadata.

        Args:
            db: Open database connection.
            results: FTS result pairs.
            where: Metadata filter dict.

        Returns:
            Filtered result pairs.
        """
        filtered: list[tuple[str, float]] = []
        for doc_id, score in results:
            cursor = await db.execute(
                "SELECT data FROM memories WHERE id = ?",
                (doc_id,),
            )
            row = await cursor.fetchone()
            if row:
                data = json.loads(row[0])
                if _matches_where(data, where):
                    filtered.append((doc_id, score))
        return filtered


def _filter_items(
    items: list[dict[str, Any]],
    where: dict[str, Any],
) -> list[dict[str, Any]]:
    """Filter a list of dicts by key-value matches.

    Args:
        items: List of item dicts.
        where: Filter criteria.

    Returns:
        Items that match all filter criteria.
    """
    return [i for i in items if _matches_where(i, where)]


def _matches_where(
    data: dict[str, Any], where: dict[str, Any]
) -> bool:
    """Check if *data* matches all *where* criteria.

    Args:
        data: Item dict.
        where: Filter criteria.

    Returns:
        True if every key-value pair in *where* matches.
    """
    for k, v in where.items():
        if data.get(k) != v:
            return False
    return True


def _sanitise_fts_query(query: str) -> str:
    """Sanitise a user query for FTS5 MATCH syntax.

    Removes special FTS5 operators to prevent syntax
    errors while preserving search intent.

    Args:
        query: Raw user query.

    Returns:
        Sanitised query safe for FTS5 MATCH.
    """
    # Remove FTS5 special chars
    cleaned = ""
    for ch in query:
        if ch.isalnum() or ch in " _-":
            cleaned += ch
        else:
            cleaned += " "
    # Collapse whitespace
    tokens = cleaned.split()
    if not tokens:
        return ""
    return " ".join(tokens)
