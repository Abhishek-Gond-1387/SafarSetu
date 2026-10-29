"""Stops API endpoints for searching and querying nearby real transit stops."""
from typing import Optional
from fastapi import APIRouter, HTTPException, Query, status

from app.schemas.routing import NearbyStopOut, NearbyStopsResponse, StopOut, StopsResponse
from app.services.data_source_service import get_transit_context

router = APIRouter()


@router.get("/", response_model=StopsResponse, summary="Search and Paginate Stops")
def list_stops(
    query: Optional[str] = Query(None, description="Search term for stop name or code"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
):
    """Search authentic ingested stops with pagination."""
    ctx = get_transit_context()
    stops, total = ctx.repository.search_stops(query=query, page=page, page_size=page_size)

    results = [
        StopOut(
            stop_id=s.stop_id,
            stop_name=s.stop_name,
            stop_lat=s.stop_lat,
            stop_lon=s.stop_lon,
            stop_code=s.stop_code,
            stop_desc=s.stop_desc,
            zone_id=s.zone_id,
            location_type=int(s.location_type),
            parent_station=s.parent_station,
            source_id=s.source_id,
        )
        for s in stops
    ]

    return StopsResponse(
        total=total,
        page=page,
        page_size=page_size,
        results=results,
    )


@router.get("/nearby", response_model=NearbyStopsResponse, summary="Find Nearby Stops")
def get_nearby_stops(
    lat: float = Query(..., ge=-90.0, le=90.0, description="Latitude (WGS-84)"),
    lon: float = Query(..., ge=-180.0, le=180.0, description="Longitude (WGS-84)"),
    radius_meters: float = Query(1000.0, ge=50.0, le=10000.0, description="Search radius in metres"),
    limit: int = Query(30, ge=1, le=100, description="Maximum number of stops to return"),
):
    """Find authentic stops within radius of coordinates.
    
    NOTE: Distance returned is straight-line Haversine distance, NOT verified
    pedestrian-routed network distance.
    """
    ctx = get_transit_context()
    nearby = ctx.repository.find_nearby_stops(lat=lat, lon=lon, radius_meters=radius_meters, limit=limit)

    results = [
        NearbyStopOut(
            stop_id=s.stop_id,
            stop_name=s.stop_name,
            stop_lat=s.stop_lat,
            stop_lon=s.stop_lon,
            stop_code=s.stop_code,
            stop_desc=s.stop_desc,
            zone_id=s.zone_id,
            location_type=int(s.location_type),
            parent_station=s.parent_station,
            source_id=s.source_id,
            distance_meters=dist,
            distance_type="straight_line",
        )
        for s, dist in nearby
    ]

    return NearbyStopsResponse(
        query_lat=lat,
        query_lon=lon,
        radius_meters=radius_meters,
        results=results,
    )


@router.get("/{stop_id}", response_model=StopOut, summary="Get Stop Details")
def get_stop_by_id(stop_id: str):
    """Retrieve details for a specific stop ID."""
    ctx = get_transit_context()
    stop = ctx.repository.get_stop(stop_id)
    if not stop:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Stop ID '{stop_id}' not found in loaded transit dataset.",
        )
    return StopOut(
        stop_id=stop.stop_id,
        stop_name=stop.stop_name,
        stop_lat=stop.stop_lat,
        stop_lon=stop.stop_lon,
        stop_code=stop.stop_code,
        stop_desc=stop.stop_desc,
        zone_id=stop.zone_id,
        location_type=int(stop.location_type),
        parent_station=stop.parent_station,
        source_id=stop.source_id,
    )

