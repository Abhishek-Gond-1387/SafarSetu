"""Locust Load Testing Suite for SafarSetu.

Simulates thousands of concurrent commuters planning transit routes, checking live vehicle
positions, viewing HerRoute community safety cards, and using lost assistance.

Run:
    pip install locust
    locust -f backend/tests/locustfile.py --host https://safarsetu-2.onrender.com
"""
import random
from locust import HttpUser, task, between

SAMPLE_STOP_PAIRS = [
    ("metro_122", "metro_80"),   # Rajiv Chowk -> Hauz Khas
    ("metro_80", "metro_122"),   # Hauz Khas -> Rajiv Chowk
    ("metro_10", "metro_122"),   # Kashmere Gate -> Rajiv Chowk
    ("metro_122", "metro_180"),  # Rajiv Chowk -> Noida Sector 18
]

SAMPLE_CORRIDORS = [
    "corridor_1603_Blue_Line",
    "corridor_Yellow_Line",
    "corridor_Blue_Line",
]


class SafarSetuCommuterUser(HttpUser):
    # Wait between 1 and 3 seconds between actions (typical commuter behaviour)
    wait_time = between(1.0, 3.0)

    @task(5)
    def test_plan_route(self):
        """Simulate a commuter querying multimodal route planning."""
        origin, destination = random.choice(SAMPLE_STOP_PAIRS)
        self.client.post(
            "/api/v1/routes/plan",
            json={
                "origin_stop_id": origin,
                "destination_stop_id": destination,
                "departure_date": "2026-10-31",
                "departure_time": "09:30:00",
                "criterion": random.choice(["fastest", "cheapest", "balanced"]),
            },
            name="/api/v1/routes/plan"
        )

    @task(3)
    def test_herroute_safety_insights(self):
        """Simulate viewing HerRoute safety scores on route comparison cards."""
        corridor = random.choice(SAMPLE_CORRIDORS)
        self.client.get(
            f"/api/v1/safety/routes/{corridor}",
            name="/api/v1/safety/routes/[route_id]"
        )

    @task(2)
    def test_live_vehicle_positions(self):
        """Simulate checking live vehicle tracking positions."""
        self.client.get(
            "/api/v1/realtime/vehicles?limit=10",
            name="/api/v1/realtime/vehicles"
        )

    @task(1)
    def test_lost_assistance(self):
        """Simulate clicking 'I Am Lost / Emergency' near Connaught Place."""
        self.client.post(
            "/api/v1/routes/lost-assistance",
            json={
                "lat": 28.6328,
                "lon": 77.2197,
            },
            name="/api/v1/routes/lost-assistance"
        )

    @task(1)
    def test_prometheus_metrics(self):
        """Simulate monitoring scraper pulling telemetry metrics."""
        self.client.get("/metrics", name="/metrics")

