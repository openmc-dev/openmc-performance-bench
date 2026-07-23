#!/usr/bin/env python3
"""Run a Python benchmark function directly in the current process."""

from __future__ import annotations

import argparse
import importlib
import json
import os
from collections.abc import Sequence


def _positive_int(value: str) -> int:
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return number


def _create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Import a module from benchmarks.scripts and call its "
            "run_benchmark() function directly."
        )
    )
    parser.add_argument(
        "benchmark",
        help="benchmark script module name, e.g. pack_spheres_sphere",
    )
    parser.add_argument(
        "--threads",
        type=_positive_int,
        default=1,
        help="number of threads to pass to the benchmark (default: 1)",
    )
    parser.add_argument(
        "--mpi-procs",
        type=_positive_int,
        help=(
            "MPI process count to pass to the benchmark; values greater than "
            "one are unsupported because this runner does not launch MPI"
        ),
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _create_parser()
    args = parser.parse_args(argv)

    if not args.benchmark.isidentifier() or args.benchmark.startswith("_"):
        parser.error("benchmark must be a public Python module name")
    if args.mpi_procs is not None and args.mpi_procs > 1:
        parser.error(
            "--mpi-procs greater than one requires an MPI launcher and is not "
            "supported by this in-process runner"
        )

    # Set these before importing the benchmark so libraries that inspect the
    # environment during import see the requested thread count.
    os.environ["OMP_NUM_THREADS"] = str(args.threads)
    os.environ["OPENMC_THREADS"] = str(args.threads)

    module_name = f"benchmarks.scripts.{args.benchmark}"
    try:
        module = importlib.import_module(module_name)
    except ModuleNotFoundError as exc:
        if exc.name == module_name:
            parser.error(f"benchmark module not found: {module_name}")
        raise

    benchmark = getattr(module, "run_benchmark", None)
    if not callable(benchmark):
        parser.error(f"{module_name} does not define a callable run_benchmark()")

    metrics = benchmark(threads=args.threads, mpi_procs=args.mpi_procs)
    if metrics is not None:
        print(json.dumps(metrics, indent=2, sort_keys=True))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
