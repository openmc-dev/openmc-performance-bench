# Performance dashboard and regression detection

Tools for turning ASV results into a dataset for the dashboard and for detecting
sustained performance changes. Standard library only (Python 3.10+).

## Build the dataset

```sh
python dashboard/build_data.py \
    --results-dir ../openmc-performance-bench-results/results/ec2-c7i-metal-24xl \
    --output perf.json \
    --commit-cache commit_info.json
```

`perf.json` contains the commits in date order (with PR number, title and author
fetched from GitHub and cached in `commit_info.json`) and, for every
benchmark/metric/configuration, an array of values aligned with the commits.
A derived `parallel_efficiency` metric, `t(1 thread) / (cores * t(config))`, is
added for benchmarks that report transport time. Set `GH_TOKEN` to avoid GitHub
API rate limits, or pass `--offline` to skip commit lookups.

## Detect regressions

```sh
python dashboard/regressions.py perf.json [--since 2026-10-01] [--json regressions.json]
```

The report has four sections: corroborated changes, uncorroborated (low
confidence) changes, results changes, and unconfirmed changes at the latest
commits.

### What is analyzed

Which series are analyzed, in what role, and how sensitively is set by
`POLICIES` in `regressions.py`. Each series has a role:

- **alert**: changes are reported, and alerted on when corroborated.
- **support**: never reported on its own, but corroborates an alert-series
  change in the same benchmark.
- **dashboard**: analyzed for display only (currently too noisy to alert on).
- **results**: deterministic values; any change means the simulation results
  changed, reported separately as information.

| Metric | Role | Configs | Min change | Notes |
|---|---|---|---|---|
| `transport_time` | alert | 1 thread | 3% | skipped if median < 0.25 s |
| `elapsed_wall` | alert | 1 thread | 3% | Python-API benchmarks only (no transport time) |
| Python-API timings (`integration_seconds`, ...) | alert | 1 thread | 3% | skipped if median < 0.25 s |
| `max_rss_kb` | alert | all | 2% | |
| `figure_of_merit` | alert | 1 thread | 5% | higher is better |
| `transport_time` | support | parallel | 3% | skipped if median < 1 s |
| `figure_of_merit` | support | parallel | 5% | |
| `total_time_elapsed` | dashboard | 1 thread | 3% | includes bimodal initialization time |
| `initialization_time` | dashboard | 1 thread | 3% | promote once nuclear data is pre-cached |
| `parallel_efficiency` | dashboard | parallel | 5% | skipped if parallel transport time < 1 s |
| `avg_rel_error`, `max_rel_error`, `pct_cells_with_tallies` | results | all | any | |

### How changes are detected

For each series (on a log scale), a change is reported when the median of the
next 3 commits differs from the median of up to 10 preceding commits by more
than both the minimum change and 4x the series' noise, and each of those 3
commits individually moved the same way. The step is then attributed to the
first commit from which values sit closer to the new level than the old one.
Noise is estimated from the median absolute difference between consecutive
commits; series noisier than 10% are reported as `noisy`.

A series with no value in the last 3 commits (e.g. a failing or removed
benchmark) is reported as `stale`: its confirmed changes are kept, but its
last values are not reported as an unconfirmed change at the latest commits.

Results series are reported whenever a value changes after at least 5
identical values. Series that return to an earlier value (e.g. tallies that
depend on thread scheduling) are reported as `nondeterministic` and ignored.

### Events and corroboration

Changes of the same kind in the same metric at the same or adjacent commits
are grouped into one **event**. When the series in an event disagree on the
commit, all candidate commits are listed. An event in a benchmark is
**corroborated** if it appears in two or more alert/support series of that
benchmark, or if the event spans three or more benchmarks. Uncorroborated
changes are shown separately; most of them are noise.

## Dashboard site

`site/` is a static page (plain HTML/CSS/ES modules, no build step or
dependencies) that reads `data/perf.json` and `data/regressions.json`. To
build and preview it:

```sh
python dashboard/build_site.py \
    --results-dir ../openmc-performance-bench-results/results/ec2-c7i-metal-24xl \
    --output _site --commit-cache commit_info.json
python -m http.server --directory _site
```

It has three views:

- **Overview**: recent detected changes (low-confidence ones collapsed) and a
  table of every benchmark with its status, latest 1-thread time and memory,
  change vs. the previous 10 commits (grey when within the series' noise), and
  a trend line.
- **Benchmark** (`#/benchmark/<name>?metric=<metric>`): one chart per
  thread/MPI configuration, each on its own scale, with detected changes
  marked; hover for commit details, click a point to open that commit.
- **Commit** (`#/commit/<sha>`): every benchmark at one commit compared with
  its baseline, ordered by how unusual the change is for that series.

The site expects the full ASV report to be published alongside it at `asv/`.

## Tests

```sh
cd dashboard && python -m unittest -v
```
