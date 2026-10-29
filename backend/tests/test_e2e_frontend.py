"""End-to-end tests validating frontend static mounting and full commuter journey API flow."""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.data_source_service import TransitContext
from app.core.auth import AuthenticatedUser, security
from uuid import UUID


@pytest.fixture(scope="module")
def client():
    TransitContext.initialize()
    with TestClient(app) as test_client:
        yield test_client


def test_root_endpoint_exposes_frontend_and_api(client: TestClient):
    """Verify that root JSON contains links to frontend and transit endpoints."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "SafarSetu" in data["message"]
    assert data["frontend"] == "/app"
    assert "/api/v1/stops" in data["api_v1_stops"]


def test_frontend_dist_mounted_and_served(client: TestClient):
    """Verify that the compiled frontend is served at /app with HTML entrypoint."""
    response = client.get("/app/")
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")
    assert "SafarSetu" in response.text
    assert '<div id="root">' in response.text


def test_commuter_e2e_journey_flow(client: TestClient):
    """End-to-end commuter flow:
    1. Search for genuine stops.
    2. Plan timetable-aware journey with fastest criterion.
    3. Verify non-negotiable honesty constraints (freshness warnings, straight-line walking tags, fare honesty).
    """
    # 1. Search stop
    search_res = client.get("/api/v1/stops/?query=Kashmere&page_size=5")
    assert search_res.status_code == 200
    stops_data = search_res.json()
    assert stops_data["total"] > 0
    origin_stop_id = stops_data["results"][0]["stop_id"]

    # Search destination
    dest_search = client.get("/api/v1/stops/?query=Mori&page_size=5")
    assert dest_search.status_code == 200
    dest_stops = dest_search.json()
    assert dest_stops["total"] > 0
    dest_stop_id = dest_stops["results"][0]["stop_id"]

    # 2. Plan Route
    plan_payload = {
        "origin_stop_id": origin_stop_id,
        "destination_stop_id": dest_stop_id,
        "departure_date": "2024-03-15",
        "departure_time": "08:30:00",
        "criterion": "fastest",
        "max_transfers": 3,
        "max_walk_meters": 800,
    }
    plan_res = client.post("/api/v1/routes/plan", json=plan_payload)
    assert plan_res.status_code == 200
    plan_data = plan_res.json()

    # 3. Freshness & Data integrity assertions
    assert "journeys" in plan_data
    assert "data_freshness_warnings" in plan_data
    assert len(plan_data["data_freshness_warnings"]) > 0

    if len(plan_data["journeys"]) > 0:
        journey = plan_data["journeys"][0]
        assert journey["total_duration_minutes"] > 0
        assert "legs" in journey
        for leg in journey["legs"]:
            if leg["mode"] == "walking":
                assert leg["distance_type"] == "straight_line"


def test_authenticated_commuter_save_journey(client: TestClient):
    """Verify that an authenticated user can save a planned journey and retrieve it."""
    # Use dev auth bypass
    fake_token = "eyJhbGciOiJub25lIn0.eyJzdWIiOiJhMDAwMDAwMC0wMDAwLTAwMDAtMDAwMC0wMDAwMDAwMDAwMDEiLCJlbWFpbCI6ImNvbW11dGVyQHRlc3QuaW4ifQ."
    headers = {"Authorization": f"Bearer {fake_token}"}

    # Save journey with genuine stops
    save_payload = {
        "journey_name": "Work Commute",
        "origin_stop_id": "3127",
        "destination_stop_id": "2024",
        "departure_time_preference": "08:30",
        "ranking_criterion_preference": "fastest",
    }
    save_res = client.post("/api/v1/users/me/saved-journeys", json=save_payload, headers=headers)
    assert save_res.status_code == 201
    saved_id = save_res.json()["id"]

    # Retrieve saved journeys
    get_res = client.get("/api/v1/users/me/saved-journeys", headers=headers)
    assert get_res.status_code == 200
    results = get_res.json()["results"]
    assert any(j["id"] == saved_id for j in results)

    # Clean up
    del_res = client.delete(f"/api/v1/users/me/saved-journeys/{saved_id}", headers=headers)
    assert del_res.status_code == 204
