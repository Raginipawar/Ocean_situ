"""Explicit source selection and fallback orchestration."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from .config import ModelPipelineSettings
from .errors import IngestionError
from .schema import ModelSource
from .sources.glorys import GlorysIngestor
from .sources.incois_las import IncoisLasIngestor, IncoisLasIngestionResult

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SourceAttempt:
    """One source-selection attempt for provenance/debugging."""

    source: ModelSource
    reference: str | None
    ok: bool
    error: str | None = None


@dataclass(frozen=True)
class SelectedModelDataset:
    """Output of explicit source selection."""

    dataset: object
    source: ModelSource
    source_path: str | None
    attempts: list[SourceAttempt] = field(default_factory=list)
    coordinate_mapping: dict[str, str] = field(default_factory=dict)
    variable_mapping: dict[str, str] = field(default_factory=dict)


def load_with_explicit_fallback(
    *,
    primary_path: str | Path | None,
    fallback_path: str | Path | None,
    settings: ModelPipelineSettings | None = None,
) -> SelectedModelDataset:
    """Load INCOIS first, then GLORYS fallback only after explicit failure.

    The function records every attempt. It never hides source switching: the
    returned object carries the selected source and the failure reason for the
    skipped/failed primary attempt.
    """

    cfg = settings or ModelPipelineSettings()
    attempts: list[SourceAttempt] = []

    if primary_path is not None:
        try:
            logger.info("Attempting primary model source: %s", ModelSource.INCOIS_LAS.value)
            result = IncoisLasIngestor(settings=cfg).load(primary_path)
            attempts.append(
                SourceAttempt(ModelSource.INCOIS_LAS, str(primary_path), True)
            )
            return _selected_from_incois(result, attempts)
        except IngestionError as exc:
            logger.warning("Primary INCOIS LAS source failed: %s", exc)
            attempts.append(
                SourceAttempt(ModelSource.INCOIS_LAS, str(primary_path), False, str(exc))
            )

    if fallback_path is None:
        raise IngestionError(
            "INCOIS LAS primary source failed or was not configured, and no GLORYS "
            f"fallback path was provided. Attempts: {attempts}"
        )

    try:
        logger.info("Attempting fallback model source: %s", ModelSource.COPERNICUS_GLORYS.value)
        result = GlorysIngestor(settings=cfg).load(fallback_path)
        attempts.append(
            SourceAttempt(ModelSource.COPERNICUS_GLORYS, str(fallback_path), True)
        )
        return SelectedModelDataset(
            dataset=result.dataset,
            source=result.source,
            source_path=result.source_path,
            attempts=attempts,
            coordinate_mapping=result.coordinate_mapping,
            variable_mapping=result.variable_mapping,
        )
    except IngestionError as exc:
        logger.error("GLORYS fallback source failed: %s", exc)
        attempts.append(
            SourceAttempt(ModelSource.COPERNICUS_GLORYS, str(fallback_path), False, str(exc))
        )
        raise IngestionError(
            "Both INCOIS LAS primary and GLORYS fallback model sources failed. "
            f"Attempts: {attempts}"
        ) from exc


def _selected_from_incois(
    result: IncoisLasIngestionResult,
    attempts: list[SourceAttempt],
) -> SelectedModelDataset:
    return SelectedModelDataset(
        dataset=result.dataset,
        source=result.source,
        source_path=result.source_path,
        attempts=attempts,
        coordinate_mapping=result.coordinate_mapping,
        variable_mapping=result.variable_mapping,
    )

