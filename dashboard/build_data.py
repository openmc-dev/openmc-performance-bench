#!/usr/bin/env python3
"""
Build a compact dataset from ASV results for the dashboard and regression checks.

The output JSON has one entry per commit (ordered by commit date) and, for each
benchmark/metric/configuration, an array of values aligned with that commit list
(null where no value was recorded). A derived ``parallel_efficiency`` metric is
added for every benchmark that reports transport time:

    efficiency(config) = t(1 thread) / (cores(config) * t(config))

Commit titles, authors and PR numbers are fetched from the GitHub API and cached
so that each commit is only looked up once.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from itertools import product
from pathlib import Path

OPENMC_REPO = "openmc-dev/openmc"
SERIAL_CONFIG = "(1, None)"
EFFICIENCY_METRIC = "parallel_efficiency"


def parse_config(config: str) -> tuple[int, int | None]:
    """Parse a "(threads, mpi_procs)" parameter string."""
    threads, procs = config.strip("()").split(",")
    procs = procs.strip()
    return int(threads), (None if procs == "None" else int(procs))


def cores(config: str) -> int:
    threads, procs = parse_config(config)
    return threads * (procs or 1)


def config_labels(params: list[list[str]]) -> list[str]:
    """Return a "(threads, mpi_procs)" label for each ASV parameter combination.

    ASV stores one value per combination of all parameter axes (their
    Cartesian product, in row-major order). Current benchmarks use a single
    combined axis; older ones used separate thread and MPI axes.
    """
    if not params:
        return [SERIAL_CONFIG]
    if len(params) == 1:  # current format: [["(1, None)", "(4, None)", ...]]
        return list(params[0])
    if len(params) == 2:  # older format: [["1", "2"], ["None", "2"]]
        return [f"({t}, {m})" for t, m in product(*params)]
    raise ValueError(f"Unrecognized benchmark parameter layout: {params}")


def _clean(value):
    """Convert NaN/inf (skipped or unreported metrics) to None."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)) and math.isfinite(value):
        return value
    return None


def load_results(machine_dir: Path) -> tuple[list[dict], dict]:
    """Return (runs sorted by commit date, benchmark definitions)."""
    runs = {}
    for path in machine_dir.glob("*.json"):
        if path.name == "machine.json":
            continue
        data = json.loads(path.read_text())
        if "results" not in data or "commit_hash" not in data:
            continue
        runs[data["commit_hash"]] = data

    benchmarks_file = machine_dir.parent / "benchmarks.json"
    definitions = json.loads(benchmarks_file.read_text()) if benchmarks_file.exists() else {}
    return sorted(runs.values(), key=lambda d: d["date"]), definitions


def build_series(runs: list[dict], definitions: dict) -> tuple[dict, dict]:
    """Return ({benchmark: {metric: {config: [values]}}}, {metric: unit})."""
    n = len(runs)
    series: dict = {}
    units: dict = {}

    for i, run in enumerate(runs):
        cols = run["result_columns"]
        ri, pi = cols.index("result"), cols.index("params")
        for key, row in run["results"].items():
            # Keys have the form "benchmarks.ClassName.track_metric"
            _, bench, method = key.split(".", 2)
            metric = method.removeprefix("track_")
            units.setdefault(metric, definitions.get(key, {}).get("unit", ""))

            configs = config_labels(row[pi] or [])
            values = row[ri]
            if not isinstance(values, list):
                values = [values] * len(configs)
            if len(values) != len(configs):
                raise ValueError(
                    f"{key} in {run['commit_hash'][:8]}: {len(values)} values for "
                    f"{len(configs)} parameter combinations")

            by_config = series.setdefault(bench, {}).setdefault(metric, {})
            for config, value in zip(configs, values):
                by_config.setdefault(config, [None] * n)[i] = _clean(value)

    # Derived scaling metric from transport time
    for bench, metrics in series.items():
        transport = metrics.get("transport_time", {})
        serial = transport.get(SERIAL_CONFIG)
        if not serial:
            continue
        eff = {}
        for config, values in transport.items():
            if config == SERIAL_CONFIG:
                continue
            c = cores(config)
            eff[config] = [
                round(t1 / (c * t), 4) if t1 and t else None
                for t1, t in zip(serial, values)
            ]
        if eff:
            metrics[EFFICIENCY_METRIC] = eff
    units[EFFICIENCY_METRIC] = "fraction"

    return series, units


def fetch_commit_info(sha: str, token: str | None) -> dict | None:
    req = urllib.request.Request(
        f"https://api.github.com/repos/{OPENMC_REPO}/commits/{sha}",
        headers={"Accept": "application/vnd.github+json"},
    )
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.load(resp)
    except (urllib.error.URLError, TimeoutError) as e:
        print(f"Warning: could not fetch commit {sha[:8]}: {e}", file=sys.stderr)
        return None

    title = data["commit"]["message"].splitlines()[0]
    pr = re.search(r"\(#(\d+)\)\s*$", title)
    author = (data.get("author") or {}).get("login") or data["commit"]["author"]["name"]
    return {
        "title": title,
        "pr": int(pr.group(1)) if pr else None,
        "author": author,
    }


def commit_records(runs: list[dict], cache_path: Path | None, offline: bool) -> list[dict]:
    cache = {}
    if cache_path and cache_path.exists():
        cache = json.loads(cache_path.read_text())

    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    updated = False
    records = []
    for run in runs:
        sha = run["commit_hash"]
        if sha not in cache and not offline:
            info = fetch_commit_info(sha, token)
            if info is not None:
                cache[sha] = info
                updated = True
        info = cache.get(sha, {})
        records.append({
            "sha": sha,
            "date": datetime.fromtimestamp(run["date"] / 1000, timezone.utc)
                            .isoformat(timespec="seconds"),
            "title": info.get("title"),
            "pr": info.get("pr"),
            "author": info.get("author"),
        })

    if cache_path and updated:
        cache_path.write_text(json.dumps(cache, indent=1, sort_keys=True) + "\n")
    return records


def build_dataset(machine_dir: Path, cache_path: Path | None = None,
                  offline: bool = False) -> dict:
    runs, definitions = load_results(machine_dir)
    series, units = build_series(runs, definitions)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "machine": machine_dir.name,
        "commits": commit_records(runs, cache_path, offline),
        "units": units,
        "benchmarks": series,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--results-dir", required=True, type=Path,
                        help="ASV results directory for one machine.")
    parser.add_argument("--output", required=True, type=Path,
                        help="Path of the dataset JSON to write.")
    parser.add_argument("--commit-cache", type=Path,
                        help="JSON file caching commit titles/PRs between runs.")
    parser.add_argument("--offline", action="store_true",
                        help="Do not query GitHub for commit information.")
    args = parser.parse_args()

    dataset = build_dataset(args.results_dir, args.commit_cache, args.offline)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(dataset, separators=(",", ":")))
    n_series = sum(len(c) for m in dataset["benchmarks"].values() for c in m.values())
    print(f"Wrote {args.output}: {len(dataset['commits'])} commits, "
          f"{len(dataset['benchmarks'])} benchmarks, {n_series} series")


if __name__ == "__main__":
    main()
