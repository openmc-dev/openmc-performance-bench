#!/usr/bin/env python3
"""
Detect sustained performance changes in the dashboard dataset.

Each series (benchmark, metric, configuration) is analyzed on a log scale so that
changes are relative. A change is reported when, compared with the median of the
preceding commits (the baseline), the median of the next few commits moves by
more than both a minimum relative change and a multiple of the series' own noise,
and every one of those commits individually moves in the same direction. This
requires a change to persist rather than reacting to a single noisy run, and it
attributes the change to the first commit of the step.

Noise is estimated from the median absolute difference between consecutive
commits, which is robust to the steps we are trying to find. Series whose noise
exceeds a cap are reported as "noisy" and not analyzed.

Every analyzed series has a role:

  alert      Changes are reported (and alerted on) when corroborated.
  support    Changes never stand alone, but count as corroborating evidence for
             changes in alert series of the same benchmark and commit.
  dashboard  Analyzed for display only; never alerted on (too noisy for now).
  results    Deterministic values (e.g. tally errors at a fixed seed). Any change
             means the simulation results changed, which is reported separately
             as information rather than as a regression.
"""

from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path
from statistics import median

SERIAL_CONFIG = "(1, None)"

ALERT, SUPPORT, DASHBOARD, RESULTS = "alert", "support", "dashboard", "results"


@dataclass(frozen=True)
class Policy:
    """Which series to analyze, in what role, and how sensitively."""
    metric: str
    role: str
    configs: str | tuple[str, ...] = (SERIAL_CONFIG,)  # "all", "parallel" or explicit
    higher_is_worse: bool = True
    min_change: float = 0.03        # minimum relative change to report
    min_value: float = 0.0          # skip series whose median is below this
    fallback_for: str | None = None  # only use if the benchmark has no values for this metric
    # Apply min_value to this metric of the same benchmark/config instead (e.g.
    # efficiency is only meaningful when the parallel run itself is long enough)
    min_value_metric: str | None = None


# Timings reported by the Python-API benchmarks
SCRIPT_TIMINGS = (
    "integration_seconds", "core_sec_per_mat_timestep", "operator_setup_seconds",
    "decay_spectra_seconds", "material_creation_seconds", "result_loading_seconds",
)

POLICIES = (
    # --- Alerts ---
    Policy("transport_time", ALERT, min_value=0.25),
    # Benchmarks without transport time (Python-API benchmarks, and random ray,
    # whose solver doesn't report it) use their wall time instead
    Policy("elapsed_wall", ALERT, min_value=0.25, fallback_for="transport_time"),
    *(Policy(m, ALERT, min_value=0.25) for m in SCRIPT_TIMINGS),
    Policy("max_rss_kb", ALERT, configs="all", min_change=0.02),
    Policy("figure_of_merit", ALERT, higher_is_worse=False, min_change=0.05),

    # --- Corroborating evidence only ---
    Policy("transport_time", SUPPORT, configs="parallel", min_value=1.0),
    Policy("elapsed_wall", SUPPORT, configs="parallel", min_value=1.0,
           fallback_for="transport_time"),
    Policy("figure_of_merit", SUPPORT, configs="parallel", higher_is_worse=False,
           min_change=0.05),

    # --- Dashboard only ---
    # Includes initialization time, which is bimodal (cold vs. warm file cache)
    Policy("total_time_elapsed", DASHBOARD, min_value=0.25),
    # Promote to ALERT once nuclear data is pre-cached before benchmarking
    Policy("initialization_time", DASHBOARD, min_value=0.25),
    # Promote to ALERT once parallel runs are long enough to measure scaling
    Policy("parallel_efficiency", DASHBOARD, configs="parallel", higher_is_worse=False,
           min_change=0.05, min_value=1.0, min_value_metric="transport_time"),

    # --- Results (deterministic) ---
    *(Policy(m, RESULTS, configs="all")
      for m in ("avg_rel_error", "max_rel_error", "pct_cells_with_tallies")),
)


