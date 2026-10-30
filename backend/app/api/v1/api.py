from fastapi import APIRouter
from app.api.v1.endpoints import health, realtime, routes, safety, stops, trips, users, voice

api_router = APIRouter()

api_router.include_router(health.router, tags=["Health"])
api_router.include_router(realtime.router, prefix="/realtime", tags=["Realtime"])
api_router.include_router(stops.router, prefix="/stops", tags=["Stops"])
api_router.include_router(routes.router, prefix="/routes", tags=["Routes"])
api_router.include_router(trips.router, prefix="/trips", tags=["Trips"])
api_router.include_router(users.router, prefix="/users", tags=["Users"])
api_router.include_router(voice.router, prefix="/voice", tags=["Voice Assistant"])
api_router.include_router(safety.router, prefix="/safety", tags=["HerRoute Safety Feedback"])
