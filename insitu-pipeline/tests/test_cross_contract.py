"""
Cross-contract integration test validating that InSituPipeline output
parses cleanly into Person 1 (graph_fusion) and Person 5 (backend) schemas.
"""
import importlib.util
import sys
from pathlib import Path

from varuna_insitu_pipeline import InSituPipeline

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def test_person1_graph_fusion_contract():
    """Verify Person 1's ObservationSnapshot validates in-situ pipeline output."""
    gf_schemas_path = REPO_ROOT / "varuna-graph-fusion" / "src" / "graph_fusion" / "schemas.py"
    assert gf_schemas_path.is_file(), f"Expected {gf_schemas_path} to exist"

    spec = importlib.util.spec_from_file_location("graph_fusion.schemas", gf_schemas_path)
    gf_schemas = importlib.util.module_from_spec(spec)
    sys.modules["graph_fusion.schemas"] = gf_schemas
    spec.loader.exec_module(gf_schemas)

    pipeline = InSituPipeline()
    snapshot = pipeline.get_snapshot()
    raw_dict = snapshot.model_dump(mode="json")

    gf_snapshot = gf_schemas.ObservationSnapshot.model_validate(raw_dict)
    assert len(gf_snapshot.points) == len(snapshot.points)
    assert gf_snapshot.region == "bay_of_bengal"
    assert gf_snapshot.points[0].sensor_id == snapshot.points[0].sensor_id


def test_person5_backend_contract():
    """Verify Person 5's backend ObservationSnapshot validates in-situ pipeline output."""
    be_schemas_path = REPO_ROOT / "backend" / "app" / "schemas.py"
    assert be_schemas_path.is_file(), f"Expected {be_schemas_path} to exist"

    spec = importlib.util.spec_from_file_location("backend.app.schemas", be_schemas_path)
    be_schemas = importlib.util.module_from_spec(spec)
    sys.modules["backend.app.schemas"] = be_schemas
    spec.loader.exec_module(be_schemas)

    pipeline = InSituPipeline()
    snapshot = pipeline.get_snapshot()
    raw_dict = snapshot.model_dump(mode="json")

    be_snapshot = be_schemas.ObservationSnapshot.model_validate(raw_dict)
    assert len(be_snapshot.points) == len(snapshot.points)
    assert be_snapshot.region == "bay_of_bengal"
    assert be_snapshot.points[0].sensor_id == snapshot.points[0].sensor_id
