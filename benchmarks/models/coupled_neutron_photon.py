"""OpenMC model with coupled neutron-photon transport."""

import openmc

BENCHMARK_NAME = "CoupledNeutronPhoton"


def build_model() -> openmc.Model:
    # Natural gadolinium
    gd = openmc.Material(name="gadolinium")
    gd.set_density("g/cm3", 7.90)
    gd.add_element("Gd", 1.0)

    # Large sphere with a single material
    sphere = openmc.Sphere(r=100, boundary_type="vacuum")
    geometry = openmc.Geometry([openmc.Cell(fill=gd, region=-sphere)])

    # Neutron source with discrete energies corresponding to strong (n,gamma)
    # resonances in Gd isotopes
    source = openmc.IndependentSource()
    source.space = openmc.stats.Point((0.0, 0.0, 0.0))
    source.angle = openmc.stats.Isotropic()
    source.particle = "neutron"
    source.energy = openmc.stats.Discrete(
        [2.568, 33.23, 16.77, 22.3, 222.0],
        [1.0,   1.0,   1.0,   1.0,  1.0]
    )

    # Settings with fixed source run and photon transport enabled
    settings = openmc.Settings()
    settings.batches = 10
    settings.particles = 100_000
    settings.run_mode = "fixed source"
    settings.source = source
    settings.photon_transport = True
    settings.electron_treatment = "led"
    settings.atomic_relaxation = False

    return openmc.Model(geometry=geometry, settings=settings)
