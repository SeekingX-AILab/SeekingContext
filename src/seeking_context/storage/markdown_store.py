r"""Markdown filesystem storage backend.

Each memory is a YAML-frontmatter ``.md`` file.  Directories
are organized by namespace -> category.  The ``profile``
category uses a single append-only ``profile.md``.

This is the **SOURCE OF TRUTH**.  ChromaDB + SQLite are
derived indexes that can be rebuilt from these files at
any time.

Directory layout::

    base_dir/
    ├── {namespace}/
    │   ├── .abstract.md
    │   ├── .overview.md
    │   ├── profile.md          # append-only
    │   ├── preferences/
    │   │   ├── .abstract.md
    │   │   └── mem_{uuid}.md
    │   ├── entities/
    │   │   └── ...
    │   └── ...
    └── default/
        └── ...

Attributes:
    MarkdownStore: Async markdown-file storage backend
        with YAML frontmatter parsing and directory
        summary generation.
"""

from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from seeking_context.identity import (
    DEFAULT_NS,
    NS_SEP,
    strip_namespace,
)

logger = logging.getLogger(__name__)

# Categories that map to subdirectories.
_CATEGORY_DIRS = frozenset(
    {
        "preferences",
        "entities",
        "events",
        "cases",
        "patterns",
    }
)

# Regex to split frontmatter from body.
_FM_RE = re.compile(
    r"^---\s*\n(.*?)\n---\s*\n(.*)$",
    re.DOTALL,
)

# Section header pattern for Abstract / Overview / Content.
_SECTION_RE = re.compile(
    r"^#\s+(Abstract|Overview|Content)\s*$",
    re.MULTILINE,
)


