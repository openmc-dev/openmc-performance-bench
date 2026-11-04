"""Tests for converting ASV results into the dashboard dataset.

Run with:  python -m unittest discover dashboard
"""

import math
import unittest

from build_data import build_series, config_labels

COLUMNS = ["result", "params"]


def run(results: dict, date: int = 0, sha: str = "a" * 40) -> dict:
    return {"commit_hash": sha, "date": date, "result_columns": COLUMNS,
            "results": results}


class ConfigLabels(unittest.TestCase):
    def test_current_single_axis(self):
        params = [["(1, None)", "(4, None)", "(1, 48)"]]
        self.assertEqual(config_labels(params), ["(1, None)", "(4, None)", "(1, 48)"])

    def test_older_separate_axes(self):
        # Cartesian product in row-major order (threads outer, MPI inner)
        params = [["1", "2"], ["None", "2"]]
        self.assertEqual(config_labels(params),
                         ["(1, None)", "(1, 2)", "(2, None)", "(2, 2)"])

    def test_no_params_is_serial(self):
        self.assertEqual(config_labels([]), ["(1, None)"])

    def test_unknown_layout_rejected(self):
        with self.assertRaises(ValueError):
            config_labels([["1"], ["None"], ["x"]])


class BuildSeries(unittest.TestCase):
    def test_older_format_maps_every_combination(self):
        key = "benchmarks.B.track_transport_time"
        r = run({key: [[10.0, 6.0, 5.0, 3.0], [["1", "2"], ["None", "2"]]]})
        series, _ = build_series([r], {})
        self.assertEqual(series["B"]["transport_time"], {
            "(1, None)": [10.0], "(1, 2)": [6.0], "(2, None)": [5.0], "(2, 2)": [3.0],
        })

    def test_formats_merge_into_same_series(self):
        key = "benchmarks.B.track_transport_time"
        old = run({key: [[10.0, 5.0], [["1", "2"], ["None"]]]}, date=1, sha="a" * 40)
        new = run({key: [[9.0, 4.5], [["(1, None)", "(2, None)"]]]}, date=2, sha="b" * 40)
        series, _ = build_series([old, new], {})
        self.assertEqual(series["B"]["transport_time"]["(1, None)"], [10.0, 9.0])
        self.assertEqual(series["B"]["transport_time"]["(2, None)"], [5.0, 4.5])
        # Efficiency derived for the parallel config: 9 / (2 * 4.5) = 1.0
        self.assertEqual(series["B"]["parallel_efficiency"]["(2, None)"], [1.0, 1.0])

    def test_value_count_mismatch_rejected(self):
        key = "benchmarks.B.track_transport_time"
        r = run({key: [[10.0, 5.0], [["1", "2"], ["None", "2"]]]})
        with self.assertRaises(ValueError):
            build_series([r], {})

    def test_nan_becomes_missing(self):
        key = "benchmarks.B.track_transport_time"
        r = run({key: [[math.nan], [["(1, None)"]]]})
        series, _ = build_series([r], {})
        self.assertEqual(series["B"]["transport_time"]["(1, None)"], [None])


if __name__ == "__main__":
    unittest.main()
