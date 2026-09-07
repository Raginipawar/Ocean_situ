"""
Dynamic Adapter Registry for the In-Situ Observation Pipeline.

Enables runtime discovery, registration, and instantiation of sensor adapters.
"""
from __future__ import annotations

import logging
from collections.abc import Callable
from typing import ClassVar

from .base import BaseSensorAdapter

logger = logging.getLogger("varuna.insitu.registry")


class AdapterRegistry:
    """Registry managing available sensor adapter classes."""

    _registry: ClassVar[dict[str, type[BaseSensorAdapter]]] = {}

    @classmethod
    def register(cls, name: str, adapter_cls: type[BaseSensorAdapter]) -> None:
        """Register an adapter class with a unique key."""
        name_lower = name.lower()
        if name_lower in cls._registry:
            logger.warning("Overwriting adapter registration for %s", name_lower)
        cls._registry[name_lower] = adapter_cls
        logger.debug("Registered adapter: %s -> %s", name_lower, adapter_cls.__name__)

    @classmethod
    def get(cls, name: str) -> type[BaseSensorAdapter] | None:
        """Retrieve an adapter class by name."""
        return cls._registry.get(name.lower())

    @classmethod
    def list_adapters(cls) -> list[str]:
        """List all registered adapter names."""
        return sorted(cls._registry.keys())

    @classmethod
    def instantiate(cls, name: str, **kwargs) -> BaseSensorAdapter:
        """Instantiate an adapter by name with optional kwargs."""
        adapter_cls = cls.get(name)
        if adapter_cls is None:
            raise KeyError(f"No adapter registered under name: '{name}'. Available: {cls.list_adapters()}")
        return adapter_cls(**kwargs)


def register_adapter(name: str) -> Callable[[type[BaseSensorAdapter]], type[BaseSensorAdapter]]:
    """Decorator to auto-register an adapter class."""
    def decorator(cls: type[BaseSensorAdapter]) -> type[BaseSensorAdapter]:
        AdapterRegistry.register(name, cls)
        return cls
    return decorator