@dataclass(frozen=True)
class Params:
    window: int = 10        # max baseline length (commits)
    min_baseline: int = 5   # min baseline length before testing for a step
    persist: int = 3        # commits a change must persist to be confirmed
    z: float = 4.0          # threshold in units of series noise
    max_noise: float = 0.10  # series noisier than this (relative sigma) are skipped
    recent: int = 10        # a confirmed change this many commits ago is "recent"
    results_tol: float = 1e-9  # relative tolerance for deterministic values


@dataclass
class Change:
    commit_index: int
    kind: str               # "regression", "improvement" or "changed"
    change: float           # relative change of step median vs baseline median
    baseline: float
    after: float


@dataclass
class SeriesResult:
    benchmark: str
    metric: str
    config: str
    role: str
    status: str             # ok, regression, improvement, possible_regression,
                            # possible_improvement, results_changed, noisy,
                            # nondeterministic, insufficient_data, too_small,
                            # stale (no value in the last `persist` commits)
    noise: float | None = None
    threshold: float | None = None
    latest_change: float | None = None
    changes: list[Change] = field(default_factory=list)


def _kind(delta: float, higher_is_worse: bool) -> str:
    worse = delta > 0 if higher_is_worse else delta < 0
    return "regression" if worse else "improvement"


def analyze_series(values: list[float | None], policy: Policy,
                   params: Params = Params()) -> SeriesResult:
    """Look for sustained steps in one value array aligned with the commit list."""
    result = SeriesResult("", policy.metric, "", policy.role, "insufficient_data")
    points = [(i, math.log(v)) for i, v in enumerate(values) if v is not None and v > 0]
    if len(points) < params.min_baseline + 1:
        return result

    idx = [i for i, _ in points]
    ys = [y for _, y in points]
    if policy.min_value and not policy.min_value_metric \
            and math.exp(median(ys)) < policy.min_value:
        result.status = "too_small"
        return result

    diffs = [abs(b - a) for a, b in zip(ys, ys[1:])]
    sigma = 1.4826 * median(diffs) / math.sqrt(2)
    threshold = max(math.log1p(policy.min_change), params.z * sigma)
    result.noise = math.expm1(sigma)
    result.threshold = math.expm1(threshold)

    def baseline(seg: int, j: int) -> list[float]:
        return ys[max(seg, j - params.window):j]

    # Latest value relative to the commits just before it
    prev = baseline(0, len(ys) - 1)
    result.latest_change = math.expm1(ys[-1] - median(prev))

    if sigma > math.log1p(params.max_noise):
        result.status = "noisy"
        return result

    def shifted(base_med: float, recent: list[float]) -> float | None:
        """Return the step size if all of `recent` moved past the threshold together."""
        d = median(recent) - base_med
        if abs(d) <= threshold:
            return None
        if all(abs(r - base_med) > threshold / 2 and (r - base_med) * d > 0 for r in recent):
            return d
        return None

    seg = 0
    j = params.min_baseline
    while j <= len(ys) - params.persist:
        base = baseline(seg, j)
        if len(base) >= params.min_baseline:
            m = median(base)
            d = shifted(m, ys[j:j + params.persist])
            if d is not None:
                after = median(ys[j:j + params.persist])
                start = _refine_start(ys, seg, j, m, after, params.persist)
                result.changes.append(Change(
                    commit_index=idx[start],
                    kind=_kind(d, policy.higher_is_worse),
                    change=math.expm1(after - m),
                    baseline=math.exp(m),
                    after=math.exp(after),
                ))
                seg = start
                j = start + params.persist
                continue
        j += 1

    # A series that stopped reporting (failing or removed benchmark) has no
    # current state: keep its confirmed changes, but don't report the old tail
    # as a pending change or the old last value as the latest one.
    if _is_stale(idx[-1], len(values), params):
        result.status = "stale"
        result.latest_change = None
        return result

    # An unconfirmed shift at the very end (fewer than `persist` commits so far)
    result.status = "ok"
    for j in range(max(seg + params.min_baseline, len(ys) - params.persist + 1), len(ys)):
        base = baseline(seg, j)
        if len(base) < params.min_baseline:
            continue
        d = shifted(median(base), ys[j:])
        if d is not None:
            result.status = "possible_" + _kind(d, policy.higher_is_worse)
            break

    if result.status == "ok" and result.changes:
        last = result.changes[-1]
        if last.commit_index >= len(values) - params.recent:
            result.status = last.kind
    return result


