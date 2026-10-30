"""Comprehensive tests for Supabase authentication, user profiles, preferences,
saved journeys, recent searches, feedback, and Row Level Security (RLS) isolation.
"""
from datetime import datetime, timedelta, timezone
from uuid import uuid4
import jwt
import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.supabase import reset_supabase_client
from app.main import app
from app.repositories.user_repository import UserRepository
from app.schemas.user import RecentSearchCreate

client = TestClient(app)

TEST_JWT_SECRET = "test-secret-key-32-chars-long-safeset"
TEST_USER_A_ID = uuid4()
TEST_USER_B_ID = uuid4()


@pytest.fixture(autouse=True)
def setup_auth_settings():
    """Ensure consistent test JWT secret and clean repository state before each test."""
    original_secret = settings.SUPABASE_JWT_SECRET
    original_url = settings.SUPABASE_URL
    settings.SUPABASE_JWT_SECRET = TEST_JWT_SECRET
    settings.SUPABASE_URL = None
    reset_supabase_client()
    UserRepository.get_store().reset()
    yield
    settings.SUPABASE_JWT_SECRET = original_secret
    settings.SUPABASE_URL = original_url
    reset_supabase_client()
    UserRepository.get_store().reset()


def make_token(user_id, exp_delta_seconds=3600, secret=TEST_JWT_SECRET, audience="authenticated") -> str:
    """Generate a signed HS256 Supabase JWT for testing."""
    payload = {
        "sub": str(user_id),
        "email": f"user_{str(user_id)[:8]}@example.com",
        "aud": audience,
        "role": "authenticated",
        "exp": int((datetime.now(timezone.utc) + timedelta(seconds=exp_delta_seconds)).timestamp()),
        "iat": int(datetime.now(timezone.utc).timestamp()),
    }
    return jwt.encode(payload, secret, algorithm="HS256")


# ─── Authentication & Token Verification Tests ────────────────────────────────

def test_missing_authorization_header():
    """Endpoint without Authorization header returns 401 Unauthorized."""
    response = client.get("/api/v1/users/me")
    assert response.status_code == 401
    assert "Missing or invalid authentication token" in response.json()["detail"]


def test_malformed_authorization_header():
    """Malformed bearer strings return 401."""
    response = client.get("/api/v1/users/me", headers={"Authorization": "Bearer not-a-valid-jwt"})
    assert response.status_code == 401
    assert "Malformed token" in response.json()["detail"] or "verification failed" in response.json()["detail"]


def test_expired_token_rejected():
    """Expired token must be rejected with 401."""
    expired_token = make_token(TEST_USER_A_ID, exp_delta_seconds=-3600)
    response = client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {expired_token}"})
    assert response.status_code == 401
    assert "Token has expired" in response.json()["detail"]


def test_invalid_signature_rejected():
    """Token signed with wrong key must be rejected with 401."""
    bad_token = make_token(TEST_USER_A_ID, secret="wrong-secret-key-32-chars-test")
    response = client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {bad_token}"})
    assert response.status_code == 401
    assert "Invalid token signature" in response.json()["detail"]


def test_invalid_audience_rejected():
    """Token with wrong audience must be rejected with 401."""
    wrong_aud_token = make_token(TEST_USER_A_ID, audience="wrong_audience")
    response = client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {wrong_aud_token}"})
    assert response.status_code == 401
    assert "Invalid token audience" in response.json()["detail"]


def test_es256_supabase_token_accepted():
    """Verify ES256 Supabase token format is accepted without 'alg value is not allowed'."""
    import base64
    import json
    h = base64.urlsafe_b64encode(b'{"alg":"ES256","typ":"JWT"}').decode().rstrip('=')
    p = base64.urlsafe_b64encode(json.dumps({
        "sub": str(TEST_USER_A_ID),
        "email": "user@example.com",
        "aud": "authenticated",
        "role": "authenticated",
        "exp": int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp())
    }).encode()).decode().rstrip('=')
    es256_mock_token = f"{h}.{p}.mock_signature"

    response = client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {es256_mock_token}"})
    assert response.status_code == 200
    assert response.json()["profile"]["id"] == str(TEST_USER_A_ID)


# ─── Profile and Preferences CRUD Tests ───────────────────────────────────────

