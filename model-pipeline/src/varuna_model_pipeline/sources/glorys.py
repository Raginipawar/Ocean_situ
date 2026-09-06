"""Copernicus Marine GLORYS fallback ingestion.

This module keeps GLORYS parsing isolated from INCOIS LAS parsing while
returning the same canonical xarray Dataset structure. It supports fixture/local
NetCDF paths and xarray-readable URLs; live Copernicus authentication/download
work is intentionally outside this checkpoint.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping

import xarray as xr

from ..config import ModelPipelineSettings
from ..errors import IngestionError, MissingCoordinateError, MissingVariableError, UnsupportedUnitError
from ..schema import CANONICAL_VARIABLES, ModelSource, validate_dataset_like

logger = logging.getLogger(__name__)


COORDINATE_CANDIDATES: dict[str, tuple[str, ...]] = {
    "time": ("time", "TIME", "t"),
    "lat": ("latitude", "lat", "nav_lat", "y"),
    "lon": ("longitude", "lon", "nav_lon", "x"),
    "depth": ("depth", "depth_m", "lev", "level"),
}

GLORYS_DEFAULT_MAPPING: dict[str, str] = {
    "thetao": "sst",
    "tos": "sst",
    "analysed_sst": "sst",
    "uo": "u_current",
    "vo": "v_current",
    "VHM0": "wave_height",
    "swh": "wave_height",
    "so": "salinity",
    "chl": "chlorophyll",
    "chl_a": "chlorophyll",
}

SUPPORTED_UNITS: dict[str, set[str]] = {
    "sst": {"degC", "degree_Celsius", "degrees_Celsius", "Celsius", "celsius"},
    "u_current": {"m s-1", "m/s", "meter second-1", "meters second-1"},
    "v_current": {"m s-1", "m/s", "meter second-1", "meters second-1"},
    "wave_height": {"m", "meter", "meters"},
    "salinity": {"1e-3", "psu", "PSU", "0.001", "practical_salinity_unit"},
    "chlorophyll": {"mg m-3", "mg/m^3", "milligram m-3", "mg m^-3"},
}


@dataclass(frozen=True)
class GlorysIngestionResult:
    """Standardized result returned by the GLORYS ingestor."""

    dataset: xr.Dataset
    source: ModelSource = ModelSource.COPERNICUS_GLORYS
    source_path: str | None = None
    coordinate_mapping: dict[str, str] = field(default_factory=dict)
    variable_mapping: dict[str, str] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


class GlorysIngestor:
    """Load and standardize Copernicus Marine GLORYS NetCDF datasets."""

    def __init__(
        self,
        settings: ModelPipelineSettings | None = None,
        variable_mapping: Mapping[str, str] | None = None,
    ) -> None:
        self.settings = settings or ModelPipelineSettings()
        self.variable_mapping = {
            **GLORYS_DEFAULT_MAPPING,
            **dict(variable_mapping or {}),
        }

    def load(self, path_or_url: str | Path) -> GlorysIngestionResult:
        source_ref = str(path_or_url)
        logger.info("Loading GLORYS fallback model dataset from %s", source_ref)
        try:
            raw = xr.open_dataset(path_or_url)
        except Exception as exc:  # noqa: BLE001 - wrap with source context
            raise IngestionError(f"Could not open GLORYS dataset {source_ref!r}: {exc}") from exc
        return self.standardize(raw, source_path=source_ref)

    def standardize(
        self,
        dataset: xr.Dataset,
        *,
        source_path: str | None = None,
    ) -> GlorysIngestionResult:
        coord_mapping = self._detect_coordinates(dataset)
        renamed = dataset.rename(
            {
                source_name: canonical_name
                for canonical_name, source_name in coord_mapping.items()
                if source_name != canonical_name
            }
        )

        variable_mapping = self._resolve_variables(renamed)
        standardized_vars: dict[str, xr.DataArray] = {}
        for source_var, canonical_name in variable_mapping.items():
            source_da = renamed[source_var]
            self._validate_units(canonical_name, source_da)
            canonical_spec = CANONICAL_VARIABLES[canonical_name]
            standardized = source_da.rename(canonical_name)
            standardized.attrs = {
                **source_da.attrs,
                "units": canonical_spec.units,
                "standard_name": canonical_spec.standard_name,
                "long_name": canonical_spec.long_name,
                "source_variable": source_var,
            }
            standardized_vars[canonical_name] = standardized

        canonical = xr.Dataset(
            standardized_vars,
            coords={
                name: renamed.coords[name]
                for name in ("time", "lat", "lon", "depth")
                if name in renamed.coords
            },
            attrs={
                **renamed.attrs,
                "source": ModelSource.COPERNICUS_GLORYS.value,
                "source_url": source_path,
                "region": self.settings.region.name,
                "processing_level": "glorys_ingested",
                "target_resolution_deg": self.settings.target_grid.resolution_deg,
                "history": self._append_history(renamed.attrs.get("history")),
            },
        )

        report = validate_dataset_like(canonical)
        if not report.ok:
            raise MissingVariableError(
                "Standardized GLORYS dataset failed canonical validation: "
                + "; ".join(report.errors)
            )

        return GlorysIngestionResult(
            dataset=canonical,
            source_path=source_path,
            coordinate_mapping=coord_mapping,
            variable_mapping=variable_mapping,
            warnings=report.warnings,
        )

    def _detect_coordinates(self, dataset: xr.Dataset) -> dict[str, str]:
        available_coords = set(dataset.coords)
        available = available_coords | set(dataset.dims)
        mapping: dict[str, str] = {}

        for canonical_name in ("time", "lat", "lon"):
            source_name = self._first_present(
                available_coords, COORDINATE_CANDIDATES[canonical_name]
            )
            if not source_name:
                raise MissingCoordinateError(
                    f"GLORYS dataset is missing required coordinate {canonical_name!r}. "
                    f"Available coordinates/dimensions: {sorted(available)}"
                )
            mapping[canonical_name] = source_name

        depth_name = self._first_present(available_coords, COORDINATE_CANDIDATES["depth"])
        if depth_name:
            mapping["depth"] = depth_name

        return mapping

    def _resolve_variables(self, dataset: xr.Dataset) -> dict[str, str]:
        resolved_by_canonical: dict[str, str] = {}
        for source_var, data_array in dataset.data_vars.items():
            canonical_name = self.variable_mapping.get(source_var)
            if canonical_name is None:
                standard_name = data_array.attrs.get("standard_name")
                canonical_name = self.variable_mapping.get(str(standard_name))
            if canonical_name is None:
                continue
            if canonical_name not in CANONICAL_VARIABLES:
                raise MissingVariableError(
                    f"GLORYS mapping for source variable {source_var!r} points to "
                    f"unknown canonical variable {canonical_name!r}"
                )
            if canonical_name in resolved_by_canonical:
                raise MissingVariableError(
                    f"Multiple GLORYS variables map to {canonical_name!r}: "
                    f"{resolved_by_canonical[canonical_name]!r} and {source_var!r}"
                )
            resolved_by_canonical[canonical_name] = source_var

        missing = [
            name
            for name in self.settings.required_variables
            if name not in resolved_by_canonical
        ]
        if missing:
            raise MissingVariableError(
                f"GLORYS dataset missing required canonical variable(s): {missing}. "
                f"Available variables: {sorted(dataset.data_vars)}"
            )

        return {
            source_var: canonical_name
            for canonical_name, source_var in resolved_by_canonical.items()
        }

    def _validate_units(self, canonical_name: str, data_array: xr.DataArray) -> None:
        units = data_array.attrs.get("units")
        if units is None:
            raise UnsupportedUnitError(
                f"GLORYS variable {data_array.name!r} mapped to {canonical_name!r} "
                "has no units attribute"
            )
        unit_text = str(units).strip()
        if unit_text not in SUPPORTED_UNITS[canonical_name]:
            raise UnsupportedUnitError(
                f"GLORYS variable {data_array.name!r} mapped to {canonical_name!r} "
                f"has unsupported units {unit_text!r}. Supported units: "
                f"{sorted(SUPPORTED_UNITS[canonical_name])}"
            )

    @staticmethod
    def _first_present(available: set[str], candidates: tuple[str, ...]) -> str | None:
        for candidate in candidates:
            if candidate in available:
                return candidate
        return None

    @staticmethod
    def _append_history(existing_history: object) -> str:
        prefix = str(existing_history).strip() if existing_history else ""
        entry = "VARUNA model-pipeline: standardized GLORYS fallback source variables."
        return f"{prefix}\n{entry}" if prefix else entry