def _is_stale(last_index: int, n_commits: int, params: Params) -> bool:
    """True if the last value is `persist` or more commits before the latest commit."""
    return n_commits - 1 - last_index >= params.persist


def _refine_start(ys: list[float], seg: int, j: int, before: float, after: float,
                  persist: int) -> int:
    """Locate the first commit of a detected step more precisely.

    Detection at ``j`` can fire one commit early (a slightly elevated value just
    before the step) or late (shortly after a previous change, when the baseline
    is still too short to test). Return the first index from which every value
    through the confirmation window is closer to the new level than the old one.
    """
    end = j + persist  # exclusive end of the confirmation window
    for k in range(max(seg + 1, j - persist), end):
        if all(abs(y - after) < abs(y - before) for y in ys[k:end]):
            return k
    return j


def analyze_results_series(values: list[float | None], policy: Policy,
                           params: Params = Params()) -> SeriesResult:
    """Report every change in a series that is otherwise constant.

    Series that vary within their baseline (e.g. tallies that depend on thread
    scheduling) are reported as "nondeterministic" and ignored.
    """
    result = SeriesResult("", policy.metric, "", policy.role, "insufficient_data")
    points = [(i, v) for i, v in enumerate(values) if v is not None]
    if len(points) < params.min_baseline + 1:
        return result

    def same(a: float, b: float) -> bool:
        return abs(a - b) <= params.results_tol * max(abs(a), abs(b), 1e-300)

    result.status = "ok"
    run_start = 0  # start of the current run of identical values
    for k in range(1, len(points)):
        if same(points[k][1], points[k - 1][1]):
            continue
        if k - run_start >= params.min_baseline:
            before, after = points[k - 1][1], points[k][1]
            result.changes.append(Change(
                commit_index=points[k][0], kind="changed",
                change=(after - before) / before if before else math.inf,
                baseline=before, after=after,
            ))
        run_start = k

    # A deterministic series only moves when the code changes, so it never
    # returns to a value it had before; one that flips between values (or never
    # settles) depends on run-to-run effects such as thread scheduling.
    runs = list(_runs([v for _, v in points], same))
    revisits = any(same(later[0], earlier[0])
                   for i, later in enumerate(runs) for earlier in runs[:max(i - 1, 0)])
    if revisits or max(len(r) for r in runs) < params.min_baseline:
        result.status = "nondeterministic"
        result.changes = []
    elif _is_stale(points[-1][0], len(values), params):
        result.status = "stale"
    elif result.changes and result.changes[-1].commit_index >= len(values) - params.recent:
        result.status = "results_changed"
    return result


def _runs(values, same):
    """Group consecutive equal values."""
    run = [values[0]]
    for v in values[1:]:
        if same(v, run[-1]):
            run.append(v)
        else:
            yield run
            run = [v]
    yield run


def _config_selected(config: str, configs) -> bool:
    if configs == "all":
        return True
    if configs == "parallel":
        return config != SERIAL_CONFIG
    return config in configs


def _has_values(by_config: dict) -> bool:
    return any(v is not None for values in by_config.values() for v in values)


def _too_small(metrics: dict, config: str, policy: Policy) -> bool:
    if not (policy.min_value and policy.min_value_metric):
        return False
    ref = [v for v in metrics.get(policy.min_value_metric, {}).get(config, []) if v]
    return not ref or median(ref) < policy.min_value


def analyze(dataset: dict, params: Params = Params()) -> list[SeriesResult]:
    results = []
    for bench, metrics in sorted(dataset["benchmarks"].items()):
        for policy in POLICIES:
            if policy.fallback_for and _has_values(metrics.get(policy.fallback_for, {})):
                continue
            for config, values in sorted(metrics.get(policy.metric, {}).items()):
                if not _config_selected(config, policy.configs):
                    continue
                if _too_small(metrics, config, policy):
                    r = SeriesResult(bench, policy.metric, config, policy.role, "too_small")
                elif policy.role == RESULTS:
                    r = analyze_results_series(values, policy, params)
                else:
                    r = analyze_series(values, policy, params)
                r.benchmark, r.config = bench, config
                results.append(r)
    return results


