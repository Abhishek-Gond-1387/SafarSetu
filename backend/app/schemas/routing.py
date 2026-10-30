"""Pydantic schemas for routing API request/response validation."""
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, model_validator
from app.schemas.realtime import RealtimeStatusResponse


# ─── Stop schemas ────────────────────────────────────────────────────────────

class StopOut(BaseModel):
    stop_id: str
    stop_name: str
    stop_lat: float
    stop_lon: float
    stop_code: Optional[str] = None
    stop_desc: Optional[str] = None
    zone_id: Optional[str] = None
    location_type: int = 0
    parent_station: Optional[str] = None
    source_id: str = ""


class NearbyStopOut(StopOut):
    distance_meters: float = Field(..., description="Straight-line distance from query point (NOT pedestrian route distance)")
    distance_type: str = "straight_line"


class StopsResponse(BaseModel):
    total: int
    page: int
    page_size: int
    results: List[StopOut]


class NearbyStopsResponse(BaseModel):
    query_lat: float
    query_lon: float
    radius_meters: float
    distance_note: str = "Distances are straight-line (Haversine). Pedestrian route distances are not yet computed."
    results: List[NearbyStopOut]


# ─── Route planning schemas ───────────────────────────────────────────────────

class RoutePlanRequest(BaseModel):
    origin_stop_id: str = Field(..., description="GTFS stop_id of the origin stop")
    destination_stop_id: str = Field(..., description="GTFS stop_id of the destination stop")
    departure_date: date = Field(..., description="Date of travel (YYYY-MM-DD)")
    departure_time: str = Field(..., pattern=r"^\d{2}:\d{2}(:\d{2})?$",
                                description="Departure time HH:MM or HH:MM:SS")
    criterion: str = Field("fastest", pattern=r"^(fastest|cheapest|balanced)$",
                            description="Routing objective")
    max_transfers: int = Field(3, ge=0, le=10)
    max_walk_meters: float = Field(800, ge=0, le=5000,
                                   description="Max walking distance per connection (metres)")
    mode_preference: Optional[str] = Field("all", description="'all', 'metro', 'bus', 'multimodal'")

    @model_validator(mode="after")
    def parse_departure_time(self) -> "RoutePlanRequest":
        t = self.departure_time
        parts = t.split(":")
        if len(parts) == 2:
            self.departure_time = t + ":00"
        return self


class LegStopDetail(BaseModel):
    stop_id: str
    stop_name: str
    lat: float
    lon: float
    is_board: bool = False
    is_alight: bool = False
    mode: str = "transit"


class JourneyLegOut(BaseModel):
    mode: str
    from_stop_id: str
    to_stop_id: str
    from_stop_name: str
    to_stop_name: str
    from_stop_lat: Optional[float] = None
    from_stop_lon: Optional[float] = None
    to_stop_lat: Optional[float] = None
    to_stop_lon: Optional[float] = None
    departure_time: str
    arrival_time: str
    duration_minutes: float
    route_id: Optional[str] = None
    route_short_name: Optional[str] = None
    route_long_name: Optional[str] = None
    trip_id: Optional[str] = None
    headsign: Optional[str] = None
    distance_meters: Optional[float] = None
    distance_type: Optional[str] = None
    fare_inr: Optional[float] = None
    fare_note: Optional[str] = None
    source_id: str = ""
    path_coordinates: List[List[float]] = Field(default_factory=list)
    stops_detail: List[LegStopDetail] = Field(default_factory=list)


class JourneyOut(BaseModel):
    departure_time: str
    arrival_time: str
    total_duration_minutes: float
    total_walk_meters: float
    num_transfers: int
    initial_wait_minutes: float = 0.0
    fare_inr: Optional[float] = None
    fare_complete: bool
    fare_note: Optional[str] = None
    rank_criterion: str
    legs: List[JourneyLegOut]
    warnings: List[str] = Field(default_factory=list)
    data_sources: List[str] = Field(default_factory=list)


class RoutePlanResponse(BaseModel):
    origin_stop_id: str
    destination_stop_id: str
    departure_date: str
    requested_time: str
    criterion: str
    journeys: List[JourneyOut]
    data_freshness_warnings: List[str] = Field(default_factory=list)
    calendar_validity_note: Optional[str] = None
    no_route_reason: Optional[str] = None