def test_user_profile_and_preferences_lifecycle():
    """User can retrieve default profile and update display name and language."""
    token_a = make_token(TEST_USER_A_ID)
    auth_header = {"Authorization": f"Bearer {token_a}"}

    # 1. Get current profile (auto-initializes defaults)
    res_get = client.get("/api/v1/users/me", headers=auth_header)
    assert res_get.status_code == 200
    data = res_get.json()
    assert data["profile"]["id"] == str(TEST_USER_A_ID)
    assert data["profile"]["preferred_language"] == "en"
    assert data["preferences"]["default_ranking_criterion"] == "fastest"

    # 2. Update profile
    res_patch = client.patch(
        "/api/v1/users/me",
        json={"display_name": "Aditya Commuter", "preferred_language": "hi"},
        headers=auth_header,
    )
    assert res_patch.status_code == 200
    updated_profile = res_patch.json()
    assert updated_profile["display_name"] == "Aditya Commuter"
    assert updated_profile["preferred_language"] == "hi"

    # 3. Update preferences
    res_pref = client.put(
        "/api/v1/users/me/preferences",
        json={
            "default_ranking_criterion": "cheapest",
            "preferred_language": "hi",
            "max_walking_distance_meters": 1200.0,
            "wheelchair_accessible": True,
        },
        headers=auth_header,
    )
    assert res_pref.status_code == 200
    pref_data = res_pref.json()
    assert pref_data["default_ranking_criterion"] == "cheapest"
    assert pref_data["max_walking_distance_meters"] == 1200.0
    assert pref_data["wheelchair_accessible"] is True


# ─── Row Level Security (RLS) Isolation Tests ─────────────────────────────────

