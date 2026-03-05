"""Photon transport OpenMC model stressing Compton scattering."""

import openmc

import numpy as np
import openmc

BENCHMARK_NAME = "Compton"


def build_model() -> openmc.Model:
    # Compton scattering dominates for 1 MeV photons in iron. Doppler
    # broadening is more expensive for higher Z elements
    iron = openmc.Material(name="iron")
    iron.set_density("g/cm3", 7.874)
    iron.add_element("Fe", 1.0)

    # Geometry is a single large sphere
    sphere = openmc.Sphere(r=100, boundary_type="vacuum")
    geometry = openmc.Geometry([openmc.Cell(fill=iron, region=-sphere)])

    # Isotropic point source of 1 MeV photons at the origin
    source = openmc.IndependentSource()
    source.space = openmc.stats.Point((0.0, 0.0, 0.0))
    source.angle = openmc.stats.Isotropic()
    source.energy = openmc.stats.delta_function(1.0e6)
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
