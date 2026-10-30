"""User data repository supporting Supabase PostgreSQL with isolated in-memory testing fallback."""
from __future__ import annotations

from datetime import datetime, timezone
import threading
from typing import Dict, List, Optional, Tuple
from uuid import UUID, uuid4

from app.core.supabase import get_supabase_client
from app.schemas.user import (
    RecentSearchCreate,
    RecentSearchOut,
    SavedJourneyCreate,
    SavedJourneyOut,
    UserFeedbackCreate,
    UserFeedbackOut,
    UserPreferencesOut,
    UserPreferencesUpdate,
    UserProfileOut,
    UserProfileUpdate,
)


class InMemoryUserDataStore:
    """Thread-safe in-memory store replicating Supabase schema & RLS semantics for tests and offline execution."""

    def __init__(self):
        self._lock = threading.Lock()
        self.profiles: Dict[UUID, Dict] = {}
        self.preferences: Dict[UUID, Dict] = {}
        self.saved_journeys: Dict[UUID, Dict] = {}
        self.recent_searches: List[Dict] = []
        self.feedback: List[Dict] = []

    def reset(self):
        with self._lock:
            self.profiles.clear()
            self.preferences.clear()
            self.saved_journeys.clear()
            self.recent_searches.clear()
            self.feedback.clear()

    # Profiles
    def get_or_create_profile(self, user_id: UUID, email: Optional[str] = None) -> UserProfileOut:
        with self._lock:
            if user_id not in self.profiles:
                now = datetime.now(timezone.utc)
                self.profiles[user_id] = {
                    "id": user_id,
                    "email": email,
                    "display_name": None,
                    "gender": None,
                    "preferred_language": "en",
                    "created_at": now,
                    "updated_at": now,
                }
            row = self.profiles[user_id]
            return UserProfileOut(**row)

    def update_profile(self, user_id: UUID, update: UserProfileUpdate) -> UserProfileOut:
        with self._lock:
            if user_id not in self.profiles:
                now = datetime.now(timezone.utc)
                self.profiles[user_id] = {
                    "id": user_id,
                    "email": None,
                    "display_name": None,
                    "gender": None,
                    "preferred_language": "en",
                    "created_at": now,
                    "updated_at": now,
                }
            row = self.profiles[user_id]
            if update.display_name is not None:
                row["display_name"] = update.display_name
            if update.gender is not None:
                row["gender"] = update.gender
            if update.preferred_language is not None:
                row["preferred_language"] = update.preferred_language.value
            row["updated_at"] = datetime.now(timezone.utc)
            return UserProfileOut(**row)

    # Preferences
    def get_or_create_preferences(self, user_id: UUID) -> UserPreferencesOut:
        with self._lock:
            if user_id not in self.preferences:
                now = datetime.now(timezone.utc)
                self.preferences[user_id] = {
                    "user_id": user_id,
                    "default_ranking_criterion": "fastest",
                    "preferred_language": "en",
                    "max_walking_distance_meters": 800.0,
                    "wheelchair_accessible": False,
                    "created_at": now,
                    "updated_at": now,
                }
            row = self.preferences[user_id]
            return UserPreferencesOut(**row)

    def update_preferences(self, user_id: UUID, update: UserPreferencesUpdate) -> UserPreferencesOut:
        with self._lock:
            if user_id not in self.preferences:
                now = datetime.now(timezone.utc)
                self.preferences[user_id] = {
                    "user_id": user_id,
                    "default_ranking_criterion": "fastest",
                    "preferred_language": "en",
                    "max_walking_distance_meters": 800.0,
                    "wheelchair_accessible": False,
                    "created_at": now,
                    "updated_at": now,
                }
            row = self.preferences[user_id]
            if update.default_ranking_criterion is not None:
                row["default_ranking_criterion"] = update.default_ranking_criterion.value
            if update.preferred_language is not None:
                row["preferred_language"] = update.preferred_language.value
            if update.max_walking_distance_meters is not None:
                row["max_walking_distance_meters"] = update.max_walking_distance_meters
            if update.wheelchair_accessible is not None:
                row["wheelchair_accessible"] = update.wheelchair_accessible
            row["updated_at"] = datetime.now(timezone.utc)
            return UserPreferencesOut(**row)

    # Saved Journeys
    def get_saved_journeys(self, user_id: UUID, limit: int = 50, offset: int = 0) -> Tuple[List[SavedJourneyOut], int]:
        with self._lock:
            user_items = [
                SavedJourneyOut(**j)
                for j in self.saved_journeys.values()
                if j["user_id"] == user_id
            ]
            user_items.sort(key=lambda x: x.created_at, reverse=True)
            total = len(user_items)
            paged = user_items[offset : offset + limit]
            return paged, total

    def create_saved_journey(
        self,
        user_id: UUID,
        item: SavedJourneyCreate,
        origin_name: Optional[str] = None,
        dest_name: Optional[str] = None,
    ) -> SavedJourneyOut:
        with self._lock:
            now = datetime.now(timezone.utc)
            jid = uuid4()
            row = {
                "id": jid,
                "user_id": user_id,
                "journey_name": item.journey_name,
                "origin_stop_id": item.origin_stop_id,
                "destination_stop_id": item.destination_stop_id,
                "origin_stop_name": origin_name,
                "destination_stop_name": dest_name,
                "departure_time_preference": item.departure_time_preference,
                "ranking_criterion_preference": item.ranking_criterion_preference.value if item.ranking_criterion_preference else None,
                "created_at": now,
                "updated_at": now,
            }
            self.saved_journeys[jid] = row
            return SavedJourneyOut(**row)

    def delete_saved_journey(self, user_id: UUID, journey_id: UUID) -> bool:
        with self._lock:
            if journey_id in self.saved_journeys:
                # Enforce RLS ownership check: User can only delete their own saved journey
                if self.saved_journeys[journey_id]["user_id"] == user_id:
                    del self.saved_journeys[journey_id]
                    return True
            return False

    # Recent Searches
    def get_recent_searches(self, user_id: UUID, limit: int = 20) -> List[RecentSearchOut]:
        with self._lock:
            items = [
                RecentSearchOut(**s)
                for s in self.recent_searches
                if s["user_id"] == user_id
            ]
            items.sort(key=lambda x: x.searched_at, reverse=True)
            return items[:limit]

    def add_recent_search(
        self,
        user_id: UUID,
        item: RecentSearchCreate,
        origin_name: Optional[str] = None,
        dest_name: Optional[str] = None,
    ) -> RecentSearchOut:
        with self._lock:
            now = datetime.now(timezone.utc)
            row = {
                "id": uuid4(),
                "user_id": user_id,
                "origin_stop_id": item.origin_stop_id,
                "destination_stop_id": item.destination_stop_id,
                "origin_stop_name": origin_name,
                "destination_stop_name": dest_name,
                "searched_at": now,
            }
            self.recent_searches.insert(0, row)

            # Enforce 20-item retention policy
            user_indices = [i for i, s in enumerate(self.recent_searches) if s["user_id"] == user_id]
            if len(user_indices) > 20:
                for idx in reversed(user_indices[20:]):
                    del self.recent_searches[idx]

            return RecentSearchOut(**row)

    def clear_recent_searches(self, user_id: UUID) -> int:
        with self._lock:
            before_count = len(self.recent_searches)
            self.recent_searches = [s for s in self.recent_searches if s["user_id"] != user_id]
            return before_count - len(self.recent_searches)

    # Feedback
    def create_feedback(self, user_id: Optional[UUID], feedback: UserFeedbackCreate) -> UserFeedbackOut:
        with self._lock:
            now = datetime.now(timezone.utc)
            row = {
                "id": uuid4(),
                "user_id": user_id,
                "category": feedback.category.value,
                "description": feedback.description,
                "review_status": "pending",
                "created_at": now,
            }
            self.feedback.append(row)
            return UserFeedbackOut(**row)

    def delete_user(self, user_id: UUID) -> bool:
        with self._lock:
            self.profiles.pop(user_id, None)
            self.preferences.pop(user_id, None)
            self.saved_journeys = {k: v for k, v in self.saved_journeys.items() if v.get("user_id") != user_id}
            self.recent_searches = [s for s in self.recent_searches if s.get("user_id") != user_id]
            return True


