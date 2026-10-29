"""Pydantic schemas for GTFS-Realtime vehicle positions and feed status endpoints."""
from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, Field


class VehiclePositionOut(BaseModel):
    entity_id: str = Field(..., description="Protobuf feed entity identifier")
    vehicle_id: str = Field(..., description="Vehicle hardware or fleet identifier")
    latitude: float = Field(..., description="Observed WGS-84 latitude")
    longitude: float = Field(..., description="Observed WGS-84 longitude")
    bearing: Optional[float] = Field(None, description="Compass bearing in degrees (0-360)")
    speed_mps: Optional[float] = Field(None, description="Instantaneous speed in metres/second")
    speed_kmh: Optional[float] = Field(None, description="Instantaneous speed converted to km/h")
    timestamp: Optional[str] = Field(None, description="Observation timestamp reported by vehicle GPS (UTC ISO 8601)")
    server_fetch_time: str = Field(..., description="Timestamp when SafarSetu fetched the feed (UTC ISO 8601)")
    # Telemetry associations
    trip_id: Optional[str] = Field(None, description="Reported trip ID")
    route_id: Optional[str] = Field(None, description="Reported route ID")
    current_stop_sequence: Optional[int] = Field(None, description="Current GTFS stop sequence index")
    current_status: str = Field("UNKNOWN", description="Vehicle transit status: INCOMING_AT, STOPPED_AT, IN_TRANSIT_TO, UNKNOWN")
    # Verified static GTFS match
    is_trip_matched: bool = Field(False, description="True only if trip_id matches a validated static GTFS trip")
    is_route_matched: bool = Field(False, description="True only if route_id matches a validated static GTFS route")
    route_short_name: Optional[str] = Field(None, description="Verified static route public name/number (e.g., '764')")
    route_long_name: Optional[str] = Field(None, description="Verified static route description")
    next_stop_id: Optional[str] = Field(None, description="Identified scheduled next stop ID (not an estimated arrival)")
    next_stop_name: Optional[str] = Field(None, description="Identified scheduled next stop name")
    association_status: str = Field("unassociated", description="Status: 'verified_trip', 'verified_route_only', or 'unassociated'")
    is_stale: bool = Field(False, description="True if observation exceeds configured staleness threshold")


class RealtimeStatusResponse(BaseModel):
    enabled: bool = Field(..., description="Whether real-time polling is enabled in configuration")
    api_key_configured: bool = Field(..., description="Whether an OTD private API key is configured (boolean only)")
    last_poll_status: str = Field(..., description="Latest poll result: 'success', 'auth_error', 'timeout', etc.")
    last_successful_fetch: Optional[str] = Field(None, description="Timestamp of last successful HTTP response (UTC ISO 8601)")
    last_feed_timestamp: Optional[str] = Field(None, description="Header timestamp from latest valid GTFS-RT message (UTC ISO 8601)")
    cached_vehicles_count: int = Field(0, description="Number of valid live vehicles currently in memory cache")
    rejected_entities_count: int = Field(0, description="Entities rejected during latest poll due to invalid coordinates or format")
    feed_freshness: str = Field("unavailable", description="Freshness status: 'fresh', 'stale', or 'unavailable'")
    live_tracking_verified: bool = Field(False, description="True only if live vehicle feeds are active and successfully tracking")
    error_category: Optional[str] = Field(None, description="Sanitized classification of latest error, if any")
    error_message: Optional[str] = Field(None, description="Sanitized error description with no credentials exposed")


class VehicleListResponse(BaseModel):
    total: int = Field(..., description="Total live vehicles currently held in cache")
    filtered_count: int = Field(..., description="Number of vehicles matching requested query filters")
    feed_freshness: str = Field(..., description="Freshness of the cached vehicle data")
    last_successful_fetch: Optional[str] = Field(None, description="Timestamp of last successful feed fetch")
    results: List[VehiclePositionOut] = Field(default_factory=list, description="List of matching vehicle observations")
    disclaimer: str = Field(
        "Real-time records reflect live vehicle positions provided by Delhi OTD at the time of polling. "
        "Absence of a vehicle does not imply absence of scheduled service. No predicted ETAs are fabricated.",
        description="Data provenance and limitations statement",
    )

