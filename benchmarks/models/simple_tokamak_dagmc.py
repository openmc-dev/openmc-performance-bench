"""Simple tokamak DAGMC model loaded from XML."""

from __future__ import annotations
from pathlib import Path

import openmc

BENCHMARK_NAME = "SimpleTokamakDAGMC"

_XML_PATH = Path(__file__).parent / "simple_tokamak_dagmc.xml"
_H5M_PATH = Path(__file__).parent / "octomak.h5m"


def build_model() -> openmc.Model:
    model = openmc.Model.from_model_xml(_XML_PATH)
    # Patch the DAGMC filename to an absolute path so OpenMC can find
    # it regardless of what temporary working directory ASV runs in
    for univ in model.geometry.get_all_universes().values():
        if isinstance(univ, openmc.DAGMCUniverse):
            univ.filename = str(_H5M_PATH)
    return model
