"""Public entry point for asv to discover all OpenMC benchmarks."""

from __future__ import annotations

from .models import MODEL_REGISTRY
from .suites import make_benchmark

__all__ = []

for _module_name, (benchmark_name, builder, thread_opts, mpi_opts) in sorted(
    MODEL_REGISTRY.items(), key=lambda item: item[1][0]
):
    cls = make_benchmark(
        benchmark_name,
        builder,
        thread_options=thread_opts,
        mpi_options=mpi_opts,
    )
    globals()[benchmark_name] = cls
    __all__.append(benchmark_name)
