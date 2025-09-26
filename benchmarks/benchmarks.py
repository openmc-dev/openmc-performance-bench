"""Public entry point for asv to discover benchmark classes."""

from __future__ import annotations

from .models import build_infinite_medium_model
from .suites.base import make_benchmark

InfiniteMediumEigenvalue = make_benchmark(
    "InfiniteMediumEigenvalue",
    build_infinite_medium_model,
)

__all__ = ["InfiniteMediumEigenvalue"]
