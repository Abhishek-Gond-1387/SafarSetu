"""Tests for HerRoute Women's Safety Feedback feature."""
from datetime import datetime
from uuid import uuid4
import pytest
from app.repositories.safety_repository import SafetyRepository, InMemorySafetyStore
from app.schemas.safety import (
    SafetyExperienceEnum,
    SafetyFeedbackSubmitRequest,
    SegmentTypeEnum,
    TimeCategoryEnum,
)


def test_submit_safety_feedback():
    store = InMemorySafetyStore()
    user_id = uuid4()
    req = SafetyFeedbackSubmitRequest(
        journey_id="test_journey_1",
        route_id="route_metro_122_metro_80",
        segment_id="metro_122",
        segment_type=SegmentTypeEnum.METRO,
        segment_name="Rajiv Chowk",
        experience_rating=SafetyExperienceEnum.COMFORTABLE,
        safety_concerns=[],
        time_category=TimeCategoryEnum.DAYTIME,
    )

    out = store.submit_feedback(user_id, req)
    assert out.id is not None
    assert out.user_id == user_id
    assert out.segment_id == "metro_122"
    assert out.experience_rating == "comfortable"
    assert out.time_category == "daytime"


def test_prevent_duplicate_feedback():
    store = InMemorySafetyStore()
    user_id = uuid4()
    req = SafetyFeedbackSubmitRequest(
        journey_id="test_journey_dup",
        segment_id="walk_segment_1",
        segment_type=SegmentTypeEnum.WALKING,
        experience_rating=SafetyExperienceEnum.UNCOMFORTABLE,
        safety_concerns=["poor_lighting"],
    )

    # First submission succeeds
    store.submit_feedback(user_id, req)

    # Duplicate submission for same user, journey, and segment must fail
    with pytest.raises(ValueError, match="Duplicate review"):
        store.submit_feedback(user_id, req)


def test_rate_limiting():
    store = InMemorySafetyStore()
    user_id = uuid4()

    for i in range(5):
        store.submit_feedback(
            user_id,
            SafetyFeedbackSubmitRequest(
                journey_id=f"journey_{i}",
                segment_id=f"seg_{i}",
                experience_rating=SafetyExperienceEnum.COMFORTABLE,
            )
        )

    # 6th submission in 1 minute must raise rate limit
    with pytest.raises(ValueError, match="Rate limit exceeded"):
        store.submit_feedback(
            user_id,
            SafetyFeedbackSubmitRequest(
                journey_id="journey_6",
                segment_id="seg_6",
                experience_rating=SafetyExperienceEnum.COMFORTABLE,
            )
        )


def test_segment_aggregation_and_time_filters():
    store = InMemorySafetyStore()
    test_seg = "custom_test_station"

    # Add 2 daytime comfortable
    store.submit_feedback(uuid4(), SafetyFeedbackSubmitRequest(
        segment_id=test_seg,
        experience_rating=SafetyExperienceEnum.COMFORTABLE,
        time_category=TimeCategoryEnum.DAYTIME,
    ))
    store.submit_feedback(uuid4(), SafetyFeedbackSubmitRequest(
        segment_id=test_seg,
        experience_rating=SafetyExperienceEnum.COMFORTABLE,
        time_category=TimeCategoryEnum.DAYTIME,
    ))

    # Add 1 nighttime uncomfortable with concerns
    store.submit_feedback(uuid4(), SafetyFeedbackSubmitRequest(
        segment_id=test_seg,
        experience_rating=SafetyExperienceEnum.UNCOMFORTABLE,
        safety_concerns=["poor_lighting", "isolated_location"],
        time_category=TimeCategoryEnum.NIGHTTIME,
    ))

    # Overall
    summary = store.aggregate_segment_insights(test_seg, time_filter="all")
    assert summary.has_sufficient_data is True
    assert summary.total_reports == 3
    assert summary.comfortable_count == 2
    assert summary.uncomfortable_count == 1
    assert len(summary.frequent_concerns) >= 1
    assert summary.frequent_concerns[0].concern_key in ("poor_lighting", "isolated_location")

    # Filtered by nighttime
    night_summary = store.aggregate_segment_insights(test_seg, time_filter="nighttime")
    assert night_summary.total_reports == 1
    assert night_summary.comfortable_count == 0
    assert night_summary.uncomfortable_count == 1


def test_unreviewed_route_returns_insufficient_data():
    store = InMemorySafetyStore()
    summary, _ = store.aggregate_route_insights("unknown_route_9999", ["unknown_stop_1"])
    assert summary.has_sufficient_data is False
    assert summary.total_reports == 0
