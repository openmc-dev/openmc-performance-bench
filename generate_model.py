#!/usr/bin/env python3
"""Generate a runnable OpenMC XML model from a benchmark model.

For example::

    python generate_model.py mesh_tally_regular --output-dir /tmp

The model module is imported from ``benchmarks.models``. The output directory
contains a model XML file named after the model module.
"""

import argparse
import importlib
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate a model XML file from an OpenMC benchmark."
    )
    parser.add_argument(
        "model_name",
        help="benchmark model module name, e.g. mesh_tally_regular",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("."),
        help="directory for the generated XML (default: current directory)",
    )
    args = parser.parse_args()

    # Import the model module
    try:
        module = importlib.import_module(f"benchmarks.models.{args.model_name}")
    except ImportError as exc:
        parser.error(
            f"could not import benchmarks.models.{args.model_name}: {exc}"
        )

    # Check that build_model function exists
    if not hasattr(module, "build_model"):
        parser.error(
            f"benchmarks.models.{args.model_name} does not have a build_model() function"
        )

    # Build the model
    print(f"Building model from benchmarks.models.{args.model_name}...")
    model = module.build_model()

    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f"{args.model_name}.xml"
    print(f"Exporting to {output_file}...")
    model.export_to_model_xml(output_file)

    print(f"Successfully generated {output_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
