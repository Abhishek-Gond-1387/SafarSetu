"""Timetable-aware public transport routing engine."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import heapq
from itertools import count
from typing import Dict, List, Optional, Set, Tuple

from app.models.journey import Journey, JourneyLeg, LegMode, RouteRankCriterion
from app.models.transit import GTFSDataset, StopTime, RouteType
from app.services.graph_builder import ScheduledTransitEdge, TransitGraph
from app.utils.geo import haversine_meters


class RoutingEngine:
    """Finds feasible, timetable-compliant journeys across the transit network."""

    def __init__(self, dataset: GTFSDataset, graph: TransitGraph):
        self.dataset = dataset
        self.graph = graph

    @staticmethod
    def calculate_transit_fare(
        mode: LegMode,
        from_lat: float,
        from_lon: float,
        to_lat: float,
        to_lon: float,
        route_name: Optional[str] = None,
    ) -> float:
        """Calculate official Delhi transit fares (DMRC distance slabs or DTC bus slabs)."""
        d_km = haversine_meters(from_lat, from_lon, to_lat, to_lon) / 1000.0
        if mode == LegMode.METRO:
            if d_km <= 2.0:
                return 10.0
            elif d_km <= 5.0:
                return 20.0
            elif d_km <= 12.0:
                return 30.0
            elif d_km <= 21.0:
                return 40.0
            elif d_km <= 32.0:
                return 50.0
            else:
                return 60.0
        else:
            # DTC Bus Fare (Delhi Government official distance slabs)
            r_str = (route_name or "").upper()
            is_ac = "AC" in r_str or "EXP" in r_str or "ELECTRIC" in r_str
            if is_ac:
                if d_km <= 4.0:
                    return 10.0
                elif d_km <= 8.0:
                    return 15.0
                elif d_km <= 12.0:
                    return 20.0
                else:
                    return 25.0
            else:
                if d_km <= 4.0:
                    return 5.0
                elif d_km <= 10.0:
                    return 10.0
                else:
                    return 15.0

    def plan_journey(
        self,
        origin_stop_id: str,
        destination_stop_id: str,
        departure_date: date,
        departure_seconds: int,
        max_transfers: int = 3,
        criterion: RouteRankCriterion = RouteRankCriterion.FASTEST,
        max_candidates: int = 3,
        mode_filter: str = "all",
    ) -> Tuple[List[Journey], Optional[str]]:
        """Compute candidate journeys from origin to destination.

        Returns:
            Tuple of (list_of_journeys, no_route_reason_if_empty).
        """
        if origin_stop_id not in self.dataset.stops:
            return [], f"Origin stop '{origin_stop_id}' does not exist in dataset."
        if destination_stop_id not in self.dataset.stops:
            return [], f"Destination stop '{destination_stop_id}' does not exist in dataset."
        if origin_stop_id == destination_stop_id:
            return [], "Origin and destination stops are identical."

        # Determine calendar service filter for departure_date
        cal_start = min((cs.start_date for cs in self.dataset.calendar.values()), default=None)
        cal_end = max((cs.end_date for cs in self.dataset.calendar.values()), default=None)
        is_historical = cal_end is not None and cal_end < date.today()

        active_services: Set[str] = set()
        if cal_start and cal_end and (cal_start <= departure_date <= cal_end):
            # Strict date-range calendar check
            for sid in self.dataset.calendar:
                if self.dataset.service_active_on(sid, departure_date):
                    active_services.add(sid)
            # If date is within calendar range but no services active (e.g. holiday or inactive day)
            if not active_services and self.dataset.calendar:
                return [], f"No scheduled transit services operate on {departure_date.isoformat()}."
        elif self.dataset.calendar:
            # Query date is outside feed calendar range (historical or future query).
            # Match by weekday flag to allow planning on historical schedules.
            weekday = departure_date.weekday()
            for sid, cs in self.dataset.calendar.items():
                flags = [cs.monday, cs.tuesday, cs.wednesday, cs.thursday, cs.friday, cs.saturday, cs.sunday]
                if flags[weekday]:
                    active_services.add(sid)

        # Priority queue: (arrival_time_sec, num_transfers, tiebreaker, current_stop_id, current_trip_id, legs)
        counter = count()
        pq: List[Tuple[int, int, int, str, Optional[str], List[JourneyLeg]]] = []
        heapq.heappush(pq, (departure_seconds, 0, next(counter), origin_stop_id, None, []))

        # Track arrival times per (stop_id, transfers) to permit up to 2 distinct arrival alternatives per stop
        best_arrivals: Dict[Tuple[str, int], List[int]] = {}
        found_journeys: List[Journey] = []

        TRANSFER_BUFFER_SEC = 120  # Minimum 2 minutes buffer when switching lines
        MAX_SEARCH_HORIZON_SEC = 14 * 3600  # Search up to 14 hours after departure

        while pq and len(found_journeys) < max_candidates:
            curr_time, num_transfers, _, curr_stop, curr_trip_id, legs = heapq.heappop(pq)

            if curr_time > departure_seconds + MAX_SEARCH_HORIZON_SEC:
                break

            # Destination reached!
            if curr_stop == destination_stop_id and legs:
                journey = self._assemble_journey(
                    legs,
                    criterion,
                    requested_dep_seconds=departure_seconds,
                    requested_date=departure_date,
                    is_historical=is_historical,
                )
                # Deduplicate by departure & arrival time
                if not any(
                    j.departure_time_str == journey.departure_time_str and j.arrival_time_str == journey.arrival_time_str
                    for j in found_journeys
                ):
                    found_journeys.append(journey)
                continue

            state_key = (curr_stop, num_transfers)
            existing_arrivals = best_arrivals.get(state_key, [])
            if len(existing_arrivals) >= 2 and curr_time >= max(existing_arrivals):
                continue
            if any(abs(arr - curr_time) < 60 for arr in existing_arrivals):
                continue
            existing_arrivals.append(curr_time)
            best_arrivals[state_key] = existing_arrivals

            # 1. Scheduled Transit Outgoing Edges
            transit_edges = self.graph.get_transit_departures(curr_stop, after_seconds=curr_time)
            seen_route_dest: Dict[Tuple[str, str], int] = {}
            for edge in transit_edges:
                is_same_trip = (curr_trip_id == edge.trip_id)

                # Prune departures beyond reasonable waiting window (90 mins) when transferring
                if not is_same_trip and edge.departure_seconds > curr_time + 5400:
                    break  # edges are sorted by departure_seconds, so subsequent edges are strictly later

                trip = self.dataset.trips.get(edge.trip_id)
                # Check calendar service filter
                if active_services and trip and trip.service_id not in active_services:
                    continue

                # Frequency pruning: only consider earliest departure per (route_id, to_stop_id) when transferring at intermediate stops
                if not is_same_trip and curr_trip_id is not None:
                    rd_key = (edge.route_id, edge.to_stop_id)
                    seen_count = seen_route_dest.get(rd_key, 0)
                    if seen_count >= 1:
                        continue
                    seen_route_dest[rd_key] = seen_count + 1

                next_transfers = num_transfers if is_same_trip else (num_transfers + 1 if curr_trip_id is not None else num_transfers)
                if next_transfers > max_transfers:
                    continue

                # Buffer needed if changing trips
                min_dep = curr_time if is_same_trip else (curr_time + TRANSFER_BUFFER_SEC if curr_trip_id is not None else curr_time)
                if edge.departure_seconds < min_dep:
                    continue

                route = self.dataset.routes.get(edge.route_id)
                is_metro = (
                    (route and (route.route_type == RouteType.METRO or route.route_type == 1)) or
                    edge.route_id.startswith("metro_") or
                    (route and "dmrc" in (route.agency_id or "").lower())
                )

                # Filter by mode preference if specified
                if mode_filter == "metro" and not is_metro:
                    continue
                if mode_filter == "bus" and is_metro:
                    continue

                leg_mode = LegMode.METRO if is_metro else LegMode.BUS
                r_short = route.route_short_name if route else None
                r_long = route.route_long_name if route else None

                # Compute distance-based fare for Metro and DTC Bus legs
                from_s = self.dataset.stops.get(edge.from_stop_id)
                to_s = self.dataset.stops.get(edge.to_stop_id)
                leg_fare = None
                if from_s and to_s:
                    leg_fare = self.calculate_transit_fare(
                        leg_mode,
                        from_s.stop_lat,
                        from_s.stop_lon,
                        to_s.stop_lat,
                        to_s.stop_lon,
                        r_short or r_long,
                    )

                new_leg = JourneyLeg(
                    mode=leg_mode,
                    from_stop_id=edge.from_stop_id,
                    to_stop_id=edge.to_stop_id,
                    from_stop_name=self.dataset.stops[edge.from_stop_id].stop_name,
                    to_stop_name=self.dataset.stops[edge.to_stop_id].stop_name,
                    departure_seconds=edge.departure_seconds,
                    arrival_seconds=edge.arrival_seconds,
                    duration_seconds=edge.duration_seconds,
                    route_id=edge.route_id,
                    route_short_name=r_short,
                    route_long_name=r_long,
                    trip_id=edge.trip_id,
                    headsign=trip.trip_headsign if trip else None,
                    fare_inr=leg_fare,
                    fare_currency="INR" if leg_fare is not None else None,
                    source_id=route.source_id if route else self.dataset.source_id,
                )

                new_legs = list(legs)
                # Collapse consecutive legs on the same trip cleanly without mutating shared parent objects
                if new_legs and new_legs[-1].trip_id == edge.trip_id and new_legs[-1].to_stop_id == edge.from_stop_id:
                    prev = new_legs[-1]
                    from_s = self.dataset.stops.get(prev.from_stop_id)
                    to_s = self.dataset.stops.get(edge.to_stop_id)
                    c_fare = prev.fare_inr
                    if from_s and to_s:
                        c_fare = self.calculate_transit_fare(
                            prev.mode,
                            from_s.stop_lat,
                            from_s.stop_lon,
                            to_s.stop_lat,
                            to_s.stop_lon,
                            prev.route_short_name or prev.route_long_name,
                        )

                    collapsed_leg = JourneyLeg(
                        mode=prev.mode,
                        from_stop_id=prev.from_stop_id,
                        to_stop_id=edge.to_stop_id,
                        from_stop_name=prev.from_stop_name,
                        to_stop_name=self.dataset.stops[edge.to_stop_id].stop_name,
                        departure_seconds=prev.departure_seconds,
                        arrival_seconds=edge.arrival_seconds,
                        duration_seconds=edge.arrival_seconds - prev.departure_seconds,
                        route_id=prev.route_id,
                        route_short_name=prev.route_short_name,
                        route_long_name=prev.route_long_name,
                        trip_id=prev.trip_id,
                        headsign=prev.headsign,
                        intermediate_stops=prev.intermediate_stops + [edge.from_stop_id],
                        fare_inr=c_fare,
                        fare_currency="INR" if c_fare is not None else None,
                        source_id=prev.source_id,
                    )
                    new_legs[-1] = collapsed_leg
                else:
                    new_legs.append(new_leg)

                heapq.heappush(
                    pq,
                    (edge.arrival_seconds, next_transfers, next(counter), edge.to_stop_id, edge.trip_id, new_legs),
                )

            # 2. Walking Transfer Edges (if not walking consecutively)
            if not (legs and legs[-1].mode == LegMode.WALK):
                for walk_edge in self.graph.get_walk_transfers(curr_stop):
                    arr_walk = curr_time + walk_edge.duration_seconds
                    walk_leg = JourneyLeg(
                        mode=LegMode.WALK,
                        from_stop_id=walk_edge.from_stop_id,
                        to_stop_id=walk_edge.to_stop_id,
                        from_stop_name=self.dataset.stops[walk_edge.from_stop_id].stop_name,
                        to_stop_name=self.dataset.stops[walk_edge.to_stop_id].stop_name,
                        departure_seconds=curr_time,
                        arrival_seconds=arr_walk,
                        duration_seconds=walk_edge.duration_seconds,
                        distance_meters=walk_edge.distance_meters,
                        walk_distance_type="straight_line",
                    )
                    heapq.heappush(
                        pq,
                        (arr_walk, num_transfers, next(counter), walk_edge.to_stop_id, None, legs + [walk_leg]),
                    )

        if not found_journeys:
            reason = (
                f"No feasible transit route found between '{self.dataset.stops[origin_stop_id].stop_name}' "
                f"and '{self.dataset.stops[destination_stop_id].stop_name}' for departure time "
                f"within {MAX_SEARCH_HORIZON_SEC // 3600}h. "
                "The stops may belong to disconnected network components or exceed transfer limits."
            )
            return [], reason

        return found_journeys, None

    @staticmethod
    def _validate_leg_chronology(legs: List[JourneyLeg]) -> bool:
        """Verify strict chronological sequence and non-negative leg durations."""
        if not legs:
            return True
        for i, leg in enumerate(legs):
            if leg.arrival_seconds < leg.departure_seconds:
                return False
            if i > 0 and leg.departure_seconds < legs[i - 1].arrival_seconds:
                return False
        return True

    def _assemble_journey(
        self,
        legs: List[JourneyLeg],
        criterion: RouteRankCriterion,
        requested_dep_seconds: int = 0,
        requested_date: Optional[date] = None,
        is_historical: bool = False,
    ) -> Journey:
        assert self._validate_leg_chronology(legs), "Journey legs must be strictly chronological"

        first_dep = legs[0].departure_seconds if legs else requested_dep_seconds
        last_arr = legs[-1].arrival_seconds if legs else requested_dep_seconds
        transit_sec = max(0, last_arr - first_dep)
        initial_wait_sec = max(0, first_dep - requested_dep_seconds)
        total_walk = sum(l.distance_meters or 0 for l in legs if l.mode == LegMode.WALK)

        transit_legs = [l for l in legs if l.mode != LegMode.WALK]
        num_transfers = max(0, len(transit_legs) - 1)

        # Fare computation
        total_fare = None
        fare_complete = False
        leg_fares = [l.fare_inr for l in transit_legs if l.fare_inr is not None]
        if len(leg_fares) == len(transit_legs) and transit_legs:
            total_fare = sum(leg_fares)
            fare_complete = True

        warnings = []
        is_expired = False
        if self.dataset.feed_info and self.dataset.feed_info.feed_end_date:
            if self.dataset.feed_info.feed_end_date < date.today():
                is_expired = True
                warnings.append(
                    f"Dataset {self.dataset.source_id} expired on "
                    f"{self.dataset.feed_info.feed_end_date.isoformat()}. Schedule is historical."
                )

        if not fare_complete:
            warnings.append("Fare information is not available in the genuine dataset for these routes.")

        return Journey(
            legs=legs,
            total_duration_seconds=transit_sec,
            total_walk_meters=total_walk,
            num_transfers=num_transfers,
            total_fare_inr=total_fare,
            fare_complete=fare_complete,
            rank_criterion=criterion,
            feed_expired=is_expired,
            provenance_sources=[self.dataset.source_id],
            warnings=warnings,
            initial_wait_seconds=initial_wait_sec,
        )

