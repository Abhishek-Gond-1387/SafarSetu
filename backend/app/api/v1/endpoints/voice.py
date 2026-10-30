"""Voice Assistant API Endpoints for Multilingual Navigation & Conversational Journey Support."""
from fastapi import APIRouter, HTTPException, status
from app.schemas.voice import (
    VoiceQueryRequest,
    VoiceQueryResponse,
    VoiceStepGuidance,
    VoiceStepGuidanceRequest,
)
from app.services.voice_assistant import MultilingualVoiceAssistant

router = APIRouter()


@router.post("/interact", response_model=VoiceQueryResponse, summary="Process Multilingual Voice/Text Query")
def interact(request: VoiceQueryRequest):
    """Process natural speech transcripts or typed queries in English, Hindi, and Hinglish.
    Extracts transit intents, landmarks, criteria, executes timetable-aware routing,
    rerouting, and generates spoken and display guidance.
    """
    if not request.query or not request.query.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Query string cannot be empty.",
        )
    return MultilingualVoiceAssistant.handle_interaction(request)


@router.post("/guidance", response_model=VoiceStepGuidance, summary="Get Spoken Step Navigation Guidance")
def get_guidance(request: VoiceStepGuidanceRequest):
    """Generate spoken step guidance for a specific leg of an active journey."""
    return MultilingualVoiceAssistant.generate_step_guidance(
        journey=request.journey,
        leg_index=request.leg_index,
        sub_step=request.sub_step or "board",
        target_lang=request.target_language,
    )


@router.get("/languages", summary="Get Supported Voice Assistant Languages")
def get_supported_languages():
    """List of supported input and spoken output languages."""
    return {
        "supported_languages": [
            {"code": "en", "name": "English", "native_name": "English", "locale": "en-IN", "speech_supported": True},
            {"code": "hi", "name": "Hindi", "native_name": "हिन्दी", "locale": "hi-IN", "speech_supported": True},
            {"code": "hinglish", "name": "Hinglish", "native_name": "Hinglish (Hindi-English)", "locale": "hi-IN", "speech_supported": True},
            {"code": "fr", "name": "French", "native_name": "Français", "locale": "fr-FR", "speech_supported": True},
            {"code": "es", "name": "Spanish", "native_name": "Español", "locale": "es-ES", "speech_supported": True},
            {"code": "de", "name": "German", "native_name": "Deutsch", "locale": "de-DE", "speech_supported": True},
        ],
        "default": "en",
    }

