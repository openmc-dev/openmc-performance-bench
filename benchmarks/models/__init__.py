"""OpenMC model builders used by the benchmark suites."""

from .infinite_medium import build_model as build_infinite_medium_model

__all__ = ["build_infinite_medium_model"]
