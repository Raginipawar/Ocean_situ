"""Typed exceptions for model-pipeline failures."""

from __future__ import annotations


class ModelPipelineError(Exception):
    """Base error for model-pipeline failures."""


class IngestionError(ModelPipelineError):
    """Raised when a source dataset cannot be opened or interpreted safely."""


class MissingCoordinateError(IngestionError):
    """Raised when required geospatial/time coordinates are absent."""


class MissingVariableError(IngestionError):
    """Raised when required model variables are absent."""


class UnsupportedUnitError(IngestionError):
    """Raised when a source variable has unsupported or ambiguous units."""

