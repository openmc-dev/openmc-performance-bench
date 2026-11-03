# SPDX-License-Identifier: MIT
# Copyright (c) 2026 TAKT contributors
# Generated with the assistance of an AI coding tool.
"""Stock CLI workflow fixture with artificial, self-contained one-group data."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import subprocess
import time
from pathlib import Path

import h5py
import numpy as np
import openmc
import openmc.mgxs

DENSITIES = (0.80, 0.85, 0.90, 0.95, 1.00, 1.05, 1.10, 1.15, 1.20, 1.25)
SEED = 321
PROFILES = {"smoke": (128, 8, 2), "performance": (50000, 50, 10)}


def build_model(xs_path, particles, batches, inactive):
    groups = openmc.mgxs.EnergyGroups([1e-5, 20e6])
    xs = openmc.XSdata("toy-fuel", groups)
    xs.order = 0
    xs.set_total([1.0])
    xs.set_absorption([0.3])
    xs.set_fission([0.15])
    xs.set_nu_fission([0.375])
    xs.set_chi([1.0])
    xs.set_scatter_matrix(np.array([[[0.7]]]))
    library = openmc.MGXSLibrary(groups)
    library.add_xsdata(xs)
    library.export_to_hdf5(str(xs_path))
    material = openmc.Material(name="Artificial one-group material")
    material.add_macroscopic("toy-fuel")
    material.set_density("macro", 1.0)
    surfaces = [
        openmc.XPlane(x0=-5, boundary_type="vacuum"),
        openmc.XPlane(x0=5, boundary_type="vacuum"),
        openmc.YPlane(y0=-5, boundary_type="vacuum"),
        openmc.YPlane(y0=5, boundary_type="vacuum"),
        openmc.ZPlane(z0=-5, boundary_type="vacuum"),
        openmc.ZPlane(z0=5, boundary_type="vacuum"),
    ]
    region = (
        +surfaces[0]
        & -surfaces[1]
        & +surfaces[2]
        & -surfaces[3]
        & +surfaces[4]
        & -surfaces[5]
    )
    cell = openmc.Cell(fill=material, region=region)
    materials = openmc.Materials([material])
    materials.cross_sections = str(xs_path)
    settings = openmc.Settings()
    settings.energy_mode = "multi-group"
    settings.run_mode = "eigenvalue"
    settings.particles, settings.batches, settings.inactive = (
        particles,
        batches,
        inactive,
    )
    settings.seed = SEED
    settings.source = openmc.IndependentSource(
        space=openmc.stats.Box((-4, -4, -4), (4, 4, 4)),
        energy=openmc.stats.Discrete([1e6], [1.0]),
    )
    settings.statepoint = {"batches": [batches]}
    settings.output = {"summary": False}
    tally = openmc.Tally(name="responses")
    tally.scores = ["flux", "absorption", "fission"]
    return openmc.Model(
        openmc.Geometry([cell]), materials, settings, openmc.Tallies([tally])
    ), material


def scientific_arrays(path):
    """Read every numeric dataset/attribute outside native runtime timing data."""
    arrays = {}

    def add(key, value):
        array = np.asarray(value)
        if array.dtype.names:
            for name in array.dtype.names:
                add(key + "." + name, array[name])
        elif array.dtype.kind in "biufc":
            if not np.all(np.isfinite(array)):
                raise ValueError("Non-finite statepoint field: " + key)
            arrays[key] = np.array(array, copy=True)

    with h5py.File(path, "r") as statepoint:

        def visit(name, item):
            if name == "runtime" or name.startswith("runtime/"):
                return
            for key, value in item.attrs.items():
                add(name + "@" + key, value)
            if isinstance(item, h5py.Dataset):
                add(name, item[()])

        visit("", statepoint)
        statepoint.visititems(visit)
    if not arrays:
        raise ValueError("No numeric scientific statepoint fields")
    return arrays


def array_record(array):
    return {
        "dtype": str(array.dtype),
        "shape": list(array.shape),
        "sha256": hashlib.sha256(array.tobytes()).hexdigest(),
    }


def run_family(output, *, profile="performance", threads=1, repeat=False):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    particles, batches, inactive = PROFILES[profile]
    densities = (0.90, 1.10) if profile == "smoke" else DENSITIES
    executable = shutil.which("openmc")
    if executable is None:
        raise FileNotFoundError("The stock openmc executable must be on PATH")
    model, material = build_model(output / "mgxs.h5", particles, batches, inactive)
    cases = []
    for index, density in enumerate(densities):
        case = output / f"density-{index:02d}"
        material.set_density("macro", density)
        model.export_to_xml(directory=case)
        cases.append((case, density))
    if repeat:
        duplicate = output / "repeat-first"
        duplicate.mkdir()
        for source in cases[0][0].glob("*.xml"):
            shutil.copyfile(source, duplicate / source.name)
        cases.append((duplicate, densities[0]))
    manifest = {
        "profile": profile,
        "python_openmc_version": openmc.__version__,
        "seed": SEED,
        "native_version": subprocess.check_output(
            [executable, "--version"], text=True
        ).strip(),
        "python_version": platform.python_version(),
        "numpy_version": np.__version__,
        "h5py_version": h5py.__version__,
        "threads": threads,
        "mpi_ranks": 1,
        "density_units": "relative macroscopic density",
        "particles": particles,
        "batches": batches,
        "inactive": inactive,
        "executable": executable,
        "xs_sha256": hashlib.sha256((output / "mgxs.h5").read_bytes()).hexdigest(),
        "inputs": {
            case.name: {
                p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                for p in sorted(case.glob("*.xml"))
            }
            for case, _ in cases
        },
        "scientific_check": "all numeric datasets/attributes except runtime/; full byte compare on same-input repeat",
    }
    if len(
        {
            manifest["inputs"][case.name]["materials.xml"]
            for case, _ in cases[: len(densities)]
        }
    ) != len(densities):
        raise ValueError("Density inputs must be distinct")
    (output / "METHOD_PRE_RUN.json").write_text(json.dumps(manifest, indent=2) + "\n")
    env = dict(os.environ, OMP_NUM_THREADS=str(threads), OPENMC_THREADS=str(threads))
    results, reference = [], None
    native_wall = 0.0
    for case, density in cases:
        started = time.perf_counter()
        with (case / "stock.log").open("wb") as log:
            subprocess.run(
                [executable, "-s", str(threads)],
                cwd=case,
                env=env,
                stdout=log,
                stderr=subprocess.STDOUT,
                check=True,
            )
        wall = time.perf_counter() - started
        native_wall += wall
        statepoint_path = case / f"statepoint.{batches}.h5"
        arrays = scientific_arrays(statepoint_path)
        with openmc.StatePoint(statepoint_path) as sp:
            if sp.n_realizations != batches - inactive or not np.isfinite(
                sp.keff.nominal_value
            ):
                raise ValueError("Incomplete eigenvalue result")
            if not np.all(np.isfinite(sp.get_tally(name="responses").mean)):
                raise ValueError("Invalid full response tally")
            keff = [sp.keff.nominal_value, sp.keff.std_dev]
        if reference is None:
            reference = arrays
        if case.name == "repeat-first":
            if arrays.keys() != reference.keys():
                raise ValueError("Repeated scientific field set changed")
            for name, array in arrays.items():
                prior = reference[name]
                if (
                    array.dtype != prior.dtype
                    or array.shape != prior.shape
                    or array.tobytes() != prior.tobytes()
                ):
                    raise ValueError("Repeated scientific array changed: " + name)
        results.append(
            {
                "case": case.name,
                "density": density,
                "native_cli_wall_s": wall,
                "keff": keff,
                "numeric_fields": {k: array_record(v) for k, v in arrays.items()},
            }
        )
    manifest.update(
        native_cli_wall_s=native_wall,
        results=results,
        repeat_requested=repeat,
        repeat_full_numeric_bytes_pass=True if repeat else None,
    )
    (output / "RESULT.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return {"native_cli_wall_s": native_wall, "completed_cases": len(cases)}
