"""
In-Situ Sensor Adapters package.

Exposes the base class, registry, and concrete adapters for:
- Deterministic Local Demo (Bay of Bengal)
- Argovis REST API (Argo Floats)
- Argo NetCDF (Coriolis GDAC / Ifremer)
- Moored Buoys (NIOT OMNI / RAMA)
- NOAA World Ocean Database (CTD / XBT)
- Autonomous Underwater Gliders
"""
from .argo_netcdf import ArgoNetCDFAdapter
from .argovis_api import ArgovisRestAdapter
from .base import BaseSensorAdapter, RawObservationRecord
from .buoy_adapter import BuoyObservationAdapter
from .glider_netcdf import GliderNetCDFAdapter
from .local_demo import LocalDemoObservationAdapter
from .noaa_wod import NoaaWodAdapter
from .registry import AdapterRegistry, register_adapter

__all__ = [
    "AdapterRegistry",
    "ArgoNetCDFAdapter",
    "ArgovisRestAdapter",
    "BaseSensorAdapter",
    "BuoyObservationAdapter",
    "GliderNetCDFAdapter",
    "LocalDemoObservationAdapter",
    "NoaaWodAdapter",
    "RawObservationRecord",
    "register_adapter",
]
