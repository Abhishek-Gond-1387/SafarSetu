"""In-memory repository for caching real-time vehicle positions and feed status."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import threading
from typing import Dict, List, Optional, Tuple

from app.core.config import settings
from app.models.realtime import (
    ErrorCategory,
    FeedFreshness,
    RealtimeFeedStatus,
    VehiclePositionRecord,
)


class RealtimeVehicleRepository:
    """Thread-safe, bounded in-memory cache for live vehicle observations."""

    def __init__(self, max_cache_size: int = 10000, stale_threshold_seconds: int = 300):
        self.max_cache_size = max_cache_size
        self.stale_threshold_seconds = stale_threshold_seconds
        self._vehicles: Dict[str, VehiclePositionRecord] = {}
        self._lock = threading.Lock()
        self._status = RealtimeFeedStatus(
            enabled=settings.OTD_REALTIME_ENABLED,
            api_key_configured=bool(settings.OTD_REALTIME_API_KEY),
            last_poll_status="unpolled",
            feed_freshness=FeedFreshness.UNAVAILABLE,
        )

    def update_config_status(self):
        with self._lock:
            self._status.enabled = settings.OTD_REALTIME_ENABLED
            self._status.api_key_configured = bool(settings.OTD_REALTIME_API_KEY)

    def upsert_vehicles(
        self,
        records: List[VehiclePositionRecord],
        fetch_time: datetime,
        feed_timestamp: Optional[datetime],
        rejected_count: int,
    ):
        """Update cache with new valid vehicle records from a successful poll."""
        with self._lock:
            for rec in records:
                # If vehicle already in cache, only overwrite if new observation timestamp >= old
                if rec.vehicle_id in self._vehicles:
                    old_rec = self._vehicles[rec.vehicle_id]
                    old_ts = old_rec.timestamp or old_rec.server_fetch_time
                    new_ts = rec.timestamp or rec.server_fetch_time
                    if new_ts >= old_ts:
                        self._vehicles[rec.vehicle_id] = rec
                else:
                    self._vehicles[rec.vehicle_id] = rec

            # Evict if exceeding max cache size (evict oldest fetch times)
            if len(self._vehicles) > self.max_cache_size:
                sorted_by_time = sorted(
                    self._vehicles.items(),
                    key=lambda item: item[1].server_fetch_time,
                )
                excess = len(self._vehicles) - self.max_cache_size
                for vid, _ in sorted_by_time[:excess]:
                    del self._vehicles[vid]

            # Update status
            self._status.enabled = settings.OTD_REALTIME_ENABLED
            self._status.api_key_configured = bool(settings.OTD_REALTIME_API_KEY)
            self._status.last_poll_status = "success"
            self._status.last_successful_fetch = fetch_time
            self._status.last_feed_timestamp = feed_timestamp
            self._status.cached_vehicles_count = len(self._vehicles)
            self._status.rejected_entities_count = rejected_count
            self._status.feed_freshness = FeedFreshness.FRESH
            self._status.error_category = None
            self._status.error_message_sanitized = None

    def record_error(self, category: ErrorCategory, sanitized_message: str):
        """Record a polling failure without discarding existing valid cached records."""
        with self._lock:
            self._status.enabled = settings.OTD_REALTIME_ENABLED
            self._status.api_key_configured = bool(settings.OTD_REALTIME_API_KEY)
            self._status.last_poll_status = category.value
            self._status.error_category = category
            self._status.error_message_sanitized = sanitized_message

            # Evaluate freshness based on last successful fetch
            now = datetime.now(timezone.utc)
            if self._status.last_successful_fetch is None:
                self._status.feed_freshness = FeedFreshness.UNAVAILABLE
            else:
                elapsed = (now - self._status.last_successful_fetch).total_seconds()
                if elapsed > self.stale_threshold_seconds:
                    self._status.feed_freshness = FeedFreshness.STALE
                else:
                    self._status.feed_freshness = FeedFreshness.FRESH

    def get_status(self) -> RealtimeFeedStatus:
        with self._lock:
            # Recompute freshness on read
            now = datetime.now(timezone.utc)
            if self._status.last_successful_fetch is None:
                freshness = FeedFreshness.UNAVAILABLE
            else:
                elapsed = (now - self._status.last_successful_fetch).total_seconds()
                freshness = FeedFreshness.STALE if elapsed > self.stale_threshold_seconds else FeedFreshness.FRESH
            self._status.feed_freshness = freshness
            self._status.cached_vehicles_count = len(self._vehicles)
            return RealtimeFeedStatus(
                enabled=self._status.enabled,
                api_key_configured=self._status.api_key_configured,
                last_poll_status=self._status.last_poll_status,
                last_successful_fetch=self._status.last_successful_fetch,
                last_feed_timestamp=self._status.last_feed_timestamp,
                cached_vehicles_count=self._status.cached_vehicles_count,
                rejected_entities_count=self._status.rejected_entities_count,
                feed_freshness=freshness,
                error_category=self._status.error_category,
                error_message_sanitized=self._status.error_message_sanitized,
            )

    def get_vehicles(
        self,
        route_id: Optional[str] = None,
        trip_id: Optional[str] = None,
        is_matched: Optional[bool] = None,
        min_lat: Optional[float] = None,
        max_lat: Optional[float] = None,
        min_lon: Optional[float] = None,
        max_lon: Optional[float] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Tuple[List[VehiclePositionRecord], int, int]:
        """Query cached vehicles with optional filters.
        
        Returns:
            Tuple of (paged_records, total_matching, total_cached).
        """
        now = datetime.now(timezone.utc)
        with self._lock:
            all_records = list(self._vehicles.values())
            total_cached = len(all_records)

        # Apply staleness check dynamically on read
        for rec in all_records:
            ref_ts = rec.timestamp or rec.server_fetch_time
            age = (now - ref_ts).total_seconds()
            rec.is_stale = (age > self.stale_threshold_seconds)

        filtered = all_records

        if route_id is not None:
            r_target = route_id.strip().lower()
            filtered = [
                v for v in filtered
                if (v.route_id and v.route_id.lower() == r_target)
                or (v.route_short_name and v.route_short_name.lower() == r_target)
            ]

        if trip_id is not None:
            t_target = trip_id.strip().lower()
            filtered = [v for v in filtered if v.trip_id and v.trip_id.lower() == t_target]

        if is_matched is not None:
            filtered = [v for v in filtered if v.is_trip_matched == is_matched]

        # Bounding box filter
        if min_lat is not None:
            filtered = [v for v in filtered if v.latitude >= min_lat]
        if max_lat is not None:
            filtered = [v for v in filtered if v.latitude <= max_lat]
        if min_lon is not None:
            filtered = [v for v in filtered if v.longitude >= min_lon]
        if max_lon is not None:
            filtered = [v for v in filtered if v.longitude <= max_lon]

        total_matching = len(filtered)
        paged = filtered[offset : offset + limit]
        return paged, total_matching, total_cached

    def clear(self):
        """Clear cache and reset status (used in tests)."""
        with self._lock:
            self._vehicles.clear()
            self._status = RealtimeFeedStatus(
                enabled=settings.OTD_REALTIME_ENABLED,
                api_key_configured=bool(settings.OTD_REALTIME_API_KEY),
                last_poll_status="unpolled",
                feed_freshness=FeedFreshness.UNAVAILABLE,
            )

