from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class Place(BaseModel):
    name: str
    city: str
    state: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None  # e.g., Heritage, Nature, Pilgrimage, Adventure


class TripBase(BaseModel):
    title: str
    source: str
    destination: str
    duration_days: int = Field(..., gt=0, description="Duration of the trip in days")
    estimated_budget_inr: float = Field(..., ge=0, description="Estimated budget in INR")
    places_to_visit: List[Place] = []
    tags: List[str] = []


class TripCreate(TripBase):
    pass


class Trip(TripBase):
    id: str
    created_at: datetime

    model_config = {"from_attributes": True}


class TripSearchQuery(BaseModel):
    query: Optional[str] = None
    max_budget_inr: Optional[float] = None
    duration_days: Optional[int] = None

