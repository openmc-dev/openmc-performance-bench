"""Monte Carlo benchmark (no variance reduction) for the Jetson 2D model.

Runs a fixed-source continuous-energy simulation without weight windows,
serving as a baseline comparison for the weight-window-accelerated run.
"""

from __future__ import annotations

import openmc

from ._jetson2d import MC_CUSTOM_METRICS, build_base_model

BENCHMARK_NAME = "Jetson2dMcAnalog"
CUSTOM_METRICS = MC_CUSTOM_METRICS


def build_model() -> openmc.Model:
    model, mesh, plasma_cell = build_base_model()
    model.settings.batches = 50
    model.settings.particles = 4500
    return model
