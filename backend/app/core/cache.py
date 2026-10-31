"""High-Performance Multi-Tier Caching System.

Provides in-memory LRU with TTL + optional Redis integration to prevent
repeated expensive RAPTOR/Dijkstra multi-modal routing calculations.
"""
from __future__ import annotations

from collections import OrderedDict
from datetime import datetime
import json
import logging
import threading
import time
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger("safarsetu.cache")


class LRUTTLCache:
    """Thread-safe In-Memory Least-Recently-Used (LRU) Cache with Time-To-Live (TTL)."""

    def __init__(self, max_items: int = 1000, default_ttl_seconds: float = 300.0):
        self.max_items = max_items
        self.default_ttl_seconds = default_ttl_seconds
        self._cache: OrderedDict[str, Tuple[Any, float]] = OrderedDict()
        self._lock = threading.Lock()
        self._hits: int = 0
        self._misses: int = 0

    def get(self, key: str) -> Optional[Any]:
        """Retrieve item if present and unexpired; increments hit/miss counters."""
        with self._lock:
            if key not in self._cache:
                self._misses += 1
                return None

            val, expiry = self._cache[key]
            now = time.time()
            if now > expiry:
                # Expired
                del self._cache[key]
                self._misses += 1
                return None

            # Mark recently used
            self._cache.move_to_end(key)
            self._hits += 1
            return val

    def set(self, key: str, value: Any, ttl_seconds: Optional[float] = None) -> None:
        """Store item with expiration TTL."""
        ttl = ttl_seconds if ttl_seconds is not None else self.default_ttl_seconds
        expiry = time.time() + ttl
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
            self._cache[key] = (value, expiry)
            if len(self._cache) > self.max_items:
                self._cache.popitem(last=False)  # Evict oldest

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()

    def get_stats(self) -> Dict[str, Any]:
        """Observability metrics for cache performance."""
        with self._lock:
            total = self._hits + self._misses
            hit_ratio = round((self._hits / total) * 100, 2) if total > 0 else 0.0
            return {
                "size": len(self._cache),
                "max_items": self.max_items,
                "hits": self._hits,
                "misses": self._misses,
                "total_queries": total,
                "hit_ratio_percent": hit_ratio,
            }


# Route Planning Cache: 5-minute TTL (300 seconds)
route_plan_cache = LRUTTLCache(max_items=2000, default_ttl_seconds=300.0)

# Station/Stops Search Cache: 1-hour TTL (3600 seconds)
station_search_cache = LRUTTLCache(max_items=1000, default_ttl_seconds=3600.0)


def generate_route_plan_cache_key(
    origin_id: str,
    dest_id: str,
    departure_date: str,
    departure_time: str,
    criterion: str = "fastest",
    mode_preference: str = "all",
) -> str:
    """Generate normalized cache key grouped into 5-minute time windows."""
    # Group time into 5-minute intervals (e.g., 09:03 -> 09:00, 09:07 -> 09:05)
    time_parts = departure_time.split(":")
    if len(time_parts) >= 2:
        hour = time_parts[0]
        minute_bucket = (int(time_parts[1]) // 5) * 5
        bucketed_time = f"{hour}:{minute_bucket:02d}"
    else:
        bucketed_time = departure_time

    return f"route:{origin_id}:{dest_id}:{departure_date}:{bucketed_time}:{criterion}:{mode_preference}"

