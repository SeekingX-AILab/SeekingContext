"""Tests for identity namespace resolver."""

from __future__ import annotations

import pytest

from seeking_context.identity import (
    DEFAULT_ID,
    DEFAULT_NS,
    NS_SEP,
    build_cross_scopes,
    resolve_scope,
    strip_namespace,
)


class TestResolveScope:
    """Tests for resolve_scope()."""

    def test_basic_namespacing(self) -> None:
        """Namespace prefixes user_id and agent_id."""
        scope = resolve_scope(
            "less-agent", "alice", "main",
        )
        assert scope.user_id == "less-agent:alice"
        assert scope.agent_id == "less-agent:main"
        assert scope.session_id is None

    def test_default_namespace(self) -> None:
        """None namespace falls back to 'default'."""
        scope = resolve_scope()
        assert scope.user_id == "default:default"
        assert scope.agent_id == "default:default"

    def test_session_never_prefixed(self) -> None:
        """session_id should not be prefixed."""
        sid = "abc-123-uuid"
        scope = resolve_scope(
            "myns", session_id=sid,
        )
        assert scope.session_id == sid

    def test_no_double_prefix(self) -> None:
        """Already-prefixed values are not doubled."""
        scope = resolve_scope(
            "less-agent",
            user_id="less-agent:alice",
            agent_id="less-agent:main",
        )
        assert scope.user_id == "less-agent:alice"
        assert scope.agent_id == "less-agent:main"

    def test_different_namespaces_differ(self) -> None:
        """Two namespaces produce different scopes."""
        s1 = resolve_scope("ns-a", "alice", "main")
        s2 = resolve_scope("ns-b", "alice", "main")
        assert s1.user_id != s2.user_id
        assert s1.agent_id != s2.agent_id

    def test_partial_user_only(self) -> None:
        """Only user_id provided; agent defaults."""
        scope = resolve_scope("x", user_id="bob")
        assert scope.user_id == "x:bob"
        assert scope.agent_id == "x:default"

    def test_partial_agent_only(self) -> None:
        """Only agent_id provided; user defaults."""
        scope = resolve_scope("x", agent_id="worker")
        assert scope.user_id == "x:default"
        assert scope.agent_id == "x:worker"


class TestStripNamespace:
    """Tests for strip_namespace()."""

    def test_basic_strip(self) -> None:
        """Strip returns (namespace, raw_value)."""
        ns, raw = strip_namespace("less-agent:main")
        assert ns == "less-agent"
        assert raw == "main"

    def test_no_separator(self) -> None:
        """Value without separator returns default ns."""
        ns, raw = strip_namespace("plain-value")
        assert ns == DEFAULT_NS
        assert raw == "plain-value"

    def test_multiple_colons(self) -> None:
        """Only first colon is used as separator."""
        ns, raw = strip_namespace("ns:a:b:c")
        assert ns == "ns"
        assert raw == "a:b:c"


class TestBuildCrossScopes:
    """Tests for build_cross_scopes()."""

    def test_builds_one_per_namespace(self) -> None:
        """One Scope per namespace string."""
        scopes = build_cross_scopes(
            ["ns-a", "ns-b", "ns-c"],
        )
        assert len(scopes) == 3
        assert scopes[0].user_id == "ns-a:default"
        assert scopes[1].user_id == "ns-b:default"
        assert scopes[2].user_id == "ns-c:default"

    def test_passes_user_and_agent(self) -> None:
        """user_id and agent_id are applied per ns."""
        scopes = build_cross_scopes(
            ["x", "y"],
            user_id="alice",
            agent_id="bot",
        )
        assert scopes[0].user_id == "x:alice"
        assert scopes[0].agent_id == "x:bot"
        assert scopes[1].user_id == "y:alice"
        assert scopes[1].agent_id == "y:bot"
