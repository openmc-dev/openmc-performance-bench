"""Nested rectangular lattice OpenMC model."""

from __future__ import annotations

import numpy as np
import openmc

BENCHMARK_NAME = "RectLattices"


def build_model() -> openmc.Model:
    # Create a simple low-density hydrogen material (effectively vacuum)
    mat = openmc.Material(name='Low-density H')
    mat.add_nuclide('H1', 1.0)
    mat.set_density('g/cm3', 1.0e-10)

    # Domain length and number of outer and nested lattice elements
    length = 100.0
    n_outer = 40
    n_inner = 20

    # Distance between lattice element centers
    pitch_outer = length / n_outer
    pitch_inner = pitch_outer / n_inner

    # Lower left and upper right lattice coordinates
    ll_outer = (-0.5 * length, -0.5 * length, -0.5 * length)
    ur_outer = (0.5 * length, 0.5 * length, 0.5 * length)
    ll_inner = (-0.5 * pitch_outer, -0.5 * pitch_outer, -0.5 * pitch_outer)
    
    # Universe applied outside the defined lattices
    u_outer = openmc.Universe(cells=[openmc.Cell(fill=mat)])

    # Inner rectangular lattice filled with a single material
    lat_inner = openmc.RectLattice()
    lat_inner.lower_left = ll_inner
    lat_inner.pitch = (pitch_inner, pitch_inner, pitch_inner)
    lat_inner.universes = np.tile(
        [openmc.Universe(cells=[openmc.Cell(fill=mat)]) for _ in range(n_inner)],
        (n_inner, n_inner, 1)
    )
    lat_inner.outer = u_outer

    # Outer rectangular lattice filled with inner lattice
    lat_outer = openmc.RectLattice()
    lat_outer.lower_left = ll_outer
    lat_outer.pitch = (pitch_outer, pitch_outer, pitch_outer)
    lat_outer.universes = np.full(
        (n_outer, n_outer, n_outer),
        openmc.Universe(cells=[openmc.Cell(fill=lat_inner)])
    )
    lat_outer.outer = u_outer
    
    # Create outer cell filled with the lattice
    box = openmc.model.RectangularPrism(
        width=length, height=length, boundary_type='vacuum'
    )
    geometry = openmc.Geometry([openmc.Cell(fill=lat_outer, region=-box)])

    # Isotropic source uniformly distributed in a box
    source = openmc.IndependentSource()
    source.space = openmc.stats.Box(ll_outer, ur_outer)
    source.angle = openmc.stats.Isotropic()
    source.energy = openmc.stats.delta_function(1.0e6)

    # Settings with fixed source run and uniform source
    settings = openmc.Settings()
    settings.batches = 10
    settings.particles = 100_000
    settings.run_mode = "fixed source"
    settings.source = source

    return openmc.Model(geometry=geometry, settings=settings)
