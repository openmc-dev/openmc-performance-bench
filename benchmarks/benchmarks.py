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

    @classmethod
    def setup_cache(cls, *_params: object) -> None:
        # asv may pass parameter values to setup_cache; ignore them and
        # lazily create shared resources if missing.
        if not hasattr(cls, 'runner'):
            cls.runner = OpenMCRunner(default_mpi_runner=_MPI_RUNNER)
        if not hasattr(cls, 'model'):
            cls.model = _build_infinite_medium_model()
        if not hasattr(cls, '_result_cache'):
            cls._result_cache: Dict[Tuple[int, Optional[int]], OpenMCRunResult] = {}

    def setup(self, threads: int, mpi_procs: Optional[int]) -> None:
        cls = type(self)
        if not hasattr(cls, 'runner') or not hasattr(cls, 'model'):
            cls.setup_cache(threads, mpi_procs)
        self.runner = cls.runner
        self.model = cls.model
        self._result_cache = cls._result_cache

    def time_eigenvalue(self, threads: int, mpi_procs: Optional[int]) -> None:
        self._run(threads, mpi_procs, use_cache=False)

    def track_elapsed_wall(self, threads: int, mpi_procs: Optional[int]) -> float:
        result = self._run(threads, mpi_procs, use_cache=False)
        return _nan(result.time_usage.elapsed_seconds)

    def track_user_cpu(self, threads: int, mpi_procs: Optional[int]) -> float:
        result = self._run(threads, mpi_procs, use_cache=True)
        return _nan(result.time_usage.user_seconds)

    def track_system_cpu(self, threads: int, mpi_procs: Optional[int]) -> float:
        result = self._run(threads, mpi_procs, use_cache=True)
        return _nan(result.time_usage.system_seconds)

    def track_max_rss_kb(self, threads: int, mpi_procs: Optional[int]) -> float:
        result = self._run(threads, mpi_procs, use_cache=True)
        rss = result.time_usage.max_rss_kb
        return float(rss) if rss is not None else math.nan

    def track_cpu_percent(self, threads: int, mpi_procs: Optional[int]) -> float:
        result = self._run(threads, mpi_procs, use_cache=True)
        return _nan(result.time_usage.cpu_percent)

    def track_total_time_elapsed(self, threads: int, mpi_procs: Optional[int]) -> float:
        result = self._run(threads, mpi_procs, use_cache=True)
        stats = result.timing_stats
        return _nan(stats.total_elapsed if stats else None)

    def track_initialization_time(self, threads: int, mpi_procs: Optional[int]) -> float:
        result = self._run(threads, mpi_procs, use_cache=True)
        stats = result.timing_stats
        return _nan(stats.initialization if stats else None)

    def track_transport_time(self, threads: int, mpi_procs: Optional[int]) -> float:
        result = self._run(threads, mpi_procs, use_cache=True)
        stats = result.timing_stats
        return _nan(stats.transport if stats else None)

    def track_calc_rate_inactive(self, threads: int, mpi_procs: Optional[int]) -> float:
        result = self._run(threads, mpi_procs, use_cache=True)
        stats = result.timing_stats
        return _nan(stats.calc_rate_inactive if stats else None)

    def track_calc_rate_active(self, threads: int, mpi_procs: Optional[int]) -> float:
        result = self._run(threads, mpi_procs, use_cache=True)
        stats = result.timing_stats
        return _nan(stats.calc_rate_active if stats else None)

    def _run(
        self,
        threads: int,
        mpi_procs: Optional[int],
        *,
        use_cache: bool,
    ) -> OpenMCRunResult:
        key = (threads, mpi_procs)
        cache = self._result_cache
        if use_cache and key in cache:
            return cache[key]

        result = self.runner.run_model(
            self.model,
            threads=threads,
            mpi_procs=mpi_procs,
            keep_workdir=True,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"OpenMC exited with {result.returncode}: {result.stderr.strip()}"
            )

        cache[key] = result
        return result
