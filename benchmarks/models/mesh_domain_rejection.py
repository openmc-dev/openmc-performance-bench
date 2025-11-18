"""Mesh source OpenMC model with domain rejection."""

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

    # Create region for outer cell
    box = openmc.model.RectangularParallelepiped(
        d_min, d_max, d_min, d_max, d_min, d_max, boundary_type='vacuum'
    )

    # Create points for cylinder centers
    centers = np.array([
        (x, y)
        for x in np.linspace(d_min, d_max, 10)
        for y in np.linspace(d_min, d_max, 10)
    ])

    # Create cells to use for domain rejection
    holes = None
    cells = []
    for (x, y) in centers:
        cylinder = openmc.ZCylinder(x0=x, y0=y, r=2.0)
        region = -box & -cylinder
        cell = openmc.Cell(fill=mat, region=region)
        cells.append(cell)
        if holes is None:
            holes = -cylinder
        else:
            holes = holes | -cylinder

    # Inside box and outside cylinders
    outer_region = -box & ~holes
    outer_cell = openmc.Cell(fill=mat, region=outer_region)

    # Create a mesh on the geometry
    geometry = openmc.Geometry([outer_cell, *cells])
    dim = (16, 16, 16)
    mesh = openmc.RegularMesh.from_domain(geometry, dim)

    # Create sources with different intensities for each mesh element
    strengths = np.random.exponential(5, dim[0] * dim[1] * dim[2])
    strengths /= np.sum(strengths)
    sources = []
    for strength in strengths:
        source = openmc.IndependentSource()
        source.strength = strength
        source.angle = openmc.stats.Isotropic()
        source.energy = openmc.stats.delta_function(1.0e6)
        source.constraints['domains'] = [outer_cell]
        sources.append(source)

    # Settings with fixed source run and uniform source
    settings = openmc.Settings()
    settings.batches = 10
    settings.particles = 100_000
    settings.run_mode = "fixed source"
    settings.source = openmc.MeshSource(mesh, sources)

    return openmc.Model(geometry=geometry, settings=settings)
