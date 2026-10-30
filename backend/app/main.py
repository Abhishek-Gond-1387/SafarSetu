import os
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.v1.api import api_router
from app.api.v1.endpoints.health import get_health
from app.core.config import settings
from app.schemas.routing import HealthResponse
from app.services.data_source_service import TransitContext


@asynccontextmanager
async def lifespan(app: FastAPI):
    print(f"[*] Starting up {settings.PROJECT_NAME} (v{settings.VERSION})...")
    # Initialize transit data into repository and graph engine
    TransitContext.initialize()
    # Start live background poller if enabled and configured
    if TransitContext.realtime_poller:
        await TransitContext.realtime_poller.start()
    yield
    print(f"[*] Shutting down {settings.PROJECT_NAME}...")
    if TransitContext.realtime_poller:
        await TransitContext.realtime_poller.stop()


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description=(
        "SafarSetu backend service providing timetable-aware multimodal public transit routing "
        "and real-time GTFS-RT vehicle positions for Delhi/NCR commuters and tourists, "
        "powered by genuine transit data."
    ),
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS if settings.CORS_ORIGINS != ["*"] else [],
    allow_origin_regex=r".*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API v1 router
app.include_router(api_router, prefix=settings.API_V1_STR)

# Mount frontend dist if compiled
_frontend_dist = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
if _frontend_dist.exists() and (_frontend_dist / "index.html").exists():
    app.mount("/app", StaticFiles(directory=str(_frontend_dist), html=True), name="frontend")


@app.get("/", summary="Root Endpoint", tags=["Root"])
def root():
    return JSONResponse(
        content={
            "message": f"Welcome to {settings.PROJECT_NAME}",
            "version": settings.VERSION,
            "frontend": "/app" if _frontend_dist.exists() else "unbuilt",
            "docs": "/docs",
            "redoc": "/redoc",
            "health": "/health",
            "api_v1_health": f"{settings.API_V1_STR}/health",
            "api_v1_stops": f"{settings.API_V1_STR}/stops",
            "api_v1_routes_plan": f"{settings.API_V1_STR}/routes/plan",
            "api_v1_realtime_status": f"{settings.API_V1_STR}/realtime/status",
            "api_v1_realtime_vehicles": f"{settings.API_V1_STR}/realtime/vehicles",
        }
    )


@app.get("/health", response_model=HealthResponse, summary="Top-level Health Endpoint", tags=["Root"])
def health_endpoint():
    return get_health()
