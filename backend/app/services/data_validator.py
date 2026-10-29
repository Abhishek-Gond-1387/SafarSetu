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
    REQUIRED_STOP_TIME_COLS = {"trip_id", "stop_id", "stop_sequence"}

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

        # 4. Validate Calendar & Expiry
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
        counts["services"] = len(service_ids)

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
            warnings.append(f"trips.txt contains {broken_service_refs} references to service_id not in calendar.txt")

        # 6. Check Expiry
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

