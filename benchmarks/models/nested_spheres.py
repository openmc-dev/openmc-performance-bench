"""Nested spheres for distance-to-boundary benchmarking"""

from __future__ import annotations

import openmc
import numpy as np

BENCHMARK_NAME = "NestedSpheres"


def build_model() -> openmc.Model:
    # Create a simple low-density hydrogen material (effectively vacuum)
    mat = openmc.Material(name='Low-density H')
    mat.add_nuclide('H1', 1.0)
    mat.set_density('g/cm3', 1.0e-10)

    # Create 100 nested spherical shells
    n_shells = 100
    r_inner = 1.0
    r_outer = 100.0

    # Generate radii for shells (linearly spaced)
    radii = np.linspace(r_inner, r_outer, n_shells + 1)

    # Create spherical surfaces
    spheres = [openmc.Sphere(r=r) for r in radii]

    # Set vacuum boundary on outermost sphere
    spheres[-1].boundary_type = 'vacuum'

    # Create cells
    cells = []
    for i in range(n_shells + 1):
        if i == 0:
            # Innermost cell
            region = -spheres[i]
        else:
            # Shell cells
            region = +spheres[i - 1] & -spheres[i]

        cell = openmc.Cell(fill=mat, region=region)
        cells.append(cell)

    geometry = openmc.Geometry(cells)

    # Settings with point source in the first (innermost) cell
    settings = openmc.Settings()
    settings.batches = 10
    settings.inactive = 5
    settings.particles = 100000
    settings.run_mode = "fixed source"

    # Point source at origin (center of first cell)
    source = openmc.IndependentSource()
    source.space = openmc.stats.Point((0, 0, 0))
    source.energy = openmc.stats.delta_function(1.0e6)
    settings.source = source

    return openmc.Model(geometry=geometry, settings=settings)
