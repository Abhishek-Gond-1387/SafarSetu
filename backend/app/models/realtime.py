"""Real-time transit domain models for vehicle positions and feed status."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class VehicleStopStatus(str, Enum):
    INCOMING_AT = "INCOMING_AT"
    STOPPED_AT = "STOPPED_AT"
    IN_TRANSIT_TO = "IN_TRANSIT_TO"
    UNKNOWN = "UNKNOWN"


class FeedFreshness(str, Enum):
    FRESH = "fresh"
    STALE = "stale"
    UNAVAILABLE = "unavailable"


class ErrorCategory(str, Enum):
    AUTH_ERROR = "auth_error"
    TIMEOUT = "timeout"
    NETWORK_ERROR = "network_error"
    PARSE_ERROR = "parse_error"
    DISABLED = "disabled"
    UNKNOWN = "unknown"


@dataclass
class VehiclePositionRecord:
    """Normalized real-time observation of a transit vehicle."""
    entity_id: str
    vehicle_id: str
    latitude: float
    longitude: float
    server_fetch_time: datetime
    # Optional vehicle telemetry
    trip_id: Optional[str] = None
    route_id: Optional[str] = None
    bearing: Optional[float] = None
    speed_mps: Optional[float] = None
    timestamp: Optional[datetime] = None  # Telemetry observation timestamp from GPS
    current_stop_sequence: Optional[int] = None
    current_status: VehicleStopStatus = VehicleStopStatus.UNKNOWN
    # Static GTFS matching metadata (evaluated during ingestion)
    is_trip_matched: bool = False
    is_route_matched: bool = False
    route_short_name: Optional[str] = None
    route_long_name: Optional[str] = None
    # Next stop identification (only populated when matched to static trip sequence)
    next_stop_id: Optional[str] = None
    next_stop_name: Optional[str] = None
    # Data quality
    is_stale: bool = False

    @property
    def speed_kmh(self) -> Optional[float]:
        if self.speed_mps is None:
            return None
        return round(self.speed_mps * 3.6, 1)

    @property
    def association_status(self) -> str:
        if self.is_trip_matched:
            return "verified_trip"
        elif self.is_route_matched:
            return "verified_route_only"
        return "unassociated"


@dataclass
class RealtimeFeedStatus:
    """Status metadata for the real-time vehicle positions polling engine."""
    enabled: bool = False
    api_key_configured: bool = False
    last_poll_status: str = "unpolled"  # "success" | "auth_error" | "network_error" | "timeout" | "parse_error" | "unpolled"
    last_successful_fetch: Optional[datetime] = None
    last_feed_timestamp: Optional[datetime] = None
    cached_vehicles_count: int = 0
    rejected_entities_count: int = 0
    feed_freshness: FeedFreshness = FeedFreshness.UNAVAILABLE
    error_category: Optional[ErrorCategory] = None
    error_message_sanitized: Optional[str] = None
