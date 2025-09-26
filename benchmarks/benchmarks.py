"""ASV benchmark suites for OpenMC."""

from __future__ import annotations

import logging
import math
import os
import shutil
from typing import Dict, Optional, Tuple

import openmc

from .openmc_runner import OpenMCRunResult, OpenMCRunner

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_THREAD_OPTIONS: Tuple[int, ...] = (1, 2, 4)


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
_MPI_OPTIONS: Tuple[Optional[int], ...] = (None, 2) if (_MPI_ENABLED and _MPI_RUNNER) else (None,)



def _param_key(threads: object, mpi_procs: object) -> Tuple[int, Optional[int]]:
    thread_val = int(threads) if isinstance(threads, str) else threads
    mpi_val: Optional[int]
    if mpi_procs in (None, 'None'):
        mpi_val = None
    else:
        mpi_val = int(mpi_procs) if isinstance(mpi_procs, str) else mpi_procs
    return int(thread_val), mpi_val


def _nan(value: Optional[float]) -> float:
    return value if value is not None else math.nan


def _build_infinite_medium_model() -> openmc.Model:

    fuel = openmc.Material(name="UO2 fuel")
    fuel.add_element("U", 1, enrichment=4.5)
    fuel.add_element("O", 2)
    fuel.set_density("g/cm3", 10.5)

    boundary = openmc.Sphere(r=100.0, boundary_type="vacuum")
    cell = openmc.Cell(name="fuel cell", fill=fuel, region=-boundary)
    geometry = openmc.Geometry([cell])

    source = openmc.IndependentSource()
    source.space = openmc.stats.Point((0.0, 0.0, 0.0))
    source.angle = openmc.stats.Isotropic()
    source.energy = openmc.stats.Discrete([2.0e6], [1.0])

    settings = openmc.Settings()
    settings.batches = 20
    settings.inactive = 5
    settings.particles = 1000
    settings.run_mode = "eigenvalue"
    settings.source = source

    return openmc.Model(geometry=geometry, settings=settings)


class _OpenMCModelBenchmark:
    """Common OpenMC benchmarking harness."""

    params = (_THREAD_OPTIONS, _MPI_OPTIONS)
    param_names = ("threads", "mpi_procs")
    timeout = 600

    thread_options: Tuple[int, ...] = _THREAD_OPTIONS
    mpi_options: Tuple[Optional[int], ...] = _MPI_OPTIONS

    def __init__(self) -> None:
        self._runner: Optional[OpenMCRunner] = None
        self._model = None
        self._cache: Optional[Dict[Tuple[int, Optional[int]], OpenMCRunResult]] = None

    def setup_cache(self, *_params: object) -> Dict[Tuple[int, Optional[int]], OpenMCRunResult]:
        if self._cache is None:
            runner = self._ensure_runner()
            model = self._ensure_model()
            cache: Dict[Tuple[int, Optional[int]], OpenMCRunResult] = {}
            for threads in self.thread_options:
                for mpi_procs in self.mpi_options:
                    logger.info(f"Running with threads={threads}, mpi_procs={mpi_procs}")
                    cache[threads, mpi_procs] = self._run_model(runner, model, threads, mpi_procs)
                    logger.info(f"OpenMC output:\n{cache[threads, mpi_procs].stdout}")

            self._cache = cache
        return self._cache

    def track_elapsed_wall(
        self,
        results: Dict[Tuple[int, Optional[int]], OpenMCRunResult],
        threads: int,
        mpi_procs: Optional[int],
    ) -> float:
        result = results[_param_key(threads, mpi_procs)]
        return _nan(result.time_usage.elapsed_seconds)

    def track_user_cpu(
        self,
        results: Dict[Tuple[int, Optional[int]], OpenMCRunResult],
        threads: int,
        mpi_procs: Optional[int],
    ) -> float:
        result = results[_param_key(threads, mpi_procs)]
        return _nan(result.time_usage.user_seconds)

    def track_system_cpu(
        self,
        results: Dict[Tuple[int, Optional[int]], OpenMCRunResult],
        threads: int,
        mpi_procs: Optional[int],
    ) -> float:
        result = results[_param_key(threads, mpi_procs)]
        return _nan(result.time_usage.system_seconds)

    def track_max_rss_kb(
        self,
        results: Dict[Tuple[int, Optional[int]], OpenMCRunResult],
        threads: int,
        mpi_procs: Optional[int],
    ) -> float:
        result = results[_param_key(threads, mpi_procs)]
        rss = result.time_usage.max_rss_kb
        return float(rss) if rss is not None else math.nan

    def track_cpu_percent(
        self,
        results: Dict[Tuple[int, Optional[int]], OpenMCRunResult],
        threads: int,
        mpi_procs: Optional[int],
    ) -> float:
        result = results[_param_key(threads, mpi_procs)]
        return _nan(result.time_usage.cpu_percent)

    def track_total_time_elapsed(
        self,
        results: Dict[Tuple[int, Optional[int]], OpenMCRunResult],
        threads: int,
        mpi_procs: Optional[int],
    ) -> float:
        result = results[_param_key(threads, mpi_procs)]
        stats = result.timing_stats
        return _nan(stats.total_elapsed if stats else None)

    def track_initialization_time(
        self,
        results: Dict[Tuple[int, Optional[int]], OpenMCRunResult],
        threads: int,
        mpi_procs: Optional[int],
    ) -> float:
        result = results[_param_key(threads, mpi_procs)]
        stats = result.timing_stats
        return _nan(stats.initialization if stats else None)

    def track_transport_time(
        self,
        results: Dict[Tuple[int, Optional[int]], OpenMCRunResult],
        threads: int,
        mpi_procs: Optional[int],
    ) -> float:
        result = results[_param_key(threads, mpi_procs)]
        stats = result.timing_stats
        return _nan(stats.transport if stats else None)

    def track_calc_rate_inactive(
        self,
        results: Dict[Tuple[int, Optional[int]], OpenMCRunResult],
        threads: int,
        mpi_procs: Optional[int],
    ) -> float:
        result = results[_param_key(threads, mpi_procs)]
        stats = result.timing_stats
        return _nan(stats.calc_rate_inactive if stats else None)

    def track_calc_rate_active(
        self,
        results: Dict[Tuple[int, Optional[int]], OpenMCRunResult],
        threads: int,
        mpi_procs: Optional[int],
    ) -> float:
        result = results[_param_key(threads, mpi_procs)]
        stats = result.timing_stats
        return _nan(stats.calc_rate_active if stats else None)

    def _ensure_runner(self) -> OpenMCRunner:
        if self._runner is None:
            self._runner = OpenMCRunner(default_mpi_runner=_MPI_RUNNER)
        return self._runner

    def _ensure_model(self) -> openmc.Model:
        if self._model is None:
            self._model = self._build_model()
        return self._model

    def _run_model(
        self,
        runner: OpenMCRunner,
        model: "openmc.model.Model",
        threads: int,
        mpi_procs: Optional[int],
    ) -> OpenMCRunResult:
        result = runner.run_model(
            model,
            threads=threads,
            mpi_procs=mpi_procs,
            keep_workdir=True,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"OpenMC exited with {result.returncode}: {result.stderr.strip()}"
            )
        return result

    def _build_model(self) -> openmc.Model:
        raise NotImplementedError


class InfiniteMediumEigenvalue(_OpenMCModelBenchmark):
    """Benchmark an infinite-medium eigenvalue problem."""

    def _build_model(self) -> openmc.Model:
        return _build_infinite_medium_model()
