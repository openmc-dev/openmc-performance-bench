"""Benchmark loading depletion results and generating decay photon sources."""

from pathlib import Path
import time

from openmc.deplete import Results


BENCHMARK_NAME = "DecayPhotonSource"
RETURN_METRICS = (
    "result_loading_seconds",
    "material_creation_seconds",
    "decay_spectra_seconds",
)

_RESULTS_PATH = Path(__file__).resolve().parent / "activation_results.h5"


def run_benchmark(threads, mpi_procs):
    t0 = time.perf_counter()
    results = Results(_RESULTS_PATH)
    last_step = results[-1]
    t1 = time.perf_counter()

    materials = [
        last_step.get_material(material_id)
        for material_id in last_step.index_mat
    ]
    t2 = time.perf_counter()

    spectra = [
        material.get_decay_photon_energy()
        for material in materials
    ]
    t3 = time.perf_counter()

    return {
        "result_loading_seconds": t1 - t0,
        "material_creation_seconds": t2 - t1,
        "decay_spectra_seconds": t3 - t2,
    }
