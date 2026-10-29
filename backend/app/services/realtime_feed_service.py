"""GTFS-Realtime Protocol Buffers feed parser and static GTFS matcher.

Adheres strictly to protobuf field-presence semantics, coordinate validation,
and truthful association with static GTFS records.
"""
from __future__ import annotations

from datetime import datetime, timezone
import math
from typing import Dict, List, Optional, Tuple

from google.transit import gtfs_realtime_pb2
from google.protobuf.message import DecodeError

from app.models.realtime import (
    VehiclePositionRecord,
    VehicleStopStatus,
)
from app.models.transit import GTFSDataset
from app.utils.geo import is_valid_delhi_ncr_coord


class RealtimeFeedParser:
    """Parses raw GTFS-Realtime protobuf bytes and matches to static GTFS."""

    @classmethod
    def parse(
        cls,
        raw_bytes: bytes,
        server_fetch_time: datetime,
        static_dataset: Optional[GTFSDataset] = None,
        stale_threshold_seconds: int = 300,
    ) -> Tuple[List[VehiclePositionRecord], Optional[datetime], int]:
        """Parse raw protobuf bytes into normalized VehiclePositionRecords.

        Args:
            raw_bytes: Raw bytes received from the GTFS-RT endpoint.
            server_fetch_time: UTC timestamp when the feed was fetched by SafarSetu.
            static_dataset: In-memory validated static GTFS dataset for foreign key matching.
            stale_threshold_seconds: Threshold in seconds to flag observations as stale.

        Returns:
            Tuple of (valid_records, feed_header_timestamp, rejected_entity_count).
        """
        feed = gtfs_realtime_pb2.FeedMessage()
        try:
            feed.ParseFromString(raw_bytes)
        except (DecodeError, Exception) as e:
            raise ValueError(f"Malformed GTFS-Realtime protobuf stream: {e}") from e

        # Extract feed header timestamp
        feed_timestamp: Optional[datetime] = None
        if feed.HasField("header") and feed.header.HasField("timestamp"):
            try:
                feed_timestamp = datetime.fromtimestamp(feed.header.timestamp, tz=timezone.utc)
            except (ValueError, OSError, OverflowError):
                feed_timestamp = None

        raw_records_by_vehicle: Dict[str, VehiclePositionRecord] = {}
        rejected_count = 0

        for entity in feed.entity:
            # We are interested in VehiclePositions feeds
            if not entity.HasField("vehicle"):
                continue

            v_msg = entity.vehicle
            entity_id = entity.id or "unknown_entity"

            # 1. Vehicle identifier
            vehicle_id: str
            if v_msg.HasField("vehicle") and v_msg.vehicle.HasField("id") and v_msg.vehicle.id.strip():
                vehicle_id = v_msg.vehicle.id.strip()
            elif entity.HasField("id") and entity.id.strip():
                vehicle_id = entity.id.strip()
            else:
                # Cannot track an entity with no identifier
                rejected_count += 1
                continue

            # 2. Position and coordinate validation
            if not v_msg.HasField("position"):
                rejected_count += 1
                continue

            pos = v_msg.position
            lat = getattr(pos, "latitude", None)
            lon = getattr(pos, "longitude", None)

            if lat is None or lon is None:
                rejected_count += 1
                continue

            try:
                lat_f = float(lat)
                lon_f = float(lon)
            except (ValueError, TypeError):
                rejected_count += 1
                continue

            if math.isnan(lat_f) or math.isnan(lon_f) or math.isinf(lat_f) or math.isinf(lon_f):
                rejected_count += 1
                continue

            # Check WGS-84 valid bounds
            if not (-90.0 <= lat_f <= 90.0 and -180.0 <= lon_f <= 180.0):
                rejected_count += 1
                continue

            # Reject null island (0, 0) coordinates often sent on GPS initialization failure
            if abs(lat_f) < 0.0001 and abs(lon_f) < 0.0001:
                rejected_count += 1
                continue

            # 3. Telemetry (Bearing & Speed)
            bearing: Optional[float] = None
            if pos.HasField("bearing"):
                b = float(pos.bearing)
                if not math.isnan(b) and 0.0 <= b <= 360.0:
                    bearing = round(b, 1)

            speed_mps: Optional[float] = None
            if pos.HasField("speed"):
                s = float(pos.speed)
                if not math.isnan(s) and s >= 0.0:
                    speed_mps = round(s, 2)

            # 4. Vehicle Timestamp
            obs_time: Optional[datetime] = None
            if v_msg.HasField("timestamp") and v_msg.timestamp > 0:
                try:
                    obs_time = datetime.fromtimestamp(v_msg.timestamp, tz=timezone.utc)
                except (ValueError, OSError, OverflowError):
                    obs_time = None

            # Check staleness
            is_stale = False
            ref_time = obs_time or feed_timestamp or server_fetch_time
            age_seconds = (server_fetch_time - ref_time).total_seconds()
            if age_seconds > stale_threshold_seconds:
                is_stale = True

            # 5. Trip and Route Identifiers
            trip_id: Optional[str] = None
            route_id: Optional[str] = None
            if v_msg.HasField("trip"):
                if v_msg.trip.HasField("trip_id") and v_msg.trip.trip_id.strip():
                    trip_id = v_msg.trip.trip_id.strip()
                if v_msg.trip.HasField("route_id") and v_msg.trip.route_id.strip():
                    route_id = v_msg.trip.route_id.strip()

            # 6. Stop Sequence and Status
            current_stop_seq: Optional[int] = None
            if v_msg.HasField("current_stop_sequence"):
                current_stop_seq = int(v_msg.current_stop_sequence)

            status_str = "UNKNOWN"
            if v_msg.HasField("current_status"):
                raw_status = v_msg.current_status
                if raw_status == gtfs_realtime_pb2.VehiclePosition.INCOMING_AT:
                    status_str = VehicleStopStatus.INCOMING_AT.value
                elif raw_status == gtfs_realtime_pb2.VehiclePosition.STOPPED_AT:
                    status_str = VehicleStopStatus.STOPPED_AT.value
                elif raw_status == gtfs_realtime_pb2.VehiclePosition.IN_TRANSIT_TO:
                    status_str = VehicleStopStatus.IN_TRANSIT_TO.value

            current_status = VehicleStopStatus(status_str)

            # 7. Static GTFS Matching
            is_trip_matched = False
            is_route_matched = False
            route_short_name: Optional[str] = None
            route_long_name: Optional[str] = None
            next_stop_id: Optional[str] = None
            next_stop_name: Optional[str] = None

            if static_dataset and not static_dataset.is_empty:
                # Match Trip
                if trip_id and trip_id in static_dataset.trips:
                    static_trip = static_dataset.trips[trip_id]
                    is_trip_matched = True
                    # If route_id is missing, use route_id from verified static trip
                    if not route_id:
                        route_id = static_trip.route_id

                    # Look up route
                    if route_id and route_id in static_dataset.routes:
                        static_route = static_dataset.routes[route_id]
                        is_route_matched = True
                        route_short_name = static_route.route_short_name
                        route_long_name = static_route.route_long_name

                    # Determine next stop if stop sequence is reported
                    if current_stop_seq is not None:
                        trip_st_list = static_dataset.stop_times.get(trip_id, [])
                        for st in trip_st_list:
                            # If IN_TRANSIT_TO or INCOMING_AT, current_stop_sequence is the upcoming stop
                            # If STOPPED_AT, next stop is current_stop_sequence + 1
                            target_seq = (
                                current_stop_seq + 1
                                if current_status == VehicleStopStatus.STOPPED_AT
                                else current_stop_seq
                            )
                            if st.stop_sequence == target_seq:
                                next_stop_id = st.stop_id
                                if st.stop_id in static_dataset.stops:
                                    next_stop_name = static_dataset.stops[st.stop_id].stop_name
                                break

                # Trip was not matched; try matching route_id independently
                elif route_id and route_id in static_dataset.routes:
                    static_route = static_dataset.routes[route_id]
                    is_route_matched = True
                    route_short_name = static_route.route_short_name
                    route_long_name = static_route.route_long_name

            # Determine association label
            association_status = "unassociated"
            if is_trip_matched:
                association_status = "verified_trip"
            elif is_route_matched:
                association_status = "verified_route_only"

            record = VehiclePositionRecord(
                entity_id=entity_id,
                vehicle_id=vehicle_id,
                latitude=round(lat_f, 6),
                longitude=round(lon_f, 6),
                bearing=bearing,
                speed_mps=speed_mps,
                timestamp=obs_time,
                server_fetch_time=server_fetch_time,
                trip_id=trip_id,
                route_id=route_id,
                current_stop_sequence=current_stop_seq,
                current_status=current_status,
                is_trip_matched=is_trip_matched,
                is_route_matched=is_route_matched,
                route_short_name=route_short_name,
                route_long_name=route_long_name,
                next_stop_id=next_stop_id,
                next_stop_name=next_stop_name,
                is_stale=is_stale,
            )

            # Handle duplicate entities in the same payload: retain newest timestamp
            if vehicle_id in raw_records_by_vehicle:
                prev = raw_records_by_vehicle[vehicle_id]
                prev_ts = prev.timestamp or datetime.min.replace(tzinfo=timezone.utc)
                new_ts = record.timestamp or datetime.min.replace(tzinfo=timezone.utc)
                if new_ts >= prev_ts:
                    raw_records_by_vehicle[vehicle_id] = record
            else:
                raw_records_by_vehicle[vehicle_id] = record

        return list(raw_records_by_vehicle.values()), feed_timestamp, rejected_count

