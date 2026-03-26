"""Benchmark for close random packing of spheres in a rectangular prism"""

from __future__ import annotations

import openmc

BENCHMARK_NAME = "PackSpheresRectangularPrism"


def run_benchmark(threads, mpi_procs):
    min_x = openmc.XPlane(-1)
    max_x = openmc.XPlane(1)
    min_y = openmc.YPlane(-1)
    max_y = openmc.YPlane(1)
    min_z = openmc.ZPlane(-1)
    max_z = openmc.ZPlane(1)
    region = +min_x & -max_x & +min_y & -max_y & +min_z & -max_z
    centers = openmc.model.pack_spheres(
        radius=0.1, region=region, pf=0.5, initial_pf=0.1
    )
