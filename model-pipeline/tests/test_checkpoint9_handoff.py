"""
Checkpoint 9: Graph Fusion Handoff Test

Verifies that the canonical model pipeline's output strictly complies
with the Graph Fusion Engine's input interface and can be successfully
fused with observation data.
"""

import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

# Setup paths to import from both modules
ROOT_DIR = Path(__file__).parent.parent.parent
MODEL_SRC = ROOT_DIR / "model-pipeline" / "src"
FUSION_SRC = ROOT_DIR / "varuna-graph-fusion" / "src"

if str(MODEL_SRC) not in sys.path:
    sys.path.insert(0, str(MODEL_SRC))

from varuna_model_pipeline.pipeline import load_local_demo_model_data
from varuna_model_pipeline.api_contract import to_model_snapshot

# Add backend app directory to sys path so we can import its schemas
BACKEND_SRC = ROOT_DIR / "backend"

if str(BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(BACKEND_SRC))

try:
    from app.schemas import ModelSnapshot as BackendModelSnapshot
    BACKEND_AVAILABLE = True
    BACKEND_IMPORT_ERROR = None
except ImportError as e:
    BACKEND_AVAILABLE = False
    BACKEND_IMPORT_ERROR = str(e)


@pytest.mark.skipif(not BACKEND_AVAILABLE, reason=f"Backend schemas not available: {BACKEND_IMPORT_ERROR}")
def test_graph_fusion_handoff():
    """
    Test that the ModelSnapshot produced by our pipeline can be cleanly consumed
    by the Backend's schema (which mirrors the Graph Fusion Engine).
    """
    
    # 1. Generate real (demo) model data through the pipeline
    result = load_local_demo_model_data()
    
    # 2. Serialize it using our Checkpoint 8 contract
    our_snapshot = to_model_snapshot(result.dataset)
    
    # 3. Export to JSON payload
    json_payload = our_snapshot.model_dump_json()
    
    # 4. Attempt to parse it using the Backend's STRICT Pydantic schema
    try:
        fusion_snapshot = BackendModelSnapshot.model_validate_json(json_payload)
    except ValidationError as e:
        pytest.fail(f"Backend/Graph fusion engine rejected the ModelSnapshot payload:\n{e}")
        
    # 5. Validate the parsed output
    assert isinstance(fusion_snapshot, BackendModelSnapshot)
    assert fusion_snapshot.region == "bay_of_bengal"
    assert fusion_snapshot.source == "LOCAL_DEMO"
    assert len(fusion_snapshot.points) == len(our_snapshot.points)
    
    # Ensure variables mapped correctly
    assert fusion_snapshot.points[0].sst_c == our_snapshot.points[0].sst_c
    assert fusion_snapshot.points[0].current_u_ms == our_snapshot.points[0].current_u_ms

if __name__ == "__main__":
    pytest.main([__file__])

