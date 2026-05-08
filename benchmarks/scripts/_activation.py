from copy import deepcopy
import os
from pathlib import Path
from random import uniform
import time

import numpy as np
import openmc
import openmc.deplete

ACTIVATION_RETURN_METRICS = (
    "operator_setup_seconds",
    "integration_seconds",
    "core_sec_per_mat_timestep",
)

_SCRIPT_DIR = Path(__file__).resolve().parent


def run_activation(n_materials, threads, mpi_procs):
    hour = 3600.0
    day = 24*hour
    source_rates = [2.32e10, 0.0, 2.87e10, 0.0, 1.90e10, 0.0, 1.36e10]
    source_times = [19440., 61680., 32940., 54840., 15720., 6360., 8940.]
    cooling_times_cumulative = [
        1*hour, 6*hour, 12*hour, 16*hour, 20*hour, 1*day, 2*day, 3*day, 4*day,
        5*day, 7*day, 9*day, 12*day, 15*day, 18*day, 21*day, 30*day, 60*day
    ]

    source_rates.extend([0.0]*len(cooling_times_cumulative))
    cooling_times = list(np.diff(cooling_times_cumulative, prepend=0.0))
    timesteps = source_times + cooling_times

    fluxes = []
    micros = []
    materials = []

    micro_xs = openmc.deplete.MicroXS.from_csv(_SCRIPT_DIR / 'micros.csv')

    for _ in range(n_materials):
        # Create material with randomly sampled data
        mat = openmc.Material()
        mat.depletable = True
        mat.volume = 1.0
        mat.set_density('g/cm3', 7.954)
        mat.add_element('B', 0.0035*(1 + uniform(-0.01, 0.01)))
        mat.add_element('C', 0.040*(1 + uniform(-0.01, 0.01)))
        mat.add_element('Si', 0.47*(1 + uniform(-0.01, 0.01)))
        mat.add_element('V', 0.160*(1 + uniform(-0.01, 0.01)))
        mat.add_element('Cr', 16.8*(1 + uniform(-0.01, 0.01)))
        mat.add_element('Mn', 1.14*(1 + uniform(-0.01, 0.01)))
        mat.add_element('Fe', 68.12*(1 + uniform(-0.01, 0.01)))
        mat.add_element('Co', 0.14*(1 + uniform(-0.01, 0.01)))
        mat.add_element('Ni', 10.7*(1 + uniform(-0.01, 0.01)))
        mat.add_element('Mo', 2.12*(1 + uniform(-0.01, 0.01)))
        mat.add_element('Cu', 0.09*(1 + uniform(-0.01, 0.01)))
        materials.append(mat)

        # Create a copy of `micro_xs` and randomly perturb the data array to
        # create a unique MicroXS for each material
        xs = deepcopy(micro_xs)
        xs.data *= (1 + uniform(-0.01, 0.01))
        micros.append(xs)

        # Random sample a flux value between 0.0 and 1.0 and append to `fluxes` list
        fluxes.append(uniform(0.0, 1.0))

    # Set up activation via IndependentOperator
    t0 = time.perf_counter()
    op = openmc.deplete.IndependentOperator(
        materials, fluxes, micros, normalization_mode='source-rate',
        chain_file=_SCRIPT_DIR / 'chain_endfb80_reduced.xml',
    )
    integrator = openmc.deplete.PredictorIntegrator(
        op, timesteps, source_rates=source_rates,
    )
    t1 = time.perf_counter()
    integrator.integrate(final_step=False)
    t2 = time.perf_counter()

    integration_time = t2 - t1
    cpu_count = os.cpu_count() or 1
    core_sec_per_mat_timestep = (
        integration_time * cpu_count / (n_materials * len(timesteps))
    )
    return {
        "operator_setup_seconds": t1 - t0,
        "integration_seconds": integration_time,
        "core_sec_per_mat_timestep": core_sec_per_mat_timestep,
    }
