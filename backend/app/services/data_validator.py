"""GTFS data validation service.

Enforces structural, relational, and domain rules on GTFS datasets
without silently discarding or fabricating transit records.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass, field
from datetime import date, datetime
import os
from typing import Dict, List, Optional, Set, Tuple

from app.models.transit import StopTime
from app.utils.geo import is_valid_delhi_ncr_coord


@dataclass
class ValidationReport:
    """Detailed results of a GTFS validation run."""
    source_id: str
    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    counts: Dict[str, int] = field(default_factory=dict)
    feed_start_date: Optional[date] = None
    feed_end_date: Optional[date] = None
    is_expired: bool = False
    validation_time_utc: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")


class GTFSValidator:
    """Validates raw GTFS CSV files in a directory."""

    REQUIRED_FILES = [
        "agency.txt",
        "stops.txt",
        "routes.txt",
        "trips.txt",
        "stop_times.txt",
    ]

    REQUIRED_STOP_COLS = {"stop_id", "stop_name", "stop_lat", "stop_lon"}
    REQUIRED_ROUTE_COLS = {"route_id", "route_type"}
    REQUIRED_TRIP_COLS = {"trip_id", "route_id", "service_id"}
    REQUIRED_STOP_TIME_COLS = {"trip_id", "stop_id", "stop_sequence", "arrival_time", "departure_time"}

    @classmethod
    def validate_directory(cls, dir_path: str, source_id: str = "gtfs") -> ValidationReport:
        errors: List[str] = []
        warnings: List[str] = []
        counts: Dict[str, int] = {}
        feed_start: Optional[date] = None
        feed_end: Optional[date] = None

        if not os.path.isdir(dir_path):
            return ValidationReport(
                source_id=source_id,
                is_valid=False,
                errors=[f"Directory does not exist: {dir_path}"],
            )

        # 1. Check required files
        existing_files = os.listdir(dir_path)
        for req in cls.REQUIRED_FILES:
            if req not in existing_files:
                errors.append(f"Missing required GTFS file: {req}")

        if "calendar.txt" not in existing_files and "calendar_dates.txt" not in existing_files:
            errors.append("At least one of calendar.txt or calendar_dates.txt must be provided")

        if errors:
            return ValidationReport(source_id=source_id, is_valid=False, errors=errors)

        # 2. Validate Stops
        stop_ids: Set[str] = set()
        stops_file = os.path.join(dir_path, "stops.txt")
        out_of_ncr_count = 0
        with open(stops_file, mode="r", encoding="utf-8-sig", errors="replace") as f:
            reader = csv.DictReader(f)
            missing_cols = cls.REQUIRED_STOP_COLS - set(reader.fieldnames or [])
            if missing_cols:
                errors.append(f"stops.txt missing columns: {missing_cols}")
            else:
                for row_idx, row in enumerate(reader, start=2):
                    sid = row.get("stop_id", "").strip()
                    if not sid:
                        errors.append(f"stops.txt line {row_idx}: empty stop_id")
                        continue
                    if sid in stop_ids:
                        warnings.append(f"stops.txt line {row_idx}: duplicate stop_id '{sid}'")
                    stop_ids.add(sid)

                    try:
                        lat = float(row.get("stop_lat", 0))
                        lon = float(row.get("stop_lon", 0))
                        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                            errors.append(f"stops.txt line {row_idx}: invalid lat/lon ({lat}, {lon})")
                        elif not is_valid_delhi_ncr_coord(lat, lon):
                            out_of_ncr_count += 1
                    except ValueError:
                        errors.append(f"stops.txt line {row_idx}: non-numeric lat/lon")
        
        counts["stops"] = len(stop_ids)
        if out_of_ncr_count > 0:
            warnings.append(f"{out_of_ncr_count} stops lie outside standard Delhi/NCR bounding box")

        # 3. Validate Routes
        route_ids: Set[str] = set()
        routes_file = os.path.join(dir_path, "routes.txt")
        with open(routes_file, mode="r", encoding="utf-8-sig", errors="replace") as f:
            reader = csv.DictReader(f)
            missing_cols = cls.REQUIRED_ROUTE_COLS - set(reader.fieldnames or [])
            if missing_cols:
                errors.append(f"routes.txt missing columns: {missing_cols}")
            else:
                for row_idx, row in enumerate(reader, start=2):
                    rid = row.get("route_id", "").strip()
                    if not rid:
                        errors.append(f"routes.txt line {row_idx}: empty route_id")
                        continue
                    if rid in route_ids:
                        warnings.append(f"routes.txt line {row_idx}: duplicate route_id '{rid}'")
                    route_ids.add(rid)
        counts["routes"] = len(route_ids)

        # 4. Validate Calendar & Calendar Dates
        service_ids: Set[str] = set()
        calendar_file = os.path.join(dir_path, "calendar.txt")
        if os.path.exists(calendar_file):
            with open(calendar_file, mode="r", encoding="utf-8-sig", errors="replace") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    sid = row.get("service_id", "").strip()
                    if sid:
                        service_ids.add(sid)
                    s_str = row.get("start_date", "").strip()
                    e_str = row.get("end_date", "").strip()
                    try:
                        if len(s_str) == 8:
                            sd = date(int(s_str[:4]), int(s_str[4:6]), int(s_str[6:8]))
                            if feed_start is None or sd < feed_start:
                                feed_start = sd
                        if len(e_str) == 8:
                            ed = date(int(e_str[:4]), int(e_str[4:6]), int(e_str[6:8]))
                            if feed_end is None or ed > feed_end:
                                feed_end = ed
                    except ValueError:
                        pass

        cal_dates_file = os.path.join(dir_path, "calendar_dates.txt")
        cal_dates_count = 0
        if os.path.exists(cal_dates_file):
            with open(cal_dates_file, mode="r", encoding="utf-8-sig", errors="replace") as f:
                reader = csv.DictReader(f)
                for row_idx, row in enumerate(reader, start=2):
                    sid = row.get("service_id", "").strip()
                    if sid:
                        service_ids.add(sid)
                    d_str = row.get("date", "").strip()
                    ex_type = row.get("exception_type", "").strip()
                    if ex_type not in ("1", "2"):
                        warnings.append(f"calendar_dates.txt line {row_idx}: invalid exception_type '{ex_type}'")
                    try:
                        if len(d_str) == 8:
                            cd = date(int(d_str[:4]), int(d_str[4:6]), int(d_str[6:8]))
                            if feed_start is None or cd < feed_start:
                                feed_start = cd
                            if feed_end is None or cd > feed_end:
                                feed_end = cd
                    except ValueError:
                        warnings.append(f"calendar_dates.txt line {row_idx}: invalid date format '{d_str}'")
                    cal_dates_count += 1

        counts["services"] = len(service_ids)
        counts["calendar_dates"] = cal_dates_count

        # 5. Validate Trips & Route Foreign Keys
        trip_ids: Set[str] = set()
        trips_file = os.path.join(dir_path, "trips.txt")
        broken_route_refs = 0
        broken_service_refs = 0
        with open(trips_file, mode="r", encoding="utf-8-sig", errors="replace") as f:
            reader = csv.DictReader(f)
            missing_cols = cls.REQUIRED_TRIP_COLS - set(reader.fieldnames or [])
            if missing_cols:
                errors.append(f"trips.txt missing columns: {missing_cols}")
            else:
                for row_idx, row in enumerate(reader, start=2):
                    tid = row.get("trip_id", "").strip()
                    rid = row.get("route_id", "").strip()
                    sid = row.get("service_id", "").strip()
                    if not tid:
                        continue
                    if tid in trip_ids:
                        warnings.append(f"trips.txt line {row_idx}: duplicate trip_id '{tid}'")
                    trip_ids.add(tid)

                    if rid and rid not in route_ids:
                        broken_route_refs += 1
                    if sid and service_ids and sid not in service_ids:
                        broken_service_refs += 1

        counts["trips"] = len(trip_ids)
        if broken_route_refs > 0:
            errors.append(f"trips.txt contains {broken_route_refs} references to nonexistent route_id")
        if broken_service_refs > 0:
            warnings.append(f"trips.txt contains {broken_service_refs} references to service_id not in calendar files")

        # 6. Validate Stop Times (Foreign Keys, Monotonicity, and Times)
        st_file = os.path.join(dir_path, "stop_times.txt")
        broken_st_trip_refs = 0
        broken_st_stop_refs = 0
        sequence_errors = 0
        time_monotonic_errors = 0
        overnight_times_count = 0
        total_st_rows = 0

        # Track previous stop_sequence and departure_seconds per trip: trip_id -> (last_seq, last_dep_sec)
        trip_last_st: Dict[str, Tuple[int, Optional[int]]] = {}

        with open(st_file, mode="r", encoding="utf-8-sig", errors="replace") as f:
            reader = csv.DictReader(f)
            missing_cols = cls.REQUIRED_STOP_TIME_COLS - set(reader.fieldnames or [])
            if missing_cols:
                errors.append(f"stop_times.txt missing columns: {missing_cols}")
            else:
                for row_idx, row in enumerate(reader, start=2):
                    total_st_rows += 1
                    tid = row.get("trip_id", "").strip()
                    sid = row.get("stop_id", "").strip()
                    seq_str = row.get("stop_sequence", "").strip()
                    arr_str = row.get("arrival_time", "").strip()
                    dep_str = row.get("departure_time", "").strip()

                    if tid not in trip_ids:
                        broken_st_trip_refs += 1
                    if sid not in stop_ids:
                        broken_st_stop_refs += 1

                    try:
                        seq = int(seq_str)
                    except ValueError:
                        sequence_errors += 1
                        seq = -1

                    arr_sec = StopTime.parse_time(arr_str)
                    dep_sec = StopTime.parse_time(dep_str)

                    # Track 24:00+ overnight times
                    if (arr_sec is not None and arr_sec >= 86400) or (dep_sec is not None and dep_sec >= 86400):
                        overnight_times_count += 1

                    # Check dwell time validity: arrival <= departure
                    if arr_sec is not None and dep_sec is not None and dep_sec < arr_sec:
                        time_monotonic_errors += 1

                    # Check trip sequence monotonicity: strictly increasing sequences
                    if tid in trip_last_st:
                        prev_seq, prev_dep = trip_last_st[tid]
                        if seq <= prev_seq:
                            sequence_errors += 1
                        # Check travel time monotonicity across stops: dep_prev <= arr_curr
                        if prev_dep is not None and arr_sec is not None and arr_sec < prev_dep:
                            time_monotonic_errors += 1

                    trip_last_st[tid] = (seq, dep_sec if dep_sec is not None else arr_sec)

        counts["stop_times"] = total_st_rows
        counts["overnight_stop_times"] = overnight_times_count

        if broken_st_trip_refs > 0:
            errors.append(f"stop_times.txt contains {broken_st_trip_refs} references to nonexistent trip_id")
        if broken_st_stop_refs > 0:
            errors.append(f"stop_times.txt contains {broken_st_stop_refs} references to nonexistent stop_id")
        if sequence_errors > 0:
            warnings.append(f"stop_times.txt contains {sequence_errors} non-monotonic or malformed stop_sequence values")
        if time_monotonic_errors > 0:
            warnings.append(f"stop_times.txt contains {time_monotonic_errors} negative dwell times or backwards travel times")

        # 7. Validate Transfers if present
        transfers_file = os.path.join(dir_path, "transfers.txt")
        if os.path.exists(transfers_file):
            broken_transfers = 0
            with open(transfers_file, mode="r", encoding="utf-8-sig", errors="replace") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    f_id = row.get("from_stop_id", "").strip()
                    t_id = row.get("to_stop_id", "").strip()
                    if f_id not in stop_ids or t_id not in stop_ids:
                        broken_transfers += 1
            if broken_transfers > 0:
                warnings.append(f"transfers.txt contains {broken_transfers} references to nonexistent stop IDs")

        # 8. Check Expiry
        today = date.today()
        is_expired = False
        if feed_end and feed_end < today:
            is_expired = True
            warnings.append(
                f"GTFS feed expired on {feed_end.isoformat()}. Current date is {today.isoformat()}. "
                "Schedules are historical and must be treated as stale."
            )

        return ValidationReport(
            source_id=source_id,
            is_valid=(len(errors) == 0),
            errors=errors,
            warnings=warnings,
            counts=counts,
            feed_start_date=feed_start,
            feed_end_date=feed_end,
            is_expired=is_expired,
        )
