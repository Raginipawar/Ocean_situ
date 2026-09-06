"""
VARUNA Model Pipeline — Command Line Interface.

Provides a reproducible command to execute the pipeline with specific paths,
or drop back to the local demo mode for safe judging conditions.
"""

import argparse
import logging
import sys
from pathlib import Path

from varuna_model_pipeline.pipeline import prepare_model_dataset
from varuna_model_pipeline.api_contract import to_model_snapshot

def main():
    parser = argparse.ArgumentParser(description="VARUNA Ocean Model Pipeline CLI")
    parser.add_argument("--primary", type=str, help="Path to primary INCOIS LAS NetCDF file")
    parser.add_argument("--fallback", type=str, help="Path to fallback GLORYS NetCDF file")
    parser.add_argument("--demo", action="store_true", help="Use local offline demo source")
    parser.add_argument("--export", action="store_true", help="Print the final JSON payload for the Graph Fusion Engine")
    
    args = parser.parse_args()
    
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s"
    )
    logger = logging.getLogger("varuna_model_pipeline.cli")
    
    if not (args.primary or args.fallback or args.demo):
        logger.error("Must specify at least one of --primary, --fallback, or --demo.")
        sys.exit(1)
        
    logger.info("Initializing Ocean Model Pipeline")
    
    try:
        result = prepare_model_dataset(
            primary_path=Path(args.primary) if args.primary else None,
            fallback_path=Path(args.fallback) if args.fallback else None,
            use_local_demo=args.demo
        )
    except Exception as e:
        logger.exception("Pipeline failed critically:")
        sys.exit(1)
        
    logger.info("Pipeline complete. Selected Source: %s", result.source.value)
    
    if result.attempts:
        logger.info("Source Attempts History:")
        for attempt in result.attempts:
            status = "OK" if attempt.ok else f"FAILED: {attempt.error}"
            logger.info("  - %s: %s", attempt.source.value, status)
            
    logger.info("Performance: %s ms", result.dataset.attrs.get('pipeline_runtime_ms', 'unknown'))
    
    if args.export:
        snapshot = to_model_snapshot(result.dataset)
        print("\n--- MODEL SNAPSHOT PAYLOAD ---")
        print(snapshot.model_dump_json(indent=2))

if __name__ == "__main__":
    main()
