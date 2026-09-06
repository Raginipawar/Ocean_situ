"""Central configuration for the VARUNA ocean model data pipeline."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import BaseModel, Field, model_validator
from pydantic_settings import BaseSettings

from .schema import CANONICAL_VARIABLES, ModelSource


class RegionBounds(BaseModel):
    """Geographic bounds in EPSG:4326 degrees."""

    name: str = "bay_of_bengal"
    lat_min: float = Field(5.0, ge=-90.0, le=90.0)
    lat_max: float = Field(22.0, ge=-90.0, le=90.0)
    lon_min: float = Field(80.0, ge=-180.0, le=360.0)
    lon_max: float = Field(100.0, ge=-180.0, le=360.0)

    @model_validator(mode="after")
    def validate_bounds(self) -> "RegionBounds":
        if self.lat_min >= self.lat_max:
            raise ValueError("lat_min must be less than lat_max")
        if self.lon_min >= self.lon_max:
            raise ValueError("lon_min must be less than lon_max")
        return self


class TargetGridConfig(BaseModel):
    """Common target grid settings used before downstream handoff."""

    resolution_deg: float = Field(1.0, gt=0.0, le=5.0)
    method: Literal["nearest", "linear"] = "linear"


class TimeRangeConfig(BaseModel):
    """Optional time window for demo/model extraction."""

    start: str | None = None
    end: str | None = None


class SourceConfig(BaseModel):
    """Source endpoint and variable mapping configuration."""

    source: ModelSource
    url: str | None = None
    variable_mapping: dict[str, str] = Field(default_factory=dict)


class ModelPipelineSettings(BaseSettings):
    """Pipeline settings.

    Environment variables use the VARUNA_MODEL_ prefix. Nested values can be
    supplied with double underscores, for example:

    VARUNA_MODEL_REGION__LAT_MIN=5.0
    """

    primary_source: ModelSource = ModelSource.INCOIS_LAS
    fallback_source: ModelSource = ModelSource.COPERNICUS_GLORYS
    demo_source: ModelSource = ModelSource.LOCAL_DEMO

    incois_las_url: str | None = None
    glorys_url: str | None = None
    local_demo_path: str | None = None

    region: RegionBounds = Field(default_factory=RegionBounds)
    target_grid: TargetGridConfig = Field(default_factory=TargetGridConfig)
    time_range: TimeRangeConfig = Field(default_factory=TimeRangeConfig)

    required_variables: tuple[str, ...] = tuple(CANONICAL_VARIABLES.keys())
    missing_value_policy: Literal["preserve_nan", "fail_on_nan_heavy"] = "preserve_nan"
    output_format: Literal["xarray_dataset_plus_model_snapshot_json"] = (
        "xarray_dataset_plus_model_snapshot_json"
    )

    model_config = {
        "env_prefix": "VARUNA_MODEL_",
        "env_nested_delimiter": "__",
        "case_sensitive": False,
    }

    @model_validator(mode="after")
    def validate_required_variables(self) -> "ModelPipelineSettings":
        unknown = sorted(set(self.required_variables) - set(CANONICAL_VARIABLES))
        if unknown:
            raise ValueError(f"Unknown canonical required variable(s): {unknown}")
        return self


@lru_cache(maxsize=1)
def get_settings() -> ModelPipelineSettings:
    """Return cached model-pipeline settings."""

    return ModelPipelineSettings()