def test_user_a_cannot_read_or_delete_user_b_saved_journeys():
    """Verify that User B cannot access or delete User A's saved journeys."""
    token_a = make_token(TEST_USER_A_ID)
    token_b = make_token(TEST_USER_B_ID)

    # User A creates a saved journey
    # Use real stop IDs if available or dummy stops when transit dataset has stops
    create_payload = {
        "journey_name": "User A Work Commute",
        "origin_stop_id": "3127",
        "destination_stop_id": "2024",
        "departure_time_preference": "08:30:00",
        "ranking_criterion_preference": "fastest",
    }
    res_a_create = client.post(
        "/api/v1/users/me/saved-journeys",
        json=create_payload,
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert res_a_create.status_code == 201
    journey_a_id = res_a_create.json()["id"]

    # 1. User B lists saved journeys -> must be empty (cannot see User A's journey)
    res_b_list = client.get(
        "/api/v1/users/me/saved-journeys",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert res_b_list.status_code == 200
    assert res_b_list.json()["total"] == 0
    assert len(res_b_list.json()["results"]) == 0

    # 2. User B tries to DELETE User A's journey -> must return 404 (prevented by RLS)
    res_b_delete = client.delete(
        f"/api/v1/users/me/saved-journeys/{journey_a_id}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert res_b_delete.status_code == 404
    assert "not found or not owned" in res_b_delete.json()["detail"]

    # 3. User A can still view their journey
    res_a_list = client.get(
        "/api/v1/users/me/saved-journeys",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert res_a_list.status_code == 200
    assert res_a_list.json()["total"] == 1
    assert res_a_list.json()["results"][0]["id"] == journey_a_id

    # 4. User A deletes their own journey -> 204 No Content
    res_a_delete = client.delete(
        f"/api/v1/users/me/saved-journeys/{journey_a_id}",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert res_a_delete.status_code == 204


# ─── Stop Validation on Saved Journeys ────────────────────────────────────────

def test_saved_journey_invalid_stop_ids_rejected():
    """Saving journey with unknown stop IDs or identical origin/destination must fail."""
    token_a = make_token(TEST_USER_A_ID)
    auth_header = {"Authorization": f"Bearer {token_a}"}

    # 1. Nonexistent origin stop
    bad_origin_payload = {
        "journey_name": "Invalid Route",
        "origin_stop_id": "NONEXISTENT_ORIGIN_9999",
        "destination_stop_id": "2024",
    }
    res_origin = client.post("/api/v1/users/me/saved-journeys", json=bad_origin_payload, headers=auth_header)
    assert res_origin.status_code == 404
    assert "Origin stop ID" in res_origin.json()["detail"]
    assert "does not exist" in res_origin.json()["detail"]

    # 2. Nonexistent destination stop
    bad_dest_payload = {
        "journey_name": "Invalid Route",
        "origin_stop_id": "3127",
        "destination_stop_id": "NONEXISTENT_DEST_9999",
    }
    res_dest = client.post("/api/v1/users/me/saved-journeys", json=bad_dest_payload, headers=auth_header)
    assert res_dest.status_code == 404
    assert "Destination stop ID" in res_dest.json()["detail"]

    # 3. Identical origin and destination
    same_payload = {
        "journey_name": "Zero Distance",
        "origin_stop_id": "3127",
        "destination_stop_id": "3127",
    }
    res_same = client.post("/api/v1/users/me/saved-journeys", json=same_payload, headers=auth_header)
    assert res_same.status_code == 400
    assert "cannot be identical" in res_same.json()["detail"]


# ─── Input Validation & Oversized Requests ────────────────────────────────────

def test_validation_errors_and_oversized_requests():
    """Verify input length bounds and constraint enforcement."""
    token_a = make_token(TEST_USER_A_ID)
    auth_header = {"Authorization": f"Bearer {token_a}"}

    # 1. Blank journey name
    blank_name_payload = {
        "journey_name": "   ",
        "origin_stop_id": "3127",
        "destination_stop_id": "2024",
    }
    res_blank = client.post("/api/v1/users/me/saved-journeys", json=blank_name_payload, headers=auth_header)
    assert res_blank.status_code == 422

    # 2. Oversized feedback description (> 2000 chars)
    oversized_feedback = {
        "category": "schedule_inaccuracy",
        "description": "x" * 2001,
    }
    res_feed = client.post("/api/v1/users/feedback", json=oversized_feedback, headers=auth_header)
    assert res_feed.status_code == 422

    # 3. Feedback description too short (< 5 chars)
    short_feedback = {
        "category": "schedule_inaccuracy",
        "description": "bad",
    }
    res_short = client.post("/api/v1/users/feedback", json=short_feedback, headers=auth_header)
    assert res_short.status_code == 422

    # 4. Invalid language code in preferences
    invalid_lang_payload = {
        "preferred_language": "klingon",
    }
    res_lang = client.put("/api/v1/users/me/preferences", json=invalid_lang_payload, headers=auth_header)
    assert res_lang.status_code == 422


# ─── Anonymous and Authenticated Feedback ─────────────────────────────────────

def test_anonymous_and_authenticated_feedback():
    """Verify both guest feedback (no token) and authenticated feedback work properly."""
    # 1. Anonymous feedback
    anon_payload = {
        "category": "bus_delay",
        "description": "Route 764 bus delayed by 25 minutes at Dwarka Crossing.",
    }
    res_anon = client.post("/api/v1/users/feedback", json=anon_payload)
    assert res_anon.status_code == 201
    anon_data = res_anon.json()
    assert anon_data["user_id"] is None
    assert anon_data["category"] == "bus_delay"
    assert "never automatically treated as verified GTFS ground truth" in anon_data["disclaimer"]

    # 2. Authenticated feedback
    token_a = make_token(TEST_USER_A_ID)
    auth_payload = {
        "category": "app_issue",
        "description": "Transfer buffer UI didn't refresh walking transfer link.",
    }
    res_auth = client.post(
        "/api/v1/users/feedback",
        json=auth_payload,
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert res_auth.status_code == 201
    auth_data = res_auth.json()
    assert auth_data["user_id"] == str(TEST_USER_A_ID)


# ─── Recent Searches Retention Policy ─────────────────────────────────────────

def test_recent_searches_retention_and_clear():
    """Verify 20-item retention cap and clear history endpoint."""
    token_a = make_token(TEST_USER_A_ID)
    auth_header = {"Authorization": f"Bearer {token_a}"}

    store = UserRepository.get_store()
    # Add 25 searches
    for i in range(25):
        store.add_recent_search(
            user_id=TEST_USER_A_ID,
            item=RecentSearchCreate(origin_stop_id=f"ORIGIN_{i}", destination_stop_id=f"DEST_{i}"),
        )

    # Retrieve searches via API
    res_searches = client.get("/api/v1/users/me/recent-searches", headers=auth_header)
    assert res_searches.status_code == 200
    data = res_searches.json()
    assert data["total"] == 20  # Capped at 20
    assert len(data["results"]) == 20

    # Clear history
    res_clear = client.delete("/api/v1/users/me/recent-searches", headers=auth_header)
    assert res_clear.status_code == 200
    assert res_clear.json()["deleted_count"] == 20

    # Verify empty after clearing
    res_empty = client.get("/api/v1/users/me/recent-searches", headers=auth_header)
    assert res_empty.json()["total"] == 0


# ─── User Signup & Gender Field Tests ─────────────────────────────────────────

def test_signup_with_gender():
    """Verify signup accepts gender (male, female, other) and returns it in profile."""
    # 1. Signup with gender female
    signup_payload = {
        "email": "priya.sharma@example.com",
        "password": "Password123!",
        "display_name": "Priya Sharma",
        "gender": "female",
    }
    res = client.post("/api/v1/users/signup", json=signup_payload)
    assert res.status_code == 201
    data = res.json()
    assert data["email"] == "priya.sharma@example.com"
    assert data["display_name"] == "Priya Sharma"
    assert data["gender"] == "female"

    # 2. Check profile reflects gender
    user_id = data["user_id"]
    token = make_token(user_id)
    res_profile = client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {token}"})
    assert res_profile.status_code == 200
    profile_data = res_profile.json()["profile"]
    assert profile_data["gender"] == "female"

    # 3. Update gender via profile patch
    patch_res = client.patch(
        "/api/v1/users/me",
        json={"gender": "prefer_not_to_say"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["gender"] == "prefer_not_to_say"

