"""Rectangular mesh source OpenMC model."""

import openmc

from . import _mesh_source

BENCHMARK_NAME = "RegularMeshSource"


def build_model() -> openmc.Model:
    return _mesh_source.build_model('regular')
