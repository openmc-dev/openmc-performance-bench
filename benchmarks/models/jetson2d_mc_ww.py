"""Monte Carlo benchmark (with weight windows) for the Jetson 2D model.

Runs a fixed-source continuous-energy simulation using pre-generated weight
windows from a FW-CADIS random ray solve.
"""

from __future__ import annotations

from pathlib import Path

import openmc

from ._jetson2d import MC_CUSTOM_METRICS, build_base_model

BENCHMARK_NAME = "Jetson2dMcWw"
CUSTOM_METRICS = MC_CUSTOM_METRICS

_WW_PATH = Path(__file__).parent / "weight_windows.h5"


def build_model() -> openmc.Model:
    model, mesh, plasma_cell = build_base_model()

    # Load pre-generated weight windows
    model.settings.weight_windows = openmc.hdf5_to_wws(_WW_PATH)
    model.settings.weight_window_checkpoints = {
        "collision": True,
        "surface": True,
    }
    model.settings.survival_biasing = False
    model.settings.weight_windows_on = True

    # Adjusted particle counts for variance-reduced run
    model.settings.batches = 10
    model.settings.particles = 200000

    return model
