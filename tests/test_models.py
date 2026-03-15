"""Tests for data models."""

from __future__ import annotations

import pytest

from seeking_context.models.memory import (
    ContextLevel,
    MemoryCategory,
    MemoryItem,
)
from seeking_context.models.scope import Scope
from seeking_context.models.search import (
    SearchQuery,
    SearchResult,
)


class TestMemoryItem:
    """Tests for the MemoryItem model."""

    def test_create_default(self) -> None:
        """Test creating a MemoryItem with defaults."""
        item = MemoryItem(content="hello")
        assert item.content == "hello"
        assert item.id  # UUID generated
        assert item.active_count == 0
        assert item.category == MemoryCategory.ENTITIES

    def test_touch_increments(self) -> None:
        """Test that touch() increments active_count."""
        item = MemoryItem(content="x")
        old_ts = item.updated_at
        item.touch()
        assert item.active_count == 1
        assert item.updated_at >= old_ts

    def test_content_at_level_abstract(self) -> None:
        """Test L0 returns abstract."""
        item = MemoryItem(
            content="full",
            abstract="short",
            overview="medium",
        )
        assert (
            item.get_content_at_level(
                ContextLevel.ABSTRACT
            )
            == "short"
        )

    def test_content_at_level_fallback(self) -> None:
        """Test L0 falls back to overview then content."""
        item = MemoryItem(content="full")
        assert (
            item.get_content_at_level(
                ContextLevel.ABSTRACT
            )
            == "full"
        )

    def test_content_at_level_overview(self) -> None:
        """Test L1 returns overview."""
        item = MemoryItem(
            content="full", overview="mid"
        )
        assert (
            item.get_content_at_level(
                ContextLevel.OVERVIEW
            )
            == "mid"
        )

    def test_content_at_level_detail(self) -> None:
        """Test L2 returns full content."""
        item = MemoryItem(
            content="full",
            abstract="short",
            overview="mid",
        )
        assert (
            item.get_content_at_level(
                ContextLevel.DETAIL
            )
            == "full"
        )

    def test_serialization_roundtrip(self) -> None:
        """Test model_dump / model_validate roundtrip."""
        item = MemoryItem(
            content="test",
            category=MemoryCategory.CASES,
            user_id="u1",
        )
        data = item.model_dump(mode="json")
        restored = MemoryItem.model_validate(data)
        assert restored.id == item.id
        assert restored.category == MemoryCategory.CASES


class TestScope:
    """Tests for the Scope model."""

    def test_empty_scope(self) -> None:
        """Test empty scope produces empty filter."""
        s = Scope()
        assert s.to_filter_dict() == {}

    def test_partial_scope(self) -> None:
        """Test scope with only user_id."""
        s = Scope(user_id="u1")
        assert s.to_filter_dict() == {"user_id": "u1"}

    def test_matches_true(self) -> None:
        """Test scope matching succeeds."""
        s = Scope(user_id="u1", agent_id="a1")
        meta = {"user_id": "u1", "agent_id": "a1"}
        assert s.matches(meta)

    def test_matches_false(self) -> None:
        """Test scope matching fails on mismatch."""
        s = Scope(user_id="u1")
        assert not s.matches({"user_id": "u2"})


class TestContextLevel:
    """Tests for the ContextLevel enum."""

    def test_values(self) -> None:
        """Test enum integer values."""
        assert ContextLevel.ABSTRACT == 0
        assert ContextLevel.OVERVIEW == 1
        assert ContextLevel.DETAIL == 2
