"""Tests for regression detection on synthetic series.

Run with:  python -m unittest discover dashboard
"""

import random
import unittest

from regressions import (POLICIES, Params, analyze, analyze_results_series,
                         analyze_series, group_changes, results_changes)

TIME = next(p for p in POLICIES if p.metric == "transport_time")
EFFICIENCY = next(p for p in POLICIES if p.metric == "parallel_efficiency")
RESULT = next(p for p in POLICIES if p.metric == "avg_rel_error")


def noisy(n, level=10.0, rel_noise=0.01, seed=0):
    rng = random.Random(seed)
    return [level * (1 + rng.gauss(0, rel_noise)) for _ in range(n)]


class AnalyzeSeries(unittest.TestCase):
    def test_flat_series_is_ok(self):
        r = analyze_series(noisy(40), TIME)
        self.assertEqual(r.status, "ok")
        self.assertEqual(r.changes, [])

    def test_step_regression_detected_at_first_commit(self):
        values = noisy(20) + noisy(20, level=11.0, seed=1)  # +10%
        r = analyze_series(values, TIME)
        self.assertEqual(len(r.changes), 1)
        c = r.changes[0]
        self.assertEqual(c.commit_index, 20)
        self.assertEqual(c.kind, "regression")
        self.assertAlmostEqual(c.change, 0.10, delta=0.02)

    def test_improvement_direction(self):
        values = noisy(20) + noisy(20, level=9.0, seed=1)
        r = analyze_series(values, TIME)
        self.assertEqual([c.kind for c in r.changes], ["improvement"])

    def test_lower_is_worse_metric(self):
        values = noisy(20, level=0.8) + noisy(20, level=0.6, seed=1)
        r = analyze_series(values, EFFICIENCY)
        self.assertEqual([c.kind for c in r.changes], ["regression"])

    def test_single_spike_ignored(self):
        values = noisy(40)
        values[25] *= 1.5
        r = analyze_series(values, TIME)
        self.assertEqual(r.changes, [])

    def test_two_commit_blip_ignored(self):
        values = noisy(40)
        values[25] *= 1.3
        values[26] *= 1.3
        r = analyze_series(values, TIME)
        self.assertEqual(r.changes, [])

    def test_change_below_min_change_ignored(self):
        values = noisy(20, rel_noise=0.001) + noisy(20, level=10.2, rel_noise=0.001, seed=1)
        r = analyze_series(values, TIME)  # +2% < 3% minimum
        self.assertEqual(r.changes, [])

    def test_threshold_scales_with_noise(self):
        # 8% step in a series with ~4% noise should not be reported
        values = noisy(20, rel_noise=0.04) + noisy(20, level=10.8, rel_noise=0.04, seed=1)
        r = analyze_series(values, TIME)
        self.assertEqual(r.changes, [])

    def test_noisy_series_skipped(self):
        r = analyze_series(noisy(40, rel_noise=0.3), TIME)
        self.assertEqual(r.status, "noisy")

    def test_missing_values_tolerated(self):
        values = noisy(20) + noisy(20, level=11.0, seed=1)
        values[5] = values[22] = None
        r = analyze_series(values, TIME)
        self.assertEqual([c.commit_index for c in r.changes], [20])

    def test_unconfirmed_change_at_end(self):
        values = noisy(30) + [11.0, 11.1]
        r = analyze_series(values, TIME)
        self.assertEqual(r.status, "possible_regression")
        self.assertEqual(r.changes, [])

    def test_recent_confirmed_change_sets_status(self):
        values = noisy(30) + noisy(5, level=11.0, seed=1)
        self.assertEqual(analyze_series(values, TIME).status, "regression")

    def test_old_change_reverts_to_ok(self):
        values = noisy(15) + noisy(30, level=11.0, seed=1)
        r = analyze_series(values, TIME, Params(recent=10))
        self.assertEqual(r.status, "ok")
        self.assertEqual(len(r.changes), 1)

    def test_two_successive_steps(self):
        values = noisy(15) + noisy(15, level=11.0, seed=1) + noisy(15, level=12.5, seed=2)
        r = analyze_series(values, TIME)
        self.assertEqual([c.commit_index for c in r.changes], [15, 30])

    def test_stale_series_not_reported_as_pending(self):
        # Measurements ended 10 commits ago (e.g. the benchmark started failing)
        r = analyze_series([10.0] * 10 + [11.0] * 2 + [None] * 10, TIME)
        self.assertEqual(r.status, "stale")
        self.assertIsNone(r.latest_change)

    def test_stale_series_keeps_confirmed_changes(self):
        values = noisy(20) + noisy(10, level=11.0, seed=1) + [None] * 5
        r = analyze_series(values, TIME)
        self.assertEqual(r.status, "stale")
        self.assertEqual([c.commit_index for c in r.changes], [20])

    def test_short_gap_at_end_still_reported(self):
        # One missing commit at the end is not enough to call the series stale
        r = analyze_series(noisy(30) + [11.0, 11.1, None], TIME)
        self.assertEqual(r.status, "possible_regression")

    def test_too_small(self):
        r = analyze_series(noisy(40, level=0.05), TIME)
        self.assertEqual(r.status, "too_small")

    def test_insufficient_data(self):
        r = analyze_series(noisy(4), TIME)
        self.assertEqual(r.status, "insufficient_data")


