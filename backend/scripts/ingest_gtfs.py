"""CLI script to run full ingestion pipeline and build in-memory transit graph report."""
import argparse
import sys
import os

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.gtfs_loader import GTFSLoader
from app.services.graph_builder import GraphBuilder


def main():
    parser = argparse.ArgumentParser(description="Ingest GTFS dataset and verify graph construction.")
    parser.add_argument("--dir", default="data/raw/mdb-1262", help="Path to GTFS directory")
    parser.add_argument("--source", default="mdb-1262", help="Source ID tag")
    parser.add_argument("--max-trips", type=int, default=2000, help="Max trips to load (for memory optimization)")
    args = parser.parse_args()

    print(f"[INGEST] Ingesting GTFS data from '{args.dir}' (max_trips={args.max_trips})...")
    dataset = GTFSLoader.load(args.dir, source_id=args.source, max_trips=args.max_trips)

    if dataset.validation_errors:
        print(f"[FAILED] Ingestion failed with {len(dataset.validation_errors)} errors:")
        for err in dataset.validation_errors[:10]:
            print(f"  - {err}")
        sys.exit(1)

    print(f"[LOADED] Ingested {len(dataset.stops)} stops, {len(dataset.routes)} routes, {len(dataset.trips)} trips.")
    print("[BUILD] Constructing multimodal timetable graph...")
    graph = GraphBuilder.build_graph(dataset, max_walk_transfer_meters=300.0)

    print("\n" + "=" * 60)
    print("INGESTION SUMMARY")
    print("=" * 60)
    print(f"Graph Nodes:             {graph.total_nodes}")
    print(f"Scheduled Transit Edges: {graph.total_transit_edges}")
    print(f"Synthesized Walk Links:  {graph.total_walk_edges}")
    print(f"Has Fare Attributes:     {dataset.has_fare_data}")
    print("[SUCCESS] Ingestion pipeline verified!")


if __name__ == "__main__":
    main()
