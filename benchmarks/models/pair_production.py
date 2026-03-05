"""Photon transport OpenMC model stressing pair production."""

import openmc

import numpy as np
import openmc

BENCHMARK_NAME = "PairProduction"


def build_model() -> openmc.Model:
    lead = openmc.Material(name="lead")
    lead.set_density("g/cm3", 11.34)
    lead.add_element("Pb", 1.0)

    # Geometry is a single lead sphere. The radius is not so large that
    # secondary photons continue to scatter many times before escaping.
    sphere = openmc.Sphere(r=20, boundary_type="vacuum")
    geometry = openmc.Geometry([openmc.Cell(fill=lead, region=-sphere)])

    # Isotropic point source of 10 MeV photons at the origin. Pair production
    # dominates at very high energies
    source = openmc.IndependentSource()
    source.space = openmc.stats.Point((0.0, 0.0, 0.0))
    source.angle = openmc.stats.Isotropic()
    source.energy = openmc.stats.delta_function(1.0e9)
    source.particle = "photon"

    # Settings with fixed source run and uniform source
    settings = openmc.Settings()
    settings.batches = 10
    settings.particles = 100_000
    settings.run_mode = "fixed source"
    settings.source = source
    settings.photon_transport = True
    settings.electron_treatment = "led"
    settings.atomic_relaxation = False

    return openmc.Model(geometry=geometry, settings=settings)
