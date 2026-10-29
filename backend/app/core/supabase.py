"""Supabase client initialization and management."""
from __future__ import annotations

from typing import Optional
from supabase import Client, create_client

from app.core.config import settings

_supabase_client: Optional[Client] = None


def get_supabase_client() -> Optional[Client]:
    """Retrieve or create the singleton Supabase service client.

    Uses SUPABASE_SERVICE_ROLE_KEY for server-side trusted execution,
    or falls back to SUPABASE_ANON_KEY if service key is omitted.
    Returns None if neither URL nor keys are configured.
    """
    global _supabase_client
    if _supabase_client is not None:
        return _supabase_client

    if not settings.SUPABASE_URL:
        return None

    api_key = settings.SUPABASE_SERVICE_ROLE_KEY or settings.SUPABASE_ANON_KEY
    if not api_key:
        return None

    try:
        _supabase_client = create_client(settings.SUPABASE_URL, api_key)
        return _supabase_client
    except Exception as e:
        print(f"[WARN] Failed to initialize Supabase client: {e}")
        return None


def reset_supabase_client() -> None:
    """Reset the cached client instance (primarily used in tests)."""
    global _supabase_client
    _supabase_client = None

