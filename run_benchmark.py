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
        help="benchmark name, e.g. PackSpheresSphere",
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

    if args.mpi_procs is not None and args.mpi_procs > 1:
        parser.error(
            "--mpi-procs greater than one requires an MPI launcher and is not "
            "supported by this in-process runner"
        )

    # Set these before importing the benchmark so libraries that inspect the
    # environment during import see the requested thread count.
    os.environ["OMP_NUM_THREADS"] = str(args.threads)
    os.environ["OPENMC_THREADS"] = str(args.threads)

    scripts = importlib.import_module("benchmarks.scripts")
    matches = [
        module_path
        for (
            benchmark_name,
            module_path,
            _configs,
            _custom_metrics,
            _return_metrics,
        ) in scripts.SCRIPT_REGISTRY.values()
        if benchmark_name == args.benchmark
    ]
    if not matches:
        parser.error(f"Python benchmark not found: {args.benchmark}")
    if len(matches) > 1:
        parser.error(f"Python benchmark name is ambiguous: {args.benchmark}")

    module_name = matches[0]
    module = importlib.import_module(module_name)
    benchmark = getattr(module, "run_benchmark", None)
    if not callable(benchmark):
        parser.error(f"{module_name} does not define a callable run_benchmark()")

    metrics = benchmark(threads=args.threads, mpi_procs=args.mpi_procs)
    if metrics is not None:
        print(json.dumps(metrics, indent=2, sort_keys=True))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
