"""Infinite-medium UO2 eigenvalue OpenMC model."""

from __future__ import annotations

import openmc

BENCHMARK_NAME = "InfiniteMediumEigenvalue"


def build_model() -> openmc.Model:
    fuel = openmc.Material(name="UO2 fuel")
    fuel.add_element("U", 1, enrichment=4.5)
    fuel.add_element("O", 2)
    fuel.set_density("g/cm3", 10.5)

    materials = openmc.Materials([fuel])

    boundary = openmc.Sphere(r=100.0, boundary_type="vacuum")
    cell = openmc.Cell(name="fuel cell", fill=fuel, region=-boundary)
    geometry = openmc.Geometry([cell])

    source = openmc.IndependentSource()
    source.space = openmc.stats.Point((0.0, 0.0, 0.0))
    source.angle = openmc.stats.Isotropic()
    source.energy = openmc.stats.Discrete([2.0e6], [1.0])

    settings = openmc.Settings()
    settings.batches = 20
    settings.inactive = 5
    settings.particles = 1000
    settings.run_mode = "eigenvalue"
    settings.source = source

    return openmc.Model(geometry=geometry, settings=settings)
