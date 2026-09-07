"""
VARUNA In-Situ Pipeline CLI.

Commands:
  run       Execute pipeline and print snapshot summary.
  serve     Launch the FastAPI microservice.
  adapters  List registered sensor adapters.
  export    Generate and export deterministic demo dataset to JSON.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .adapters.registry import AdapterRegistry
from .config import settings
from .pipeline import InSituPipeline


def main():
    parser = argparse.ArgumentParser(
        prog="varuna-insitu",
        description="VARUNA In-Situ Ocean Observation Pipeline & Adapter CLI",
    )
    subparsers = parser.add_subparsers(dest="command", help="Subcommand to execute")

    # run command
    run_parser = subparsers.add_parser("run", help="Run the in-situ pipeline and print summary")
    run_parser.add_argument("--source", default=None, help="Source adapter (local_demo, argovis, etc.)")

    # serve command
    serve_parser = subparsers.add_parser("serve", help="Start the FastAPI microservice")
    serve_parser.add_argument("--host", default=settings.api_host, help="Host interface to bind")
    serve_parser.add_argument("--port", type=int, default=settings.api_port, help="Port to bind")

    # adapters command
    subparsers.add_parser("adapters", help="List registered sensor adapters")

    # export command
    export_parser = subparsers.add_parser("export", help="Export demo dataset to JSON")
    export_parser.add_argument("--out", default="data/demo_bay_of_bengal_obs.json", help="Output JSON path")

    args = parser.parse_args()

    if args.command == "adapters":
        print("Registered Sensor Adapters:")
        for a in AdapterRegistry.list_adapters():
            print(f"  - {a}")
        sys.exit(0)

    pipeline = InSituPipeline()

    if args.command == "run":
        snapshot, profiles, qc = pipeline.run(source=args.source)
        print("=== VARUNA In-Situ Snapshot ===")
        print(f"Region:    {snapshot.region}")
        print(f"Source:    {snapshot.source}")
        print(f"Time:      {snapshot.time.isoformat()}")
        print(f"Sensors:   {len(snapshot.points)} surface points")
        print(f"Profiles:  {len(profiles)} vertical profiles")
        print(f"QC Report: {qc.retained_records}/{qc.total_raw_records} retained ({qc.dropped_bad_qc} bad QC, {qc.dropped_sentinels} sentinels)")
        sys.exit(0)

    if args.command == "serve":
        import uvicorn
        print(f"Starting VARUNA In-Situ API on http://{args.host}:{args.port}")
        uvicorn.run("varuna_insitu_pipeline.service:app", host=args.host, port=args.port, reload=False)
        sys.exit(0)

    if args.command == "export":
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        snapshot, profiles, qc = pipeline.run(source="local_demo")
        payload = {
            "snapshot": snapshot.model_dump(mode="json"),
            "profiles": [p.model_dump(mode="json") for p in profiles],
            "qc_report": qc.model_dump(mode="json"),
        }
        out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"Exported demo dataset ({len(snapshot.points)} points) to {out_path}")
        sys.exit(0)

    parser.print_help()


if __name__ == "__main__":
    main()
