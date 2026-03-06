"""Simple tokamak DAGMC model loaded from XML."""

from __future__ import annotations
from pathlib import Path

import openmc

BENCHMARK_NAME = "SimpleTokamakDAGMC"

_XML_PATH = Path(__file__).parent / "simple_tokamak_dagmc.xml"


def build_model() -> openmc.Model:
    return openmc.Model.from_model_xml(_XML_PATH)
