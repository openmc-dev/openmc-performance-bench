"""Shared configuration and helpers for OpenMC benchmarks."""

from __future__ import annotations

import math
import os
import shutil
from typing import Optional, Tuple

from .openmc_runner import OpenMCRunner


def _detect_mpi_runner() -> Optional[Tuple[str, ...]]:
    for candidate in ("mpirun", "mpiexec"):
        if shutil.which(candidate):
            return (candidate,)
    return None


_MPI_RUNNER = _detect_mpi_runner()


def _detect_mpi_enabled() -> bool:
    runner = OpenMCRunner(default_mpi_runner=_MPI_RUNNER)
    try:
        build_info = runner._get_build_info(runner.openmc_exec, os.environ)
    except Exception:
        return True
    return runner._build_supports_mpi(build_info)


_MPI_ENABLED = _detect_mpi_enabled()

# Explicit list of (threads, MPI procs) configurations to benchmark
_CONFIGS: Tuple[Tuple[int, Optional[int]], ...] = (
    (1, None),
    (12, None),
    (48, None),
)
if _MPI_ENABLED and _MPI_RUNNER:
    _CONFIGS += (
        (1, 48),
        (4, 12),
        (12, 4),
    )


def _param_key(threads: object, mpi_procs: object) -> Tuple[int, Optional[int]]:
    thread_val = int(threads) if isinstance(threads, str) else threads
    if mpi_procs in (None, "None"):
        mpi_val: Optional[int] = None
    else:
        mpi_val = int(mpi_procs) if isinstance(mpi_procs, str) else mpi_procs
    return int(thread_val), mpi_val


def _nan(value: Optional[float]) -> float:
    return value if value is not None else math.nan


__all__ = [
    "_CONFIGS",
    "_MPI_RUNNER",
    "_param_key",
    "_nan",
]
