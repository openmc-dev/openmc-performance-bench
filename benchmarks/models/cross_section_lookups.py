"""Repeated slabs with many nuclides"""

import openmc

from . import _many_nuclides

BENCHMARK_NAME = "CrossSectionLookups"


def build_model() -> openmc.Model:
    return _many_nuclides.build_model(add_tallies=False)
