"""
Resilient parsing of raw /model and /observations payloads.

`ModelSnapshot.model_validate(raw)` / `ObservationSnapshot.model_validate(raw)`
validate the whole `points` list at once -- one malformed reading from one
flaky real sensor (bad GPS fix pushing lat out of [-90, 90], a sensor_type
we didn't enumerate, a missing required field) fails the *entire* snapshot.
That's invisible with clean mock data, but it is exactly the kind of thing
the approach doc calls out as Person 6's own end-to-end smoke-test focus:
"missing readings, timestamp mismatches -- the kind of thing that quietly
breaks a live demo."

These functions parse point-by-point instead: a bad point is dropped and
logged, everything else still comes through. Use these instead of calling
`.model_validate()` directly on any payload that might come from a real,
occasionally-flaky feed (see adapters.py's HTTP sources).
"""
from __future__ import annotations

import logging
from typing import Any

from pydantic import ValidationError

from .schemas import ModelGridPoint, ModelSnapshot, ObservationPoint, ObservationSnapshot

logger = logging.getLogger("graph_fusion.ingest")


def _first_error_message(exc: ValidationError) -> str:
    errors = exc.errors()
    if not errors:
        return str(exc)
    first = errors[0]
    loc = ".".join(str(part) for part in first.get("loc", ()))
    return f"{loc}: {first.get('msg', exc)}" if loc else str(first.get("msg", exc))


def parse_model_snapshot(raw: dict[str, Any]) -> ModelSnapshot:
    points: list[ModelGridPoint] = []
    dropped = 0
    for item in raw.get("points", []):
        try:
            points.append(ModelGridPoint.model_validate(item))
        except ValidationError as exc:
            dropped += 1
            logger.warning("Dropping malformed /model point: %s", _first_error_message(exc))

    if dropped:
        logger.warning("Dropped %d malformed /model point(s) out of %d", dropped, dropped + len(points))

    payload = {k: v for k, v in raw.items() if k != "points"}
    return ModelSnapshot(points=points, **payload)


def parse_observation_snapshot(raw: dict[str, Any]) -> ObservationSnapshot:
    points: list[ObservationPoint] = []
    dropped = 0
    for item in raw.get("points", []):
        try:
            points.append(ObservationPoint.model_validate(item))
        except ValidationError as exc:
            sensor_id = item.get("sensor_id", "?") if isinstance(item, dict) else "?"
            dropped += 1
            logger.warning(
                "Dropping malformed /observations point (sensor_id=%r): %s",
                sensor_id,
                _first_error_message(exc),
            )

    if dropped:
        logger.warning(
            "Dropped %d malformed /observations point(s) out of %d", dropped, dropped + len(points)
        )

    payload = {k: v for k, v in raw.items() if k != "points"}
    return ObservationSnapshot(points=points, **payload)
