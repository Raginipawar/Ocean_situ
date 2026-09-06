"""
Argo Float NetCDF Profile Adapter (Ifremer FTP / Coriolis GDAC).

Parses standard oceanographic Argo NetCDF files complying with Argo user manual
specifications (versions 3.1+):
- Coordinates: JULD (converted from 1950-01-01 epoch), LATITUDE, LONGITUDE, PRES
- Physical variables: TEMP, TEMP_ADJUSTED, PSAL, PSAL_ADJUSTED
- Quality flags: TEMP_QC, PSAL_QC, PROFILE_QC
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ..schemas import RegionBounds, SensorType
from .base import BaseSensorAdapter, RawObservationRecord
from .registry import register_adapter

logger = logging.getLogger("varuna.insitu.argo_netcdf")

# Argo reference date: 1950-01-01 00:00:00 UTC
ARGO_EPOCH = datetime(1950, 1, 1, 0, 0, 0, tzinfo=timezone.utc)


def argo_juld_to_datetime(juld_val: float) -> datetime:
    """Convert Argo JULD (days since 1950-01-01) to UTC datetime."""
    try:
        return ARGO_EPOCH + timedelta(days=float(juld_val))
    except (ValueError, TypeError, OverflowError):
        return datetime.now(timezone.utc)


@register_adapter("argo_netcdf")
class ArgoNetCDFAdapter(BaseSensorAdapter):
    """
    Adapter reading Argo profiling float NetCDF files.
    """

    def __init__(self, file_path_or_dir: str | Path | None = None):
        self.target_path = Path(file_path_or_dir) if file_path_or_dir else None

    @property
    def adapter_name(self) -> str:
        return "argo_netcdf"

    @property
    def supported_sensor_types(self) -> list[SensorType]:
        return [SensorType.ARGO]

    def _parse_netcdf_file(self, path: Path) -> list[RawObservationRecord]:
        """Parse a single Argo NetCDF file using available netcdf libraries or fallback."""
        records: list[RawObservationRecord] = []
        try:
            import xarray as xr  # type: ignore
            ds = xr.open_dataset(path)
            
            # Extract metadata
            platform_num = str(ds.attrs.get("platform_number", path.stem))
            
            # Coordinates
            lats = ds["LATITUDE"].values
            lons = ds["LONGITUDE"].values
            julds = ds["JULD"].values if "JULD" in ds else [0.0]
            
            # Determine best available temp & psal variables
            temp_var = "TEMP_ADJUSTED" if "TEMP_ADJUSTED" in ds else "TEMP"
            psal_var = "PSAL_ADJUSTED" if "PSAL_ADJUSTED" in ds else "PSAL"
            pres_var = "PRES_ADJUSTED" if "PRES_ADJUSTED" in ds else "PRES"
            
            temps = ds[temp_var].values if temp_var in ds else None
            psals = ds[psal_var].values if psal_var in ds else None
            press = ds[pres_var].values if pres_var in ds else None
            
            temp_qc = ds[f"{temp_var}_QC"].values if f"{temp_var}_QC" in ds else None
            
            n_profiles = len(lats) if hasattr(lats, "__len__") else 1
            for p_idx in range(n_profiles):
                lat = float(lats[p_idx]) if hasattr(lats, "__getitem__") else float(lats)
                lon = float(lons[p_idx]) if hasattr(lons, "__getitem__") else float(lons)
                try:
                    juld = float(julds[p_idx])
                except (IndexError, TypeError):
                    juld = 0.0
                dt = argo_juld_to_datetime(juld)
                
                # Iterate levels
                if temps is not None and len(temps.shape) > 1:
                    n_levels = temps.shape[1]
                    for lev in range(n_levels):
                        depth = float(press[p_idx, lev]) if press is not None else lev * 2.0
                        t = float(temps[p_idx, lev])
                        s = float(psals[p_idx, lev]) if psals is not None else None
                        qc = int(temp_qc[p_idx, lev]) if temp_qc is not None else 1
                        
                        records.append(
                            RawObservationRecord(
                                source_adapter="argo_netcdf",
                                sensor_id=f"argo-{platform_num}",
                                sensor_type=SensorType.ARGO,
                                raw_lat=lat,
                                raw_lon=lon,
                                raw_depth=depth,
                                time=dt,
                                raw_sst=t,
                                raw_salinity=s,
                                qc_flag=qc,
                            )
                        )
            ds.close()
        except ImportError:
            logger.warning("xarray/netCDF4 not available to read %s directly.", path)
        except (OSError, ValueError, KeyError) as exc:
            logger.warning("Error reading Argo NetCDF %s: %s", path, exc)

        return records

    def fetch_raw(
        self,
        bounds: RegionBounds,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> list[RawObservationRecord]:
        """Read all configured NetCDF files."""
        if not self.target_path or not self.target_path.exists():
            return []

        records: list[RawObservationRecord] = []
        if self.target_path.is_file() and self.target_path.suffix in (".nc", ".nc4"):
            records.extend(self._parse_netcdf_file(self.target_path))
        elif self.target_path.is_dir():
            for f in self.target_path.glob("*.nc"):
                records.extend(self._parse_netcdf_file(f))

        return records
