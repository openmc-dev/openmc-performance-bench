"""Benchmark for close random packing of spheres in a cylinder"""

from __future__ import annotations

import openmc

BENCHMARK_NAME = "PackSpheresCylinder"


def run_benchmark(threads, mpi_procs):
    cylinder = openmc.ZCylinder(r=1)
    min_z = openmc.ZPlane(0)
    max_z = openmc.ZPlane(1)
    region = +min_z & -max_z & -cylinder
    centers = openmc.model.pack_spheres(
        radius=0.1, region=region, pf=0.57, initial_pf=0.2, contraction_rate=1e-4
    )
