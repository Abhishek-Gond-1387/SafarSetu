"""User profile, preferences, saved journeys, recent searches, and feedback endpoints."""
from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.auth import AuthenticatedUser, get_current_user, get_optional_user
from app.repositories.user_repository import UserRepository
from app.schemas.user import (
    CurrentUserSummaryResponse,
    RecentSearchCreate,
    RecentSearchListResponse,
    RecentSearchOut,
    SavedJourneyCreate,
    SavedJourneyListResponse,
    SavedJourneyOut,
    UserFeedbackCreate,
    UserFeedbackOut,
    UserPreferencesOut,
    UserPreferencesUpdate,
    UserProfileOut,
    UserProfileUpdate,
    UserSignUpRequest,
    UserSignUpResponse,
)
from app.services.data_source_service import get_transit_context

router = APIRouter()


# ─── Auth / Registration Endpoints ───────────────────────────────────────────

@router.post("/signup", response_model=UserSignUpResponse, status_code=status.HTTP_201_CREATED, summary="Register New User Account")
def register_user(payload: UserSignUpRequest):
    """Register a new user in Supabase auth and create their profile in public.profiles.
    
    The account is confirmed upon creation so commuters can immediately sign in with
    the exact same credentials.
    """
    try:
        user_id, email, display_name = UserRepository.register_user(
            email=payload.email,
            password=payload.password,
            display_name=payload.display_name,
        )
        return UserSignUpResponse(
            user_id=user_id,
            email=email,
            display_name=display_name,
            message="User account registered successfully.",
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


# ─── Profile Endpoints ────────────────────────────────────────────────────────

@router.get("/me", response_model=CurrentUserSummaryResponse, summary="Get Current User Profile & Context")
def get_current_user_profile(user: AuthenticatedUser = Depends(get_current_user)):
    """Retrieve authenticated user's profile, preferences, and aggregate counts."""
    profile = UserRepository.get_or_create_profile(user.id, email=user.email)
    preferences = UserRepository.get_or_create_preferences(user.id)
    journeys, total_journeys = UserRepository.get_saved_journeys(user.id, limit=1)
    recent = UserRepository.get_recent_searches(user.id, limit=20)

    return CurrentUserSummaryResponse(
        profile=profile,
        preferences=preferences,
        saved_journeys_count=total_journeys,
        recent_searches_count=len(recent),
    )


@router.patch("/me", response_model=UserProfileOut, summary="Update User Profile")
def update_current_user_profile(
    update: UserProfileUpdate,
    user: AuthenticatedUser = Depends(get_current_user),
):
    """Update profile fields (display name, preferred language)."""
    return UserRepository.update_profile(user.id, update)


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT, summary="Delete Current User Account")
def delete_current_user_account(user: AuthenticatedUser = Depends(get_current_user)):
    """Permanently delete authenticated user's account and all associated data.
    
    Removes user from auth.users and cascades to public.profiles, user_preferences,
    saved_journeys, and recent_searches.
    """
    UserRepository.delete_user(user.id)
    return None


# ─── Preferences Endpoints ────────────────────────────────────────────────────

@router.get("/me/preferences", response_model=UserPreferencesOut, summary="Get User Preferences")
def get_user_preferences(user: AuthenticatedUser = Depends(get_current_user)):
    """Retrieve commuter preferences (default ranking criterion, language, walking limit)."""
    return UserRepository.get_or_create_preferences(user.id)


@router.put("/me/preferences", response_model=UserPreferencesOut, summary="Update User Preferences")
def update_user_preferences(
    update: UserPreferencesUpdate,
    user: AuthenticatedUser = Depends(get_current_user),
):
    """Update user routing preferences and constraints."""
    return UserRepository.update_preferences(user.id, update)


# ─── Saved Journeys Endpoints ─────────────────────────────────────────────────