class AnalyzeResultsSeries(unittest.TestCase):
    def test_constant_series_ok(self):
        r = analyze_results_series([40.3] * 20, RESULT)
        self.assertEqual((r.status, r.changes), ("ok", []))

    def test_change_reported(self):
        r = analyze_results_series([40.3] * 10 + [39.9] * 10, RESULT)
        self.assertEqual([c.commit_index for c in r.changes], [10])
        self.assertEqual(r.changes[0].kind, "changed")

    def test_recent_change_sets_status(self):
        r = analyze_results_series([40.3] * 20 + [39.9] * 2, RESULT)
        self.assertEqual(r.status, "results_changed")

    def test_flip_flopping_series_is_nondeterministic(self):
        values = [92.31] * 8 + [92.30] + [92.31] * 8 + [92.30] * 3 + [92.31] * 5
        r = analyze_results_series(values, RESULT)
        self.assertEqual((r.status, r.changes), ("nondeterministic", []))

    def test_stale_results_series(self):
        r = analyze_results_series([40.3] * 10 + [39.9] * 3 + [None] * 5, RESULT)
        self.assertEqual(r.status, "stale")

    def test_varying_series_is_nondeterministic(self):
        r = analyze_results_series(noisy(20), RESULT)
        self.assertEqual(r.status, "nondeterministic")


