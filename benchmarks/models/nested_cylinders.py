"""Nested cylinders for distance-to-boundary benchmarking"""

from __future__ import annotations

import openmc
import numpy as np

BENCHMARK_NAME = "NestedCylinders"


def build_model() -> openmc.Model:
    # Create a simple low-density hydrogen material (effectively vacuum)
    mat = openmc.Material(name='Low-density H')
    mat.add_nuclide('H1', 1.0)
    mat.set_density('g/cm3', 1.0e-10)

    # Create 100 nested cylindrical shells
    n_shells = 100
    r_inner = 1.0
    r_outer = 100.0
    z_min = -50.0
    z_max = 50.0

    # Generate radii for shells (linearly spaced)
    radii = np.linspace(r_inner, r_outer, n_shells + 1)

    # Create cylindrical surfaces (infinite Z cylinders)
    cylinders = [openmc.ZCylinder(r=r) for r in radii]

    # Create top and bottom planes
    z_bottom = openmc.ZPlane(z0=z_min, boundary_type='vacuum')
    z_top = openmc.ZPlane(z0=z_max, boundary_type='vacuum')

    # Set vacuum boundary on outermost cylinder
    cylinders[-1].boundary_type = 'vacuum'

    # Create cells
    cells = []
    for i in range(n_shells + 1):
        if i == 0:
            # Innermost cell
            region = -cylinders[i] & +z_bottom & -z_top
        else:
            # Shell cells
            region = +cylinders[i - 1] & -cylinders[i] & +z_bottom & -z_top

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
