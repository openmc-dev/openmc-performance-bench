"""ASV benchmark suites for OpenMC."""

from __future__ import annotations

import math
import shutil
from typing import Dict, Optional, Tuple, TYPE_CHECKING

from .openmc_runner import OpenMCRunResult, OpenMCRunner

if TYPE_CHECKING:  # pragma: no cover - type checking only
    import openmc


_THREAD_OPTIONS: Tuple[int, ...] = (1, 2)


def _detect_mpi_runner() -> Optional[Tuple[str, ...]]:
    for candidate in ("mpirun", "mpiexec"):
        if shutil.which(candidate):
            return (candidate,)
    return None


_MPI_RUNNER = _detect_mpi_runner()
_MPI_OPTIONS: Tuple[Optional[int], ...] = (None, 2) if _MPI_RUNNER else (None,)



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


def _build_infinite_medium_model() -> "openmc.model.Model":
    import openmc

    fuel = openmc.Material(name="UO2 fuel")
    fuel.add_element("U", 1, enrichment=4.5)
    fuel.add_element("O", 2)
    fuel.set_density("g/cm3", 10.5)

    materials = openmc.Materials([fuel])

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

    return openmc.model.Model(materials=materials, geometry=geometry, settings=settings)


class InfiniteMediumEigenvalue:
    """Benchmark an infinite-medium eigenvalue problem."""

    params = (_THREAD_OPTIONS, _MPI_OPTIONS)
    param_names = ("threads", "mpi_procs")
    timeout = 600

    def __init__(self) -> None:
        self._runner: Optional[OpenMCRunner] = None
        self._model = None
        self._cache: Optional[Dict[Tuple[int, Optional[int]], OpenMCRunResult]] = None

    def setup_cache(self) -> Dict[Tuple[int, Optional[int]], OpenMCRunResult]:
        if self._cache is not None:
            return self._cache

        runner = self._ensure_runner()
        model = self._ensure_model()

        cache: Dict[Tuple[int, Optional[int]], OpenMCRunResult] = {}
        for threads in _THREAD_OPTIONS:
            for mpi_procs in _MPI_OPTIONS:
                result = self._run_model(runner, model, threads, mpi_procs)
                cache[(threads, mpi_procs)] = result

        self._cache = cache
        return cache

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

    def _ensure_model(self) -> "openmc.model.Model":
        if self._model is None:
            self._model = _build_infinite_medium_model()
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
