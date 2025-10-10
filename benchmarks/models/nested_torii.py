"""Nested torii for distance-to-boundary benchmarking"""

from __future__ import annotations

import openmc
import numpy as np

BENCHMARK_NAME = "NestedTorii"


def build_model() -> openmc.Model:
    # Create a simple low-density hydrogen material (effectively vacuum)
    mat = openmc.Material(name='Low-density H')
    mat.add_nuclide('H1', 1.0)
    mat.set_density('g/cm3', 1.0e-10)

    # Create 100 nested toroidal shells
    n_shells = 100
    major_radius = 50.0  # Distance from origin to center of torus tube
    minor_radius_inner = 1.0  # Inner tube radius
    minor_radius_outer = 20.0  # Outer tube radius

    # Generate minor radii for shells (linearly spaced)
    minor_radii = np.linspace(minor_radius_inner, minor_radius_outer, n_shells + 1)

    # Create toroidal surfaces (Z-axis torus)
    torii = [openmc.ZTorus(a=major_radius, b=b, c=b) for b in minor_radii]

    # Create a bounding sphere for vacuum boundary
    bounding_sphere = openmc.Sphere(r=major_radius + minor_radius_outer + 10.0,
                                     boundary_type='vacuum')

    # Create cells
    cells = []
    for i in range(n_shells + 1):
        if i == 0:
            # Innermost cell (inside first torus)
            region = -torii[i] & -bounding_sphere
        else:
            # Shell cells (between consecutive torii)
            region = +torii[i - 1] & -torii[i] & -bounding_sphere

        cell = openmc.Cell(fill=mat, region=region)
        cells.append(cell)

    # Add outermost cell (outside last torus but inside bounding sphere)
    outer_cell = openmc.Cell(fill=mat, region=+torii[-1] & -bounding_sphere)
    cells.append(outer_cell)

    geometry = openmc.Geometry(cells)

    # Settings with point source in the first (innermost) cell
    settings = openmc.Settings()
    settings.batches = 10
    settings.inactive = 5
    settings.particles = 10000
    settings.run_mode = "fixed source"

    # Point source at a point inside the first torus
    # Place it at (major_radius, 0, 0) which is in the center of the torus tube
    source = openmc.IndependentSource()
    source.space = openmc.stats.Point((major_radius, 0, 0))
    source.energy = openmc.stats.delta_function(1.0e6)
    settings.source = source

    return openmc.Model(geometry=geometry, settings=settings)
