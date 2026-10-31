"""Routes planning and comparison API endpoints."""
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Body, Depends, HTTPException, status
from app.core.cache import generate_route_plan_cache_key, route_plan_cache
from app.core.rate_limit import rate_limit_plan

from app.models.journey import LegMode, RouteRankCriterion
from app.models.transit import StopTime
from app.schemas.routing import (
    JourneyLegOut,
    JourneyOut,
    LostAssistanceRequest,
    LostAssistanceResponse,
    ModeExploreRequest,
    ModeExploreResponse,
    ModeOption,
    NearestStationDetail,
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


@router.post("/plan", response_model=RoutePlanResponse, dependencies=[Depends(rate_limit_plan)], summary="Plan Transit Journey")
def plan_route(req: RoutePlanRequest = Body(...)):
    """Plan feasible journeys between genuine transit stops using the timetable-aware engine."""
    ctx = get_transit_context()
    if not ctx.router:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Transit routing engine is not initialized or dataset is missing.",
        )

    # Parse requested departure time to seconds since midnight
    dep_seconds = StopTime.parse_time(req.departure_time)
    if dep_seconds is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid departure time format: '{req.departure_time}'. Expected HH:MM or HH:MM:SS.",
        )

    if req.origin_stop_id == req.destination_stop_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Origin and destination stops are identical.",
        )

    if ctx.dataset and req.origin_stop_id not in ctx.dataset.stops:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Origin stop '{req.origin_stop_id}' does not exist in dataset.",
        )

    if ctx.dataset and req.destination_stop_id not in ctx.dataset.stops:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Destination stop '{req.destination_stop_id}' does not exist in dataset.",
        )

    # Check Multi-Tier Cache for instant sub-millisecond retrieval
    cache_key = generate_route_plan_cache_key(
        origin_id=req.origin_stop_id,
        dest_id=req.destination_stop_id,
        departure_date=req.departure_date.isoformat(),
        departure_time=req.departure_time,
        criterion=req.criterion,
        mode_preference=req.mode_preference or "all",
    )
    cached_plan = route_plan_cache.get(cache_key)
    if cached_plan is not None:
        return cached_plan

    criterion = RouteRankCriterion(req.criterion)
    raw_journeys, no_route_reason = ctx.router.plan_journey(
        origin_stop_id=req.origin_stop_id,
        destination_stop_id=req.destination_stop_id,
        departure_date=req.departure_date,
        departure_seconds=dep_seconds,
        max_transfers=req.max_transfers,
        criterion=criterion,
        mode_filter=req.mode_preference or "all",
    )

    ranked_journeys = RouteRanker.rank(raw_journeys, criterion=criterion)

    journeys_out = []
    for rj in ranked_journeys:
        legs_out = []
        for leg in rj.legs:
            from_s = ctx.dataset.stops.get(leg.from_stop_id) if ctx.dataset else None
            to_s = ctx.dataset.stops.get(leg.to_stop_id) if ctx.dataset else None

            path_coords = []
            stops_detail = []

            if from_s:
                path_coords.append([from_s.stop_lat, from_s.stop_lon])
                stops_detail.append({
                    "stop_id": from_s.stop_id,
                    "stop_name": from_s.stop_name,
                    "lat": from_s.stop_lat,
                    "lon": from_s.stop_lon,
                    "is_board": True,
                    "is_alight": False,
                    "mode": leg.mode.value,
                })

            if ctx.dataset and leg.intermediate_stops:
                for sid in leg.intermediate_stops:
                    mid_s = ctx.dataset.stops.get(sid)
                    if mid_s:
                        path_coords.append([mid_s.stop_lat, mid_s.stop_lon])
                        stops_detail.append({
                            "stop_id": mid_s.stop_id,
                            "stop_name": mid_s.stop_name,
                            "lat": mid_s.stop_lat,
                            "lon": mid_s.stop_lon,
                            "is_board": False,
                            "is_alight": False,
                            "mode": leg.mode.value,
                        })

            if to_s:
                if not path_coords or path_coords[-1] != [to_s.stop_lat, to_s.stop_lon]:
                    path_coords.append([to_s.stop_lat, to_s.stop_lon])
                stops_detail.append({
                    "stop_id": to_s.stop_id,
                    "stop_name": to_s.stop_name,
                    "lat": to_s.stop_lat,
                    "lon": to_s.stop_lon,
                    "is_board": False,
                    "is_alight": True,
                    "mode": leg.mode.value,
                })

            # Check live vehicle tracking for this leg from OTD realtime feed
            live_vehicles_on_route = []
            if ctx.realtime_repo and leg.route_id:
                try:
                    records, _, _ = ctx.realtime_repo.get_vehicles(route_id=leg.route_id, limit=5)
                    live_vehicles_on_route = records
                except Exception:
                    live_vehicles_on_route = []

            legs_out.append(
                JourneyLegOut(
                    mode=leg.mode.value,
                    from_stop_id=leg.from_stop_id,
                    to_stop_id=leg.to_stop_id,
                    from_stop_name=leg.from_stop_name,
                    to_stop_name=leg.to_stop_name,
                    from_stop_lat=from_s.stop_lat if from_s else None,
                    from_stop_lon=from_s.stop_lon if from_s else None,
                    to_stop_lat=to_s.stop_lat if to_s else None,
                    to_stop_lon=to_s.stop_lon if to_s else None,
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
                    path_coordinates=path_coords,
                    stops_detail=stops_detail,
                    has_live_vehicle=len(live_vehicles_on_route) > 0,
                    live_vehicle_count=len(live_vehicles_on_route),
                )
            )

        transit_identifiers = [
            (leg.route_short_name or leg.route_id or "transit").replace(" ", "_")
            for leg in rj.legs if leg.mode != LegMode.WALK and (leg.route_short_name or leg.route_id)
        ]
        if transit_identifiers:
            canonical_id = "corridor_" + "_".join(transit_identifiers)
        else:
            canonical_id = f"corridor_walk_{rj.legs[0].from_stop_id if rj.legs else 'start'}_{rj.legs[-1].to_stop_id if rj.legs else 'end'}"

        journey_id_hash = f"journey_{canonical_id}_{rj.departure_time_str}_{rj.arrival_time_str}"
        any_live_tracking = any(l.has_live_vehicle for l in legs_out)

        journeys_out.append(
            JourneyOut(
                journey_id=journey_id_hash,
                canonical_route_id=canonical_id,
                has_live_tracking=any_live_tracking,
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
        if ctx.dataset.feed_info.feed_end_date < req.departure_date:
            freshness_warnings.append(
                f"Dataset {ctx.dataset.source_id} calendar expired on "
                f"{ctx.dataset.feed_info.feed_end_date.isoformat()}. "
                f"Requested journey date is {req.departure_date.isoformat()}. "
                "Results reflect historical schedule timetables."
            )
            cal_note = (
                f"Historical timetable: static GTFS calendar expired on "
                f"{ctx.dataset.feed_info.feed_end_date.isoformat()}. "
                "Evaluated using day-of-week service pattern."
            )
        else:
            cal_note = f"Service calendar valid through {ctx.dataset.feed_info.feed_end_date.isoformat()}."

    response = RoutePlanResponse(
        origin_stop_id=req.origin_stop_id,
        destination_stop_id=req.destination_stop_id,
        departure_date=req.departure_date.isoformat(),
        requested_time=req.departure_time,
        criterion=req.criterion,
        journeys=journeys_out,
        data_freshness_warnings=freshness_warnings,
        calendar_validity_note=cal_note,
        no_route_reason=no_route_reason,
    )
    if journeys_out:
        route_plan_cache.set(cache_key, response, ttl_seconds=300.0)
    return response


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

    # Find nearby stops for both endpoints (8 km radius to ensure Metro connection anywhere in Delhi NCR)
    origin_nearby = ctx.repository.find_nearby_stops(origin_stop.stop_lat, origin_stop.stop_lon, radius_meters=8000.0, limit=35)
    dest_nearby = ctx.repository.find_nearby_stops(dest_stop.stop_lat, dest_stop.stop_lon, radius_meters=8000.0, limit=35)

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


@router.post("/lost-assistance", response_model=LostAssistanceResponse, summary="Emergency Lost Commuter Rerouting")
def lost_assistance(req: LostAssistanceRequest):
    """Emergency Lost Assistance:
    Locates the commuter's nearest bus stand, auto stand, and metro station,
    provides pedestrian walking guidance, and recalculates the complete journey to their destination.
    """
    ctx = get_transit_context()
    if not ctx.repository:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Transit repository is not initialized.",
        )

    # 1. Specifically search for nearest bus stops (up to 4km, expanding to 10km)
    bus_nearby = ctx.repository.find_nearby_stops(
        req.user_lat, req.user_lon, radius_meters=4000.0, limit=20,
        filter_fn=lambda s: not s.stop_id.startswith("metro_")
    )
    if not bus_nearby:
        bus_nearby = ctx.repository.find_nearby_stops(
            req.user_lat, req.user_lon, radius_meters=10000.0, limit=20,
            filter_fn=lambda s: not s.stop_id.startswith("metro_")
        )

    # 2. Specifically search for nearest Metro stations (up to 8km, expanding to 25km)
    metro_nearby = ctx.repository.find_nearby_stops(
        req.user_lat, req.user_lon, radius_meters=8000.0, limit=10,
        filter_fn=lambda s: s.stop_id.startswith("metro_")
    )
    if not metro_nearby:
        metro_nearby = ctx.repository.find_nearby_stops(
            req.user_lat, req.user_lon, radius_meters=25000.0, limit=10,
            filter_fn=lambda s: s.stop_id.startswith("metro_")
        )

    nearest_bus_pair = bus_nearby[0] if bus_nearby else None
    nearest_metro_pair = metro_nearby[0] if metro_nearby else None

    # Overall nearest
    all_candidates = []
    if nearest_bus_pair:
        all_candidates.append(nearest_bus_pair)
    if nearest_metro_pair:
        all_candidates.append(nearest_metro_pair)

    if not all_candidates:
        default_stop = ctx.repository.get_stop("metro_122") or (
            list(ctx.dataset.stops.values())[0] if ctx.dataset and ctx.dataset.stops else None
        )
        if default_stop:
            all_candidates = [(default_stop, 1200.0)]
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No transit stops found near the provided location.",
            )

    all_candidates.sort(key=lambda x: x[1])
    overall_pair = all_candidates[0]

    def _build_detail(stop, dist_m: float, st_type: str) -> NearestStationDetail:
        walk_mins = max(1.0, round(dist_m / 80.0, 1))
        lines: list[str] = []
        if ctx.dataset:
            dep_routes = set()
            for tid, _, _ in ctx.repository.get_stop_departures(stop.stop_id)[:20]:
                trip = ctx.repository.get_trip(tid)
                if trip and trip.route_id:
                    route = ctx.repository.get_route(trip.route_id)
                    if route:
                        dep_routes.add(route.route_short_name or route.route_long_name)
            lines = sorted(list(dep_routes))[:4]

        if st_type == "metro":
            dirs = f"Walk ~{int(dist_m)}m ({walk_mins} mins) to {stop.stop_name} Metro Station. Enter via nearest customer gate."
        elif st_type == "auto_stand":
            dirs = f"Dedicated Auto/E-Rickshaw stand located at the entrance of {stop.stop_name}."
        else:
            dirs = f"Walk ~{int(dist_m)}m ({walk_mins} mins) to {stop.stop_name} DTC Bus Stand."

        return NearestStationDetail(
            stop_id=stop.stop_id,
            stop_name=stop.stop_name,
            stop_lat=stop.stop_lat,
            stop_lon=stop.stop_lon,
            type=st_type,
            distance_meters=round(dist_m, 1),
            walk_minutes=walk_mins,
            lines=lines,
            directions_text=dirs,
        )

    nearest_metro_detail = (
        _build_detail(nearest_metro_pair[0], nearest_metro_pair[1], "metro")
        if nearest_metro_pair
        else None
    )
    nearest_bus_detail = (
        _build_detail(nearest_bus_pair[0], nearest_bus_pair[1], "bus")
        if nearest_bus_pair
        else None
    )

    overall_type = "metro" if overall_pair[0].stop_id.startswith("metro_") else "bus"
    nearest_overall_detail = _build_detail(overall_pair[0], overall_pair[1], overall_type)

    # Auto rickshaw fare estimate from location to closest metro or major hub (GNCTD Meter Slabs)
    auto_dist_km = (
        round(nearest_metro_pair[1] / 1000.0, 1)
        if nearest_metro_pair
        else round(overall_pair[1] / 1000.0, 1)
    )
    auto_fare = 30.0 if auto_dist_km <= 1.5 else round(30.0 + (auto_dist_km - 1.5) * 11.0)
    if nearest_metro_detail:
        auto_pickup = (
            f"Dedicated DMRC Feeder Auto/E-Rickshaw stand at {nearest_metro_detail.stop_name} (Gate area). "
            f"Standard GNCTD meter fare to this station is ~₹{auto_fare}."
        )
    else:
        auto_pickup = (
            f"GNCTD Auto-Rickshaw pickup point available near {nearest_overall_detail.stop_name}. "
            f"Estimated meter fare is ~₹{auto_fare}."
        )

    # 3. Reroute / Map Journey to Destination if provided
    dest_id = req.destination_stop_id
    if not dest_id and req.destination_name and ctx.repository:
        stops, _ = ctx.repository.search_stops(req.destination_name, page=1, page_size=5)
        if stops:
            m = [s for s in stops if s.stop_id.startswith("metro_")]
            dest_id = m[0].stop_id if m else stops[0].stop_id

    rerouted_plan: Optional[RoutePlanResponse] = None
    if dest_id and ctx.router:
        best_origin_stop = (
            nearest_metro_pair[0]
            if (nearest_metro_pair and nearest_metro_pair[1] <= 2500.0)
            else overall_pair[0]
        )

        now_dt = datetime.now()
        dep_str = now_dt.strftime("%H:%M:%S")

        try:
            plan_req = RoutePlanRequest(
                origin_stop_id=best_origin_stop.stop_id,
                destination_stop_id=dest_id,
                departure_date=now_dt.date(),
                departure_time=dep_str,
                criterion="fastest",
                max_transfers=3,
                max_walk_meters=1000,
                mode_preference=req.preferred_mode or "all",
            )
            rerouted_plan = plan_route(plan_req)
            if rerouted_plan:
                rerouted_plan.data_freshness_warnings.insert(
                    0,
                    f"🚨 Emergency Reroute Activated: Journey re-mapped from closest transit hub ({best_origin_stop.stop_name}).",
                )
        except Exception:
            rerouted_plan = None

    # 4. Construct reassuring message and spoken guidance
    chosen_stop_name = (
        nearest_metro_detail.stop_name
        if nearest_metro_detail
        else nearest_overall_detail.stop_name
    )
    dist_txt = (
        f"{int(nearest_metro_detail.distance_meters if nearest_metro_detail else nearest_overall_detail.distance_meters)} meters"
    )

    dest_txt = ""
    if rerouted_plan and ctx.dataset and dest_id in ctx.dataset.stops:
        dest_txt = f" to {ctx.dataset.stops[dest_id].stop_name}"

    reassuring_msg = (
        f"You are safe. The closest transit hub is {chosen_stop_name} ({dist_txt} away). "
        f"Follow the walking directions or take an auto-rickshaw (~₹{auto_fare}). "
        f"Your updated route{dest_txt} has been mapped below."
    )

    spoken = {
        "en": f"Don't worry! You are near {chosen_stop_name}, approximately {dist_txt} away. I have re-mapped your journey{dest_txt}.",
        "hi": f"चिंता न करें! आप {chosen_stop_name} के पास हैं (लगभग {dist_txt} दूर)। आपकी यात्रा का नया रूट तैयार कर दिया गया है।",
        "hinglish": f"Fret not! Aap {chosen_stop_name} ke paas hain (~{dist_txt} door). Humne aapka safar naye sire se map kar diya hai.",
    }

    return LostAssistanceResponse(
        user_lat=req.user_lat,
        user_lon=req.user_lon,
        nearest_metro=nearest_metro_detail,
        nearest_bus_stop=nearest_bus_detail,
        nearest_station_overall=nearest_overall_detail,
        auto_rickshaw_fare_estimate_inr=float(auto_fare),
        auto_pickup_instructions=auto_pickup,
        rerouted_plan=rerouted_plan,
        reassuring_message=reassuring_msg,
        spoken_guidance=spoken,
    )


