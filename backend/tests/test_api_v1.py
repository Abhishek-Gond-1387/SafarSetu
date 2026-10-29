"""API endpoint tests for SafarSetu FastAPI transit routing service."""
import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_top_level_health():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ("ok", "degraded")
    assert "data_sources" in data
    assert "graph_nodes" in data


def test_api_v1_health():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["version"] == "1.0.0"


def test_api_v1_stops_pagination_and_search():
    response = client.get("/api/v1/stops/?page=1&page_size=5")
    assert response.status_code == 200
    data = response.json()
    assert "results" in data
    assert len(data["results"]) <= 5
    assert data["page"] == 1
    assert data["page_size"] == 5

    # Search query
    search_resp = client.get("/api/v1/stops/?query=terminal&page_size=3")
    assert search_resp.status_code == 200
    search_data = search_resp.json()
    assert "total" in search_data


def test_api_v1_stops_nearby():
    # Delhi Connaught Place
    response = client.get("/api/v1/stops/nearby?lat=28.6315&lon=77.2167&radius_meters=1500")
    assert response.status_code == 200
    data = response.json()
    assert "results" in data
    assert "distance_note" in data
    assert "straight-line" in data["distance_note"].lower()

    if data["results"]:
        first = data["results"][0]
        assert "distance_meters" in first
        assert first["distance_type"] == "straight_line"


def test_api_v1_route_compare_endpoint():
    # Construct two sample journey candidates to test comparison
    journey_1 = {
        "departure_time": "08:00:00",
        "arrival_time": "08:35:00",
        "total_duration_minutes": 35.0,
        "total_walk_meters": 200.0,
        "num_transfers": 0,
        "fare_inr": None,
        "fare_complete": False,
        "rank_criterion": "fastest",
        "legs": [
            {
                "mode": "bus",
                "from_stop_id": "STOP_A",
                "to_stop_id": "STOP_B",
                "from_stop_name": "Stop A",
                "to_stop_name": "Stop B",
                "departure_time": "08:00:00",
                "arrival_time": "08:35:00",
                "duration_minutes": 35.0,
                "route_id": "101",
                "trip_id": "T1",
                "source_id": "mdb-1262",
            }
        ],
        "warnings": [],
        "data_sources": ["mdb-1262"],
    }
    journey_2 = {
        "departure_time": "08:05:00",
        "arrival_time": "08:45:00",
        "total_duration_minutes": 40.0,
        "total_walk_meters": 50.0,
        "num_transfers": 1,
        "fare_inr": None,
        "fare_complete": False,
        "rank_criterion": "fastest",
        "legs": [
            {
                "mode": "bus",
                "from_stop_id": "STOP_A",
                "to_stop_id": "STOP_C",
                "from_stop_name": "Stop A",
                "to_stop_name": "Stop C",
                "departure_time": "08:05:00",
                "arrival_time": "08:45:00",
                "duration_minutes": 40.0,
                "route_id": "102",
                "trip_id": "T2",
                "source_id": "mdb-1262",
            }
        ],
        "warnings": [],
        "data_sources": ["mdb-1262"],
    }

    response = client.post("/api/v1/routes/compare", json={"journeys": [journey_1, journey_2]})
    assert response.status_code == 200
    data = response.json()
    assert "metrics" in data
    assert len(data["metrics"]) == 2
    # Verify fastest ranking
    assert data["metrics"][0]["rank_fastest"] == 1
    assert data["metrics"][1]["rank_fastest"] == 2
    # Fare unknown handling: rank_cheapest must be None when fare is incomplete
    assert data["metrics"][0]["rank_cheapest"] is None

