"""Example script demonstrating the Checkpoint 8 API integration contract.

This loads the local demo source, processes it through the pipeline,
converts the output to the ModelSnapshot schema, and prints it as JSON.
"""

import sys
from pathlib import Path

# Add src to python path for standalone execution
src_path = str(Path(__file__).parent.parent / "src")
if src_path not in sys.path:
    sys.path.insert(0, src_path)

from varuna_model_pipeline.pipeline import load_local_demo_model_data
from varuna_model_pipeline.api_contract import to_model_snapshot


def main():
    print("Loading and processing local demo model data...")
    result = load_local_demo_model_data()
    ds = result.dataset
    
    print("\nExtracting ModelSnapshot for Graph Fusion Engine...")
    snapshot = to_model_snapshot(ds)
    
    print("\n--- ModelSnapshot JSON Payload (first 1000 chars) ---")
    json_payload = snapshot.model_dump_json(indent=2)
    
    print(json_payload[:1000])
    print(f"\n... (truncated, total payload size: {len(json_payload)} bytes)")
    
    print(f"\nTotal points in snapshot: {len(snapshot.points)}")
    print(f"Snapshot Time: {snapshot.time}")
    print(f"Region: {snapshot.region}")
    print("SUCCESS: Contract serialization complete.")

if __name__ == "__main__":
    main()
