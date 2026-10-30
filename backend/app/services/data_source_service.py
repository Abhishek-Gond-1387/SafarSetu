"""Data source service managing the lifecycle and singleton instances
of transit repository, graph, routing engine, and real-time vehicle poller.
"""
from __future__ import annotations

import os
from typing import Optional

from app.core.config import settings
from app.models.transit import GTFSDataset
from app.repositories.realtime_repository import RealtimeVehicleRepository
from app.repositories.transit_repository import TransitRepository
from app.services.graph_builder import GraphBuilder, TransitGraph
from app.services.gtfs_loader import GTFSLoader
from app.services.realtime_poller import OTDRealtimePoller
from app.services.routing_engine import RoutingEngine


class TransitContext:
    """Singleton transit context holding initialized dataset, repo, graph, router, and live poller."""
    dataset: Optional[GTFSDataset] = None
    repository: TransitRepository = TransitRepository()
    graph: TransitGraph = TransitGraph()
    router: Optional[RoutingEngine] = None
    realtime_repo: RealtimeVehicleRepository = RealtimeVehicleRepository(
        max_cache_size=settings.OTD_REALTIME_MAX_CACHE_SIZE,
        stale_threshold_seconds=settings.OTD_REALTIME_STALE_THRESHOLD_SECONDS,
    )
    realtime_poller: Optional[OTDRealtimePoller] = None
    is_initialized: bool = False

    @classmethod
    def initialize(
        cls,
        gtfs_dir: Optional[str] = None,
        source_id: Optional[str] = None,
        max_trips: Optional[int] = None,
    ):
        if cls.is_initialized and cls.dataset and not cls.dataset.is_empty:
            return

        target_dir = gtfs_dir or settings.GTFS_DATA_DIR
        if not os.path.isdir(target_dir):
            backend_candidate = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), target_dir)
            if os.path.isdir(backend_candidate):
                target_dir = backend_candidate
        target_source = source_id or settings.DEFAULT_SOURCE_ID
        trips_limit = max_trips if max_trips is not None else settings.MAX_LOADED_TRIPS

        print(f"[*] Loading GTFS dataset from: {target_dir} (source: {target_source})...")
        if os.path.isdir(target_dir):
            cls.dataset = GTFSLoader.load(target_dir, source_id=target_source, max_trips=trips_limit)

            # Ingest DMRC (Delhi Metro) static dataset if present
            dmrc_dir = os.path.join(os.path.dirname(target_dir), "dmrc")
            if not os.path.isdir(dmrc_dir):
                backend_dmrc = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "raw", "dmrc")
                if os.path.isdir(backend_dmrc):
                    dmrc_dir = backend_dmrc

            if os.path.isdir(dmrc_dir):
                print(f"[*] Ingesting DMRC Delhi Metro network from: {dmrc_dir}...")
                dmrc_data = GTFSLoader.load(dmrc_dir, source_id="dmrc")
                if dmrc_data and not dmrc_data.is_empty:
                    cls.dataset.merge(dmrc_data, prefix="metro_")
                    print(f"[OK] Ingested DMRC Metro: +{len(dmrc_data.stops)} stations, +{len(dmrc_data.routes)} lines, +{len(dmrc_data.trips)} trips.")

            cls.repository = TransitRepository(cls.dataset)
            cls.graph = GraphBuilder.build_graph(
                cls.dataset,
                max_walk_transfer_meters=settings.WALK_TRANSFER_MAX_METERS,
                enable_walking=True,
            )
            cls.router = RoutingEngine(cls.dataset, cls.graph)
            cls.is_initialized = True
            print(f"[OK] Ingestion complete: {len(cls.dataset.stops)} stops, {len(cls.dataset.routes)} routes, "
                  f"{len(cls.dataset.trips)} trips, {cls.graph.total_transit_edges} transit edges.")
        else:
            print(f"[WARN] GTFS directory not found: {target_dir}. Context initialized empty.")
            cls.dataset = None
            cls.repository = TransitRepository()
            cls.graph = TransitGraph()
            cls.router = None
            cls.is_initialized = False

        # Initialize realtime poller
        if cls.realtime_poller is None:
            cls.realtime_poller = OTDRealtimePoller(
                repository=cls.realtime_repo,
                static_dataset_provider=lambda: cls.dataset,
            )


def get_transit_context() -> TransitContext:
    if not TransitContext.is_initialized:
        TransitContext.initialize()
    return TransitContext
