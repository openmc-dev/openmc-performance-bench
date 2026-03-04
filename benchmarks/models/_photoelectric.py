"""Helper function for building a fixed-source photon transport OpenMC model in
a regime where the photoelectric effect dominates.
"""

from __future__ import annotations

import numpy as np
import openmc


def build_model(atomic_relaxation : bool) -> openmc.Model:
    # The photoelectric effect dominates at 100 keV in lead
    pb = openmc.Material(name="lead")
    pb.set_density("g/cm3", 11.34)
    pb.add_element("Pb", 1.0)

    # Geometry is a single large lead sphere
    sphere = openmc.Sphere(r=100, boundary_type="vacuum")
    geometry = openmc.Geometry([openmc.Cell(fill=pb, region=-sphere)])

    # Isotropic point source of 100 keV photons at the origin
    source = openmc.IndependentSource()
    source.space = openmc.stats.Point((0.0, 0.0, 0.0))
    source.angle = openmc.stats.Isotropic()
    source.energy = openmc.stats.delta_function(100.0e3)
    source.particle = "photon"

    # Settings with fixed source run and uniform source
    settings = openmc.Settings()
    settings.batches = 10
    settings.particles = 100_000
    settings.run_mode = "fixed source"
    settings.source = source
    settings.photon_transport = True
    settings.electron_treatment = "led"
    settings.atomic_relaxation = atomic_relaxation

    return openmc.Model(geometry=geometry, settings=settings)
