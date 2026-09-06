"""Source-specific ocean model ingestion modules."""

from .glorys import GlorysIngestionResult, GlorysIngestor
from .incois_las import IncoisLasIngestor, IncoisLasIngestionResult
from .local_demo import LocalDemoSource, LocalDemoIngestionResult

__all__ = [
    "GlorysIngestionResult",
    "GlorysIngestor",
    "IncoisLasIngestionResult",
    "IncoisLasIngestor",
    "LocalDemoIngestionResult",
    "LocalDemoSource",
]
