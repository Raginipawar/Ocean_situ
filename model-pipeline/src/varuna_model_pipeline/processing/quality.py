"""Data-quality validation for canonical model datasets."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import xarray as xr

from ..schema import CANONICAL_VARIABLES
from .units import finite_min_max


@dataclass(frozen=True)
class QualityIssue:
    """One data-quality finding."""

    code: str
    message: str
    variable: str | None = None
    severity: str = "error"


@dataclass(frozen=True)
class QualityReport:
    """Aggregated quality-check result."""

    ok: bool
    issues: list[QualityIssue] = field(default_factory=list)

    @property
    def errors(self) -> list[QualityIssue]:
        return [issue for issue in self.issues if issue.severity == "error"]

    @property
    def warnings(self) -> list[QualityIssue]:
        return [issue for issue in self.issues if issue.severity == "warning"]


def validate_quality(
    dataset: xr.Dataset,
    *,
    required_variables: tuple[str, ...] | None = None,
    max_nan_fraction: float = 0.5,
) -> QualityReport:
    """Validate canonical model data quality without mutating the dataset."""

    required = required_variables or tuple(CANONICAL_VARIABLES.keys())
    issues: list[QualityIssue] = []

    for coord_name in ("time", "lat", "lon"):
        if coord_name not in dataset.coords:
            issues.append(QualityIssue("missing_coordinate", f"Missing coordinate {coord_name!r}"))

    if "time" in dataset.coords:
        issues.extend(_validate_time(dataset["time"]))
    for coord_name in ("lat", "lon"):
        if coord_name in dataset.coords:
            issues.extend(_validate_coordinate(dataset[coord_name], coord_name))

    for name in required:
        if name not in dataset.data_vars:
            issues.append(
                QualityIssue("missing_variable", f"Missing required variable {name!r}", name)
            )
            continue
        issues.extend(_validate_variable(dataset[name], name, max_nan_fraction=max_nan_fraction))

    return QualityReport(ok=not any(issue.severity == "error" for issue in issues), issues=issues)


def raise_for_quality(report: QualityReport) -> None:
    """Raise ValueError when a quality report contains errors."""

    if report.ok:
        return
    messages = "; ".join(issue.message for issue in report.errors)
    raise ValueError(f"Canonical model dataset failed quality validation: {messages}")


def _validate_time(time_coord: xr.DataArray) -> list[QualityIssue]:
    issues: list[QualityIssue] = []
    values = np.asarray(time_coord.values)
    if values.size == 0:
        return [QualityIssue("empty_time", "Time coordinate is empty")]

    if not np.issubdtype(values.dtype, np.datetime64):
        return [
            QualityIssue(
                "malformed_timestamp",
                f"Time coordinate must be datetime64, found {values.dtype}",
            )
        ]

    if np.isnat(values).any():
        issues.append(QualityIssue("malformed_timestamp", "Time coordinate contains NaT"))
    return issues


def _validate_coordinate(coord: xr.DataArray, name: str) -> list[QualityIssue]:
    issues: list[QualityIssue] = []
    values = np.asarray(coord.values, dtype=float)
    if values.size == 0:
        return [QualityIssue("empty_coordinate", f"Coordinate {name!r} is empty")]
    if not np.all(np.isfinite(values)):
        issues.append(QualityIssue("invalid_coordinate", f"Coordinate {name!r} contains NaN/Inf"))
    if np.unique(values).size != values.size:
        issues.append(QualityIssue("duplicate_coordinate", f"Coordinate {name!r} contains duplicates"))
    return issues


def _validate_variable(
    data_array: xr.DataArray,
    name: str,
    *,
    max_nan_fraction: float,
) -> list[QualityIssue]:
    issues: list[QualityIssue] = []
    values = np.asarray(data_array.values, dtype=float)
    total = values.size
    if total == 0:
        return [QualityIssue("empty_variable", f"{name}: variable has no values", name)]

    inf_count = int(np.isinf(values).sum())
    if inf_count:
        issues.append(QualityIssue("inf_values", f"{name}: contains {inf_count} Inf value(s)", name))

    nan_fraction = float(np.isnan(values).sum() / total)
    if nan_fraction > max_nan_fraction:
        issues.append(
            QualityIssue(
                "nan_heavy",
                f"{name}: NaN fraction {nan_fraction:.2f} exceeds {max_nan_fraction:.2f}",
                name,
            )
        )
    elif nan_fraction > 0:
        issues.append(
            QualityIssue(
                "nan_values",
                f"{name}: contains NaN values ({nan_fraction:.2%})",
                name,
                severity="warning",
            )
        )

    spec = CANONICAL_VARIABLES[name]
    min_value, max_value = finite_min_max(data_array)
    if min_value is None or max_value is None:
        issues.append(QualityIssue("no_finite_values", f"{name}: contains no finite values", name))
        return issues
    if min_value < spec.valid_min or max_value > spec.valid_max:
        issues.append(
            QualityIssue(
                "impossible_value",
                f"{name}: finite range [{min_value}, {max_value}] outside "
                f"allowed [{spec.valid_min}, {spec.valid_max}]",
                name,
            )
        )

    units = data_array.attrs.get("units")
    if units != spec.units:
        issues.append(
            QualityIssue(
                "invalid_units",
                f"{name}: expected canonical units {spec.units!r}, found {units!r}",
                name,
            )
        )

    return issues

