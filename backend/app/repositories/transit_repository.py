"""Transit data repository with in-memory spatial and relational indexing."""
from __future__ import annotations

import math
from typing import Callable, Dict, List, Optional, Tuple

from app.models.transit import GTFSDataset, Route, Stop, StopTime, Trip
from app.utils.geo import bbox_for_radius, haversine_meters


DELHI_LANDMARK_ALIASES: Dict[str, List[str]] = {
    "mait": ["rohini sec 22", "aggarsain", "rohini sec 22 terminal", "begum pur", "rithala"],
    "maharaja agrasen": ["rohini sec 22", "aggarsain", "rohini sec 22 terminal"],
    "du": ["vishwavidyalaya", "delhi university", "patel chest", "chhatra marg", "gtb nagar", "south campus"],
    "delhi university": ["vishwavidyalaya", "delhi university", "patel chest", "chhatra marg", "south campus"],
    "north campus": ["vishwavidyalaya", "gtb nagar", "delhi university"],
    "south campus": ["durgabai deshmukh", "south campus", "moti bagh", "benito juarez"],
    "red fort": ["red fort", "lal quila", "lal qila", "jama masjid", "chandni chowk"],
    "redfort": ["red fort", "lal quila", "lal qila", "jama masjid"],
    "lal quila": ["lal quila", "red fort"],
    "lal qila": ["lal quila", "red fort"],
    "india gate": ["central secretariat", "national stadium", "khan market", "baroda house", "pragati maidan"],
    "cp": ["rajiv chowk", "connaught place", "barakhamba", "shivaji stadium", "janpath"],
    "connaught place": ["rajiv chowk", "connaught place", "barakhamba", "shivaji stadium", "janpath"],
    "iit": ["iit", "hauz khas", "panchsheel"],
    "iit delhi": ["iit", "hauz khas"],
    "dtu": ["shahbad daulatpur", "samaypur badli", "rohini sector 18", "delhi technological"],
    "dce": ["shahbad daulatpur", "samaypur badli", "delhi technological"],
    "nsut": ["dwarka mor", "dwarka sector 3", "netaji subhash"],
    "nsit": ["dwarka mor", "dwarka sector 3", "netaji subhash"],
    "jnu": ["munirka", "ber sarai", "vasant kunj"],
    "aiims": ["aiims", "safdarjung hospital", "dilli haat inat"],
    "safdarjung": ["safdarjung", "aiims"],
    "lotus temple": ["kalkaji mandir", "nehru place"],
    "akshardham": ["akshardham", "mayur vihar"],
    "qutub minar": ["qutab minar", "saket"],
    "qutab minar": ["qutab minar", "saket"],
    "bangla sahib": ["shivaji stadium", "patel chowk", "gurudwara bangla sahib"],
    "cyber city": ["cyber city", "sikanderpur", "indusind bank cyber city"],
    "igi airport": ["igi airport", "t3", "delhi aerocity"],
    "airport": ["igi airport", "t3", "delhi aerocity"],
    "t3": ["igi airport", "t3"],
    "terminal 3": ["igi airport", "t3"],
    "isbt kashmere gate": ["kashmere gate", "isbt kashmere gate"],
    "kashmere gate": ["kashmere gate", "isbt kashmere gate"],
    "anand vihar": ["anand vihar", "anand vihar isbt"],
    "ndls": ["new delhi", "new delhi railway station"],
    "new delhi railway": ["new delhi", "new delhi railway station"],
    "old delhi railway": ["chandni chowk", "old delhi railway station"],
    "dli": ["chandni chowk", "old delhi railway station"],
    "nizamuddin": ["sarai kale khan", "nizamuddin railway station"],
    "nzm": ["sarai kale khan", "nizamuddin railway station"],
    "sarojini nagar": ["sarojini nagar"],
    "lajpat nagar": ["lajpat nagar"],
    "hauz khas": ["hauz khas"],
    "saket": ["saket", "malviya nagar"],
    "nehru place": ["nehru place", "kalkaji"],
    "chandni chowk": ["chandni chowk", "lal quila"],
    "karol bagh": ["karol bagh", "jhandewalan"],
    "dwarka": ["dwarka sector", "dwarka mor"],
    "rohini": ["rohini", "rithala"],
    "noida": ["noida sector", "botanical garden"],
    "gurgaon": ["millennium city", "huda city", "iffco chowk", "cyber city", "sikanderpur"],
    "gurugram": ["millennium city", "huda city", "iffco chowk", "cyber city", "sikanderpur"],
}


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
        if not query or not query.strip():
            total = len(all_stops)
            start = (page - 1) * page_size
            return all_stops[start:start + page_size], total

        q = query.strip().lower()

        # Gather alias expansions for landmarks, colleges, and popular acronyms
        alias_terms: List[str] = []
        for alias_key, expansions in DELHI_LANDMARK_ALIASES.items():
            if q == alias_key or q in alias_key or alias_key in q:
                alias_terms.extend(expansions)

        alias_terms = list(dict.fromkeys(alias_terms))

        is_short = len(q) <= 3

        scored: List[Tuple[int, Stop]] = []
        for s in all_stops:
            name_lower = s.stop_name.lower()
            code_lower = (s.stop_code or "").lower()
            id_lower = s.stop_id.lower()

            score = 0
            words = name_lower.replace("(", " ").replace(")", " ").replace("/", " ").replace("-", " ").split()
            
            # 1. Exact or word-boundary match with query
            if q == name_lower:
                score = 100
            elif q in words:
                score = 98
            elif name_lower.startswith(q):
                score = 92

            # 2. Check landmark alias terms (explicit landmark intent like MAIT, DU, Red Fort, CP)
            for term in alias_terms:
                if term == name_lower:
                    score = max(score, 95)
                elif name_lower.startswith(term):
                    score = max(score, 91)
                elif term in words:
                    score = max(score, 89)
                elif term in name_lower:
                    score = max(score, 86)

            # 3. Substring match fallback
            if score == 0:
                if not is_short and (q in name_lower or (code_lower and q in code_lower) or q in id_lower):
                    score = 70
                elif is_short and (code_lower and q == code_lower):
                    score = 85
                elif is_short and (any(w.startswith(q) for w in words)):
                    score = 65

            if score > 0:
                scored.append((score, s))

        # Sort by relevance score descending, then prioritize metro stations for rail queries
        scored.sort(key=lambda x: (x[0], x[1].stop_id.startswith("metro_")), reverse=True)
        filtered = [s for _, s in scored]

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
        filter_fn: Optional[Callable[[Stop], bool]] = None,
    ) -> List[Tuple[Stop, float]]:
        """Find stops within radius_meters using bounding box pre-filter + Haversine.
        
        Returns sorted list of (Stop, straight_line_distance_meters).
        """
        if not self._stops_by_id:
            return []

        min_lat, min_lon, max_lat, max_lon = bbox_for_radius(lat, lon, radius_meters)
        candidates: List[Tuple[Stop, float]] = []

        for stop in self._stops_by_id.values():
            if filter_fn is not None and not filter_fn(stop):
                continue
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

