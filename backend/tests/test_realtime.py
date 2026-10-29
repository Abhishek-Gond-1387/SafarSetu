"""Unit and integration tests for GTFS-Realtime parsing, static matching, and poller."""
import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch
import httpx
import pytest
from fastapi.testclient import TestClient
from google.transit import gtfs_realtime_pb2

from app.core.config import settings
from app.main import app
from app.models.realtime import ErrorCategory, FeedFreshness, VehicleStopStatus
from app.models.transit import GTFSDataset, Route, RouteType, Stop, StopTime, Trip
from app.repositories.realtime_repository import RealtimeVehicleRepository
from app.services.realtime_feed_service import RealtimeFeedParser
from app.services.realtime_poller import OTDRealtimePoller, sanitize_url

client = TestClient(app)


@pytest.fixture
def sample_static_dataset():
    """Minimal static dataset fixture for foreign-key matching tests."""
    stops = {
        "S1": Stop("S1", "Narela Terminal", 28.8520, 77.0880),
        "S2": Stop("S2", "Bawana Depot", 28.7980, 77.0340),
    }
    routes = {
        "R_764": Route("R_764", RouteType.BUS, route_short_name="764", route_long_name="Najafgarh to Nehru Place"),
    }
    trips = {
        "T_01": Trip("T_01", "R_764", "SERVICE_DAILY"),
    }
    stop_times = {
        "T_01": [
            StopTime("T_01", "S1", 1, 28800, 28800),
            StopTime("T_01", "S2", 2, 30600, 30600),
        ]
    }
    return GTFSDataset(
        feed_info=None,
        agencies={},
        stops=stops,
        routes=routes,
        trips=trips,
        stop_times=stop_times,
        calendar={},
        calendar_dates={},
        shapes={},
        transfers=[],
        fare_attributes={},
        fare_rules=[],
        source_id="test_static",
    )


def build_pb_message(header_time=1700000000) -> gtfs_realtime_pb2.FeedMessage:
    msg = gtfs_realtime_pb2.FeedMessage()
    msg.header.gtfs_realtime_version = "2.0"
    msg.header.timestamp = header_time
    return msg


def test_parse_valid_feed(sample_static_dataset):
    msg = build_pb_message()
    entity = msg.entity.add()
    entity.id = "ENT_101"
    v = entity.vehicle
    v.vehicle.id = "DL-1PC-0001"
    v.position.latitude = 28.6139
    v.position.longitude = 77.2090
    v.position.bearing = 95.5
    v.position.speed = 12.5
    v.timestamp = 1700000000
    v.trip.trip_id = "T_01"
    v.current_stop_sequence = 1
    v.current_status = gtfs_realtime_pb2.VehiclePosition.IN_TRANSIT_TO

    raw = msg.SerializeToString()
    fetch_time = datetime.fromtimestamp(1700000050, tz=timezone.utc)
    records, feed_ts, rejected = RealtimeFeedParser.parse(
        raw_bytes=raw,
        server_fetch_time=fetch_time,
        static_dataset=sample_static_dataset,
    )

    assert rejected == 0
    assert len(records) == 1
    rec = records[0]
    assert rec.vehicle_id == "DL-1PC-0001"
    assert rec.latitude == pytest.approx(28.6139, abs=1e-4)
    assert rec.longitude == pytest.approx(77.2090, abs=1e-4)
    assert rec.bearing == pytest.approx(95.5, abs=0.1)
    assert rec.speed_mps == pytest.approx(12.5, abs=0.1)
    assert rec.speed_kmh == pytest.approx(45.0, abs=0.1)
    assert rec.is_trip_matched is True
    assert rec.is_route_matched is True
    assert rec.route_short_name == "764"
    assert rec.next_stop_id == "S1"
    assert rec.next_stop_name == "Narela Terminal"
    assert rec.association_status == "verified_trip"
    assert rec.is_stale is False


def test_parse_empty_feed():
    msg = build_pb_message()
    raw = msg.SerializeToString()
    fetch_time = datetime.now(timezone.utc)
    records, feed_ts, rejected = RealtimeFeedParser.parse(raw_bytes=raw, server_fetch_time=fetch_time)

    assert len(records) == 0
    assert rejected == 0
    assert feed_ts is not None


def test_parse_missing_optional_fields():
    msg = build_pb_message()
    entity = msg.entity.add()
    entity.id = "ENT_BARE"
    v = entity.vehicle
    v.vehicle.id = "DL-02"
    v.position.latitude = 28.7000
    v.position.longitude = 77.1000
    # No speed, no bearing, no trip, no timestamp

    raw = msg.SerializeToString()
    fetch_time = datetime.now(timezone.utc)
    records, _, rejected = RealtimeFeedParser.parse(raw_bytes=raw, server_fetch_time=fetch_time)

    assert rejected == 0
    assert len(records) == 1
    rec = records[0]
    assert rec.vehicle_id == "DL-02"
    assert rec.speed_mps is None
    assert rec.speed_kmh is None
    assert rec.bearing is None
    assert rec.trip_id is None
    assert rec.route_id is None
    assert rec.association_status == "unassociated"


