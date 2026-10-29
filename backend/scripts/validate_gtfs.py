"""CLI script to validate a GTFS directory and print an ingestion quality report."""
import argparse
import json
import sys
import os

# Set standard output to UTF-8 on Windows
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.data_validator import GTFSValidator


def main():
    parser = argparse.ArgumentParser(description="Validate a GTFS dataset directory.")
    parser.add_argument("--dir", default="data/raw/mdb-1262", help="Path to extracted GTFS directory")
    parser.add_argument("--source", default="mdb-1262", help="Source ID tag")
    args = parser.parse_args()

    print(f"[VALIDATION] Validating GTFS dataset in '{args.dir}' (source: {args.source})...")
    report = GTFSValidator.validate_directory(args.dir, source_id=args.source)

    print("\n" + "=" * 60)
    print(f"VALIDATION REPORT: {args.source}")
    print("=" * 60)
    print(f"Status:       {'VALID' if report.is_valid else 'INVALID'}")
    print(f"Expired:      {'YES (Historical schedules)' if report.is_expired else 'NO'}")
    print(f"Active Range: {report.feed_start_date} -> {report.feed_end_date}")
    print(f"Counts:       {json.dumps(report.counts, indent=2)}")

    if report.warnings:
        print(f"\nWarnings ({len(report.warnings)}):")
        for w in report.warnings[:15]:
            print(f"  [WARN]  {w}")
        if len(report.warnings) > 15:
            print(f"  ... and {len(report.warnings) - 15} more warnings")

    if report.errors:
        print(f"\nErrors ({len(report.errors)}):")
        for e in report.errors[:15]:
            print(f"  [ERR] {e}")
        sys.exit(1)
    else:
        print("\n[OK] No critical structural errors found.")


if __name__ == "__main__":
    main()
