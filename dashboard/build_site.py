#!/usr/bin/env python3
"""
Assemble the static dashboard: copy dashboard/site/ to an output directory and
write the data it reads (data/perf.json and data/regressions.json).

Preview locally with:

    python dashboard/build_site.py --results-dir <machine results dir> --output _site
    python -m http.server --directory _site
"""

from __future__ import annotations

import argparse
import json
import math
import shutil
from dataclasses import asdict
from pathlib import Path

from build_data import build_dataset
from regressions import analyze, group_changes, results_changes

SITE_DIR = Path(__file__).parent / "site"


def _finite(obj):
    """Replace NaN/inf (not valid JSON for browsers) with None, recursively."""
    if isinstance(obj, float):
        return obj if math.isfinite(obj) else None
    if isinstance(obj, dict):
        return {k: _finite(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_finite(v) for v in obj]
    return obj


def _write_json(path: Path, obj) -> None:
    path.write_text(json.dumps(_finite(obj), separators=(",", ":"), allow_nan=False))


def build_site(results_dir: Path, output: Path, commit_cache: Path | None = None,
               offline: bool = False) -> None:
    dataset = build_dataset(results_dir, commit_cache, offline)
    if not dataset["commits"]:
        raise SystemExit(f"No benchmark results found in {results_dir}")
    results = analyze(dataset)

    output.mkdir(parents=True, exist_ok=True)
    for path in SITE_DIR.iterdir():
        if path.is_file():
            shutil.copy2(path, output / path.name)

    data_dir = output / "data"
    data_dir.mkdir(exist_ok=True)
    _write_json(data_dir / "perf.json", dataset)
    _write_json(data_dir / "regressions.json", {
        "series": [asdict(r) for r in results],
        "changes": group_changes(results),
        "results_changes": results_changes(results),
    })
    print(f"Wrote dashboard to {output} ({len(dataset['commits'])} commits)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--results-dir", required=True, type=Path,
                        help="ASV results directory for one machine.")
    parser.add_argument("--output", required=True, type=Path,
                        help="Directory to write the site into.")
    parser.add_argument("--commit-cache", type=Path,
                        help="JSON file caching commit titles/PRs between runs.")
    parser.add_argument("--offline", action="store_true",
                        help="Do not query GitHub for commit information.")
    args = parser.parse_args()
    build_site(args.results_dir, args.output, args.commit_cache, args.offline)


if __name__ == "__main__":
    main()
