# SPDX-License-Identifier: MIT
# Copyright (c) 2026 TAKT contributors
# Generated with the assistance of an AI coding tool.
"""Ten independently initialized stock CLI density calculations."""

from pathlib import Path
from tempfile import TemporaryDirectory

from ._density_family import run_family

BENCHMARK_NAME = "DensityFamily"
CONFIGS = ((1, None),)
RETURN_METRICS = ("native_cli_wall_s", "completed_cases")


def run_benchmark(*, threads, mpi_procs):
    with TemporaryDirectory(prefix="openmc-density-family-") as work:
        return run_family(Path(work) / "family", profile="performance", threads=threads)
