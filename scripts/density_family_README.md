# Stock density-family workflow

`DensityFamily` runs ten separate stock `openmc -s 1` calculations at relative
macroscopic densities 0.80, 0.85, 0.90, 0.95, 1.00, 1.05, 1.10, 1.15, 1.20 and
1.25. Each calculation initializes its own model and writes its final statepoint.
The benchmark is a workflow/performance fixture: an artificial one-group multigroup
eigenvalue model in a 10 cm vacuum cube, with flux/absorption/fission tallies. It is self-contained;
the model does not require an external cross-section library. The artificial
data are a fixture, rather than reactor-validation data.

The profiles are separate:

| Profile | Densities | Particles/batch | Batches / inactive | Same-input check |
|---|---:|---:|---|---|
| `DensityFamilySmoke` / `smoke` | 0.90, 1.10 | 128 | 8 / 2 | Repeat first input independently |
| `DensityFamily` / `performance` | All ten | 50000 | 50 / 10 | Complete-result checks per case |

Both use seed 321, one thread and one native process at a time. Both benchmark
names are auto-discovered. A full ASV suite includes the ten-case workload; select
`DensityFamilySmoke` for a small check. No CI workflow is added.

From the repository root, with a stock OpenMC executable on PATH and its matching
Python API installed:

```sh
python run_benchmark.py DensityFamilySmoke --threads 1
python run_benchmark.py DensityFamily --threads 1
```

To retain all XML, logs, statepoints and comparison receipts in a new directory:

```sh
python scripts/run_density_family.py --profile smoke --output /tmp/density-smoke
python scripts/run_density_family.py --profile performance --output /tmp/density-perf
```

The benchmark records the Python/native versions, thread count, seed, XML/XS SHA256
before transport and full numeric-array hashes. Native nonzero exits fail the run. It checks the
complete statepoint numeric datasets and attributes, including nested source-bank
fields, except the native `runtime/` timing group. Non-numeric metadata, such as
timestamps and paths, is outside this scientific numeric comparison. All numeric
fields must be finite, the expected active-batch count must be complete, and the
full response tally is checked. Smoke repeats compare every numeric array's full
bytes, dtype and shape, rather than only hashes. This is a same-input repeat check
on one fixed thread configuration; different densities have different results.

`native_cli_wall_s` sums complete child-process windows, including initialization,
transport and native output. The existing ASV/GNU-time workflow metric additionally
includes model preparation, version queries and result checks. All ten real
calculations are included; the two timings answer different questions.

The added code and generated artificial inputs are MIT-licensed; see
`benchmarks/scripts/density_family_LICENSE.txt`. This fixture needs no TAKT package,
account, binary, external data download or secrets.
