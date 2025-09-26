"""Shared benchmark harness for running OpenMC models under asv."""

from __future__ import annotations

from typing import Callable, Dict, Optional, Tuple, Type

import openmc

from ..openmc_runner import OpenMCRunResult, OpenMCRunner
from ..config import _MPI_OPTIONS, _MPI_RUNNER, _THREAD_OPTIONS, _param_key, _nan


class _OpenMCModelBenchmark:
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
                    cache[(threads, mpi_procs)] = self._run_model(runner, model, threads, mpi_procs)
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
        return float(rss) if rss is not None else _nan(None)

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

    def _ensure_model(self):
        if self._model is None:
            self._model = self._build_model()
        return self._model

    def _run_model(
        self,
        runner: OpenMCRunner,
        model,
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

    def _build_model(self):  # pragma: no cover - abstract hook
        raise NotImplementedError


def make_benchmark(
    name: str,
    model_builder: Callable[[], openmc.Model],
    *,
    thread_options: Tuple[int, ...] | None = None,
    mpi_options: Tuple[Optional[int], ...] | None = None,
) -> Type[_OpenMCModelBenchmark]:
    threads = thread_options or _THREAD_OPTIONS
    mpi = mpi_options or _MPI_OPTIONS
    namespace = {
        "__doc__": f"Benchmark for {name} model.",
        "thread_options": threads,
        "mpi_options": mpi,
        "params": (threads, mpi),
        "_build_model": staticmethod(model_builder),
    }
    return type(name, (_OpenMCModelBenchmark,), namespace)
