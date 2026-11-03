#!/usr/bin/env python3
"""
List benchmarks that failed in this run's ASV results as Markdown.

Only result files for the given commit written at or after the given start time
are considered. A benchmark is considered failed when its recorded result is
null, or when any of its parameterized results is null. Prints nothing if no
benchmarks failed or if this run produced no results.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from collect_metadata import add_selection_args, find_result_files


def failed_benchmarks(result_file: Path) -> Counter:
    """Return a count of failed metrics keyed by benchmark class name."""
    data = json.loads(result_file.read_text())
    result_idx = data["result_columns"].index("result")

    failures = Counter()
    for name, row in data["results"].items():
        result = row[result_idx]
        if result is None or (isinstance(result, list) and None in result):
            # Names have the form "benchmarks.ClassName.track_metric"
            parts = name.split(".")
            cls = parts[1] if len(parts) > 2 else name
            failures[cls] += 1
    return failures


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    add_selection_args(parser)
    args = parser.parse_args()

    failures = Counter()
    for result_file in find_result_files(Path(args.results_dir), args.commit, args.since):
        failures.update(failed_benchmarks(result_file))

    for cls, n in sorted(failures.items()):
        print(f"- `{cls}` ({n} failed metric{'s' if n != 1 else ''})")


if __name__ == "__main__":
    main()
