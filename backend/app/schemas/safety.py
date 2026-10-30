"""Pydantic schemas for HerRoute Women's Safety Community Feedback."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID
from pydantic import BaseModel, Field, constr


class SafetyExperienceEnum(str, Enum):
    COMFORTABLE = "comfortable"
    UNCOMFORTABLE = "uncomfortable"
    UNSAFE = "unsafe"


class SegmentTypeEnum(str, Enum):
    WALKING = "walking"
    METRO = "metro"
    BUS = "bus"
    AUTO = "auto"
    STATION_INTERCHANGE = "station_interchange"
    ENTIRE_JOURNEY = "entire_journey"


class TimeCategoryEnum(str, Enum):
    DAYTIME = "daytime"
    NIGHTTIME = "nighttime"


class SafetyConcernCount(BaseModel):
    concern_key: str
    label: str
    count: int


class SafetyFeedbackSubmitRequest(BaseModel):
    journey_id: Optional[str] = Field(None, description="Optional active journey ID or hash")
    route_id: Optional[str] = Field(None, description="Identifier for the transit route or stop-to-stop pair")
    segment_id: str = Field(..., description="Specific stop_id, leg index, or 'entire_journey'")
    segment_type: SegmentTypeEnum = Field(SegmentTypeEnum.ENTIRE_JOURNEY, description="Mode or segment reviewed")
    segment_name: Optional[str] = Field(None, description="Human readable name of the segment (e.g. Rajiv Chowk Walk)")
    experience_rating: SafetyExperienceEnum = Field(..., description="Feeling rating: comfortable, uncomfortable, unsafe")
    safety_concerns: List[str] = Field(default_factory=list, description="List of factors that influenced the experience")
    feedback_text: Optional[constr(max_length=500)] = Field(None, description="Optional text feedback, kept private by default")
    time_category: Optional[TimeCategoryEnum] = Field(None, description="daytime (06:00-20:00) or nighttime (20:00-06:00)")


class SafetyFeedbackOut(BaseModel):
    id: UUID
    user_id: UUID
    journey_id: Optional[str] = None
    route_id: Optional[str] = None
    segment_id: str
    segment_type: str
    segment_name: Optional[str] = None
    experience_rating: str
    safety_concerns: List[str] = []
    feedback_text: Optional[str] = None
    time_category: str
    created_at: datetime
    moderation_status: str = "approved"


class SafetyFeedbackListResponse(BaseModel):
    items: List[SafetyFeedbackOut]
    total_count: int


class SafetyInsightsSummary(BaseModel):
    identifier: str
    display_title: Optional[str] = None
    has_sufficient_data: bool = False
    total_reports: int = 0
    comfortable_count: int = 0
    uncomfortable_count: int = 0
    unsafe_count: int = 0
    daytime_reports_count: int = 0
    nighttime_reports_count: int = 0
    frequent_concerns: List[SafetyConcernCount] = []
    time_context_notice: Optional[str] = None
    notice: str = (
        "Community reported experiences from women travelers on HerRoute. "
        "These are historical observations and do not guarantee safety or serve as official crime statistics."
    )


class RouteSafetyInsightsResponse(BaseModel):
    route_id: str
    overall: SafetyInsightsSummary
    segments: Dict[str, SafetyInsightsSummary] = {}
    time_filter_applied: str = "all"
