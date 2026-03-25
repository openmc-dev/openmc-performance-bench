"""MGXS generation benchmark for the Jetson 2D model.

Builds the continuous-energy Jetson 2D model and generates multigroup cross
sections via the stochastic slab method.  This internally runs the OpenMC
executable to compute MGXS data.
"""

from __future__ import annotations

import openmc.mgxs

from benchmarks.models._jetson2d import build_base_model

BENCHMARK_NAME = "Jetson2dMgxs"
THREAD_OPTIONS = (1, 2, 4)


def run_benchmark(threads, mpi_procs):
    model, mesh, plasma_cell = build_base_model()
    group_edges = openmc.mgxs.GROUP_STRUCTURES["CASMO-4"]
    model.convert_to_multigroup(
        method="stochastic_slab",
        nparticles=1000,
        groups=openmc.mgxs.EnergyGroups(group_edges),
        overwrite_mgxs_library=False,
        correction=None,
    )
