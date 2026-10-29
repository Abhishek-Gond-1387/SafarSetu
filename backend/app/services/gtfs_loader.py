"""GTFS data loader.

Parses genuine GTFS records from disk into normalized domain models.
"""
from __future__ import annotations

import csv
from datetime import date
import os
from typing import Dict, List, Optional, Set

from app.models.transit import (
    Agency,
    CalendarDate,
    CalendarService,
    ExceptionType,
    FareAttribute,
    FareRule,
    FeedInfo,
    GTFSDataset,
    LocationType,
    Route,
    RouteType,
    Shape,
    Stop,
    StopTime,
    Transfer,
    TransferType,
    Trip,
)
from app.services.data_validator import GTFSValidator


class GTFSLoader:
    """Loads GTFS text files into in-memory typed models."""

    @classmethod
    def load(
        cls,
        dir_path: str,
        source_id: str = "mdb-1262",
        max_trips: Optional[int] = None,
    ) -> GTFSDataset:
        """Load GTFS files from dir_path.
        
        Args:
            dir_path: Path containing extracted GTFS CSVs.
            source_id: Provenance identifier.
            max_trips: Optional limit on trips loaded for memory optimization.
        """
        val_report = GTFSValidator.validate_directory(dir_path, source_id=source_id)
        if not val_report.is_valid:
            return GTFSDataset(
                feed_info=None,
                agencies={},
                stops={},
                routes={},
                trips={},
                stop_times={},
                calendar={},
                calendar_dates={},
                shapes={},
                transfers=[],
                fare_attributes={},
                fare_rules=[],
                validation_errors=val_report.errors,
                validation_warnings=val_report.warnings,
                source_id=source_id,
            )

        # 1. Agencies
        agencies: Dict[str, Agency] = {}
        agency_file = os.path.join(dir_path, "agency.txt")
        if os.path.exists(agency_file):
            with open(agency_file, "r", encoding="utf-8-sig", errors="replace") as f:
                for row in csv.DictReader(f):
                    aid = row.get("agency_id", "").strip() or "DEFAULT"
                    agencies[aid] = Agency(
                        agency_id=aid,
                        agency_name=row.get("agency_name", "").strip(),
                        agency_url=row.get("agency_url", "").strip(),
                        agency_timezone=row.get("agency_timezone", "Asia/Kolkata").strip(),
                        agency_lang=row.get("agency_lang"),
                        agency_phone=row.get("agency_phone"),
                        agency_fare_url=row.get("agency_fare_url"),
                    )

        # 2. Stops
        stops: Dict[str, Stop] = {}
        stops_file = os.path.join(dir_path, "stops.txt")
        with open(stops_file, "r", encoding="utf-8-sig", errors="replace") as f:
            for row in csv.DictReader(f):
                sid = row.get("stop_id", "").strip()
                if not sid:
                    continue
                try:
                    lat = float(row.get("stop_lat", 0))
                    lon = float(row.get("stop_lon", 0))
                except ValueError:
                    continue
                
                loc_type_raw = row.get("location_type", "0").strip()
                try:
                    loc_type = LocationType(int(loc_type_raw)) if loc_type_raw else LocationType.STOP
                except ValueError:
                    loc_type = LocationType.STOP

                stops[sid] = Stop(
                    stop_id=sid,
                    stop_name=row.get("stop_name", "").strip(),
                    stop_lat=lat,
                    stop_lon=lon,
                    stop_code=row.get("stop_code"),
                    stop_desc=row.get("stop_desc"),
                    zone_id=row.get("zone_id"),
                    location_type=loc_type,
                    parent_station=row.get("parent_station") or None,
                    source_id=source_id,
                )

        # 3. Routes
        routes: Dict[str, Route] = {}
        routes_file = os.path.join(dir_path, "routes.txt")
        with open(routes_file, "r", encoding="utf-8-sig", errors="replace") as f:
            for row in csv.DictReader(f):
                rid = row.get("route_id", "").strip()
                if not rid:
                    continue
                rtype_raw = row.get("route_type", "3").strip()
                try:
                    rtype = RouteType(int(rtype_raw)) if rtype_raw else RouteType.BUS
                except ValueError:
                    rtype = RouteType.BUS

                routes[rid] = Route(
                    route_id=rid,
                    route_type=rtype,
                    agency_id=row.get("agency_id"),
                    route_short_name=row.get("route_short_name"),
                    route_long_name=row.get("route_long_name"),
                    route_desc=row.get("route_desc"),
                    route_color=row.get("route_color"),
                    route_text_color=row.get("route_text_color"),
                    source_id=source_id,
                )

        # 4. Calendar
        calendar: Dict[str, CalendarService] = {}
        cal_file = os.path.join(dir_path, "calendar.txt")
        if os.path.exists(cal_file):
            with open(cal_file, "r", encoding="utf-8-sig", errors="replace") as f:
                for row in csv.DictReader(f):
                    sid = row.get("service_id", "").strip()
                    if not sid:
                        continue
                    try:
                        s_str = row.get("start_date", "").strip()
                        e_str = row.get("end_date", "").strip()
                        sd = date(int(s_str[:4]), int(s_str[4:6]), int(s_str[6:8]))
                        ed = date(int(e_str[:4]), int(e_str[4:6]), int(e_str[6:8]))
                        calendar[sid] = CalendarService(
                            service_id=sid,
                            monday=row.get("monday") == "1",
                            tuesday=row.get("tuesday") == "1",
                            wednesday=row.get("wednesday") == "1",
                            thursday=row.get("thursday") == "1",
                            friday=row.get("friday") == "1",
                            saturday=row.get("saturday") == "1",
                            sunday=row.get("sunday") == "1",
                            start_date=sd,
                            end_date=ed,
                        )
                    except (ValueError, IndexError):
                        continue

        # 4b. Calendar Dates
        calendar_dates: Dict[str, List[CalendarDate]] = {}
        cd_file = os.path.join(dir_path, "calendar_dates.txt")
        if os.path.exists(cd_file):
            with open(cd_file, "r", encoding="utf-8-sig", errors="replace") as f:
                for row in csv.DictReader(f):
                    sid = row.get("service_id", "").strip()
                    d_str = row.get("date", "").strip()
                    ex_type_str = row.get("exception_type", "").strip()
                    if not sid or not d_str or not ex_type_str:
                        continue
                    try:
                        ex_date = date(int(d_str[:4]), int(d_str[4:6]), int(d_str[6:8]))
                        ex_type = ExceptionType(int(ex_type_str))
                        if sid not in calendar_dates:
                            calendar_dates[sid] = []
                        calendar_dates[sid].append(
                            CalendarDate(service_id=sid, date=ex_date, exception_type=ex_type)
                        )
                    except (ValueError, IndexError):
                        continue

        # 5. Trips
        trips: Dict[str, Trip] = {}
        trips_file = os.path.join(dir_path, "trips.txt")
        with open(trips_file, "r", encoding="utf-8-sig", errors="replace") as f:
            for row in csv.DictReader(f):
                tid = row.get("trip_id", "").strip()
                if not tid:
                    continue
                rid = row.get("route_id", "").strip()
                sid = row.get("service_id", "").strip()
                trips[tid] = Trip(
                    trip_id=tid,
                    route_id=rid,
                    service_id=sid,
                    trip_headsign=row.get("trip_headsign"),
                    trip_short_name=row.get("trip_short_name"),
                    direction_id=int(row["direction_id"]) if row.get("direction_id") and row["direction_id"].isdigit() else None,
                    shape_id=row.get("shape_id"),
                    source_id=source_id,
                )
                if max_trips and len(trips) >= max_trips:
                    break

        # 6. Stop Times
        stop_times: Dict[str, List[StopTime]] = {}
        st_file = os.path.join(dir_path, "stop_times.txt")
        with open(st_file, "r", encoding="utf-8-sig", errors="replace") as f:
            for row in csv.DictReader(f):
                tid = row.get("trip_id", "").strip()
                if tid not in trips:
                    continue
                sid = row.get("stop_id", "").strip()
                if sid not in stops:
                    continue
                try:
                    seq = int(row.get("stop_sequence", 0))
                except ValueError:
                    seq = 0
                arr_sec = StopTime.parse_time(row.get("arrival_time", ""))
                dep_sec = StopTime.parse_time(row.get("departure_time", ""))

                st = StopTime(
                    trip_id=tid,
                    stop_id=sid,
                    stop_sequence=seq,
                    arrival_seconds=arr_sec,
                    departure_seconds=dep_sec,
                    stop_headsign=row.get("stop_headsign"),
                )
                if tid not in stop_times:
                    stop_times[tid] = []
                stop_times[tid].append(st)

        # Sort stop_times by sequence
        for tid in stop_times:
            stop_times[tid].sort(key=lambda x: x.stop_sequence)

        # 7. Transfers
        transfers: List[Transfer] = []
        transfers_file = os.path.join(dir_path, "transfers.txt")
        if os.path.exists(transfers_file):
            with open(transfers_file, "r", encoding="utf-8-sig", errors="replace") as f:
                for row in csv.DictReader(f):
                    from_sid = row.get("from_stop_id", "").strip()
                    to_sid = row.get("to_stop_id", "").strip()
                    if not from_sid or not to_sid or from_sid not in stops or to_sid not in stops:
                        continue
                    tt_raw = row.get("transfer_type", "0").strip()
                    try:
                        tt = TransferType(int(tt_raw)) if tt_raw else TransferType.RECOMMENDED
                    except ValueError:
                        tt = TransferType.RECOMMENDED
                    mtt_raw = row.get("min_transfer_time", "").strip()
                    mtt = int(mtt_raw) if mtt_raw and mtt_raw.isdigit() else None
                    transfers.append(
                        Transfer(
                            from_stop_id=from_sid,
                            to_stop_id=to_sid,
                            transfer_type=tt,
                            min_transfer_time=mtt,
                        )
                    )

        # 8. Fare Attributes
        fare_attributes: Dict[str, FareAttribute] = {}
        fa_file = os.path.join(dir_path, "fare_attributes.txt")
        if os.path.exists(fa_file):
            with open(fa_file, "r", encoding="utf-8-sig", errors="replace") as f:
                for row in csv.DictReader(f):
                    fid = row.get("fare_id", "").strip()
                    if not fid:
                        continue
                    try:
                        price = float(row.get("price", 0.0))
                    except ValueError:
                        continue
                    pm_raw = row.get("payment_method", "0").strip()
                    pm = int(pm_raw) if pm_raw and pm_raw.isdigit() else 0
                    tr_raw = row.get("transfers", "").strip()
                    tr = int(tr_raw) if tr_raw and tr_raw.isdigit() else None
                    td_raw = row.get("transfer_duration", "").strip()
                    td = int(td_raw) if td_raw and td_raw.isdigit() else None
                    fare_attributes[fid] = FareAttribute(
                        fare_id=fid,
                        price=price,
                        currency_type=row.get("currency_type", "INR").strip(),
                        payment_method=pm,
                        transfers=tr,
                        agency_id=row.get("agency_id"),
                        transfer_duration=td,
                    )

        # 9. Fare Rules
        fare_rules: List[FareRule] = []
        fr_file = os.path.join(dir_path, "fare_rules.txt")
        if os.path.exists(fr_file):
            with open(fr_file, "r", encoding="utf-8-sig", errors="replace") as f:
                for row in csv.DictReader(f):
                    fid = row.get("fare_id", "").strip()
                    if not fid or fid not in fare_attributes:
                        continue
                    fare_rules.append(
                        FareRule(
                            fare_id=fid,
                            route_id=row.get("route_id"),
                            origin_id=row.get("origin_id"),
                            destination_id=row.get("destination_id"),
                            contains_id=row.get("contains_id"),
                        )
                    )

        # FeedInfo
        feed_info: Optional[FeedInfo] = None
        fi_file = os.path.join(dir_path, "feed_info.txt")
        if os.path.exists(fi_file):
            with open(fi_file, "r", encoding="utf-8-sig", errors="replace") as f:
                for row in csv.DictReader(f):
                    feed_info = FeedInfo(
                        feed_publisher_name=row.get("feed_publisher_name", ""),
                        feed_publisher_url=row.get("feed_publisher_url", ""),
                        feed_lang=row.get("feed_lang", "en"),
                        feed_version=row.get("feed_version"),
                        source_id=source_id,
                    )
                    break
        if not feed_info:
            feed_info = FeedInfo(
                feed_publisher_name="Delhi Integrated Multi-Modal Transit System Ltd. (DIMTS) / DTC",
                feed_publisher_url="https://otd.delhi.gov.in",
                feed_lang="en",
                feed_version="2022-2024",
                feed_start_date=val_report.feed_start_date,
                feed_end_date=val_report.feed_end_date,
                source_id=source_id,
            )

        return GTFSDataset(
            feed_info=feed_info,
            agencies=agencies,
            stops=stops,
            routes=routes,
            trips=trips,
            stop_times=stop_times,
            calendar=calendar,
            calendar_dates=calendar_dates,
            shapes={},
            transfers=transfers,
            fare_attributes=fare_attributes,
            fare_rules=fare_rules,
            validation_errors=val_report.errors,
            validation_warnings=val_report.warnings,
            source_id=source_id,
        )