class Analyze(unittest.TestCase):
    def dataset(self, step_benchmarks, n_benchmarks=5, parallel_time=5.0,
                step_parallel=True):
        """Benchmarks with 1- and 4-thread transport times (serial ~10 s)."""
        benchmarks = {}
        for b in range(n_benchmarks):
            level = 11.0 if b < step_benchmarks else 10.0
            serial = noisy(20, seed=b) + noisy(20, level=level, seed=100 + b)
            plevel = level if step_parallel else 10.0
            parallel = [t * parallel_time / 10.0 for t in
                        noisy(20, seed=200 + b) + noisy(20, level=plevel, seed=300 + b)]
            benchmarks[f"B{b}"] = {
                "transport_time": {"(1, None)": serial, "(4, None)": parallel},
                "parallel_efficiency": {
                    "(4, None)": [s / (4 * p) for s, p in zip(serial, parallel)]
                },
            }
        commits = [{"sha": f"{i:040x}", "date": f"2026-01-{i % 28 + 1:02d}"} for i in range(40)]
        return {"commits": commits, "benchmarks": benchmarks}

    def alert_groups(self, dataset):
        return [g for g in group_changes(analyze(dataset)) if g["role"] == "alert"]

    def test_cross_benchmark_corroboration(self):
        groups = self.alert_groups(self.dataset(step_benchmarks=3, step_parallel=False))
        self.assertEqual(len(groups), 3)
        self.assertTrue(all(g["corroborated"] for g in groups))
        self.assertTrue(all(g["benchmarks_at_commit"] == 3 for g in groups))

    def test_single_benchmark_uncorroborated(self):
        groups = self.alert_groups(self.dataset(step_benchmarks=1, step_parallel=False))
        self.assertEqual(len(groups), 1)
        self.assertFalse(groups[0]["corroborated"])

    def test_support_series_corroborates(self):
        groups = self.alert_groups(self.dataset(step_benchmarks=1))
        self.assertEqual(len(groups), 1)
        self.assertTrue(groups[0]["corroborated"])
        roles = sorted(s["role"] for s in groups[0]["series"])
        self.assertEqual(roles, ["alert", "support"])

    def test_support_only_change_not_alerted(self):
        ds = self.dataset(step_benchmarks=0)
        for b in ds["benchmarks"].values():
            p = b["transport_time"]["(4, None)"]
            b["transport_time"]["(4, None)"] = p[:20] + [v * 1.2 for v in p[20:]]
        self.assertEqual(self.alert_groups(ds), [])

    def test_short_parallel_runs_skipped(self):
        results = analyze(self.dataset(step_benchmarks=0, parallel_time=0.2))
        parallel = [r for r in results if r.config == "(4, None)"]
        self.assertTrue(parallel)
        self.assertTrue(all(r.status == "too_small" for r in parallel))

    def test_efficiency_is_dashboard_only(self):
        results = analyze(self.dataset(step_benchmarks=0))
        eff = [r for r in results if r.metric == "parallel_efficiency"]
        self.assertTrue(eff)
        self.assertTrue(all(r.role == "dashboard" for r in eff))

    def test_adjacent_commits_corroborate(self):
        ds = self.dataset(step_benchmarks=0)
        for b, start in (("B0", 20), ("B1", 21), ("B2", 20)):
            t = ds["benchmarks"][b]["transport_time"]["(1, None)"]
            ds["benchmarks"][b]["transport_time"]["(1, None)"] = \
                t[:start] + [v * 1.1 for v in t[start:]]
        groups = self.alert_groups(ds)
        self.assertEqual(len(groups), 3)
        self.assertTrue(all(g["corroborated"] for g in groups))
        self.assertTrue(all(g["event_commits"] == [20, 21] for g in groups))

    def test_different_metrics_do_not_corroborate(self):
        ds = self.dataset(step_benchmarks=1, step_parallel=False)  # B0 time step at 20
        for b in ("B1", "B2"):
            ds["benchmarks"][b]["max_rss_kb"] = {
                "(1, None)": [5e5] * 20 + [5.5e5] * 20}
        groups = self.alert_groups(ds)
        self.assertEqual(len(groups), 3)
        self.assertTrue(all(not g["corroborated"] for g in groups))

    def test_step_location_refined(self):
        # Slightly elevated value just before the step must not take the blame
        values = noisy(20, rel_noise=0.002) + noisy(20, level=11.0, rel_noise=0.002, seed=1)
        values[19] = 10.25  # beyond half the threshold, but closer to the old level
        r = analyze_series(values, TIME)
        self.assertEqual([c.commit_index for c in r.changes], [20])

    def test_wall_time_used_when_transport_time_unreported(self):
        ds = self.dataset(step_benchmarks=0)
        b = ds["benchmarks"]["B0"]
        b["transport_time"] = {"(1, None)": [None] * 40}
        b["elapsed_wall"] = {"(1, None)": noisy(20, 50.0) + noisy(20, 54.0, seed=1),
                             "(4, None)": noisy(20, 14.0, seed=2) + noisy(20, 15.1, seed=3)}
        groups = self.alert_groups(ds)
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0]["benchmark"], "B0")
        self.assertTrue(groups[0]["corroborated"])
        self.assertEqual(sorted(s["role"] for s in groups[0]["series"]), ["alert", "support"])

    def test_wall_time_not_used_when_transport_time_reported(self):
        ds = self.dataset(step_benchmarks=0)
        ds["benchmarks"]["B0"]["elapsed_wall"] = {
            "(1, None)": noisy(20, 50.0) + noisy(20, 54.0, seed=1)}
        self.assertEqual(self.alert_groups(ds), [])

    def test_results_changes_grouped(self):
        ds = self.dataset(step_benchmarks=0)
        ds["benchmarks"]["B0"]["avg_rel_error"] = {"(1, None)": [40.3] * 25 + [39.9] * 15}
        groups = results_changes(analyze(ds))
        self.assertEqual([(g["benchmark"], g["commit_index"]) for g in groups], [("B0", 25)])


if __name__ == "__main__":
    unittest.main()
