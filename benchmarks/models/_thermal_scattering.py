"""Helper function for building a fixed-source neutron transport OpenMC model
to stress thermal scattering.
"""

import openmc


def build_model(material : openmc.Material) -> openmc.Model:
    # Large sphere with a single material
    sphere = openmc.Sphere(r=100, boundary_type="vacuum")
    geometry = openmc.Geometry([openmc.Cell(fill=material, region=-sphere)])

    # Isotropic point source of 1 eV neutrons at the origin
    source = openmc.IndependentSource()
    source.space = openmc.stats.Point((0.0, 0.0, 0.0))
    source.angle = openmc.stats.Isotropic()
    source.energy = openmc.stats.delta_function(1.0)
    source.particle = "neutron"

    # Settings with fixed source run and uniform source
    settings = openmc.Settings()
    settings.batches = 10
    settings.particles = 10_000
    settings.run_mode = "fixed source"
    settings.source = source

    return openmc.Model(geometry=geometry, settings=settings)