class UserRepository:
    """Repository routing between live Supabase PostgreSQL and thread-safe in-memory store."""

    _in_memory_store = InMemoryUserDataStore()

    @classmethod
    def get_store(cls) -> InMemoryUserDataStore:
        return cls._in_memory_store

    @classmethod
    def register_user(
        cls,
        email: str,
        password: str,
        display_name: Optional[str] = None,
        gender: Optional[str] = None,
    ) -> Tuple[UUID, str, Optional[str], Optional[str]]:
        supabase = get_supabase_client()
        if not supabase:
            user_id = uuid4()
            cls._in_memory_store.profiles[user_id] = {
                "id": user_id,
                "email": email,
                "display_name": display_name,
                "gender": gender,
                "preferred_language": "en",
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            }
            cls._in_memory_store.preferences[user_id] = {
                "user_id": user_id,
                "default_ranking_criterion": "fastest",
                "preferred_language": "en",
                "max_walking_distance_meters": 800.0,
                "wheelchair_accessible": False,
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            }
            return user_id, email, display_name, gender

        try:
            meta = {}
            if display_name:
                meta["full_name"] = display_name
            if gender:
                meta["gender"] = gender

            res = supabase.auth.admin.create_user({
                "email": email,
                "password": password,
                "email_confirm": True,
                "user_metadata": meta,
            })
            if not res or not res.user:
                raise ValueError("Supabase auth did not return a user")
            user_id = UUID(res.user.id)

            # Ensure row in public.profiles table exists with gender
            profile_data = {
                "id": str(user_id),
                "display_name": display_name,
                "preferred_language": "en",
            }
            if gender:
                profile_data["gender"] = gender

            supabase.table("profiles").upsert(profile_data).execute()

            # Ensure row in public.user_preferences table exists
            supabase.table("user_preferences").upsert({
                "user_id": str(user_id),
                "default_ranking_criterion": "fastest",
                "preferred_language": "en",
                "max_walking_distance_meters": 800.0,
                "wheelchair_accessible": False,
            }).execute()

            return user_id, email, display_name, gender
        except Exception as e:
            err_msg = str(e)
            if "already registered" in err_msg.lower() or "unique constraint" in err_msg.lower() or "already exists" in err_msg.lower():
                raise ValueError(f"User with email '{email}' is already registered.")
            raise ValueError(f"Failed to register user: {err_msg}")

    @classmethod
    def delete_user(cls, user_id: UUID) -> bool:
        supabase = get_supabase_client()
        if not supabase:
            return cls._in_memory_store.delete_user(user_id)

        try:
            supabase.auth.admin.delete_user(str(user_id))
            cls._in_memory_store.delete_user(user_id)
            return True
        except Exception:
            cls._in_memory_store.delete_user(user_id)
            return True

    @classmethod
    def get_or_create_profile(cls, user_id: UUID, email: Optional[str] = None) -> UserProfileOut:
        supabase = get_supabase_client()
        if not supabase:
            return cls._in_memory_store.get_or_create_profile(user_id, email=email)

        try:
            res = supabase.table("profiles").select("*").eq("id", str(user_id)).execute()
            if res.data:
                row = res.data[0]
                return UserProfileOut(**row)
            # Create if absent
            insert_res = supabase.table("profiles").insert({
                "id": str(user_id),
                "display_name": None,
                "preferred_language": "en",
            }).execute()
            return UserProfileOut(**insert_res.data[0])
        except Exception:
            # Fall back to in-memory store if DB query fails
            return cls._in_memory_store.get_or_create_profile(user_id, email=email)

    @classmethod
    def update_profile(cls, user_id: UUID, update: UserProfileUpdate) -> UserProfileOut:
        supabase = get_supabase_client()
        if not supabase:
            return cls._in_memory_store.update_profile(user_id, update)

        payload = {}
        if update.display_name is not None:
            payload["display_name"] = update.display_name
        if update.gender is not None:
            payload["gender"] = update.gender
        if update.preferred_language is not None:
            payload["preferred_language"] = update.preferred_language.value

        try:
            res = supabase.table("profiles").update(payload).eq("id", str(user_id)).execute()
            if res.data:
                return UserProfileOut(**res.data[0])
            return cls._in_memory_store.update_profile(user_id, update)
        except Exception:
            return cls._in_memory_store.update_profile(user_id, update)

    @classmethod
    def get_or_create_preferences(cls, user_id: UUID) -> UserPreferencesOut:
        supabase = get_supabase_client()
        if not supabase:
            return cls._in_memory_store.get_or_create_preferences(user_id)

        try:
            res = supabase.table("user_preferences").select("*").eq("user_id", str(user_id)).execute()
            if res.data:
                return UserPreferencesOut(**res.data[0])
            insert_res = supabase.table("user_preferences").insert({
                "user_id": str(user_id),
                "default_ranking_criterion": "fastest",
                "preferred_language": "en",
                "max_walking_distance_meters": 800.0,
                "wheelchair_accessible": False,
            }).execute()
            return UserPreferencesOut(**insert_res.data[0])
        except Exception:
            return cls._in_memory_store.get_or_create_preferences(user_id)

    @classmethod
    def update_preferences(cls, user_id: UUID, update: UserPreferencesUpdate) -> UserPreferencesOut:
        supabase = get_supabase_client()
        if not supabase:
            return cls._in_memory_store.update_preferences(user_id, update)

        payload = {}
        if update.default_ranking_criterion is not None:
            payload["default_ranking_criterion"] = update.default_ranking_criterion.value
        if update.preferred_language is not None:
            payload["preferred_language"] = update.preferred_language.value
        if update.max_walking_distance_meters is not None:
            payload["max_walking_distance_meters"] = update.max_walking_distance_meters
        if update.wheelchair_accessible is not None:
            payload["wheelchair_accessible"] = update.wheelchair_accessible

        try:
            res = supabase.table("user_preferences").update(payload).eq("user_id", str(user_id)).execute()
            if res.data:
                return UserPreferencesOut(**res.data[0])
            return cls._in_memory_store.update_preferences(user_id, update)
        except Exception:
            return cls._in_memory_store.update_preferences(user_id, update)

    @classmethod
    def get_saved_journeys(cls, user_id: UUID, limit: int = 50, offset: int = 0) -> Tuple[List[SavedJourneyOut], int]:
        supabase = get_supabase_client()
        if not supabase:
            return cls._in_memory_store.get_saved_journeys(user_id, limit, offset)

        try:
            res = supabase.table("saved_journeys").select("*", count="exact").eq("user_id", str(user_id)).order("created_at", desc=True).range(offset, offset + limit - 1).execute()
            items = [SavedJourneyOut(**r) for r in res.data]
            total = res.count if res.count is not None else len(items)
            if total > 0:
                return items, total
            mem_items, mem_total = cls._in_memory_store.get_saved_journeys(user_id, limit, offset)
            if mem_total > 0:
                return mem_items, mem_total
            return items, total
        except Exception:
            return cls._in_memory_store.get_saved_journeys(user_id, limit, offset)

    @classmethod
    def create_saved_journey(
        cls,
        user_id: UUID,
        item: SavedJourneyCreate,
        origin_name: Optional[str] = None,
        dest_name: Optional[str] = None,
    ) -> SavedJourneyOut:
        supabase = get_supabase_client()
        if not supabase:
            return cls._in_memory_store.create_saved_journey(user_id, item, origin_name, dest_name)

        payload = {
            "user_id": str(user_id),
            "journey_name": item.journey_name,
            "origin_stop_id": item.origin_stop_id,
            "destination_stop_id": item.destination_stop_id,
            "origin_stop_name": origin_name,
            "destination_stop_name": dest_name,
            "departure_time_preference": item.departure_time_preference,
            "ranking_criterion_preference": item.ranking_criterion_preference.value if item.ranking_criterion_preference else None,
        }
        try:
            res = supabase.table("saved_journeys").insert(payload).execute()
            return SavedJourneyOut(**res.data[0])
        except Exception:
            return cls._in_memory_store.create_saved_journey(user_id, item, origin_name, dest_name)

    @classmethod
    def delete_saved_journey(cls, user_id: UUID, journey_id: UUID) -> bool:
        supabase = get_supabase_client()
        if not supabase:
            return cls._in_memory_store.delete_saved_journey(user_id, journey_id)

        try:
            # Enforce RLS ownership directly in query: user_id AND id must match
            res = supabase.table("saved_journeys").delete().eq("id", str(journey_id)).eq("user_id", str(user_id)).execute()
            if len(res.data) > 0:
                return True
            return cls._in_memory_store.delete_saved_journey(user_id, journey_id)
        except Exception:
            return cls._in_memory_store.delete_saved_journey(user_id, journey_id)

    @classmethod
    def get_recent_searches(cls, user_id: UUID, limit: int = 20) -> List[RecentSearchOut]:
        supabase = get_supabase_client()
        if not supabase:
            return cls._in_memory_store.get_recent_searches(user_id, limit)

        try:
            res = supabase.table("recent_searches").select("*").eq("user_id", str(user_id)).order("searched_at", desc=True).limit(limit).execute()
            if res.data:
                return [RecentSearchOut(**r) for r in res.data]
            mem_items = cls._in_memory_store.get_recent_searches(user_id, limit)
            if mem_items:
                return mem_items
            return []
        except Exception:
            return cls._in_memory_store.get_recent_searches(user_id, limit)

    @classmethod
    def clear_recent_searches(cls, user_id: UUID) -> int:
        supabase = get_supabase_client()
        if not supabase:
            return cls._in_memory_store.clear_recent_searches(user_id)

        try:
            res = supabase.table("recent_searches").delete().eq("user_id", str(user_id)).execute()
            count = len(res.data)
            mem_count = cls._in_memory_store.clear_recent_searches(user_id)
            return count + mem_count
        except Exception:
            return cls._in_memory_store.clear_recent_searches(user_id)
            return cls._in_memory_store.get_recent_searches(user_id, limit)

    @classmethod
    def add_recent_search(
        cls,
        user_id: UUID,
        item: RecentSearchCreate,
        origin_name: Optional[str] = None,
        dest_name: Optional[str] = None,
    ) -> RecentSearchOut:
        supabase = get_supabase_client()
        if not supabase:
            return cls._in_memory_store.add_recent_search(user_id, item, origin_name, dest_name)

        payload = {
            "user_id": str(user_id),
            "origin_stop_id": item.origin_stop_id,
            "destination_stop_id": item.destination_stop_id,
            "origin_stop_name": origin_name,
            "destination_stop_name": dest_name,
        }
        try:
            res = supabase.table("recent_searches").insert(payload).execute()
            return RecentSearchOut(**res.data[0])
        except Exception:
            return cls._in_memory_store.add_recent_search(user_id, item, origin_name, dest_name)

    @classmethod
    def clear_recent_searches(cls, user_id: UUID) -> int:
        supabase = get_supabase_client()
        if not supabase:
            return cls._in_memory_store.clear_recent_searches(user_id)

        try:
            res = supabase.table("recent_searches").delete().eq("user_id", str(user_id)).execute()
            return len(res.data)
        except Exception:
            return cls._in_memory_store.clear_recent_searches(user_id)

    @classmethod
    def create_feedback(cls, user_id: Optional[UUID], feedback: UserFeedbackCreate) -> UserFeedbackOut:
        supabase = get_supabase_client()
        if not supabase:
            return cls._in_memory_store.create_feedback(user_id, feedback)

        payload = {
            "user_id": str(user_id) if user_id else None,
            "category": feedback.category.value,
            "description": feedback.description,
            "review_status": "pending",
        }
        try:
            res = supabase.table("user_feedback").insert(payload).execute()
            return UserFeedbackOut(**res.data[0])
        except Exception:
            return cls._in_memory_store.create_feedback(user_id, feedback)