# A change is corroborated if it shows up in several alert/support series of one
# benchmark, or in this many benchmarks around the same commit (as genuine code
# changes often do)
MIN_BENCHMARKS_AT_COMMIT = 3

# Steps in different series of the same underlying change can land up to this
# many commits apart (noise near the step, or commits benchmarked back-to-back),
# so changes this close together are grouped and the commits are all listed.
COMMIT_TOLERANCE = 1


def _series_entry(r: SeriesResult, c: Change) -> dict:
    return {"metric": r.metric, "config": r.config, "role": r.role,
            "commit_index": c.commit_index, "change": c.change,
            "baseline": c.baseline, "after": c.after}


def _clusters(events: list[tuple[SeriesResult, Change]]):
    """Split events (of one kind) into windows spanning COMMIT_TOLERANCE commits."""
    events = sorted(events, key=lambda e: e[1].commit_index)
    cluster: list = []
    for e in events:
        if cluster and e[1].commit_index > cluster[0][1].commit_index + COMMIT_TOLERANCE:
            yield cluster
            cluster = []
        cluster.append(e)
    if cluster:
        yield cluster


def _group(bench: str, kind: str, role: str, items: list) -> dict:
    commits = sorted({c.commit_index for _, c in items})
    return {
        "benchmark": bench, "kind": kind, "role": role,
        "commit_index": commits[0], "commit_indices": commits,
        "series": [_series_entry(r, c) for r, c in items],
    }


def group_changes(results: list[SeriesResult]) -> list[dict]:
    """Group performance changes into events and, within each, by benchmark.

    An event is a change of one kind (regression/improvement) in one metric,
    across one or more benchmarks, at the same or adjacent commits. Unrelated
    metrics (e.g. memory in one benchmark, time in another) never corroborate
    each other.

    Groups containing at least one alert series are returned with
    ``role="alert"`` and a ``corroborated`` flag; support series only add
    evidence. Changes in dashboard series are grouped separately with
    ``role="dashboard"``.
    """
    by_kind = defaultdict(lambda: defaultdict(list))
    for r in results:
        for c in r.changes:
            if r.role in (ALERT, SUPPORT, DASHBOARD):
                group = DASHBOARD if r.role == DASHBOARD else ALERT
                by_kind[group][(c.kind, r.metric)].append((r, c))

    out = []
    for (kind, metric), events in by_kind[ALERT].items():
        for cluster in _clusters(events):
            per_bench = defaultdict(list)
            for r, c in cluster:
                per_bench[r.benchmark].append((r, c))
            per_bench = {b: items for b, items in per_bench.items()
                         if any(r.role == ALERT for r, _ in items)}
            event_commits = sorted({c.commit_index for items in per_bench.values()
                                    for _, c in items})
            for bench, items in per_bench.items():
                g = _group(bench, kind, ALERT, items)
                g["metric"] = metric
                g["event_commits"] = event_commits
                g["benchmarks_at_commit"] = len(per_bench)
                g["corroborated"] = (len(items) >= 2
                                     or len(per_bench) >= MIN_BENCHMARKS_AT_COMMIT)
                out.append(g)

    for (kind, metric), events in by_kind[DASHBOARD].items():
        for cluster in _clusters(events):
            per_bench = defaultdict(list)
            for r, c in cluster:
                per_bench[r.benchmark].append((r, c))
            for b, items in per_bench.items():
                g = _group(b, kind, DASHBOARD, items)
                g["metric"] = metric
                out.append(g)

    out.sort(key=lambda g: (-g["commit_index"], g["benchmark"]))
    return out


def results_changes(results: list[SeriesResult]) -> list[dict]:
    """Group changes in deterministic results by benchmark and commit."""
    groups = defaultdict(list)
    for r in results:
        if r.role == RESULTS:
            for c in r.changes:
                groups[(r.benchmark, c.commit_index)].append(_series_entry(r, c))
    out = [{"benchmark": b, "commit_index": ci, "series": s}
           for (b, ci), s in groups.items()]
    out.sort(key=lambda g: (-g["commit_index"], g["benchmark"]))
    return out


