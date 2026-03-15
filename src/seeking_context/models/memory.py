r"""Core memory data models.

Defines the fundamental structures used throughout
SeekingContext: ``MemoryItem`` for stored memories,
``ContextLevel`` for L0/L1/L2 detail tiers, and
``MemoryCategory`` for the six memory categories
(profile, preferences, entities, events, cases,
patterns).

The three-tier context design (L0 abstract / L1 overview /
L2 detail) is inspired by less-agent's markdown-based
persistence model (``.abstract.md``, ``.overview.md``,
and full conversation files).

Attributes:
    ContextLevel: Integer enum mapping abstract (0),
        overview (1) and detail (2) levels.
    MemoryCategory: String enum for the six memory
        categories.
    MemoryItem: Pydantic model representing a single
        stored memory with multi-level summaries.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class ContextLevel(int, Enum):
    r"""Hierarchical detail level for memory retrieval.

    Inspired by less-agent's three-tier persistence model:
    ``.abstract.md`` (L0), ``.overview.md`` (L1), and
    full conversation markdown (L2).

    Attributes:
        ABSTRACT: L0 - one-line summary (~100 tokens).
        OVERVIEW: L1 - structured summary (~2K tokens).
        DETAIL: L2 - full content.
    """

    ABSTRACT = 0
    OVERVIEW = 1
    DETAIL = 2


class MemoryCategory(str, Enum):
    r"""Category of a stored memory.

    Six categories for organising agent knowledge,
    split into user-space and agent-space.

    Attributes:
        PROFILE: User profile information.
        PREFERENCES: User preferences and settings.
        ENTITIES: Named entities (projects, people).
        EVENTS: Event records (decisions, milestones).
        CASES: Specific problems and their solutions.
        PATTERNS: Reusable processes and methods.
    """

    PROFILE = "profile"
    PREFERENCES = "preferences"
    ENTITIES = "entities"
    EVENTS = "events"
    CASES = "cases"
    PATTERNS = "patterns"


class MemoryItem(BaseModel):
    r"""A single stored memory with multi-level summaries.

    Each memory carries three levels of detail (L0/L1/L2)
    so that retrieval can return just the right amount of
    context for the caller's needs.

    Attributes:
        id (str): Unique identifier (UUID).
        content (str): Full text content (L2 detail).
        abstract (str): One-line summary (~100 tokens, L0).
        overview (str): Structured summary (~2K tokens, L1).
        category (MemoryCategory): Memory category.
        user_id (str | None): Scoping - user identifier.
        agent_id (str | None): Scoping - agent identifier.
        session_id (str | None): Scoping - session id.
        metadata (dict[str, Any]): Arbitrary metadata.
        created_at (str): ISO timestamp of creation.
        updated_at (str): ISO timestamp of last update.
        active_count (int): Usage counter for hotness.
    """

    id: str = Field(default_factory=lambda: str(uuid4()))
    content: str = ""
    abstract: str = ""
    overview: str = ""
    category: MemoryCategory = MemoryCategory.ENTITIES
    user_id: str | None = None
    agent_id: str | None = None
    session_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(
        default_factory=lambda: datetime.now(
            timezone.utc
        ).isoformat()
    )
    updated_at: str = Field(
        default_factory=lambda: datetime.now(
            timezone.utc
        ).isoformat()
    )
    active_count: int = 0

    def touch(self) -> None:
        """Increment usage counter and update timestamp."""
        self.active_count += 1
        self.updated_at = datetime.now(
            timezone.utc
        ).isoformat()

    def get_content_at_level(
        self, level: ContextLevel = ContextLevel.DETAIL
    ) -> str:
        """Return content at the requested detail level.

        Args:
            level: Desired context level.

        Returns:
            The appropriate text for the given level.
            Falls back to the next available level if
            the requested level is empty.
        """
        if level == ContextLevel.ABSTRACT:
            return self.abstract or self.overview or self.content
        if level == ContextLevel.OVERVIEW:
            return self.overview or self.content
        return self.content
