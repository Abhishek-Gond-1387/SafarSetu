"""Multimodal timetable-aware transit graph builder."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

from app.models.transit import GTFSDataset, StopTime
from app.utils.geo import estimated_walk_seconds, haversine_meters


@dataclass
class ScheduledTransitEdge:
    """Directed connection between two consecutive stops on a scheduled trip."""
    from_stop_id: str
    to_stop_id: str
    trip_id: str
    route_id: str
    departure_seconds: int
    arrival_seconds: int
    duration_seconds: int


@dataclass
class WalkingTransferEdge:
    """Walking link between two distinct stops."""
    from_stop_id: str
    to_stop_id: str
    distance_meters: float
    duration_seconds: int
    distance_type: str = "straight_line"  # Explicitly labeled per spec
    confidence: str = "straight_line_haversine"


class TransitGraph:
    """Graph structure containing scheduled transit connections and walking links."""

    def __init__(self):
        # stop_id -> list of scheduled outgoing edges
        self.transit_adj: Dict[str, List[ScheduledTransitEdge]] = {}
        # stop_id -> list of walking transfer edges
        self.walk_adj: Dict[str, List[WalkingTransferEdge]] = {}
        self.total_nodes: int = 0
        self.total_transit_edges: int = 0
        self.total_walk_edges: int = 0

    def add_transit_edge(self, edge: ScheduledTransitEdge):
        if edge.from_stop_id not in self.transit_adj:
            self.transit_adj[edge.from_stop_id] = []
        self.transit_adj[edge.from_stop_id].append(edge)
        self.total_transit_edges += 1

    def add_walk_edge(self, edge: WalkingTransferEdge):
        if edge.from_stop_id not in self.walk_adj:
            self.walk_adj[edge.from_stop_id] = []
        self.walk_adj[edge.from_stop_id].append(edge)
        self.total_walk_edges += 1

    def get_transit_departures(
        self,
        stop_id: str,
        after_seconds: int,
    ) -> List[ScheduledTransitEdge]:
        edges = self.transit_adj.get(stop_id, [])
        return [e for e in edges if e.departure_seconds >= after_seconds]

    def get_walk_transfers(self, stop_id: str) -> List[WalkingTransferEdge]:
        return self.walk_adj.get(stop_id, [])


class GraphBuilder:
    """Constructs a TransitGraph from a validated GTFSDataset."""

    @classmethod
    def build_graph(
        cls,
        dataset: GTFSDataset,
        max_walk_transfer_meters: float = 300.0,
        enable_walking: bool = True,
    ) -> TransitGraph:
        graph = TransitGraph()
        graph.total_nodes = len(dataset.stops)

        # 1. Scheduled transit edges from stop_times
        for tid, st_list in dataset.stop_times.items():
            trip = dataset.trips.get(tid)
            route_id = trip.route_id if trip else "UNKNOWN"
            for i in range(len(st_list) - 1):
                u = st_list[i]
                v = st_list[i + 1]
                if u.departure_seconds is not None and v.arrival_seconds is not None:
                    if v.arrival_seconds >= u.departure_seconds:
                        edge = ScheduledTransitEdge(
                            from_stop_id=u.stop_id,
                            to_stop_id=v.stop_id,
                            trip_id=tid,
                            route_id=route_id,
                            departure_seconds=u.departure_seconds,
                            arrival_seconds=v.arrival_seconds,
                            duration_seconds=v.arrival_seconds - u.departure_seconds,
                        )
                        graph.add_transit_edge(edge)

        # 2. Synthesize verified walking transfer links between nearby stops
        if enable_walking and len(dataset.stops) <= 5000:
            # For moderate stops count, create spatial transfers
            stop_list = list(dataset.stops.values())
            for i in range(len(stop_list)):
                s1 = stop_list[i]
                for j in range(i + 1, len(stop_list)):
                    s2 = stop_list[j]
                    # Quick delta lat/lon check (~300m is ~0.003 deg)
                    if abs(s1.stop_lat - s2.stop_lat) < 0.005 and abs(s1.stop_lon - s2.stop_lon) < 0.005:
                        dist = haversine_meters(s1.stop_lat, s1.stop_lon, s2.stop_lat, s2.stop_lon)
                        if 10.0 <= dist <= max_walk_transfer_meters:
                            walk_sec = estimated_walk_seconds(dist)
                            graph.add_walk_edge(WalkingTransferEdge(
                                from_stop_id=s1.stop_id,
                                to_stop_id=s2.stop_id,
                                distance_meters=round(dist, 1),
                                duration_seconds=walk_sec,
                            ))
                            graph.add_walk_edge(WalkingTransferEdge(
                                from_stop_id=s2.stop_id,
                                to_stop_id=s1.stop_id,
                                distance_meters=round(dist, 1),
                                duration_seconds=walk_sec,
                            ))

        return graph