def test_parse_invalid_coordinates():
    msg = build_pb_message()
    # Invalid lat > 90
    e1 = msg.entity.add()
    e1.id = "E1"
    e1.vehicle.vehicle.id = "V1"
    e1.vehicle.position.latitude = 150.0
    e1.vehicle.position.longitude = 77.0

    # Null Island (0, 0)
    e2 = msg.entity.add()
    e2.id = "E2"
    e2.vehicle.vehicle.id = "V2"
    e2.vehicle.position.latitude = 0.0
    e2.vehicle.position.longitude = 0.0

    # Valid vehicle
    e3 = msg.entity.add()
    e3.id = "E3"
    e3.vehicle.vehicle.id = "V3"
    e3.vehicle.position.latitude = 28.6500
    e3.vehicle.position.longitude = 77.2200

    raw = msg.SerializeToString()
    fetch_time = datetime.now(timezone.utc)
    records, _, rejected = RealtimeFeedParser.parse(raw_bytes=raw, server_fetch_time=fetch_time)

    assert rejected == 2
    assert len(records) == 1
    assert records[0].vehicle_id == "V3"


def test_unknown_trip_and_route_association(sample_static_dataset):
    msg = build_pb_message()
    entity = msg.entity.add()
    entity.id = "ENT_UNKNOWN"
    v = entity.vehicle
    v.vehicle.id = "DL-99"
    v.position.latitude = 28.6200
    v.position.longitude = 77.2100
    v.trip.trip_id = "NONEXISTENT_TRIP_999"
    v.trip.route_id = "NONEXISTENT_ROUTE_999"

    raw = msg.SerializeToString()
    fetch_time = datetime.now(timezone.utc)
    records, _, rejected = RealtimeFeedParser.parse(
        raw_bytes=raw,
        server_fetch_time=fetch_time,
        static_dataset=sample_static_dataset,
    )

    assert len(records) == 1
    rec = records[0]
    # Truthfulness: preserved raw IDs, but marked unassociated with no fabricated route names or ETAs
    assert rec.is_trip_matched is False
    assert rec.is_route_matched is False
    assert rec.route_short_name is None
    assert rec.next_stop_id is None
    assert rec.association_status == "unassociated"


def test_stale_observation_detection():
    msg = build_pb_message()
    entity = msg.entity.add()
    entity.id = "ENT_OLD"
    v = entity.vehicle
    v.vehicle.id = "DL-OLD"
    v.position.latitude = 28.6200
    v.position.longitude = 77.2100
    v.timestamp = 1000  # Epoch ancient time

    raw = msg.SerializeToString()
    fetch_time = datetime.now(timezone.utc)
    records, _, _ = RealtimeFeedParser.parse(
        raw_bytes=raw,
        server_fetch_time=fetch_time,
        stale_threshold_seconds=300,
    )

    assert len(records) == 1
    assert records[0].is_stale is True


def test_duplicate_vehicle_records_deduplication():
    msg = build_pb_message()
    # First duplicate (older)
    e1 = msg.entity.add()
    e1.id = "E1"
    e1.vehicle.vehicle.id = "SAME_BUS"
    e1.vehicle.position.latitude = 28.6100
    e1.vehicle.position.longitude = 77.2000
    e1.vehicle.timestamp = 1700000000

    # Second duplicate (newer)
    e2 = msg.entity.add()
    e2.id = "E2"
    e2.vehicle.vehicle.id = "SAME_BUS"
    e2.vehicle.position.latitude = 28.6200
    e2.vehicle.position.longitude = 77.2100
    e2.vehicle.timestamp = 1700000050

    raw = msg.SerializeToString()
    fetch_time = datetime.now(timezone.utc)
    records, _, _ = RealtimeFeedParser.parse(raw_bytes=raw, server_fetch_time=fetch_time)

    assert len(records) == 1
    assert records[0].vehicle_id == "SAME_BUS"
    assert records[0].latitude == pytest.approx(28.6200, abs=1e-4)


def test_malformed_protobuf_bytes():
    with pytest.raises(ValueError, match="Malformed GTFS-Realtime"):
        RealtimeFeedParser.parse(
            raw_bytes=b"not_a_valid_protobuf_stream",
            server_fetch_time=datetime.now(timezone.utc),
        )


