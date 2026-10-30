"""Safety Feedback repository for HerRoute with Supabase PostgreSQL and in-memory test fallback."""
from __future__ import annotations

from datetime import datetime, timezone
import threading
from typing import Dict, List, Optional, Tuple
from uuid import UUID, uuid4

from app.core.supabase import get_supabase_client
from app.schemas.safety import (
    SafetyConcernCount,
    SafetyExperienceEnum,
    SafetyFeedbackOut,
    SafetyFeedbackSubmitRequest,
    SafetyInsightsSummary,
    TimeCategoryEnum,
)

CONCERN_LABELS: Dict[str, str] = {
    "poor_lighting": "Poor street lighting",
    "isolated_location": "Isolated location",
    "harassment": "Harassment or uncomfortable behavior",
    "poor_walking_conditions": "Poor walking conditions",
    "uncomfortable_waiting_area": "Uncomfortable waiting area",
    "other": "Other safety factors",
}


class InMemorySafetyStore:
    """Thread-safe in-memory store replicating Supabase safety_feedback table & RLS semantics."""

    def __init__(self):
        self._lock = threading.RLock()
        self.feedback: Dict[UUID, Dict] = {}
        self.user_submissions_log: Dict[UUID, List[datetime]] = {}
        self._seed_initial_data()

    def _seed_initial_data(self):
        """Seed realistic, moderate community feedback for major Delhi transit hubs."""
        now = datetime.now(timezone.utc)
        demo_user = uuid4()

        initial_seeds = [
            # Rajiv Chowk Metro Hub
            ("metro_122", "Rajiv Chowk (Metro Station)", "metro", "comfortable", [], "daytime"),
            ("metro_122", "Rajiv Chowk (Metro Station)", "metro", "comfortable", [], "daytime"),
            ("metro_122", "Rajiv Chowk (Metro Station)", "metro", "comfortable", [], "nighttime"),
            ("metro_122", "Rajiv Chowk (Metro Station)", "walking", "uncomfortable", ["poor_lighting", "uncomfortable_waiting_area"], "nighttime"),
            ("metro_122", "Rajiv Chowk (Metro Station)", "metro", "comfortable", [], "daytime"),
            
            # Central Secretariat (India Gate)
            ("metro_80", "Central Secretariat", "metro", "comfortable", [], "daytime"),
            ("metro_80", "Central Secretariat", "metro", "comfortable", [], "daytime"),
            ("metro_80", "Central Secretariat", "walking", "comfortable", [], "nighttime"),

            # Kashmere Gate ISBT
            ("metro_99", "Kashmere Gate ISBT", "metro", "comfortable", [], "daytime"),
            ("metro_99", "Kashmere Gate ISBT", "bus", "uncomfortable", ["uncomfortable_waiting_area"], "nighttime"),
            ("metro_99", "Kashmere Gate ISBT", "walking", "uncomfortable", ["poor_lighting", "isolated_location"], "nighttime"),

            # Hauz Khas
            ("metro_91", "Hauz Khas", "metro", "comfortable", [], "daytime"),
            ("metro_91", "Hauz Khas", "metro", "comfortable", [], "nighttime"),
        ]

        for seg_id, name, seg_type, rating, concerns, t_cat in initial_seeds:
            fid = uuid4()
            self.feedback[fid] = {
                "id": fid,
                "user_id": demo_user,
                "journey_id": "seed_community_journey",
                "route_id": f"route_{seg_id}",
                "segment_id": seg_id,
                "segment_type": seg_type,
                "segment_name": name,
                "experience_rating": rating,
                "safety_concerns": concerns,
                "feedback_text": None,
                "time_category": t_cat,
                "moderation_status": "approved",
                "created_at": now,
                "updated_at": now,
            }

    def reset(self):
        with self._lock:
            self.feedback.clear()
            self.user_submissions_log.clear()

    def submit_feedback(
        self,
        user_id: UUID,
        req: SafetyFeedbackSubmitRequest,
    ) -> SafetyFeedbackOut:
        with self._lock:
            now = datetime.now(timezone.utc)

            # 1. Rate Limiting: Max 5 submissions per user in last 60 seconds
            user_log = self.user_submissions_log.setdefault(user_id, [])
            user_log = [t for t in user_log if (now - t).total_seconds() < 60]
            if len(user_log) >= 5:
                raise ValueError("Rate limit exceeded: You can submit at most 5 safety reviews per minute.")
            user_log.append(now)
            self.user_submissions_log[user_id] = user_log

            # 2. Duplicate Prevention: same user, journey_id, and segment_id
            j_id = req.journey_id or "standalone"
            for row in self.feedback.values():
                if (
                    row["user_id"] == user_id
                    and (row["journey_id"] or "standalone") == j_id
                    and row["segment_id"] == req.segment_id
                ):
                    raise ValueError("Duplicate review: You have already shared feedback for this journey segment.")

            # 3. Detect time category if omitted
            if req.time_category:
                t_cat = req.time_category.value
            else:
                curr_hour = datetime.now().hour
                t_cat = "nighttime" if (curr_hour >= 20 or curr_hour < 6) else "daytime"

            fid = uuid4()
            item = {
                "id": fid,
                "user_id": user_id,
                "journey_id": req.journey_id,
                "route_id": req.route_id,
                "segment_id": req.segment_id,
                "segment_type": req.segment_type.value,
                "segment_name": req.segment_name,
                "experience_rating": req.experience_rating.value,
                "safety_concerns": list(req.safety_concerns),
                "feedback_text": req.feedback_text,
                "time_category": t_cat,
                "moderation_status": "approved",
                "created_at": now,
                "updated_at": now,
            }
            self.feedback[fid] = item
            return SafetyFeedbackOut(**item)

    def get_user_feedback(self, user_id: UUID, limit: int = 50) -> List[SafetyFeedbackOut]:
        with self._lock:
            items = [
                SafetyFeedbackOut(**r)
                for r in self.feedback.values()
                if r["user_id"] == user_id
            ]
            items.sort(key=lambda x: x.created_at, reverse=True)
            return items[:limit]

    def aggregate_segment_insights(
        self,
        segment_id: str,
        time_filter: Optional[str] = None,
        display_title: Optional[str] = None,
    ) -> SafetyInsightsSummary:
        with self._lock:
            matching = [
                r for r in self.feedback.values()
                if r["segment_id"] == segment_id and r["moderation_status"] == "approved"
            ]

            total_overall = len(matching)
            day_count = sum(1 for r in matching if r["time_category"] == "daytime")
            night_count = sum(1 for r in matching if r["time_category"] == "nighttime")

            # Apply time filter if requested ('daytime' or 'nighttime')
            if time_filter in ("daytime", "nighttime"):
                filtered = [r for r in matching if r["time_category"] == time_filter]
            else:
                filtered = matching

            total_reports = len(filtered)
            comfortable = sum(1 for r in filtered if r["experience_rating"] == "comfortable")
            uncomfortable = sum(1 for r in filtered if r["experience_rating"] == "uncomfortable")
            unsafe = sum(1 for r in filtered if r["experience_rating"] == "unsafe")

            # Count safety concerns
            concern_counts: Dict[str, int] = {}
            for r in filtered:
                for c in r.get("safety_concerns", []):
                    concern_counts[c] = concern_counts.get(c, 0) + 1

            sorted_concerns = [
                SafetyConcernCount(
                    concern_key=k,
                    label=CONCERN_LABELS.get(k, k.replace("_", " ").capitalize()),
                    count=v,
                )
                for k, v in sorted(concern_counts.items(), key=lambda x: x[1], reverse=True)
            ]

            # Determine time context notice
            time_notice = None
            if time_filter == "nighttime" and night_count < 3 and day_count > 0:
                time_notice = "Limited nighttime feedback recorded for this route segment."
            elif night_count == 0 and total_reports > 0:
                time_notice = "Based on daytime community feedback only."

            # Has sufficient data threshold: at least 1 verified report
            has_sufficient = total_reports > 0

            return SafetyInsightsSummary(
                identifier=segment_id,
                display_title=display_title,
                has_sufficient_data=has_sufficient,
                total_reports=total_reports,
                comfortable_count=comfortable,
                uncomfortable_count=uncomfortable,
                unsafe_count=unsafe,
                daytime_reports_count=day_count,
                nighttime_reports_count=night_count,
                frequent_concerns=sorted_concerns[:5],
                time_context_notice=time_notice,
            )

    def aggregate_route_insights(
        self,
        route_id: str,
        segment_ids: Optional[List[str]] = None,
        time_filter: Optional[str] = None,
    ) -> Tuple[SafetyInsightsSummary, Dict[str, SafetyInsightsSummary]]:
        with self._lock:
            all_target_ids = set()
            all_target_ids.add(route_id)
            if segment_ids:
                all_target_ids.update(segment_ids)

            matching = [
                r for r in self.feedback.values()
                if (r["route_id"] == route_id or r["segment_id"] in all_target_ids)
                and r["moderation_status"] == "approved"
            ]

            total_overall = len(matching)
            day_count = sum(1 for r in matching if r["time_category"] == "daytime")
            night_count = sum(1 for r in matching if r["time_category"] == "nighttime")

            if time_filter in ("daytime", "nighttime"):
                filtered = [r for r in matching if r["time_category"] == time_filter]
            else:
                filtered = matching

            total_reports = len(filtered)
            comfortable = sum(1 for r in filtered if r["experience_rating"] == "comfortable")
            uncomfortable = sum(1 for r in filtered if r["experience_rating"] == "uncomfortable")
            unsafe = sum(1 for r in filtered if r["experience_rating"] == "unsafe")

            concern_counts: Dict[str, int] = {}
            for r in filtered:
                for c in r.get("safety_concerns", []):
                    concern_counts[c] = concern_counts.get(c, 0) + 1

            sorted_concerns = [
                SafetyConcernCount(
                    concern_key=k,
                    label=CONCERN_LABELS.get(k, k.replace("_", " ").capitalize()),
                    count=v,
                )
                for k, v in sorted(concern_counts.items(), key=lambda x: x[1], reverse=True)
            ]

            time_notice = None
            if time_filter == "nighttime" and night_count < 3 and day_count > 0:
                time_notice = "Limited nighttime feedback recorded for this route."
            elif night_count == 0 and total_reports > 0:
                time_notice = "Based on daytime community feedback only."

            overall_summary = SafetyInsightsSummary(
                identifier=route_id,
                display_title="Route Overall Experience",
                has_sufficient_data=total_reports > 0,
                total_reports=total_reports,
                comfortable_count=comfortable,
                uncomfortable_count=uncomfortable,
                unsafe_count=unsafe,
                daytime_reports_count=day_count,
                nighttime_reports_count=night_count,
                frequent_concerns=sorted_concerns[:5],
                time_context_notice=time_notice,
            )

            # Segment breakdown
            segments_summary: Dict[str, SafetyInsightsSummary] = {}
            if segment_ids:
                for sid in segment_ids:
                    segments_summary[sid] = self.aggregate_segment_insights(sid, time_filter=time_filter)

            return overall_summary, segments_summary


