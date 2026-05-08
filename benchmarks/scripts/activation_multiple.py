from ._activation import ACTIVATION_RETURN_METRICS, run_activation

BENCHMARK_NAME = "ActivationMultipleMat"
RETURN_METRICS = ACTIVATION_RETURN_METRICS
N_MATERIALS = 500


def run_benchmark(threads, mpi_procs):
    n_pulses = 5
    n_decay = 10
    source_rates = [1e10, 0.0] * (n_pulses - 1) + [1e10] + [0.0] * n_decay
    timesteps = [3600.] * len(source_rates)
    return run_activation(timesteps, source_rates, N_MATERIALS, threads, mpi_procs)
