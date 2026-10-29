from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_root():
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert "docs" in data


def test_health():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "version" in data


def test_list_trips():
    response = client.get("/api/v1/trips/")
    assert response.status_code == 200
    trips = response.json()
    assert isinstance(trips, list)
    assert len(trips) >= 2


def test_create_and_get_trip():
    payload = {
        "title": "Golden Temple & Wagah Border Tour",
        "source": "Chandigarh",
        "destination": "Amritsar",
        "duration_days": 2,
        "estimated_budget_inr": 6000.0,
        "places_to_visit": [
            {
                "name": "Sri Harmandir Sahib (Golden Temple)",
                "city": "Amritsar",
                "state": "Punjab",
                "category": "Pilgrimage",
            },
            {
                "name": "Attari-Wagah Border",
                "city": "Amritsar",
                "state": "Punjab",
                "category": "Heritage",
            },
        ],
        "tags": ["heritage", "culture", "peace"],
    }
    response = client.post("/api/v1/trips/", json=payload)
    assert response.status_code == 201
    created_trip = response.json()
    assert created_trip["title"] == payload["title"]
    assert "id" in created_trip

    # Test retrieval
    get_response = client.get(f"/api/v1/trips/{created_trip['id']}")
    assert get_response.status_code == 200
    assert get_response.json()["id"] == created_trip["id"]

