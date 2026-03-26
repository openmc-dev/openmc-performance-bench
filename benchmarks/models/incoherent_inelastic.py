"""OpenMC model stressing incoherent inelastic scattering."""

import openmc

from . import _thermal_scattering

BENCHMARK_NAME = "IncoherentInelastic"


def build_model() -> openmc.Model:
    water = openmc.Material(name="H2O")
    water.set_density("g/cm3", 1.0)
    water.add_element("H", 2.0)
    water.add_element("O", 1.0)
    water.add_s_alpha_beta("c_H_in_H2O")

    return _thermal_scattering.build_model(water)