# ─── Route comparison schemas ─────────────────────────────────────────────────

class RouteCompareRequest(BaseModel):
    journeys: List[JourneyOut] = Field(..., min_length=2, max_length=10,
                                       description="Journey candidates from /routes/plan")


class RouteCompareMetrics(BaseModel):
    duration_minutes: float
    walk_meters: float
    num_transfers: int
    fare_inr: Optional[float]
    fare_complete: bool
    rank_fastest: int
    rank_cheapest: Optional[int]    # None if fare unknown
    rank_balanced: int
    recommendation: Optional[str] = None


class RouteCompareResponse(BaseModel):
    journeys: List[JourneyOut]
    metrics: List[RouteCompareMetrics]
    note: str = "Comparisons use server-computed journey data only; client-supplied totals are not trusted."


# ─── Mode & Combination Explorer schemas ───────────────────────────────────────

class ModeOption(BaseModel):
    mode_id: str = Field(..., description="'metro', 'bus', 'multimodal', 'auto', 'cab'")
    title: str
    icon: str
    available: bool
    description: str
    estimated_duration_minutes: float
    estimated_distance_km: float
    fare_inr: float
    fare_breakdown: str
    optimization_tags: List[str]
    recommended_origin_stop: Optional[StopOut] = None
    recommended_destination_stop: Optional[StopOut] = None
    candidate_origin_stops: List[StopOut] = Field(default_factory=list)
    candidate_destination_stops: List[StopOut] = Field(default_factory=list)
    lines_or_routes: List[str] = Field(default_factory=list)


class ModeExploreRequest(BaseModel):
    destination_stop_id: str
    origin_stop_id: Optional[str] = None
    departure_date: Optional[date] = None
    departure_time: Optional[str] = "09:00:00"


class ModeExploreResponse(BaseModel):
    origin_stop: Optional[StopOut] = None
    destination_stop: StopOut
    straight_line_distance_km: float
    road_distance_km: float
    modes: List[ModeOption]


# ─── Health schema ────────────────────────────────────────────────────────────

class DataSourceStatus(BaseModel):
    source_id: str
    label: str
    status: str   # "loaded" | "expired" | "not_loaded" | "error"
    stops_count: int = 0
    routes_count: int = 0
    trips_count: int = 0
    feed_start_date: Optional[str] = None
    feed_end_date: Optional[str] = None
    downloaded_at: Optional[str] = None
    sha256: Optional[str] = None
    warnings: List[str] = Field(default_factory=list)


class HealthResponse(BaseModel):
    status: str
    project_name: str
    version: str
    environment: str
    data_sources: List[DataSourceStatus] = Field(default_factory=list)
    graph_nodes: int = 0
    graph_edges: int = 0
    realtime: Optional[RealtimeStatusResponse] = None


# ─── Lost Commuter Rerouting schemas ──────────────────────────────────────────

class NearestStationDetail(BaseModel):
    stop_id: str
    stop_name: str
    stop_lat: float
    stop_lon: float
    type: str = Field(..., description="'metro', 'bus', 'auto_stand'")
    distance_meters: float
    walk_minutes: float
    lines: List[str] = Field(default_factory=list)
    directions_text: str = ""


class LostAssistanceRequest(BaseModel):
    user_lat: float = Field(..., ge=-90.0, le=90.0)
    user_lon: float = Field(..., ge=-180.0, le=180.0)
    destination_stop_id: Optional[str] = None
    destination_name: Optional[str] = None
    preferred_mode: Optional[str] = Field("all", description="'all', 'metro', 'bus', 'auto'")


class LostAssistanceResponse(BaseModel):
    user_lat: float
    user_lon: float
    nearest_metro: Optional[NearestStationDetail] = None
    nearest_bus_stop: Optional[NearestStationDetail] = None
    nearest_station_overall: NearestStationDetail
    auto_rickshaw_fare_estimate_inr: float = 60.0
    auto_pickup_instructions: str = ""
    rerouted_plan: Optional[RoutePlanResponse] = None
    reassuring_message: str
    spoken_guidance: Dict[str, str] = Field(default_factory=dict)


