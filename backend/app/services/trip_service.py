from datetime import datetime, timezone
import uuid
from typing import List, Optional
from app.schemas.trip import Trip, TripCreate, Place


# In-memory sample database for SafarSetu starter
_MOCK_TRIPS: List[Trip] = [
    Trip(
        id=str(uuid.uuid4()),
        title="Varanasi Cultural & Spiritual Heritage",
        source="New Delhi",
        destination="Varanasi",
        duration_days=3,
        estimated_budget_inr=8500.0,
        places_to_visit=[
            Place(name="Dashashwamedh Ghat", city="Varanasi", state="Uttar Pradesh", category="Pilgrimage"),
            Place(name="Kashi Vishwanath Temple", city="Varanasi", state="Uttar Pradesh", category="Pilgrimage"),
            Place(name="Sarnath", city="Varanasi", state="Uttar Pradesh", category="Heritage"),
        ],
        tags=["spiritual", "heritage", "river-ganga"],
        created_at=datetime.now(timezone.utc),
    ),
    Trip(
        id=str(uuid.uuid4()),
        title="Jaipur - Udaipur Royal Rajasthan Trail",
        source="Delhi",
        destination="Udaipur",
        duration_days=5,
        estimated_budget_inr=18000.0,
        places_to_visit=[
            Place(name="Amber Fort", city="Jaipur", state="Rajasthan", category="Heritage"),
            Place(name="Hawa Mahal", city="Jaipur", state="Rajasthan", category="Heritage"),
            Place(name="City Palace", city="Udaipur", state="Rajasthan", category="Heritage"),
            Place(name="Lake Pichola", city="Udaipur", state="Rajasthan", category="Nature"),
        ],
        tags=["royal", "palaces", "culture"],
        created_at=datetime.now(timezone.utc),
    ),
]


class TripService:
    @staticmethod
    def get_all_trips(query: Optional[str] = None, max_budget: Optional[float] = None) -> List[Trip]:
        results = _MOCK_TRIPS
        if query:
            q = query.lower()
            results = [
                t for t in results
                if q in t.title.lower() or q in t.destination.lower() or q in t.source.lower()
            ]
        if max_budget is not None:
            results = [t for t in results if t.estimated_budget_inr <= max_budget]
        return results

    @staticmethod
    def get_trip_by_id(trip_id: str) -> Optional[Trip]:
        for trip in _MOCK_TRIPS:
            if trip.id == trip_id:
                return trip
        return None

    @staticmethod
    def create_trip(payload: TripCreate) -> Trip:
        new_trip = Trip(
            id=str(uuid.uuid4()),
            created_at=datetime.now(timezone.utc),
            **payload.model_dump(),
        )
        _MOCK_TRIPS.append(new_trip)
        return new_trip

