"""Transit data repository with in-memory spatial and relational indexing."""
from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple

from app.models.transit import GTFSDataset, Route, Stop, StopTime, Trip
from app.utils.geo import bbox_for_radius, haversine_meters


class TransitRepository:
    """Manages queries across loaded GTFS datasets."""

    def __init__(self, dataset: Optional[GTFSDataset] = None):
        self.dataset: Optional[GTFSDataset] = dataset
        self._stops_by_id: Dict[str, Stop] = {}
        self._routes_by_id: Dict[str, Route] = {}
        self._trips_by_id: Dict[str, Trip] = {}
        # Stop-to-trips inverted index: stop_id -> list of (trip_id, stop_sequence, departure_sec)
        self._stop_departures: Dict[str, List[Tuple[str, int, int]]] = {}
        if dataset:
            self._index_dataset()

    def set_dataset(self, dataset: GTFSDataset):
        self.dataset = dataset
        self._index_dataset()

    def _index_dataset(self):
        if not self.dataset:
            return
        self._stops_by_id = self.dataset.stops
        self._routes_by_id = self.dataset.routes
        self._trips_by_id = self.dataset.trips

        self._stop_departures.clear()
        for tid, st_list in self.dataset.stop_times.items():
            for st in st_list:
                if st.departure_seconds is not None:
                    if st.stop_id not in self._stop_departures:
                        self._stop_departures[st.stop_id] = []
                    self._stop_departures[st.stop_id].append((tid, st.stop_sequence, st.departure_seconds))

    def get_stop(self, stop_id: str) -> Optional[Stop]:
        return self._stops_by_id.get(stop_id)

    def search_stops(
        self,
        query: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[Stop], int]:
        all_stops = list(self._stops_by_id.values())
        if query:
            q = query.strip().lower()
            filtered = [
                s for s in all_stops
                if q in s.stop_name.lower() or (s.stop_code and q in s.stop_code.lower()) or q in s.stop_id.lower()
            ]
        else:
            filtered = all_stops

        total = len(filtered)
        start = (page - 1) * page_size
        end = start + page_size
        return filtered[start:end], total

    def find_nearby_stops(
        self,
        lat: float,
        lon: float,
        radius_meters: float,
        limit: int = 50,
    ) -> List[Tuple[Stop, float]]:
        """Find stops within radius_meters using bounding box pre-filter + Haversine.
        
        Returns sorted list of (Stop, straight_line_distance_meters).
        """
        if not self._stops_by_id:
            return []

        min_lat, min_lon, max_lat, max_lon = bbox_for_radius(lat, lon, radius_meters)
        candidates: List[Tuple[Stop, float]] = []

        for stop in self._stops_by_id.values():
            if min_lat <= stop.stop_lat <= max_lat and min_lon <= stop.stop_lon <= max_lon:
                dist = haversine_meters(lat, lon, stop.stop_lat, stop.stop_lon)
                if dist <= radius_meters:
                    candidates.append((stop, round(dist, 1)))

        candidates.sort(key=lambda x: x[1])
        return candidates[:limit]

    def get_route(self, route_id: str) -> Optional[Route]:
        return self._routes_by_id.get(route_id)

    def get_trip(self, trip_id: str) -> Optional[Trip]:
        return self._trips_by_id.get(trip_id)

    def get_trip_stop_times(self, trip_id: str) -> List[StopTime]:
        if not self.dataset:
            return []
        return self.dataset.stop_times.get(trip_id, [])

    def get_stop_departures(self, stop_id: str) -> List[Tuple[str, int, int]]:
        return self._stop_departures.get(stop_id, [])

