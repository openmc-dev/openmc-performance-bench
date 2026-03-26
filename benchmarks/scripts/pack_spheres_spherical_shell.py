"""Benchmark for close random packing of spheres in a spherical shell"""

from __future__ import annotations

import openmc

BENCHMARK_NAME = "PackSpheresSphericalShell"


def run_benchmark(threads, mpi_procs):
    sphere = openmc.Sphere(r=1)
    inner_sphere = openmc.Sphere(r=0.5)
    region = -sphere & +inner_sphere
    centers = openmc.model.pack_spheres(
        radius=0.1, region=region, pf=0.55, initial_pf=0.2, contraction_rate=1e-4
    )
