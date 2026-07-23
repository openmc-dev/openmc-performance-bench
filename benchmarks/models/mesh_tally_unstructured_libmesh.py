"""Collision flux tally on an unstructured libMesh mesh."""

import openmc

from ._mesh_tally_unstructured import build_model as _build_model


BENCHMARK_NAME = "MeshTallyUnstructuredLibMesh"


def build_model() -> openmc.Model:
    return _build_model(
        "cube-mesh.e",
        library="libmesh",
        density=0.1,
        estimator="collision",
    )
