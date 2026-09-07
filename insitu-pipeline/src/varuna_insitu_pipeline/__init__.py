"""
VARUNA In-Situ Ocean Observation Data Pipeline & Extensible Adapter Pattern.

Smart India Hackathon 2026 (SIH26067)
Ministry of Earth Sciences - Team Hudson Hackers
"""
from .adapters.base import BaseSensorAdapter, RawObservationRecord
from .adapters.registry import AdapterRegistry, register_adapter
from .config import InSituSettings, settings
from .pipeline import InSituPipeline
from .schemas import (
    ObservationPoint,
    ObservationSnapshot,
    QualityControlReport,
    RegionBounds,
    SensorType,
    VerticalProfile,
)

__version__ = "0.1.0"

__all__ = [
    "AdapterRegistry",
    "BaseSensorAdapter",
    "InSituPipeline",
    "InSituSettings",
    "ObservationPoint",
    "ObservationSnapshot",
    "QualityControlReport",
    "RawObservationRecord",
    "RegionBounds",
    "SensorType",
    "VerticalProfile",
    "register_adapter",
    "settings",
]
