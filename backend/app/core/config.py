import os
from pathlib import Path
from typing import List, Optional, Union
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
_ENV_FILE = _BACKEND_DIR / ".env"


class Settings(BaseSettings):
    PROJECT_NAME: str = "SafarSetu Transit API"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    ENVIRONMENT: str = "development"
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:5174",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
    ]

    # Transit data settings
    GTFS_DATA_DIR: str = "data/raw/mdb-1262"
    DEFAULT_SOURCE_ID: str = "mdb-1262"
    MAX_LOADED_TRIPS: Optional[int] = 8000  # Default 8,000 trips ensures RAM remains ~350MB, safely below Render 512MB free tier limit
    WALK_TRANSFER_MAX_METERS: float = 400.0

    # Delhi OTD Real-Time Settings
    OTD_REALTIME_ENABLED: bool = True
    OTD_REALTIME_URL: str = "https://otd.delhi.gov.in/api/realtime/VehiclePositions.pb"
    OTD_REALTIME_API_KEY: Optional[str] = None
    OTD_REALTIME_POLL_INTERVAL_SECONDS: int = 15
    OTD_REALTIME_REQUEST_TIMEOUT_SECONDS: float = 10.0
    OTD_REALTIME_MAX_CACHE_SIZE: int = 10000
    OTD_REALTIME_STALE_THRESHOLD_SECONDS: int = 300

    # Supabase Database & Auth Settings (Stage 4)
    SUPABASE_URL: Optional[str] = None
    SUPABASE_ANON_KEY: Optional[str] = None
    SUPABASE_SERVICE_ROLE_KEY: Optional[str] = None
    SUPABASE_JWT_SECRET: Optional[str] = None
    SUPABASE_JWT_ALGORITHM: str = "HS256"
    SUPABASE_JWT_AUDIENCE: str = "authenticated"

    # AI Voice Assistant Settings (Google Gemini / OpenAI)
    GEMINI_API_KEY: Optional[str] = None
    OPENAI_API_KEY: Optional[str] = None

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",") if i.strip()]
        return v

    model_config = SettingsConfigDict(
        env_file=(str(_ENV_FILE), ".env"),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


settings = Settings()
