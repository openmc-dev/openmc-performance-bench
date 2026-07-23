"""Shared model construction for unstructured mesh tally benchmarks."""

from pathlib import Path

import openmc


_MODEL_DIR = Path(__file__).resolve().parent


def build_model(
    mesh_filename: str,
    *,
    library: str,
    density: float,
    estimator: str | None = None,
) -> openmc.Model:
    """Build the common fixed-source model with an unstructured mesh tally."""
    material = openmc.Material(name="Low-density H")
    material.add_nuclide("H1", 1.0)
    material.set_density("g/cm3", density)

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

    mesh_path = _MODEL_DIR / mesh_filename
    mesh = openmc.UnstructuredMesh(mesh_path, library=library)

    tally = openmc.Tally(name="mesh flux")
    tally.filters = [openmc.MeshFilter(mesh)]
    tally.scores = ["flux"]
    if estimator is not None:
        tally.estimator = estimator

    return openmc.Model(
        geometry=geometry,
        settings=settings,
        tallies=openmc.Tallies([tally]),
    )
