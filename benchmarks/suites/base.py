"""Shared benchmark harness for running OpenMC models under asv."""

from __future__ import annotations

import itertools
import os
from types import FunctionType
from typing import Callable, Dict, Optional, Tuple, Type

import openmc

from ..openmc_runner import OpenMCRunResult, OpenMCRunner, _tty_write, _run_subprocess_live
from ..config import _MPI_OPTIONS, _MPI_RUNNER, _THREAD_OPTIONS, _param_key, _nan


def _make_custom_track(metric_name: str) -> Callable:
    """Create a ``track_*`` method that reads a pre-computed custom metric."""

    def track(self, results, threads, mpi_procs):
        result = results[_param_key(threads, mpi_procs)]
        return _nan(result.custom_metrics.get(metric_name))

    track.__name__ = f"track_{metric_name}"
    track.__qualname__ = f"_BaseBenchmark.track_{metric_name}"
    return track


class _BaseBenchmark:
    """Common base for all benchmarks with ``time -v`` metrics."""

    params = (_THREAD_OPTIONS, _MPI_OPTIONS)
    param_names = ("threads", "mpi_procs")
    timeout = 600

    thread_options: Tuple[int, ...] = _THREAD_OPTIONS
    mpi_options: Tuple[Optional[int], ...] = _MPI_OPTIONS

    _custom_metrics: Dict[str, Callable] = {}

    def _compute_custom_metrics(self, result: OpenMCRunResult) -> None:
        for name, func in self._custom_metrics.items():
            result.custom_metrics[name] = func(result)

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


class _OpenMCModelBenchmark(_BaseBenchmark):
    """Benchmark that builds an OpenMC model and runs the ``openmc`` executable."""

    def __init__(self) -> None:
        self._runner: Optional[OpenMCRunner] = None
        self._model = None
        self._cache: Optional[Dict[Tuple[int, Optional[int]], OpenMCRunResult]] = None

    def setup_cache(self, *_params: object) -> Dict[Tuple[int, Optional[int]], OpenMCRunResult]:
        _tty_write(f"\n{'=' * 60}\n")
        _tty_write(f"  Benchmark: {type(self).__name__}\n")
        _tty_write(f"{'=' * 60}\n")
        if self._cache is None:
            runner = self._ensure_runner()
            model = self._ensure_model()
            cache: Dict[Tuple[int, Optional[int]], OpenMCRunResult] = {}
            for threads in self.thread_options:
                for mpi_procs in self.mpi_options:
                    _tty_write(f"  Running: threads={threads}, mpi_procs={mpi_procs}\n")
                    result = self._run_model(runner, model, threads, mpi_procs)
                    self._compute_custom_metrics(result)
                    cache[(threads, mpi_procs)] = result
            self._cache = cache
        return self._cache

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
            live_output=bool(os.environ.get("ASV_LIVE_OUTPUT")),
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"OpenMC exited with {result.returncode}: {result.stderr.strip()}"
            )
        return result

    def _build_model(self):  # pragma: no cover - abstract hook
        raise NotImplementedError


# The setup_cache method needs to be unique for each subclass (asv determines
# based on its line number), but the auto-generation of the benchmark classes
# means that there is only a single setup_cache definition. We therefore create
# a clone of the method for each class with a unique line number.
_lineno_offset = itertools.count()
def _clone_setup_cache(class_name, source_class):
    original = source_class.setup_cache
    code = original.__code__.replace(
        co_firstlineno=original.__code__.co_firstlineno + next(_lineno_offset) + 1
    )
    new = FunctionType(code, original.__globals__, name=original.__name__,
                       argdefs=original.__defaults__, closure=original.__closure__)
    new.__qualname__ = f"{class_name}.setup_cache"
    new.__doc__ = original.__doc__
    return new


def make_benchmark(
    name: str,
    model_builder: Callable[[], openmc.Model],
    *,
    thread_options: Tuple[int, ...] | None = None,
    mpi_options: Tuple[Optional[int], ...] | None = None,
    custom_metrics: Dict[str, Callable] | None = None,
) -> Type[_OpenMCModelBenchmark]:
    threads = thread_options or _THREAD_OPTIONS
    mpi = mpi_options or _MPI_OPTIONS
    namespace: Dict[str, object] = {
        "__doc__": f"Benchmark for {name} model.",
        "thread_options": threads,
        "mpi_options": mpi,
        "params": (threads, mpi),
        "_build_model": staticmethod(model_builder),
        "_custom_metrics": custom_metrics or {},
    }
    for metric_name in (custom_metrics or {}):
        namespace[f"track_{metric_name}"] = _make_custom_track(metric_name)
    cls = type(name, (_OpenMCModelBenchmark,), namespace)
    cls.setup_cache = _clone_setup_cache(name, _OpenMCModelBenchmark)
    return cls


# ---------------------------------------------------------------------------
# Python script benchmarks
# ---------------------------------------------------------------------------

