"""Variable and metadata normalization for canonical model datasets."""

from __future__ import annotations

import xarray as xr

from ..errors import MissingVariableError
from ..schema import CANONICAL_VARIABLES, validate_dataset_like
from .quality import QualityReport, raise_for_quality, validate_quality
from .units import normalize_units


def normalize_model_dataset(
    dataset: xr.Dataset,
    *,
    required_variables: tuple[str, ...] | None = None,
    max_nan_fraction: float = 0.5,
) -> tuple[xr.Dataset, QualityReport]:
    """Normalize canonical variables, units, and validate scientific quality."""

    required = required_variables or tuple(CANONICAL_VARIABLES.keys())
    missing = [name for name in required if name not in dataset.data_vars]
    if missing:
        raise MissingVariableError(f"Missing required canonical variable(s): {missing}")

    normalized = normalize_units(dataset)
    schema_report = validate_dataset_like(normalized)
    if not schema_report.ok:
        raise MissingVariableError(
            "Normalized model dataset failed canonical schema validation: "
            + "; ".join(schema_report.errors)
        )

    quality_report = validate_quality(
        normalized,
        required_variables=required,
        max_nan_fraction=max_nan_fraction,
    )
    raise_for_quality(quality_report)

    normalized.attrs = {
        **normalized.attrs,
        "processing_level": _append_processing_level(
            normalized.attrs.get("processing_level"), "quality_checked"
        ),
    }
    return normalized, quality_report


def _append_processing_level(existing: object, stage: str) -> str:
    if not existing:
        return stage
    text = str(existing)
    if stage in text.split("+"):
        return text
    return f"{text}+{stage}"

