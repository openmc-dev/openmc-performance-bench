"""Photon transport OpenMC model stressing thick-target bremsstrahlung."""

import openmc

BENCHMARK_NAME = "ThickTargetBremsstrahlung"


def build_model() -> openmc.Model:
    # High-Z, high-density target
    tungsten = openmc.Material(name="tungsten")
    tungsten.set_density("g/cm3", 19.3)
    tungsten.add_element("W", 1.0)

    # Geometry is a single large tungsten sphere
    sphere = openmc.Sphere(r=100, boundary_type="vacuum")
    geometry = openmc.Geometry([openmc.Cell(fill=tungsten, region=-sphere)])

    # Isotropic point source of 100 MeV photons at the origin
    source = openmc.IndependentSource()
    source.space = openmc.stats.Point((0.0, 0.0, 0.0))
    source.angle = openmc.stats.Isotropic()
    source.energy = openmc.stats.delta_function(100.0e6)
    source.particle = "photon"

    # Settings with fixed source run and uniform source
    settings = openmc.Settings()
    settings.batches = 10
    settings.particles = 10_000
    settings.run_mode = "fixed source"
    settings.source = source
    settings.photon_transport = True
    settings.electron_treatment = "ttb"
    settings.atomic_relaxation = False

    return openmc.Model(geometry=geometry, settings=settings)
