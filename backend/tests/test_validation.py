"""Unit tests for GTFS schema, relational integrity, and coordinate validation."""
import os
import tempfile
import pytest

from app.models.transit import StopTime
from app.services.data_validator import GTFSValidator


@pytest.fixture
def temp_gtfs_dir():
    """Create a temporary directory with minimal valid GTFS files for fixture tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Write valid minimal files
        with open(os.path.join(tmpdir, "agency.txt"), "w", encoding="utf-8") as f:
            f.write("agency_id,agency_name,agency_url,agency_timezone\n")
            f.write("DTC,Delhi Transport Corporation,https://dtc.delhi.gov.in,Asia/Kolkata\n")

        with open(os.path.join(tmpdir, "stops.txt"), "w", encoding="utf-8") as f:
            f.write("stop_id,stop_name,stop_lat,stop_lon\n")
            f.write("STOP1,Kashmere Gate ISBT,28.6665,77.2285\n")
            f.write("STOP2,Red Fort,28.6562,77.2410\n")

        with open(os.path.join(tmpdir, "routes.txt"), "w", encoding="utf-8") as f:
            f.write("route_id,route_short_name,route_type\n")
            f.write("R101,101,3\n")

        with open(os.path.join(tmpdir, "calendar.txt"), "w", encoding="utf-8") as f:
            f.write("service_id,monday,tuesday,wednesday,thursday,friday,saturday,sunday,start_date,end_date\n")
            f.write("DAILY,1,1,1,1,1,1,1,20220101,20240101\n")

        with open(os.path.join(tmpdir, "trips.txt"), "w", encoding="utf-8") as f:
            f.write("trip_id,route_id,service_id\n")
            f.write("T001,R101,DAILY\n")

        with open(os.path.join(tmpdir, "stop_times.txt"), "w", encoding="utf-8") as f:
            f.write("trip_id,stop_id,stop_sequence,arrival_time,departure_time\n")
            f.write("T001,STOP1,1,08:00:00,08:00:00\n")
            f.write("T001,STOP2,2,08:20:00,08:20:00\n")

        yield tmpdir


def test_valid_gtfs_passes(temp_gtfs_dir):
    report = GTFSValidator.validate_directory(temp_gtfs_dir, source_id="test_valid")
    assert report.is_valid is True
    assert len(report.errors) == 0
    assert report.counts["stops"] == 2
    assert report.counts["routes"] == 1
    assert report.counts["trips"] == 1


def test_missing_required_file(temp_gtfs_dir):
    os.remove(os.path.join(temp_gtfs_dir, "stops.txt"))
    report = GTFSValidator.validate_directory(temp_gtfs_dir, source_id="test_missing")
    assert report.is_valid is False
    assert any("Missing required GTFS file: stops.txt" in err for err in report.errors)


def test_broken_foreign_key_route_id(temp_gtfs_dir):
    # Overwrite trips.txt with a route_id that doesn't exist in routes.txt
    with open(os.path.join(temp_gtfs_dir, "trips.txt"), "w", encoding="utf-8") as f:
        f.write("trip_id,route_id,service_id\n")
        f.write("T001,NONEXISTENT_ROUTE,DAILY\n")

    report = GTFSValidator.validate_directory(temp_gtfs_dir, source_id="test_broken_fk")
    assert report.is_valid is False
    assert any("references to nonexistent route_id" in err for err in report.errors)


def test_invalid_coordinates(temp_gtfs_dir):
    with open(os.path.join(temp_gtfs_dir, "stops.txt"), "w", encoding="utf-8") as f:
        f.write("stop_id,stop_name,stop_lat,stop_lon\n")
        f.write("STOP1,Bad Lat,999.0,77.2285\n")

    report = GTFSValidator.validate_directory(temp_gtfs_dir, source_id="test_bad_coords")
    assert report.is_valid is False
    assert any("invalid lat/lon" in err for err in report.errors)


def test_duplicate_stop_ids_warning(temp_gtfs_dir):
    with open(os.path.join(temp_gtfs_dir, "stops.txt"), "w", encoding="utf-8") as f:
        f.write("stop_id,stop_name,stop_lat,stop_lon\n")
        f.write("STOP1,Stop One,28.6665,77.2285\n")
        f.write("STOP1,Stop One Duplicate,28.6666,77.2286\n")

    report = GTFSValidator.validate_directory(temp_gtfs_dir, source_id="test_dup_stop")
    assert any("duplicate stop_id 'STOP1'" in w for w in report.warnings)


def test_expired_feed_detected(temp_gtfs_dir):
    report = GTFSValidator.validate_directory(temp_gtfs_dir, source_id="test_expired")
    # Feed ends on 20240101, which is in the past
    assert report.is_expired is True
    assert any("expired on 2024-01-01" in w for w in report.warnings)


def test_parse_time_beyond_24_hours():
    # GTFS standard allows 25:30:00 for overnight trips (25 hours + 30 mins)
    sec_normal = StopTime.parse_time("08:15:30")
    assert sec_normal == (8 * 3600 + 15 * 60 + 30)

    sec_overnight = StopTime.parse_time("25:30:00")
    assert sec_overnight == (25 * 3600 + 30 * 60)
    assert sec_overnight == 91800

    sec_invalid = StopTime.parse_time("invalid_time")
    assert sec_invalid is None

