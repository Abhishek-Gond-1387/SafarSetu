"""HerRoute Women's Safety Community Feedback Endpoints."""
from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.auth import AuthenticatedUser, get_current_user
from app.repositories.safety_repository import SafetyRepository
from app.schemas.safety import (
    RouteSafetyInsightsResponse,
    SafetyFeedbackListResponse,
    SafetyFeedbackOut,
    SafetyFeedbackSubmitRequest,
    SafetyInsightsSummary,
)

router = APIRouter()


@router.post(
    "/feedback",
    response_model=SafetyFeedbackOut,
    status_code=status.HTTP_201_CREATED,
    summary="Submit Journey Safety Feedback (HerRoute)",
)
def submit_safety_feedback(
    payload: SafetyFeedbackSubmitRequest,
    user: AuthenticatedUser = Depends(get_current_user),
):
    """Submit post-journey safety and comfort feedback for a route or segment.
    
    Validates user authentication, enforces rate limits, and prevents duplicate reviews
    for the exact same journey segment.
    """
    try:
        feedback = SafetyRepository.submit_feedback(user_id=user.id, req=payload)
        return feedback
    except ValueError as e:
        msg = str(e)
        if "already submitted" in msg.lower() or "duplicate" in msg.lower():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=msg,
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=msg,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to submit safety feedback: {str(e)}",
        )


@router.get(
    "/routes/{route_id}",
    response_model=RouteSafetyInsightsResponse,
    summary="Get Aggregated Community Safety Insights for Route",
)
def get_route_safety_insights(
    route_id: str,
    segments: Optional[str] = Query(None, description="Comma-separated segment IDs (e.g. stop IDs)"),
    time_filter: Optional[str] = Query("all", description="daytime, nighttime, or all"),
):
    """Retrieve aggregated community safety feedback for a route and its individual segments.
    
    Zero personal identities or private user comments are returned; only moderated,
    anonymized counts and frequently reported safety concerns are provided.
    """
    seg_list: Optional[List[str]] = None
    if segments:
        seg_list = [s.strip() for s in segments.split(",") if s.strip()]

    overall, segments_dict = SafetyRepository.get_route_insights(
        route_id=route_id,
        segment_ids=seg_list,
        time_filter=time_filter,
    )

    return RouteSafetyInsightsResponse(
        route_id=route_id,
        overall=overall,
        segments=segments_dict,
        time_filter_applied=time_filter or "all",
    )


@router.get(
    "/segments/{segment_id}",
    response_model=SafetyInsightsSummary,
    summary="Get Community Safety Insights for Specific Transit Segment/Stop",
)
def get_segment_safety_insights(
    segment_id: str,
    time_filter: Optional[str] = Query("all", description="daytime, nighttime, or all"),
):
    """Retrieve community safety insights for a specific station, stop, or interchange."""
    return SafetyRepository.get_segment_insights(
        segment_id=segment_id,
        time_filter=time_filter,
    )


@router.get(
    "/my-feedback",
    response_model=SafetyFeedbackListResponse,
    summary="Get Current User's Submitted Safety Feedback History",
)
def get_my_safety_feedback(
    limit: int = Query(50, ge=1, le=100),
    user: AuthenticatedUser = Depends(get_current_user),
):
    """Retrieve safety reviews submitted by the authenticated user."""
    items = SafetyRepository.get_user_feedback(user_id=user.id, limit=limit)
    return SafetyFeedbackListResponse(
        items=items,
        total_count=len(items),
    )
