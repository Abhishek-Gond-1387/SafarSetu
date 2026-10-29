"""Real-time GTFS-RT vehicle position endpoints."""
from typing import Optional
from fastapi import APIRouter, Query

from app.schemas.realtime import (
    RealtimeStatusResponse,
    VehicleListResponse,
    VehiclePositionOut,
)
from app.services.data_source_service import get_transit_context
from app.services.metro_realtime_service import DMRCRealtimeService, MetroNetworkStatusResponse

router = APIRouter()


@router.get("/metro", response_model=MetroNetworkStatusResponse, summary="Delhi Metro (DMRC) Real-Time Line Operations")
def get_dmrc_metro_realtime_status():
    """Retrieve operational telemetry, current headway, frequency, and live line alerts for all Delhi Metro (DMRC) lines."""
    return DMRCRealtimeService.get_network_status()


@router.get("/status", response_model=RealtimeStatusResponse, summary="Real-Time Feed Polling Status")
def get_realtime_status():
    """Retrieve operational health, poll results, freshness, and vehicle count of the OTD live feed.
    
    Security Guarantee: Never exposes private credentials or API keys.
    """
    ctx = get_transit_context()
    status_obj = ctx.realtime_repo.get_status()

    is_live_verified = (status_obj.last_poll_status == "success" and status_obj.feed_freshness.value == "fresh")

    return RealtimeStatusResponse(
        enabled=status_obj.enabled,
        api_key_configured=status_obj.api_key_configured,
        last_poll_status=status_obj.last_poll_status,
        last_successful_fetch=status_obj.last_successful_fetch.isoformat() if status_obj.last_successful_fetch else None,
        last_feed_timestamp=status_obj.last_feed_timestamp.isoformat() if status_obj.last_feed_timestamp else None,
        cached_vehicles_count=status_obj.cached_vehicles_count,
        rejected_entities_count=status_obj.rejected_entities_count,
        feed_freshness=status_obj.feed_freshness.value,
        live_tracking_verified=is_live_verified,
        error_category=status_obj.error_category.value if status_obj.error_category else None,
        error_message=status_obj.error_message_sanitized,
    )


@router.get("/vehicles", response_model=VehicleListResponse, summary="Query Live Vehicles")
def list_realtime_vehicles(
    route_id: Optional[str] = Query(None, description="Filter by GTFS route ID or short name (e.g., '764')"),
    trip_id: Optional[str] = Query(None, description="Filter by GTFS trip ID"),
    is_matched: Optional[bool] = Query(None, description="Filter by whether trip is verified against static GTFS"),
    min_lat: Optional[float] = Query(None, ge=-90.0, le=90.0, description="Minimum latitude bounding box"),
    max_lat: Optional[float] = Query(None, ge=-90.0, le=90.0, description="Maximum latitude bounding box"),
    min_lon: Optional[float] = Query(None, ge=-180.0, le=180.0, description="Minimum longitude bounding box"),
    max_lon: Optional[float] = Query(None, ge=-180.0, le=180.0, description="Maximum longitude bounding box"),
    limit: int = Query(50, ge=1, le=500, description="Max vehicles to return"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
):
    """Retrieve normalized live vehicle observations.
    
    Vehicles matching static GTFS schedules have their verified route short names
    and scheduled next stops populated. Unassociated vehicles are preserved and labeled truthfully.
    """
    ctx = get_transit_context()
    paged, filtered_count, total_cached = ctx.realtime_repo.get_vehicles(
        route_id=route_id,
        trip_id=trip_id,
        is_matched=is_matched,
        min_lat=min_lat,
        max_lat=max_lat,
        min_lon=min_lon,
        max_lon=max_lon,
        limit=limit,
        offset=offset,
    )

    status_obj = ctx.realtime_repo.get_status()

    results = []
    for v in paged:
        association_label = "unassociated"
        if v.is_trip_matched:
            association_label = "verified_trip"
        elif v.is_route_matched:
            association_label = "verified_route_only"

        results.append(
            VehiclePositionOut(
                entity_id=v.entity_id,
                vehicle_id=v.vehicle_id,
                latitude=v.latitude,
                longitude=v.longitude,
                bearing=v.bearing,
                speed_mps=v.speed_mps,
                speed_kmh=v.speed_kmh,
                timestamp=v.timestamp.isoformat() if v.timestamp else None,
                server_fetch_time=v.server_fetch_time.isoformat(),
                trip_id=v.trip_id,
                route_id=v.route_id,
                current_stop_sequence=v.current_stop_sequence,
                current_status=v.current_status.value,
                is_trip_matched=v.is_trip_matched,
                is_route_matched=v.is_route_matched,
                route_short_name=v.route_short_name,
                route_long_name=v.route_long_name,
                next_stop_id=v.next_stop_id,
                next_stop_name=v.next_stop_name,
                association_status=association_label,
                is_stale=v.is_stale,
            )
        )

    return VehicleListResponse(
        total=total_cached,
        filtered_count=filtered_count,
        feed_freshness=status_obj.feed_freshness.value,
        last_successful_fetch=status_obj.last_successful_fetch.isoformat() if status_obj.last_successful_fetch else None,
        results=results,
    )

