"""
Integration test for ModelPipelineSource -- Person 4's real model-pipeline
package, called in-process. Skipped automatically if that package isn't
installed (it's an optional dependency; see adapters.py's docstring for the
install command), so this suite still runs clean on a machine that hasn't
set it up.
"""
import pytest

pytest.importorskip("varuna_model_pipeline")

from graph_fusion.adapters import ModelPipelineSource
from graph_fusion.fusion_service import FusionService
from graph_fusion.mock_data import generate_mock_observations
from graph_fusion.schemas import ModelSnapshot


def test_model_pipeline_source_returns_valid_snapshot():
    snapshot = ModelPipelineSource(use_local_demo=True).fetch()
    assert isinstance(snapshot, ModelSnapshot)
    assert snapshot.region == "bay_of_bengal"
    assert len(snapshot.points) > 0
    # schema round-trip should preserve real values, not silently null them
    assert any(p.sst_c is not None for p in snapshot.points)


def test_model_pipeline_source_fuses_with_mock_observations():
    model = ModelPipelineSource(use_local_demo=True).fetch()
    obs = generate_mock_observations(n_sensors=20, seed=3)
    result = FusionService().fuse(model, obs, engine="fallback")
    assert result.summary.n_grid_points == len(model.points)
    assert len(result.points) == result.summary.n_sensors + result.summary.n_grid_points