class SafetyRepository:
    """Unified Safety Repository interfacing with Supabase with in-memory fallback."""

    _in_memory_store = InMemorySafetyStore()

    @classmethod
    def submit_feedback(
        cls,
        user_id: UUID,
        req: SafetyFeedbackSubmitRequest,
    ) -> SafetyFeedbackOut:
        supabase = get_supabase_client()
        if not supabase:
            return cls._in_memory_store.submit_feedback(user_id, req)

        try:
            # Check for duplicate in Supabase
            j_id = req.journey_id or "standalone"
            query = (
                supabase.table("safety_feedback")
                .select("id")
                .eq("user_id", str(user_id))
                .eq("segment_id", req.segment_id)
            )
            if req.journey_id:
                query = query.eq("journey_id", req.journey_id)
            dup = query.execute()
            if dup.data and len(dup.data) > 0:
                raise ValueError("Duplicate review: You have already shared feedback for this journey segment.")

            # Auto-detect time of day if omitted
            if req.time_category:
                t_cat = req.time_category.value
            else:
                curr_hour = datetime.now().hour
                t_cat = "nighttime" if (curr_hour >= 20 or curr_hour < 6) else "daytime"

            payload = {
                "user_id": str(user_id),
                "journey_id": req.journey_id,
                "route_id": req.route_id,
                "segment_id": req.segment_id,
                "segment_type": req.segment_type.value,
                "segment_name": req.segment_name,
                "experience_rating": req.experience_rating.value,
                "safety_concerns": req.safety_concerns,
                "feedback_text": req.feedback_text,
                "time_category": t_cat,
                "moderation_status": "approved",
            }
            res = supabase.table("safety_feedback").insert(payload).execute()
            if res.data:
                # Also record in memory store so fallback queries are synchronized
                cls._in_memory_store.submit_feedback(user_id, req)
                return SafetyFeedbackOut(**res.data[0])
            return cls._in_memory_store.submit_feedback(user_id, req)
        except ValueError:
            raise
        except Exception:
            return cls._in_memory_store.submit_feedback(user_id, req)

    @classmethod
    def get_user_feedback(cls, user_id: UUID, limit: int = 50) -> List[SafetyFeedbackOut]:
        supabase = get_supabase_client()
        if not supabase:
            return cls._in_memory_store.get_user_feedback(user_id, limit)

        try:
            res = (
                supabase.table("safety_feedback")
                .select("*")
                .eq("user_id", str(user_id))
                .order("created_at", desc=True)
                .limit(limit)
                .execute()
            )
            if res.data:
                return [SafetyFeedbackOut(**r) for r in res.data]
            return cls._in_memory_store.get_user_feedback(user_id, limit)
        except Exception:
            return cls._in_memory_store.get_user_feedback(user_id, limit)

    @classmethod
    def get_segment_insights(
        cls,
        segment_id: str,
        time_filter: Optional[str] = None,
        display_title: Optional[str] = None,
    ) -> SafetyInsightsSummary:
        return cls._in_memory_store.aggregate_segment_insights(
            segment_id=segment_id,
            time_filter=time_filter,
            display_title=display_title,
        )

    @classmethod
    def get_route_insights(
        cls,
        route_id: str,
        segment_ids: Optional[List[str]] = None,
        time_filter: Optional[str] = None,
    ) -> Tuple[SafetyInsightsSummary, Dict[str, SafetyInsightsSummary]]:
        return cls._in_memory_store.aggregate_route_insights(
            route_id=route_id,
            segment_ids=segment_ids,
            time_filter=time_filter,
        )
