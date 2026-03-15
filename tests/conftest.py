"""Shared test fixtures for SeekingContext."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest
import pytest_asyncio

from seeking_context.config import SeekingContextConfig
from seeking_context.models.memory import (
    ContextLevel,
    MemoryCategory,
    MemoryItem,
)
from seeking_context.storage.memory_store import MemoryStore


@pytest.fixture()
def tmp_data_dir(tmp_path: Path) -> Path:
    """Provide a temporary data directory.

    Returns:
        Path to a fresh temp directory.
    """
    return tmp_path / "seeking_context_test"


@pytest.fixture()
def config(tmp_data_dir: Path) -> SeekingContextConfig:
    """Provide a test config pointing to temp storage.

    Args:
        tmp_data_dir: Temporary data directory.

    Returns:
        Config with data_dir set to tmp_data_dir.
    """
    return SeekingContextConfig(
        data_dir=str(tmp_data_dir),
    )


@pytest_asyncio.fixture()
async def store(
    config: SeekingContextConfig,
) -> MemoryStore:
    """Provide a MemoryStore backed by temp storage.

    Args:
        config: Test configuration.

    Returns:
        Initialised MemoryStore.
    """
    return MemoryStore(config=config)


@pytest.fixture()
def sample_item() -> MemoryItem:
    """Provide a sample MemoryItem for testing.

    Returns:
        A MemoryItem with all fields populated.
    """
    return MemoryItem(
        content="Python is a programming language.",
        abstract="Python: a programming language.",
        overview="Python is a high-level language "
        "used for web dev, data science, and more.",
        category=MemoryCategory.ENTITIES,
        user_id="test-user",
        agent_id="test-agent",
        metadata={"source": "test"},
    )


@pytest.fixture()
def sample_items() -> list[MemoryItem]:
    """Provide multiple sample items for search tests.

    Returns:
        List of five diverse MemoryItem objects.
    """
    items = [
        MemoryItem(
            content="Python is great for data science.",
            abstract="Python for data science.",
            category=MemoryCategory.ENTITIES,
            user_id="u1",
        ),
        MemoryItem(
            content="TypeScript adds static types to JS.",
            abstract="TypeScript: typed JavaScript.",
            category=MemoryCategory.ENTITIES,
            user_id="u1",
        ),
        MemoryItem(
            content="User prefers dark mode in all apps.",
            abstract="Prefers dark mode.",
            category=MemoryCategory.PREFERENCES,
            user_id="u1",
        ),
        MemoryItem(
            content="Fixed auth bug by refreshing tokens.",
            abstract="Auth token refresh fix.",
            category=MemoryCategory.CASES,
            user_id="u1",
            agent_id="a1",
        ),
        MemoryItem(
            content="Always run tests before deploying.",
            abstract="Test before deploy pattern.",
            category=MemoryCategory.PATTERNS,
            user_id="u1",
            agent_id="a1",
        ),
    ]
    return items
