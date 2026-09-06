"""
Adapter pattern for /model and /observations data sources.

Day 1-2 of the sprint plan, this package only has mock data. Day 3, Person 4's
real ingestion pipeline lands behind a real /model endpoint and Person 6's
behind a real /observations endpoint. Swapping from mock to real is meant to
be a one-line change here -- not a rewrite of graph_builder.py, the engines,
or the API routes, all of which only ever talk to `ModelSource`/
`ObservationSource`, never to mock_data or httpx directly.

Switch via environment variables (see config.SourceConfig):
    VARUNA_MODEL_SOURCE=http
    VARUNA_MODEL_SOURCE_URL=http://<person4-host>:8000/model
    VARUNA_OBS_SOURCE=http
    VARUNA_OBS_SOURCE_URL=http://<person6-host>:8000/observations
"""
from __future__ import annotations

import abc

import httpx

from . import config, mock_data
from .ingest import parse_model_snapshot, parse_observation_snapshot
from .schemas import ModelSnapshot, ObservationSnapshot


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


class HTTPObservationSource(ObservationSource):
    """Talks to Person 6's real /observations endpoint."""

    def __init__(self, url: str | None = None, timeout: float | None = None):
        self.url = url or config.SOURCES.observation_source_url
        self.timeout = timeout or config.SOURCES.http_timeout_s

    def fetch(self) -> ObservationSnapshot:
        response = httpx.get(self.url, timeout=self.timeout)
        response.raise_for_status()
        return parse_observation_snapshot(response.json())


def get_model_source() -> ModelSource:
    if config.SOURCES.model_source == "http":
        return HTTPModelSource()
    return MockModelSource()


def get_observation_source() -> ObservationSource:
    if config.SOURCES.observation_source == "http":
        return HTTPObservationSource()
    return MockObservationSource()
