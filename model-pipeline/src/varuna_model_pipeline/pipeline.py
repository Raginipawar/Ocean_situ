"""End-to-end ocean model data pipeline orchestration."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

import xarray as xr

from .config import ModelPipelineSettings
from .errors import IngestionError, ModelPipelineError
from .processing.normalize import normalize_model_dataset
from .processing.region import extract_region
from .processing.regrid import regrid_to_target
from .schema import ModelSource
from .source_selection import SourceAttempt, load_with_explicit_fallback
from .sources.local_demo import LocalDemoSource

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ModelPipelineResult:
    """Result returned by the end-to-end model pipeline."""

    dataset: xr.Dataset
    source: ModelSource
    source_path: str | None
    attempts: list[SourceAttempt] = field(default_factory=list)
    stages: list[str] = field(default_factory=list)


def load_model_data(
    *,
    primary_path: str | Path | None = None,
    fallback_path: str | Path | None = None,
    use_local_demo: bool = False,
    settings: ModelPipelineSettings | None = None,
) -> ModelPipelineResult:
    """Load model data from local demo or primary/fallback sources."""

    cfg = settings or ModelPipelineSettings()
    if use_local_demo:
        logger.info("Loading local demo model source")
        result = LocalDemoSource(settings=cfg).load()
        return ModelPipelineResult(
            dataset=result.dataset,
            source=result.source,
            source_path=result.source_path,
            attempts=[SourceAttempt(ModelSource.LOCAL_DEMO, None, True)],
            stages=["load_local_demo"],
        )

    selected = load_with_explicit_fallback(
        primary_path=primary_path,
        fallback_path=fallback_path,
        settings=cfg,
    )
    return ModelPipelineResult(
        dataset=selected.dataset,  # type: ignore[arg-type]
        source=selected.source,
        source_path=selected.source_path,
        attempts=selected.attempts,
        stages=["load_primary_or_fallback"],
    )


def process_model_data(
    dataset: xr.Dataset,
    *,
    settings: ModelPipelineSettings | None = None,
) -> xr.Dataset:
    """Validate, extract region, normalize units/quality, and regrid."""

    cfg = settings or ModelPipelineSettings()
    stages: list[str] = []

    region = extract_region(dataset, cfg.region)
    stages.append("extract_region")

    normalized, _quality = normalize_model_dataset(
        region,
        required_variables=cfg.required_variables,
    )
    stages.append("normalize_and_quality_check")

    regridded = regrid_to_target(
        normalized,
        cfg.region,
        cfg.target_grid,
        required_variables=cfg.required_variables,
    )
    stages.append("regrid_to_common_target")

    regridded.attrs = {
        **regridded.attrs,
        "pipeline_stages": ",".join(stages),
    }
    return regridded


def prepare_model_dataset(
    *,
    primary_path: str | Path | None = None,
    fallback_path: str | Path | None = None,
    use_local_demo: bool = False,
    settings: ModelPipelineSettings | None = None,
) -> ModelPipelineResult:
    """Single clean entry point for the Checkpoint 7 model pipeline."""

    import time
    start_time = time.perf_counter()

    cfg = settings or ModelPipelineSettings()
    loaded = load_model_data(
        primary_path=primary_path,
        fallback_path=fallback_path,
        use_local_demo=use_local_demo,
        settings=cfg,
    )
    try:
        processed = process_model_data(loaded.dataset, settings=cfg)
    except ModelPipelineError:
        raise
    except Exception as exc:  # noqa: BLE001 - wrap external processing details
        raise ModelPipelineError(f"Model pipeline processing failed: {exc}") from exc

    elapsed_ms = (time.perf_counter() - start_time) * 1000.0
    logger.info("Pipeline completed successfully in %.2f ms", elapsed_ms)
    
    # Add performance metrics to attributes
    processed.attrs["pipeline_runtime_ms"] = f"{elapsed_ms:.2f}"

    return ModelPipelineResult(
        dataset=processed,
        source=loaded.source,
        source_path=loaded.source_path,
        attempts=loaded.attempts,
        stages=[*loaded.stages, "process_model_data"],
    )


def load_local_demo_model_data(
    settings: ModelPipelineSettings | None = None,
) -> ModelPipelineResult:
    """Convenience wrapper for deterministic offline/demo execution."""

    return prepare_model_dataset(use_local_demo=True, settings=settings)

