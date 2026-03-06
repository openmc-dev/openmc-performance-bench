# OpenMC Performance Benchmark Suite

This repository contains an [Airspeed Velocity (ASV)](https://asv.readthedocs.io/) benchmark suite for tracking OpenMC performance across commits. It runs a collection of OpenMC models and records timing and memory metrics for each.

## Requirements

- Python with ASV installed (`pip install asv`)
- GNU `time` at `/usr/bin/time` (standard on Linux; macOS users may need `brew install gnu-time`)
- CMake (for building OpenMC from source when not using an existing environment)
- Optional: `mpirun` or `mpiexec` on `PATH` for MPI benchmarks

## Running the Benchmarks

### For a specific OpenMC commit

To benchmark the tip of the `develop` branch:

```sh
asv run develop^!
```

The `^!` suffix is a git range shorthand meaning "just this single commit." Without it, ASV would attempt to benchmark the entire commit history reachable from `develop`. ASV will clone the OpenMC repository, build it from source using CMake, and run all benchmarks.

To benchmark a specific commit hash:

```sh
asv run <commit-hash>^!
```

To benchmark a range of commits (e.g., for regression hunting):

```sh
asv run <older-hash>..<newer-hash>
```

### Using an existing OpenMC installation

If OpenMC is already built and installed in a Python environment, you can skip the build step entirely using ASV's `existing` environment type:

```sh
asv run --environment existing <commit-hash>^!
```

The commit hash is used only to label the results — ASV will not check out or build anything. To find the hash of your installed OpenMC:

```sh
# From the OpenMC source directory you built from:
git -C /path/to/openmc rev-parse HEAD
```

If the Python interpreter with OpenMC installed is not the default `python`, specify it explicitly:

```sh
asv run --environment existing:python=/path/to/python <commit-hash>^!
```

### Running a single benchmark

Use `-b` with the benchmark class name to run just one model:

```sh
asv run develop^! -b InfiniteMediumEigenvalue
```

The `-b` argument is a regex matched against the full benchmark name, which has the form `ClassName.track_method_name`. You can target a specific metric:

```sh
asv run develop^! -b InfiniteMediumEigenvalue.track_transport_time
```

Or match a group of benchmarks with a partial pattern:

```sh
asv run develop^! -b Nested        # runs NestedCylinders, NestedSpheres, NestedTorii
asv run develop^! -b track_transport_time  # that metric only, across all benchmarks
```

### Other useful flags

- `--quick` — Run fewer samples for a faster (less precise) result
- `--show-stderr` — Print OpenMC stdout/stderr during the run

### Viewing results

After running benchmarks, generate and open the HTML report:

```sh
asv publish
asv preview
```

Results are stored in `.asv/results/` as JSON files and can be compared across commits.

## How Performance Data is Collected

Each benchmark runs OpenMC under GNU `time -v`, which provides system-level resource metrics. OpenMC's own timing output is also captured and parsed. The following metrics are recorded for every benchmark:

**From GNU `time -v`:**

| Metric | Description |
|---|---|
| `track_elapsed_wall` | Total wall-clock time (seconds) |
| `track_user_cpu` | User-space CPU time (seconds) |
| `track_system_cpu` | Kernel-space CPU time (seconds) |
| `track_max_rss_kb` | Peak resident memory usage (KB) |
| `track_cpu_percent` | CPU utilization (%) |

**From OpenMC stdout:**

| Metric | Description |
|---|---|
| `track_total_time_elapsed` | OpenMC's reported total elapsed time (seconds) |
| `track_initialization_time` | Time spent in initialization phase (seconds) |
| `track_transport_time` | Time spent in particle transport (seconds) |
| `track_calc_rate_inactive` | Particle rate during inactive batches (particles/second) |
| `track_calc_rate_active` | Particle rate during active batches (particles/second) |

### Parametrization

Each benchmark is run under multiple configurations automatically:

- **Threads:** 1 and 2 OpenMP threads (sets both `OMP_NUM_THREADS` and `OPENMC_THREADS`)
- **MPI:** No MPI, and 2 MPI ranks if `mpirun`/`mpiexec` is on `PATH` and OpenMC was built with MPI support

The active configurations are detected at import time in [benchmarks/config.py](benchmarks/config.py).

### Caching

For a given commit, ASV calls `setup_cache()` once per thread/MPI configuration, which runs the full OpenMC simulation and stores the result. The individual `track_*` methods then simply extract values from the cached result — they do not re-run the simulation.

## Adding a New Benchmark

Benchmarks are discovered automatically from the [benchmarks/models/](benchmarks/models/) directory. To add a new one:

1. Create a new file in `benchmarks/models/`, e.g. `benchmarks/models/my_model.py`.

2. Define a `build_model()` function that returns an `openmc.Model`:

   ```python
   import openmc

   BENCHMARK_NAME = "MyModel"  # Optional: defaults to CamelCase of filename

   def build_model() -> openmc.Model:
       # ... define materials, geometry, settings ...
       return openmc.Model(geometry=geometry, settings=settings)
   ```

3. That's it. The model will be discovered automatically and a benchmark class will be generated for it.

**Optional module-level attributes:**

| Attribute | Type | Description |
|---|---|---|
| `BENCHMARK_NAME` | `str` | Display name in ASV (defaults to CamelCase of filename) |
| `THREAD_OPTIONS` | `tuple[int, ...]` | Override thread counts, e.g. `(1, 4, 8)` |
| `MPI_OPTIONS` | `tuple[int \| None, ...]` | Override MPI ranks, e.g. `(None, 4)` |

If `THREAD_OPTIONS` or `MPI_OPTIONS` are omitted, the global defaults from [benchmarks/config.py](benchmarks/config.py) are used.

**Private modules** (filenames starting with `_`) are ignored by the auto-discovery system and can be used for shared helpers.

## Repository Structure

```
benchmarks/
├── benchmarks.py          # Entry point: registers all benchmark classes with ASV
├── config.py              # Global defaults for threads/MPI, auto-detection logic
├── openmc_runner.py       # Runs OpenMC under time -v and parses output
├── models/
│   ├── __init__.py        # Auto-discovery: scans for build_model() functions
│   ├── infinite_medium.py # Simple eigenvalue benchmark
│   ├── nested_cylinders.py
│   ├── nested_spheres.py
│   ├── nested_torii.py
│   ├── hex_lattices.py
│   ├── rect_lattices.py
│   ├── cross_section_lookups.py
│   ├── urr.py
│   ├── many_cells.py
│   ├── regular_mesh_source.py
│   ├── cylindrical_mesh_source.py
│   ├── spherical_mesh_source.py
│   ├── point_cloud.py
│   └── mesh_domain_rejection.py
└── suites/
    └── base.py            # Base benchmark class and make_benchmark() factory
asv.conf.json              # ASV configuration (repo URL, build commands, branches)
```

## Available Benchmarks

| Benchmark | Description |
|---|---|
| `InfiniteMediumEigenvalue` | Simple UO2 sphere eigenvalue problem |
| `NestedCylinders` | 100 concentric cylindrical shells; tests distance-to-boundary |
| `NestedSpheres` | 100 concentric spherical shells; tests distance-to-boundary |
| `NestedTorii` | 100 concentric toroidal shells; tests complex surface intersection |
| `HexLattices` | Nested hexagonal lattices; tests hex lattice navigation |
| `RectLattices` | Nested 3D rectangular lattices; tests rect lattice navigation |
| `CrossSectionLookups` | 200+ nuclides (actinides + fission products); stresses cross-section lookup |
| `URR` | ICSBEP IEU-MET-FAST-007 Case 4; realistic model with unresolved resonance region |
| `ManyCells` | Delaunay tetrahedralization of 500+ points; tests many-cell geometry |
| `RegularMeshSource` | 32³ rectangular mesh source sampling |
| `CylindricalMeshSource` | 32³ cylindrical mesh source sampling |
| `SphericalMeshSource` | 32³ spherical mesh source sampling |
| `PointCloud` | 100,000-point cloud source sampling |
| `MeshDomainRejection` | Mesh source with domain rejection constraints |
| `SimpleTokamakCSG` | Simple tokamak geometry using CSG |
| `SimpleTokamakDAGMC` | Simple tokamak geometry using DAGMC |
