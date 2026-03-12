"""Random ray weight window generation benchmark for the Jetson 2D model.

Converts the Jetson 2D model to multigroup (using a pre-existing mgxs.h5),
then runs random ray with a FW-CADIS weight window generator.
"""

from __future__ import annotations

from pathlib import Path

import openmc
import openmc.mgxs
import openmc.stats

from ._jetson2d import RO, build_base_model, _chdir

BENCHMARK_NAME = "Jetson2dRandomRay"

_MODELS_DIR = Path(__file__).parent


def build_model() -> openmc.Model:
    model, mesh, plasma_cell = build_base_model()

    group_edges = openmc.mgxs.GROUP_STRUCTURES["CASMO-4"]

    # Convert to multigroup using the pre-existing mgxs.h5
    with _chdir(_MODELS_DIR):
        model.convert_to_multigroup(
            method="stochastic_slab",
            nparticles=10000,
            groups=openmc.mgxs.EnergyGroups(group_edges),
            overwrite_mgxs_library=False,
            correction=None,
        )

    # Convert to random ray mode
    model.convert_to_random_ray()

    # Random ray settings
    model.settings.random_ray["source_region_meshes"] = [
        (mesh, [model.geometry.root_universe])
    ]
    model.settings.particles = 500
    model.settings.batches = 100
    model.settings.inactive = 50
    model.settings.random_ray["distance_inactive"] = 4000
    model.settings.random_ray["distance_active"] = 20000
    model.settings.random_ray["ray_source"] = openmc.IndependentSource(
        space=openmc.stats.Box(
            lower_left=[-RO, -RO, -RO],
            upper_right=[RO, RO, RO],
            only_fissionable=False,
        )
    )
    model.settings.random_ray["source_shape"] = "flat"
    model.settings.random_ray["sample_method"] = "halton"
    model.settings.random_ray["volume_estimator"] = "hybrid"

    # FW-CADIS weight window generator
    wwg = openmc.WeightWindowGenerator(
        method="fw_cadis",
        mesh=mesh,
        max_realizations=model.settings.batches,
    )
    model.settings.weight_window_generators = wwg

    return model
