"""Multimodal timetable-aware transit graph builder."""
from __future__ import annotations

import bisect
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

from app.models.transit import GTFSDataset, Stop, StopTime, TransferType
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
        # stop_id -> list of scheduled outgoing edges (sorted by departure_seconds)
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

    def finalize(self):
        """Sort all transit adjacency lists by departure_seconds for fast bisect lookups."""
        for stop_id in self.transit_adj:
            self.transit_adj[stop_id].sort(key=lambda e: e.departure_seconds)

    def get_transit_departures(
        self,
        stop_id: str,
        after_seconds: int,
    ) -> List[ScheduledTransitEdge]:
        edges = self.transit_adj.get(stop_id, [])
        if not edges:
            return []
        idx = bisect.bisect_left(edges, after_seconds, key=lambda e: e.departure_seconds)
        return edges[idx:]

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

        # 2. Add GTFS explicit transfers if present
        if dataset.transfers:
            for tf in dataset.transfers:
                if tf.transfer_type == TransferType.NOT_POSSIBLE:
                    continue
                s1 = dataset.stops.get(tf.from_stop_id)
                s2 = dataset.stops.get(tf.to_stop_id)
                if not s1 or not s2:
                    continue
                dist = haversine_meters(s1.stop_lat, s1.stop_lon, s2.stop_lat, s2.stop_lon)
                duration = tf.min_transfer_time if tf.min_transfer_time is not None else estimated_walk_seconds(dist)
                graph.add_walk_edge(WalkingTransferEdge(
                    from_stop_id=tf.from_stop_id,
                    to_stop_id=tf.to_stop_id,
                    distance_meters=round(dist, 1),
                    duration_seconds=duration,
                    confidence="gtfs_transfers_txt",
                ))

        # 3. Synthesize verified walking transfer links between nearby stops using spatial grid
        if enable_walking and dataset.stops:
            cell_size = 0.005  # ~500m
            grid: Dict[Tuple[int, int], List[Stop]] = {}
            for s in dataset.stops.values():
                cell = (int(s.stop_lat / cell_size), int(s.stop_lon / cell_size))
                grid.setdefault(cell, []).append(s)

            for (ci, cj), cell_stops in grid.items():
                neighbor_stops: List[Stop] = []
                for di in (0, 1):
                    for dj in (-1, 0, 1):
                        if di == 0 and dj < 0:
                            continue
                        neighbor_stops.extend(grid.get((ci + di, cj + dj), []))

                for s1 in cell_stops:
                    for s2 in neighbor_stops:
                        if s1.stop_id >= s2.stop_id:
                            continue
                        if abs(s1.stop_lat - s2.stop_lat) <= 0.005 and abs(s1.stop_lon - s2.stop_lon) <= 0.005:
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

        # Sort all transit adjacency lists
        graph.finalize()
        return graph

