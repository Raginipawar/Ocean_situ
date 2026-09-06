"""Scientifically explicit unit normalization for canonical model variables."""

from __future__ import annotations

import numpy as np
import xarray as xr

from ..errors import UnsupportedUnitError
from ..schema import CANONICAL_VARIABLES


def normalize_units(dataset: xr.Dataset) -> xr.Dataset:
    """Normalize supported variable units to the canonical VARUNA units.

    Ambiguous or unsupported units raise instead of being guessed. This function
    only performs conversions that are physically direct and explicitly defined.
    """

    out = dataset.copy()
    for name, spec in CANONICAL_VARIABLES.items():
        if name not in out.data_vars:
            continue
        da = out[name]
        source_units = str(da.attrs.get("units", "")).strip()
        if not source_units:
            raise UnsupportedUnitError(f"{name}: missing units attribute")

        converted = _convert_data_array(name, da, source_units, spec.units)
        converted.attrs = {
            **da.attrs,
            "units": spec.units,
            "standard_name": spec.standard_name,
            "long_name": spec.long_name,
            "units_normalized_from": source_units,
        }
        out[name] = converted

    out.attrs = {
        **out.attrs,
        "processing_level": _append_processing_level(
            out.attrs.get("processing_level"), "units_normalized"
        ),
    }
    return out


def _convert_data_array(
    variable: str,
    data_array: xr.DataArray,
    source_units: str,
    target_units: str,
) -> xr.DataArray:
    if source_units == target_units:
        return data_array

    if variable == "sst":
        if source_units in {"K", "kelvin", "Kelvin"} and target_units == "degC":
            return data_array - 273.15
        if source_units in {"degree_Celsius", "degrees_Celsius", "Celsius", "celsius"}:
            return data_array

    if variable in {"u_current", "v_current"}:
        if source_units in {"m/s", "meter second-1", "meters second-1"}:
            return data_array
        if source_units in {"cm s-1", "cm/s", "centimeter second-1"} and target_units == "m s-1":
            return data_array / 100.0

    if variable == "wave_height":
        if source_units in {"meter", "meters"}:
            return data_array
        if source_units in {"cm", "centimeter", "centimeters"} and target_units == "m":
            return data_array / 100.0

    if variable == "salinity":
        if source_units in {"psu", "PSU", "0.001", "practical_salinity_unit"}:
            return data_array

    if variable == "chlorophyll":
        if source_units in {"mg/m^3", "milligram m-3", "mg m^-3"}:
            return data_array

    raise UnsupportedUnitError(
        f"{variable}: unsupported unit conversion from {source_units!r} to {target_units!r}"
    )


def finite_min_max(data_array: xr.DataArray) -> tuple[float | None, float | None]:
    """Return min/max over finite values, or (None, None) when none exist."""

    values = np.asarray(data_array.values, dtype=float)
    finite = values[np.isfinite(values)]
    if finite.size == 0:
        return None, None
    return float(np.nanmin(finite)), float(np.nanmax(finite))


def _append_processing_level(existing: object, stage: str) -> str:
    if not existing:
        return stage
    text = str(existing)
    if stage in text.split("+"):
        return text
    return f"{text}+{stage}"

