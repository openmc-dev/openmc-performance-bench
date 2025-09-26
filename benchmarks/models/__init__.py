"""Auto-discover OpenMC model builders for benchmarks."""

from __future__ import annotations

import importlib
import pkgutil
from typing import Callable, Dict, Optional, Tuple

ModelBuilder = Callable[[], "openmc.Model"]  # type: ignore[name-defined]
ModelSpec = Tuple[str, ModelBuilder, Optional[Tuple[int, ...]], Optional[Tuple[Optional[int], ...]]]

# Mapping of module name -> ModelSpec
MODEL_REGISTRY: Dict[str, ModelSpec] = {}


def _default_benchmark_name(module_name: str) -> str:
    parts = module_name.split("_")
    return "".join(part.capitalize() for part in parts)


def _discover() -> None:
    package = __name__
    for module_info in pkgutil.iter_modules(__path__):
        if module_info.name.startswith("_"):
            continue
        module = importlib.import_module(f"{package}.{module_info.name}")
        builder = getattr(module, "build_model", None)
        if builder is None:
            continue
        benchmark_name = getattr(module, "BENCHMARK_NAME", _default_benchmark_name(module_info.name))
        thread_opts = getattr(module, "THREAD_OPTIONS", None)
        mpi_opts = getattr(module, "MPI_OPTIONS", None)
        MODEL_REGISTRY[module_info.name] = (benchmark_name, builder, thread_opts, mpi_opts)


_discover()

for _module, (_benchmark_name, builder, _thread_opts, _mpi_opts) in MODEL_REGISTRY.items():
    globals()[_module] = builder

__all__ = ['MODEL_REGISTRY', 'ModelBuilder', 'ModelSpec'] + sorted(MODEL_REGISTRY)
