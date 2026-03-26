"""OpenMC model stressing coherent elastic scattering."""

import openmc

from . import _thermal_scattering

BENCHMARK_NAME = "CoherentElastic"


def build_model() -> openmc.Model:
    graphite = openmc.Material(name="Graphite")
    graphite.set_density("g/cm3", 2.26)
    graphite.add_element("C", 1.0)
    graphite.add_s_alpha_beta("c_Graphite")

    return _thermal_scattering.build_model(graphite)
