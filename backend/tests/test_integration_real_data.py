"""Integration tests using the genuine downloaded Delhi DTC GTFS dataset."""
from datetime import date
import os
import pytest

from app.models.journey import RouteRankCriterion
from app.repositories.transit_repository import TransitRepository
from app.services.graph_builder import GraphBuilder
from app.services.gtfs_loader import GTFSLoader
from app.services.routing_engine import RoutingEngine

REAL_DATA_DIR = "data/raw/mdb-1262"


@pytest.fixture(scope="module")
def real_delhi_context():
    if not os.path.isdir(REAL_DATA_DIR):
        pytest.skip(f"Genuine dataset not found at {REAL_DATA_DIR}")

    # Load authentic dataset with 1500 trips for fast, deterministic integration tests
    dataset = GTFSLoader.load(REAL_DATA_DIR, source_id="mdb-1262", max_trips=1500)
    repo = TransitRepository(dataset)
    graph = GraphBuilder.build_graph(dataset, enable_walking=False)
    router = RoutingEngine(dataset, graph)
    return dataset, repo, graph, router


def test_real_dataset_integrity(real_delhi_context):
    dataset, repo, graph, router = real_delhi_context

    # Verify genuine Delhi record scale
    assert len(dataset.stops) >= 5000, f"Expected >5000 authentic Delhi stops, got {len(dataset.stops)}"
    assert len(dataset.routes) >= 1000, f"Expected >1000 routes, got {len(dataset.routes)}"
    assert len(dataset.trips) >= 1000, f"Expected >=1000 trips loaded, got {len(dataset.trips)}"

    # Check genuine agency
    assert any("DIMTS" in a.agency_name or "Delhi" in a.agency_name for a in dataset.agencies.values())

    # Expiry verification
    assert dataset.feed_info.feed_end_date == date(2024, 1, 1)


def test_real_delhi_stop_search(real_delhi_context):
    _, repo, _, _ = real_delhi_context

    # Search for genuine Delhi transport hubs
    narela_stops, total_narela = repo.search_stops(query="Narela", page=1, page_size=10)
    assert total_narela > 0
    assert any("narela" in s.stop_name.lower() for s in narela_stops)

    terminal_stops, total_terminals = repo.search_stops(query="Terminal", page=1, page_size=10)
    assert total_terminals > 10


def test_real_delhi_nearby_stops_coordinates(real_delhi_context):
    _, repo, _, _ = real_delhi_context

    # Connaught Place coordinates (28.6315° N, 77.2167° E)
    cp_lat, cp_lon = 28.6315, 77.2167
    nearby = repo.find_nearby_stops(lat=cp_lat, lon=cp_lon, radius_meters=1500.0, limit=20)

    assert len(nearby) > 0
    first_stop, dist = nearby[0]
    assert dist <= 1500.0
    # Coordinates must be within plausible Delhi bounds
    assert 28.0 <= first_stop.stop_lat <= 29.0
    assert 76.8 <= first_stop.stop_lon <= 77.5


def test_real_delhi_route_planning(real_delhi_context):
    dataset, repo, graph, router = real_delhi_context

    # Pick two consecutive stops from the first valid trip in the genuine dataset
    target_trip_id = next(iter(dataset.stop_times.keys()))
    trip_stops = dataset.stop_times[target_trip_id]
    assert len(trip_stops) >= 2

    origin_id = trip_stops[0].stop_id
    dest_id = trip_stops[1].stop_id
    dep_sec = trip_stops[0].departure_seconds - 60  # 1 min before scheduled departure

    journeys, reason = router.plan_journey(
        origin_stop_id=origin_id,
        destination_stop_id=dest_id,
        departure_date=date(2023, 6, 1),
        departure_seconds=dep_sec,
        criterion=RouteRankCriterion.FASTEST,
    )

    assert reason is None
    assert len(journeys) >= 1
    j = journeys[0]
    assert len(j.legs) >= 1
    assert j.legs[0].from_stop_id == origin_id
    assert j.legs[0].to_stop_id == dest_id
    assert j.legs[0].mode.value == "bus"
    assert j.provenance_sources == ["mdb-1262"]
    # Verify no fake fares
    assert j.fare_complete is False
    assert j.total_fare_inr is None

