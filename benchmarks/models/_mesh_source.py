"""Helper function for building a mesh source OpenMC model."""

from __future__ import annotations

import numpy as np
import openmc


def build_model(mesh_type : str) -> openmc.Model:
    # Create a simple low-density hydrogen material (effectively vacuum)
    mat = openmc.Material(name='Low-density H')
    mat.add_nuclide('H1', 1.0)
    mat.set_density('g/cm3', 1.0e-10)
            
    # Create outer cell
    box = openmc.model.RectangularParallelepiped(
        -50.0, 50.0, -50.0, 50.0, -50.0, 50.0, boundary_type='vacuum'
    )   
    geometry = openmc.Geometry([openmc.Cell(fill=mat, region=-box)])

    # Create a mesh on the geometry
    dim = (32, 32, 32)
    if mesh_type == 'regular':
        mesh = openmc.RegularMesh.from_domain(geometry, dim)
    elif mesh_type == 'cylindrical':
        mesh = openmc.CylindricalMesh.from_domain(geometry, dim)
    elif mesh_type == 'spherical':
        mesh = openmc.SphericalMesh.from_domain(geometry, dim)

    # Create sources with different intensities for each mesh element
    strengths = np.random.exponential(10, dim[0] * dim[1] * dim[2])
    strengths /= np.sum(strengths)
    sources = []
    for strength in strengths:
        source = openmc.IndependentSource()
        source.strength = strength
        source.angle = openmc.stats.Isotropic()
        source.energy = openmc.stats.delta_function(1.0e6)
        sources.append(source)

    # Settings with fixed source run and uniform source
    settings = openmc.Settings()
    settings.batches = 10
    settings.particles = 100_000
    settings.run_mode = "fixed source"
    settings.source = openmc.MeshSource(mesh, sources)

    return openmc.Model(geometry=geometry, settings=settings)
