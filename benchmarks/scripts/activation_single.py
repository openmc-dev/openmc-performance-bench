from ._activation import ACTIVATION_RETURN_METRICS, run_activation

BENCHMARK_NAME = "ActivationSingle"
RETURN_METRICS = ACTIVATION_RETURN_METRICS
N_MATERIALS = 1


def run_benchmark(threads, mpi_procs):
    return run_activation(N_MATERIALS, threads, mpi_procs)
