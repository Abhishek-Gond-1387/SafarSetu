"""Routes planning and comparison API endpoints."""
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, HTTPException, status

from app.models.journey import RouteRankCriterion
from app.models.transit import StopTime
from app.schemas.routing import (
    JourneyLegOut,
    JourneyOut,
    ModeExploreRequest,
    ModeExploreResponse,
    ModeOption,
    RouteCompareRequest,
    RouteCompareResponse,
    RoutePlanRequest,
    RoutePlanResponse,
    StopOut,
)
from app.services.data_source_service import get_transit_context
from app.services.route_ranker import RouteRanker
from app.utils.geo import haversine_meters

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
        mode_filter=request.mode_preference or "all",
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
                route_short_name=leg.route_short_name,
                route_long_name=leg.route_long_name,
                trip_id=leg.trip_id,
                headsign=leg.headsign,
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


def _stop_to_out(s) -> StopOut:
    return StopOut(
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


@router.post("/modes", response_model=ModeExploreResponse, summary="Explore Transportation Modes & Combinations")
def explore_modes(request: ModeExploreRequest):
    """Explore all available transport modes & combinations (Metro, Bus, Multimodal, Auto, Cab)
    for a destination, including distance and fare optimization estimates and recommended stops.
    """
    ctx = get_transit_context()
    if not ctx.dataset:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Transit dataset is not loaded.",
        )

    dest_stop = ctx.dataset.stops.get(request.destination_stop_id)
    if not dest_stop:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Destination stop '{request.destination_stop_id}' does not exist.",
        )

    origin_stop = None
    if request.origin_stop_id:
        origin_stop = ctx.dataset.stops.get(request.origin_stop_id)

    # If no origin specified, default to a major transit hub (Kashmere Gate metro_99 or Rajiv Chowk metro_122)
    if not origin_stop:
        default_id = "metro_122" if request.destination_stop_id != "metro_122" else "metro_99"
        origin_stop = ctx.dataset.stops.get(default_id) or list(ctx.dataset.stops.values())[0]

    # Calculate distance metrics
    dist_m = haversine_meters(origin_stop.stop_lat, origin_stop.stop_lon, dest_stop.stop_lat, dest_stop.stop_lon)
    d_km = max(0.5, round(dist_m / 1000.0, 1))
    d_road = round(d_km * 1.28, 1)

    # Find nearby stops for both endpoints
    origin_nearby = ctx.repository.find_nearby_stops(origin_stop.stop_lat, origin_stop.stop_lon, radius_meters=3500.0, limit=25)
    dest_nearby = ctx.repository.find_nearby_stops(dest_stop.stop_lat, dest_stop.stop_lon, radius_meters=3500.0, limit=25)

    # Partition into Metro and Bus stops
    orig_stops = [pair[0] for pair in origin_nearby]
    dest_stops = [pair[0] for pair in dest_nearby]

    orig_metro = [s for s in orig_stops if s.stop_id.startswith("metro_")]
    if origin_stop.stop_id.startswith("metro_") and origin_stop not in orig_metro:
        orig_metro.insert(0, origin_stop)

    dest_metro = [s for s in dest_stops if s.stop_id.startswith("metro_")]
    if dest_stop.stop_id.startswith("metro_") and dest_stop not in dest_metro:
        dest_metro.insert(0, dest_stop)

    orig_bus = [s for s in orig_stops if not s.stop_id.startswith("metro_")]
    if not origin_stop.stop_id.startswith("metro_") and origin_stop not in orig_bus:
        orig_bus.insert(0, origin_stop)

    dest_bus = [s for s in dest_stops if not s.stop_id.startswith("metro_")]
    if not dest_stop.stop_id.startswith("metro_") and dest_stop not in dest_bus:
        dest_bus.insert(0, dest_stop)

    # 1. Metro fare calculation
    if d_km <= 2.0:
        metro_fare = 10.0
    elif d_km <= 5.0:
        metro_fare = 20.0
    elif d_km <= 12.0:
        metro_fare = 30.0
    elif d_km <= 21.0:
        metro_fare = 40.0
    elif d_km <= 32.0:
        metro_fare = 50.0
    else:
        metro_fare = 60.0

    # 2. Bus fare calculation
    if d_road <= 4.0:
        bus_fare = 5.0
        bus_fare_ac = 10.0
    elif d_road <= 10.0:
        bus_fare = 10.0
        bus_fare_ac = 15.0 if d_road <= 8.0 else 20.0
    else:
        bus_fare = 15.0
        bus_fare_ac = 25.0

    # 3. Auto Rickshaw fare (GNCTD Meter)
    auto_fare = round(30.0 + max(0.0, d_road - 1.5) * 11.0, 0)

    # 4. Cab fare (App-based economy)
    cab_fare = round(50.0 + d_road * 14.0, 0)

    modes: List[ModeOption] = []

    # ── 1. Metro Only ──────────────────────────────────────────────────────────
    rec_orig_metro = orig_metro[0] if orig_metro else origin_stop
    rec_dest_metro = dest_metro[0] if dest_metro else dest_stop
    metro_duration = round(max(8.0, d_km * 1.8 + 6.0), 1)

    modes.append(
        ModeOption(
            mode_id="metro",
            title="DMRC Metro Only",
            icon="train",
            available=True,
            description="Dedicated air-conditioned rail corridors avoiding all street congestion.",
            estimated_duration_minutes=metro_duration,
            estimated_distance_km=round(d_km * 1.12, 1),
            fare_inr=metro_fare,
            fare_breakdown=f"DMRC Distance Slab: ₹{int(metro_fare)} (Smart Card: ₹{int(metro_fare * 0.9)}, Non-peak: ₹{int(metro_fare * 0.8)}).",
            optimization_tags=["⚡ Distance & Speed Optimized", "Fastest Rail Transit", "Air Conditioned"],
            recommended_origin_stop=_stop_to_out(rec_orig_metro),
            recommended_destination_stop=_stop_to_out(rec_dest_metro),
            candidate_origin_stops=[_stop_to_out(s) for s in orig_metro[:6]],
            candidate_destination_stops=[_stop_to_out(s) for s in dest_metro[:6]],
            lines_or_routes=["Yellow Line", "Blue Line", "Violet Line", "Pink Line", "Magenta Line", "Red Line"],
        )
    )

    # ── 2. DTC Bus Only ────────────────────────────────────────────────────────
    rec_orig_bus = orig_bus[0] if orig_bus else origin_stop
    rec_dest_bus = dest_bus[0] if dest_bus else dest_stop
    bus_duration = round(max(14.0, d_road * 2.7 + 7.0), 1)

    modes.append(
        ModeOption(
            mode_id="bus",
            title="DTC Bus Only",
            icon="bus",
            available=True,
            description="Extensive citywide surface network with direct street-level stops.",
            estimated_duration_minutes=bus_duration,
            estimated_distance_km=d_road,
            fare_inr=bus_fare,
            fare_breakdown=f"DTC Non-AC: ₹{int(bus_fare)} | AC: ₹{int(bus_fare_ac)} | Women: ₹0 (Delhi Govt Pink Pass).",
            optimization_tags=["💰 Fare Optimized", "Lowest Cost Option", "Direct Street Network"],
            recommended_origin_stop=_stop_to_out(rec_orig_bus),
            recommended_destination_stop=_stop_to_out(rec_dest_bus),
            candidate_origin_stops=[_stop_to_out(s) for s in orig_bus[:6]],
            candidate_destination_stops=[_stop_to_out(s) for s in dest_bus[:6]],
            lines_or_routes=["DTC City Bus Services"],
        )
    )

    # ── 3. Bus + Metro Multimodal ──────────────────────────────────────────────
    modes.append(
        ModeOption(
            mode_id="multimodal",
            title="Bus + Metro Multimodal",
            icon="multimodal",
            available=True,
            description="Combines fast metro transit trunk lines with feeder bus connections to minimize walking.",
            estimated_duration_minutes=round(max(16.0, d_km * 2.1 + 8.0), 1),
            estimated_distance_km=round(d_km * 1.18, 1),
            fare_inr=bus_fare + metro_fare,
            fare_breakdown=f"Combined Transit: ₹{int(bus_fare)} Bus + ₹{int(metro_fare)} Metro = ₹{int(bus_fare + metro_fare)} total.",
            optimization_tags=["⚖️ Balanced Optimization", "Least Walking", "High Connectivity"],
            recommended_origin_stop=_stop_to_out(rec_orig_bus),
            recommended_destination_stop=_stop_to_out(rec_dest_metro),
            candidate_origin_stops=[_stop_to_out(s) for s in (orig_bus[:4] + orig_metro[:3])],
            candidate_destination_stops=[_stop_to_out(s) for s in (dest_metro[:4] + dest_bus[:3])],
            lines_or_routes=["DMRC Metro Corridors + DTC Feeder"],
        )
    )

    # ── 4. Auto Rickshaw ───────────────────────────────────────────────────────
    modes.append(
        ModeOption(
            mode_id="auto",
            title="Auto Rickshaw (Delhi Meter)",
            icon="auto",
            available=True,
            description="Door-to-door intermediate road transport regulated by GNCTD meter fares.",
            estimated_duration_minutes=round(max(7.0, d_road * 2.2 + 2.0), 1),
            estimated_distance_km=d_road,
            fare_inr=auto_fare,
            fare_breakdown=f"GNCTD Meter Rate: ₹30 flagdown (1.5 km) + ₹11/km thereafter.",
            optimization_tags=["🚪 Door-to-Door", "No Transfers", "Immediate Departure"],
            recommended_origin_stop=_stop_to_out(origin_stop),
            recommended_destination_stop=_stop_to_out(dest_stop),
            lines_or_routes=["Roadway Auto-Rickshaw"],
        )
    )

    # ── 5. Cab / Taxi ──────────────────────────────────────────────────────────
    modes.append(
        ModeOption(
            mode_id="cab",
            title="Cab / Taxi (Ride-Hail)",
            icon="cab",
            available=True,
            description="Private air-conditioned door-to-door ride with luggage space.",
            estimated_duration_minutes=round(max(7.0, d_road * 2.0 + 3.0), 1),
            estimated_distance_km=d_road,
            fare_inr=cab_fare,
            fare_breakdown=f"Economy Ride-Hail Estimate: Base ₹50 + ₹14/km.",
            optimization_tags=["🛋️ Maximum Comfort", "Point-to-Point Direct", "Luggage Friendly"],
            recommended_origin_stop=_stop_to_out(origin_stop),
            recommended_destination_stop=_stop_to_out(dest_stop),
            lines_or_routes=["City Taxi / Cab"],
        )
    )

    return ModeExploreResponse(
        origin_stop=_stop_to_out(origin_stop),
        destination_stop=_stop_to_out(dest_stop),
        straight_line_distance_km=d_km,
        road_distance_km=d_road,
        modes=modes,
    )

