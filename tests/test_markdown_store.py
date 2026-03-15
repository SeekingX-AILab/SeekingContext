"""Tests for the MarkdownStore backend."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio

from seeking_context.models.memory import (
    MemoryCategory,
    MemoryItem,
)
from seeking_context.storage.markdown_store import (
    MarkdownStore,
)


@pytest_asyncio.fixture()
async def md_store(tmp_path: Path) -> MarkdownStore:
    """Provide a MarkdownStore backed by a temp dir.

    Args:
        tmp_path: Pytest temporary directory.

    Returns:
        Initialised MarkdownStore.
    """
    return MarkdownStore(str(tmp_path / "memories"))


def _make_item(
    category: str = "entities",
    user_id: str = "default:default",
    content: str = "Test content.",
    abstract: str = "Test abstract.",
    overview: str = "Test overview.",
) -> MemoryItem:
    """Create a MemoryItem for testing.

    Args:
        category: Memory category string.
        user_id: Namespaced user id.
        content: Full text content.
        abstract: One-line summary.
        overview: Structured summary.

    Returns:
        A MemoryItem with the given fields.
    """
    return MemoryItem(
        content=content,
        abstract=abstract,
        overview=overview,
        category=MemoryCategory(category),
        user_id=user_id,
        agent_id="default:default",
        metadata={"source": "test"},
    )


@pytest.mark.asyncio
class TestMarkdownStoreRoundtrip:
    """Test 1: Write + read roundtrip."""

    async def test_roundtrip(
        self, md_store: MarkdownStore
    ) -> None:
        """YAML frontmatter + sections survive roundtrip."""
        item = _make_item()
        dump = item.model_dump(mode="json")
        await md_store.save(item.id, dump)

        got = await md_store.get(item.id)
        assert got is not None
        assert got["id"] == item.id
        assert got["content"] == "Test content."
        assert got["abstract"] == "Test abstract."
        assert got["overview"] == "Test overview."
        assert got["category"] == "entities"


@pytest.mark.asyncio
class TestProfileAppendOnly:
    """Test 2: Profile append-only behavior."""

    async def test_two_writes_one_profile_file(
        self, md_store: MarkdownStore
    ) -> None:
        """Two profile writes append to one profile.md."""
        item1 = _make_item(
            category="profile",
            content="System: macOS",
        )
        item2 = _make_item(
            category="profile",
            content="Prefers English",
        )

        dump1 = item1.model_dump(mode="json")
        dump2 = item2.model_dump(mode="json")
        await md_store.save(item1.id, dump1)
        await md_store.save(item2.id, dump2)

        profile_path = (
            md_store.base_dir / "default" / "profile.md"
        )
        assert profile_path.is_file()
        text = profile_path.read_text()
        assert "System: macOS" in text
        assert "Prefers English" in text


@pytest.mark.asyncio
class TestNamespaceIsolation:
    """Test 3: Namespace directory isolation."""

    async def test_two_namespaces_two_dirs(
        self, md_store: MarkdownStore
    ) -> None:
        """Different namespaces create separate dirs."""
        item_a = _make_item(
            user_id="ns-a:alice",
            content="Content A",
        )
        item_b = _make_item(
            user_id="ns-b:bob",
            content="Content B",
        )

        await md_store.save(
            item_a.id,
            item_a.model_dump(mode="json"),
        )
        await md_store.save(
            item_b.id,
            item_b.model_dump(mode="json"),
        )

        assert (
            md_store.base_dir / "ns-a" / "entities"
        ).is_dir()
        assert (
            md_store.base_dir / "ns-b" / "entities"
        ).is_dir()


@pytest.mark.asyncio
class TestCategoryStructure:
    """Test 4: Category directory structure verified."""

    async def test_category_dirs(
        self, md_store: MarkdownStore
    ) -> None:
        """Each category gets its own subdirectory."""
        for cat in (
            "preferences",
            "entities",
            "events",
            "cases",
            "patterns",
        ):
            item = _make_item(category=cat)
            await md_store.save(
                item.id,
                item.model_dump(mode="json"),
            )

        ns_dir = md_store.base_dir / "default"
        for cat in (
            "preferences",
            "entities",
            "events",
            "cases",
            "patterns",
        ):
            assert (ns_dir / cat).is_dir()


@pytest.mark.asyncio
class TestDelete:
    """Test 5: Delete removes .md file."""

    async def test_delete_removes_file(
        self, md_store: MarkdownStore
    ) -> None:
        """Deleting a memory removes its .md file."""
        item = _make_item()
        dump = item.model_dump(mode="json")
        await md_store.save(item.id, dump)

        # Verify file exists.
        got = await md_store.get(item.id)
        assert got is not None

        # Delete.
        ok = await md_store.delete(item.id)
        assert ok is True

        # Verify gone.
        got = await md_store.get(item.id)
        assert got is None


@pytest.mark.asyncio
class TestListCategoryFilter:
    """Test 6: List with category filter."""

    async def test_list_by_category(
        self, md_store: MarkdownStore
    ) -> None:
        """Listing with category filter returns only matches."""
        ent = _make_item(
            category="entities", content="Entity"
        )
        pref = _make_item(
            category="preferences", content="Pref"
        )

        await md_store.save(
            ent.id, ent.model_dump(mode="json")
        )
        await md_store.save(
            pref.id, pref.model_dump(mode="json")
        )

        results = await md_store.list(
            where={"category": "entities"}
        )
        assert len(results) == 1
        assert results[0]["content"] == "Entity"


@pytest.mark.asyncio
class TestListScopeFilter:
    """Test 7: List with scope filter."""

    async def test_list_by_user_id(
        self, md_store: MarkdownStore
    ) -> None:
        """Listing with user_id filter returns matches."""
        item_a = _make_item(
            user_id="ns:alice", content="Alice mem"
        )
        item_b = _make_item(
            user_id="ns:bob", content="Bob mem"
        )

        await md_store.save(
            item_a.id,
            item_a.model_dump(mode="json"),
        )
        await md_store.save(
            item_b.id,
            item_b.model_dump(mode="json"),
        )

        results = await md_store.list(
            where={"user_id": "ns:alice"}
        )
        assert len(results) == 1
        assert results[0]["content"] == "Alice mem"


@pytest.mark.asyncio
class TestRebuildIndexes:
    """Test 8: Rebuild indexes from markdown files."""

    async def test_rebuild(
        self, md_store: MarkdownStore
    ) -> None:
        """rebuild_indexes populates mock stores."""
        item = _make_item()
        dump = item.model_dump(mode="json")
        await md_store.save(item.id, dump)

        mock_vector = AsyncMock()
        mock_meta = AsyncMock()

        count = await md_store.rebuild_indexes(
            mock_vector, mock_meta
        )

        assert count == 1
        mock_vector.insert.assert_called_once()
        mock_meta.save.assert_called_once()


@pytest.mark.asyncio
class TestAbstractMdGeneration:
    """Test 9: .abstract.md auto-generation after write."""

    async def test_abstract_md_created(
        self, md_store: MarkdownStore
    ) -> None:
        """.abstract.md exists in namespace dir after write."""
        item = _make_item()
        dump = item.model_dump(mode="json")
        await md_store.save(item.id, dump)

        ns = md_store._extract_ns(dump)
        await md_store.update_dir_summaries(
            ns, "entities"
        )

        ns_dir = md_store.base_dir / ns
        abstract_path = ns_dir / ".abstract.md"
        assert abstract_path.is_file()

        text = abstract_path.read_text()
        assert "1 memories" in text


@pytest.mark.asyncio
class TestOverviewMdGeneration:
    """Test 10: .overview.md auto-generation after write."""

    async def test_overview_md_created(
        self, md_store: MarkdownStore
    ) -> None:
        """.overview.md exists with table after write."""
        item = _make_item()
        dump = item.model_dump(mode="json")
        await md_store.save(item.id, dump)

        ns = md_store._extract_ns(dump)
        await md_store.update_dir_summaries(
            ns, "entities"
        )

        ns_dir = md_store.base_dir / ns
        overview_path = ns_dir / ".overview.md"
        assert overview_path.is_file()

        text = overview_path.read_text()
        assert "| entities |" in text
        assert "| Category |" in text
