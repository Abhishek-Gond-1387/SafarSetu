"""GTFS data models — normalized internal representation of GTFS records."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from enum import IntEnum
from typing import Dict, List, Optional, Set


class RouteType(IntEnum):
    """GTFS route_type values."""
    TRAM = 0
    METRO = 1
    RAIL = 2
    BUS = 3
    FERRY = 4
    CABLE_TRAM = 5
    AERIAL_LIFT = 6
    FUNICULAR = 7
    TROLLEYBUS = 11
    MONORAIL = 12


class LocationType(IntEnum):
    """GTFS location_type values."""
    STOP = 0
    STATION = 1
    ENTRANCE_EXIT = 2
    GENERIC_NODE = 3
    BOARDING_AREA = 4


class TransferType(IntEnum):
    """GTFS transfer_type values."""
    RECOMMENDED = 0
    TIMED = 1
    MIN_TIME_REQUIRED = 2
    NOT_POSSIBLE = 3


class ExceptionType(IntEnum):
    """GTFS calendar_dates exception_type values."""
    SERVICE_ADDED = 1
    SERVICE_REMOVED = 2


class PickupDropoffType(IntEnum):
    """GTFS pickup/drop-off type values."""
    REGULARLY_SCHEDULED = 0
    NO_SERVICE = 1
    PHONE_AGENCY = 2
    COORDINATE_WITH_DRIVER = 3


@dataclass
class FeedInfo:
    """Parsed GTFS feed_info.txt record."""
    feed_publisher_name: str
    feed_publisher_url: str
    feed_lang: str
    feed_version: Optional[str] = None
    feed_start_date: Optional[date] = None
    feed_end_date: Optional[date] = None
    feed_contact_email: Optional[str] = None
    feed_contact_url: Optional[str] = None
    source_id: str = ""          # e.g. "mdb-1262"
    source_url: str = ""
    downloaded_at: Optional[datetime] = None
    sha256: Optional[str] = None


@dataclass
class Agency:
    """GTFS agency.txt record."""
    agency_id: str
    agency_name: str
    agency_url: str
    agency_timezone: str
    agency_lang: Optional[str] = None
    agency_phone: Optional[str] = None
    agency_fare_url: Optional[str] = None
    agency_email: Optional[str] = None


@dataclass
class Stop:
    """GTFS stops.txt record."""
    stop_id: str
    stop_name: str
    stop_lat: float
    stop_lon: float
    stop_code: Optional[str] = None
    stop_desc: Optional[str] = None
    zone_id: Optional[str] = None
    stop_url: Optional[str] = None
    location_type: LocationType = LocationType.STOP
    parent_station: Optional[str] = None
    stop_timezone: Optional[str] = None
    wheelchair_boarding: int = 0
    platform_code: Optional[str] = None
    # Non-GTFS: source provenance
    source_id: str = ""


@dataclass
class Route:
    """GTFS routes.txt record."""
    route_id: str
    route_type: RouteType
    agency_id: Optional[str] = None
    route_short_name: Optional[str] = None
    route_long_name: Optional[str] = None
    route_desc: Optional[str] = None
    route_url: Optional[str] = None
    route_color: Optional[str] = None
    route_text_color: Optional[str] = None
    route_sort_order: Optional[int] = None
    source_id: str = ""


@dataclass
class CalendarService:
    """GTFS calendar.txt record — days of week + date range."""
    service_id: str
    monday: bool
    tuesday: bool
    wednesday: bool
    thursday: bool
    friday: bool
    saturday: bool
    sunday: bool
    start_date: date
    end_date: date

    def operates_on(self, d: date) -> bool:
        """Return True if service operates on date d (ignores exceptions)."""
        if not (self.start_date <= d <= self.end_date):
            return False
        weekday = d.weekday()  # 0=Mon … 6=Sun
        flags = [self.monday, self.tuesday, self.wednesday,
                 self.thursday, self.friday, self.saturday, self.sunday]
        return flags[weekday]


@dataclass
class CalendarDate:
    """GTFS calendar_dates.txt record."""
    service_id: str
    date: date
    exception_type: ExceptionType


@dataclass
class Trip:
    """GTFS trips.txt record."""
    trip_id: str
    route_id: str
    service_id: str
    trip_headsign: Optional[str] = None
    trip_short_name: Optional[str] = None
    direction_id: Optional[int] = None
    block_id: Optional[str] = None
    shape_id: Optional[str] = None
    wheelchair_accessible: int = 0
    bikes_allowed: int = 0
    source_id: str = ""


@dataclass
class StopTime:
    """GTFS stop_times.txt record.

    Arrival/departure are stored as total seconds from midnight so that
    times beyond 24:00 (e.g. 25:30:00) are handled correctly.
    """
    trip_id: str
    stop_id: str
    stop_sequence: int
    arrival_seconds: Optional[int]    # None = not specified
    departure_seconds: Optional[int]  # None = not specified
    stop_headsign: Optional[str] = None
    pickup_type: PickupDropoffType = PickupDropoffType.REGULARLY_SCHEDULED
    drop_off_type: PickupDropoffType = PickupDropoffType.REGULARLY_SCHEDULED
    shape_dist_traveled: Optional[float] = None
    timepoint: Optional[int] = None

    @staticmethod
    def parse_time(s: str) -> Optional[int]:
        """Parse 'HH:MM:SS' (24:00+ allowed) to seconds since midnight.

        Returns None if the string is empty or unparseable.
        """
        if not s or not s.strip():
            return None
        s = s.strip()
        parts = s.split(":")
        if len(parts) != 3:
            return None
        try:
            h, m, sec = int(parts[0]), int(parts[1]), int(parts[2])
            return h * 3600 + m * 60 + sec
        except ValueError:
            return None

    @property
    def arrival_time_str(self) -> str:
        if self.arrival_seconds is None:
            return ""
        h, rem = divmod(self.arrival_seconds, 3600)
        m, s = divmod(rem, 60)
        return f"{h:02d}:{m:02d}:{s:02d}"

    @property
    def departure_time_str(self) -> str:
        if self.departure_seconds is None:
            return ""
        h, rem = divmod(self.departure_seconds, 3600)
        m, s = divmod(rem, 60)
        return f"{h:02d}:{m:02d}:{s:02d}"


@dataclass
class Shape:
    """A single shape point from GTFS shapes.txt."""
    shape_id: str
    shape_pt_lat: float
    shape_pt_lon: float
    shape_pt_sequence: int
    shape_dist_traveled: Optional[float] = None


@dataclass
class Transfer:
    """GTFS transfers.txt record."""
    from_stop_id: str
    to_stop_id: str
    transfer_type: TransferType = TransferType.RECOMMENDED
    min_transfer_time: Optional[int] = None  # seconds


@dataclass
class FareAttribute:
    """GTFS fare_attributes.txt record."""
    fare_id: str
    price: float
    currency_type: str
    payment_method: int
    transfers: Optional[int]  # None = unlimited
    agency_id: Optional[str] = None
    transfer_duration: Optional[int] = None  # seconds


@dataclass
class FareRule:
    """GTFS fare_rules.txt record."""
    fare_id: str
    route_id: Optional[str] = None
    origin_id: Optional[str] = None
    destination_id: Optional[str] = None
    contains_id: Optional[str] = None


@dataclass
class GTFSDataset:
    """Complete parsed and validated GTFS dataset."""
    feed_info: Optional[FeedInfo]
    agencies: Dict[str, Agency]                   # agency_id -> Agency
    stops: Dict[str, Stop]                        # stop_id   -> Stop
    routes: Dict[str, Route]                      # route_id  -> Route
    trips: Dict[str, Trip]                        # trip_id   -> Trip
    stop_times: Dict[str, List[StopTime]]         # trip_id   -> sorted StopTimes
    calendar: Dict[str, CalendarService]          # service_id-> CalendarService
    calendar_dates: Dict[str, List[CalendarDate]] # service_id-> [CalendarDate]
    shapes: Dict[str, List[Shape]]                # shape_id  -> [Shape]
    transfers: List[Transfer]
    fare_attributes: Dict[str, FareAttribute]     # fare_id   -> FareAttribute
    fare_rules: List[FareRule]
    validation_errors: List[str] = field(default_factory=list)
    validation_warnings: List[str] = field(default_factory=list)
    source_id: str = ""

    @property
    def is_empty(self) -> bool:
        return not self.stops

    @property
    def has_fare_data(self) -> bool:
        return bool(self.fare_attributes)

    def service_active_on(self, service_id: str, d: date) -> bool:
        """Return True if a service runs on the given date."""
        cal = self.calendar.get(service_id)
        base_active = cal.operates_on(d) if cal else False

        # Apply calendar_date exceptions
        for cd in self.calendar_dates.get(service_id, []):
            if cd.date == d:
                if cd.exception_type == ExceptionType.SERVICE_ADDED:
                    return True
                elif cd.exception_type == ExceptionType.SERVICE_REMOVED:
                    return False

        return base_active

    def merge(self, other: GTFSDataset, prefix: str = "metro_") -> None:
        """Merge another GTFSDataset (e.g. DMRC) into this dataset with prefixed IDs to prevent collisions."""
        self.agencies.update(other.agencies)

        # Merge Stops
        for sid, s in other.stops.items():
            new_sid = f"{prefix}{sid}"
            clean_name = s.stop_name if "metro" in s.stop_name.lower() else f"{s.stop_name} (Metro Station)"
            self.stops[new_sid] = Stop(
                stop_id=new_sid,
                stop_name=clean_name,
                stop_lat=s.stop_lat,
                stop_lon=s.stop_lon,
                stop_code=s.stop_code,
                stop_desc=s.stop_desc or "Delhi Metro Station (DMRC)",
                location_type=s.location_type,
                parent_station=f"{prefix}{s.parent_station}" if s.parent_station else None,
                source_id=other.source_id or "dmrc",
            )

        # Helper for friendly Metro Line names
        def format_metro_route_name(long_name: str, short_name: str) -> tuple[str, str, str]:
            lname_up = (long_name or "").upper()
            if "YELLOW" in lname_up:
                return "Yellow Line", long_name, "#eab308"
            elif "BLUE" in lname_up:
                return "Blue Line", long_name, "#2563eb"
            elif "RED" in lname_up:
                return "Red Line", long_name, "#dc2626"
            elif "GREEN" in lname_up:
                return "Green Line", long_name, "#16a34a"
            elif "VIOLET" in lname_up:
                return "Violet Line", long_name, "#7c3aed"
            elif "PINK" in lname_up:
                return "Pink Line", long_name, "#ec4899"
            elif "MAGENTA" in lname_up:
                return "Magenta Line", long_name, "#d946ef"
            elif "AIRPORT" in lname_up or "ORANGE" in lname_up:
                return "Airport Express", long_name, "#ea580c"
            elif "GRAY" in lname_up or "GREY" in lname_up:
                return "Grey Line", long_name, "#64748b"
            elif "RAPID" in lname_up:
                return "Rapid Metro", long_name, "#06b6d4"
            elif "AQUA" in lname_up:
                return "Aqua Line", long_name, "#0284c7"
            return short_name or "Metro", long_name, "#0f766e"

        # Merge Routes
        for rid, r in other.routes.items():
            new_rid = f"{prefix}{rid}"
            r_short, r_long, r_color = format_metro_route_name(r.route_long_name or "", r.route_short_name or "")
            self.routes[new_rid] = Route(
                route_id=new_rid,
                route_type=RouteType.METRO,
                agency_id=r.agency_id or "DMRC",
                route_short_name=r_short,
                route_long_name=r_long,
                route_desc=r.route_desc or "Delhi Metro Rail Network",
                route_color=r_color,
                route_text_color="#ffffff" if r_color != "#eab308" else "#000000",
                source_id=other.source_id or "dmrc",
            )

        # Merge Calendar
        for cid, c in other.calendar.items():
            new_cid = f"{prefix}{cid}"
            # Delhi Metro operates daily across all 11 corridors; DMRC static GTFS timetable trips
            # are indexed under 'weekday' (5,379 trips) while weekend schedules share the same corridor headway.
            # Enable 7-day operation for DMRC services so weekend journeys route properly.
            is_dmrc_weekday = "weekday" in cid.lower()
            self.calendar[new_cid] = CalendarService(
                service_id=new_cid,
                monday=c.monday or is_dmrc_weekday,
                tuesday=c.tuesday or is_dmrc_weekday,
                wednesday=c.wednesday or is_dmrc_weekday,
                thursday=c.thursday or is_dmrc_weekday,
                friday=c.friday or is_dmrc_weekday,
                saturday=True if is_dmrc_weekday else c.saturday,
                sunday=True if is_dmrc_weekday else c.sunday,
                start_date=c.start_date,
                end_date=c.end_date,
            )

        # Merge Calendar Dates
        for cid, cd_list in other.calendar_dates.items():
            new_cid = f"{prefix}{cid}"
            self.calendar_dates[new_cid] = [
                CalendarDate(service_id=new_cid, date=cd.date, exception_type=cd.exception_type)
                for cd in cd_list
            ]

        # Merge Trips
        for tid, t in other.trips.items():
            new_tid = f"{prefix}{tid}"
            new_rid = f"{prefix}{t.route_id}"
            new_cid = f"{prefix}{t.service_id}"
            self.trips[new_tid] = Trip(
                trip_id=new_tid,
                route_id=new_rid,
                service_id=new_cid,
                trip_headsign=t.trip_headsign,
                trip_short_name=t.trip_short_name,
                direction_id=t.direction_id,
                shape_id=f"{prefix}{t.shape_id}" if t.shape_id else None,
                source_id=other.source_id or "dmrc",
            )

        # Merge StopTimes
        for tid, st_list in other.stop_times.items():
            new_tid = f"{prefix}{tid}"
            self.stop_times[new_tid] = [
                StopTime(
                    trip_id=new_tid,
                    stop_id=f"{prefix}{st.stop_id}",
                    stop_sequence=st.stop_sequence,
                    arrival_seconds=st.arrival_seconds,
                    departure_seconds=st.departure_seconds,
                    stop_headsign=st.stop_headsign,
                    pickup_type=st.pickup_type,
                    drop_off_type=st.drop_off_type,
                )
                for st in st_list
            ]

