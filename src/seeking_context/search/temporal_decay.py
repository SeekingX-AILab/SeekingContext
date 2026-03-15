r"""Temporal decay scoring for search results.

Ported from less-agent.  Applies exponential time-based
decay so fresher memories score higher, with an optional
boost for very recent items.

Decay formula::

    factor = 2 ** (-age_days / half_life_days)

Attributes:
    TemporalDecayConfig: Configuration dataclass.
    compute_decay_factor: Compute the multiplicative
        decay factor for a single timestamp.
    apply_temporal_decay_to_hybrid: Apply decay to a
        list of HybridResult objects in-place.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from seeking_context.search.hybrid import HybridResult


@dataclass
class TemporalDecayConfig:
    r"""Configuration for temporal decay scoring.

    Attributes:
        enabled (bool): Toggle decay on/off.
        half_life_days (float): Days for score to halve.
        min_decay (float): Floor so old items never hit 0.
        boost_recent_days (float): Items newer than this
            receive the boost multiplier.
        boost_factor (float): Multiplier for recent items.
    """

    enabled: bool = True
    half_life_days: float = 30.0
    min_decay: float = 0.1
    boost_recent_days: float = 7.0
    boost_factor: float = 1.2


def compute_decay_factor(
    timestamp: str,
    config: TemporalDecayConfig,
    now: datetime | None = None,
) -> float:
    r"""Compute decay factor for a single timestamp.

    Args:
        timestamp: ISO-format timestamp string.
        config: Decay configuration.
        now: Current time (defaults to utcnow).

    Returns:
        Multiplicative factor.  Values > 1 indicate a
        recency boost; values < 1 indicate decay.
    """
    if not config.enabled:
        return 1.0

    if now is None:
        now = datetime.now()

    try:
        ts = datetime.fromisoformat(timestamp)
        # Strip tzinfo for comparison if mixed
        if ts.tzinfo and not now.tzinfo:
            ts = ts.replace(tzinfo=None)
        elif now.tzinfo and not ts.tzinfo:
            now = now.replace(tzinfo=None)
    except (ValueError, TypeError):
        return 1.0

    age_days = (now - ts).total_seconds() / 86400

    if age_days < 0:
        return 1.0

    if age_days <= config.boost_recent_days:
        return config.boost_factor

    decay = math.pow(2, -age_days / config.half_life_days)
    return max(decay, config.min_decay)


def apply_temporal_decay_to_hybrid(
    results: list[HybridResult],
    config: TemporalDecayConfig,
    now: datetime | None = None,
) -> list[HybridResult]:
    r"""Apply temporal decay to HybridResult objects.

    Modifies ``combined_score`` in-place and re-sorts.

    Args:
        results: List of HybridResult from hybrid merge.
        config: Decay configuration.
        now: Current time.

    Returns:
        The same list, re-sorted by decayed scores.
    """
    if not config.enabled or not results:
        return results

    for r in results:
        if r.timestamp:
            factor = compute_decay_factor(
                r.timestamp, config, now
            )
            r.combined_score *= factor

    results.sort(
        key=lambda x: x.combined_score, reverse=True
    )
    return results


def get_age_bucket(
    timestamp: str, now: datetime | None = None
) -> str:
    """Return a human-readable age bucket.

    Args:
        timestamp: ISO timestamp string.
        now: Current time.

    Returns:
        One of ``today``, ``this_week``, ``this_month``,
        ``this_quarter``, ``this_year``, ``older``, or
        ``unknown``.
    """
    if now is None:
        now = datetime.now()
    try:
        ts = datetime.fromisoformat(timestamp)
        if ts.tzinfo and not now.tzinfo:
            ts = ts.replace(tzinfo=None)
    except (ValueError, TypeError):
        return "unknown"

    age = now - ts
    if age < timedelta(hours=24):
        return "today"
    if age < timedelta(days=7):
        return "this_week"
    if age < timedelta(days=30):
        return "this_month"
    if age < timedelta(days=90):
        return "this_quarter"
    if age < timedelta(days=365):
        return "this_year"
    return "older"
