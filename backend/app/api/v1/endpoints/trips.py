from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query, status
from app.schemas.trip import Trip, TripCreate
from app.services.trip_service import TripService

router = APIRouter()


@router.get("/", response_model=List[Trip], summary="List or Search Trips")
def list_trips(
    query: Optional[str] = Query(None, description="Search term for destination, source, or title"),
    max_budget: Optional[float] = Query(None, description="Maximum budget in INR"),
):
    """Retrieve all trips or filter by search criteria."""
    return TripService.get_all_trips(query=query, max_budget=max_budget)


@router.get("/{trip_id}", response_model=Trip, summary="Get Trip Details")
def get_trip(trip_id: str):
    """Retrieve details for a specific trip by its ID."""
    trip = TripService.get_trip_by_id(trip_id)
    if not trip:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Trip with ID '{trip_id}' not found",
        )
    return trip


@router.post("/", response_model=Trip, status_code=status.HTTP_201_CREATED, summary="Create a New Trip")
def create_trip(payload: TripCreate):
    """Create a new itinerary/trip in SafarSetu."""
    return TripService.create_trip(payload)

