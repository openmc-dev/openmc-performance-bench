import time
import numpy as np
import openmc
import openmc.deplete

openmc.deplete.pool.USE_MULTIPROCESSING = True

# Set data
openmc.config['chain_file'] = 'chain_endfb80_reduced.xml'

def run_benchmark(threads, mpi_procs):
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
    n = 100

    micro_xs = openmc.deplete.MicroXS.from_csv('micros.csv')

    for i in range(n):
        # Create material with randomly sampled data
        mat = openmc.Material()
        mat.set_density('g/cm3', 7.954)
        mat.add_element('B', 0.0035)
        mat.add_element('C', 0.040)
        mat.add_element('Si', 0.47)
        mat.add_element('V', 0.160)
        mat.add_element('Cr', 16.8)
        mat.add_element('Mn', 1.14)
        mat.add_element('Fe', 68.12)
        mat.add_element('Co', 0.14)
        mat.add_element('Ni', 10.7)
        mat.add_element('Mo', 2.12)
        mat.add_element('Cu', 0.09)

        # TODO: Create a copy of `micro_xs` and randomly perturb the data array
        # to create a unique MicroXS for each material, then append to `micros`
        # list

        # TODO: Random sample a flux value between 0.0 and 1.0 and append to `fluxes` list


    # Set up activation via IndependentOperator
    op = openmc.deplete.IndependentOperator(
        materials, fluxes, micros, normalization_mode='source-rate',
    )
    integrator = openmc.deplete.PredictorIntegrator(
        op, timesteps, source_rates=source_rates,
    )
    start_time = time.perf_counter()
    integrator.integrate(final_step=False)
    end_time = time.perf_counter()
    integration_time = end_time - start_time
    core_sec_per_mat_timestep = integration_time*8 / (n * len(timesteps))
