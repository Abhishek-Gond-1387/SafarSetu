"""Benchmark routing performance and memory on genuine Delhi DTC dataset."""
from datetime import date
import os
import sys
import time

# Ensure utf-8 encoding on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Add backend directory to sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from app.models.journey import RouteRankCriterion
from app.services.graph_builder import GraphBuilder
from app.services.gtfs_loader import GTFSLoader
from app.services.routing_engine import RoutingEngine

DATA_DIR = os.path.join(BASE_DIR, "data", "raw", "mdb-1262")


def get_process_memory_mb() -> float:
    try:
        import psutil
        return psutil.Process(os.getpid()).memory_info().rss / (1024 * 1024)
    except ImportError:
        return 0.0


def run_benchmark():
    print("=" * 70, flush=True)
    print("SafarSetu Stage 3: Routing Engine Performance Benchmark", flush=True)
    print("=" * 70, flush=True)

    t0 = time.perf_counter()
    mem_start = get_process_memory_mb()

    trips_cap = 10000  # High-coverage operational benchmark: 10,000 scheduled trips
    print(f"Loading genuine dataset from: {DATA_DIR} (trips cap: {trips_cap:,})...", flush=True)
    dataset = GTFSLoader.load(DATA_DIR, source_id="mdb-1262", max_trips=trips_cap)
    t_load = time.perf_counter() - t0
    mem_after_load = get_process_memory_mb()

    print(f"Dataset Ingested & Validated in {t_load:.2f}s:", flush=True)
    print(f"  - Unique Stops in Network: {len(dataset.stops):,}", flush=True)
    print(f"  - Active Routes: {len(dataset.routes):,}", flush=True)
    print(f"  - Trips loaded: {len(dataset.trips):,}", flush=True)
    print(f"  - Trips in stop_times index: {len(dataset.stop_times):,}", flush=True)
    if mem_after_load > 0:
        print(f"  - Process Memory: {mem_after_load:.1f} MB (+{mem_after_load - mem_start:.1f} MB)", flush=True)

    t1 = time.perf_counter()
    print("\nBuilding Multimodal Transit Graph (Scheduled + Spatial Walking Grid)...", flush=True)
    graph = GraphBuilder.build_graph(dataset, max_walk_transfer_meters=300.0, enable_walking=True)
    t_graph = time.perf_counter() - t1
    mem_after_graph = get_process_memory_mb()

    print(f"Graph Construction completed in {t_graph:.3f}s:", flush=True)
    print(f"  - Transit nodes: {graph.total_nodes:,}", flush=True)
    print(f"  - Scheduled transit edges: {graph.total_transit_edges:,}", flush=True)
    print(f"  - Synthesized walking transfer edges: {graph.total_walk_edges:,}", flush=True)
    if mem_after_graph > 0:
        print(f"  - Process Memory after graph: {mem_after_graph:.1f} MB (+{mem_after_graph - mem_after_load:.1f} MB)", flush=True)

    router = RoutingEngine(dataset, graph)

    # Realistic Test Queries
    print("\nExecuting realistic journey queries across Delhi stops...", flush=True)
    trip_keys = list(dataset.stop_times.keys())
    sample_trip_1 = dataset.stop_times[trip_keys[0]]
    sample_trip_2 = dataset.stop_times[trip_keys[min(len(trip_keys) - 1, 100)]]

    origin_direct = sample_trip_1[0].stop_id
    dest_direct = sample_trip_1[min(6, len(sample_trip_1) - 1)].stop_id

    origin_transfer = sample_trip_1[0].stop_id
    dest_transfer = sample_trip_2[min(4, len(sample_trip_2) - 1)].stop_id

    queries = [
        ("Direct Journey Query (Early Morning)", origin_direct, dest_direct, 7 * 3600),
        ("Cross-Network Transfer Query (Peak Morning)", origin_transfer, dest_transfer, 8 * 3600),
        ("Off-Peak Query (Midday)", origin_direct, dest_direct, 13 * 3600),
    ]

    for label, orig, dest, dep_sec in queries:
        orig_name = dataset.stops[orig].stop_name
        dest_name = dataset.stops[dest].stop_name
        t_q = time.perf_counter()
        journeys, reason = router.plan_journey(
            origin_stop_id=orig,
            destination_stop_id=dest,
            departure_date=date(2023, 6, 1),
            departure_seconds=dep_sec,
            max_transfers=3,
            criterion=RouteRankCriterion.FASTEST,
        )
        latency_ms = (time.perf_counter() - t_q) * 1000.0
        print(f"\n[QUERY] {label}:", flush=True)
        print(f"  From: '{orig_name}' (ID: {orig}) -> To: '{dest_name}' (ID: {dest})", flush=True)
        print(f"  Requested Departure: {dep_sec // 3600:02d}:{(dep_sec % 3600) // 60:02d}:00", flush=True)
        print(f"  Query Latency: {latency_ms:.2f} ms", flush=True)
        if journeys:
            print(f"  Candidate Journeys Found: {len(journeys)}", flush=True)
            for idx, j in enumerate(journeys[:2], 1):
                print(f"    Option {idx}: Dep {j.departure_time_str} -> Arr {j.arrival_time_str} | "
                      f"Duration: {j.total_duration_seconds // 60}m | Transfers: {j.num_transfers} | "
                      f"Walk: {j.total_walk_meters:.0f}m", flush=True)
        else:
            print(f"  No route found: {reason}", flush=True)

    print("\n" + "=" * 70, flush=True)
    print("Benchmark complete.", flush=True)
    print("=" * 70, flush=True)


if __name__ == "__main__":
    run_benchmark()
