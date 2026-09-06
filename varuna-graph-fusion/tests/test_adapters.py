"""
Adapter tests:

1. ModelPipelineSource -- Person 4's real model-pipeline package, called
   in-process. Skipped automatically if that package isn't installed (it's
   an optional dependency; see adapters.py's docstring for the install
   command), so this suite still runs clean on a machine that hasn't set it
   up.
2. FallbackModelSource -- the safety net that keeps a bad/missing pipeline
   from ever taking the live API down. These use a synthetic failing
   source, not the real package, so they always run regardless of whether
   varuna_model_pipeline is installed.
"""
import pytest

from graph_fusion.adapters import FallbackModelSource, ModelSource
from graph_fusion.mock_data import generate_mock_model_grid
from graph_fusion.schemas import ModelSnapshot


class _AlwaysFailsSource(ModelSource):
    def fetch(self) -> ModelSnapshot:
        raise RuntimeError("simulated pipeline failure")


class _AlwaysSucceedsSource(ModelSource):
    def __init__(self, snapshot: ModelSnapshot):
        self.snapshot = snapshot
        self.calls = 0

    def fetch(self) -> ModelSnapshot:
        self.calls += 1
        return self.snapshot


def test_fallback_model_source_uses_primary_when_healthy():
    good = _AlwaysSucceedsSource(generate_mock_model_grid())
    never_used = _AlwaysFailsSource()
    source = FallbackModelSource(primary=good, fallback=never_used)
    result = source.fetch()
    assert good.calls == 1
    assert isinstance(result, ModelSnapshot)


def test_fallback_model_source_degrades_on_primary_failure():
    fallback_snapshot = generate_mock_model_grid()
    fallback = _AlwaysSucceedsSource(fallback_snapshot)
    source = FallbackModelSource(primary=_AlwaysFailsSource(), fallback=fallback)
    result = source.fetch()
    assert fallback.calls == 1
    assert result is fallback_snapshot


# --- Person 4's real pipeline, in-process -----------------------------------

pytest.importorskip("varuna_model_pipeline")

from graph_fusion.adapters import ModelPipelineSource  # noqa: E402
from graph_fusion.fusion_service import FusionService  # noqa: E402
from graph_fusion.mock_data import generate_mock_observations  # noqa: E402


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
