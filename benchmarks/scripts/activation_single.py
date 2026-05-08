from ._activation import ACTIVATION_RETURN_METRICS, run_activation

BENCHMARK_NAME = "ActivationSingleMat"
RETURN_METRICS = ACTIVATION_RETURN_METRICS
N_MATERIALS = 1


def run_benchmark(threads, mpi_procs):
    n_pulses = 100
    source_rates = [1e10, 0.0] * n_pulses
    timesteps = [3600.] * len(source_rates)
    return run_activation(timesteps, source_rates, N_MATERIALS, threads, mpi_procs)
