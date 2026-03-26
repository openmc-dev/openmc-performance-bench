"""OpenMC model with depletiion-like reaction rate tallies."""

import openmc

from . import _many_nuclides

BENCHMARK_NAME = "DepletionTallies"


def build_model() -> openmc.Model:
    return _many_nuclides.build_model(add_tallies=True)
