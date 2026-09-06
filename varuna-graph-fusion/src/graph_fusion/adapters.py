"""
Adapter pattern for /model and /observations data sources.

Day 1-2 of the sprint plan, this package only had mock data. Person 6's real
ingestion pipeline is meant to land behind a real /observations HTTP endpoint
(see HTTPObservationSource). Person 4's turned out to ship as an in-process
Python library (`varuna_model_pipeline`, checked in at ../model-pipeline)
rather than its own server -- ModelPipelineSource below calls it directly in
the same interpreter, no network hop, which is actually preferable for a live
demo (one fewer process that can fall over on stage). Either way, swapping
sources is a one-line env var change here -- not a rewrite of
graph_builder.py, the engines, or the API routes, all of which only ever talk
to `ModelSource`/`ObservationSource`, never to mock_data, httpx, or
varuna_model_pipeline directly.

Switch via environment variables (see config.SourceConfig):
    VARUNA_MODEL_SOURCE=pipeline           # Person 4's model-pipeline, in-process
    VARUNA_MODEL_SOURCE=http                # or: a real /model HTTP endpoint
    VARUNA_MODEL_SOURCE_URL=http://<host>:8000/model
    VARUNA_OBS_SOURCE=http
    VARUNA_OBS_SOURCE_URL=http://<person6-host>:8000/observations
"""
from __future__ import annotations

import abc
import logging

import httpx

from . import config, mock_data
from .ingest import parse_model_snapshot, parse_observation_snapshot
from .schemas import ModelSnapshot, ObservationSnapshot

logger = logging.getLogger("graph_fusion.adapters")


class ModelSource(abc.ABC):
    @abc.abstractmethod
    def fetch(self) -> ModelSnapshot: ...


class ObservationSource(abc.ABC):
    @abc.abstractmethod
    def fetch(self) -> ObservationSnapshot: ...


class MockModelSource(ModelSource):
    def fetch(self) -> ModelSnapshot:
        return mock_data.generate_mock_model_grid()


class MockObservationSource(ObservationSource):
    def fetch(self) -> ObservationSnapshot:
        return mock_data.generate_mock_observations()


class HTTPModelSource(ModelSource):
    """Talks to Person 4's real /model endpoint."""

    def __init__(self, url: str | None = None, timeout: float | None = None):
        self.url = url or config.SOURCES.model_source_url
        self.timeout = timeout or config.SOURCES.http_timeout_s

    def fetch(self) -> ModelSnapshot:
        response = httpx.get(self.url, timeout=self.timeout)
        response.raise_for_status()
        return parse_model_snapshot(response.json())


class ModelPipelineSource(ModelSource):
    """
    Calls Person 4's `varuna_model_pipeline` package in-process.

    Its `ModelSnapshot`/`ModelGridPoint` (in `api_contract.py`) mirror ours
    field-for-field on purpose (their README says as much), so a
    `.model_dump()` round-trip is all the translation needed -- no manual
    field mapping to keep in sync.

    `use_local_demo=True` by default: real INCOIS LAS / GLORYS ingestion
    needs actual source files/credentials this environment doesn't have.
    Pass real `primary_path`/`fallback_path` once those exist -- the
    pipeline's own source-selection logic (LOCAL_DEMO as last-resort
    fallback) is unchanged either way.

    Note: their local-demo pipeline run takes several seconds (regridding a
    synthetic base grid), not milliseconds -- this is exactly what
    FusionService's content-hash cache is for. A demo hitting `/fused`
    repeatedly against unchanged upstream data pays that cost once, not
    per request.
    """

    def __init__(self, use_local_demo: bool = True, primary_path: str | None = None, fallback_path: str | None = None):
        self.use_local_demo = use_local_demo
        self.primary_path = primary_path
        self.fallback_path = fallback_path

    def fetch(self) -> ModelSnapshot:
        try:
            from varuna_model_pipeline.api_contract import to_model_snapshot
            from varuna_model_pipeline.pipeline import prepare_model_dataset
        except ImportError as exc:  # pragma: no cover - environment-dependent
            raise RuntimeError(
                "varuna_model_pipeline isn't installed. From varuna-graph-fusion/: "
                "pip install -e ../model-pipeline"
            ) from exc

        result = prepare_model_dataset(
            primary_path=self.primary_path,
            fallback_path=self.fallback_path,
            use_local_demo=self.use_local_demo,
        )
        their_snapshot = to_model_snapshot(result.dataset)
        return ModelSnapshot.model_validate(their_snapshot.model_dump())


class HTTPObservationSource(ObservationSource):
    """Talks to Person 6's real /observations endpoint."""

    def __init__(self, url: str | None = None, timeout: float | None = None):
        self.url = url or config.SOURCES.observation_source_url
        self.timeout = timeout or config.SOURCES.http_timeout_s

    def fetch(self) -> ObservationSnapshot:
        response = httpx.get(self.url, timeout=self.timeout)
        response.raise_for_status()
        return parse_observation_snapshot(response.json())


class FallbackModelSource(ModelSource):
    """
    Tries `primary`; on ANY exception, logs a warning and silently returns
    `fallback`'s data instead of raising -- same "never cut the core loop"
    philosophy as FusionService's GNN-to-graph-weighted-fallback degrade.

    Used to wrap ModelPipelineSource: a live jury demo should never go down
    because a teammate's real-data pipeline hit an edge case. Mock data
    (always available, deterministic, fast) is a strictly better failure
    mode than a broken page.
    """

    def __init__(self, primary: ModelSource, fallback: ModelSource):
        self.primary = primary
        self.fallback = fallback

    def fetch(self) -> ModelSnapshot:
        try:
            return self.primary.fetch()
        except Exception as exc:  # noqa: BLE001 - deliberate, see class docstring
            logger.warning(
                "Primary model source (%s) failed (%s); falling back to %s.",
                type(self.primary).__name__,
                exc,
                type(self.fallback).__name__,
            )
            return self.fallback.fetch()


def get_model_source() -> ModelSource:
    if config.SOURCES.model_source == "http":
        return HTTPModelSource()
    if config.SOURCES.model_source == "pipeline":
        return FallbackModelSource(primary=ModelPipelineSource(), fallback=MockModelSource())
    return MockModelSource()


def get_observation_source() -> ObservationSource:
    if config.SOURCES.observation_source == "http":
        return HTTPObservationSource()
    return MockObservationSource()
