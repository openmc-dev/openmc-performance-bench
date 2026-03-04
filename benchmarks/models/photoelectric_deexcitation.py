"""Photon transport OpenMC model stressing photoelectric effect with atomic
relaxation.
"""

import openmc

from . import _photoelectric

BENCHMARK_NAME = "PhotoelectricDeexcitation"


def build_model() -> openmc.Model:
    return _photoelectric.build_model(atomic_relaxation=True)
