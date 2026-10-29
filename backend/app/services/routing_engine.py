"""Timetable-aware public transport routing engine."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import heapq
from typing import Dict, List, Optional, Set, Tuple

from app.models.journey import Journey, JourneyLeg, LegMode, RouteRankCriterion
from app.models.transit import GTFSDataset, StopTime
from app.services.graph_builder import ScheduledTransitEdge, TransitGraph


@dataclass
class RoutingState:
    arrival_time_sec: int
    transfers: int
    walk_meters: float
    path: List[Tuple[str, Optional[ScheduledTransitEdge], Optional[float]]] # (stop_id, edge_used, walk_dist)


class RoutingEngine:
    """Finds feasible, timetable-compliant journeys across the transit network."""

    def __init__(self, dataset: GTFSDataset, graph: TransitGraph):
        self.dataset = dataset
        self.graph = graph

    def plan_journey(
        self,
        origin_stop_id: str,
        destination_stop_id: str,
        departure_date: date,
        departure_seconds: int,
        max_transfers: int = 3,
        criterion: RouteRankCriterion = RouteRankCriterion.FASTEST,
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

        # Check calendar validity for departure_date
        active_services: Set[str] = set()
        for sid in self.dataset.calendar:
            if self.dataset.service_active_on(sid, departure_date):
                active_services.add(sid)

        # Priority queue for Time-Dependent Dijkstra:
        # elements: (arrival_time_sec, transfers, current_stop_id, current_trip_id, legs_history)
        # We allow up to max_transfers
        pq = []
        heapq.heappush(pq, (departure_seconds, 0, origin_stop_id, None, []))

        # Best arrival tracking: (stop_id, transfers) -> earliest arrival
        best_arrivals: Dict[Tuple[str, int], int] = {}
        found_journeys: List[Journey] = []

        TRANSFER_BUFFER_SEC = 120  # Minimum 2 minutes buffer when switching lines
        MAX_SEARCH_HORIZON_SEC = 14 * 3600  # Search up to 14 hours after departure

        while pq and len(found_journeys) < 3:
            curr_time, num_transfers, curr_stop, curr_trip_id, legs = heapq.heappop(pq)

            if curr_time > departure_seconds + MAX_SEARCH_HORIZON_SEC:
                break

            # Destination reached!
            if curr_stop == destination_stop_id and legs:
                journey = self._assemble_journey(legs, criterion)
                # Check for duplicates
                if not any(j.departure_time_str == journey.departure_time_str and j.arrival_time_str == journey.arrival_time_str for j in found_journeys):
                    found_journeys.append(journey)
                continue

            state_key = (curr_stop, num_transfers)
            if state_key in best_arrivals and best_arrivals[state_key] < curr_time:
                continue
            best_arrivals[state_key] = curr_time

            # 1. Scheduled Transit Outgoing Edges
            transit_edges = self.graph.get_transit_departures(curr_stop, after_seconds=curr_time)
            for edge in transit_edges:
                trip = self.dataset.trips.get(edge.trip_id)
                # Check calendar service filter if calendar data exists
                if active_services and trip and trip.service_id not in active_services:
                    continue

                is_same_trip = (curr_trip_id == edge.trip_id)
                next_transfers = num_transfers if is_same_trip else (num_transfers + 1 if curr_trip_id is not None else num_transfers)
                if next_transfers > max_transfers:
                    continue

                # Buffer needed if changing trips
                min_dep = curr_time if is_same_trip else (curr_time + TRANSFER_BUFFER_SEC if curr_trip_id is not None else curr_time)
                if edge.departure_seconds < min_dep:
                    continue

                new_leg = JourneyLeg(
                    mode=LegMode.BUS,
                    from_stop_id=edge.from_stop_id,
                    to_stop_id=edge.to_stop_id,
                    from_stop_name=self.dataset.stops[edge.from_stop_id].stop_name,
                    to_stop_name=self.dataset.stops[edge.to_stop_id].stop_name,
                    departure_seconds=edge.departure_seconds,
                    arrival_seconds=edge.arrival_seconds,
                    duration_seconds=edge.duration_seconds,
                    route_id=edge.route_id,
                    trip_id=edge.trip_id,
                    source_id=self.dataset.source_id,
                )

                new_legs = list(legs)
                # Collapse consecutive legs on the same trip
                if new_legs and new_legs[-1].trip_id == edge.trip_id and new_legs[-1].to_stop_id == edge.from_stop_id:
                    last_leg = new_legs[-1]
                    last_leg.to_stop_id = edge.to_stop_id
                    last_leg.to_stop_name = self.dataset.stops[edge.to_stop_id].stop_name
                    last_leg.arrival_seconds = edge.arrival_seconds
                    last_leg.duration_seconds = edge.arrival_seconds - last_leg.departure_seconds
                    last_leg.intermediate_stops.append(edge.from_stop_id)
                else:
                    new_legs.append(new_leg)

                heapq.heappush(pq, (edge.arrival_seconds, next_transfers, edge.to_stop_id, edge.trip_id, new_legs))

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
                    heapq.heappush(pq, (arr_walk, num_transfers, walk_edge.to_stop_id, None, legs + [walk_leg]))

        if not found_journeys:
            reason = (
                f"No feasible transit route found between '{self.dataset.stops[origin_stop_id].stop_name}' "
                f"and '{self.dataset.stops[destination_stop_id].stop_name}' for departure time "
                f"within {MAX_SEARCH_HORIZON_SEC // 3600}h. "
                "The stops may belong to disconnected network components or exceed transfer limits."
            )
            return [], reason

        return found_journeys, None

    def _assemble_journey(self, legs: List[JourneyLeg], criterion: RouteRankCriterion) -> Journey:
        total_sec = legs[-1].arrival_seconds - legs[0].departure_seconds if legs else 0
        total_walk = sum(l.distance_meters or 0 for l in legs if l.mode == LegMode.WALK)
        # Count transfers: number of transit vehicle boardings minus 1
        transit_legs = [l for l in legs if l.mode != LegMode.WALK]
        num_transfers = max(0, len(transit_legs) - 1)

        # Fare computation:
        # If dataset lacks fare data, fare is None and fare_complete is False per Section 4
        has_fares = self.dataset.has_fare_data
        total_fare = None
        fare_complete = False
        if has_fares:
            # sum known leg fares
            leg_fares = [l.fare_inr for l in transit_legs if l.fare_inr is not None]
            if len(leg_fares) == len(transit_legs):
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
            total_duration_seconds=total_sec,
            total_walk_meters=total_walk,
            num_transfers=num_transfers,
            total_fare_inr=total_fare,
            fare_complete=fare_complete,
            rank_criterion=criterion,
            feed_expired=is_expired,
            provenance_sources=[self.dataset.source_id],
            warnings=warnings,
        )

