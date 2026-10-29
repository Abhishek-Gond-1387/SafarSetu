"""Pydantic schemas for user profiles, preferences, saved journeys, recent searches, and feedback."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class SupportedLanguage(str, Enum):
    ENGLISH = "en"
    HINDI = "hi"
    PUNJABI = "pa"
    URDU = "ur"


class SupportedRankingCriterion(str, Enum):
    FASTEST = "fastest"
    CHEAPEST = "cheapest"
    BALANCED = "balanced"


class FeedbackCategory(str, Enum):
    SCHEDULE_INACCURACY = "schedule_inaccuracy"
    BUS_DELAY = "bus_delay"
    MISSING_STOP = "missing_stop"
    APP_ISSUE = "app_issue"
    SAFETY_CONCERN = "safety_concern"
    GENERAL = "general"


class ReviewStatus(str, Enum):
    PENDING = "pending"
    UNDER_REVIEW = "under_review"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"


# ─── Auth / Registration Schemas ──────────────────────────────────────────────

class UserSignUpRequest(BaseModel):
    email: str = Field(..., description="Valid email address")
    password: str = Field(..., min_length=8, description="Password with minimum 8 characters")
    display_name: Optional[str] = Field(None, max_length=100, description="Optional commuter display name")


class UserSignUpResponse(BaseModel):
    user_id: UUID
    email: str
    display_name: Optional[str] = None
    message: str = "User account created successfully."


# ─── Profile Schemas ──────────────────────────────────────────────────────────

class UserProfileOut(BaseModel):
    id: UUID
    email: Optional[str] = None
    display_name: Optional[str] = None
    preferred_language: str = "en"
    created_at: datetime
    updated_at: datetime


class UserProfileUpdate(BaseModel):
    display_name: Optional[str] = Field(None, max_length=100)
    preferred_language: Optional[SupportedLanguage] = None


# ─── Preferences Schemas ──────────────────────────────────────────────────────

class UserPreferencesOut(BaseModel):
    user_id: UUID
    default_ranking_criterion: str = "fastest"
    preferred_language: str = "en"
    max_walking_distance_meters: float = 800.0
    wheelchair_accessible: bool = False
    created_at: datetime
    updated_at: datetime


class UserPreferencesUpdate(BaseModel):
    default_ranking_criterion: Optional[SupportedRankingCriterion] = None
    preferred_language: Optional[SupportedLanguage] = None
    max_walking_distance_meters: Optional[float] = Field(None, ge=0.0, le=5000.0)
    wheelchair_accessible: Optional[bool] = None


# ─── Saved Journey Schemas ────────────────────────────────────────────────────

class SavedJourneyCreate(BaseModel):
    journey_name: str = Field(..., min_length=1, max_length=100, description="User label, e.g., 'Work Commute'")
    origin_stop_id: str = Field(..., description="GTFS origin stop identifier")
    destination_stop_id: str = Field(..., description="GTFS destination stop identifier")
    departure_time_preference: Optional[str] = Field(
        None,
        pattern=r"^\d{2}:\d{2}(:\d{2})?$",
        description="Optional preferred departure time (HH:MM or HH:MM:SS)",
    )
    ranking_criterion_preference: Optional[SupportedRankingCriterion] = None

    @field_validator("journey_name")
    @classmethod
    def validate_name_not_empty(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("journey_name cannot be blank or whitespace only")
        return s


class SavedJourneyOut(BaseModel):
    id: UUID
    user_id: UUID
    journey_name: str
    origin_stop_id: str
    destination_stop_id: str
    origin_stop_name: Optional[str] = None
    destination_stop_name: Optional[str] = None
    departure_time_preference: Optional[str] = None
    ranking_criterion_preference: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class SavedJourneyListResponse(BaseModel):
    total: int
    results: List[SavedJourneyOut]


# ─── Recent Searches Schemas ──────────────────────────────────────────────────

class RecentSearchCreate(BaseModel):
    origin_stop_id: str
    destination_stop_id: str


class RecentSearchOut(BaseModel):
    id: UUID
    user_id: UUID
    origin_stop_id: str
    destination_stop_id: str
    origin_stop_name: Optional[str] = None
    destination_stop_name: Optional[str] = None
    searched_at: datetime


class RecentSearchListResponse(BaseModel):
    total: int
    retention_limit: int = 20
    results: List[RecentSearchOut]


# ─── User Feedback Schemas ────────────────────────────────────────────────────

class UserFeedbackCreate(BaseModel):
    category: FeedbackCategory
    description: str = Field(..., min_length=5, max_length=2000, description="Commuter issue description")


class UserFeedbackOut(BaseModel):
    id: UUID
    user_id: Optional[UUID] = None
    category: str
    description: str
    review_status: str = "pending"
    created_at: datetime
    disclaimer: str = (
        "User feedback records commuter-reported operational issues. "
        "Reports are queued for review and are never automatically treated as verified GTFS ground truth."
    )


# ─── Unified Current User Summary ─────────────────────────────────────────────

class CurrentUserSummaryResponse(BaseModel):
    profile: UserProfileOut
    preferences: UserPreferencesOut
    saved_journeys_count: int
    recent_searches_count: int