def test_api_key_redaction_in_urls():
    url = "https://otd.delhi.gov.in/api/realtime/VehiclePositions.pb?key=SECRET_TOKEN_12345"
    sanitized = sanitize_url(url)
    assert "SECRET_TOKEN_12345" not in sanitized
    assert "key=REDACTED" in sanitized


def test_poller_authorization_failure_and_timeout():
    repo = RealtimeVehicleRepository()
    poller = OTDRealtimePoller(repository=repo)

    # 1. Test missing key
    with patch.object(settings, "OTD_REALTIME_API_KEY", None):
        success = asyncio.run(poller.poll_once())
        assert success is False
        status = repo.get_status()
        assert status.error_category == ErrorCategory.AUTH_ERROR
        assert status.api_key_configured is False

    # 2. Test 401 HTTP response from OTD
    with patch.object(settings, "OTD_REALTIME_API_KEY", "MOCK_KEY"):
        mock_resp = httpx.Response(status_code=401, request=httpx.Request("GET", "https://example.com"))
        with patch("httpx.AsyncClient.get", AsyncMock(return_value=mock_resp)):
            success = asyncio.run(poller.poll_once())
            assert success is False
            status = repo.get_status()
            assert status.error_category == ErrorCategory.AUTH_ERROR
            assert "HTTP 401" in (status.error_message_sanitized or "")

    # 3. Test timeout exception
    with patch.object(settings, "OTD_REALTIME_API_KEY", "MOCK_KEY"):
        with patch("httpx.AsyncClient.get", AsyncMock(side_effect=httpx.TimeoutException("timeout"))):
            success = asyncio.run(poller.poll_once())
            assert success is False
            status = repo.get_status()
            assert status.error_category == ErrorCategory.TIMEOUT


def test_poller_start_and_stop_lifecycle():
    repo = RealtimeVehicleRepository()
    poller = OTDRealtimePoller(repository=repo)

    # Disabled poller
    with patch.object(settings, "OTD_REALTIME_ENABLED", False):
        asyncio.run(poller.start())
        assert poller._is_running is False
        assert repo.get_status().error_category == ErrorCategory.DISABLED

    # Configured poller starts and stops cleanly
    async def run_lifecycle():
        with patch.object(settings, "OTD_REALTIME_ENABLED", True), \
             patch.object(settings, "OTD_REALTIME_API_KEY", "TEST_KEY"):
            with patch.object(poller, "poll_once", AsyncMock(return_value=True)):
                await poller.start()
                assert poller._is_running is True
                await poller.stop()
                assert poller._is_running is False

    asyncio.run(run_lifecycle())


def test_api_realtime_status_endpoint():
    response = client.get("/api/v1/realtime/status")
    assert response.status_code == 200
    data = response.json()
    assert "enabled" in data
    assert "api_key_configured" in data
    assert "feed_freshness" in data
    assert "cached_vehicles_count" in data
    # Security: ensure no key leaked
    assert "key" not in data or data["key"] is None


def test_api_realtime_vehicles_filtering():
    # Insert test observation into the repository
    from app.services.data_source_service import get_transit_context
    ctx = get_transit_context()
    ctx.realtime_repo.clear()

    msg = build_pb_message()
    entity = msg.entity.add()
    entity.id = "TEST_E1"
    entity.vehicle.vehicle.id = "DL-01-VTEST"
    entity.vehicle.position.latitude = 28.6500
    entity.vehicle.position.longitude = 77.2000
    entity.vehicle.trip.route_id = "R_764"

    raw = msg.SerializeToString()
    records, _, _ = RealtimeFeedParser.parse(raw, datetime.now(timezone.utc))
    ctx.realtime_repo.upsert_vehicles(records, datetime.now(timezone.utc), None, 0)

    # 1. Query all
    resp = client.get("/api/v1/realtime/vehicles")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["filtered_count"] == 1
    assert data["results"][0]["vehicle_id"] == "DL-01-VTEST"

    # 2. Query filter matching
    resp_filtered = client.get("/api/v1/realtime/vehicles?route_id=R_764")
    assert resp_filtered.status_code == 200
    assert resp_filtered.json()["filtered_count"] == 1

    # 3. Query filter non-matching
    resp_none = client.get("/api/v1/realtime/vehicles?route_id=NON_EXISTENT")
    assert resp_none.status_code == 200
    assert resp_none.json()["filtered_count"] == 0

    # 4. Bounding box query
    resp_bbox = client.get("/api/v1/realtime/vehicles?min_lat=28.60&max_lat=28.70&min_lon=77.10&max_lon=77.30")
    assert resp_bbox.status_code == 200
    assert resp_bbox.json()["filtered_count"] == 1


def test_health_endpoint_includes_realtime():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert "realtime" in data
    assert data["realtime"] is not None
    assert "cached_vehicles_count" in data["realtime"]
    assert "feed_freshness" in data["realtime"]
