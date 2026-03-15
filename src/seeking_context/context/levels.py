r"""L0/L1/L2 context level handling.

Provides utilities for selecting the appropriate detail
level when returning memory content to callers.

Attributes:
    resolve_content_at_level: Pick the right text field
        from a MemoryItem for the requested level.
    summarise_items_at_level: Batch-resolve content at a
        given level for multiple items.
"""

from __future__ import annotations

from seeking_context.models.memory import (
    ContextLevel,
    MemoryItem,
)


def resolve_content_at_level(
    item: MemoryItem,
    level: ContextLevel = ContextLevel.DETAIL,
) -> str:
    """Return content for the requested detail level.

    Falls back through levels when the requested level
    field is empty:  L0 -> L1 -> L2.

    Args:
        item: The source memory item.
        level: Desired context level.

    Returns:
        The best-available text at the given level.
    """
    return item.get_content_at_level(level)


def summarise_items_at_level(
    items: list[MemoryItem],
    level: ContextLevel = ContextLevel.ABSTRACT,
    separator: str = "\n---\n",
) -> str:
    """Concatenate multiple items at a given level.

    Useful for producing a combined L0 digest of an
    entire scope or category.

    Args:
        items: List of memory items.
        level: Detail level to resolve.
        separator: String placed between each item's
            resolved content.

    Returns:
        Combined text of all items at the given level.
    """
    parts: list[str] = []
    for item in items:
        text = resolve_content_at_level(item, level)
        if text:
            parts.append(text)
    return separator.join(parts)
