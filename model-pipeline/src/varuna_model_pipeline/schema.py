"""Canonical schema definitions for VARUNA ocean model data."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, model_validator


class ModelSource(str, Enum):
    """Allowed ocean model data sources."""

    INCOIS_LAS = "INCOIS_LAS"
    COPERNICUS_GLORYS = "COPERNICUS_GLORYS"
    LOCAL_DEMO = "LOCAL_DEMO"


class CanonicalVariable(BaseModel):
    """Metadata for one canonical model variable."""

    name: str
    api_name: str
    standard_name: str
    long_name: str
    units: str
    valid_min: float
    valid_max: float
    preserve_depth: bool = False

    @model_validator(mode="after")
    def validate_range(self) -> "CanonicalVariable":
        if self.valid_min >= self.valid_max:
            raise ValueError(f"{self.name}: valid_min must be less than valid_max")
        return self


CANONICAL_VARIABLES: dict[str, CanonicalVariable] = {
    "sst": CanonicalVariable(
        name="sst",
        api_name="sst_c",
        standard_name="sea_surface_temperature",
        long_name="Sea Surface Temperature",
        units="degC",
        valid_min=-2.0,
        valid_max=45.0,
        preserve_depth=False,
    ),
    "u_current": CanonicalVariable(
        name="u_current",
        api_name="current_u_ms",
        standard_name="eastward_sea_water_velocity",
        long_name="Eastward Sea Water Velocity",
        units="m s-1",
        valid_min=-5.0,
        valid_max=5.0,
        preserve_depth=True,
    ),
    "v_current": CanonicalVariable(
        name="v_current",
        api_name="current_v_ms",
        standard_name="northward_sea_water_velocity",
        long_name="Northward Sea Water Velocity",
        units="m s-1",
        valid_min=-5.0,
        valid_max=5.0,
        preserve_depth=True,
    ),
    "wave_height": CanonicalVariable(
        name="wave_height",
        api_name="wave_height_m",
        standard_name="sea_surface_wave_significant_height",
        long_name="Significant Wave Height",
        units="m",
        valid_min=0.0,
        valid_max=25.0,
        preserve_depth=False,
    ),
    "salinity": CanonicalVariable(
        name="salinity",
        api_name="salinity",
        standard_name="sea_water_practical_salinity",
        long_name="Practical Salinity",
        units="1e-3",
        valid_min=0.0,
        valid_max=42.0,
        preserve_depth=True,
    ),
    "chlorophyll": CanonicalVariable(
        name="chlorophyll",
        api_name="chlorophyll",
        standard_name="mass_concentration_of_chlorophyll_a_in_sea_water",
        long_name="Chlorophyll-a Concentration",
        units="mg m-3",
        valid_min=0.0,
        valid_max=100.0,
        preserve_depth=False,
    ),
}


class CanonicalDatasetMetadata(BaseModel):
    """Required metadata for a processed canonical model dataset."""

    source: ModelSource
    source_url: str | None = None
    region: str = "bay_of_bengal"
    processing_level: str = "canonical_schema"
    target_resolution_deg: float = Field(..., gt=0.0)
    variables: dict[str, CanonicalVariable]
    history: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_variables(self) -> "CanonicalDatasetMetadata":
        missing = sorted(set(CANONICAL_VARIABLES) - set(self.variables))
        if missing:
            raise ValueError(f"Missing canonical variable metadata: {missing}")
        return self


class CanonicalSchemaReport(BaseModel):
    """Validation result for a dataset-like object's schema."""

    ok: bool
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


def expected_coordinate_names() -> tuple[str, ...]:
    """Return canonical coordinate names for the xarray Dataset."""

    return ("time", "lat", "lon")


def validate_dataset_like(dataset: Any) -> CanonicalSchemaReport:
    """Validate the canonical structure of an xarray-like Dataset.

    This accepts any object exposing xarray-style ``coords``, ``data_vars``,
    and ``attrs`` mappings so Checkpoint 1 can be tested without requiring
    NetCDF dependencies to be installed in the current runtime.
    """

    errors: list[str] = []
    warnings: list[str] = []

    coords = getattr(dataset, "coords", {})
    data_vars = getattr(dataset, "data_vars", {})
    attrs = getattr(dataset, "attrs", {})

    for coord in expected_coordinate_names():
        if coord not in coords:
            errors.append(f"Missing coordinate: {coord}")

    for name, spec in CANONICAL_VARIABLES.items():
        if name not in data_vars:
            errors.append(f"Missing canonical variable: {name}")
            continue

        variable = data_vars[name]
        units = getattr(variable, "attrs", {}).get("units")
        if units != spec.units:
            errors.append(
                f"{name}: expected units {spec.units!r}, found {units!r}"
            )

    for attr in ("source", "region", "processing_level", "target_resolution_deg"):
        if attr not in attrs:
            errors.append(f"Missing dataset attr: {attr}")

    if "depth" not in coords:
        depth_vars = [name for name, spec in CANONICAL_VARIABLES.items() if spec.preserve_depth]
        warnings.append(
            "No depth coordinate present; depth-preserving variables should document "
            f"surface-only selection or retain depth later: {depth_vars}"
        )

    return CanonicalSchemaReport(ok=not errors, errors=errors, warnings=warnings)


def build_default_metadata(
    source: ModelSource = ModelSource.LOCAL_DEMO,
    source_url: str | None = None,
    target_resolution_deg: float = 1.0,
) -> CanonicalDatasetMetadata:
    """Build default canonical metadata for examples and tests."""

    return CanonicalDatasetMetadata(
        source=source,
        source_url=source_url,
        target_resolution_deg=target_resolution_deg,
        variables=CANONICAL_VARIABLES,
        history=["Checkpoint 1 schema metadata generated."],
    )

