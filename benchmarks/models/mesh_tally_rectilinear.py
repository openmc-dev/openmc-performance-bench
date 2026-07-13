"""Flux tally on a fine rectilinear mesh."""

import numpy as np
import openmc


BENCHMARK_NAME = "MeshTallyRectilinear"


def build_model() -> openmc.Model:
    material = openmc.Material(name="Low-density H")
    material.add_nuclide("H1", 1.0)
    material.set_density("g/cm3", 1.0e-10)

    sphere = openmc.Sphere(r=50.0, boundary_type="vacuum")
    geometry = openmc.Geometry([openmc.Cell(fill=material, region=-sphere)])

    source = openmc.IndependentSource(
        space=openmc.stats.Box((-25.0, -25.0, -25.0), (25.0, 25.0, 25.0)),
        energy=openmc.stats.delta_function(1.0e6),
    )

    settings = openmc.Settings()
    settings.batches = 10
    settings.particles = 100_000
    settings.run_mode = "fixed source"
    settings.source = source

    grid = np.linspace(-20.0, 20.0, 51)
    mesh = openmc.RectilinearMesh()
    mesh.x_grid = grid
    mesh.y_grid = grid
    mesh.z_grid = grid

    tally = openmc.Tally(name="mesh flux")
    tally.filters = [openmc.MeshFilter(mesh)]
    tally.scores = ["flux"]

    return openmc.Model(
        geometry=geometry,
        settings=settings,
        tallies=openmc.Tallies([tally]),
    )
