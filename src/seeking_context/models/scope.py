r"""Scope filter for memory queries.

Provides a lightweight filter object that narrows memory
operations to a specific user, agent, and/or session.
Inspired by mem0's ``user_id / agent_id / run_id``
scoping pattern.

Attributes:
    Scope: Pydantic model holding optional user_id,
        agent_id and session_id fields used to filter
        storage and search operations.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class Scope(BaseModel):
    r"""Filter for narrowing memory operations.

    Any combination of the three fields can be set. Only
    non-None fields are used as filter criteria.

    Attributes:
        user_id (str | None): Filter by user.
        agent_id (str | None): Filter by agent.
        session_id (str | None): Filter by session.
    """

    user_id: str | None = None
    agent_id: str | None = None
    session_id: str | None = None

    def to_filter_dict(self) -> dict[str, str]:
        """Build a dict with only the non-None fields.

        Returns:
            Dictionary suitable for metadata filtering.
        """
        d: dict[str, str] = {}
        if self.user_id is not None:
            d["user_id"] = self.user_id
        if self.agent_id is not None:
            d["agent_id"] = self.agent_id
        if self.session_id is not None:
            d["session_id"] = self.session_id
        return d

    def matches(self, item_meta: dict[str, Any]) -> bool:
        """Check whether *item_meta* satisfies this scope.

        Args:
            item_meta: Metadata dict from a MemoryItem.

        Returns:
            True if every non-None scope field matches.
        """
        for k, v in self.to_filter_dict().items():
            if item_meta.get(k) != v:
                return False
        return True