_PYTHON_DEFAULT_THREADS: Tuple[int, ...] = (1,)
_PYTHON_DEFAULT_MPI: Tuple[Optional[int], ...] = (None,)


class _PythonBenchmark(_BaseBenchmark):
    """Benchmark that runs arbitrary Python code as a subprocess."""

    params = (_PYTHON_DEFAULT_THREADS, _PYTHON_DEFAULT_MPI)

    thread_options: Tuple[int, ...] = _PYTHON_DEFAULT_THREADS
    mpi_options: Tuple[Optional[int], ...] = _PYTHON_DEFAULT_MPI

    _module_path: str = ""  # fully qualified module name, set by factory

    def __init__(self) -> None:
        self._cache: Optional[Dict[Tuple[int, Optional[int]], OpenMCRunResult]] = None

    def setup_cache(self, *_params: object) -> Dict[Tuple[int, Optional[int]], OpenMCRunResult]:
        _tty_write(f"\n{'=' * 60}\n")
        _tty_write(f"  Benchmark: {type(self).__name__}\n")
        _tty_write(f"{'=' * 60}\n")
        if self._cache is None:
            cache: Dict[Tuple[int, Optional[int]], OpenMCRunResult] = {}
            for threads in self.thread_options:
                for mpi_procs in self.mpi_options:
                    _tty_write(f"  Running: threads={threads}, mpi_procs={mpi_procs}\n")
                    cache[(threads, mpi_procs)] = self._run_script(threads, mpi_procs)
            self._cache = cache
        return self._cache

    def _run_script(self, threads: int, mpi_procs: Optional[int]) -> OpenMCRunResult:
        import subprocess
        import sys
        import tempfile
        from pathlib import Path

        workdir = Path(tempfile.mkdtemp(prefix="openmc-pybench-"))
        try:
            script_path = workdir / "run_benchmark.py"
            script_path.write_text(
                f"import importlib\n"
                f"mod = importlib.import_module({self._module_path!r})\n"
                f"mod.run_benchmark(threads={threads!r}, mpi_procs={mpi_procs!r})\n"
            )

            env = OpenMCRunner._build_environment(
                os.environ, threads=threads, extra_env=None,
            )
            # Ensure the project root (parent of the benchmarks package) is
            # on PYTHONPATH so the subprocess can resolve top-level imports
            # like ``benchmarks.scripts.foo``.
            project_root = str(Path(__file__).resolve().parent.parent.parent)
            paths = list(sys.path)
            if project_root not in paths:
                paths.insert(0, project_root)
            env["PYTHONPATH"] = os.pathsep.join(paths)

            cmd: list[str] = []
            if mpi_procs is not None and mpi_procs > 1 and _MPI_RUNNER:
                cmd.extend(_MPI_RUNNER)
                cmd.extend(["-np", str(mpi_procs)])
            cmd.extend([sys.executable, str(script_path)])

            time_output = workdir / "time-usage.txt"
            full_cmd = ["/usr/bin/time", "-v", "-o", str(time_output), *cmd]

            if os.environ.get("ASV_LIVE_OUTPUT"):
                returncode, stdout, stderr = _run_subprocess_live(
                    full_cmd, cwd=None, env=env,
                )
            else:
                completed = subprocess.run(
                    full_cmd, capture_output=True, text=True, env=env, check=False,
                )
                returncode, stdout, stderr = (
                    completed.returncode, completed.stdout, completed.stderr,
                )

            time_usage = OpenMCRunner._parse_time_output(time_output)

            if returncode != 0:
                raise RuntimeError(
                    f"Python benchmark exited with {returncode}: "
                    f"{stderr.strip()}"
                )

            result = OpenMCRunResult(
                returncode=returncode,
                stdout=stdout,
                stderr=stderr,
                command=full_cmd,
                workdir=workdir,
                threads=threads,
                mpi_procs=mpi_procs,
                time_usage=time_usage,
            )
            self._compute_custom_metrics(result)
            return result
        finally:
            import shutil
            shutil.rmtree(workdir, ignore_errors=True)


def make_python_benchmark(
    name: str,
    module_path: str,
    *,
    thread_options: Tuple[int, ...] | None = None,
    mpi_options: Tuple[Optional[int], ...] | None = None,
    custom_metrics: Dict[str, Callable] | None = None,
) -> Type[_PythonBenchmark]:
    threads = thread_options or _PYTHON_DEFAULT_THREADS
    mpi = mpi_options or _PYTHON_DEFAULT_MPI
    namespace: Dict[str, object] = {
        "__doc__": f"Python benchmark for {name}.",
        "thread_options": threads,
        "mpi_options": mpi,
        "params": (threads, mpi),
        "_module_path": module_path,
        "_custom_metrics": custom_metrics or {},
    }
    for metric_name in (custom_metrics or {}):
        namespace[f"track_{metric_name}"] = _make_custom_track(metric_name)
    cls = type(name, (_PythonBenchmark,), namespace)
    cls.setup_cache = _clone_setup_cache(name, _PythonBenchmark)
    return cls