@router.get("/me/saved-journeys", response_model=SavedJourneyListResponse, summary="List Saved Journeys")
def list_saved_journeys(
    limit: int = Query(50, ge=1, le=100, description="Max journeys to retrieve"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    user: AuthenticatedUser = Depends(get_current_user),
):
    """Retrieve user's bookmarked transit journeys, ordered newest first."""
    items, total = UserRepository.get_saved_journeys(user.id, limit=limit, offset=offset)
    return SavedJourneyListResponse(total=total, results=items)


@router.post("/me/saved-journeys", response_model=SavedJourneyOut, status_code=status.HTTP_201_CREATED, summary="Save Journey")
def create_saved_journey(
    item: SavedJourneyCreate,
    user: AuthenticatedUser = Depends(get_current_user),
):
    """Save a transit itinerary for quick planning.

    Validation Requirement: Enforces that origin and destination stop IDs exist
    in the genuine GTFS dataset. Unknown stop identifiers are strictly rejected.
    """
    ctx = get_transit_context()

    # Reject identical origin and destination
    if item.origin_stop_id == item.destination_stop_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Origin and destination stops cannot be identical.",
        )

    # Validate stop existence against genuine GTFS dataset
    origin_name = None
    dest_name = None
    if ctx.dataset and ctx.dataset.stops:
        if item.origin_stop_id not in ctx.dataset.stops:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Origin stop ID '{item.origin_stop_id}' does not exist in genuine transit dataset.",
            )
        if item.destination_stop_id not in ctx.dataset.stops:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Destination stop ID '{item.destination_stop_id}' does not exist in genuine transit dataset.",
            )
        origin_name = ctx.dataset.stops[item.origin_stop_id].stop_name
        dest_name = ctx.dataset.stops[item.destination_stop_id].stop_name

    return UserRepository.create_saved_journey(
        user_id=user.id,
        item=item,
        origin_name=origin_name,
        dest_name=dest_name,
    )


@router.delete("/me/saved-journeys/{journey_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete Saved Journey")
def delete_saved_journey(
    journey_id: UUID,
    user: AuthenticatedUser = Depends(get_current_user),
):
    """Delete a saved journey.

    Security Guarantee: A user can only delete journeys they own (RLS enforced).
    """
    success = UserRepository.delete_saved_journey(user.id, journey_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Saved journey '{journey_id}' not found or not owned by current user.",
        )
    return None


# ─── Recent Searches Endpoints ────────────────────────────────────────────────

@router.get("/me/recent-searches", response_model=RecentSearchListResponse, summary="Get Recent Searches")
def get_recent_searches(
    limit: int = Query(20, ge=1, le=50, description="Max recent searches"),
    user: AuthenticatedUser = Depends(get_current_user),
):
    """Retrieve commuter's recent route searches under the bounded 20-item retention policy."""
    results = UserRepository.get_recent_searches(user.id, limit=limit)
    return RecentSearchListResponse(total=len(results), retention_limit=20, results=results)


@router.delete("/me/recent-searches", summary="Clear Search History")
def clear_recent_searches(user: AuthenticatedUser = Depends(get_current_user)):
    """Clear all recent search history for the authenticated user."""
    cleared_count = UserRepository.clear_recent_searches(user.id)
    return {"message": "Search history cleared successfully.", "deleted_count": cleared_count}


# ─── Feedback Endpoint ────────────────────────────────────────────────────────

@router.post("/feedback", response_model=UserFeedbackOut, status_code=status.HTTP_201_CREATED, summary="Submit Commuter Feedback")
def submit_feedback(
    feedback: UserFeedbackCreate,
    user: Optional[AuthenticatedUser] = Depends(get_optional_user),
):
    """Submit operational feedback or report schedule inaccuracies.

    Permits authenticated commuters or anonymous reports (when user token is omitted).
    Reports are queued for verification and never automatically alter GTFS ground truth.
    """
    user_id = user.id if user else None
    return UserRepository.create_feedback(user_id=user_id, feedback=feedback)

