"""Routes planning and comparison API endpoints."""
from datetime import datetime
from fastapi import APIRouter, HTTPException, status

from app.models.journey import RouteRankCriterion
from app.models.transit import StopTime
from app.schemas.routing import (
    JourneyLegOut,
    JourneyOut,
    RouteCompareRequest,
    RouteCompareResponse,
    RoutePlanRequest,
    RoutePlanResponse,
)
from app.services.data_source_service import get_transit_context
from app.services.route_ranker import RouteRanker

router = APIRouter()


@router.post("/plan", response_model=RoutePlanResponse, summary="Plan Transit Journey")
def plan_route(request: RoutePlanRequest):
    """Plan feasible journeys between genuine transit stops using the timetable-aware engine."""
    ctx = get_transit_context()
    if not ctx.router:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Transit routing engine is not initialized or dataset is missing.",
        )

    # Parse requested departure time to seconds since midnight
    dep_seconds = StopTime.parse_time(request.departure_time)
    if dep_seconds is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid departure time format: '{request.departure_time}'. Expected HH:MM or HH:MM:SS.",
        )

    if request.origin_stop_id == request.destination_stop_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Origin and destination stops are identical.",
        )

    if ctx.dataset and request.origin_stop_id not in ctx.dataset.stops:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Origin stop '{request.origin_stop_id}' does not exist in dataset.",
        )

    if ctx.dataset and request.destination_stop_id not in ctx.dataset.stops:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Destination stop '{request.destination_stop_id}' does not exist in dataset.",
        )

    criterion = RouteRankCriterion(request.criterion)
    raw_journeys, no_route_reason = ctx.router.plan_journey(
        origin_stop_id=request.origin_stop_id,
        destination_stop_id=request.destination_stop_id,
        departure_date=request.departure_date,
        departure_seconds=dep_seconds,
        max_transfers=request.max_transfers,
        criterion=criterion,
    )

    ranked_journeys = RouteRanker.rank(raw_journeys, criterion=criterion)

    journeys_out = []
    for rj in ranked_journeys:
        legs_out = [
            JourneyLegOut(
                mode=leg.mode.value,
                from_stop_id=leg.from_stop_id,
                to_stop_id=leg.to_stop_id,
                from_stop_name=leg.from_stop_name,
                to_stop_name=leg.to_stop_name,
                departure_time=leg.departure_time_str,
                arrival_time=leg.arrival_time_str,
                duration_minutes=round(leg.duration_seconds / 60.0, 1),
                route_id=leg.route_id,
                trip_id=leg.trip_id,
                distance_meters=leg.distance_meters,
                distance_type=leg.walk_distance_type,
                fare_inr=leg.fare_inr,
                source_id=leg.source_id,
            )
            for leg in rj.legs
        ]

        journeys_out.append(
            JourneyOut(
                departure_time=rj.departure_time_str,
                arrival_time=rj.arrival_time_str,
                total_duration_minutes=round(rj.total_duration_seconds / 60.0, 1),
                total_walk_meters=round(rj.total_walk_meters, 1),
                num_transfers=rj.num_transfers,
                initial_wait_minutes=round(rj.initial_wait_seconds / 60.0, 1),
                fare_inr=rj.total_fare_inr,
                fare_complete=rj.fare_complete,
                fare_note=None if rj.fare_complete else "Genuine dataset lacks fare information for these routes",
                rank_criterion=rj.rank_criterion.value,
                legs=legs_out,
                warnings=rj.warnings,
                data_sources=rj.provenance_sources,
            )
        )

    # Collect freshness warnings and calendar validity note
    freshness_warnings = []
    cal_note = None
    if ctx.dataset and ctx.dataset.feed_info and ctx.dataset.feed_info.feed_end_date:
        if ctx.dataset.feed_info.feed_end_date < request.departure_date:
            freshness_warnings.append(
                f"Dataset {ctx.dataset.source_id} calendar expired on "
                f"{ctx.dataset.feed_info.feed_end_date.isoformat()}. "
                f"Requested journey date is {request.departure_date.isoformat()}. "
                "Results reflect historical schedule timetables."
            )
            cal_note = (
                f"Historical timetable: static GTFS calendar expired on "
                f"{ctx.dataset.feed_info.feed_end_date.isoformat()}. "
                "Evaluated using day-of-week service pattern."
            )
        else:
            cal_note = f"Service calendar valid through {ctx.dataset.feed_info.feed_end_date.isoformat()}."

    return RoutePlanResponse(
        origin_stop_id=request.origin_stop_id,
        destination_stop_id=request.destination_stop_id,
        departure_date=request.departure_date.isoformat(),
        requested_time=request.departure_time,
        criterion=request.criterion,
        journeys=journeys_out,
        data_freshness_warnings=freshness_warnings,
        calendar_validity_note=cal_note,
        no_route_reason=no_route_reason,
    )


@router.post("/compare", response_model=RouteCompareResponse, summary="Compare Route Options")
def compare_routes(request: RouteCompareRequest):
    """Compare multiple route candidates on duration, fare, walking distance, transfers, and data quality.
    
    Server recalculates metrics from the leg sequences; client totals are never trusted blindly.
    """
    return RouteRanker.compare(request.journeys)