class MarkdownStore:
    r"""Markdown filesystem storage backend.

    Each memory is a YAML-frontmatter ``.md`` file.  Dirs
    organized by namespace -> category.  Profile category
    uses a single append-only ``profile.md``.

    This is the SOURCE OF TRUTH.  ChromaDB + SQLite are
    derived indexes rebuilt from these files.

    Attributes:
        base_dir (Path): Root directory for all markdown
            memory files.
    """

    def __init__(self, base_dir: str) -> None:
        """Initialise the markdown store.

        Args:
            base_dir: Root directory for markdown files.
                Created if it does not exist.
        """
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        # Per-namespace locks for file safety.
        self._locks: dict[str, asyncio.Lock] = {}

    # -- lock helpers -----------------------------------------

    def _lock_for(self, namespace: str) -> asyncio.Lock:
        """Return an asyncio.Lock for a namespace.

        Args:
            namespace: Namespace identifier.

        Returns:
            asyncio.Lock scoped to the namespace.
        """
        if namespace not in self._locks:
            self._locks[namespace] = asyncio.Lock()
        return self._locks[namespace]

    # -- namespace extraction ---------------------------------

    @staticmethod
    def _extract_ns(data: dict[str, Any]) -> str:
        """Extract namespace from a memory data dict.

        Derives namespace from the ``user_id`` field by
        splitting on the namespace separator.  Falls back
        to ``"default"`` when no namespace prefix exists.

        Args:
            data: Serialised MemoryItem dict.

        Returns:
            Namespace string (e.g. ``"claude-code"``).
        """
        uid = data.get("user_id") or ""
        if NS_SEP in uid:
            ns, _ = strip_namespace(uid)
            return ns
        return DEFAULT_NS

    # -- path helpers -----------------------------------------

    def _ns_dir(self, namespace: str) -> Path:
        """Return the namespace directory path.

        Args:
            namespace: Namespace identifier.

        Returns:
            Path to the namespace directory.
        """
        return self.base_dir / namespace

    def _memory_path(
        self,
        namespace: str,
        category: str,
        mem_id: str,
    ) -> Path:
        """Compute the file path for a memory.

        Profile memories go to ``profile.md`` (append-only).
        Other categories go to ``{cat}/mem_{id}.md``.

        Args:
            namespace: Namespace identifier.
            category: Memory category string.
            mem_id: Memory UUID.

        Returns:
            Path to the ``.md`` file.
        """
        ns_dir = self._ns_dir(namespace)
        if category == "profile":
            return ns_dir / "profile.md"
        cat_dir = ns_dir / category
        cat_dir.mkdir(parents=True, exist_ok=True)
        return cat_dir / f"mem_{mem_id}.md"

    # -- YAML + Markdown I/O ----------------------------------

    def _write_md(
        self, path: Path, data: dict[str, Any]
    ) -> None:
        """Write a memory as YAML frontmatter + markdown.

        Args:
            path: Destination file path.
            data: Serialised MemoryItem dict.
        """
        path.parent.mkdir(parents=True, exist_ok=True)

        # Build frontmatter dict (exclude body sections).
        fm = {
            k: v
            for k, v in data.items()
            if k not in ("abstract", "overview", "content")
        }

        body_parts: list[str] = []
        if data.get("abstract"):
            body_parts.append(
                f"# Abstract\n\n{data['abstract']}"
            )
        if data.get("overview"):
            body_parts.append(
                f"# Overview\n\n{data['overview']}"
            )
        if data.get("content"):
            body_parts.append(
                f"# Content\n\n{data['content']}"
            )

        body = "\n\n".join(body_parts) + "\n"

        frontmatter = yaml.safe_dump(
            fm,
            default_flow_style=False,
            allow_unicode=True,
            sort_keys=False,
            width=72,
        )

        text = f"---\n{frontmatter}---\n\n{body}"
        path.write_text(text, encoding="utf-8")

    def _read_md(self, path: Path) -> dict[str, Any] | None:
        """Read a memory from a YAML-frontmatter .md file.

        Args:
            path: File path to read.

        Returns:
            Parsed dict with all MemoryItem fields,
            or None if the file does not exist.
        """
        if not path.is_file():
            return None

        raw = path.read_text(encoding="utf-8")
        match = _FM_RE.match(raw)
        if not match:
            logger.warning(
                "No frontmatter in %s", path
            )
            return None

        fm_text, body = match.group(1), match.group(2)

        try:
            data: dict[str, Any] = (
                yaml.safe_load(fm_text) or {}
            )
        except yaml.YAMLError:
            logger.warning(
                "Invalid YAML in %s", path
            )
            return None

        # Parse sectioned body.
        sections = _split_sections(body)
        data["abstract"] = sections.get("abstract", "")
        data["overview"] = sections.get("overview", "")
        data["content"] = sections.get("content", "")

        return data

    def _append_profile(
        self, namespace: str, data: dict[str, Any]
    ) -> None:
        """Append to the profile.md file (append-only).

        Profile entries accumulate over time; they are
        never overwritten.

        Args:
            namespace: Namespace identifier.
            data: Serialised MemoryItem dict.
        """
        ns_dir = self._ns_dir(namespace)
        ns_dir.mkdir(parents=True, exist_ok=True)
        profile_path = ns_dir / "profile.md"

        now = datetime.now(
            timezone.utc
        ).strftime("%Y-%m-%d")

        entry_lines: list[str] = []
        entry_lines.append(f"\n## {now}")
        if data.get("content"):
            for line in data["content"].splitlines():
                entry_lines.append(f"- {line}")
        entry_text = "\n".join(entry_lines) + "\n"

        if not profile_path.is_file():
            header = "# User Profile\n"
            profile_path.write_text(
                header + entry_text, encoding="utf-8"
            )
        else:
            with profile_path.open(
                "a", encoding="utf-8"
            ) as f:
                f.write(entry_text)

    # -- Core CRUD (async) ------------------------------------

    async def save(
        self,
        doc_id: str,
        data: dict[str, Any],
    ) -> None:
        """Save a memory to a .md file.

        Profile-category memories are appended to
        ``profile.md``.  All others get their own
        ``mem_{id}.md`` file.

        Args:
            doc_id: Memory UUID.
            data: Serialised MemoryItem dict.
        """
        ns = self._extract_ns(data)
        category = data.get("category", "entities")

        async with self._lock_for(ns):
            if category == "profile":
                self._append_profile(ns, data)
                # Also write individual mem file so
                # get() and rebuild work correctly.
                path = self._ns_dir(ns) / category
                path.mkdir(parents=True, exist_ok=True)
                mem_path = path / f"mem_{doc_id}.md"
                self._write_md(mem_path, data)
            else:
                path = self._memory_path(
                    ns, category, doc_id
                )
                self._write_md(path, data)

    async def get(
        self, doc_id: str
    ) -> dict[str, Any] | None:
        """Retrieve a memory by scanning for its file.

        Args:
            doc_id: Memory UUID.

        Returns:
            Parsed MemoryItem dict, or None.
        """
        # Search all namespace/category dirs for the file.
        pattern = f"**/mem_{doc_id}.md"
        matches = list(self.base_dir.glob(pattern))
        if not matches:
            return None
        return self._read_md(matches[0])

    async def delete(self, doc_id: str) -> bool:
        """Delete a memory's .md file.

        Args:
            doc_id: Memory UUID.

        Returns:
            True if the file was found and deleted.
        """
        pattern = f"**/mem_{doc_id}.md"
        matches = list(self.base_dir.glob(pattern))
        if not matches:
            return False
        for m in matches:
            m.unlink(missing_ok=True)
        return True

    async def list(
        self,
        where: dict[str, Any] | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """List memories from markdown files.

        Walks all ``mem_*.md`` files and applies optional
        filters from the ``where`` dict.

        Args:
            where: Optional key-value filters applied to
                frontmatter fields.
            limit: Maximum items to return.
            offset: Number of items to skip.

        Returns:
            List of parsed MemoryItem dicts.
        """
        all_items = await self.walk_all()

        if where:
            all_items = [
                item
                for item in all_items
                if _matches_where(item, where)
            ]

        # Sort by updated_at descending.
        all_items.sort(
            key=lambda x: x.get("updated_at", ""),
            reverse=True,
        )

        return all_items[offset: offset + limit]

    async def count(
        self, where: dict[str, Any] | None = None
    ) -> int:
        """Count memories matching optional filters.

        Args:
            where: Optional key-value filters.

        Returns:
            Number of matching memories.
        """
        items = await self.list(
            where=where, limit=999999
        )
        return len(items)

    # -- Walk all files ---------------------------------------

    async def walk_all(self) -> list[dict[str, Any]]:
        """Walk all mem_*.md files and parse them.

        Returns:
            List of all parsed MemoryItem dicts.
        """
        results: list[dict[str, Any]] = []
        for md_file in self.base_dir.rglob("mem_*.md"):
            data = self._read_md(md_file)
            if data:
                results.append(data)
        return results

    # -- Directory summaries ----------------------------------

    async def update_dir_summaries(
        self, namespace: str, category: str
    ) -> None:
        """Regenerate .abstract.md and .overview.md.

        Updates both the namespace-level and category-level
        summary files after a write or delete.

        Args:
            namespace: Namespace identifier.
            category: Category that was modified.
        """
        await self._update_ns_summary(namespace)
        if category != "profile":
            await self._update_cat_summary(
                namespace, category
            )

    async def _update_ns_summary(
        self, namespace: str
    ) -> None:
        """Regenerate namespace-level summary files.

        Writes ``.abstract.md`` and ``.overview.md`` in
        the namespace directory.

        Args:
            namespace: Namespace identifier.
        """
        ns_dir = self._ns_dir(namespace)
        if not ns_dir.is_dir():
            return

        # Count per category.
        cat_counts: dict[str, int] = {}
        cat_latest: dict[str, str] = {}

        for cat in _CATEGORY_DIRS | {"profile"}:
            cat_dir = ns_dir / cat
            if not cat_dir.is_dir():
                continue
            mems = list(cat_dir.glob("mem_*.md"))
            cat_counts[cat] = len(mems)
            # Find latest by mtime.
            if mems:
                latest = max(mems, key=lambda p: p.stat().st_mtime)
                data = self._read_md(latest)
                if data:
                    abstract = data.get("abstract", "")
                    cat_latest[cat] = (
                        abstract[:60] + "..."
                        if len(abstract) > 60
                        else abstract
                    )

        total = sum(cat_counts.values())
        now = datetime.now(
            timezone.utc
        ).isoformat()

        # .abstract.md
        abstract_text = (
            f"# {namespace}\n\n"
            f"{total} memories across "
            f"{len(cat_counts)} categories.\n"
            f"Last updated: {now}\n"
        )
        (ns_dir / ".abstract.md").write_text(
            abstract_text, encoding="utf-8"
        )

        # .overview.md
        rows: list[str] = []
        rows.append(
            f"# {namespace} — Memory Overview\n"
        )
        rows.append(
            "| Category | Count | Latest |"
        )
        rows.append(
            "|----------|-------|--------|"
        )
        for cat in sorted(cat_counts.keys()):
            cnt = cat_counts[cat]
            latest_txt = cat_latest.get(cat, "—")
            rows.append(
                f"| {cat} | {cnt} | {latest_txt} |"
            )
        rows.append("")

        (ns_dir / ".overview.md").write_text(
            "\n".join(rows), encoding="utf-8"
        )

    async def _update_cat_summary(
        self, namespace: str, category: str
    ) -> None:
        """Regenerate category-level .abstract.md.

        Args:
            namespace: Namespace identifier.
            category: Category name.
        """
        cat_dir = self._ns_dir(namespace) / category
        if not cat_dir.is_dir():
            return

        mems = list(cat_dir.glob("mem_*.md"))
        count = len(mems)

        latest_text = ""
        if mems:
            latest = max(
                mems, key=lambda p: p.stat().st_mtime
            )
            data = self._read_md(latest)
            if data:
                abstract = data.get("abstract", "")
                latest_text = (
                    abstract[:80] + "..."
                    if len(abstract) > 80
                    else abstract
                )

        abstract_text = (
            f"# {category}\n\n"
            f"{count} {category} memories."
        )
        if latest_text:
            abstract_text += (
                f' Most recent: "{latest_text}"'
            )
        abstract_text += "\n"

        (cat_dir / ".abstract.md").write_text(
            abstract_text, encoding="utf-8"
        )

    # -- Rebuild / Migration ----------------------------------

    async def rebuild_indexes(
        self,
        vector_store: Any,
        meta_store: Any,
    ) -> int:
        """Rebuild vector + FTS indexes from .md files.

        Walks all markdown files, parses them, and
        re-inserts into the provided stores.  Proves
        that markdown is the canonical source of truth.

        Args:
            vector_store: VectorStore backend to populate.
            meta_store: MetadataStore backend to populate.

        Returns:
            Number of memories re-indexed.
        """
        items = await self.walk_all()
        count = 0

        for data in items:
            doc_id = data.get("id")
            if not doc_id:
                continue

            content = data.get("content", "")

            # Build vector metadata.
            vec_meta: dict[str, Any] = {}
            if data.get("user_id"):
                vec_meta["user_id"] = data["user_id"]
            if data.get("agent_id"):
                vec_meta["agent_id"] = data["agent_id"]
            if data.get("session_id"):
                vec_meta["session_id"] = data[
                    "session_id"
                ]
            if data.get("category"):
                vec_meta["category"] = data["category"]

            await vector_store.insert(
                doc_id=doc_id,
                text=content,
                metadata=vec_meta,
            )
            await meta_store.save(
                doc_id=doc_id,
                data=data,
            )
            count += 1

        logger.info(
            "Rebuilt indexes from %d markdown files",
            count,
        )
        return count

    async def export_from_db(
        self, meta_store: Any
    ) -> int:
        """Export all memories from MetadataStore to .md.

        One-time migration for existing users who have
        data in SQLite but no markdown files yet.

        Args:
            meta_store: MetadataStore to read from.

        Returns:
            Number of memories exported.
        """
        rows = await meta_store.list(
            where=None, limit=999999
        )
        count = 0

        for data in rows:
            doc_id = data.get("id")
            if not doc_id:
                continue
            await self.save(doc_id, data)
            count += 1

        logger.info(
            "Exported %d memories to markdown", count
        )
        return count


# -- module-level helpers --------------------------------------


def _split_sections(body: str) -> dict[str, str]:
    """Parse markdown body into named sections.

    Splits on ``# Abstract``, ``# Overview``, and
    ``# Content`` headers.

    Args:
        body: Markdown text after the frontmatter.

    Returns:
        Dict mapping lowercase section name to its
        text content (stripped).
    """
    sections: dict[str, str] = {}
    parts = _SECTION_RE.split(body)

    # parts alternates: [pre, name, text, name, text, ...]
    i = 1
    while i < len(parts) - 1:
        name = parts[i].lower()
        text = parts[i + 1].strip()
        sections[name] = text
        i += 2

    return sections


def _matches_where(
    item: dict[str, Any],
    where: dict[str, Any],
) -> bool:
    """Check if an item matches all filter conditions.

    Args:
        item: Parsed MemoryItem dict.
        where: Key-value filters to match.

    Returns:
        True if all where conditions match.
    """
    for key, val in where.items():
        item_val = item.get(key)
        if item_val != val:
            return False
    return True
