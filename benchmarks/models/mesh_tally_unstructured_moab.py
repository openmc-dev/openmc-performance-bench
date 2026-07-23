"""Track-length flux tally on an unstructured MOAB mesh."""

import openmc

from ._mesh_tally_unstructured import build_model as _build_model


BENCHMARK_NAME = "MeshTallyUnstructuredMOAB"


def build_model() -> openmc.Model:
    return _build_model(
        "cube-mesh.h5m",
        library="moab",
        density=1.0e-10,
    )
