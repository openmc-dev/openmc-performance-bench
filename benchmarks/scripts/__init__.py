"""Auto-discover Python script benchmarks."""

from __future__ import annotations

import importlib
import pkgutil
from typing import Callable, Dict, Optional, Tuple

CustomMetrics = Optional[Dict[str, Callable]]
ScriptSpec = Tuple[str, str, Optional[Tuple[int, ...]], Optional[Tuple[Optional[int], ...]], CustomMetrics]

# Mapping of module name -> ScriptSpec
SCRIPT_REGISTRY: Dict[str, ScriptSpec] = {}


def _default_benchmark_name(module_name: str) -> str:
    parts = module_name.split("_")
    return "".join(part.capitalize() for part in parts)


def _discover() -> None:
    package = __name__
    for module_info in pkgutil.iter_modules(__path__):
        if module_info.name.startswith("_"):
            continue
        module = importlib.import_module(f"{package}.{module_info.name}")
        runner = getattr(module, "run_benchmark", None)
        if runner is None:
            continue
        benchmark_name = getattr(module, "BENCHMARK_NAME", _default_benchmark_name(module_info.name))
        thread_opts = getattr(module, "THREAD_OPTIONS", None)
        mpi_opts = getattr(module, "MPI_OPTIONS", None)
        custom_metrics = getattr(module, "CUSTOM_METRICS", None)
        module_path = f"{package}.{module_info.name}"
        SCRIPT_REGISTRY[module_info.name] = (benchmark_name, module_path, thread_opts, mpi_opts, custom_metrics)


_discover()

__all__ = ['SCRIPT_REGISTRY', 'ScriptSpec']
