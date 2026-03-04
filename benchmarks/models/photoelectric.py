"""Photon transport OpenMC model stressing photoelectric effect."""

import openmc

from . import _photoelectric

BENCHMARK_NAME = "Photoelectric"


def build_model() -> openmc.Model:
    return _photoelectric.build_model(atomic_relaxation=False)
