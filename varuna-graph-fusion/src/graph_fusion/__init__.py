"""
graph_fusion -- VARUNA's Graph Fusion Engine (SIH26067, Person 1 / Intelligence Core #1).

Corrects the ocean forecast model grid using a graph of real in-situ sensor
readings, with edges weighted by oceanographic connectivity (current
alignment + depth similarity + distance decay) rather than raw distance.
"""
from .fallback_engine import FallbackFusionEngine
from .fusion_service import FusionService
from .gnn_engine import GNNFusionEngine
from .graph_builder import FusionGraph, SensorGraphBuilder

__all__ = [
    "FusionService",
    "SensorGraphBuilder",
    "FusionGraph",
    "GNNFusionEngine",
    "FallbackFusionEngine",
]

__version__ = "0.1.0"
