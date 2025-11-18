"""Point cloud source OpenMC model."""

from __future__ import annotations

import numpy as np
import openmc


def build_model() -> openmc.Model:
    # Create a simple low-density hydrogen material (effectively vacuum)
    mat = openmc.Material(name='Low-density H')
    mat.add_nuclide('H1', 1.0)
    mat.set_density('g/cm3', 1.0e-10)
            
    # Domain lower and upper limit
    d_min = -50.0
    d_max = 50.0

    # Create outer cell
    box = openmc.model.RectangularParallelepiped(
        d_min, d_max, d_min, d_max, d_min, d_max, boundary_type='vacuum'
    )
    geometry = openmc.Geometry([openmc.Cell(fill=mat, region=-box)])

    # Create a point cloud source
    n_points = 100_000
    positions = np.random.uniform(d_min, d_max, n_points * 3).reshape(n_points, 3)
    strengths = np.random.exponential(10, n_points)
    space = openmc.stats.PointCloud(positions, strengths)

    source = openmc.IndependentSource()
    source.angle = openmc.stats.Isotropic()
    source.energy = openmc.stats.delta_function(1.0e6)
    source.space = space

    # Settings with fixed source run and uniform source
    settings = openmc.Settings()
    settings.batches = 10
    settings.particles = 100_000
    settings.run_mode = "fixed source"
    settings.source = source

    return openmc.Model(geometry=geometry, settings=settings)
