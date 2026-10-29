"""Health check endpoint reporting dataset version, validation status, graph size, and real-time feed status."""
from fastapi import APIRouter
from app.core.config import settings
from app.schemas.realtime import RealtimeStatusResponse
from app.schemas.routing import DataSourceStatus, HealthResponse
from app.services.data_source_service import get_transit_context

router = APIRouter()


@router.get("/health", response_model=HealthResponse, summary="System Health & Dataset Status")
def get_health():
    """Returns application health, loaded transit data provenance, calendar freshness, graph scale,
    and real-time GTFS-RT feed status.
    """
    ctx = get_transit_context()
    sources = []

    if ctx.dataset and not ctx.dataset.is_empty:
        status_val = "expired" if ctx.dataset.validation_warnings and any("expired" in w.lower() for w in ctx.dataset.validation_warnings) else "loaded"
        s_date = ctx.dataset.feed_info.feed_start_date.isoformat() if ctx.dataset.feed_info and ctx.dataset.feed_info.feed_start_date else None
        e_date = ctx.dataset.feed_info.feed_end_date.isoformat() if ctx.dataset.feed_info and ctx.dataset.feed_info.feed_end_date else None

        sources.append(
            DataSourceStatus(
                source_id=ctx.dataset.source_id,
                label="Delhi Transport Corporation (DTC) Bus GTFS",
                status=status_val,
                stops_count=len(ctx.dataset.stops),
                routes_count=len(ctx.dataset.routes),
                trips_count=len(ctx.dataset.trips),
                feed_start_date=s_date,
                feed_end_date=e_date,
                warnings=ctx.dataset.validation_warnings,
            )
        )
    else:
        sources.append(
            DataSourceStatus(
                source_id=settings.DEFAULT_SOURCE_ID,
                label="Delhi Transit GTFS",
                status="not_loaded",
                warnings=["Transit dataset not currently loaded in memory."],
            )
        )

    # Real-time status
    rt_status_obj = ctx.realtime_repo.get_status()
    realtime_summary = RealtimeStatusResponse(
        enabled=rt_status_obj.enabled,
        api_key_configured=rt_status_obj.api_key_configured,
        last_poll_status=rt_status_obj.last_poll_status,
        last_successful_fetch=rt_status_obj.last_successful_fetch.isoformat() if rt_status_obj.last_successful_fetch else None,
        last_feed_timestamp=rt_status_obj.last_feed_timestamp.isoformat() if rt_status_obj.last_feed_timestamp else None,
        cached_vehicles_count=rt_status_obj.cached_vehicles_count,
        rejected_entities_count=rt_status_obj.rejected_entities_count,
        feed_freshness=rt_status_obj.feed_freshness.value,
        error_category=rt_status_obj.error_category.value if rt_status_obj.error_category else None,
        error_message=rt_status_obj.error_message_sanitized,
    )

    return HealthResponse(
        status="ok" if ctx.is_initialized else "degraded",
        project_name=settings.PROJECT_NAME,
        version=settings.VERSION,
        environment=settings.ENVIRONMENT,
        data_sources=sources,
        graph_nodes=ctx.graph.total_nodes,
        graph_edges=ctx.graph.total_transit_edges + ctx.graph.total_walk_edges,
        realtime=realtime_summary,
    )