def _commit_line(commits: list[dict], ci: int) -> tuple[str, str]:
    c = commits[ci]
    pr = f"#{c['pr']}" if c.get("pr") else ""
    return f"{c['date'][:10]} {c['sha'][:8]} {pr:7s}", c.get("title") or ""


def _series_line(s: dict) -> str:
    role = "" if s["role"] == ALERT else f"  [{s['role']}]"
    if s["change"] == math.inf:
        delta = "   new"
    elif abs(s["change"]) < 0.001:
        delta = f"{s['change']:+7.0e}"
    else:
        delta = f"{s['change']:+7.1%}"
    return (f"    {s['metric']:26s} {s['config']:11s} {delta}  "
            f"({s['baseline']:.6g} -> {s['after']:.6g}){role}")


def report(dataset: dict, results: list[SeriesResult], since: str | None = None) -> str:
    commits = dataset["commits"]
    lines = []

    counts = defaultdict(lambda: defaultdict(int))
    for r in results:
        counts[r.role][r.status] += 1
    lines.append(f"Analyzed {len(results)} series over {len(commits)} commits")
    for role in (ALERT, SUPPORT, DASHBOARD, RESULTS):
        lines.append(f"  {role:9s}: " + ", ".join(
            f"{k}={v}" for k, v in sorted(counts[role].items())))

    def in_range(ci: int) -> bool:
        return not since or commits[ci]["date"] >= since

    groups = [g for g in group_changes(results)
              if g["role"] == ALERT and in_range(g["commit_index"])]
    for title, corroborated in (("Corroborated changes", True),
                                ("Uncorroborated changes (low confidence)", False)):
        lines += ["", f"{title}:"]
        # One entry per event: a change of one kind around the same commit(s)
        events = defaultdict(list)
        for g in groups:
            if g["corroborated"] == corroborated:
                events[(tuple(g["event_commits"]), g["kind"], g["metric"])].append(g)
        if not events:
            lines.append("    none")
        for (event_commits, kind, metric), gs in sorted(events.items(),
                                                        key=lambda e: -e[0][0][0]):
            head, msg = _commit_line(commits, event_commits[0])
            lines.append(f"{head} {kind.upper()} in {metric}, {len(gs)} benchmark"
                         f"{'s' if len(gs) != 1 else ''}")
            if len(event_commits) > 1:
                lines.append("    Steps span adjacent commits; candidates:")
                for ci in event_commits:
                    h, m = _commit_line(commits, ci)
                    lines.append(f"      {h} {m}")
            elif msg:
                lines.append(f"    {msg}")
            for g in sorted(gs, key=lambda g: g["benchmark"]):
                lines.append(f"  {g['benchmark']}")
                for s in g["series"]:
                    at = (f"  at {commits[s['commit_index']]['sha'][:8]}"
                          if len(event_commits) > 1 else "")
                    lines.append(_series_line(s) + at)

    lines += ["", "Results changed (deterministic values):"]
    changed = [g for g in results_changes(results) if in_range(g["commit_index"])]
    if not changed:
        lines.append("    none")
    for g in changed:
        head, msg = _commit_line(commits, g["commit_index"])
        lines.append(f"{head} {g['benchmark']}")
        if msg:
            lines.append(f"    {msg}")
        lines += [_series_line(s) for s in g["series"]]

    pending = [r for r in results
               if r.role == ALERT and r.status.startswith("possible_")]
    if pending:
        lines += ["", "Unconfirmed changes at the latest commits:"]
        for r in pending:
            lines.append(f"    {r.status:21s} {r.benchmark} {r.metric} {r.config} "
                         f"latest {r.latest_change:+.1%}")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("dataset", type=Path, help="Dataset JSON from build_data.py.")
    parser.add_argument("--since", help="Only report changes on or after this date (YYYY-MM-DD).")
    parser.add_argument("--json", type=Path, help="Also write full results as JSON.")
    args = parser.parse_args()

    dataset = json.loads(args.dataset.read_text())
    results = analyze(dataset)
    print(report(dataset, results, args.since))

    if args.json:
        args.json.write_text(json.dumps({
            "series": [asdict(r) for r in results],
            "changes": group_changes(results),
            "results_changes": results_changes(results),
        }, indent=1))


if __name__ == "__main__":
    main()
