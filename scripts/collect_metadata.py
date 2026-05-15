#!/usr/bin/env python3
"""
Collect build/environment metadata and inject into ASV JSON result file.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


def get_compiler_info() -> dict:
    def run(cmd):
        try:
            return subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True).strip()
        except Exception:
            return "unknown"

    return {
        "compiler": run(["gcc", "--version"]).splitlines()[0],
        "cmake": run(["cmake", "--version"]).splitlines()[0],
    }


def get_openmc_build_config(build_dir: str) -> dict:
    """Extract key CMake cache variables from the OpenMC build directory."""
    keys = {
        "CMAKE_BUILD_TYPE",
        "OpenMC_VERSION",
        "OPENMC_USE_DAGMC",
        "OPENMC_USE_LIBMESH",
        "OPENMC_USE_MPI",
        "HDF5_VERSION",
    }
    config = {}
    cache_file = Path(build_dir) / "CMakeCache.txt"
    if cache_file.exists():
        for line in cache_file.read_text().splitlines():
            for key in keys:
                if line.startswith(f"{key}:"):
                    config[key] = line.split("=", 1)[-1].strip()
    return config


def get_env_vars() -> dict:
    keys = [
        "OPENMC_CROSS_SECTIONS",
    ]
    return {k: os.environ.get(k, "") for k in keys}


def get_mpi_version() -> str:
    """Get MPI version string from mpirun."""
    try:
        output = subprocess.check_output(
            ["mpirun", "--version"],
            stderr=subprocess.STDOUT,
            text=True,
        )
        for line in output.splitlines():
            if "Version:" in line:
                return line.split(":", 1)[1].strip()
        return output.splitlines()[0].strip()
    except Exception:
        return "unknown"


def get_dagmc_version(dagmc_dir: str) -> str:
    """Read DAGMC version from cmake config file."""
    if not dagmc_dir:
        return "unknown"
    config_file = Path(dagmc_dir) / "lib" / "cmake" / "dagmc" / "DAGMCConfigVersion.cmake"
    if config_file.exists():
        for line in config_file.read_text().splitlines():
            if "PACKAGE_VERSION" in line:
                return line.split('"')[1]
    return "unknown"


def get_moab_version(moab_dir: str) -> str:
    """Read MOAB version from pkgconfig file."""
    if not moab_dir:
        return "unknown"
    pc_file = Path(moab_dir) / "lib" / "pkgconfig" / "MOAB.pc"
    if pc_file.exists():
        for line in pc_file.read_text().splitlines():
            if line.startswith("Version:"):
                return line.split(":", 1)[1].strip()
    return "unknown"


def get_libmesh_version(libmesh_dir: str) -> str:
    """Get LibMesh version from libmesh-config."""
    try:
        out = subprocess.check_output(
            [Path(libmesh_dir) / "bin" / "libmesh-config", "--version"],
            stderr=subprocess.STDOUT,
            text=True
        ).strip()
        return out
    except Exception:
        return "unknown"


def inject(results_dir: Path, metadata: dict) -> None:
    result_files = [path for path in results_dir.glob("*.json") if path.name != "machine.json"]

    if not result_files:
        print(f"Warning: no result files found in {results_dir}", file=sys.stderr)
        return

    # Get the most recently modified file
    result_files.sort(key=lambda path: path.stat().st_mtime, reverse=True)
    result_file = result_files[0]
    try:
        data = json.loads(result_file.read_text())
        data["system_metadata"] = metadata
        result_file.write_text(json.dumps(data))
        print(f"Injected metadata into '{result_file}'")
    except Exception as e:
        print(f"Failed to add metadata to '{result_file}'", file=sys.stderr)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-dir", required=True,
                        help="ASV results directory.")
    parser.add_argument("--openmc-build-dir", default="",
                        help="Path (or glob) to the OpenMC CMake build directory.")
    parser.add_argument("--dagmc-dir", default=os.environ.get("DAGMC_INSTALL_DIR", ""),
                        help="DAGMC install directory (default: $DAGMC_INSTALL_DIR).")
    parser.add_argument("--moab-dir", default=os.environ.get("MOAB_INSTALL_DIR", ""),
                        help="MOAB install directory (default: $MOAB_INSTALL_DIR).")
    parser.add_argument("--libmesh-dir", default=os.environ.get("LIBMESH_INSTALL_DIR", ""),
                        help="LibMesh install directory (default: $LIBMESH_INSTALL_DIR).")
    args = parser.parse_args()

    metadata = {
        "build": {
            **get_compiler_info(),
            "config": get_openmc_build_config(args.openmc_build_dir),
            "dependencies": {
                "dagmc": get_dagmc_version(args.dagmc_dir),
                "libmesh": get_libmesh_version(args.libmesh_dir),
                "moab": get_moab_version(args.moab_dir),
                "mpi": get_mpi_version(),
            }
        },
        "environ": get_env_vars(),
    }
    print("Metadata collected:")
    print(json.dumps(metadata, indent=2))

    inject(Path(args.results_dir), metadata)


if __name__ == "__main__":
    main()
