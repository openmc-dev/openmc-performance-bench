"""Benchmark for close random packing of spheres in a sphere"""

from __future__ import annotations

import openmc

BENCHMARK_NAME = "PackSpheresSphere"


def run_benchmark(threads, mpi_procs):
    sphere = openmc.Sphere(r=3)
    region = -sphere
    centers = openmc.model.pack_spheres(
        radius=0.1, region=region, pf=0.4, initial_pf=0.2
    )
