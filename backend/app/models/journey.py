"""Journey leg and route data models."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Optional


class LegMode(str, Enum):
    BUS = "bus"
    METRO = "metro"
    RAIL = "rail"
    WALK = "walk"
    TRAM = "tram"
    FERRY = "ferry"
    UNKNOWN = "unknown"


class RouteRankCriterion(str, Enum):
    FASTEST = "fastest"
    CHEAPEST = "cheapest"
    BALANCED = "balanced"


@dataclass
class JourneyLeg:
    """A single contiguous leg of a journey on one route/mode or on foot."""
    mode: LegMode
    from_stop_id: str
    to_stop_id: str
    from_stop_name: str
    to_stop_name: str
    departure_seconds: int      # seconds since midnight
    arrival_seconds: int        # seconds since midnight
    duration_seconds: int       # arrival - departure
    # Transit-specific (None for walk legs)
    route_id: Optional[str] = None
    route_short_name: Optional[str] = None
    route_long_name: Optional[str] = None
    trip_id: Optional[str] = None
    headsign: Optional[str] = None
    intermediate_stops: List[str] = field(default_factory=list)
    # Walk-specific
    distance_meters: Optional[float] = None      # straight-line, not routed
    walk_distance_type: str = "straight_line"    # always label distance type
    # Fare
    fare_inr: Optional[float] = None             # None = not determinable
    fare_currency: Optional[str] = None
    # Provenance
    source_id: str = ""                          # e.g. "mdb-1262"

    @property
    def departure_time_str(self) -> str:
        h, rem = divmod(self.departure_seconds, 3600)
        m, s = divmod(rem, 60)
        return f"{h:02d}:{m:02d}:{s:02d}"

    @property
    def arrival_time_str(self) -> str:
        h, rem = divmod(self.arrival_seconds, 3600)
        m, s = divmod(rem, 60)
        return f"{h:02d}:{m:02d}:{s:02d}"


@dataclass
class Journey:
    """A complete point-to-point journey composed of ordered legs."""
    legs: List[JourneyLeg]
    total_duration_seconds: int
    total_walk_meters: float
    num_transfers: int
    total_fare_inr: Optional[float]   # None if any leg has unknown fare
    fare_complete: bool               # True only if all legs have known fares
    rank_criterion: RouteRankCriterion
    # Data quality
    feed_expired: bool = False
    provenance_sources: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    @property
    def departure_time_str(self) -> str:
        if not self.legs:
            return "N/A"
        return self.legs[0].departure_time_str

    @property
    def arrival_time_str(self) -> str:
        if not self.legs:
            return "N/A"
        return self.legs[-1].arrival_time_str

    @property
    def summary(self) -> str:
        modes = "+".join(sorted({l.mode.value for l in self.legs if l.mode != LegMode.WALK}))
        mins = self.total_duration_seconds // 60
        fare = f"₹{self.total_fare_inr:.0f}" if self.fare_complete and self.total_fare_inr is not None else "fare unknown"
        return f"{modes or 'walk'} · {mins} min · {fare}"

