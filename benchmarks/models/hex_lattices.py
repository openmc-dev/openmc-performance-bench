"""Nested hexagonal lattice OpenMC model."""

from __future__ import annotations

import openmc
import numpy as np

BENCHMARK_NAME = "HexLattices"


def build_model() -> openmc.Model:
    # Create a simple low-density hydrogen material (effectively vacuum)
    mat = openmc.Material(name='Low-density H')
    mat.add_nuclide('H1', 1.0)
    mat.set_density('g/cm3', 1.0e-10)

    # Number of rings and axial layers for inner and outer nested lattices
    n_rings_inner = 10
    n_axial_inner = 40
    n_rings_outer = 10
    n_axial_outer = 40

    # Lattice element edge length, axial pitch, and minimal diameter
    edge_inner = 10.0
    z_pitch_inner = 10.0
    pitch_inner = np.sqrt(3) * edge_inner
    edge_outer = pitch_inner * n_rings_inner
    z_pitch_outer = z_pitch_inner * n_axial_inner
    pitch_outer = np.sqrt(3) * edge_outer

    # Universe applied outside the defined lattices
    u_outer = openmc.Universe(cells=[openmc.Cell(fill=mat)])
    
    # Helper function to create the rings of the lattice
    def make_rings(n, fill):
        rings = []
        for i in range(n - 1, 0, -1):
            u = openmc.Universe(cells=[openmc.Cell(fill=fill)])
            rings.append([u] * 6 * i)
        rings.append([openmc.Universe(cells=[openmc.Cell(fill=fill)])])
        return rings

    # Inner rectangular lattice filled with a single material
    lat_inner = openmc.HexLattice()
    lat_inner.center = (0.0, 0.0, 0.0)
    lat_inner.pitch = (pitch_inner, z_pitch_inner)
    lat_inner.orientation = 'x'
    lat_inner.outer = u_outer
    lat_inner.universes = [make_rings(n_rings_inner, mat)] * n_axial_inner

    # Outer rectangular lattice filled with inner lattice
    lat_outer = openmc.HexLattice()
    lat_outer.center = (0.0, 0.0, 0.0)
    lat_outer.pitch = (pitch_outer, z_pitch_outer)
    lat_outer.orientation = 'y'
    lat_outer.outer = u_outer
    lat_outer.universes = [make_rings(n_rings_outer, lat_inner)] * n_axial_outer
    
    # Create outer cell filled with the lattice
    hex_prism = openmc.model.HexagonalPrism(
        edge_length=pitch_outer * n_rings_outer, boundary_type='vacuum'
    )
    geometry = openmc.Geometry([openmc.Cell(fill=lat_outer, region=-hex_prism)])

    # Isotropic point source
    source = openmc.IndependentSource()
    source.space = openmc.stats.Point((0, 0, 0))
    source.angle = openmc.stats.Isotropic()
    source.energy = openmc.stats.delta_function(1.0e6)

    # Settings with fixed source run
    settings = openmc.Settings()
    settings.batches = 10
    settings.particles = 100_000
    settings.run_mode = "fixed source"
    settings.source = source

    return openmc.Model(geometry=geometry, settings=settings)
