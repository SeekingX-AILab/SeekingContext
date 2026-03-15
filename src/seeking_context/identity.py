r"""Namespace identity resolver for cross-framework isolation.

When multiple agent frameworks (less-agent, openclaw, Claude Code)
share one SeekingContext instance, each framework passes its own
``agent_id="main"``.  Without namespacing these collide.

This module provides ``resolve_scope()`` which prefixes identity
fields with a namespace string, and ``strip_namespace()`` for
display.

Design:
    - ``namespace="less-agent"`` + ``agent_id="main"``
      → stored as ``"less-agent:main"``
    - ``session_id`` is never prefixed (already unique UUIDs)
    - ``None`` namespace → default scope (``"default:default"``)
    - Already-prefixed values are detected to prevent
      double-prefixing

Inspired by less-agent's ``.context/`` per-session isolation
pattern, extended to cross-framework scenarios.
"""

from __future__ import annotations

from seeking_context.models.scope import Scope

# Delimiter used between namespace and identity value.
NS_SEP = ":"

# Default namespace applied when callers omit it.
DEFAULT_NS = "default"

# Default identity used when callers omit user/agent.
DEFAULT_ID = "default"


def resolve_scope(
    namespace: str | None = None,
    user_id: str | None = None,
    agent_id: str | None = None,
    session_id: str | None = None,
) -> Scope:
    r"""Resolve raw identity fields into a namespaced Scope.

    Prefixes ``user_id`` and ``agent_id`` with the given
    namespace to prevent collisions across frameworks.
    ``session_id`` is left untouched (UUIDs are unique).

    Args:
        namespace: Framework identifier (e.g. ``"less-agent"``).
            ``None`` uses ``"default"``.
        user_id: Raw user identifier.  ``None`` → ``"default"``.
        agent_id: Raw agent identifier.  ``None`` → ``"default"``.
        session_id: Session UUID.  Never prefixed.

    Returns:
        Scope: A Scope with namespaced user_id and agent_id.

    Examples:
        >>> resolve_scope("less-agent", "alice", "main")
        Scope(user_id='less-agent:alice',
              agent_id='less-agent:main',
              session_id=None)

        >>> resolve_scope()
        Scope(user_id='default:default',
              agent_id='default:default',
              session_id=None)
    """
    ns = namespace or DEFAULT_NS
    uid = user_id or DEFAULT_ID
    aid = agent_id or DEFAULT_ID

    return Scope(
        user_id=_prefix(ns, uid),
        agent_id=_prefix(ns, aid),
        session_id=session_id,
    )


def _prefix(namespace: str, value: str) -> str:
    r"""Add namespace prefix if not already present.

    Detects ``"ns:value"`` patterns to avoid double-prefixing.

    Args:
        namespace: The namespace string.
        value: The raw identity value.

    Returns:
        Prefixed string like ``"namespace:value"``.
    """
    if value.startswith(f"{namespace}{NS_SEP}"):
        return value
    return f"{namespace}{NS_SEP}{value}"


def strip_namespace(prefixed: str) -> tuple[str, str]:
    r"""Split a namespaced value into (namespace, raw_value).

    Args:
        prefixed: A string like ``"less-agent:main"``.

    Returns:
        Tuple of (namespace, raw_value).  If no separator
        is found, returns (``"default"``, original string).
    """
    if NS_SEP in prefixed:
        ns, _, raw = prefixed.partition(NS_SEP)
        return ns, raw
    return DEFAULT_NS, prefixed


def build_cross_scopes(
    namespaces: list[str],
    user_id: str | None = None,
    agent_id: str | None = None,
) -> list[Scope]:
    r"""Build Scope objects for cross-namespace search.

    Creates one Scope per namespace so the caller can query
    each and merge results.

    Args:
        namespaces: List of namespace strings to search.
        user_id: Raw user_id applied within each namespace.
        agent_id: Raw agent_id applied within each namespace.

    Returns:
        List of Scope objects, one per namespace.
    """
    scopes: list[Scope] = []
    for ns in namespaces:
        scopes.append(
            resolve_scope(
                namespace=ns,
                user_id=user_id,
                agent_id=agent_id,
            )
        )
    return scopes
