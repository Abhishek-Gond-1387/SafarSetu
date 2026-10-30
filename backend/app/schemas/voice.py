"""Pydantic schemas for Multilingual Voice Assistant & Conversational Guidance."""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class VoiceQueryRequest(BaseModel):
    query: str = Field(..., description="Recognized speech transcript or typed query")
    language: Optional[str] = Field("auto", description="Spoken/input language code (auto, en, hi, hinglish, etc.)")
    target_language: Optional[str] = Field("auto", description="Preferred output language (auto, en, hi, hinglish, fr, es, de, etc.)")
    session_id: Optional[str] = Field(None, description="Client conversational session identifier")
    current_journey: Optional[Dict[str, Any]] = Field(None, description="Active journey object currently selected in commuter UI")
    current_leg_index: Optional[int] = Field(None, description="Index of currently active journey leg in navigation")
    user_lat: Optional[float] = Field(None, description="GPS latitude if granted by commuter")
    user_lon: Optional[float] = Field(None, description="GPS longitude if granted by commuter")


class VoiceStepGuidance(BaseModel):
    step_number: int
    total_steps: int
    step_type: str = Field(..., description="walk, board_metro, board_bus, in_transit, transfer, alight, destination")
    spoken_instruction: str
    display_instruction: str
    stop_name: str
    line_name: Optional[str] = None
    headsign: Optional[str] = None
    duration_minutes: Optional[float] = None
    distance_meters: Optional[float] = None
    next_stop_name: Optional[str] = None
    fare_inr: Optional[float] = None


class VoiceQueryResponse(BaseModel):
    success: bool = True
    transcript: str
    detected_language: str
    response_language: str
    intent: str
    spoken_text: str
    display_text: str
    action: Optional[str] = Field("NONE", description="NAVIGATE, REROUTE, STEP_GUIDANCE, SET_FILTER, NONE")
    entities: Dict[str, Any] = Field(default_factory=dict)
    planned_route: Optional[Dict[str, Any]] = None
    step_guidance: Optional[VoiceStepGuidance] = None
    suggested_followups: List[str] = Field(default_factory=list)


class VoiceStepGuidanceRequest(BaseModel):
    journey: Dict[str, Any]
    leg_index: int = 0
    sub_step: Optional[str] = "board"  # board, in_transit, alight, walk
    target_language: str = "en"  # en, hi, hinglish, fr, es, de

