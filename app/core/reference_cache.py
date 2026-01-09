"""
Module-level caches for reference data that rarely changes.

These caches reduce database load for frequently-accessed, rarely-changing data
like rarities, card types, etc.
"""

import threading
from typing import Optional

from cachetools import TTLCache

# Rarity table cache (1 hour TTL) - only 6 rows, never changes
_rarity_cache: TTLCache = TTLCache(maxsize=10, ttl=3600)
_rarity_cache_lock = threading.Lock()


def get_rarity_map(session) -> dict[int, str]:
    """
    Get cached mapping of rarity_id -> rarity_name.

    The Rarity table has only 6 rows and never changes, so we cache it
    for 1 hour to avoid repeated database queries.

    Args:
        session: SQLModel session (only used on cache miss)

    Returns:
        Dict mapping rarity_id to rarity_name
    """
    cache_key = "rarity_map"

    with _rarity_cache_lock:
        cached = _rarity_cache.get(cache_key)
        if cached is not None:
            return cached

    # Import here to avoid circular imports
    from sqlmodel import select

    from app.models.card import Rarity

    rarities = session.execute(select(Rarity)).scalars().all()
    rarity_map = {r.id: r.name for r in rarities}

    with _rarity_cache_lock:
        _rarity_cache[cache_key] = rarity_map

    return rarity_map


def get_rarity_name(session, rarity_id: Optional[int]) -> str:
    """
    Get rarity name by ID using the cached rarity map.

    Args:
        session: SQLModel session
        rarity_id: The rarity ID to look up

    Returns:
        Rarity name or "Unknown" if not found
    """
    if rarity_id is None:
        return "Unknown"

    rarity_map = get_rarity_map(session)
    return rarity_map.get(rarity_id, "Unknown")


def clear_rarity_cache():
    """Clear the rarity cache (useful for testing or after migrations)."""
    with _rarity_cache_lock:
        _rarity_cache.clear()
