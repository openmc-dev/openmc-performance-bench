"""Simple tokamak CSG model loaded from XML."""

from __future__ import annotations
from pathlib import Path

import openmc

BENCHMARK_NAME = "SimpleTokamakCSG"

_XML_PATH = Path(__file__).parent / "simple_tokamak_csg.xml"


def build_model() -> openmc.Model:
    return openmc.Model.from_model_xml(_XML_PATH)
